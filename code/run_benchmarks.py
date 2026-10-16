#!/usr/bin/env python3
"""Run the full Paper A benchmark matrix and append one JSON line per repetition
to ../results/raw_timings.jsonl. Each (variant, regime, n) runs in a fresh process.
Run from this folder:  python run_benchmarks.py   (about 40 minutes on 2 vCPUs)"""
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "results", "raw_timings.jsonl")
RUST = os.path.join(HERE, "rust", "target", "release", "threat_scorer")
PY = [sys.executable, os.path.join(HERE, "python", "bench_one.py")]

STEADY_N = [100, 500, 1000, 2000]                      # as in v3 Table 2, 50 iterations
BATCH_N = [1_000, 5_000, 10_000, 20_000, 50_000, 100_000, 1_000_000]
BOUNDED_N = [1_000, 5_000, 10_000, 50_000, 100_000, 1_000_000]

# largest n each variant is run at, per regime, to keep the matrix within about 40 minutes
CAP = {
    ("burst", "py_naive_deque_index"): 50_000, ("burst", "py_naive_deque_iter"): 50_000,
    ("burst", "rs_naive"): 100_000,
    ("bounded", "py_naive_deque_index"): 100_000, ("bounded", "py_naive_deque_iter"): 100_000,
    ("bounded", "rs_naive"): 100_000,
}
VARIANTS = ["py_naive_deque_index", "py_naive_deque_iter", "py_incremental", "rs_naive", "rs_incremental"]


def reps_for(variant, regime, n, mode):
    if mode == "steady":
        return 50
    naive = "naive" in variant
    if naive and n >= 50_000:
        return 1
    if naive and n >= 20_000 and variant.startswith("py") and regime == "burst":
        return 1
    return 3 if naive else 10


def run(variant, regime, n, reps, mode):
    cmd = ([RUST, variant, regime, str(n), str(reps)] if variant.startswith("rs")
           else PY + [variant, regime, str(n), str(reps)])
    t0 = time.time()
    out = subprocess.run(cmd, capture_output=True, text=True, check=True).stdout
    with open(OUT, "a") as fh:
        for line in out.strip().splitlines():
            rec = json.loads(line)
            rec["mode"] = mode
            fh.write(json.dumps(rec) + "\n")
    print(f"{mode:7s} {regime:8s} {variant:22s} n={n:>9,} reps={reps:>2}  {time.time() - t0:8.1f}s", flush=True)


def main():
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    plan = [("steady", "burst", v, n) for n in STEADY_N for v in VARIANTS]
    for regime, sizes in (("bounded", BOUNDED_N), ("burst", BATCH_N)):
        for n in sizes:
            for v in VARIANTS:
                if n <= CAP.get((regime, v), 10**9):
                    plan.append(("batch", regime, v, n))
    for mode, regime, v, n in plan:
        run(v, regime, n, reps_for(v, regime, n, mode), mode)


if __name__ == "__main__":
    main()
