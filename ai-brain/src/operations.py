from __future__ import annotations
import math
from dataclasses import dataclass, asdict
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


@dataclass(slots=True)
class PlannedImpactStats:
    corridor_hour_baseline: dict[str, float]
    planned_key_rate: dict[str, float]
    spillover_by_key: dict[str, float]
    multiplier_by_key: dict[str, float]


def nearest_hotspot_features(
    latitude: float | None,
    longitude: float | None,
    hotspots: list[dict[str, Any]] | None,
) -> dict[str, float]:
    if latitude is None or longitude is None or not hotspots:
        return {
            "dbscan_min_distance_km": 0.0,
            "dbscan_nearest_hotspot_score": 0.0,
            "dbscan_nearest_hotspot_count": 0.0,
            "hotspots_within_2.5km": 0.0,
            "hotspots_within_5km": 0.0,
        }

    best_distance = float("inf")
    best_score = 0.0
    best_count = 0.0
    
    within_25k = 0.0
    within_50k = 0.0

    # Haversine implementation for precise geodesic distance calculations
    lat1_rad = math.radians(latitude)

    for hotspot in hotspots:
        try:
            lat2 = float(hotspot.get("centroid_latitude", 0.0))
            lon2 = float(hotspot.get("centroid_longitude", 0.0))
            score = float(hotspot.get("hotspot_score", 0.0))
            count = float(hotspot.get("count", 0.0))
        except (TypeError, ValueError):
            continue

        lat2_rad = math.radians(lat2)
        dlat = math.radians(lat2 - latitude)
        dlon = math.radians(lon2 - longitude)

        a = (math.sin(dlat / 2.0) ** 2) + math.cos(lat1_rad) * math.cos(lat2_rad) * (math.sin(dlon / 2.0) ** 2)
        c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
        distance_km = 6371.0 * c  # Mean earth radius in kilometers

        # Increment local cluster density counters
        if distance_km <= 2.5:
            within_25k += 1.0
        if distance_km <= 5.0:
            within_50k += 1.0

        if distance_km < best_distance:
            best_distance = distance_km
            best_score = score
            best_count = count

    if best_distance == float("inf"):
        best_distance = 0.0

    return {
        "dbscan_min_distance_km": float(best_distance),
        "dbscan_nearest_hotspot_score": float(best_score),
        "dbscan_nearest_hotspot_count": float(best_count),
        "hotspots_within_2.5km": within_25k,
        "hotspots_within_5km": within_50k,
    }

def _valid_latlon(row: dict[str, str]) -> tuple[float, float] | None:
    try:
        lat = float(normalize_text(row.get("latitude")))
        lon = float(normalize_text(row.get("longitude")))
    except ValueError:
        return None
    if lat == 0.0 or lon == 0.0:
        return None
    return lat, lon


def build_dbscan_hotspots(rows: list[dict[str, str]], eps: float = 0.005, min_samples: int = 5) -> list[DbscanHotspot]:
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
        coords = np.asarray([_valid_latlon(r) for r in cluster_rows if _valid_latlon(r) is not None], dtype=float)
        if coords.size == 0:
            continue
        durations = [duration_minutes(r) for r in cluster_rows]
        durations = [d for d in durations if d is not None]
        count = len(cluster_rows)
        high_rate = sum(normalize_text(r.get("priority")).lower() == "high" for r in cluster_rows) / count
        closure_rate = sum(is_truthy(r.get("requires_road_closure")) for r in cluster_rows) / count
        avg_duration = float(np.mean(durations)) if durations else 0.0
        score = float(
            100.0
            * (0.4 * min(1.0, count / 20.0) + 0.3 * min(1.0, avg_duration / 240.0) + 0.2 * high_rate + 0.1 * closure_rate)
        )
        results.append(
            DbscanHotspot(
                cluster_id=cluster_id,
                count=count,
                centroid_latitude=float(coords[:, 0].mean()),
                centroid_longitude=float(coords[:, 1].mean()),
                avg_duration_min=avg_duration,
                high_priority_rate=float(high_rate),
                road_closure_rate=float(closure_rate),
                hotspot_score=score,
            )
        )

    results.sort(key=lambda item: (item.hotspot_score, item.count), reverse=True)
    return results


def build_planned_impact_stats(rows: list[dict[str, str]]) -> PlannedImpactStats:
    planned_rows = []
    unplanned_rows = []
    for row in rows:
        dt = parse_dt(row.get("start_datetime"))
        if dt is None:
            continue
        if normalize_text(row.get("event_type")) == "planned":
            planned_rows.append(row)
        else:
            unplanned_rows.append(row)

    corridor_hour_counts: dict[str, int] = {}
    corridor_hour_days: dict[str, set[str]] = {}
    for row in unplanned_rows:
        dt = parse_dt(row.get("start_datetime"))
        if dt is None:
            continue
        corridor = normalize_text(row.get("corridor")) or "unknown"
        key = f"{corridor}|{dt.hour}"
        corridor_hour_counts[key] = corridor_hour_counts.get(key, 0) + 1
        corridor_hour_days.setdefault(key, set()).add(dt.date().isoformat())

    corridor_hour_baseline: dict[str, float] = {}
    for key, count in corridor_hour_counts.items():
        days = max(1, len(corridor_hour_days.get(key, set())))
        corridor_hour_baseline[key] = count / days

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
        spillover = 0
        baseline = corridor_hour_baseline.get(f"{corridor}|{dt.hour}", 0.0)
        for other in unplanned_rows:
            other_dt = parse_dt(other.get("start_datetime"))
            if other_dt is None:
                continue
            if normalize_text(other.get("corridor")) != corridor:
                continue
            if window_start <= other_dt <= window_end:
                spillover += 1
        planned_key_rate[key] = planned_key_rate.get(key, 0.0) + 1.0
        spillover_by_key[key] = spillover_by_key.get(key, 0.0) + spillover
        multiplier_by_key[key] = (spillover + 1.0) / (baseline + 1.0)

    return PlannedImpactStats(
        corridor_hour_baseline=corridor_hour_baseline,
        planned_key_rate=planned_key_rate,
        spillover_by_key=spillover_by_key,
        multiplier_by_key=multiplier_by_key,
    )


def forecast_planned_event(
    event: dict[str, str],
    stats: AggregateStats,
    planned_stats: PlannedImpactStats,
) -> dict[str, Any]:
    dt = parse_dt(event.get("start_datetime"))
    corridor = normalize_text(event.get("corridor")) or "unknown"
    cause = normalize_text(event.get("event_cause")) or "unknown"
    hour = dt.hour if dt else -1
    key = f"{cause}|{corridor}|{hour}"
    baseline = planned_stats.corridor_hour_baseline.get(f"{corridor}|{hour}", 0.0)
    multiplier = planned_stats.multiplier_by_key.get(key, 1.0)
    spillover = planned_stats.spillover_by_key.get(key, 0.0)
    planned_rate = planned_stats.planned_key_rate.get(key, 0.0)
    corridor_risk = stats.hotspot_scores.get(corridor, 0.0)

    expected_spillover = spillover / max(1.0, planned_rate)
    adjusted_duration_multiplier = max(1.0, multiplier, stats.planned_multiplier_by_cause.get(cause, 1.0))
    return {
        "planned_key": key,
        "baseline_unplanned_rate": round(baseline, 4),
        "spillover_events_per_planned_event": round(expected_spillover, 2),
        "impact_multiplier": round(adjusted_duration_multiplier, 2),
        "compounding_risk_score": round(min(100.0, corridor_risk + expected_spillover * 10.0), 2),
        "recommend_preposition_hours_before": 3,
    }


def _severity_to_bounds(severity: str) -> tuple[int, int]:
    severity = severity.lower()
    if severity == "low":
        return 1, 1
    if severity == "medium":
        return 2, 3
    if severity == "high":
        return 4, 5
    return 6, 8


def allocate_resources(events: list[dict[str, Any]], total_personnel: int = 50) -> dict[str, Any]:
    if not events:
        return {"status": "empty", "allocations": [], "remaining_personnel": total_personnel}

    n = len(events)
    min_bounds = []
    max_bounds = []
    weights = []
    severities = []
    for event in events:
        severity = str(event.get("predicted_severity", "medium")).lower()
        min_manpower, max_manpower = _severity_to_bounds(severity)
        min_bounds.append(min_manpower)
        max_bounds.append(max_manpower)
        weights.append(float(event.get("risk_score", event.get("predicted_duration_min", 0.0))) + (5.0 if severity == "critical" else 0.0))
        severities.append(severity)

    # Decision vector is [x_0..x_n-1, y_0..y_n-1] where x is assigned personnel and y is whether the event is covered.
    num_vars = 2 * n
    c = np.zeros(num_vars, dtype=float)
    for i, weight in enumerate(weights):
        c[n + i] = -weight

    integrality = np.ones(num_vars, dtype=int)
    bounds = Bounds(
        lb=np.asarray([0.0] * n + [0.0] * n, dtype=float),
        ub=np.asarray(max_bounds + [1.0] * n, dtype=float),
    )

    a_rows = []
    a_lbs = []
    a_ubs = []

    # Sum of all assigned personnel <= total budget
    total_row = np.zeros(num_vars, dtype=float)
    total_row[:n] = 1.0
    a_rows.append(total_row)
    a_lbs.append(-np.inf)
    a_ubs.append(float(total_personnel))

    # Min and max constraints per event based on coverage binary y_i
    for i in range(n):
        row_min = np.zeros(num_vars, dtype=float)
        row_min[i] = -1.0
        row_min[n + i] = float(min_bounds[i])
        a_rows.append(row_min)
        a_lbs.append(-np.inf)
        a_ubs.append(0.0)

        row_max = np.zeros(num_vars, dtype=float)
        row_max[i] = 1.0
        row_max[n + i] = -float(max_bounds[i])
        a_rows.append(row_max)
        a_lbs.append(-np.inf)
        a_ubs.append(0.0)

    constraints = LinearConstraint(np.asarray(a_rows), np.asarray(a_lbs), np.asarray(a_ubs))
    try:
        result = milp(c=c, constraints=constraints, bounds=bounds, integrality=integrality)
        solution = result.x if result.success and result.x is not None else None
    except Exception:
        solution = None

    if solution is None:
        remaining = total_personnel
        allocations = []
        ranked = sorted(range(n), key=lambda i: weights[i] / max(min_bounds[i], 1), reverse=True)
        assigned = [0] * n
        for idx in ranked:
            if remaining <= 0:
                break
            need = min_bounds[idx]
            give = min(need, remaining)
            assigned[idx] = give
            remaining -= give
        allocations = [
            {"event_index": i, "assigned_personnel": assigned[i], "severity": severities[i], "risk_score": weights[i]}
            for i in range(n)
        ]
        return {"status": "fallback_greedy", "allocations": allocations, "remaining_personnel": remaining}

    assigned = np.rint(solution[:n]).astype(int)
    covered = np.rint(solution[n:]).astype(int)
    allocations = []
    used = 0
    for i, event in enumerate(events):
        assigned_i = int(max(0, assigned[i]))
        used += assigned_i
        allocations.append(
            {
                "event_index": i,
                "assigned_personnel": assigned_i,
                "covered": bool(covered[i]),
                "severity": severities[i],
                "risk_score": weights[i],
                "planned_duration_min": float(event.get("predicted_duration_min", 0.0)),
            }
        )

    return {
        "status": "optimal" if getattr(result, "success", False) else "approximate",
        "allocations": allocations,
        "remaining_personnel": int(total_personnel - used),
        "objective_value": float(-result.fun) if getattr(result, "fun", None) is not None else None,
    }
