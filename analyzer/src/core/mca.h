#pragma once

#include <util.h>

#include <array>

#include <y9inc/string.h>


namespace {
	const std::vector<std::string> removeList = {
		".type",
		".size",
		".section",
		".ident"
	};
}


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
	std::string arg;

public:
	Mca(const std::span<std::string> inp) {
		fname = generateAsmFilePath(inp[0], inp[1], inp[2]);
		if (inp.size() == 4) {
			arg = inp[3];
		} /*else if (inp.size() == 5) {
			if (inp[3] == "json") arg = "--json "
		} else if (inp.size() > 5) {
			throw std::runtime_error("input size > 5");
		}*/
		path = fs::path("mca") / "asm" / fname;
		isa = ISAMap.at(inp[1]);
		cpuJson = readJson(( fs::path("..") / ".." / "DB" / "cpu.json" ).string());
	}

	void run() {
		if (!fs::exists("mca/asm"))
			fs::create_directories("mca/asm");

		{
			std::ifstream ifs(fs::path("asm") / fname);
			std::ofstream ofs(path);
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

		const std::string& llvmArch = mcaIsaMap[(size_t)isa];
		cmd(
			( BASEPATH / "external-bin" / "llvm" / "bin" / "llvm-mca" ).string() + " " +
			std::format("-march={} -mcpu={} {} ", llvmArch, cpuJson["6-wide"][llvmArch].get<std::string>(), arg) +
			path.string()
		);
	}
};
