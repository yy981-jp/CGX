#pragma once

#include <def.h>

#include <sstream>
#include <string>


class CountInstr {
	std::stringstream content;

public:
	CountInstr(const Target& target);

	void run();
};
