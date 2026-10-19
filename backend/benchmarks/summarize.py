"""Turn Locust CSV output into a markdown table: python -m benchmarks.summarize"""

import csv
import platform
import subprocess
from pathlib import Path

RESULTS = Path(__file__).parent / "results"
MODES = [("cached", "Redis cache ON"), ("uncached", "Redis cache OFF (Postgres every hit)")]


def _cpu() -> str:
    try:
        out = subprocess.run(
            ["/usr/sbin/sysctl", "-n", "machdep.cpu.brand_string"],
            capture_output=True,
            text=True,
            check=True,
        )
        return out.stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return platform.processor() or platform.machine()


def main() -> None:
    lines = [
        "| Mode | Requests | Failures | Req/s | p50 (ms) | p95 (ms) | p99 (ms) |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for mode, label in MODES:
        path = RESULTS / f"{mode}_stats.csv"
        if not path.exists():
            continue
        with path.open() as handle:
            row = next(r for r in csv.DictReader(handle) if r["Name"] == "Aggregated")
        lines.append(
            f"| {label} | {int(row['Request Count']):,} | {int(row['Failure Count']):,} "
            f"| {float(row['Requests/s']):,.0f} | {row['50%']} | {row['95%']} | {row['99%']} |"
        )
    lines.append("")
    lines.append(f"Machine: {_cpu()}, {platform.system()} {platform.release()}")
    summary = "\n".join(lines)
    (RESULTS / "summary.md").write_text(summary + "\n")
    print(summary)


if __name__ == "__main__":
    main()
