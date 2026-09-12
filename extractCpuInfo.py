import json
import csv
import os
from pathlib import Path


def get_int(data, key, default=-1):
	return data.get(key, default)


def extract_cpu_models(json_file, output_csv):
	with open(json_file, "r", encoding="utf-8") as f:
		data = json.load(f)

	records = data.get("!instanceof", {})
	sched_models = records.get("SchedMachineModel", [])

	results = []

	for model_name in sched_models:
		model_data = data.get(model_name, {})

		# 実体のあるCPUモデルだけ
		if "IssueWidth" not in model_data:
			continue

		cpu_feature = {
			"Model Name": model_name,

			# Frontend / OoO
			"Issue Width": get_int(model_data, "IssueWidth"),
			"MicroOp Buffer Size": get_int(model_data, "MicroOpBufferSize"),
			"Loop MicroOp Buffer Size": get_int(model_data, "LoopMicroOpBufferSize"),

			# Memory / latency
			"Load Latency": get_int(model_data, "LoadLatency"),
			"High Latency": get_int(model_data, "HighLatency"),
			"Mispredict Penalty": get_int(model_data, "MispredictPenalty"),

			# Model information
			"Post RA Scheduler": int(bool(model_data.get("PostRAScheduler", False))),
			"Is Complete": int(bool(model_data.get("CompleteModel", False))),
		}

		results.append(cpu_feature)

	if not results:
		return

	fieldnames = list(results[0].keys())

	with open(output_csv, "w", newline="", encoding="utf-8") as f:
		writer = csv.DictWriter(f, fieldnames=fieldnames)
		writer.writeheader()
		writer.writerows(results)

	print(f"抽出完了: {output_csv}")


if __name__ == "__main__":

	with open("config.json", "r", encoding="utf-8") as f:
		j = json.load(f)

	cd = os.getcwd()
	dataDir:Path = Path(".") / j["data-dir"] / "DB"
	dataDir.resolve()
	os.chdir(dataDir)

	os.makedirs("info", exist_ok=True)

	for isa in ["x86","arm","riscv"]:
		extract_cpu_models(
			f"llvm-ISA/{isa}.json",
			f"info/{isa}.csv"
		)

	os.chdir(cd)
