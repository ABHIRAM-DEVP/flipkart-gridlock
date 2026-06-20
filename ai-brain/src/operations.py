"""
operations.py  –  DBSCAN hotspots, planned-event impact stats, resource allocation.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

import numpy as np
from scipy.optimize import LinearConstraint, Bounds, milp
from sklearn.cluster import DBSCAN

from astram_data import (
    AggregateStats,
    duration_minutes,
    is_truthy,
    normalize_text,
    parse_dt,
    severity_tier,
)


# ---------------------------------------------------------------------------
# DBSCAN geographic hotspots
# ---------------------------------------------------------------------------
@dataclass(slots=True)
class DbscanHotspot:
    cluster_id: int
    count: int
    centroid_latitude: float
    centroid_longitude: float
    avg_duration_min: float
    high_priority_rate: float
    road_closure_rate: float
    hotspot_score: float


def _valid_latlon(row: dict[str, str]) -> tuple[float, float] | None:
    try:
        lat = float(normalize_text(row.get("latitude")))
        lon = float(normalize_text(row.get("longitude")))
    except (ValueError, TypeError):
        return None
    if lat == 0.0 or lon == 0.0:
        return None
    return lat, lon


def build_dbscan_hotspots(
    rows: list[dict[str, str]], eps: float = 0.005, min_samples: int = 5
) -> list[DbscanHotspot]:
    points: list[tuple[float, float]] = []
    row_refs: list[dict[str, str]] = []
    for row in rows:
        coords = _valid_latlon(row)
        if coords is None:
            continue
        points.append(coords)
        row_refs.append(row)

    if len(points) < min_samples:
        return []

    matrix = np.asarray(points, dtype=float)
    labels = DBSCAN(eps=eps, min_samples=min_samples).fit_predict(matrix)

    clusters: dict[int, list[dict[str, str]]] = {}
    for label, row in zip(labels, row_refs, strict=False):
        if label == -1:
            continue
        clusters.setdefault(int(label), []).append(row)

    results: list[DbscanHotspot] = []
    for cluster_id, cluster_rows in clusters.items():
        coords_arr = np.asarray(
            [_valid_latlon(r) for r in cluster_rows if _valid_latlon(r) is not None],
            dtype=float,
        )
        if coords_arr.size == 0:
            continue
        durations = [d for d in (duration_minutes(r) for r in cluster_rows) if d is not None]
        count = len(cluster_rows)
        high_rate = sum(
            normalize_text(r.get("priority")).lower() in ("high", "critical")
            for r in cluster_rows
        ) / count
        closure_rate = sum(is_truthy(r.get("requires_road_closure")) for r in cluster_rows) / count
        avg_dur = float(np.mean(durations)) if durations else 0.0
        score = float(
            100.0 * (
                0.4 * min(1.0, count / 20.0)
                + 0.3 * min(1.0, avg_dur / 240.0)
                + 0.2 * high_rate
                + 0.1 * closure_rate
            )
        )
        results.append(DbscanHotspot(
            cluster_id=cluster_id, count=count,
            centroid_latitude=float(coords_arr[:, 0].mean()),
            centroid_longitude=float(coords_arr[:, 1].mean()),
            avg_duration_min=avg_dur,
            high_priority_rate=float(high_rate),
            road_closure_rate=float(closure_rate),
            hotspot_score=score,
        ))

    results.sort(key=lambda h: (h.hotspot_score, h.count), reverse=True)
    return results


def nearest_hotspot_features(
    latitude: float | None,
    longitude: float | None,
    hotspots: list[dict[str, Any]] | None,
) -> dict[str, float]:
    zero = {
        "dbscan_min_distance_km": 0.0,
        "dbscan_nearest_hotspot_score": 0.0,
        "dbscan_nearest_hotspot_count": 0.0,
        "hotspots_within_2_5km": 0.0,
        "hotspots_within_5km": 0.0,
    }
    if latitude is None or longitude is None or not hotspots:
        return zero

    best_dist = float("inf")
    best_score = 0.0
    best_count = 0.0
    within_25 = 0.0
    within_50 = 0.0
    lat1_rad = math.radians(latitude)

    for h in hotspots:
        try:
            lat2 = float(h.get("centroid_latitude", 0.0))
            lon2 = float(h.get("centroid_longitude", 0.0))
            score = float(h.get("hotspot_score", 0.0))
            count = float(h.get("count", 0.0))
        except (TypeError, ValueError):
            continue

        dlat = math.radians(lat2 - latitude)
        dlon = math.radians(lon2 - longitude)
        lat2_rad = math.radians(lat2)
        a = math.sin(dlat / 2) ** 2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2) ** 2
        dist_km = 6371.0 * 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))

        if dist_km <= 2.5:
            within_25 += 1.0
        if dist_km <= 5.0:
            within_50 += 1.0
        if dist_km < best_dist:
            best_dist, best_score, best_count = dist_km, score, count

    return {
        "dbscan_min_distance_km": float(best_dist if best_dist != float("inf") else 0.0),
        "dbscan_nearest_hotspot_score": float(best_score),
        "dbscan_nearest_hotspot_count": float(best_count),
        "hotspots_within_2_5km": within_25,
        "hotspots_within_5km": within_50,
    }


# ---------------------------------------------------------------------------
# Planned event impact statistics
# ---------------------------------------------------------------------------
@dataclass(slots=True)
class PlannedImpactStats:
    corridor_hour_baseline: dict[str, float]
    planned_key_rate: dict[str, float]
    spillover_by_key: dict[str, float]
    multiplier_by_key: dict[str, float]


def build_planned_impact_stats(rows: list[dict[str, str]]) -> PlannedImpactStats:
    planned_rows, unplanned_rows = [], []
    for row in rows:
        dt = parse_dt(row.get("start_datetime"))
        if dt is None:
            continue
        (planned_rows if normalize_text(row.get("event_type")) == "planned" else unplanned_rows).append(row)

    corr_hour_counts: dict[str, int] = {}
    corr_hour_days: dict[str, set[str]] = {}
    for row in unplanned_rows:
        dt = parse_dt(row.get("start_datetime"))
        if dt is None:
            continue
        corridor = normalize_text(row.get("corridor")) or "unknown"
        key = f"{corridor}|{dt.hour}"
        corr_hour_counts[key] = corr_hour_counts.get(key, 0) + 1
        corr_hour_days.setdefault(key, set()).add(dt.date().isoformat())

    baseline: dict[str, float] = {
        k: v / max(1, len(corr_hour_days.get(k, set())))
        for k, v in corr_hour_counts.items()
    }
    planned_key_rate: dict[str, float] = {}
    spillover_by_key: dict[str, float] = {}
    multiplier_by_key: dict[str, float] = {}

    for row in planned_rows:
        dt = parse_dt(row.get("start_datetime"))
        if dt is None:
            continue
        corridor = normalize_text(row.get("corridor")) or "unknown"
        cause = normalize_text(row.get("event_cause")) or "unknown"
        key = f"{cause}|{corridor}|{dt.hour}"
        window_start = dt - timedelta(hours=3)
        window_end = dt + timedelta(hours=3)
        spillover = sum(
            1 for other in unplanned_rows
            if normalize_text(other.get("corridor")) == corridor
            and (other_dt := parse_dt(other.get("start_datetime"))) is not None
            and window_start <= other_dt <= window_end
        )
        b = baseline.get(f"{corridor}|{dt.hour}", 0.0)
        planned_key_rate[key] = planned_key_rate.get(key, 0.0) + 1.0
        spillover_by_key[key] = spillover_by_key.get(key, 0.0) + spillover
        multiplier_by_key[key] = (spillover + 1.0) / (b + 1.0)

    return PlannedImpactStats(
        corridor_hour_baseline=baseline,
        planned_key_rate=planned_key_rate,
        spillover_by_key=spillover_by_key,
        multiplier_by_key=multiplier_by_key,
    )


def forecast_planned_event(
    event: dict[str, Any], stats: AggregateStats, planned_stats: PlannedImpactStats
) -> dict[str, Any]:
    dt = parse_dt(event.get("start_datetime"))
    corridor = normalize_text(event.get("corridor")) or "unknown"
    cause = normalize_text(event.get("event_cause")) or "unknown"
    hour = dt.hour if dt else -1
    key = f"{cause}|{corridor}|{hour}"
    b = planned_stats.corridor_hour_baseline.get(f"{corridor}|{hour}", 0.0)
    multiplier = planned_stats.multiplier_by_key.get(key, 1.0)
    spillover = planned_stats.spillover_by_key.get(key, 0.0)
    planned_rate = planned_stats.planned_key_rate.get(key, 0.0)
    corridor_risk = stats.hotspot_scores.get(corridor, 0.0)
    expected_spill = spillover / max(1.0, planned_rate)
    adj_mult = max(1.0, multiplier, stats.planned_multiplier_by_cause.get(cause, 1.0))
    return {
        "planned_key": key,
        "baseline_unplanned_rate": round(b, 4),
        "spillover_events_per_planned_event": round(expected_spill, 2),
        "impact_multiplier": round(adj_mult, 2),
        "compounding_risk_score": round(min(100.0, corridor_risk + expected_spill * 10.0), 2),
        "recommend_preposition_hours_before": 3,
    }


# ---------------------------------------------------------------------------
# Resource allocation (MILP)
# ---------------------------------------------------------------------------
def _severity_to_bounds(severity: str) -> tuple[int, int]:
    return {"low": (1, 1), "medium": (2, 3), "high": (4, 5), "critical": (6, 8)}.get(
        severity.lower(), (2, 3)
    )


def allocate_resources(events: list[dict[str, Any]], total_personnel: int = 50) -> dict[str, Any]:
    if not events:
        return {"status": "empty", "allocations": [], "remaining_personnel": total_personnel}

    n = len(events)
    min_bounds, max_bounds, weights, severities = [], [], [], []
    for event in events:
        severity = str(event.get("predicted_severity", "medium")).lower()
        lo, hi = _severity_to_bounds(severity)
        min_bounds.append(lo)
        max_bounds.append(hi)
        base_w = float(event.get("risk_score", event.get("predicted_duration_min", 0.0)))
        weights.append(base_w + (5.0 if severity == "critical" else 0.0))
        severities.append(severity)

    c = np.zeros(2 * n, dtype=float)
    for i, w in enumerate(weights):
        c[n + i] = -w

    bounds = Bounds(
        lb=np.zeros(2 * n),
        ub=np.asarray(max_bounds + [1.0] * n, dtype=float),
    )
    integrality = np.ones(2 * n, dtype=int)

    a_rows, a_lbs, a_ubs = [], [], []
    total_row = np.zeros(2 * n)
    total_row[:n] = 1.0
    a_rows.append(total_row)
    a_lbs.append(-np.inf)
    a_ubs.append(float(total_personnel))
    for i in range(n):
        r_min = np.zeros(2 * n)
        r_min[i] = -1.0
        r_min[n + i] = float(min_bounds[i])
        a_rows.append(r_min)
        a_lbs.append(-np.inf)
        a_ubs.append(0.0)
        r_max = np.zeros(2 * n)
        r_max[i] = 1.0
        r_max[n + i] = -float(max_bounds[i])
        a_rows.append(r_max)
        a_lbs.append(-np.inf)
        a_ubs.append(0.0)

    constraints = LinearConstraint(np.asarray(a_rows), np.asarray(a_lbs), np.asarray(a_ubs))
    try:
        result = milp(c=c, constraints=constraints, bounds=bounds, integrality=integrality)
        solution = result.x if result.success and result.x is not None else None
    except Exception:
        solution = None

    if solution is None:
        # Greedy fallback
        remaining = total_personnel
        assigned = [0] * n
        for idx in sorted(range(n), key=lambda i: weights[i] / max(min_bounds[i], 1), reverse=True):
            if remaining <= 0:
                break
            give = min(min_bounds[idx], remaining)
            assigned[idx] = give
            remaining -= give
        return {
            "status": "fallback_greedy",
            "allocations": [
                {"event_index": i, "assigned_personnel": assigned[i],
                 "severity": severities[i], "risk_score": weights[i]}
                for i in range(n)
            ],
            "remaining_personnel": remaining,
        }

    assigned_arr = np.rint(solution[:n]).astype(int)
    covered_arr = np.rint(solution[n:]).astype(int)
    used = int(np.sum(np.maximum(0, assigned_arr)))
    allocations = [
        {
            "event_index": i,
            "assigned_personnel": int(max(0, assigned_arr[i])),
            "covered": bool(covered_arr[i]),
            "severity": severities[i],
            "risk_score": weights[i],
            "planned_duration_min": float(events[i].get("predicted_duration_min", 0.0)),
        }
        for i in range(n)
    ]
    return {
        "status": "optimal" if getattr(result, "success", False) else "approximate",
        "allocations": allocations,
        "remaining_personnel": int(total_personnel - used),
        "objective_value": float(-result.fun) if getattr(result, "fun", None) is not None else None,
    }
