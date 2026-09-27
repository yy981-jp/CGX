#pragma once

#include <util.h>

#include <array>


class Mca {
	static constexpr std::array<std::string, (size_t)ISA::Count> mcaIsaMap = {
		"x86-64",
		"aarch64",
		"riscv64",
	};

	fs::path path;
	json cpuJson;
	ISA isa;

public:
	Mca(const std::span<std::string> inp) {
		path = "asm/" + generateAsmFilePath(inp[0], inp[1], inp[2]);
		isa = ISAMap.at(inp[1]);
		cpuJson = readJson(( fs::path("..") / ".." / "DB" / "cpu.json" ).string());
	}

	void run() {
		const std::string& llvmArch = mcaIsaMap[(size_t)isa];
		cmd(
			( BASEPATH / "external-bin" / "llvm" / "bin" / "llvm-mca" ).string() + " " +
			std::format("-march={} -mcpu={} --timeline ", llvmArch, cpuJson["6-wide"][llvmArch].get<std::string>()) +
			path.string()
		);
	}
};
