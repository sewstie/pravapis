"""Cold-start and warm p95 latency for api/convert.py's artifact-loading cold path.

    python scripts/measure_artifact_perf.py [--cold-runs N] [--warm-runs N]

Cold: spawns a fresh Python process per run and times wall clock from process start to
"the converter is loaded and ready to serve" — imports plus ``pickle.load`` of
data/pravapis-<hash>.bin, no YAML or TSV parsing. Warm: converts a representative
~1k-character text repeatedly in one already-warmed-up process, through the same
``pravapis.webapi.handle`` path a real request takes.

These are **local** numbers, not Vercel's: no network, no container cold boot, no
neighbour noise. They are the ceiling on what the artifact itself costs — the thing
``pravapis build-artifact`` controls — not a promise about the deployed p95. Record
them in README, "Precompiled artifact" regardless of whether the targets (cold p95 <
1.5s, warm p95 < 50ms) are met: the point is writing down what is actually true.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Final

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

COLD_DRIVER: Final[str] = r"""
import importlib.util, sys, time
t0 = time.perf_counter()
spec = importlib.util.spec_from_file_location("convert", sys.argv[1])
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
elapsed = time.perf_counter() - t0
assert mod.CONVERTER.convert("снег", __import__("pravapis").Orthography.TARASKIEVICA).text
print(elapsed)
"""


def percentile(values: list[float], p: float) -> float:
    ordered = sorted(values)
    idx = min(len(ordered) - 1, round(p * (len(ordered) - 1)))
    return ordered[idx]


def measure_cold(runs: int) -> list[float]:
    from pravapis.artifact import artifact_filename, build_artifact
    from pravapis.dataversion import compute_data_hash

    data = ROOT / "data"
    artifact = data / artifact_filename(compute_data_hash(data))
    if not artifact.is_file():
        build_artifact(data, data)

    times: list[float] = []
    for _ in range(runs):
        proc = subprocess.run(
            [sys.executable, "-c", COLD_DRIVER, str(ROOT / "api" / "convert.py")],
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=True,
            timeout=60,
        )
        times.append(float(proc.stdout.strip()))
    return times


def _warm_text() -> str:
    from pravapis.metrics import read_gold

    sentences = [n for n, _ in read_gold(ROOT / "data" / "eval" / "gold.tsv")]
    text = ""
    for s in sentences:
        text += s + " "
        if len(text) >= 1000:
            break
    return text[:1000]


def measure_warm(runs: int) -> list[float]:
    import io

    from pravapis.artifact import artifact_filename, build_artifact, load_artifact
    from pravapis.dataversion import compute_data_hash
    from pravapis.webapi import handle

    data = ROOT / "data"
    artifact_path = data / artifact_filename(compute_data_hash(data))
    if not artifact_path.is_file():
        build_artifact(data, data)
    converter = load_artifact(artifact_path).converter()

    text = _warm_text()
    body = json.dumps({"text": text}).encode("utf-8")
    headers = {"content-type": "application/json", "content-length": str(len(body))}

    for _ in range(50):  # warm up caches before timing
        handle(converter, "POST", headers, io.BytesIO(body).read)

    times: list[float] = []
    for _ in range(runs):
        t0 = time.perf_counter()
        handle(converter, "POST", headers, io.BytesIO(body).read)
        times.append(time.perf_counter() - t0)
    return times


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cold-runs", type=int, default=15)
    parser.add_argument("--warm-runs", type=int, default=500)
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    args = parser.parse_args()

    cold = measure_cold(args.cold_runs)
    warm = measure_warm(args.warm_runs)

    result = {
        "cold_runs": len(cold),
        "cold_p50_s": round(percentile(cold, 0.50), 4),
        "cold_p95_s": round(percentile(cold, 0.95), 4),
        "cold_max_s": round(max(cold), 4),
        "warm_runs": len(warm),
        "warm_p50_ms": round(percentile(warm, 0.50) * 1000, 3),
        "warm_p95_ms": round(percentile(warm, 0.95) * 1000, 3),
        "warm_max_ms": round(max(warm) * 1000, 3),
        "targets": {"cold_p95_s": 1.5, "warm_p95_ms": 50},
        "meets_cold_target": percentile(cold, 0.95) < 1.5,
        "meets_warm_target": percentile(warm, 0.95) * 1000 < 50,
    }
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(
            f"cold  ({result['cold_runs']} runs): p50 {result['cold_p50_s']:.3f}s  "
            f"p95 {result['cold_p95_s']:.3f}s  max {result['cold_max_s']:.3f}s  "
            f"(target p95 < 1.5s: {'OK' if result['meets_cold_target'] else 'MISS'})"
        )
        print(
            f"warm  ({result['warm_runs']} runs): p50 {result['warm_p50_ms']:.2f}ms  "
            f"p95 {result['warm_p95_ms']:.2f}ms  max {result['warm_max_ms']:.2f}ms  "
            f"(target p95 < 50ms: {'OK' if result['meets_warm_target'] else 'MISS'})"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
