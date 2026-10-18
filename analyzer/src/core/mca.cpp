#include <core/mca.h>

#include <format>
#include <cctype>
#include <optional>
#include <utility>


namespace {
	const std::vector<std::string> removeList = {
		".type",
		".size",
		".section",
		".ident",
		".hidden",
	};


	bool startsWith(std::string_view s, size_t pos, std::string_view prefix) {
		return pos + prefix.size() <= s.size() &&
			s.substr(pos, prefix.size()) == prefix;
	}


	struct FileDirective {
		int id;
		std::string filename;
	};


	std::optional<FileDirective> parseFileDirective(std::string_view line) {
		size_t pos = 0;
		while (pos < line.size() && std::isspace(static_cast<unsigned char>(line[pos])))
			++pos;

		if (line.substr(pos, 5) != ".file")
			return std::nullopt;
		pos += 5;
		if (pos < line.size() && !std::isspace(static_cast<unsigned char>(line[pos])))
			return std::nullopt;

		while (pos < line.size() && std::isspace(static_cast<unsigned char>(line[pos])))
			++pos;

		const size_t idStart = pos;
		while (pos < line.size() && std::isdigit(static_cast<unsigned char>(line[pos])))
			++pos;
		if (idStart == pos)
			return std::nullopt;

		const int id = std::stoi(std::string(line.substr(idStart, pos - idStart)));
		std::string filename;
		bool foundFilename = false;

		while (pos < line.size()) {
			while (pos < line.size() && std::isspace(static_cast<unsigned char>(line[pos])))
				++pos;
			if (pos >= line.size())
				break;

			if (line[pos] != '"') {
				while (pos < line.size() && !std::isspace(static_cast<unsigned char>(line[pos])))
					++pos;
				continue;
			}

			++pos;
			std::string field;
			bool closed = false;
			while (pos < line.size()) {
				const char c = line[pos++];
				if (c == '"') {
					closed = true;
					break;
				}
				if (c == '\\\\' && pos < line.size()) {
					const char next = line[pos];
					if (next == '"' || next == '\\\\') {
						field += next;
						++pos;
						continue;
					}
				}
				field += c;
			}
			if (!closed)
				return std::nullopt;

			filename = std::move(field);
			foundFilename = true;
		}

		if (!foundFilename)
			return std::nullopt;

		return FileDirective{.id = id, .filename = std::move(filename)};
	}

}


std::string_view Mca::stripComment(std::string_view line) {
	bool inString = false;
	bool escaped = false;

	for(size_t i = 0; i < line.size(); ++i) {
		char c = line[i];

		if(inString) {
			if(escaped) {
				escaped = false;
			} else if(c == '\\') {
				escaped = true;
			} else if(c == '"') {
				inString = false;
			}

			continue;
		}

		if(c == '"') {
			inString = true;
			continue;
		}

		if(startsWith(line, i, commentMarker))
			return line.substr(0, i);
	}

	return line;
}


Mca::Mca(
	const Target& target,
	const McaData& mcaData
): arg(mcaData) {
	fname = genFilePath(target);
	path = fs::path("mca") / "asm" / fname;
	path += ".s";
	isa = ISAMap.at(target.isa);
	cpuJson = readJson(( fs::path("..") / ".." / "DB" / "cpu.json" ).string());

	switch (isa) {
		case ISA::x86: case ISA::riscv: commentMarker = "#"; break;
		case ISA::arm: commentMarker = "//"; break;
		case ISA::Count: throw std::runtime_error("Mca::Mca(): ISA error");
	}

}


void Mca::run() {
	if (!fs::exists("mca/asm"))
		fs::create_directories("mca/asm");
	if (!fs::exists("mca/json"))
		fs::create_directories("mca/json");

	{
		std::ifstream ifs((fs::path("asm") / fname).string() + ".s");
		if (!ifs) throw std::runtime_error("Mca::run(): ifs");

		std::vector<std::string> lines;
		std::string line;
		while (std::getline(ifs, line))
			lines.emplace_back(line);

		// Resolve .file entries before reading .loc so marker lookup does not depend on
		// the order in which the compiler emits debug directives.
		// Both ".file id \"filename\"" and
		// ".file id \"directory\" \"filename\"" are supported.
		for (const auto& sourceLine: lines) {
			const std::string trimed = st::trim(sourceLine);
			if (!trimed.starts_with(".file")) continue;

			const auto directive = parseFileDirective(trimed);
			if (!directive || directive->id == 0) continue;

			mc.files[directive->id] = directive->filename;
		}

		std::ofstream ofs(path);
		if (!ofs) throw std::runtime_error("Mca::run(): ofs");

		for (std::string line: lines) {
			const std::string trimed = st::trim(line);

			// 除去
			bool skip = false;
			for (const auto& e: removeList) {
				if (trimed.starts_with(e)) {
					skip = true;
					break;
				}
			}
			if (skip) continue;

			// .file directives were resolved in the prepass and are not llvm-mca input.
			if (trimed.starts_with(".file")) continue;

			// marker - loc
			else if (trimed.starts_with(".loc")) {
				const auto tokens = st::tokenFromSpace(trimed);
				if (tokens.size() < 4) throw std::runtime_error("Mca::run()::marker::loc: parse error");

				const int id = st::toi(tokens[1]);
				if (id == 0) continue; // id==0は特殊なので扱わない

				const auto fileIt = mc.files.find(id);
				if (fileIt == mc.files.end()) {
					// Unknown file IDs can appear in compiler-generated debug information.
					// They are not our source markers, so preserve the .loc and keep going.
					ofs << line << "\n";
					continue;
				}

				line.clear();
				const auto& name = fileIt->second;
				if (name == "CGX-MCA-BEGIN") {
					if (llvmBegin) continue;
					llvmBegin = true;
					line = "\t" + commentMarker + " LLVM-MCA-BEGIN\n";
				} else if (name == "CGX-MCA-END") {
					if (llvmEnd) continue;
					llvmEnd = true;
					line = "\t" + commentMarker + " LLVM-MCA-END\n";
				}
			}

			ofs << line << "\n";
		}
		ofs.flush();
	}
	const std::string jsonPath = (fs::path("mca") / "json" / fname).string() + ".json";

	const std::string& llvmArch = mcaIsaMap[(size_t)isa];
	cmd(
		( BASEPATH / "external-bin" / "llvm" / "bin" / "llvm-mca" ).string() + " " +
		std::format("-march={} -mcpu={} {} {} {}", llvmArch, cpuJson["6-wide"][llvmArch].get<std::string>(),
			arg.extraArgs,
			path.string(),
			(arg.jsonMode? auto{"--json -timeline > "} + jsonPath : "")
		)
	);
}
