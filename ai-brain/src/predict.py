from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
# pyrefly: ignore [missing-import]
import lightgbm as lgb

from astram_data import AggregateStats, normalize_text, severity_tier
from operations import PlannedImpactStats, forecast_planned_event
from train import MAX_FORECAST_MINUTES, recommend_resources, row_features


ROOT = Path(__file__).resolve().parents[1]


def _ensure_mapping(name: str, value: object) -> dict:
    """Validate that `value` is a mapping suitable for ** unpacking."""
    if not isinstance(value, dict):
        raise ValueError(
            f"The '{name}' entry in the model bundle must be a mapping (dict). "
            f"Got {type(value)!r} instead. Verify that the bundle was created "
            f"correctly by the training script."
        )
    return value


def feature_name(key: str, value: object) -> str:
    if isinstance(value, str):
        return f"{key}={value}"
    if isinstance(value, bool):
        return f"{key}={str(value).lower()}"
    return key


def vectorize_features(features: dict[str, float | str], feature_names: list[str]) -> np.ndarray:
    lookup = {name: idx for idx, name in enumerate(feature_names)}
    x = np.zeros(len(feature_names), dtype=float)
    for key, value in features.items():
        if isinstance(value, str):
            name = feature_name(key, value)
            idx = lookup.get(name)
            if idx is not None:
                x[idx] = 1.0
        else:
            name = feature_name(key, value)
            idx = lookup.get(name)
            if idx is not None:
                x[idx] = float(value)
    return x


def load_duration_booster(bundle: dict[str, object]) -> lgb.Booster:
    model_path = Path(str(bundle["duration_model_file"]))
    if not model_path.is_absolute():
        model_path = ROOT / model_path
    return lgb.Booster(model_file=str(model_path))


def predict_from_bundle(
    bundle: dict[str, object], 
    event: dict[str, object], 
    duration_booster: lgb.Booster | None = None
) -> dict[str, object]:
    # Validate mappings safely; dropping the {} default prevents sub-instantiation crashes 
    stats_dict = _ensure_mapping("stats", bundle.get("stats"))
    planned_stats_dict = _ensure_mapping("planned_stats", bundle.get("planned_stats"))
    
    stats = AggregateStats(**stats_dict)
    planned_stats = PlannedImpactStats(**planned_stats_dict)
    
    features = row_features(event, stats, dbscan_hotspots=bundle.get("dbscan_hotspots"))
    feature_names = bundle["feature_names"]
    x = vectorize_features(features, feature_names)

    booster = duration_booster or load_duration_booster(bundle)
    
    # Predict duration in minutes using the LightGBM booster
    predicted_minutes = float(np.expm1(booster.predict(x.reshape(1, -1))[0]))
    predicted_minutes = min(max(0.0, predicted_minutes), MAX_FORECAST_MINUTES)
    
    severity = severity_tier(predicted_minutes)
    resources = recommend_resources(predicted_minutes, severity, event, stats)
    
    planned_impact = None
    if normalize_text(event.get("event_type")) == "planned":
        planned_impact = forecast_planned_event(event, stats, planned_stats)
        
    return {
        "predicted_duration_min": round(predicted_minutes, 2),
        "predicted_severity": severity,
        "resource_plan": resources,
        "planned_impact": planned_impact,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Predict event impact and resource needs.")
    parser.add_argument("--bundle", default="artifacts/astram_model_bundle.json", help="Path to the trained model bundle.")
    parser.add_argument("--json", help="Path to a JSON file with a single event record.")
    args = parser.parse_args()

    bundle_path = Path(args.bundle)
    if not bundle_path.exists():
        raise FileNotFoundError(f"Bundle not found: {bundle_path}")

    with bundle_path.open("r", encoding="utf-8") as f:
        bundle = json.load(f)
    duration_booster = load_duration_booster(bundle)

    if not args.json:
        raise SystemExit("Pass --json with an event record to score.")

    event_path = Path(args.json)
    with event_path.open("r", encoding="utf-8") as f:
        event = json.load(f)

    output = predict_from_bundle(bundle, event, duration_booster=duration_booster)
    print(json.dumps(output, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())