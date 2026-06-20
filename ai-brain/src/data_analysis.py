"""Quick diagnostic script to understand the dataset distribution and identify root causes."""
from __future__ import annotations
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

import numpy as np
from collections import Counter
from astram_data import read_csv_rows, duration_minutes, normalize_text, parse_dt, severity_tier

csv_path = os.path.join(os.path.dirname(__file__), "..", "dataset")
import glob
csvs = glob.glob(os.path.join(csv_path, "*.csv"))
rows = read_csv_rows(csvs[0])

print(f"Total rows: {len(rows)}")
print(f"Columns: {list(rows[0].keys())[:20]}")
print()

# Duration distribution
durations = []
for r in rows:
    d = duration_minutes(r)
    if d is not None:
        durations.append(d)

durations_arr = np.array(durations)
print(f"Rows with valid duration: {len(durations)}")
print(f"Duration stats:")
print(f"  Min:    {np.min(durations_arr):.1f} min")
print(f"  P10:    {np.percentile(durations_arr, 10):.1f} min")
print(f"  P25:    {np.percentile(durations_arr, 25):.1f} min")
print(f"  Median: {np.median(durations_arr):.1f} min")
print(f"  Mean:   {np.mean(durations_arr):.1f} min")
print(f"  P75:    {np.percentile(durations_arr, 75):.1f} min")
print(f"  P90:    {np.percentile(durations_arr, 90):.1f} min")
print(f"  P95:    {np.percentile(durations_arr, 95):.1f} min")
print(f"  P99:    {np.percentile(durations_arr, 99):.1f} min")
print(f"  Max:    {np.max(durations_arr):.1f} min")
print(f"  Std:    {np.std(durations_arr):.1f} min")
print()

# Severity distribution
sev_counts = Counter(severity_tier(d) for d in durations)
print(f"Severity distribution:")
for tier in ["low", "medium", "high", "critical"]:
    cnt = sev_counts.get(tier, 0)
    print(f"  {tier:10s}: {cnt:5d} ({100*cnt/len(durations):.1f}%)")
print()

# Check how many are > 720 (our cap)
over_cap = sum(1 for d in durations if d > 720)
print(f"Duration > 720 min: {over_cap} ({100*over_cap/len(durations):.1f}%)")

# Check outlier impact
durations_capped = np.clip(durations_arr, 0, 720)
print(f"After cap to 720: mean={np.mean(durations_capped):.1f}, std={np.std(durations_capped):.1f}")

durations_capped_360 = np.clip(durations_arr, 0, 360)
print(f"After cap to 360: mean={np.mean(durations_capped_360):.1f}, std={np.std(durations_capped_360):.1f}")

# Log transform analysis
log_durations = np.log1p(durations_capped)
print(f"\nLog1p(duration) stats (capped 720):")
print(f"  Mean:   {np.mean(log_durations):.3f}")
print(f"  Std:    {np.std(log_durations):.3f}")
print(f"  CV:     {np.std(log_durations)/np.mean(log_durations):.3f}")

# Feature cardinality
print(f"\n--- Feature cardinality ---")
for col in ["event_cause", "corridor", "zone", "junction", "priority", "event_type"]:
    vals = [normalize_text(r.get(col)) for r in rows if normalize_text(r.get(col))]
    print(f"  {col:20s}: {len(set(vals)):4d} unique, top: {Counter(vals).most_common(3)}")

# Check time span
dts = [parse_dt(r.get("start_datetime")) for r in rows]
dts = [d for d in dts if d]
if dts:
    print(f"\nTime span: {min(dts)} to {max(dts)}")
    print(f"  Days: {(max(dts)-min(dts)).days}")

# Duration by cause
print(f"\n--- Duration by cause ---")
cause_durations = {}
for r in rows:
    d = duration_minutes(r)
    if d is None:
        continue
    cause = normalize_text(r.get("event_cause")) or "unknown"
    cause_durations.setdefault(cause, []).append(d)

for cause, durs in sorted(cause_durations.items(), key=lambda x: -len(x[1])):
    arr = np.array(durs)
    print(f"  {cause:25s}: n={len(durs):4d}, median={np.median(arr):7.1f}, mean={np.mean(arr):7.1f}, std={np.std(arr):7.1f}")

# Duration by priority
print(f"\n--- Duration by priority ---")
prio_durations = {}
for r in rows:
    d = duration_minutes(r)
    if d is None:
        continue
    prio = normalize_text(r.get("priority")).lower() or "unknown"
    prio_durations.setdefault(prio, []).append(d)

for prio, durs in sorted(prio_durations.items()):
    arr = np.array(durs)
    print(f"  {prio:10s}: n={len(durs):4d}, median={np.median(arr):7.1f}, mean={np.mean(arr):7.1f}, std={np.std(arr):7.1f}")
