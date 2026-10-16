#!/usr/bin/env python3
"""Aggregate Paper A timings, decompose the speedup, and draw the figures.

Reads ../results/raw_timings.jsonl, writes
  ../results/summary.csv            median time per variant, regime, n (with min and max)
  ../results/decomposition.csv      language factor, algorithm factor, and their product
  ../results/figures/fig1_time_vs_n.(png|pdf)
  ../results/figures/fig2_speedup_decomposition.(png|pdf)
  ../results/paperA_numbers.json    headline numbers quoted in the manuscript
"""
import json
import math
import os
import statistics as st
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # figstyle.py sits next to this script
import figstyle                                           # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
RES = os.path.join(HERE, "..", "results")
FIG = os.path.join(RES, "figures")
VARIANTS = ["py_naive_deque_index", "py_naive_deque_iter", "py_incremental", "rs_naive", "rs_incremental"]
LABELS = {"py_naive_deque_index": "Python simple, by position", "py_naive_deque_iter": "Python simple, stepping through",
          "py_incremental": "Python efficient", "rs_naive": "Rust simple", "rs_incremental": "Rust efficient"}
REGIME_TITLES = {"bounded": "steady traffic", "burst": "bursts"}


def load():
    rows = [json.loads(l) for l in open(os.path.join(RES, "raw_timings.jsonl"))]
    agg = {}
    for r in rows:
        agg.setdefault((r["regime"], r["variant"], r["n"]), []).append(r["ns"] / 1e6)
    summ = {}
    for (regime, v, n), times in agg.items():
        summ[(regime, v, n)] = {"median_ms": st.median(times), "min_ms": min(times),
                                "max_ms": max(times), "reps": len(times)}
    return rows, summ


def write_summary(summ):
    import csv
    with open(os.path.join(RES, "summary.csv"), "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["regime", "variant", "n", "median_ms", "min_ms", "max_ms", "reps"])
        for (regime, v, n) in sorted(summ, key=lambda k: (k[0], VARIANTS.index(k[1]), k[2])):
            s = summ[(regime, v, n)]
            w.writerow([regime, v, n, f"{s['median_ms']:.4f}", f"{s['min_ms']:.4f}",
                        f"{s['max_ms']:.4f}", s["reps"]])


def med(summ, regime, v, n):
    return summ.get((regime, v, n), {}).get("median_ms")


def decomposition(summ):
    """At each n and regime, separate the end to end naive-Python to incremental-Rust
    speedup into a language factor and an algorithm factor."""
    import csv
    rows = []
    ns = sorted({n for (reg, v, n) in summ if reg == "bounded"})
    for regime in ("bounded", "burst"):
        for n in sorted({nn for (reg, v, nn) in summ if reg == regime}):
            pn = med(summ, regime, "py_naive_deque_index", n)
            pi = med(summ, regime, "py_incremental", n)
            rn = med(summ, regime, "rs_naive", n)
            ri = med(summ, regime, "rs_incremental", n)
            row = {"regime": regime, "n": n}
            if pn and ri:
                row["endtoend_pyNaive_over_rsIncr"] = pn / ri
            if pn and pi:
                row["algorithm_naive_over_incr_python"] = pn / pi
            if rn and ri:
                row["algorithm_naive_over_incr_rust"] = rn / ri
            if pn and rn:
                row["language_py_over_rs_naive"] = pn / rn
            if pi and ri:
                row["language_py_over_rs_incr"] = pi / ri
            rows.append(row)
    cols = ["regime", "n", "endtoend_pyNaive_over_rsIncr", "algorithm_naive_over_incr_python",
            "algorithm_naive_over_incr_rust", "language_py_over_rs_naive", "language_py_over_rs_incr"]
    with open(os.path.join(RES, "decomposition.csv"), "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        for r in rows:
            w.writerow({c: (f"{r[c]:.3f}" if isinstance(r.get(c), float) else r.get(c, "")) for c in cols})
    return rows


def loglog_slope(xs, ys):
    lx = [math.log(x) for x in xs]
    ly = [math.log(y) for y in ys]
    mx, my = sum(lx) / len(lx), sum(ly) / len(ly)
    return sum((a - mx) * (b - my) for a, b in zip(lx, ly)) / sum((a - mx) ** 2 for a in lx)


def fig_time_vs_n(summ):
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(1, 2, figsize=(figstyle.WIDTH_IN, 3.8))
    for ax, regime in zip(axes, ("bounded", "burst")):
        for v, c in zip(VARIANTS, figstyle.SEQ):
            pts = sorted((n, med(summ, regime, v, n)) for (reg, vv, n) in summ if reg == regime and vv == v)
            pts = [(n, m) for n, m in pts if m]
            if pts:
                xs, ys = zip(*pts)
                ax.plot(xs, ys, marker="o", color=c, label=LABELS[v])
        ax.set_xscale("log")
        ax.set_yscale("log")
        ax.set_title(REGIME_TITLES.get(regime, regime))
        ax.set_xlabel("events processed (n)")
    axes[0].set_ylabel("median time (ms)")
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", ncol=2, fontsize=8, frameon=False)
    fig.tight_layout(rect=(0, 0.17, 1, 1))
    figstyle.save(fig, os.path.join(FIG, "fig1_time_vs_n"))


def fig_speedup(summ):
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(figstyle.WIDTH_IN, 3.9))
    series = [
        ("endtoend", "py_naive_deque_index", "rs_incremental", figstyle.OKABE["red"], "Overall (simple Python to efficient Rust)"),
        ("algorithm", "py_naive_deque_index", "py_incremental", figstyle.OKABE["orange"], "Method part (simple to efficient, Python)"),
        ("language", "py_incremental", "rs_incremental", figstyle.OKABE["blue"], "Language part (Python to Rust, efficient)"),
    ]
    for _, num, den, c, lab in series:
        pts = []
        for n in sorted({nn for (reg, v, nn) in summ if reg == "burst"}):
            a, b = med(summ, "burst", num, n), med(summ, "burst", den, n)
            if a and b:
                pts.append((n, a / b))
        if pts:
            xs, ys = zip(*pts)
            ax.plot(xs, ys, marker="o", color=c, label=lab)
    ax.axhline(1, color=figstyle.OKABE["grey"], lw=0.8, ls=":")
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel("events processed (n)")
    ax.set_ylabel("speedup factor")
    ax.set_title("Where the speedup comes from (bursts)")
    ax.legend(loc="lower right", fontsize=8)
    figstyle.save(fig, os.path.join(FIG, "fig2_speedup_decomposition"))


def main():
    os.makedirs(FIG, exist_ok=True)
    figstyle.apply()
    rows, summ = load()
    write_summary(summ)
    dec = decomposition(summ)
    fig_time_vs_n(summ)
    fig_speedup(summ)

    # headline numbers
    def big(regime):
        ns = sorted({n for (reg, v, n) in summ if reg == regime and med(summ, regime, "py_naive_deque_index", n)})
        return max(ns) if ns else None
    out = {"checksum_consistent": len({round(r["checksum"], 6) for r in rows
                                       if r["regime"] == "bounded" and r["n"] == 1000}) == 1}
    for regime in ("bounded", "burst"):
        nb = big(regime)
        if nb:
            out[regime] = {
                "n": nb,
                "endtoend_speedup": med(summ, regime, "py_naive_deque_index", nb) / med(summ, regime, "rs_incremental", nb),
                "language_speedup_incremental": (med(summ, regime, "py_incremental", nb) / med(summ, regime, "rs_incremental", nb)),
                "algorithm_speedup_python": med(summ, regime, "py_naive_deque_index", nb) / med(summ, regime, "py_incremental", nb),
            }
    # growth exponents on burst
    for v in VARIANTS:
        pts = sorted((n, med(summ, "burst", v, n)) for (reg, vv, n) in summ if reg == "burst" and vv == v)
        pts = [(n, m) for n, m in pts if m]
        if len(pts) >= 3:
            xs, ys = zip(*pts)
            out.setdefault("growth_exponent_burst", {})[v] = loglog_slope(xs, ys)
    json.dump(out, open(os.path.join(RES, "paperA_numbers.json"), "w"), indent=1)
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
