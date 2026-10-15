#include <core/mca.h>

#include <format>


namespace {
	const std::vector<std::string> removeList = {
		".type",
		".size",
		".section",
		".ident"
	};


	bool startsWith(std::string_view s, size_t pos, std::string_view prefix) {
		return pos + prefix.size() <= s.size() &&
			s.substr(pos, prefix.size()) == prefix;
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
		for (const auto& sourceLine: lines) {
			const std::string trimed = st::trim(sourceLine);
			if (!trimed.starts_with(".file")) continue;

			const auto tokens = st::tokenFromSpace(trimed);
			if (tokens.size() != 3) continue;

			const int id = st::toi(tokens[1]);
			if (id == 0) continue;

			const std::string_view quotedName = tokens[2];
			if (quotedName.size() < 2 ||
				quotedName.front() != '"' ||
				quotedName.back() != '"') {
				continue;
			}

			mc.files[id] = std::string(quotedName.substr(1, quotedName.size() - 2));
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

			// marker - file
			if (trimed.starts_with(".file")) {
				const auto tokens = st::tokenFromSpace(trimed);

				switch (tokens.size()) {
					case 2: case 4: case 6: continue; // ここで取りたい.fileではないので無視 (root or fileNo0)
					case 3: {
						const int id = st::toi(tokens[1]);
						if (id == 0) continue; // 多分この場合はsize==6になるが、念のため
						std::string_view name_tr = tokens[2];
						if (name_tr.size() < 2 ||
							name_tr.front() != '"' ||
							name_tr.back() != '"') {
							throw std::runtime_error("Mca::run()::marker::file: invalid quoted filename");
						}
						name_tr = name_tr.substr(1, name_tr.size() - 2);
						mc.files[id] = std::string(name_tr);
					} break;
					default: throw std::runtime_error("Mca::run()::marker::file: parse error");
				}
			}

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
					ofs << line << "\\n";
					continue;
				}

				const auto& name = fileIt->second;
				if (name == "CGX-MCA-BEGIN") {
					if (llvmBegin) continue;
					llvmBegin = true;
					line = "\\t" + commentMarker + " LLVM-MCA-BEGIN\\n" + line;
				} else if (name == "CGX-MCA-END") {
					if (llvmEnd) continue;
					llvmEnd = true;
					line = "\\t" + commentMarker + " LLVM-MCA-END\\n" + line;
				}
			}

			ofs << line << "\\n";
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
			(arg.jsonMode? auto{"--json > "} + jsonPath : "")
		)
	);
}
