#include <yy981/string.h>
#include <unordered_map>
#include "util.h"
#include <iostream>
#include <fstream>
#include <filesystem>

namespace fs = std::filesystem;



enum class SubCmd {
	countInstr
};

enum class ISA {
	x86, // 便宜上"_64"は省略する
	arm,
	riscv,
};

const std::unordered_map<std::string_view, ISA> ISAMap {
	{"ARM", ISA::arm}, {"arm", ISA::arm},
	{"X86", ISA::x86}, {"x86", ISA::x86}, {"intel", ISA::x86}, // amdはarmと見間違えそうだからやめとく
	{"riscv", ISA::riscv}, {"RISCV", ISA::riscv}
};


inline std::string generateAsmFilePath(
	const std::string compiler,
	const std::string_view isa,
	const std::string optLevel
) {
	std::string arch;
	switch ( ISAMap.at(isa) ) {
		case ISA::x86: arch = "X86_64"; break;
		case ISA::arm: arch = "ARM"; break;
		case ISA::riscv: arch = "RISCV"; break;
	}

	std::string res = compiler + "-" + arch + "-O" + optLevel + ".s";
	return res;
}


class CountInstr {
	std::stringstream content;

public:
	CountInstr(const std::span<std::string> inp) {
		if (inp.size() != 3) throw std::runtime_error("countInstr:: Three arguments are required");
		
		std::ifstream ifs( "asm/" + generateAsmFilePath(inp[0], inp[1], inp[2]) );
		if (!ifs) throw std::runtime_error("countInstr:: couldn't open file");

		content << ifs.rdbuf();
	}

	json count() {
	}
};


const std::unordered_map<std::string, SubCmd> SubCmdDict {
	{"countInstr", SubCmd::countInstr}
};

int main(int argc, char *argv[]) {
	auto inp = st::charV(argc, argv);
	if (
		(inp.size() == 2 && std::string(inp[1]) == "help")
		|| inp.size() == 1
	) {
		std::cout << "Usage: <targetName> <subCommand> ";
	}
	if (inp.size() < 3)
		throw std::runtime_error("argc < 3");

	if (fs::current_path().parent_path() == "build") {
		fs::path to = fs::current_path() / "..";
		fs::current_path( to.lexically_normal() );
	}

	const json config = readJson("config.json");
	
	fs::path targetDir = fs::path(config.at("data-dir")) / inp[1];
	if (!fs::exists(targetDir))
		throw std::runtime_error("Analyzer couldn't find targetDir");
	fs::current_path(targetDir);


	inp.erase(inp.begin(), inp.begin()+3); // subcommandに必要ない部分をそぎ落とす

	switch ( SubCmdDict.at( inp[2] ) ) {
		using enum SubCmd;
		case countInstr: {
			CountInstr impl(inp);
		} break;
	}
}
