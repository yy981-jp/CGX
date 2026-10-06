#pragma once

#include <fstream>
#include <nlohmann/json.hpp>
#include <filesystem>

#include <def.h>


using json = nlohmann::json;
namespace fs = std::filesystem;

extern fs::path BASEPATH;
extern json config;


inline json readJson(const std::string& path) {
	std::ifstream ifs(path);
	if (!ifs) throw std::runtime_error(
		"readJson()::ファイルを開けませんでした: " + path);
	json j;
	ifs >> j;
	return j;
}

inline void writeJson(const json& j, const std::string& path) {
	std::ofstream ofs(path);
	if (!ofs) throw std::runtime_error(
		"writeJson()::ファイルを開けませんでした: " + path);
	ofs << j;
}

inline int cmd(const std::string& str) {
	printf("[[[cmd:\t%s]]]\n", str.c_str());
	return std::system(str.c_str());
}


enum class ISA {
	x86, // 便宜上"_64"は省略する
	arm,
	riscv,
	Count
};

const std::unordered_map<std::string_view, ISA> ISAMap {
	{"X86", ISA::x86}, {"x86", ISA::x86}, {"intel", ISA::x86}, // amdはarmと見間違えそうだからやめとく
	{"ARM", ISA::arm}, {"arm", ISA::arm},
	{"riscv", ISA::riscv}, {"RISCV", ISA::riscv}
};


inline std::string genFilePath(const Target& target) {
	std::string arch;
	switch ( ISAMap.at(target.isa) ) {
		case ISA::x86: arch = "X86_64"; break;
		case ISA::arm: arch = "ARM"; break;
		case ISA::riscv: arch = "RISCV"; break;
		default: throw std::runtime_error("generateAsmFilePath: arch");
	}

	std::string res = target.cmp + "-" + arch + "-O" + target.opt;
	return res;
}
