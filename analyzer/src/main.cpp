#include <y9inc/string.h>
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

std::string debug_cd() {
	return fs::current_path().string();
}

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
		case ISA::riscv: arch = "RISC_V"; break;
	}

	std::string res = compiler + "-" + arch + "-O" + optLevel + ".s";
	return res;
}

std::vector<std::string_view> asmTokenizer(std::string_view str) {
    std::vector<std::string_view> result;

    while (true) {
        const auto begin = str.find_first_not_of(" \t");
        if (begin == std::string_view::npos)
            break;

        str.remove_prefix(begin);

        const auto end = str.find_first_of(" \t");

        if (end == std::string_view::npos) {
            result.emplace_back(str);
            break;
        }

        result.emplace_back(
			str.substr(0, end)
		);
        str.remove_prefix(end);
    }

    return result;
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

	void run() {
		std::string line_orig;
		std::unordered_map<std::string, int> stat;
		while (std::getline(content,line_orig)) {
			const auto& trimed = st::trim(line_orig);
			
			if (
				trimed.empty() ||
				trimed.starts_with(".") ||
				trimed.starts_with("//") ||
				trimed.starts_with("#")
			) continue;
			
			const auto& tokens = asmTokenizer(
				std::string_view(trimed)
			);

			for (const auto& token: tokens) {
				printf("[%s]", std::string(token).c_str());
			}
			printf("\n");

			if (tokens[0].ends_with(":")) continue;

			std::string op = std::string(tokens[0]);
			if (!stat.contains(op)) stat[op] = 0;
			stat[op]++;
		}

		printf("\n\n####################\n\n");

		for (const auto& [op,num]: stat) {
			printf("op: %s  \tnum: %d\n", op.c_str(), num);
		}
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

	if (fs::current_path().filename() == "build") {
		fs::path to = fs::current_path() / "..";
		fs::current_path( to.lexically_normal() );
	}

	const json config = readJson("config.json");
	
	fs::path targetDir = fs::path(config.at("data-dir")) / "experiments" / inp[1];
	if (!fs::exists(targetDir))
		throw std::runtime_error("Analyzer couldn't find targetDir");
	fs::current_path(targetDir);

	SubCmd subCmd = SubCmdDict.at( inp[2] );
	inp.erase(inp.begin(), inp.begin()+3); // subcommandに必要ない部分をそぎ落とす

	switch ( subCmd ) {
		using enum SubCmd;
		case countInstr: {
			CountInstr impl(inp);
			impl.run();
		} break;
	}
}
