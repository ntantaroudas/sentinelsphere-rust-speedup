//! Windowed threat scorer (Paper A). Same logic and same event stream as
//! ../python/threat_scorer.py, so checksums can be compared across languages.
//! Usage: threat_scorer <rs_naive|rs_incremental> <burst|bounded> <n> <reps>
use std::collections::{HashMap, HashSet, VecDeque};
use std::hint::black_box;
use std::time::Instant;

const WINDOW_MS: i64 = 300_000;
const RATE_MS: i64 = 60_000;
const GAP_MS: i64 = 30_000;
const TAU_MS: f64 = 60_000.0;
const NORM: f64 = 50.0;
const SEVERITY: [f64; 8] = [0.30, 0.45, 0.60, 0.70, 0.80, 0.85, 0.90, 0.95];
const N_TYPES: usize = 8;
const N_IPS: u64 = 256;

#[derive(Clone, Copy)]
struct Event {
    t: i64,
    ip: u32,
    attack: usize,
    w: f64,
}

fn generate(n: usize, burst: bool, seed: u64) -> Vec<Event> {
    let mut state = seed;
    let mut nxt = move || {
        state = state
            .wrapping_mul(6364136223846793005)
            .wrapping_add(1442695040888963407);
        state >> 33
    };
    let mut t: i64 = 0;
    let mut v = Vec::with_capacity(n);
    for _ in 0..n {
        if burst {
            t += (nxt() % 3) as i64;
        } else {
            t += 50 + (nxt() % 100) as i64;
        }
        let ip = (nxt() % N_IPS) as u32;
        let attack = (nxt() % N_TYPES as u64) as usize;
        let conf = 50 + nxt() % 51;
        v.push(Event { t, ip, attack, w: SEVERITY[attack] * (conf as f64) / 100.0 });
    }
    v
}

fn factors(per_min: usize, clusters: usize, uniq_ips: usize, n_types: usize, sustained_ms: i64) -> f64 {
    let f = if per_min <= 5 { 1.0 } else if per_min <= 20 { 1.5 } else if per_min <= 50 { 2.0 } else { 3.0 };
    let c = if clusters <= 1 { 1.2 } else if clusters == 2 { 1.5 } else { 2.0 };
    let i = if uniq_ips == 1 { 1.5 } else if uniq_ips <= 4 { 1.3 } else { 1.0 };
    let d = if n_types == 1 { 1.0 } else if n_types == 2 { 1.2 } else if n_types <= 4 { 1.4 } else { 1.8 };
    let s = if sustained_ms > 180_000 { 2.0 } else if sustained_ms > 120_000 { 1.5 } else if sustained_ms > 60_000 { 1.2 } else { 1.0 };
    f * c * i * d * s
}

/// Returns (final score capped at 100, uncapped raw score used for checksums).
fn score(base_sum: f64, per_min: usize, clusters: usize, uniq_ips: usize, n_types: usize, sustained_ms: i64) -> (f64, f64) {
    let raw_base = 100.0 * base_sum / NORM;
    let mult = factors(per_min, clusters, uniq_ips, n_types, sustained_ms);
    ((raw_base.min(100.0) * mult).min(100.0), raw_base * mult)
}

fn run_naive(events: &[Event]) -> (f64, f64) {
    let mut win: VecDeque<Event> = VecDeque::new();
    let mut total = 0.0;
    let mut total_raw = 0.0;
    for ev in events {
        let t_now = ev.t;
        win.push_back(*ev);
        while win[0].t <= t_now - WINDOW_MS {
            win.pop_front();
        }
        let mut base_sum = 0.0;
        let mut per_min = 0usize;
        let mut ips: HashSet<u32> = HashSet::new();
        let mut types: HashSet<usize> = HashSet::new();
        let mut clusters = 1usize;
        let mut start = win[0].t;
        let mut prev_t = start;
        for i in 0..win.len() {
            // VecDeque indexing is O(1)
            let e = win[i];
            base_sum += e.w * (-((t_now - e.t) as f64) / TAU_MS).exp();
            if e.t > t_now - RATE_MS {
                per_min += 1;
            }
            ips.insert(e.ip);
            types.insert(e.attack);
            if e.t - prev_t > GAP_MS {
                clusters += 1;
                start = e.t;
            }
            prev_t = e.t;
        }
        let (fin, raw) = score(base_sum, per_min, clusters, ips.len(), types.len(), t_now - start);
        total += fin;
        total_raw += raw;
    }
    (total, total_raw)
}

fn run_incremental(events: &[Event]) -> (f64, f64) {
    let mut win: VecDeque<Event> = VecDeque::new();
    let mut minute: VecDeque<i64> = VecDeque::new();
    let mut ip_count: HashMap<u32, u32> = HashMap::new();
    let mut type_count = [0u32; N_TYPES];
    let (mut uniq_ips, mut n_types, mut gaps) = (0usize, 0usize, 0usize);
    let mut cluster_start: i64 = 0;
    let mut base_sum = 0.0f64;
    let mut last_t: Option<i64> = None;
    let mut total = 0.0;
    let mut total_raw = 0.0;
    for ev in events {
        let t_now = ev.t;
        if let Some(lt) = last_t {
            base_sum *= (-((t_now - lt) as f64) / TAU_MS).exp();
        }
        if let Some(back) = win.back() {
            if t_now - back.t > GAP_MS {
                gaps += 1;
                cluster_start = t_now;
            }
        }
        if win.is_empty() {
            cluster_start = t_now;
        }
        win.push_back(*ev);
        minute.push_back(t_now);
        base_sum += ev.w;
        let c = ip_count.entry(ev.ip).or_insert(0);
        if *c == 0 {
            uniq_ips += 1;
        }
        *c += 1;
        if type_count[ev.attack] == 0 {
            n_types += 1;
        }
        type_count[ev.attack] += 1;
        while win[0].t <= t_now - WINDOW_MS {
            let e0 = win.pop_front().unwrap();
            base_sum -= e0.w * (-((t_now - e0.t) as f64) / TAU_MS).exp();
            if let Some(head) = win.front() {
                if head.t - e0.t > GAP_MS {
                    gaps -= 1;
                }
            }
            let c0 = ip_count.get_mut(&e0.ip).unwrap();
            *c0 -= 1;
            if *c0 == 0 {
                uniq_ips -= 1;
            }
            type_count[e0.attack] -= 1;
            if type_count[e0.attack] == 0 {
                n_types -= 1;
            }
        }
        while minute[0] <= t_now - RATE_MS {
            minute.pop_front();
        }
        let head_t = win[0].t;
        let start = if cluster_start > head_t { cluster_start } else { head_t };
        let (fin, raw) = score(base_sum, minute.len(), gaps + 1, uniq_ips, n_types, t_now - start);
        total += fin;
        total_raw += raw;
        last_t = Some(t_now);
    }
    (total, total_raw)
}

fn peak_rss_kb() -> u64 {
    std::fs::read_to_string("/proc/self/status")
        .ok()
        .and_then(|s| {
            s.lines()
                .find(|l| l.starts_with("VmHWM:"))
                .and_then(|l| l.split_whitespace().nth(1).and_then(|v| v.parse().ok()))
        })
        .unwrap_or(0)
}

fn main() {
    let args: Vec<String> = std::env::args().collect();
    if args.len() < 5 {
        eprintln!("usage: threat_scorer <rs_naive|rs_incremental> <burst|bounded> <n> <reps>");
        std::process::exit(2);
    }
    let variant = args[1].as_str();
    let regime = args[2].as_str();
    let n: usize = args[3].parse().expect("n");
    let reps: usize = args[4].parse().expect("reps");
    let events = generate(n, regime == "burst", 20261005);
    let run: fn(&[Event]) -> (f64, f64) = match variant {
        "rs_naive" => run_naive,
        "rs_incremental" => run_incremental,
        _ => panic!("unknown variant"),
    };
    for rep in 0..reps {
        let t0 = Instant::now();
        let (total, total_raw) = black_box(run(black_box(&events)));
        let ns = t0.elapsed().as_nanos();
        println!(
            "{{\"variant\":\"{}\",\"regime\":\"{}\",\"n\":{},\"rep\":{},\"ns\":{},\"checksum\":{:.17e},\"checksum_raw\":{:.17e},\"peak_rss_kb\":{}}}",
            variant, regime, n, rep, ns, total, total_raw, peak_rss_kb()
        );
    }
}
