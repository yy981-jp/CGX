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
	Mca(const Target& target, const McaData& mcaData);
	void run();
};
