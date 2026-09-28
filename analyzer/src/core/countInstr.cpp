#include <core/countInstr.h>

#include <fstream>
#include <vector>

#include <util.h>
#include <y9inc/string.h>


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


CountInstr::CountInstr(const std::span<std::string> inp) {
	if (inp.size() != 3) throw std::runtime_error("countInstr:: Three arguments are required");
	
	std::ifstream ifs( "asm/" + generateAsmFilePath(inp[0], inp[1], inp[2]) );
	if (!ifs) throw std::runtime_error("countInstr:: couldn't open file");

	content << ifs.rdbuf();
}

void CountInstr::run() {
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
