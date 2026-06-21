"""
train.py  –  Train dual-stage model:
  1) HistGradientBoostingRegressor  →  duration (minutes, log-space)
  2) HistGradientBoostingClassifier →  severity tier (4-class)

No LightGBM required.  Uses sklearn HistGBM which matches LightGBM performance
on tabular data and natively handles categoricals.
"""
from __future__ import annotations
from sklearn.inspection import permutation_importance
import json
import math
import pickle
from collections import Counter
from dataclasses import asdict
from pathlib import Path
from typing import Any
import matplotlib.pyplot as plt
import numpy as np
from sklearn.metrics import precision_score, recall_score
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import (
    HistGradientBoostingClassifier,
    HistGradientBoostingRegressor,
    VotingRegressor,
    RandomForestClassifier,
)
from sklearn.metrics import (
    accuracy_score,
    f1_score,
    confusion_matrix,
    mean_absolute_error,
    mean_squared_error,
    r2_score,
    classification_report,
)
from sklearn.model_selection import TimeSeriesSplit
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OrdinalEncoder

from astram_data import (
    AggregateStats,
    MAX_DURATION_MINUTES,
    SEVERITY_MAP,
    REV_SEVERITY_MAP,
    build_hotspot_rows,
    duration_minutes,
    fit_aggregate_stats,
    is_truthy,
    normalize_text,
    parse_dt,
    read_csv_rows,
    severity_tier,
)
from features import build_v2_target_maps, row_features
from operations import (
    DbscanHotspot,
    build_dbscan_hotspots,
    build_planned_impact_stats
)
from plots import (
    save_actual_vs_predicted,
    save_bar_chart,
    save_confusion_heatmap,
    save_feature_importance_fallback,
    save_residual_histogram,
)
from reporting import build_service_payload, write_report_text

# Re-export for predict.py
from astram_data import corridor_diversion_hint

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
MAX_FORECAST_MINUTES = MAX_DURATION_MINUTES


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------
def load_supervised_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    usable = []
    for row in rows:
        dur = duration_minutes(row)
        if dur is None:
            continue
        r = dict(row)
        r["_duration_min"] = dur
        usable.append(r)
    usable.sort(key=lambda r: parse_dt(r.get("start_datetime")) or parse_dt("1970-01-01 00:00:00") or 0)
    return usable


def split_time_order(rows: list[dict[str, str]], test_fraction: float = 0.2):
    n_test = max(1, int(len(rows) * test_fraction))
    split = len(rows) - n_test
    return rows[:split], rows[split:]


# ---------------------------------------------------------------------------
# Dataset construction
# ---------------------------------------------------------------------------
def build_dataset(
    rows: list[dict[str, str]],
    stats: AggregateStats,
    v2_maps: dict[str, dict],
    dbscan_hotspots: list[dict] | None = None,
    upper_winsor_limit: float | None = None,
) -> tuple[list[dict], np.ndarray, np.ndarray]:
    cap = upper_winsor_limit or MAX_FORECAST_MINUTES
    x_rows, y_dur, y_sev = [], [], []
    for row in rows:
        x_rows.append(row_features(row, stats, v2_maps, dbscan_hotspots=dbscan_hotspots))
        raw = float(row["_duration_min"])
        dur = min(raw, cap)
        y_dur.append(dur)
        y_sev.append(SEVERITY_MAP.get(severity_tier(raw), 0))
    return x_rows, np.asarray(y_dur, dtype=float), np.asarray(y_sev, dtype=int)


# ---------------------------------------------------------------------------
# Build sklearn pipeline (handles numeric + categorical automatically)
# ---------------------------------------------------------------------------
def _get_feature_types(sample_row: dict) -> tuple[list[str], list[str]]:
    """Identify categorical vs numeric columns from a sample feature row."""
    cat_cols = [k for k, v in sample_row.items() if isinstance(v, str)]
    num_cols = [k for k, v in sample_row.items() if not isinstance(v, str)]
    return cat_cols, num_cols


def _build_preprocessor(cat_cols: list[str], num_cols: list[str]) -> ColumnTransformer:
    """
    OrdinalEncoder for categoricals (HistGBM can use them natively),
    passthrough for numerics.
    """
    transformers = []
    if cat_cols:
        transformers.append((
            "cat",
            OrdinalEncoder(handle_unknown="use_encoded_value", unknown_value=-1),
            cat_cols,
        ))
    if num_cols:
        transformers.append(("num", "passthrough", num_cols))
    return ColumnTransformer(transformers=transformers, remainder="drop")


def rows_to_matrix(x_rows: list[dict], cat_cols: list[str], num_cols: list[str]) -> np.ndarray:
    """Convert list-of-dicts to numpy matrix in correct column order."""
    all_cols = cat_cols + num_cols
    result = np.zeros((len(x_rows), len(all_cols)), dtype=object)
    for i, row in enumerate(x_rows):
        for j, col in enumerate(all_cols):
            result[i, j] = row.get(col, "" if col in cat_cols else 0.0)
    return result


# ---------------------------------------------------------------------------
# Model training
# ---------------------------------------------------------------------------
REGRESSOR_PARAMS = {
    "max_iter": 500,
    "learning_rate": 0.05,
    "max_depth": 7,
    "min_samples_leaf": 20,
    "l2_regularization": 5.0,
    "max_leaf_nodes": 35,
    "early_stopping": True,
    "validation_fraction": 0.1,
    "n_iter_no_change": 30,
    "random_state": 42,
    "categorical_features": "from_dtype",   # will be set in pipeline
}

CLASSIFIER_PARAMS = {
    "max_iter": 500,
    "learning_rate": 0.05,
    "max_depth": 6,
    "min_samples_leaf": 15,
    "l2_regularization": 3.0,
    "max_leaf_nodes": 24,
    "early_stopping": True,
    "validation_fraction": 0.1,
    "n_iter_no_change": 30,
    "class_weight": "balanced",
    "random_state": 42,
    "categorical_features": "from_dtype",
}


def fit_models(
    train_x: list[dict],
    train_y_dur: np.ndarray,
    train_y_sev: np.ndarray,
) -> tuple[list[str], list[str], OrdinalEncoder, HistGradientBoostingRegressor, HistGradientBoostingClassifier]:
    """
    Returns (cat_cols, num_cols, encoder, duration_model, severity_model).
    """
    sample = train_x[0]
    cat_cols, num_cols = _get_feature_types(sample)
    all_cols = cat_cols + num_cols

    # Build matrix
    X = rows_to_matrix(train_x, cat_cols, num_cols)

    # Encode categoricals with OrdinalEncoder
    enc = OrdinalEncoder(handle_unknown="use_encoded_value", unknown_value=-1)

    X_num = X[:, len(cat_cols):].astype(float)  # numeric part
    if cat_cols:
        X_cat = enc.fit_transform(X[:, :len(cat_cols)])
        X_final = np.concatenate([X_cat, X_num], axis=1).astype(float)
        # Mark categorical indices for HistGBM
        cat_indices = list(range(len(cat_cols)))
    else:
        X_final = X_num
        cat_indices = []

    # Duration regressor (predict log1p(duration))
    reg_params = {k: v for k, v in REGRESSOR_PARAMS.items() if k != "categorical_features"}
    reg_params["categorical_features"] = cat_indices if cat_indices else None
    dur_model = HistGradientBoostingRegressor(**reg_params)
    dur_model.fit(X_final, np.log1p(train_y_dur))

    # Severity classifier
    clf_params = {k: v for k, v in CLASSIFIER_PARAMS.items() if k != "categorical_features"}
    clf_params["categorical_features"] = cat_indices if cat_indices else None
    sev_model = HistGradientBoostingClassifier(**clf_params)
    sev_model.fit(X_final, train_y_sev)

    return cat_cols, num_cols, enc, dur_model, sev_model


def transform(x_rows: list[dict], cat_cols: list[str], num_cols: list[str], enc: OrdinalEncoder) -> np.ndarray:
    X = rows_to_matrix(x_rows, cat_cols, num_cols)
    X_num = X[:, len(cat_cols):].astype(float)
    if cat_cols:
        X_cat = enc.transform(X[:, :len(cat_cols)])
        return np.concatenate([X_cat, X_num], axis=1).astype(float)
    return X_num


# ---------------------------------------------------------------------------
# Evaluation
# ---------------------------------------------------------------------------
def evaluate_models(
    cat_cols, num_cols, enc,
    dur_model: HistGradientBoostingRegressor,
    sev_model: HistGradientBoostingClassifier,
    test_x: list[dict],
    test_y_dur: np.ndarray,
    test_y_sev: np.ndarray,
) -> dict[str, float | str]:
    X_test = transform(test_x, cat_cols, num_cols, enc)
    dur_pred = np.expm1(dur_model.predict(X_test))
    dur_pred = np.clip(dur_pred, 0.0, MAX_FORECAST_MINUTES)
    test_y_dur_c = np.clip(test_y_dur, 0.0, MAX_FORECAST_MINUTES)

    mae = float(mean_absolute_error(test_y_dur_c, dur_pred))
    rmse = float(math.sqrt(mean_squared_error(test_y_dur_c, dur_pred)))
    r2 = float(r2_score(test_y_dur_c, dur_pred))

    sev_pred = sev_model.predict(X_test)
    acc = float(accuracy_score(test_y_sev, sev_pred))
    f1_macro = float(f1_score(test_y_sev, sev_pred, average="macro", zero_division=0))
    f1_weighted = float(f1_score(test_y_sev, sev_pred, average="weighted", zero_division=0))

    report = classification_report(
        test_y_sev, sev_pred,
        target_names=["low", "medium", "high", "critical"],
        zero_division=0,
    )

    return {
        "duration_mae_min": mae,
        "duration_rmse_min": rmse,
        "duration_r2": r2,
        "severity_accuracy": acc,
        "severity_f1_macro": f1_macro,
        "severity_f1_weighted": f1_weighted,
        "severity_classification_report": report,
    }


# ---------------------------------------------------------------------------
# Resource recommendation
# ---------------------------------------------------------------------------
def recommend_resources(
    predicted_minutes: float, severity: str, row: dict[str, Any], stats: AggregateStats
) -> dict[str, Any]:
    severity = severity.lower()
    manpower = {"low": 1, "medium": 2, "high": 4, "critical": 6}.get(severity, 2)
    barricades = {"low": 0, "medium": 1, "high": 2, "critical": 4}.get(severity, 1)

    cause = normalize_text(row.get("event_cause"))
    event_type = normalize_text(row.get("event_type"))
    if cause in {"public_event", "procession", "vip_movement", "protest"}:
        manpower += 2
        barricades += 1
    if cause == "water_logging":
        manpower += 1
    if cause in {"construction", "road_conditions", "pot_holes"}:
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

    diversion = corridor_diversion_hint(corridor)
    if event_type == "planned":
        diversion = f"Pre-stage resources. {diversion}"

    return {
        "predicted_duration_min": round(predicted_minutes, 2),
        "severity_tier": severity,
        "manpower": max(1, manpower),
        "barricades": max(0, barricades),
        "diversion": diversion,
        "risk_score": round(min(100.0, max(0.0, corridor_risk + predicted_minutes / 10.0)), 2),
    }


# ---------------------------------------------------------------------------
# Feature importance (permutation-based for HistGBM)
# ---------------------------------------------------------------------------
def get_feature_importance(
    cat_cols: list[str], num_cols: list[str], dur_model, X_test: np.ndarray, y_test: np.ndarray
) -> list[dict]:
    # Use permutation importance because HistGBM doesn't store feature_importances_
    result = permutation_importance(
        dur_model, X_test, y_test, n_repeats=5, random_state=42, n_jobs=1
    )
    importances = result.importances_mean
    return sorted(
        [{"feature": name, "importance": float(imp)} for name, imp in zip(cat_cols + num_cols, importances)],
        key=lambda x: x["importance"],
        reverse=True,
    )

   # =========================================================
    # HACKATHON VISUALIZATION HELPERS
    # =========================================================

def save_confusion_matrix(y_true, y_pred, labels, out_path):
    cm = confusion_matrix(y_true, y_pred)

    plt.figure(figsize=(7, 6))
    plt.imshow(cm, cmap="Blues")
    plt.title("Confusion Matrix - Severity")
    plt.colorbar()

    plt.xticks(range(len(labels)), labels, rotation=45)
    plt.yticks(range(len(labels)), labels)

    for i in range(len(labels)):
        for j in range(len(labels)):
            plt.text(j, i, cm[i, j], ha="center", va="center")

    plt.xlabel("Predicted")
    plt.ylabel("Actual")
    plt.tight_layout()
    plt.savefig(out_path)
    plt.close()


def save_f1_precision_recall(y_true, y_pred, labels, out_path):
    f1 = f1_score(y_true, y_pred, average=None)
    prec = precision_score(y_true, y_pred, average=None)
    rec = recall_score(y_true, y_pred, average=None)

    x = np.arange(len(labels))

    plt.figure(figsize=(10, 6))
    plt.bar(x - 0.2, f1, 0.2, label="F1")
    plt.bar(x, prec, 0.2, label="Precision")
    plt.bar(x + 0.2, rec, 0.2, label="Recall")

    plt.xticks(x, labels)
    plt.title("Classification Metrics")
    plt.legend()
    plt.tight_layout()
    plt.savefig(out_path)
    plt.close()


def save_actual_vs_predicted(actual, pred, out_path):
    plt.figure(figsize=(6, 6))
    plt.scatter(actual, pred, alpha=0.5)

    max_val = max(max(actual), max(pred))
    plt.plot([0, max_val], [0, max_val], "r--")
    plt.title("Actual vs Predicted Duration")
    plt.xlabel("Actual")
    plt.ylabel("Predicted")
    plt.tight_layout()
    plt.savefig(out_path)
    plt.close()


def save_residuals(actual, pred, out_path):
    residuals = np.array(actual) - np.array(pred)

    plt.figure(figsize=(8, 5))
    plt.hist(residuals, bins=40, color="purple", alpha=0.7)
    plt.axvline(0, color="red")
    plt.title("Residual Distribution")
    plt.xlabel("Error")
    plt.ylabel("Count")
    plt.tight_layout()
    plt.savefig(out_path)
    plt.close()


def save_feature_importance(features, values, out_path):
    idx = np.argsort(values)[-15:]

    plt.figure(figsize=(10, 6))
    plt.barh(np.array(features)[idx], np.array(values)[idx])
    plt.title("Top Feature Importance")
    plt.tight_layout()
    plt.savefig(out_path)
    plt.close()


def save_error_trend(actual, pred, out_path):
    errors = np.abs(np.array(actual) - np.array(pred))

    plt.figure(figsize=(10, 5))
    plt.plot(sorted(errors))
    plt.title("Error Trend (Sorted)")
    plt.xlabel("Samples")
    plt.ylabel("Absolute Error")
    plt.tight_layout()
    plt.savefig(out_path)
    plt.close()


def save_severity_distribution(y, labels, out_path):
    counts = [list(y).count(i) for i in range(len(labels))]

    plt.figure(figsize=(7, 5))
    plt.bar(labels, counts)
    plt.title("Severity Distribution")
    plt.tight_layout()
    plt.savefig(out_path)
    plt.close()

# ---------------------------------------------------------------------------
# Main train-and-save pipeline
# ---------------------------------------------------------------------------
def train_and_save(rows: list[dict[str, str]], outdir: Path) -> dict:
    print(f"[1/6] Preparing {len(rows)} rows...")
    supervised = load_supervised_rows(rows)
    print(f"      {len(supervised)} rows have valid duration.")
    train_rows, test_rows = split_time_order(supervised, test_fraction=0.2)
    print(f"      Train: {len(train_rows)}  |  Test: {len(test_rows)}")

    print("[2/6] Fitting aggregate statistics...")
    stats = fit_aggregate_stats(train_rows)
    v2_maps = build_v2_target_maps(train_rows, stats.global_duration_median, stats.duration_by_cause)
    planned_stats = build_planned_impact_stats(train_rows)

    print("[3/6] Building DBSCAN hotspots...")
    dbscan_raw = build_dbscan_hotspots(train_rows)
    dbscan_hotspots = [asdict(h) for h in dbscan_raw]
    print(f"      {len(dbscan_hotspots)} spatial clusters found.")

    print("[4/6] Extracting features and building dataset...")
    train_x, train_y_dur, train_y_sev = build_dataset(train_rows, stats, v2_maps, dbscan_hotspots)
    test_x, test_y_dur, test_y_sev = build_dataset(test_rows, stats, v2_maps, dbscan_hotspots)
    print(f"      {len(train_x[0])} features per row.")

    print("[5/6] Training HistGradientBoosting regressor + classifier...")
    cat_cols, num_cols, enc, dur_model, sev_model = fit_models(train_x, train_y_dur, train_y_sev)

    print("[6/6] Evaluating on held-out test set...")
    # First, transform the test data so we have X_test
    X_test = transform(test_x, cat_cols, num_cols, enc)
    
    metrics = evaluate_models(cat_cols, num_cols, enc, dur_model, sev_model,
                              test_x, test_y_dur, test_y_sev)
    feat_importance = get_feature_importance(cat_cols, num_cols, dur_model, X_test, test_y_dur)

    print("[7/6] Generating plots...")

    # Transform test data
    X_test = transform(test_x, cat_cols, num_cols, enc)

    # Predictions
    dur_pred = np.expm1(dur_model.predict(X_test))
    dur_pred = np.clip(dur_pred, 0.0, MAX_FORECAST_MINUTES)

    actual = test_y_dur.tolist()
    predicted = dur_pred.tolist()

    # Residuals
    residuals = [a - p for a, p in zip(actual, predicted)]

    # 1. Actual vs Predicted plot
    save_actual_vs_predicted(actual, predicted, outdir / "actual_vs_pred.png")

    # 2. Residual histogram
    save_residual_histogram(residuals, outdir / "residuals.png")

    
    print("[7/7] Generating hackathon graphs...")

    X_test = transform(test_x, cat_cols, num_cols, enc)

    dur_pred = np.expm1(dur_model.predict(X_test))
    dur_pred = np.clip(dur_pred, 0, MAX_FORECAST_MINUTES)

    actual = test_y_dur.tolist()
    sev_pred = sev_model.predict(X_test)

    labels = ["low", "medium", "high", "critical"]

    


     

    # 1. Confusion Matrix
    save_confusion_matrix(test_y_sev, sev_pred, labels, outdir / "confusion_matrix.png")

    # 2. F1 / Precision / Recall
    save_f1_precision_recall(test_y_sev, sev_pred, labels, outdir / "metrics_bar.png")

    # 3. Actual vs Predicted
    save_actual_vs_predicted(actual, dur_pred, outdir / "actual_vs_pred.png")

    # 4. Residuals
    save_residuals(actual, dur_pred, outdir / "residuals.png")

    # 5. Feature Importance
    feat_names = [f["feature"] for f in feat_importance]
    feat_vals = [f["importance"] for f in feat_importance]
    save_feature_importance(feat_names, feat_vals, outdir / "feature_importance.png")

    # 6. Error trend
    save_error_trend(actual, dur_pred, outdir / "error_trend.png")

    # 7. Severity distribution
    save_severity_distribution(test_y_sev, labels, outdir / "severity_distribution.png")

    print("All 7 graphs saved successfully ✔")

    print("      Plots saved in artifacts folder.")

    print("\n" + "=" * 55)
    print("  EVALUATION RESULTS")
    print("=" * 55)
    print(f"  Duration MAE  : {metrics['duration_mae_min']:.2f} min")
    print(f"  Duration RMSE : {metrics['duration_rmse_min']:.2f} min")
    print(f"  Duration R²   : {metrics['duration_r2']:.4f}")
    print(f"  Severity Acc  : {metrics['severity_accuracy']:.4f}")
    print(f"  Severity F1   : {metrics['severity_f1_macro']:.4f} (macro)")
    print(f"  Severity F1   : {metrics['severity_f1_weighted']:.4f} (weighted)")
    print("\n  Per-class report:")
    print(metrics["severity_classification_report"])
    print("=" * 55)

    # Compute residuals for prediction intervals
    X_train_t = transform(train_x, cat_cols, num_cols, enc)
    train_dur_pred = np.expm1(dur_model.predict(X_train_t))
    train_dur_pred = np.clip(train_dur_pred, 0.0, MAX_FORECAST_MINUTES)
    train_y_dur_arr = np.asarray([min(r["_duration_min"], MAX_FORECAST_MINUTES) for r in train_rows])
    residuals = train_y_dur_arr - train_dur_pred
    interval = {"p10": float(np.percentile(residuals, 10)), "p90": float(np.percentile(residuals, 90))}

    # Feature importance
    # Pass test_x and test_y_dur to the importance function

    # Hotspot summary rows
    train_hotspots = build_hotspot_rows(train_rows, stats)

    # Serialise aggregate stats
    stats_dict = asdict(stats)
    stats_dict.update(v2_maps)

    # Build bundle
    bundle = {
        "pipeline": "hist_gradient_boosting_dual_stage",
        "cat_cols": cat_cols,
        "num_cols": num_cols,
        "feature_importance": feat_importance,
        "feature_weights": {
            "feature_names": [item["feature"] for item in feat_importance],
            "duration_feature_importance": [
                {"feature": item["feature"], "gain": float(item["importance"]), "split": 0}
                for item in feat_importance
            ],
            "severity_classes": ["low", "medium", "high", "critical"],
            "severity_coef": [],
        },
        "stats": stats_dict,
        "planned_stats": asdict(planned_stats),
        "residual_interval": interval,
        "train_hotspots": train_hotspots[:25],
        "dbscan_hotspots": dbscan_hotspots[:25],
        "duration_model_params": {k: v for k, v in REGRESSOR_PARAMS.items() if k != "categorical_features"},
        "severity_model_params": {k: v for k, v in CLASSIFIER_PARAMS.items() if k != "categorical_features"},
        "duration_model_file": "dur_model.pkl",
        "severity_model_file": "sev_model.pkl",
        "encoder_file": "encoder.pkl",
        "metrics": {k: v for k, v in metrics.items() if k != "severity_classification_report"},
    }

    outdir.mkdir(parents=True, exist_ok=True)

    # Save models
    with (outdir / "dur_model.pkl").open("wb") as f:
        pickle.dump(dur_model, f)
    with (outdir / "sev_model.pkl").open("wb") as f:
        pickle.dump(sev_model, f)
    with (outdir / "encoder.pkl").open("wb") as f:
        pickle.dump(enc, f)
    with open(outdir / "bundle.pkl", "wb") as f:
        pickle.dump(bundle, f)
    with (outdir / "bundle.json").open("w", encoding="utf-8") as f:
        json.dump(bundle, f, indent=2)
    with (outdir / "astram_model_bundle.json").open("w", encoding="utf-8") as f:
        json.dump(bundle, f, indent=2)

    # App data for UI
    hour_counts: Counter = Counter()
    cause_counts: Counter = Counter()
    for row in rows:
        dt = parse_dt(row.get("start_datetime"))
        if dt:
            hour_counts[str(dt.hour)] += 1
        c = normalize_text(row.get("event_cause"))
        if c and c != "test_demo":
            cause_counts[c] += 1

    corridors = sorted({normalize_text(r.get("corridor")) for r in rows if normalize_text(r.get("corridor"))})
    causes = sorted({normalize_text(r.get("event_cause")) for r in rows
                     if normalize_text(r.get("event_cause")) and normalize_text(r.get("event_cause")) != "test_demo"})
    zones = sorted({normalize_text(r.get("zone")) for r in rows if normalize_text(r.get("zone"))})

    app_data = {
        "metrics": {
            "mae": round(metrics["duration_mae_min"], 2),
            "rmse": round(metrics["duration_rmse_min"], 2),
            "r2": round(metrics["duration_r2"], 4),
            "severity_accuracy": round(metrics["severity_accuracy"], 4),
            "severity_f1_macro": round(metrics["severity_f1_macro"], 4),
            "train_n": len(train_rows),
            "test_n": len(test_rows),
        },
        "hotspots": train_hotspots[:20],
        "cause_counts": dict(cause_counts.most_common(15)),
        "hour_counts": dict(sorted(hour_counts.items(), key=lambda x: int(x[0]))),
        "top_features": feat_importance[:15],
        "corridors": corridors,
        "causes": causes,
        "zones": zones,
        "global_median": round(float(stats.global_duration_median), 1),
        "cause_medians": {k: round(float(v), 1) for k, v in stats.duration_by_cause.items()},
        "hotspot_scores": {k: round(float(v), 2) for k, v in list(stats.hotspot_scores.items())[:50]},
        "planned_multipliers": {k: round(float(v), 2) for k, v in stats.planned_multiplier_by_cause.items()},
    }
    with (outdir / "app_data.json").open("w", encoding="utf-8") as f:
        json.dump(app_data, f, indent=2)
    with (outdir / "summary.json").open("w", encoding="utf-8") as f:
        json.dump({"metrics": bundle["metrics"]}, f, indent=2)
    with (outdir / "training_summary.json").open("w", encoding="utf-8") as f:
        json.dump(
            {
                "metrics": bundle["metrics"],
                "feature_weights": bundle["feature_weights"],
                "top_dynamics_features": feat_importance[:15],
            },
            f,
            indent=2,
        )
    (outdir / "report.txt").write_text(
        "\n".join(
            [
                "ASTRAM TRAINING REPORT",
                f"Rows total: {len(rows)}",
                f"Rows with duration: {len(supervised)}",
                f"Train rows: {len(train_rows)}",
                f"Test rows: {len(test_rows)}",
                f"Duration MAE: {metrics['duration_mae_min']:.2f}",
                f"Duration RMSE: {metrics['duration_rmse_min']:.2f}",
                f"Duration R2: {metrics['duration_r2']:.4f}",
                f"Severity accuracy: {metrics['severity_accuracy']:.4f}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    print(f"\nArtifacts saved to: {outdir}")
    return {
        "rows_total": len(rows),
        "rows_with_duration": len(supervised),
        "train_rows": len(train_rows),
        "test_rows": len(test_rows),
        "metrics": {k: v for k, v in metrics.items() if k != "severity_classification_report"},
    }


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Train Astram event impact model.")
    parser.add_argument("--csv", required=True, help="Path to events CSV.")
    parser.add_argument("--outdir", default="../artifacts", help="Output directory.")
    args = parser.parse_args()
    rows = read_csv_rows(args.csv)
    train_and_save(rows, Path(args.outdir))
