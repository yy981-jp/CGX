#pragma once
#include <sstream>


class CountInstr {
	std::stringstream content;

public:
	CountInstr(const std::span<std::string> inp);

	void run();
};
