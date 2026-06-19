from __future__ import annotations

import argparse
import json
import math
import pickle
import re
import shutil
from collections import Counter, defaultdict
from dataclasses import asdict
from pathlib import Path
import numpy as np
# pyrefly: ignore [missing-import]
import lightgbm as lgb
import optuna
from sklearn.feature_extraction import DictVectorizer
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score, accuracy_score
from sklearn.model_selection import TimeSeriesSplit

from astram_data import (
    AggregateStats,
    build_hotspot_rows,
    corridor_diversion_hint,
    day_features,
    duration_minutes,
    fit_aggregate_stats,
    is_truthy,
    normalize_text,
    parse_dt,
    read_csv_rows,
    safe_float,
    severity_tier,
)
from operations import PlannedImpactStats, build_dbscan_hotspots, build_planned_impact_stats
from operations import nearest_hotspot_features
from reporting import build_service_payload, write_graphs, write_report_text

SEVERITY_ORDER = ["low", "medium", "high", "critical"]
MAX_FORECAST_MINUTES = 720.0

DEFAULT_LIGHTGBM_PARAMS = {
    "objective": "huber",        
    "metric": "rmse",                 
    "boosting_type": "gbdt",
    "num_leaves": 45,
    "max_depth": 8,
    "learning_rate": 0.03,
    "min_data_in_leaf": 15,
    "feature_fraction": 0.85,
    "reg_lambda": 5.0,
    "force_row_wise": True,
    "verbose": -1
}


def load_supervised_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    usable = []
    for row in rows:
        duration = duration_minutes(row)
        if duration is None:
            continue
        row = dict(row)
        row["_duration_min"] = duration
        usable.append(row)
    usable.sort(key=lambda r: parse_dt(r.get("start_datetime")) or parse_dt("1970-01-01 00:00:00") or 0)
    return usable

    
def split_time_order(rows: list[dict[str, str]], test_fraction: float = 0.2) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    n_test = max(1, int(len(rows) * test_fraction))
    split = len(rows) - n_test
    return rows[:split], rows[split:]


def _category(value: str, default: str = "unknown") -> str:
    text = normalize_text(value)
    return text if text else default


def _extract_pin(addr: str | None) -> str:
    if not addr:
        return "unknown"
    m = re.search(r'Pin[- ]?(\d{6})', addr, re.IGNORECASE)
    return m.group(1) if m else "unknown"


def build_v2_target_maps(train_rows: list[dict[str, str]], global_median: float, duration_by_cause: dict[str, float]) -> dict[str, dict]:
    """Compiles single variables along with compound joint intersections into a standard dictionary container."""
    cc_groups = defaultdict(list)
    pin_groups = defaultdict(list)
    month_groups = defaultdict(list)
    grid_groups = defaultdict(list)
    
    for r in train_rows:
        raw_dur = safe_float(r.get("_duration_min")) or global_median
        dur = min(raw_dur, MAX_FORECAST_MINUTES)  # Cap extreme outliers to balance distributions
        
        c = normalize_text(r.get("event_cause")) or "unknown"
        co = normalize_text(r.get("corridor")) or "unknown"
        pin = _extract_pin(r.get("address"))
        dt = parse_dt(r.get("start_datetime"))
        
        lat = safe_float(r.get("latitude")) or 0.0
        lon = safe_float(r.get("longitude")) or 0.0
        grid_key = (round(lat, 2), round(lon, 2))
        
        cc_groups[(c, co)].append(dur)
        pin_groups[pin].append(dur)
        grid_groups[grid_key].append(dur)
        if dt:
            month_groups[dt.month].append(dur)
            
    return {
        "duration_by_cause_corridor": {f"{k[0]}_x_{k[1]}": float(np.median(v)) for k, v in cc_groups.items()},
        "duration_by_pin": {k: float(np.median(v)) for k, v in pin_groups.items()},
        "duration_by_month": {str(k): float(np.median(v)) for k, v in month_groups.items()},
        "duration_by_grid": {f"GRID_{k[0]}_{k[1]}": float(np.median(v)) for k, v in grid_groups.items()}
    }


def row_features(
    row: dict[str, str],
    stats: AggregateStats,
    v2_maps: dict[str, dict],
    dbscan_hotspots: list[dict[str, float]] | None = None,
) -> dict[str, float | str]:
    dt = parse_dt(row.get("start_datetime"))
    
    features: dict[str, float | str] = {
        "event_type": _category(row.get("event_type")),
        "priority": _category(row.get("priority")).lower(),
        "requires_road_closure": "yes" if is_truthy(row.get("requires_road_closure")) else "no",
        "road_closure_flag": float(is_truthy(row.get("requires_road_closure"))),
        "is_planned": float(normalize_text(row.get("event_type")) == "planned"),
        "latitude": safe_float(row.get("latitude")) or 0.0,
        "longitude": safe_float(row.get("longitude")) or 0.0,
    }
    features.update(day_features(dt))

    cause = _category(row.get("event_cause"))
    corridor = _category(row.get("corridor"))
    zone = _category(row.get("zone"))
    junction = _category(row.get("junction"))
    pin_code = _extract_pin(row.get("address"))

    # V2 Multi-variable Joint Targets safely backed by container dict fallbacks
    cc_string_key = f"{cause}_x_{corridor}"
    if cc_string_key in v2_maps["duration_by_cause_corridor"]:
        features["cause_corridor_joint_median"] = v2_maps["duration_by_cause_corridor"][cc_string_key]
    else:
        features["cause_corridor_joint_median"] = stats.duration_by_cause.get(cause, stats.global_duration_median)

    features["pin_regional_median_duration"] = v2_maps["duration_by_pin"].get(pin_code, stats.global_duration_median)

    if dt:
        features["seasonal_month_median"] = v2_maps["duration_by_month"].get(str(dt.month), stats.global_duration_median)
    else:
        features["seasonal_month_median"] = stats.global_duration_median

    grid_string_key = f"GRID_{round(features['latitude'], 2)}_{round(features['longitude'], 2)}"
    features["geo_grid_median_duration"] = v2_maps["duration_by_grid"].get(grid_string_key, stats.global_duration_median)

    # Base Targets
    features["cause_median_duration"] = stats.duration_by_cause.get(cause, stats.global_duration_median)
    features["corridor_median_duration"] = stats.duration_by_corridor.get(corridor, stats.global_duration_median)
    features["zone_median_duration"] = stats.duration_by_zone.get(zone, stats.global_duration_median)
    features["junction_median_duration"] = stats.global_duration_median
    
    features["cause_frequency"] = stats.freq_by_cause.get(cause, 0.0)
    features["corridor_frequency"] = stats.freq_by_corridor.get(corridor, 0.0)
    features["zone_frequency"] = stats.freq_by_zone.get(zone, 0.0)
    
    features["cause_high_priority_rate"] = stats.high_rate_by_cause.get(cause, stats.global_priority_high_rate)
    features["corridor_high_priority_rate"] = stats.high_rate_by_corridor.get(corridor, stats.global_priority_high_rate)
    
    features["hotspot_score"] = stats.hotspot_scores.get(junction, stats.hotspot_scores.get(corridor, 0.0))
    features["priority_is_high"] = float(features["priority"] == "high")
    features["priority_is_critical"] = float(features["priority"] == "critical")

    if dbscan_hotspots:
        features.update(
            nearest_hotspot_features(
                safe_float(row.get("latitude")),
                safe_float(row.get("longitude")),
                dbscan_hotspots,
            )
        )
    else:
        features["dbscan_min_distance_km"] = 0.0
        features["dbscan_nearest_hotspot_score"] = 0.0
        features["dbscan_nearest_hotspot_count"] = 0.0
        features["hotspots_within_2.5km"] = 0.0
        features["hotspots_within_5km"] = 0.0

    # Interaction Layout Metrics
    features["critical_closure_interaction"] = float(features["priority_is_critical"] * features["road_closure_flag"])
    features["high_risk_location_event"] = float((features["hotspot_score"] > 50.0) and (features["priority_is_high"] == 1.0 or features["priority_is_critical"] == 1.0))
    features["is_weekend_planned"] = float(features.get("is_weekend", 0.0) == 1.0 and features["is_planned"] == 1.0)
    
    features["density_weighted_distance"] = float(features["dbscan_min_distance_km"] / (features["hotspots_within_2.5km"] + 1.0))
    features["regional_concentration_ratio"] = float((features["hotspots_within_2.5km"] + 1.0) / (features["hotspots_within_5km"] + 1.0))
    
    is_peak = float(features.get("is_peak_hour", 0.0) == 1.0)
    features["peak_hour_high_priority"] = float(is_peak == 1.0 and (features["priority_is_high"] == 1.0 or features["priority_is_critical"] == 1.0))
    features["peak_road_closure"] = float(is_peak * features["road_closure_flag"])
    
    global_ref = float(stats.global_duration_median if stats.global_duration_median > 0 else 1.0)
    features["corridor_deviation_factor"] = float(features["corridor_median_duration"] / global_ref)
    features["cause_deviation_factor"] = float(features["cause_median_duration"] / global_ref)
    features["combined_risk_multiplier"] = float(features["corridor_deviation_factor"] * features["cause_deviation_factor"])
    
    features["cause_corridor_expected_scale"] = float(features["cause_median_duration"] * features["corridor_frequency"])
    features["spatial_severity_bound"] = float(features["dbscan_nearest_hotspot_score"] * (features["corridor_median_duration"] + 1.0))

    return features


def build_dataset(
    rows: list[dict[str, str]],
    stats: AggregateStats,
    v2_maps: dict[str, dict],
    dbscan_hotspots: list[dict[str, float]] | None = None,
    upper_winsor_limit: float | None = None,
) -> tuple[list[dict[str, float | str]], np.ndarray, np.ndarray]:
    x_rows: list[dict[str, float | str]] = []
    y_duration: list[float] = []
    y_severity: list[str] = []
    
    for row in rows:
        x_rows.append(row_features(row, stats, v2_maps, dbscan_hotspots=dbscan_hotspots))
        raw_duration = float(row["_duration_min"])
        
        if upper_winsor_limit is not None:
            duration = min(raw_duration, upper_winsor_limit)
        else:
            duration = min(raw_duration, MAX_FORECAST_MINUTES)
            
        y_duration.append(duration)
        y_severity.append(severity_tier(raw_duration))
        
    return x_rows, np.asarray(y_duration, dtype=float), np.asarray(y_severity, dtype=object)


def optimize_hyperparameters(X_train: np.ndarray, y_train: np.ndarray) -> dict[str, object]:
    optuna.logging.set_verbosity(optuna.logging.WARNING)
    
    def objective(trial: optuna.Trial) -> float:
        params = {
            "objective": "huber",
            "metric": "rmse",
            "boosting_type": trial.suggest_categorical("boosting_type", ["gbdt", "dart"]),
            "n_estimators": trial.suggest_int("n_estimators", 100, 400),
            "num_leaves": trial.suggest_int("num_leaves", 31, 90),
            "max_depth": trial.suggest_int("max_depth", 4, 12),
            "learning_rate": trial.suggest_float("learning_rate", 0.008, 0.06, log=True),
            "min_data_in_leaf": trial.suggest_int("min_data_in_leaf", 10, 40),
            "feature_fraction": trial.suggest_float("feature_fraction", 0.65, 0.95),
            "bagging_fraction": trial.suggest_float("bagging_fraction", 0.7, 1.0),
            "bagging_freq": trial.suggest_int("bagging_freq", 1, 5) if trial.relative_params.get("boosting_type") != "dart" else 0,
            "reg_lambda": trial.suggest_float("reg_lambda", 1e-2, 50.0, log=True),
            "reg_alpha": trial.suggest_float("reg_alpha", 1e-2, 50.0, log=True),
            "huber_delta": trial.suggest_float("huber_delta", 0.8, 1.5),
            "force_row_wise": True,
            "verbose": -1
        }
        
        tscv = TimeSeriesSplit(n_splits=3)
        fold_scores = []
        
        for train_idx, val_idx in tscv.split(X_train):
            X_tr, X_val = X_train[train_idx], X_train[val_idx]
            y_tr, y_val = y_train[train_idx], y_train[val_idx]
            
            model = lgb.LGBMRegressor(**params)
            
            if params["boosting_type"] == "gbdt":
                model.fit(
                    X_tr, np.log1p(y_tr),
                    eval_set=[(X_val, np.log1p(y_val))],
                    callbacks=[lgb.early_stopping(stopping_rounds=25, verbose=False)]
                )
            else:
                model.fit(X_tr, np.log1p(y_tr))
                
            preds = np.expm1(model.predict(X_val))
            preds = np.clip(preds, 0.0, MAX_FORECAST_MINUTES)
            fold_scores.append(math.sqrt(mean_squared_error(y_val, preds)))
            
        return float(np.mean(fold_scores))

    print("🚀 Running Advanced Time-Series Optuna search space analysis...")
    study = optuna.create_study(direction="minimize")
    study.optimize(objective, n_trials=35)
    
    best_params = {
        "objective": "huber",
        "metric": "rmse",
        "force_row_wise": True,
        "verbose": -1,
        **study.best_params
    }
    print(f"🎯 Ideal Parameters Secured: {json.dumps(study.best_params, indent=2)}")
    return best_params


def fit_models(
    train_x: list[dict[str, float | str]],
    train_y_duration: np.ndarray,
    lgb_params: dict[str, object],
) -> tuple[DictVectorizer, lgb.LGBMRegressor]:
    vec_duration = DictVectorizer(sparse=False)
    X_duration = vec_duration.fit_transform(train_x).astype(np.float32, copy=False)

    duration_model = lgb.LGBMRegressor(**lgb_params)
    duration_model.fit(X_duration, np.log1p(train_y_duration))

    return vec_duration, duration_model


def evaluate_models(
    duration_vec: DictVectorizer,
    duration_model: lgb.LGBMRegressor,
    test_x: list[dict[str, float | str]],
    test_y_duration: np.ndarray,
    test_y_severity: np.ndarray,
) -> dict[str, float | str]:
    log_pred = duration_model.booster_.predict(duration_vec.transform(test_x).astype(np.float32, copy=False))
    duration_pred = np.expm1(log_pred)
    duration_pred = np.clip(duration_pred, 0.0, MAX_FORECAST_MINUTES)
    
    test_y_duration = np.clip(test_y_duration, 0.0, MAX_FORECAST_MINUTES)

    duration_mae = mean_absolute_error(test_y_duration, duration_pred)
    duration_rmse = math.sqrt(mean_squared_error(test_y_duration, duration_pred))
    duration_r2 = r2_score(test_y_duration, duration_pred)
    
    pred_severity = np.array([severity_tier(d) for d in duration_pred], dtype=object)
    sev_accuracy = accuracy_score(test_y_severity, pred_severity)

    return {
        "duration_mae_min": float(duration_mae),
        "duration_rmse_min": float(duration_rmse),
        "duration_r2": float(duration_r2),
        "severity_accuracy": float(sev_accuracy),
    }


def make_prediction_bundle(
    duration_vec: DictVectorizer,
    duration_model: lgb.LGBMRegressor,
    stats: AggregateStats,
    v2_maps: dict[str, dict],
    planned_stats: PlannedImpactStats,
    train_rows: list[dict[str, str]],
    upper_winsor_limit: float,
    lgb_params: dict[str, object]
) -> dict[str, object]:
    train_hotspots = build_hotspot_rows(train_rows, stats)
    dbscan_hotspots = [asdict(item) for item in build_dbscan_hotspots(train_rows)]
    train_x = [row_features(r, stats, v2_maps, dbscan_hotspots=dbscan_hotspots) for r in train_rows]
    
    log_train_pred = duration_model.booster_.predict(duration_vec.transform(train_x).astype(np.float32, copy=False))
    train_duration_pred = np.expm1(log_train_pred)
    train_duration_pred = np.clip(train_duration_pred, 0.0, MAX_FORECAST_MINUTES)
    
    train_duration_true = np.asarray([min(r["_duration_min"], upper_winsor_limit) for r in train_rows], dtype=float)
    residuals = np.asarray(train_duration_true - train_duration_pred, dtype=float)
    
    interval = {
        "p10": float(np.percentile(residuals, 10)),
        "p90": float(np.percentile(residuals, 90)),
    }
    gain_importance = duration_model.booster_.feature_importance(importance_type="gain")
    split_importance = duration_model.booster_.feature_importance(importance_type="split")
    feature_names = duration_vec.get_feature_names_out().tolist()
    feature_importance = [
        {
            "feature": name,
            "gain": float(gain),
            "split": int(split),
        }
        for name, gain, split in sorted(
            zip(feature_names, gain_importance, split_importance, strict=False),
            key=lambda item: item[1],
            reverse=True,
        )
    ]

    serialized_stats = asdict(stats)
    serialized_stats.update(v2_maps)

    bundle = {
        "feature_names": feature_names,
        "duration_model_file": str(Path("artifacts") / "lightgbm_duration.txt"),
        "duration_model_params": lgb_params,
        "duration_feature_importance": feature_importance,
        "stats": serialized_stats,
        "planned_stats": asdict(planned_stats),
        "residual_interval": interval,
        "train_hotspots": train_hotspots[:25],
        "dbscan_hotspots": dbscan_hotspots[:25],
    }
    return bundle


def recommend_resources(predicted_minutes: float, severity: str, row: dict[str, str], stats: AggregateStats) -> dict[str, object]:
    severity = severity.lower()
    manpower_map = {"low": 1, "medium": 2, "high": 4, "critical": 6}
    barricade_map = {"low": 0, "medium": 1, "high": 2, "critical": 4}

    manpower = manpower_map.get(severity, 2)
    barricades = barricade_map.get(severity, 1)

    cause = normalize_text(row.get("event_cause"))
    event_type = normalize_text(row.get("event_type"))
    if cause in {"public_event", "procession", "vip_movement", "protest"}:
        manpower += 2
        barricades += 1
    if cause == "water_logging":
        manpower += 1
    if cause in {"construction", "road_conditions"}:
        barricades += 1
    if is_truthy(row.get("requires_road_closure")):
        barricades += 2
    if event_type == "planned":
        manpower += 1

    corridor = normalize_text(row.get("corridor"))
    corridor_risk = stats.hotspot_scores.get(corridor, 0.0)
    if corridor_risk > 70:
        manpower += 1
        barricades += 1

    manpower = max(1, manpower)
    barricades = max(0, barricades)
    diversion = corridor_diversion_hint(corridor)
    if event_type == "planned":
        diversion = f"Pre-stage resources {diversion.lower()}"

    return {
        "predicted_duration_min": round(predicted_minutes, 2),
        "severity_tier": severity,
        "manpower": manpower,
        "barricades": barricades,
        "diversion": diversion,
        "risk_score": round(min(100.0, max(0.0, corridor_risk + predicted_minutes / 10.0)), 2)
    }


def build_app_data(
    rows: list[dict[str, str]],
    stats: AggregateStats,
    bundle: dict[str, object],
    metrics: dict[str, float | str],
) -> dict[str, object]:
    hour_counts: Counter[str] = Counter()
    cause_counts = Counter(normalize_text(row.get("event_cause")) for row in rows if normalize_text(row.get("event_cause")))

    for row in rows:
        dt = parse_dt(row.get("start_datetime"))
        if dt is None:
            continue
        hour_counts[str(dt.hour)] += 1

    corridors = sorted({normalize_text(row.get("corridor")) for row in rows if normalize_text(row.get("corridor"))})
    causes = sorted({normalize_text(row.get("event_cause")) for row in rows if normalize_text(row.get("event_cause")) and normalize_text(row.get("event_cause")) not in {"test_demo"}})
    zones = sorted({normalize_text(row.get("zone")) for row in rows if normalize_text(row.get("zone"))})

    return {
        "metrics": {
            "mae": round(float(metrics["duration_mae_min"]), 2),
            "r2": round(float(metrics["duration_r2"]), 4),
            "train_n": int(metrics.get("train_rows", 0)),
            "test_n": int(metrics.get("test_rows", 0)),
        },
        "hotspots": bundle["train_hotspots"][:20],
        "cause_counts": dict(cause_counts.most_common(15)),
        "hour_counts": dict(sorted(hour_counts.items(), key=lambda item: int(item[0]))),
        "top_features": [
            {"name": item["feature"], "importance": int(item["split"])}
            for item in bundle["duration_feature_importance"][:15]
        ],
        "corridors": corridors,
        "causes": causes,
        "zones": zones,
        "global_median": round(float(stats.global_duration_median), 1),
        "cause_medians": {k: round(float(v), 1) for k, v in stats.duration_by_cause.items()},
        "hotspot_scores": {k: round(float(v), 2) for k, v in list(stats.hotspot_scores.items())[:50]},
        "planned_multipliers": {k: round(float(v), 2) for k, v in stats.planned_multiplier_by_cause.items()},
    }


def train_and_save(rows: list[dict[str, str]], outdir: Path, skip_tuning: bool = False) -> dict[str, object]:
    supervised_rows = load_supervised_rows(rows)
    train_rows, test_rows = split_time_order(supervised_rows, test_fraction=0.2)
    
    # 1. Compile immutable foundation stats object
    stats = fit_aggregate_stats(train_rows)
    
    # 2. Build our separate target lookup mappings to avoid dataclass dynamic attribute errors
    v2_maps = build_v2_target_maps(train_rows, stats.global_duration_median, stats.duration_by_cause)
    
    planned_stats = build_planned_impact_stats(train_rows)
    dbscan_hotspots = [asdict(item) for item in build_dbscan_hotspots(train_rows)]
    outdir.mkdir(parents=True, exist_ok=True)

    upper_winsor_limit = MAX_FORECAST_MINUTES

    train_x, train_y_duration, train_y_severity = build_dataset(train_rows, stats, v2_maps, dbscan_hotspots=dbscan_hotspots, upper_winsor_limit=upper_winsor_limit)
    test_x, test_y_duration, test_y_severity = build_dataset(test_rows, stats, v2_maps, dbscan_hotspots=dbscan_hotspots, upper_winsor_limit=upper_winsor_limit)

    if not skip_tuning:
        temp_vec = DictVectorizer(sparse=False)
        X_train_encoded = temp_vec.fit_transform(train_x).astype(np.float32, copy=False)
        lgb_params = optimize_hyperparameters(X_train_encoded, train_y_duration)
    else:
        print("Using default robust configurations.")
        lgb_params = DEFAULT_LIGHTGBM_PARAMS

    duration_vec, duration_model = fit_models(train_x, train_y_duration, lgb_params)
    metrics = evaluate_models(duration_vec, duration_model, test_x, test_y_duration, test_y_severity)
    
    metrics["train_rows"] = float(len(train_rows))
    metrics["test_rows"] = float(len(test_rows))

    duration_model_path = outdir / "lightgbm_duration.txt"
    duration_model.booster_.save_model(str(duration_model_path))
    duration_model.booster_.save_model(str(outdir / "lgb_model.txt"))
    with (outdir / "vec.pkl").open("wb") as f:
        pickle.dump(duration_vec, f)
        
    bundle = make_prediction_bundle(
        duration_vec,
        duration_model,
        stats,
        v2_maps,
        planned_stats,
        train_rows,
        upper_winsor_limit=upper_winsor_limit,
        lgb_params=lgb_params
    )
    bundle["duration_model_file"] = str(duration_model_path)

    artifact_path = outdir / "astram_model_bundle.json"
    with artifact_path.open("w", encoding="utf-8") as f:
        json.dump(bundle, f)
        
    with (outdir / "bundle.json").open("w", encoding="utf-8") as f:
        json.dump(
            {
                "feature_names": bundle["feature_names"],
                "lgb_model": str(outdir / "lgb_model.txt"),
                "duration_model_file": bundle["duration_model_file"],
                "duration_model_params": lgb_params,
                "stats": bundle["stats"],
                "planned_stats": bundle["planned_stats"],
            },
            f,
            indent=2,
        )

    serialized_summary_stats = asdict(stats)
    serialized_summary_stats.update(v2_maps)

    summary = {
        "rows_total": len(rows),
        "rows_with_duration": len(supervised_rows),
        "train_rows": len(train_rows),
        "test_rows": len(test_rows),
        "forecast_cap": MAX_FORECAST_MINUTES,
        "lightgbm_params": lgb_params,
        "metrics": metrics,
        "stats": serialized_summary_stats,
        "planned_stats": asdict(planned_stats),
        "top_hotspots": bundle["train_hotspots"][:10],
        "dbscan_hotspots": bundle["dbscan_hotspots"][:10],
    }
    with (outdir / "training_summary.json").open("w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    with (outdir / "training_summary.txt").open("w", encoding="utf-8") as f:
        f.write(f"Rows total: {len(rows)}\n")
        f.write(f"Rows with valid duration: {len(supervised_rows)}\n")
        f.write(f"Train rows: {len(train_rows)}\n")
        f.write(f"Test rows: {len(test_rows)}\n")
        f.write(f"Duration MAE (min): {metrics['duration_mae_min']:.2f}\n")
        f.write(f"Duration RMSE (min): {metrics['duration_rmse_min']:.2f}\n")
        f.write(f"Duration R2: {metrics['duration_r2']:.4f}\n")
        f.write(f"Severity Accuracy: {metrics['severity_accuracy']:.4f}\n")

    hotspot_path = outdir / "hotspots.json"
    with hotspot_path.open("w", encoding="utf-8") as f:
        json.dump(bundle["train_hotspots"], f, indent=2)

    graph_paths = write_graphs(outdir, rows, planned_stats, bundle, metrics)
    bundle["graph_paths"] = graph_paths

    write_report_text(
        outdir / "report.txt",
        rows,
        supervised_rows,
        stats,
        planned_stats,
        dbscan_hotspots,
        bundle,
        {
            **metrics,
            "train_rows": len(train_rows),
            "test_rows": len(test_rows),
            "forecast_cap": MAX_FORECAST_MINUTES,
        },
    )

    service_payload = build_service_payload(rows, supervised_rows, stats, planned_stats, dbscan_hotspots, bundle, metrics)
    service_payload["graph_paths"] = graph_paths
    with (outdir / "service_payload.json").open("w", encoding="utf-8") as f:
        json.dump(service_payload, f, indent=2)

    app_data = build_app_data(rows, stats, bundle, metrics)
    with (outdir / "app_data.json").open("w", encoding="utf-8") as f:
        json.dump(app_data, f, indent=2)

    shutil.copyfile(duration_model_path, outdir / "lgb_model.txt")

    print("Training complete")
    print(json.dumps(summary["metrics"], indent=2))
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Train the Astram event impact model.")
    parser.add_argument("--csv", default="", help="Path to the Astram CSV file.")
    parser.add_argument("--outdir", default="artifacts", help="Directory to write trained artifacts.")
    parser.add_argument("--skip-tuning", action="store_true", help="Skip Optuna hyperparameter optimization.")
    args = parser.parse_args()

    if args.csv:
        csv_path = Path(args.csv)
    else:
        dataset_dir = Path("dataset")
        csv_files = list(dataset_dir.glob("*.csv"))
        if len(csv_files) == 1:
            csv_path = csv_files[0]
        elif len(csv_files) == 0:
            raise FileNotFoundError("No CSV files found in 'dataset'.")
        else:
            raise ValueError("Multiple CSV files found in 'dataset'.")
            
    outdir = Path(args.outdir)
    rows = read_csv_rows(csv_path)
    train_and_save(rows, outdir, skip_tuning=args.skip_tuning)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())