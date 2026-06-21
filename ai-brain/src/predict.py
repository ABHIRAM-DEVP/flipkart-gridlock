"""
predict.py  –  Load trained artifacts and score a single event.
"""
from __future__ import annotations

import os
import json
import pickle
import warnings
from dataclasses import fields
from pathlib import Path
from typing import Any

import numpy as np

os.environ.setdefault("LOKY_MAX_CPU_COUNT", "1")

try:
    from sklearn.exceptions import InconsistentVersionWarning
except Exception:  # pragma: no cover - older sklearn versions
    InconsistentVersionWarning = None

if InconsistentVersionWarning is not None:
    warnings.filterwarnings("ignore", category=InconsistentVersionWarning)
warnings.filterwarnings("ignore", message="Could not find the number of physical cores*")

from astram_data import AggregateStats, normalize_text, severity_tier
from features import row_features
from operations import PlannedImpactStats, forecast_planned_event
from train import MAX_FORECAST_MINUTES, recommend_resources, transform


ARTIFACTS_DIR = Path(__file__).resolve().parent.parent / "artifacts"


def _load_bundle_dict(artifacts_dir: Path) -> dict[str, Any]:
    """
    Load the model bundle from any supported on-disk format.

    The project has used multiple bundle filenames and formats over time, so
    this keeps inference compatible with both the current trainer output and
    older generated artifacts.
    """
    candidates = (
        artifacts_dir / "bundle.json",
        artifacts_dir / "bundle.pkl",
        artifacts_dir / "astram_model_bundle.json",
        artifacts_dir / "astram_model_bundle.pkl",
    )
    for path in candidates:
        if not path.exists():
            continue
        try:
            if path.suffix == ".json":
                with path.open("r", encoding="utf-8") as f:
                    loaded = json.load(f)
            else:
                with path.open("rb") as f:
                    loaded = pickle.load(f)
        except Exception:
            continue
        if isinstance(loaded, dict):
            return loaded
        if isinstance(loaded, tuple) and loaded and isinstance(loaded[0], dict):
            return loaded[0]
    raise FileNotFoundError(f"No readable bundle found in {artifacts_dir}")


def _reconstruct_stats(stats_dict: dict[str, Any]) -> AggregateStats:
    stat_keys = {f.name for f in fields(AggregateStats)}
    return AggregateStats(**{k: v for k, v in stats_dict.items() if k in stat_keys})


def _extract_v2_maps(stats_dict: dict[str, Any]) -> dict[str, dict]:
    return {
        "duration_by_cause_corridor": stats_dict.get("duration_by_cause_corridor", {}),
        "duration_by_pin": stats_dict.get("duration_by_pin", {}),
        "duration_by_month": stats_dict.get("duration_by_month", {}),
        "duration_by_grid": stats_dict.get("duration_by_grid", {}),
    }


def load_artifacts(artifacts_dir: Path | None = None) -> dict[str, Any]:
    d = artifacts_dir or ARTIFACTS_DIR
    bundle = _load_bundle_dict(d)
    with (d / "dur_model.pkl").open("rb") as f:
        dur_model = pickle.load(f)
    with (d / "sev_model.pkl").open("rb") as f:
        sev_model = pickle.load(f)
    with (d / "encoder.pkl").open("rb") as f:
        enc = pickle.load(f)
    return {"bundle": bundle, "dur_model": dur_model, "sev_model": sev_model, "enc": enc}


def predict_event(
    event: dict[str, Any],
    artifacts: dict[str, Any],
) -> dict[str, Any]:
    bundle = artifacts["bundle"]
    dur_model = artifacts["dur_model"]
    sev_model = artifacts["sev_model"]
    enc = artifacts["enc"]
    cat_cols: list[str] = bundle["cat_cols"]
    num_cols: list[str] = bundle["num_cols"]

    stats_dict = bundle["stats"]
    stats = _reconstruct_stats(stats_dict)
    v2_maps = _extract_v2_maps(stats_dict)
    planned_stats = PlannedImpactStats(**bundle["planned_stats"])

    feats = row_features(event, stats, v2_maps, dbscan_hotspots=bundle.get("dbscan_hotspots"))

    X = transform([feats], cat_cols, num_cols, enc)
    predicted_minutes = float(np.expm1(dur_model.predict(X)[0]))
    predicted_minutes = float(np.clip(predicted_minutes, 0.0, MAX_FORECAST_MINUTES))

    severity = severity_tier(predicted_minutes)
    resources = recommend_resources(predicted_minutes, severity, event, stats)

    planned_impact = None
    if normalize_text(event.get("event_type")) == "planned":
        planned_impact = forecast_planned_event(event, stats, planned_stats)

    # Prediction interval from training residuals
    interval = bundle.get("residual_interval", {})
    p10 = predicted_minutes + interval.get("p10", 0.0)
    p90 = predicted_minutes + interval.get("p90", 0.0)

    return {
        "predicted_duration_min": round(predicted_minutes, 2),
        "predicted_severity": severity,
        "prediction_interval_min": {
            "p10": round(max(0.0, p10), 2),
            "p90": round(min(MAX_FORECAST_MINUTES, p90), 2),
        },
        "resource_plan": resources,
        "planned_impact": planned_impact,
    }

def load_pipeline(artifacts_dir: Path | str) -> tuple:
    """Load the bundle and model objects used by the HTTP service."""
    path = Path(artifacts_dir)

    bundle = _load_bundle_dict(path)
    stats = _reconstruct_stats(bundle["stats"])
    planned_stats = PlannedImpactStats(**bundle["planned_stats"])

    with (path / "dur_model.pkl").open("rb") as f:
        dur_model = pickle.load(f)
    with (path / "sev_model.pkl").open("rb") as f:
        sev_model = pickle.load(f)
    with (path / "encoder.pkl").open("rb") as f:
        encoder = pickle.load(f)

    return bundle, dur_model, sev_model, encoder, stats, planned_stats

def predict_from_bundle(bundle: dict, event: dict, pipeline: tuple | None = None) -> dict[str, Any]:
    """Scores an event using the loaded pipeline tuple."""
    if pipeline is None:
        pipeline = load_pipeline(ARTIFACTS_DIR)

    _, dur_model, sev_model, enc, stats, planned_stats = pipeline
    
    cat_cols = bundle["cat_cols"]
    num_cols = bundle["num_cols"]
    
    # V2 Maps
    stats_dict = bundle["stats"]
    v2_maps = _extract_v2_maps(stats_dict)

    feats = row_features(event, stats, v2_maps, dbscan_hotspots=bundle.get("dbscan_hotspots"))
    X = transform([feats], cat_cols, num_cols, enc)
    
    predicted_minutes = float(np.expm1(dur_model.predict(X)[0]))
    predicted_minutes = float(np.clip(predicted_minutes, 0.0, MAX_FORECAST_MINUTES))

    severity = severity_tier(predicted_minutes)
    resources = recommend_resources(predicted_minutes, severity, event, stats)

    planned_impact = None
    if normalize_text(event.get("event_type")) == "planned":
        planned_impact = forecast_planned_event(event, stats, planned_stats)

    interval = bundle.get("residual_interval", {})
    p10 = predicted_minutes + interval.get("p10", 0.0)
    p90 = predicted_minutes + interval.get("p90", 0.0)

    return {
        "predicted_duration_min": round(predicted_minutes, 2),
        "predicted_severity": severity,
        "prediction_interval_min": {
            "p10": round(max(0.0, p10), 2),
            "p90": round(min(MAX_FORECAST_MINUTES, p90), 2),
        },
        "resource_plan": resources,
        "planned_impact": planned_impact,
    }
# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import argparse, sys

    parser = argparse.ArgumentParser(description="Predict event impact.")
    parser.add_argument("--artifacts", default=str(ARTIFACTS_DIR))
    parser.add_argument("--json", required=True, help="Path to JSON event record.")
    args = parser.parse_args()

    artifacts = load_artifacts(Path(args.artifacts))
    with open(args.json, "r") as f:
        event = json.load(f)

    result = predict_event(event, artifacts)
    print(json.dumps(result, indent=2))
