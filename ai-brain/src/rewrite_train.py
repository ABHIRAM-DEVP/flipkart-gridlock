import sys

with open("ai-brain/src/train.py", "r") as f:
    code = f.read()

# 1. MAX_FORECAST_MINUTES
code = code.replace("MAX_FORECAST_MINUTES = 720.0", "MAX_FORECAST_MINUTES = 480.0")

# 2. load_supervised_rows
old_load = """def load_supervised_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    usable = []
    for row in rows:
        duration = duration_minutes(row)
        if duration is None:
            continue
        row = dict(row)
        row["_duration_min"] = duration
        usable.append(row)
    usable.sort(key=lambda r: parse_dt(r.get("start_datetime")) or parse_dt("1970-01-01 00:00:00") or 0)
    return usable"""
new_load = """def load_supervised_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    usable = []
    chronic_causes = {"pot_holes", "road_conditions", "debris", "construction", "water_logging"}
    for row in rows:
        cause = normalize_text(row.get("event_cause")).lower()
        if cause in chronic_causes:
            continue
        duration = duration_minutes(row)
        if duration is None:
            continue
        row = dict(row)
        row["_duration_min"] = duration
        usable.append(row)
        
    if usable:
        durs = np.array([r["_duration_min"] for r in usable])
        p95 = np.percentile(durs, 95)
        usable = [r for r in usable if r["_duration_min"] <= p95]
        
    usable.sort(key=lambda r: parse_dt(r.get("start_datetime")) or parse_dt("1970-01-01 00:00:00") or 0)
    return usable"""
code = code.replace(old_load, new_load)

# 3. row_features (drop exact identifiers)
old_features_dict = """    features: dict[str, float | str] = {
        "event_type": _category(row.get("event_type")),
        "priority": _category(row.get("priority")).lower(),
        "requires_road_closure": "yes" if is_truthy(row.get("requires_road_closure")) else "no",
        "road_closure_flag": float(is_truthy(row.get("requires_road_closure"))),
        "is_planned": float(normalize_text(row.get("event_type")) == "planned"),
        "latitude": safe_float(row.get("latitude")) or 0.0,
        "longitude": safe_float(row.get("longitude")) or 0.0,
    }"""
new_features_dict = """    lat = safe_float(row.get("latitude")) or 0.0
    lon = safe_float(row.get("longitude")) or 0.0
    features: dict[str, float | str] = {
        "event_type": _category(row.get("event_type")),
        "priority": _category(row.get("priority")).lower(),
        "requires_road_closure": "yes" if is_truthy(row.get("requires_road_closure")) else "no",
        "road_closure_flag": float(is_truthy(row.get("requires_road_closure"))),
        "is_planned": float(normalize_text(row.get("event_type")) == "planned"),
    }"""
code = code.replace(old_features_dict, new_features_dict)

code = code.replace("grid_string_key = f\"GRID_{round(features['latitude'], 2)}_{round(features['longitude'], 2)}\"", 
                    "grid_string_key = f\"GRID_{round(lat, 2)}_{round(lon, 2)}\"")

code = code.replace("""        features.update(
            nearest_hotspot_features(
                safe_float(row.get("latitude")),
                safe_float(row.get("longitude")),
                dbscan_hotspots,
            )
        )""", """        features.update(
            nearest_hotspot_features(
                lat,
                lon,
                dbscan_hotspots,
            )
        )""")

# 4. compute_severity_label
old_build_ds = """def build_dataset("""
new_build_ds = """def compute_severity_label(row: dict[str, str]) -> int:
    score = 0
    if normalize_text(row.get("priority")).lower() == "high":
        score += 2
    if is_truthy(row.get("requires_road_closure")):
        score += 2
    cause = normalize_text(row.get("event_cause")).lower()
    if cause in {"accident", "protest", "procession"}:
        score += 1
    if cause in {"water_logging", "tree_fall"}:
        score += 1
    if score >= 4: return 3
    if score >= 3: return 2
    if score >= 1: return 1
    return 0


def build_dataset("""
code = code.replace(old_build_ds, new_build_ds)

code = code.replace("""        # Continuous ground truth text mapped directly down to numerical classification labels
        tier_str = severity_tier(raw_duration)
        y_severity.append(SEVERITY_MAP.get(tier_str, 0))""", """        y_severity.append(compute_severity_label(row))""")

# 5. fit_models / evaluate_models
old_fit_eval = """def fit_models(
    train_x: list[dict[str, float | str]],
    train_y_duration: np.ndarray,
    train_y_severity: np.ndarray,
    lgb_params: dict[str, object],
) -> tuple[DictVectorizer, lgb.LGBMRegressor, lgb.LGBMClassifier]:
    vec = DictVectorizer(sparse=False)
    X_train = vec.fit_transform(train_x).astype(np.float32, copy=False)

    # Engine 1: Continuous Duration Tracker (Regression)
    duration_model = lgb.LGBMRegressor(**lgb_params)
    duration_model.fit(X_train, np.log1p(train_y_duration))

    # Engine 2: Native 4-Class Probability Evaluator (Classification)
    severity_model = lgb.LGBMClassifier(**DEFAULT_CLASSIFIER_PARAMS)
    severity_model.fit(X_train, train_y_severity)

    return vec, duration_model, severity_model


def evaluate_models(
    vec: DictVectorizer,
    duration_model: lgb.LGBMRegressor,
    severity_model: lgb.LGBMClassifier,
    test_x: list[dict[str, float | str]],
    test_y_duration: np.ndarray,
    test_y_severity: np.ndarray,
) -> dict[str, float | str]:
    X_test = vec.transform(test_x).astype(np.float32, copy=False)
    
    # Evaluate Regression Performance
    log_pred = duration_model.booster_.predict(X_test)
    duration_pred = np.expm1(log_pred)
    duration_pred = np.clip(duration_pred, 0.0, MAX_FORECAST_MINUTES)
    test_y_duration = np.clip(test_y_duration, 0.0, MAX_FORECAST_MINUTES)

    duration_mae = mean_absolute_error(test_y_duration, duration_pred)
    duration_rmse = math.sqrt(mean_squared_error(test_y_duration, duration_pred))
    duration_r2 = r2_score(test_y_duration, duration_pred)
    
    # Evaluate Multi-Class Severity Performance
    pred_sev_indices = severity_model.predict(X_test)
    sev_accuracy = accuracy_score(test_y_severity, pred_sev_indices)

    return {
        "duration_mae_min": float(duration_mae),
        "duration_rmse_min": float(duration_rmse),
        "duration_r2": float(duration_r2),
        "severity_accuracy": float(sev_accuracy),
    }"""
new_fit_eval = """def fit_models(
    train_x: list[dict[str, float | str]],
    train_y_duration: np.ndarray,
    train_y_severity: np.ndarray,
    lgb_params: dict[str, object],
    selector: np.ndarray | None = None
) -> tuple[DictVectorizer, np.ndarray, lgb.LGBMRegressor, lgb.LGBMClassifier]:
    vec = DictVectorizer(sparse=False)
    X = vec.fit_transform(train_x).astype(np.float32, copy=False)
    
    if selector is None:
        selector = np.var(X, axis=0) > 1e-4
    
    X_pruned = X[:, selector]

    # Regression: Use higher regularization
    reg = lgb.LGBMRegressor(**lgb_params, reg_lambda=20.0, min_data_in_leaf=30)
    reg.fit(X_pruned, np.log1p(train_y_duration))

    # Classifier: Use the same pruned features
    clf = lgb.LGBMClassifier(**DEFAULT_CLASSIFIER_PARAMS)
    clf.fit(X_pruned, train_y_severity)

    return vec, selector, reg, clf


def evaluate_models(
    vec: DictVectorizer,
    selector: np.ndarray,
    duration_model: lgb.LGBMRegressor,
    severity_model: lgb.LGBMClassifier,
    test_x: list[dict[str, float | str]],
    test_y_duration: np.ndarray,
    test_y_severity: np.ndarray,
) -> dict[str, float | str]:
    X_test = vec.transform(test_x).astype(np.float32, copy=False)
    X_test_pruned = X_test[:, selector]  # <--- CRITICAL: Apply the variance mask
    
    # Evaluate Regression Performance
    log_pred = duration_model.predict(X_test_pruned)
    duration_pred = np.expm1(log_pred)
    duration_pred = np.clip(duration_pred, 0.0, MAX_FORECAST_MINUTES)
    test_y_duration = np.clip(test_y_duration, 0.0, MAX_FORECAST_MINUTES)

    duration_mae = mean_absolute_error(test_y_duration, duration_pred)
    duration_rmse = math.sqrt(mean_squared_error(test_y_duration, duration_pred))
    duration_r2 = r2_score(test_y_duration, duration_pred)
    
    # Evaluate Multi-Class Severity Performance
    pred_sev_indices = severity_model.predict(X_test_pruned)
    sev_accuracy = accuracy_score(test_y_severity, pred_sev_indices)

    return {
        "duration_mae_min": float(duration_mae),
        "duration_rmse_min": float(duration_rmse),
        "duration_r2": float(duration_r2),
        "severity_accuracy": float(sev_accuracy),
    }"""
code = code.replace(old_fit_eval, new_fit_eval)

# 6. optimize_hyperparameters uses pruned X
old_train_save = """    if not skip_tuning:
        temp_vec = DictVectorizer(sparse=False)
        X_train_encoded = temp_vec.fit_transform(train_x).astype(np.float32, copy=False)
        lgb_params = optimize_hyperparameters(X_train_encoded, train_y_duration)
    else:
        print("Using default robust configurations.")
        lgb_params = DEFAULT_LIGHTGBM_PARAMS

    vec, duration_model, severity_model = fit_models(train_x, train_y_duration, train_y_severity, lgb_params)
    metrics = evaluate_models(vec, duration_model, severity_model, test_x, test_y_duration, test_y_severity)"""
new_train_save = """    if not skip_tuning:
        temp_vec = DictVectorizer(sparse=False)
        X_train_encoded = temp_vec.fit_transform(train_x).astype(np.float32, copy=False)
        selector = np.var(X_train_encoded, axis=0) > 1e-4
        X_train_pruned = X_train_encoded[:, selector]
        lgb_params = optimize_hyperparameters(X_train_pruned, train_y_duration)
    else:
        print("Using default robust configurations.")
        lgb_params = DEFAULT_LIGHTGBM_PARAMS
        selector = None

    vec, selector, duration_model, severity_model = fit_models(train_x, train_y_duration, train_y_severity, lgb_params, selector)
    with (outdir / "selector.pkl").open("wb") as f:
        pickle.dump(selector, f)
    metrics = evaluate_models(vec, selector, duration_model, severity_model, test_x, test_y_duration, test_y_severity)"""
code = code.replace(old_train_save, new_train_save)

# 7. make_prediction_bundle uses selector
old_bundle = """def make_prediction_bundle(
    vec: DictVectorizer,
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
    
    X_train = vec.transform(train_x).astype(np.float32, copy=False)
    log_train_pred = duration_model.booster_.predict(X_train)"""
new_bundle = """def make_prediction_bundle(
    vec: DictVectorizer,
    selector: np.ndarray,
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
    
    X_train = vec.transform(train_x).astype(np.float32, copy=False)
    X_train_pruned = X_train[:, selector]
    log_train_pred = duration_model.predict(X_train_pruned)"""
code = code.replace(old_bundle, new_bundle)

# Fix feature_names in bundle
code = code.replace("""    feature_names = vec.get_feature_names_out().tolist()""", """    feature_names = np.array(vec.get_feature_names_out())[selector].tolist()""")

# Fix call to make_prediction_bundle
code = code.replace("""    bundle = make_prediction_bundle(
        vec,
        duration_model,
        stats,""", """    bundle = make_prediction_bundle(
        vec,
        selector,
        duration_model,
        stats,""")

with open("ai-brain/src/train.py", "w") as f:
    f.write(code)
