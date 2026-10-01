#pragma once

#include <util.h>
#include <def.h>

#include <array>
#include <format>

#include <y9inc/string.h>


namespace {
	const std::vector<std::string> removeList = {
		".type",
		".size",
		".section",
		".ident"
	};
}


struct McaData {
	std::string extraArgs;
	bool jsonMode = false;
};


class Mca {
	static constexpr std::array<std::string, (size_t)ISA::Count> mcaIsaMap = {
		"x86-64",
		"aarch64",
		"riscv64",
	};

	fs::path path;
	json cpuJson;
	ISA isa;
	std::string fname;
	const McaData& arg;

public:
	Mca(
		const Target& target,
		const McaData& mcaData
	): arg(mcaData) {
		fname = genFilePath(target);
		path = fs::path("mca") / "asm" / fname;
		path += ".s";
		isa = ISAMap.at(target.isa);
		cpuJson = readJson(( fs::path("..") / ".." / "DB" / "cpu.json" ).string());
	}

	void run() {
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

				bool skip = false;
				for (const auto& e: removeList) {
					if (trimed.starts_with(e)) {
						skip = true;
						break;
					}
				}
				if (skip) continue;

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
};
