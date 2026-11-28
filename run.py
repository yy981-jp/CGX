import json
import os
import subprocess
import sys
from enum import Enum, auto
from pathlib import Path


class Arch(Enum):
	X86_64 = auto()
	ARM = auto()
	RISCV = auto()


ARCH_CONFIG = {
	Arch.X86_64: ("x86-64", "x86_64-linux-gnu"),
	Arch.ARM: ("aarch64", "aarch64-linux-gnu"),
	Arch.RISCV: ("riscv64", "riscv64-linux-gnu"),
}


def compiler_command(compiler: str, arch: Arch):
	if compiler == "gcc":
		return {
			Arch.X86_64: ["x86_64-linux-gnu-g++"],
			Arch.ARM: ["aarch64-linux-gnu-g++"],
			Arch.RISCV: ["riscv64-linux-gnu-g++"],
		}[arch]

	return ["clang++", "-target", ARCH_CONFIG[arch][1]]


def select_cpu_flags(compiler, arch, candidates):
	command = compiler_command(compiler, arch)
	for flags in candidates:
		probe = subprocess.run(
			command + flags + ["-std=c++23", "-x", "c++", "-fsyntax-only", "-"],
			input="int main() {}",
			stdout=subprocess.DEVNULL,
			stderr=subprocess.PIPE,
			text=True
		)
		if probe.returncode == 0:
			return flags

		print(
			f"Skipping unsupported CPU flags for {compiler}/{arch.name}: "
			f"{' '.join(flags)}",
			file=sys.stderr
		)
		if probe.stderr.strip():
			print(probe.stderr.strip(), file=sys.stderr)

	raise RuntimeError(
		f"No supported CPU target flags for {compiler}/{arch.name}"
	)


def generate_command(compiler, arch, opt_level, cpu_flags):
	command = compiler_command(compiler, arch)
	output = f"asm/{compiler}-{arch.name}-O{opt_level}.s"

	return command + cpu_flags + [
		"-std=c++23",
		f"-O{opt_level}",
		"-g1" if compiler == "gcc" else "-gline-tables-only",
		"-S",
		"source.cpp",
		"-o",
		output
	]


def main():
	if len(sys.argv) < 2:
		raise RuntimeError("argc < 2")

	repo_dir = Path.cwd()
	with open(repo_dir / "config.json", "r", encoding="utf-8") as f:
		config = json.load(f)

	data_root = (repo_dir / config["data-dir"]).resolve()
	experiment_dir = data_root / "experiments" / sys.argv[1]
	cpu_db_path = data_root / "DB" / "cpu.json"

	with open(cpu_db_path, "r", encoding="utf-8") as f:
		cpu_db = json.load(f)

	cpu_tier = config.get("cpu-tier", "6-wide")
	if cpu_tier not in cpu_db:
		raise RuntimeError(f"Unknown CPU tier: {cpu_tier}")

	os.chdir(experiment_dir)
	Path("asm").mkdir(exist_ok=True)

	for arch in Arch:
		arch_name, _ = ARCH_CONFIG[arch]
		arch_config = cpu_db[cpu_tier][arch_name]

		for compiler in ("gcc", "clang"):
			candidates = arch_config[compiler]
			cpu_flags = select_cpu_flags(compiler, arch, candidates)
			print(
				f"{compiler}/{arch.name}: selected CPU flags: "
				f"{' '.join(cpu_flags)}"
			)

			for opt_level in (0, 2, 3):
				subprocess.run(
					generate_command(compiler, arch, opt_level, cpu_flags),
					check=True
				)


if __name__ == "__main__":
	main()
