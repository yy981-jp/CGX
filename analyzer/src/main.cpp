#include <CLI/CLI.hpp>
#include <util.h>
#include <def.h>
#include <iostream>
#include <filesystem>

#include <core/countInstr.h>
#include <core/mca.h>


fs::path BASEPATH;
json config;


int main(int argc, char *argv[]) {
	CLI::App app{"CGX analyzer"};
	app.require_subcommand(1);

	// countInstr / mca 共通の引数 (analyzer <subCommand> <targetName> --cmp .. --isa .. --opt ..)
	Target target;
	std::vector<std::string> isaNames;
	for (const auto& [name, _]: ISAMap) isaNames.emplace_back(name);

	auto addCommonOptions = [&](CLI::App* sub) {
		sub->add_option("targetName", target.name, "experiments 以下の対象ディレクトリ名")->required();
		sub->add_option("--cmp", target.cmp, "コンパイラ (gcc / clang)")->required();
		sub->add_option("--isa", target.isa, "ISA")->required()->check(CLI::IsMember(isaNames));
		sub->add_option("--opt", target.opt, "最適化レベル (0 / 2 / 3)")->required();
	};

	// subcmd: countInstr
	auto* subCountInstr = app.add_subcommand("countInstr", "命令の出現数を集計する");
	addCommonOptions(subCountInstr);

	// subcmd: mca
	auto* subMca = app.add_subcommand("mca", "llvm-mca で解析する");
	addCommonOptions(subMca);
	McaData mcaData;
	subMca->add_option("--args", mcaData.extraArgs,
		 "llvm-mca にそのまま渡す追加引数 (例: --args=\"--timeline --json\")");
	subMca->add_flag("-j,--json", mcaData.jsonMode, "json mode");
	
	// subcmd: batchMca
	auto* subBatchMca = app.add_subcommand("batchMca", "llvm-mca で解析する (一括)");
	subBatchMca->add_option("targetName", target.name, "experiments 以下の対象ディレクトリ名")->required();

	CLI11_PARSE(app, argc, argv);

	if (fs::current_path().filename() == "build") {
		fs::path to = fs::current_path() / "..";
		fs::current_path( to.lexically_normal() );
	}

	BASEPATH = fs::current_path();

	config = readJson("config.json");

	fs::path targetDir = fs::path(config.at("data-dir")) / "experiments" / target.name;
	if (!fs::exists(targetDir))
		throw std::runtime_error("Analyzer couldn't find targetDir");
	fs::current_path(targetDir);

	if (subCountInstr->parsed()) {
		CountInstr impl(target);
		impl.run();
	} else if (subMca->parsed()) {
		Mca impl(target, mcaData);
		impl.run();
	} else if (subBatchMca->parsed()) {
		for (const auto& cmp: {"gcc","clang"}) {
			for (const std::string& isa: {"x86", "arm", "riscv"}) {
				for (const auto& opt: {"0","2","3"}) {
					Target t = {
						.name = target.name,
						.cmp = cmp,
						.isa = isa,
						.opt = opt,
					};
					Mca impl(t, {.jsonMode=true});
					impl.run();
				}
			}
		}
					
	}
}
