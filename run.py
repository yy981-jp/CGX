import subprocess
from enum import Enum, auto
import os
import json
import sys
from pathlib import Path


class Arch(Enum):
	X86_64 = auto()
	ARM = auto()
	RISCV = auto()

def generateCmd_gcc(arch: Arch, optLevel:int):
	arg0:str = ""
	match arch:
		case Arch.X86_64:
			arg0 = "x86_64-linux-gnu-gcc"
		case Arch.ARM:
			arg0 = "aarch64-linux-gnu-gcc"
		case Arch.RISCV:
			arg0 = "riscv64-linux-gnu-gcc"

	cmd = [
		arg0,
		"-std=c++23",
		f"-O{optLevel}",
		"-S",
		"source.cpp",
		"-o",
		f"asm/gcc-{arch.name}-O{optLevel}.s"
	]

	return cmd


def generateCmd_clang(arch: Arch, optLevel: int):
	target: str = ""

	match arch:
		case Arch.X86_64:
			target = "x86_64-linux-gnu"
		case Arch.ARM:
			target = "aarch64-linux-gnu"
		case Arch.RISCV:
			target = "riscv64-linux-gnu"

	cmd = [
		"clang++",
		"-target",
		target,
		"-std=c++23",
		f"-O{optLevel}",
		"-S",
		"source.cpp",
		"-o",
		f"asm/clang-{arch.name}-O{optLevel}.s"
	]

	return cmd


def main():
	if len(sys.argv) < 2:
		raise RuntimeError("argc < 2")

	with open("config.json", "r", encoding="utf-8") as f:
		j = json.load(f)

	cd = os.getcwd()
	dataDir:Path = Path(".") / j["data-dir"] / "experiments" / sys.argv[1]
	dataDir.resolve()
	os.chdir(dataDir)

	if not Path("asm").exists():
		os.mkdir("asm")

	# print(f"debug: {os.getcwd()}")
	
	for arch in Arch:
		for optLevel in [0,2,3]:
			subprocess.run(
				generateCmd_gcc(arch,optLevel),
				check=True
			)
			subprocess.run(
				generateCmd_clang(arch,optLevel),
				check=True
			)

	os.chdir(cd)


main()
