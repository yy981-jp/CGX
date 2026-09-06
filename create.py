import sys
import json
import os
from pathlib import Path


def main():
	if len(sys.argv) < 2:
		raise RuntimeError("argc < 2")

	with open("config.json", "r", encoding="utf-8") as f:
		j = json.load(f)

	dataDir:Path = Path(".") / j["data-dir"] / "experiments" / sys.argv[1]
	os.makedirs(dataDir / "asm")
	with open(dataDir / "source.cpp", "w") as f:
		pass


main()
