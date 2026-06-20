"""
astram_data.py  –  Data loading, parsing, and aggregate statistics.
Uses only stdlib + numpy/scipy (no LightGBM dependency).
"""
from __future__ import annotations

import csv
import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from statistics import median
from typing import Any, Iterable

import numpy as np

# ---------------------------------------------------------------------------
# Date parsing
# ---------------------------------------------------------------------------
DATE_FORMATS = (
    "%Y-%m-%d %H:%M:%S.%f",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d %H:%M",
    "%d-%m-%Y %H:%M:%S.%f",
    "%d-%m-%Y %H:%M:%S",
    "%d-%m-%Y %H:%M",
)


def read_csv_rows(path: str | Path) -> list[dict[str, str]]:
    with Path(path).open(newline="", encoding="utf-8", errors="replace") as f:
        return list(csv.DictReader(f))


def normalize_text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if text.upper() in {"", "NULL", "NONE", "NAN", "NAT"}:
        return ""
    return text


def parse_dt(value: Any) -> datetime | None:
    text = normalize_text(value)
    if not text:
        return None
    cleaned = text.replace("T", " ").replace("Z", "")
    if "+" in cleaned:
        cleaned = cleaned.split("+")[0].strip()
    elif cleaned.count("-") > 2:
        parts = cleaned.split("-")
        # Only strip trailing offset if it looks like one (short numeric)
        if len(parts[-1]) <= 4 and parts[-1].isdigit():
            cleaned = "-".join(parts[:-1]).strip()
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(cleaned, fmt)
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(cleaned)
    except ValueError:
        return None


def safe_float(value: Any) -> float | None:
    text = normalize_text(value)
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def is_truthy(value: Any) -> bool:
    return normalize_text(value).upper() in {"TRUE", "1", "YES", "Y"}


# ---------------------------------------------------------------------------
# Duration calculation  (tries closed → resolved → end datetime)
# ---------------------------------------------------------------------------
MAX_DURATION_MINUTES = 720.0   # 12 hours cap for training


def duration_minutes(row: dict[str, str]) -> float | None:
    """
    Return event duration in minutes.
    Tries (in order): closed_datetime, resolved_datetime, end_datetime.
    Returns None if timestamps are missing / invalid / negative.
    """
    start_val = None
    for k in ("start_datetime", "start_time", "Start_DateTime"):
        v = row.get(k)
        if normalize_text(v):
            start_val = v
            break

    closed_val = None
    for k in ("closed_datetime", "resolved_datetime", "end_datetime",
               "closed_time", "end_time", "Closed_DateTime"):
        v = row.get(k)
        if normalize_text(v):
            closed_val = v
            break

    if not start_val or not closed_val:
        return None

    start = parse_dt(start_val)
    closed = parse_dt(closed_val)
    if not start or not closed:
        return None

    mins = (closed - start).total_seconds() / 60.0
    if mins < 0.5 or mins > 43200:   # < 30 seconds or > 30 days → skip
        return None
    return mins


# ---------------------------------------------------------------------------
# Severity tiers
# ---------------------------------------------------------------------------
def severity_tier(minutes: float) -> str:
    if minutes < 30:
        return "low"
    if minutes < 120:
        return "medium"
    if minutes < 480:
        return "high"
    return "critical"


SEVERITY_MAP = {"low": 0, "medium": 1, "high": 2, "critical": 3}
REV_SEVERITY_MAP = {v: k for k, v in SEVERITY_MAP.items()}

# ---------------------------------------------------------------------------
# Time-based features
# ---------------------------------------------------------------------------
def day_features(dt: datetime | None) -> dict[str, float]:
    if dt is None:
        return {
            "hour": -1.0, "hour_sin": 0.0, "hour_cos": 0.0,
            "day_of_week": -1.0, "day_sin": 0.0, "day_cos": 0.0,
            "month": -1.0, "is_weekend": 0.0, "is_peak_hour": 0.0, "is_daytime": 0.0,
        }
    hour = float(dt.hour) + float(dt.minute) / 60.0
    day = float(dt.weekday())
    return {
        "hour": hour,
        "hour_sin": float(math.sin(2.0 * math.pi * hour / 24.0)),
        "hour_cos": float(math.cos(2.0 * math.pi * hour / 24.0)),
        "day_of_week": day,
        "day_sin": float(math.sin(2.0 * math.pi * day / 7.0)),
        "day_cos": float(math.cos(2.0 * math.pi * day / 7.0)),
        "month": float(dt.month),
        "is_weekend": float(dt.weekday() >= 5),
        "is_peak_hour": float((7 <= dt.hour <= 10) or (17 <= dt.hour <= 20)),
        "is_daytime": float(6 <= dt.hour <= 21),
    }


# ---------------------------------------------------------------------------
# AggregateStats dataclass
# ---------------------------------------------------------------------------
@dataclass(slots=True)
class AggregateStats:
    global_duration_median: float
    global_duration_mean: float
    global_duration_p90: float
    global_priority_high_rate: float
    duration_by_cause: dict[str, float]
    duration_by_corridor: dict[str, float]
    duration_by_zone: dict[str, float]
    duration_by_junction: dict[str, float]
    freq_by_cause: dict[str, float]
    freq_by_corridor: dict[str, float]
    freq_by_zone: dict[str, float]
    freq_by_junction: dict[str, float]
    high_rate_by_cause: dict[str, float]
    high_rate_by_corridor: dict[str, float]
    high_rate_by_zone: dict[str, float]
    high_rate_by_junction: dict[str, float]
    planned_multiplier_by_cause: dict[str, float]
    planned_multiplier_by_corridor: dict[str, float]
    hotspot_scores: dict[str, float]


def _median_map(values_by_key: dict[str, list[float]]) -> dict[str, float]:
    return {k: float(np.median(v)) for k, v in values_by_key.items() if v}


def _rate_map(counts: dict[str, list[int]]) -> dict[str, float]:
    return {k: float(sum(v) / len(v)) for k, v in counts.items() if v}


def fit_aggregate_stats(rows: Iterable[dict[str, str]]) -> AggregateStats:
    durations: list[float] = []
    by_cause: dict[str, list[float]] = defaultdict(list)
    by_corridor: dict[str, list[float]] = defaultdict(list)
    by_zone: dict[str, list[float]] = defaultdict(list)
    by_junction: dict[str, list[float]] = defaultdict(list)
    cause_count: Counter[str] = Counter()
    corridor_count: Counter[str] = Counter()
    zone_count: Counter[str] = Counter()
    junction_count: Counter[str] = Counter()
    cause_high: dict[str, list[int]] = defaultdict(list)
    corridor_high: dict[str, list[int]] = defaultdict(list)
    zone_high: dict[str, list[int]] = defaultdict(list)
    junction_high: dict[str, list[int]] = defaultdict(list)
    planned_dur_by_cause: dict[str, list[float]] = defaultdict(list)
    planned_dur_by_corridor: dict[str, list[float]] = defaultdict(list)

    for row in rows:
        dur = duration_minutes(row)
        if dur is None:
            continue
        durations.append(dur)
        cause = normalize_text(row.get("event_cause")) or "unknown"
        corridor = normalize_text(row.get("corridor")) or "unknown"
        zone = normalize_text(row.get("zone")) or "unknown"
        junction = normalize_text(row.get("junction")) or "unknown"
        priority = normalize_text(row.get("priority")).lower()
        high_flag = int(priority in ("high", "critical"))

        by_cause[cause].append(dur)
        by_corridor[corridor].append(dur)
        by_zone[zone].append(dur)
        by_junction[junction].append(dur)
        cause_count[cause] += 1
        corridor_count[corridor] += 1
        zone_count[zone] += 1
        junction_count[junction] += 1
        cause_high[cause].append(high_flag)
        corridor_high[corridor].append(high_flag)
        zone_high[zone].append(high_flag)
        junction_high[junction].append(high_flag)

        if normalize_text(row.get("event_type")) == "planned":
            planned_dur_by_cause[cause].append(dur)
            planned_dur_by_corridor[corridor].append(dur)

    if not durations:
        raise ValueError("No valid start/closed datetime pairs found in the data.")

    global_median = float(np.median(durations))
    global_mean = float(np.mean(durations))
    global_p90 = float(np.percentile(durations, 90))

    high_total = sum(sum(v) for v in cause_high.values())
    high_count = sum(len(v) for v in cause_high.values())
    priority_high_rate = float(high_total / high_count) if high_count else 0.0

    total_rows = max(1, sum(cause_count.values()))
    freq_by_cause = {k: v / total_rows for k, v in cause_count.items()}
    freq_by_corridor = {k: v / total_rows for k, v in corridor_count.items()}
    freq_by_zone = {k: v / total_rows for k, v in zone_count.items()}
    freq_by_junction = {k: v / total_rows for k, v in junction_count.items()}

    planned_mult_cause: dict[str, float] = {}
    planned_mult_corridor: dict[str, float] = {}
    for key, vals in planned_dur_by_cause.items():
        if vals:
            planned_mult_cause[key] = max(1.0, float(np.median(vals) / max(global_median, 1)))
    for key, vals in planned_dur_by_corridor.items():
        if vals:
            planned_mult_corridor[key] = max(1.0, float(np.median(vals) / max(global_median, 1)))

    # Hotspot scores (corridor + junction combined)
    hotspot_scores: dict[str, float] = {}
    max_freq = max(max(freq_by_corridor.values(), default=1e-9),
                   max(freq_by_junction.values(), default=1e-9), 1e-9)
    dur_by_corr = _median_map(by_corridor)
    dur_by_junc = _median_map(by_junction)
    hr_by_corr = _rate_map(corridor_high)
    hr_by_junc = _rate_map(junction_high)
    for key in set(corridor_count) | set(junction_count):
        freq = max(freq_by_corridor.get(key, 0.0), freq_by_junction.get(key, 0.0))
        dur_comp = max(dur_by_corr.get(key, global_median),
                       dur_by_junc.get(key, global_median)) / max(global_median, 1.0)
        high_comp = max(hr_by_corr.get(key, 0.0), hr_by_junc.get(key, 0.0))
        hotspot_scores[key] = float(
            100.0 * (0.45 * freq / max_freq + 0.35 * dur_comp / 5.0 + 0.20 * high_comp)
        )

    return AggregateStats(
        global_duration_median=global_median,
        global_duration_mean=global_mean,
        global_duration_p90=global_p90,
        global_priority_high_rate=priority_high_rate,
        duration_by_cause=_median_map(by_cause),
        duration_by_corridor=_median_map(by_corridor),
        duration_by_zone=_median_map(by_zone),
        duration_by_junction=_median_map(by_junction),
        freq_by_cause=freq_by_cause,
        freq_by_corridor=freq_by_corridor,
        freq_by_zone=freq_by_zone,
        freq_by_junction=freq_by_junction,
        high_rate_by_cause=_rate_map(cause_high),
        high_rate_by_corridor=_rate_map(corridor_high),
        high_rate_by_zone=_rate_map(zone_high),
        high_rate_by_junction=_rate_map(junction_high),
        planned_multiplier_by_cause=planned_mult_cause,
        planned_multiplier_by_corridor=planned_mult_corridor,
        hotspot_scores=hotspot_scores,
    )


# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------
def extract_pin(addr: str | None) -> str:
    if not addr:
        return "unknown"
    m = re.search(r'Pin[- ]?(\d{6})', addr, re.IGNORECASE)
    return m.group(1) if m else "unknown"


def corridor_diversion_hint(corridor: str) -> str:
    corridor = normalize_text(corridor)
    lookup = {
        "Tumkur Road": "Use parallel service roads and Hesaraghatta side connectors.",
        "Bellary Road 1": "Shift to Airport Road / feeder arterial segments.",
        "Bellary Road 2": "Use Airport Road side access and nearby local connectors.",
        "Hosur Road": "Route traffic through Silk Board feeder roads and local service lanes.",
        "Mysore Road": "Use adjacent service roads and West of Chord Road connectors.",
        "Magadi Road": "Divert through West of Chord Road links and local neighborhood roads.",
        "Old Madras Road": "Use alternative arterial routes via KR Puram side roads.",
        "ORR East 1": "Use inner ring or feeder corridors to split volume across the junction.",
        "ORR East 2": "Divert to neighboring feeder roads and adjacent ring-road segments.",
        "ORR North 1": "Use local cross-streets and airport-side feeder roads as alternates.",
        "ORR North 2": "Use feeder corridors around Thanisandra and adjacent road links.",
        "ORR West 1": "Use inner-city connectors and service roads parallel to the corridor.",
        "ORR West 2": "Use nearby cross-links and service lanes to absorb diverted traffic.",
    }
    if corridor in lookup:
        return lookup[corridor]
    if not corridor or corridor == "Non-corridor":
        return "Use local perimeter roads and on-ground officer guidance."
    return "Use the nearest parallel arterial and feeder roads; confirm on-site."


def build_hotspot_rows(rows: Iterable[dict[str, str]], stats: AggregateStats) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = defaultdict(lambda: {
        "count": 0, "duration_sum": 0.0, "high_count": 0, "closure_count": 0,
    })
    for row in rows:
        dur = duration_minutes(row)
        if dur is None:
            continue
        keys = [
            normalize_text(row.get("junction")) or "unknown",
            normalize_text(row.get("corridor")) or "unknown",
        ]
        for key in keys:
            b = grouped[key]
            b["count"] += 1
            b["duration_sum"] += dur
            b["high_count"] += int(normalize_text(row.get("priority")).lower() in ("high", "critical"))
            b["closure_count"] += int(is_truthy(row.get("requires_road_closure")))

    rows_out: list[dict[str, Any]] = []
    total = max(1, sum(b["count"] for b in grouped.values()))
    for key, b in grouped.items():
        cnt = b["count"]
        avg_dur = b["duration_sum"] / cnt if cnt else 0.0
        high_rate = b["high_count"] / cnt if cnt else 0.0
        closure_rate = b["closure_count"] / cnt if cnt else 0.0
        freq = cnt / total
        base = max(stats.global_duration_median, 1.0)
        score = 100.0 * (
            0.40 * min(1.0, freq / 0.02)
            + 0.35 * min(1.0, avg_dur / (3.0 * base))
            + 0.20 * high_rate
            + 0.05 * closure_rate
        )
        rows_out.append({
            "name": key, "count": cnt,
            "avg_duration_min": round(avg_dur, 2),
            "high_priority_rate": round(high_rate, 4),
            "road_closure_rate": round(closure_rate, 4),
            "hotspot_score": round(score, 2),
        })
    rows_out.sort(key=lambda r: (r["hotspot_score"], r["count"]), reverse=True)
    return rows_out