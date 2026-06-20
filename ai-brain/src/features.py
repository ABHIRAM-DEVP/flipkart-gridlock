"""
features.py  –  Row-level feature extraction for the ML models.
"""
from __future__ import annotations

from typing import Any

import numpy as np

from astram_data import (
    AggregateStats,
    day_features,
    extract_pin,
    is_truthy,
    normalize_text,
    parse_dt,
    safe_float,
    MAX_DURATION_MINUTES,
)
from operations import nearest_hotspot_features


def _cat(value: str, default: str = "unknown") -> str:
    t = normalize_text(value)
    return t if t else default


def build_v2_target_maps(
    train_rows: list[dict[str, str]],
    global_median: float,
    duration_by_cause: dict[str, float],
) -> dict[str, dict]:
    """
    Smoothed target-encoding maps: cause×corridor, PIN-code, month, geo-grid.
    Uses m-estimate with m=10 pseudo-counts to prevent overfitting on rare keys.
    """
    m = 10.0
    cc_groups: dict[str, list[float]] = {}
    pin_groups: dict[str, list[float]] = {}
    month_groups: dict[str, list[float]] = {}
    grid_groups: dict[str, list[float]] = {}

    for r in train_rows:
        raw = safe_float(r.get("_duration_min"))
        if raw is None:
            continue
        dur = min(raw, MAX_DURATION_MINUTES)

        cause = normalize_text(r.get("event_cause")) or "unknown"
        corridor = normalize_text(r.get("corridor")) or "unknown"
        pin = extract_pin(r.get("address"))
        dt = parse_dt(r.get("start_datetime"))
        lat = safe_float(r.get("latitude")) or 0.0
        lon = safe_float(r.get("longitude")) or 0.0
        grid_key = f"GRID_{round(lat, 2)}_{round(lon, 2)}"
        cc_key = f"{cause}_x_{corridor}"

        cc_groups.setdefault(cc_key, []).append(dur)
        pin_groups.setdefault(pin, []).append(dur)
        grid_groups.setdefault(grid_key, []).append(dur)
        if dt:
            month_groups.setdefault(str(dt.month), []).append(dur)

    def _smooth(groups: dict[str, list[float]]) -> dict[str, float]:
        return {
            k: float((len(v) * float(np.median(v)) + m * global_median) / (len(v) + m))
            for k, v in groups.items()
        }

    return {
        "duration_by_cause_corridor": _smooth(cc_groups),
        "duration_by_pin": _smooth(pin_groups),
        "duration_by_month": _smooth(month_groups),
        "duration_by_grid": _smooth(grid_groups),
    }


def row_features(
    row: dict[str, Any],
    stats: AggregateStats,
    v2_maps: dict[str, dict] | None = None,
    dbscan_hotspots: list[dict[str, float]] | None = None,
) -> dict[str, float | str]:
    """
    Build the complete feature dictionary for a single event row.
    v2_maps can be None for inference when maps are not yet available.
    """
    if v2_maps is None:
        v2_maps = {
            "duration_by_cause_corridor": {},
            "duration_by_pin": {},
            "duration_by_month": {},
            "duration_by_grid": {},
        }

    dt = parse_dt(row.get("start_datetime"))
    cause = _cat(row.get("event_cause"))
    corridor = _cat(row.get("corridor"))
    zone = _cat(row.get("zone"))
    junction = _cat(row.get("junction"))
    pin_code = extract_pin(str(row.get("address", "")))
    priority = _cat(row.get("priority")).lower()
    event_type = _cat(row.get("event_type")).lower()

    lat = safe_float(row.get("latitude")) or 0.0
    lon = safe_float(row.get("longitude")) or 0.0

    f: dict[str, float | str] = {
        # Categorical (will be one-hot encoded by sklearn pipeline)
        "event_type_cat": event_type,
        "priority_cat": priority,
        "cause_cat": cause,
        "corridor_cat": corridor,
        "zone_cat": zone,
        "junction_cat": junction,
        "requires_road_closure_cat": "yes" if is_truthy(row.get("requires_road_closure")) else "no",
        # Numeric flags
        "road_closure_flag": float(is_truthy(row.get("requires_road_closure"))),
        "is_planned": float(event_type == "planned"),
        "priority_is_high": float(priority == "high"),
        "priority_is_critical": float(priority == "critical"),
        "latitude": lat,
        "longitude": lon,
    }

    # Time features
    f.update(day_features(dt))

    # --- Target-encoded lookups (m-estimate smoothed) ---
    gmed = stats.global_duration_median
    cc_key = f"{cause}_x_{corridor}"
    f["cause_corridor_joint_median"] = v2_maps["duration_by_cause_corridor"].get(
        cc_key, stats.duration_by_cause.get(cause, gmed)
    )
    f["pin_regional_median_duration"] = v2_maps["duration_by_pin"].get(pin_code, gmed)
    f["seasonal_month_median"] = (
        v2_maps["duration_by_month"].get(str(dt.month), gmed) if dt else gmed
    )
    grid_key = f"GRID_{round(lat, 2)}_{round(lon, 2)}"
    f["geo_grid_median_duration"] = v2_maps["duration_by_grid"].get(grid_key, gmed)

    # --- Aggregate stat lookups ---
    f["cause_median_duration"] = stats.duration_by_cause.get(cause, gmed)
    f["corridor_median_duration"] = stats.duration_by_corridor.get(corridor, gmed)
    f["zone_median_duration"] = stats.duration_by_zone.get(zone, gmed)
    f["cause_frequency"] = stats.freq_by_cause.get(cause, 0.0)
    f["corridor_frequency"] = stats.freq_by_corridor.get(corridor, 0.0)
    f["zone_frequency"] = stats.freq_by_zone.get(zone, 0.0)
    f["cause_high_priority_rate"] = stats.high_rate_by_cause.get(cause, stats.global_priority_high_rate)
    f["corridor_high_priority_rate"] = stats.high_rate_by_corridor.get(corridor, stats.global_priority_high_rate)
    f["hotspot_score"] = stats.hotspot_scores.get(junction, stats.hotspot_scores.get(corridor, 0.0))

    # --- DBSCAN spatial features ---
    f.update(
        nearest_hotspot_features(lat if lat != 0 else None, lon if lon != 0 else None, dbscan_hotspots)
    )

    # --- Cross-features / interactions ---
    is_peak = float(f.get("is_peak_hour", 0.0))
    f["priority_x_closure"] = f"{priority}_{int(f['road_closure_flag'])}"
    f["cause_x_peak"] = f"{cause}_{int(is_peak)}"
    f["critical_closure_interaction"] = float(f["priority_is_critical"] * f["road_closure_flag"])
    f["high_risk_location"] = float(
        f["hotspot_score"] > 50.0
        and (f["priority_is_high"] == 1.0 or f["priority_is_critical"] == 1.0)
    )
    f["is_weekend_planned"] = float(f.get("is_weekend", 0.0) == 1.0 and f["is_planned"] == 1.0)
    density_w = float(f["dbscan_nearest_hotspot_count"]) if "dbscan_nearest_hotspot_count" in f else 0.0
    dist = float(f.get("dbscan_min_distance_km", 0.0))
    within_25 = float(f.get("hotspots_within_2_5km", 0.0))
    within_50 = float(f.get("hotspots_within_5km", 0.0))
    f["density_weighted_distance"] = dist / (within_25 + 1.0)
    f["regional_concentration_ratio"] = (within_25 + 1.0) / (within_50 + 1.0)
    f["peak_hour_high_priority"] = float(is_peak == 1.0 and (f["priority_is_high"] == 1.0 or f["priority_is_critical"] == 1.0))
    f["peak_road_closure"] = float(is_peak * f["road_closure_flag"])

    gref = float(gmed) if gmed > 0 else 1.0
    corr_dev = f["corridor_median_duration"] / gref
    cause_dev = f["cause_median_duration"] / gref
    f["corridor_deviation_factor"] = corr_dev
    f["cause_deviation_factor"] = cause_dev
    f["combined_risk_multiplier"] = corr_dev * cause_dev
    f["cause_corridor_expected_scale"] = f["cause_median_duration"] * f["corridor_frequency"]

    hs_score = float(f.get("dbscan_nearest_hotspot_score", 0.0))
    raw_spatial = hs_score * (f["corridor_median_duration"] + 1.0)
    f["spatial_severity_bound"] = float(np.log1p(raw_spatial))

    return f