import subprocess
import re
import json
from pathlib import Path


LLVM_MCA = "c:/_/llvm-dist/bin/llvm-mca"


def run_mca(triple, mcpu, asm):
    result = subprocess.run(
        [
            LLVM_MCA,
            f"--mtriple={triple}",
            f"--mcpu={mcpu}",
        ],
        input=asm,
        text=True,
        capture_output=True,
        check=True,
    )

    return result.stdout


def extract_summary(text):
    result = {}

    patterns = {
        "iterations": r"Iterations:\s+(\d+)",
        "instructions": r"Instructions:\s+(\d+)",
        "total_cycles": r"Total Cycles:\s+(\d+)",
        "dispatch_width": r"Dispatch Width:\s+(\d+)",
        "uops_per_cycle": r"uOps Per Cycle:\s+([0-9.]+)",
        "ipc": r"IPC:\s+([0-9.]+)",
        "block_rthroughput": r"Block RThroughput:\s+([0-9.]+)",
    }

    for name, pattern in patterns.items():
        m = re.search(pattern, text)
        if m:
            value = m.group(1)

            if "." in value:
                result[name] = float(value)
            else:
                result[name] = int(value)

    return result


def extract_cpu(triple, mcpu, asm):
    output = run_mca(triple, mcpu, asm)

    return {
        "triple": triple,
        "mcpu": mcpu,
        "summary": extract_summary(output),
    }


def main():
    asm = """
        add rax, rbx
        add rcx, rdx
        imul rax, rcx
    """

    cpus = [
        ("x86_64", "skylake"),
        ("x86_64", "znver4"),
    ]

    results = []

    for triple, mcpu in cpus:
        print(f"Analyzing {triple}/{mcpu}...")

        results.append(
            extract_cpu(triple, mcpu, asm)
        )

    Path("cpu_features.json").write_text(
        json.dumps(results, indent=2),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()