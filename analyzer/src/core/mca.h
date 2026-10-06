#pragma once

#include <util.h>
#include <def.h>

#include <array>

#include <y9inc/string.h>


struct Marker {
	std::unordered_map<int, std::string> files;
};

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
	Marker mc;
	std::string commentMarker;

	std::string_view stripComment(std::string_view line);

	bool llvmBegin = false, llvmEnd = false;


public:
	Mca(const Target& target, const McaData& mcaData);
	void run();
};
