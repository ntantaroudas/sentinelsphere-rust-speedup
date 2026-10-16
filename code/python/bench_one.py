#!/usr/bin/env python3
"""Time one Python variant in a fresh process.
Usage: python bench_one.py <variant> <burst|bounded> <n> <reps>
Prints one JSON line per repetition (time in ns, checksum, peak RSS in kB)."""
import json
import resource
import sys
import time

from threat_scorer import VARIANTS, generate_events

variant, regime, n, reps = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4])
events = generate_events(n, regime)
run = VARIANTS[variant]
for rep in range(reps):
    t0 = time.perf_counter_ns()
    total, total_raw = run(events)
    ns = time.perf_counter_ns() - t0
    print(json.dumps({"variant": variant, "regime": regime, "n": n, "rep": rep, "ns": ns,
                      "checksum": float(f"{total:.17e}"), "checksum_raw": float(f"{total_raw:.17e}"),
                      "peak_rss_kb": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss}), flush=True)
