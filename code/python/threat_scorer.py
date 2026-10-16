#!/usr/bin/env python3
"""
Windowed threat scorer used as the benchmark workload for Paper A.

The scorer follows the structure of the SentinelSphere Traffic Light threat
calculator, Final = min(100, Base x Frequency x Cluster x IP x Diversity x Sustained),
computed for every incoming event over a 300 s sliding time window.

Three Python implementations compute the same scores
  naive_deque_index   rescans the window for every event, reading the deque by index
  naive_deque_iter    rescans the window for every event, iterating the deque
  incremental         keeps running counters, O(1) amortised work per event
The Rust crate in ../rust implements naive and incremental versions of the same logic.

Event streams come from a 64 bit linear congruential generator that the Rust code
reproduces bit for bit, so all implementations score identical inputs.
"""
import math
from collections import deque

WINDOW_MS = 300_000      # sliding window for all statistics
RATE_MS = 60_000         # frequency counted over the last minute
GAP_MS = 30_000          # gap that separates temporal clusters
TAU_MS = 60_000.0        # time constant of the exponential decay in the base score
NORM = 50.0              # normalisation of the decayed weight sum to a 0 to 100 scale
SEVERITY = (0.30, 0.45, 0.60, 0.70, 0.80, 0.85, 0.90, 0.95)   # per attack type
N_TYPES = len(SEVERITY)
N_IPS = 256

MASK64 = (1 << 64) - 1
LCG_A = 6364136223846793005
LCG_C = 1442695040888963407


def generate_events(n, regime, seed=20261005):
    """Return n events (t_ms, ip, attack_type, weight) from the shared LCG.

    regime 'burst'   inter arrival 0 to 2 ms, so every event stays inside the window (W grows with n)
    regime 'bounded' inter arrival 50 to 149 ms, so the window holds about 3,000 events
    """
    state = seed & MASK64

    def nxt():
        nonlocal state
        state = (state * LCG_A + LCG_C) & MASK64
        return state >> 33

    events = []
    t = 0
    for _ in range(n):
        if regime == "burst":
            t += nxt() % 3
        else:
            t += 50 + nxt() % 100
        ip = nxt() % N_IPS
        attack = nxt() % N_TYPES
        conf = 50 + nxt() % 51
        events.append((t, ip, attack, SEVERITY[attack] * conf / 100.0))
    return events


def factors(per_min, clusters, uniq_ips, n_types, sustained_ms):
    f = 1.0 if per_min <= 5 else 1.5 if per_min <= 20 else 2.0 if per_min <= 50 else 3.0
    c = 1.2 if clusters <= 1 else 1.5 if clusters == 2 else 2.0
    i = 1.5 if uniq_ips == 1 else 1.3 if uniq_ips <= 4 else 1.0
    d = 1.0 if n_types == 1 else 1.2 if n_types == 2 else 1.4 if n_types <= 4 else 1.8
    s = 2.0 if sustained_ms > 180_000 else 1.5 if sustained_ms > 120_000 else 1.2 if sustained_ms > 60_000 else 1.0
    return f * c * i * d * s


def score_from_stats(base_sum, per_min, clusters, uniq_ips, n_types, sustained_ms):
    """Return (final score capped at 100, uncapped raw score used for checksums)."""
    raw_base = 100.0 * base_sum / NORM
    mult = factors(per_min, clusters, uniq_ips, n_types, sustained_ms)
    return min(100.0, min(100.0, raw_base) * mult), raw_base * mult


# ---------------------------------------------------------------------------
# Naive rescans
# ---------------------------------------------------------------------------
def run_naive_deque_index(events):
    win = deque()
    total = 0.0
    total_raw = 0.0
    for ev in events:
        t_now = ev[0]
        win.append(ev)
        while win[0][0] <= t_now - WINDOW_MS:
            win.popleft()
        base_sum = 0.0
        per_min = 0
        ips = set()
        types = set()
        clusters = 1
        start = win[0][0]
        prev_t = start
        for i in range(len(win)):                 # O(n) deque indexing in the middle
            t, ip, attack, w = win[i]
            base_sum += w * math.exp(-(t_now - t) / TAU_MS)
            if t > t_now - RATE_MS:
                per_min += 1
            ips.add(ip)
            types.add(attack)
            if t - prev_t > GAP_MS:
                clusters += 1
                start = t
            prev_t = t
        final, raw = score_from_stats(base_sum, per_min, clusters, len(ips), len(types), t_now - start)
        total += final
        total_raw += raw
    return total, total_raw


def run_naive_deque_iter(events):
    win = deque()
    total = 0.0
    total_raw = 0.0
    for ev in events:
        t_now = ev[0]
        win.append(ev)
        while win[0][0] <= t_now - WINDOW_MS:
            win.popleft()
        base_sum = 0.0
        per_min = 0
        ips = set()
        types = set()
        clusters = 1
        start = win[0][0]
        prev_t = start
        for t, ip, attack, w in win:              # iterator access, O(1) per step
            base_sum += w * math.exp(-(t_now - t) / TAU_MS)
            if t > t_now - RATE_MS:
                per_min += 1
            ips.add(ip)
            types.add(attack)
            if t - prev_t > GAP_MS:
                clusters += 1
                start = t
            prev_t = t
        final, raw = score_from_stats(base_sum, per_min, clusters, len(ips), len(types), t_now - start)
        total += final
        total_raw += raw
    return total, total_raw


# ---------------------------------------------------------------------------
# Incremental version, O(1) amortised per event
# ---------------------------------------------------------------------------
def run_incremental(events):
    win = deque()
    minute = deque()
    ip_count = {}
    type_count = [0] * N_TYPES
    uniq_ips = 0
    n_types = 0
    gaps = 0
    cluster_start = 0
    base_sum = 0.0
    last_t = None
    total = 0.0
    total_raw = 0.0
    for ev in events:
        t_now, ip, attack, w = ev
        if last_t is not None:
            base_sum *= math.exp(-(t_now - last_t) / TAU_MS)
        # append the new event
        if win and t_now - win[-1][0] > GAP_MS:
            gaps += 1
            cluster_start = t_now
        if not win:
            cluster_start = t_now
        win.append(ev)
        minute.append(t_now)
        base_sum += w
        c = ip_count.get(ip, 0)
        if c == 0:
            uniq_ips += 1
        ip_count[ip] = c + 1
        if type_count[attack] == 0:
            n_types += 1
        type_count[attack] += 1
        # evict events that left the window
        while win[0][0] <= t_now - WINDOW_MS:
            t0, ip0, a0, w0 = win.popleft()
            base_sum -= w0 * math.exp(-(t_now - t0) / TAU_MS)
            if win and win[0][0] - t0 > GAP_MS:
                gaps -= 1
            c0 = ip_count[ip0] - 1
            ip_count[ip0] = c0
            if c0 == 0:
                uniq_ips -= 1
            type_count[a0] -= 1
            if type_count[a0] == 0:
                n_types -= 1
        while minute[0] <= t_now - RATE_MS:
            minute.popleft()
        start = cluster_start if cluster_start > win[0][0] else win[0][0]
        final, raw = score_from_stats(base_sum, len(minute), gaps + 1, uniq_ips, n_types, t_now - start)
        total += final
        total_raw += raw
        last_t = t_now
    return total, total_raw


VARIANTS = {
    "py_naive_deque_index": run_naive_deque_index,
    "py_naive_deque_iter": run_naive_deque_iter,
    "py_incremental": run_incremental,
}
