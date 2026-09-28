#include <y9inc/string.h>
#include <unordered_map>
#include "util.h"
#include <iostream>
#include <filesystem>

#include <core/countInstr.h>
#include <core/mca.h>

fs::path BASEPATH;


enum class SubCmd {
	countInstr,
	mca,
};

const std::unordered_map<std::string, SubCmd> SubCmdDict {
	{"countInstr", SubCmd::countInstr},
	{"mca", SubCmd::mca},
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

	BASEPATH = fs::current_path();

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
		case mca: {
			Mca impl(inp);
			impl.run();
		} break;
	}
}
