from __future__ import annotations

import csv
import math
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from statistics import median
from typing import Any, Iterable


# Clean, standard patterns (we strip timezone text artifacts manually for stability)
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

    # Standardize format variations (T/Z indicators)
    cleaned = text.replace("T", " ").replace("Z", "")
    
    # Strip explicit PostgreSQL/ISO timezone offsets (+00, +0000, +05:30) 
    # to maintain compatibility with %f millisecond parsing tokens
    if "+" in cleaned:
        cleaned = cleaned.split("+")[0].strip()
    elif "-" in cleaned and len(cleaned.split("-")) > 3:
        # Handles trailing negative offsets safely without mangling YYYY-MM-DD
        parts = cleaned.split("-")
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


def duration_minutes(row: dict[str, str]) -> float | None:
    """
    Extracts timestamps flexibly by checking common header variants and 
    filtering out missing or unclosed ('NULL') incident records.
    """
    start_keys = ["start_datetime", "start_time", "startdatetime", "start datetime", "Start_DateTime"]
    closed_keys = ["closed_datetime", "closed_time", "closeddatetime", "closed datetime", "Closed_DateTime", "end_datetime", "end_time"]
    
    start_val = None
    for k in start_keys:
        for key_variant in (k, k.upper(), k.title()):
            if row.get(key_variant):
                start_val = row.get(key_variant)
                break
        if start_val:
            break
            
    closed_val = None
    for k in closed_keys:
        for key_variant in (k, k.upper(), k.title()):
            if row.get(key_variant):
                closed_val = row.get(key_variant)
                break
        if closed_val:
            break

    # If either value normalizes to an empty string or 'NULL', skip the row
    if not normalize_text(start_val) or not normalize_text(closed_val):
        return None

    start = parse_dt(start_val)
    closed = parse_dt(closed_val)
    
    if not start or not closed:
        return None
        
    minutes = (closed - start).total_seconds() / 60.0
    if minutes < 0 or minutes > 43200:  # Exclude negative ranges or anomalies over 30 days
        return None
    return minutes


def severity_tier(minutes: float) -> str:
    if minutes < 30:
        return "low"
    if minutes < 120:
        return "medium"
    if minutes < 480:
        return "high"
    return "critical"


def is_truthy(value: Any) -> bool:
    return normalize_text(value).upper() in {"TRUE", "1", "YES", "Y"}


def day_features(dt: datetime | None) -> dict[str, float]:
    if dt is None:
        return {
            "hour": -1.0,
            "hour_sin": 0.0,
            "hour_cos": 0.0,
            "day_of_week": -1.0,
            "day_sin": 0.0,
            "day_cos": 0.0,
            "month": -1.0,
            "is_weekend": 0.0,
            "is_peak_hour": 0.0,
            "is_daytime": 0.0,
        }

    hour = float(dt.hour) + float(dt.minute) / 60.0
    day = float(dt.weekday())

    # Cyclical transformations map midnight and late night closely together
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
    return {k: float(median(v)) for k, v in values_by_key.items() if v}


def _rate_map(counts: dict[str, list[int]]) -> dict[str, float]:
    result: dict[str, float] = {}
    for key, values in counts.items():
        if not values:
            continue
        result[key] = float(sum(values) / len(values))
    return result


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
    planned_durations_by_cause: dict[str, list[float]] = defaultdict(list)
    planned_durations_by_corridor: dict[str, list[float]] = defaultdict(list)
    planned_count = 0

    for row in rows:
        duration = duration_minutes(row)
        if duration is None:
            continue
        durations.append(duration)

        cause = normalize_text(row.get("event_cause")) or "unknown"
        corridor = normalize_text(row.get("corridor")) or "unknown"
        zone = normalize_text(row.get("zone")) or "unknown"
        junction = normalize_text(row.get("junction")) or "unknown"
        priority = normalize_text(row.get("priority")).lower()
        high_flag = int(priority == "high")

        by_cause[cause].append(duration)
        by_corridor[corridor].append(duration)
        by_zone[zone].append(duration)
        by_junction[junction].append(duration)
        cause_count[cause] += 1
        corridor_count[corridor] += 1
        zone_count[zone] += 1
        junction_count[junction] += 1
        cause_high[cause].append(high_flag)
        corridor_high[corridor].append(high_flag)
        zone_high[zone].append(high_flag)
        junction_high[junction].append(high_flag)

        if normalize_text(row.get("event_type")) == "planned":
            planned_count += 1
            planned_durations_by_cause[cause].append(duration)
            planned_durations_by_corridor[corridor].append(duration)

    if not durations:
        raise ValueError("No valid start/closed datetime pairs were found in the data.")

    global_median = float(median(durations))
    global_mean = float(sum(durations) / len(durations))
    sorted_durations = sorted(durations)
    p90 = float(sorted_durations[int(0.9 * (len(sorted_durations) - 1))])
    priority_high_rate = 0.0
    if durations:
        high_total = sum(sum(v) for v in cause_high.values())
        high_count = sum(len(v) for v in cause_high.values())
        priority_high_rate = float(high_total / high_count) if high_count else 0.0

    duration_by_cause = _median_map(by_cause)
    duration_by_corridor = _median_map(by_corridor)
    duration_by_zone = _median_map(by_zone)
    duration_by_junction = _median_map(by_junction)

    total_rows = sum(cause_count.values())
    freq_by_cause = {k: v / total_rows for k, v in cause_count.items()}
    freq_by_corridor = {k: v / total_rows for k, v in corridor_count.items()}
    freq_by_zone = {k: v / total_rows for k, v in zone_count.items()}
    freq_by_junction = {k: v / total_rows for k, v in junction_count.items()}
    high_rate_by_cause = _rate_map(cause_high)
    high_rate_by_corridor = _rate_map(corridor_high)
    high_rate_by_zone = _rate_map(zone_high)
    high_rate_by_junction = _rate_map(junction_high)

    planned_multiplier_by_cause: dict[str, float] = {}
    planned_multiplier_by_corridor: dict[str, float] = {}
    for key, values in planned_durations_by_cause.items():
        if values:
            planned_multiplier_by_cause[key] = max(1.0, float(median(values) / global_median))
    for key, values in planned_durations_by_corridor.items():
        if values:
            planned_multiplier_by_corridor[key] = max(1.0, float(median(values) / global_median))

    hotspot_scores: dict[str, float] = {}
    for key in set(corridor_count) | set(junction_count):
        freq = max(freq_by_corridor.get(key, 0.0), freq_by_junction.get(key, 0.0))
        duration_component = max(
            duration_by_corridor.get(key, global_median),
            duration_by_junction.get(key, global_median),
        ) / max(global_median, 1.0)
        high_component = max(high_rate_by_corridor.get(key, 0.0), high_rate_by_junction.get(key, 0.0))
        hotspot_scores[key] = float(
            100.0 * (0.45 * freq / max(max(freq_by_corridor.values() or [1.0]), 1e-9)
                     + 0.35 * duration_component / 5.0
                     + 0.20 * high_component)
        )

    return AggregateStats(
        global_duration_median=global_median,
        global_duration_mean=global_mean,
        global_duration_p90=p90,
        global_priority_high_rate=priority_high_rate,
        duration_by_cause=duration_by_cause,
        duration_by_corridor=duration_by_corridor,
        duration_by_zone=duration_by_zone,
        duration_by_junction=duration_by_junction,
        freq_by_cause=freq_by_cause,
        freq_by_corridor=freq_by_corridor,
        freq_by_zone=freq_by_zone,
        freq_by_junction=freq_by_junction,
        high_rate_by_cause=high_rate_by_cause,
        high_rate_by_corridor=high_rate_by_corridor,
        high_rate_by_zone=high_rate_by_zone,
        high_rate_by_junction=high_rate_by_junction,
        planned_multiplier_by_cause=planned_multiplier_by_cause,
        planned_multiplier_by_corridor=planned_multiplier_by_corridor,
        hotspot_scores=hotspot_scores,
    )


def corridor_diversion_hint(corridor: str) -> str:
    corridor = normalize_text(corridor)
    lookup = {
        "Tumkur Road": "Use parallel service roads and Hesaraghatta side connectors where available.",
        "Bellary Road 1": "Shift to Airport Road / feeder arterial segments and keep a parallel lane open.",
        "Bellary Road 2": "Use Airport Road side access and nearby local connectors for diversion.",
        "Hosur Road": "Route traffic through Silk Board feeder roads and local service lanes.",
        "Mysore Road": "Use adjacent service roads and West of Chord Road connectors.",
        "Magadi Road": "Divert through nearby West of Chord Road links and local neighborhood roads.",
        "Old Madras Road": "Use alternative arterial routes via KR Puram side roads and feeder links.",
        "ORR East 1": "Use inner ring or feeder corridors to split volume across the junction.",
        "ORR East 2": "Divert to neighboring feeder roads and adjacent ring-road segments.",
        "ORR North 1": "Use local cross-streets and airport-side feeder roads as alternates.",
        "ORR North 2": "Use feeder corridors around Thanisandra and adjacent road links.",
        "ORR West 1": "Use inner-city connectors and service roads running parallel to the corridor.",
        "ORR West 2": "Use nearby cross-links and service lanes to absorb diverted traffic.",
    }
    if corridor in lookup:
        return lookup[corridor]
    if corridor == "Non-corridor" or not corridor:
        return "Use local perimeter roads and on-ground officer guidance for site-specific diversion."
    return "Use the nearest parallel arterial and feeder roads; confirm on-site with live traffic conditions."


def build_hotspot_rows(rows: Iterable[dict[str, str]], stats: AggregateStats) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = defaultdict(lambda: {
        "count": 0,
        "duration_sum": 0.0,
        "high_count": 0,
        "closure_count": 0,
    })

    for row in rows:
        duration = duration_minutes(row)
        if duration is None:
            continue
        keys = [normalize_text(row.get("junction")) or "unknown", normalize_text(row.get("corridor")) or "unknown"]
        for key in keys:
            bucket = grouped[key]
            bucket["count"] += 1
            bucket["duration_sum"] += duration
            bucket["high_count"] += int(normalize_text(row.get("priority")).lower() == "high")
            bucket["closure_count"] += int(is_truthy(row.get("requires_road_closure")))

    rows_out: list[dict[str, Any]] = []
    for key, bucket in grouped.items():
        count = bucket["count"]
        avg_duration = bucket["duration_sum"] / count if count else 0.0
        high_rate = bucket["high_count"] / count if count else 0.0
        closure_rate = bucket["closure_count"] / count if count else 0.0
        freq = count / max(1, sum(v["count"] for v in grouped.values()))
        base = max(stats.global_duration_median, 1.0)
        score = 100.0 * (
            0.40 * min(1.0, freq / 0.02)
            + 0.35 * min(1.0, avg_duration / (3.0 * base))
            + 0.20 * high_rate
            + 0.05 * closure_rate
        )
        rows_out.append(
            {
                "name": key,
                "count": count,
                "avg_duration_min": round(avg_duration, 2),
                "high_priority_rate": round(high_rate, 4),
                "road_closure_rate": round(closure_rate, 4),
                "hotspot_score": round(score, 2),
            }
        )

    rows_out.sort(key=lambda r: (r["hotspot_score"], r["count"]), reverse=True)
    return rows_out