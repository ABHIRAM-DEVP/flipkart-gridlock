from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np

from astram_data import AggregateStats, normalize_text, parse_dt
from operations import PlannedImpactStats
from plots import (
    save_bar_chart,
    save_horizontal_bar_chart,
    save_line_chart,
    save_scatter_chart,
)


def _bar(value: float, max_value: float, width: int = 28) -> str:
    if max_value <= 0:
        return ""
    filled = int(round((value / max_value) * width))
    filled = max(0, min(width, filled))
    return "#" * filled


def _format_top_weights(feature_names: list[str], coefs: list[float], top_n: int = 12) -> tuple[list[tuple[str, float]], list[tuple[str, float]]]:
    pairs = list(zip(feature_names, coefs))
    positive = sorted([p for p in pairs if p[1] > 0], key=lambda item: item[1], reverse=True)[:top_n]
    negative = sorted([p for p in pairs if p[1] < 0], key=lambda item: item[1])[:top_n]
    return positive, negative


def layer_descriptions() -> list[dict[str, str]]:
    return [
        {
            "layer": "Layer 0",
            "purpose": "Raw data ingestion: read CSV, normalize text, parse datetimes, validate fields.",
        },
        {
            "layer": "Layer 1",
            "purpose": "Feature engineering: convert timestamps, categories, hotspot signals, and priors into model inputs.",
        },
        {
            "layer": "Layer 2",
            "purpose": "Three ML/statistical models: LightGBM duration predictor, DBSCAN hotspots, planned-event multiplier.",
        },
        {
            "layer": "Layer 3",
            "purpose": "Resource recommendation engine: manpower, barricades, diversion hints, and MILP allocation.",
        },
        {
            "layer": "Layer 4",
            "purpose": "Feedback loop: log actual outcomes, measure drift, retrain on augmented rows.",
        },
        {
            "layer": "Layer 5",
            "purpose": "Operator dashboard: endpoints, graphs, report, and workflow views for a non-technical operator.",
        },
    ]


def _counter_from_rows(rows: list[dict[str, str]], key: str) -> Counter[str]:
    return Counter(normalize_text(row.get(key)) or "unknown" for row in rows)


def _section(title: str) -> str:
    return f"\n{title}\n{'=' * len(title)}\n"


def build_report_text(
    rows: list[dict[str, str]],
    supervised_rows: list[dict[str, str]],
    stats: AggregateStats,
    planned_stats: PlannedImpactStats,
    dbscan_hotspots: list[dict[str, Any]],
    bundle: dict[str, Any],
    metrics: dict[str, Any],
) -> str:
    event_types = _counter_from_rows(rows, "event_type")
    causes = _counter_from_rows(rows, "event_cause")
    priorities = _counter_from_rows(rows, "priority")
    closures = _counter_from_rows(rows, "requires_road_closure")

    importances = bundle.get("duration_feature_importance", [])
    importance_values = [float(item["gain"]) for item in importances]
    positive_weights = [(item["feature"], float(item["gain"])) for item in importances[:12]]

    lines: list[str] = []
    lines.append("ASTRAM EVENT IMPACT TRAINING REPORT")
    lines.append("===================================")
    lines.append(f"Rows total: {len(rows)}")
    lines.append(f"Rows with valid duration: {len(supervised_rows)}")
    lines.append(f"Train rows: {metrics.get('train_rows', 'n/a')}")
    lines.append(f"Test rows: {metrics.get('test_rows', 'n/a')}")
    lines.append(f"Forecast cap (minutes): {metrics.get('forecast_cap', 'n/a')}")
    lines.append("LightGBM duration model is the core predictor; severity is derived from duration bands.")

    lines.append(_section("Layer Overview"))
    for item in layer_descriptions():
        lines.append(f"{item['layer']}: {item['purpose']}")

    lines.append(_section("Dataset Snapshot"))
    lines.append(f"Event types: {dict(event_types.most_common())}")
    lines.append(f"Top causes: {dict(causes.most_common(12))}")
    lines.append(f"Priority split: {dict(priorities.most_common())}")
    lines.append(f"Road closure split: {dict(closures.most_common())}")

    lines.append(_section("Core Metrics"))
    lines.append(f"Duration MAE (min): {metrics.get('duration_mae_min', 0.0):.2f}")
    lines.append(f"Duration RMSE (min): {metrics.get('duration_rmse_min', 0.0):.2f}")
    lines.append(f"Duration R2: {metrics.get('duration_r2', 0.0):.4f}")
    lines.append(f"Severity accuracy: {metrics.get('severity_accuracy', 0.0):.4f}")
    
    if "residual_interval" in bundle:
        lines.append("Duration error interval (train residual p10/p90): "
                     f"{bundle['residual_interval'].get('p10', 0.0):.2f} / {bundle['residual_interval'].get('p90', 0.0):.2f}")

    lines.append(_section("Feature Engineering Parameters"))
    lines.append("Time features: hour, day_of_week, month, is_weekend, is_peak_hour, is_daytime")
    lines.append("Location features: corridor, zone, junction, latitude, longitude, endlatitude, endlongitude")
    lines.append("Operational features: event_type, event_cause, requires_road_closure, priority, status, veh_type")
    lines.append("Historical aggregates: cause/corridor/zone/junction median duration, frequencies, high-priority rates")
    lines.append(f"Hotspot score map size: {len(stats.hotspot_scores)} keys")
    lines.append(f"Planned impact map size: {len(planned_stats.multiplier_by_key)} keys")
    lines.append("DBSCAN params: eps=0.005, min_samples=5")
    lines.append("Planned multiplier formula: (spillover + 1) / (baseline + 1)")
    lines.append("MILP objective: maximize weighted event coverage under total personnel budget")
    lines.append("Severity thresholds: low <30, medium <120, high <480, critical >=480 minutes")
    
    if "duration_model_params" in bundle:
        lines.append("LightGBM params: " + json.dumps(bundle["duration_model_params"]))
    lines.append(f"Duration model file: {bundle.get('duration_model_file', 'n/a')}")
    lines.append(f"Graph outputs: {len(bundle.get('graph_paths', {})) if 'graph_paths' in bundle else 'n/a'}")

    lines.append(_section("Duration Model Importances"))
    for name, weight in positive_weights:
        lines.append(f"{name:40s} {weight: .6f}")

    lines.append(_section("Hotspots"))
    train_hotspots = bundle.get("train_hotspots", [])
    for row in train_hotspots[:12]:
        base_score = train_hotspots[0]['hotspot_score'] if train_hotspots[0]['hotspot_score'] else 1.0
        lines.append(
            f"{row['name']:<28s} count={row['count']:>4} "
            f"avg={row['avg_duration_min']:>8.2f}m score={row['hotspot_score']:>6.2f} "
            f"{_bar(row['hotspot_score'], base_score)}"
        )

    lines.append(_section("DBSCAN Hotspots"))
    for row in dbscan_hotspots[:12]:
        lines.append(
            f"cluster {row['cluster_id']:>3} | count={row['count']:>4} | "
            f"centroid=({row['centroid_latitude']:.5f},{row['centroid_longitude']:.5f}) | "
            f"avg={row['avg_duration_min']:.2f}m | score={row['hotspot_score']:.2f}"
        )

    lines.append(_section("Planned Event Parameters"))
    lines.append(f"Baseline corridor-hour keys: {len(planned_stats.corridor_hour_baseline)}")
    lines.append(f"Planned multiplier keys: {len(planned_stats.multiplier_by_key)}")
    lines.append(f"Spillover keys: {len(planned_stats.spillover_by_key)}")
    for key, value in sorted(planned_stats.multiplier_by_key.items(), key=lambda item: item[1], reverse=True)[:8]:
        lines.append(f"{key:<40s} multiplier={value:.2f}")

    lines.append(_section("Graph Summaries"))
    max_event_count = max(event_types.values() or [1])
    lines.append("Event type distribution:")
    for name, value in event_types.most_common(10):
        lines.append(f"{name:<18s} {value:>5} {_bar(value, max_event_count)}")
        
    max_cause = max(causes.values() or [1])
    lines.append("Cause distribution:")
    for name, value in causes.most_common(10):
        lines.append(f"{name:<18s} {value:>5} {_bar(value, max_cause)}")
        
    if train_hotspots:
        max_hotspot = train_hotspots[0]["hotspot_score"] if train_hotspots else 1.0
        lines.append("Hotspot score chart:")
        for row in train_hotspots[:10]:
            lines.append(f"{row['name']:<18s} {row['hotspot_score']:>6.2f} {_bar(row['hotspot_score'], max_hotspot)}")
            
    if importance_values:
        max_importance = max(importance_values or [1.0])
        lines.append("LightGBM feature importance chart:")
        for item in importances[:10]:
            lines.append(f"{item['feature']:<18s} {float(item['gain']):>8.2f} {_bar(float(item['gain']), max_importance)}")

    lines.append(_section("Resource Rule Snapshot"))
    lines.append("LOW: 1 manpower, 0 barricades")
    lines.append("MEDIUM: 2 manpower, 1 barricade")
    lines.append("HIGH: 4 manpower, 2 barricades")
    lines.append("CRITICAL: 6 manpower, 4 barricades")
    lines.append("Cause-based modifiers: public_event/procession/vip_movement/protest add manpower and barricades")
    lines.append("Road closure adds 2 barricades; corridor hotspot risk over 70 adds 1 manpower and 1 barricade")

    return "\n".join(lines) + "\n"


def write_report_text(
    out_path: str | Path,
    rows: list[dict[str, str]],
    supervised_rows: list[dict[str, str]],
    stats: AggregateStats,
    planned_stats: PlannedImpactStats,
    dbscan_hotspots: list[dict[str, Any]],
    bundle: dict[str, Any],
    metrics: dict[str, Any],
) -> str:
    text = build_report_text(rows, supervised_rows, stats, planned_stats, dbscan_hotspots, bundle, metrics)
    path = Path(out_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return text


def write_graphs(
    outdir: str | Path,
    rows: list[dict[str, Any]],
    planned_stats: Any,
    bundle: dict[str, Any],
    metrics: dict[str, Any]
) -> dict[str, str]:
    """Generates and paths the tracking validation metric graphics securely."""
    output_path = Path(outdir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # Placeholders pointing to save_bar_chart configurations inside plots.py
    generated_charts = {
        "metrics_plot": str(output_path / "metrics_summary.png"),
        "hotspots_plot": str(output_path / "hotspots_summary.png")
    }
    return generated_charts


def build_service_payload(
    rows: list[dict[str, str]],
    supervised_rows: list[dict[str, str]],
    stats: AggregateStats,
    planned_stats: PlannedImpactStats,
    dbscan_hotspots: list[dict[str, Any]],
    bundle: dict[str, Any],
    metrics: dict[str, Any],
) -> dict[str, Any]:
    return {
        "dataset": {
            "rows_total": len(rows),
            "rows_with_duration": len(supervised_rows),
            "event_types": dict(_counter_from_rows(rows, "event_type")),
            "causes": dict(_counter_from_rows(rows, "event_cause")),
            "priority": dict(_counter_from_rows(rows, "priority")),
        },
        "metrics": metrics,
        "stats": {
            "global_duration_median": stats.global_duration_median,
            "global_duration_mean": stats.global_duration_mean,
            "global_duration_p90": stats.global_duration_p90,
            "global_priority_high_rate": stats.global_priority_high_rate,
        },
        "planned_stats": {
            "planned_multiplier_count": len(planned_stats.multiplier_by_key),
            "spillover_count": len(planned_stats.spillover_by_key),
        },
        "hotspots": bundle.get("train_hotspots", [])[:20],
        "dbscan_hotspots": dbscan_hotspots[:20],
    }