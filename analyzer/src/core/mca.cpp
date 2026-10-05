#include <core/mca.h>

#include <format>


namespace {
	const std::vector<std::string> removeList = {
		".type",
		".size",
		".section",
		".ident"
	};
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
}

void Mca::run() {
	if (!fs::exists("mca/asm"))
		fs::create_directories("mca/asm");
	if (!fs::exists("mca/json"))
		fs::create_directories("mca/json");

	{
		std::ifstream ifs((fs::path("asm") / fname).string() + ".s");
		std::ofstream ofs(path);
		if (!ifs) throw std::runtime_error("Mca::run(): ifs");
		if (!ofs) throw std::runtime_error("Mca::run(): ofs");

		std::string line;
		while (std::getline(ifs, line)) {
			const auto& trimed = st::trim(line);

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
				const auto& tokens = st::tokenFromSpace(trimed);

				switch (tokens.size()) {
					case 2: case 4: continue; // ここで取りたい.fileではないので無視 (root or fileNo0)
					case 3: {
						const auto& id = st::toi(tokens[1]);
						if (id == 0) continue; // 多分この場合はsize==4になるが、念のため
						mc.files[id] = tokens[2];
					} break;
					default: std::runtime_error("Mca::run()::marker::file: parse error");
				}
			}

			// marker - loc
			else if (trimed.starts_with(".loc")) {
				const auto& tokens = st::tokenFromSpace(trimed);

				if (tokens.size() < 4) std::runtime_error("Mca::run()::marker::loc: parse error");

				const auto& id = st::toi(tokens[1]);
				const auto& name = mc.files.at(id);
				if (name == "CGX_MCA_BEGIN") {
					line = "\t#LLVM-MCA-BEGIN\n" + line;
				} else if (name == "CGX_MCA_END") {
					line = "\t#LLVM-MCA-END\n" + line;
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
			(arg.jsonMode? auto{"--json > "} + jsonPath : "")
		)
	);
}
