import sys

with open("ai-brain/src/train.py", "r") as f:
    code = f.read()

# 1. Add imblearn import
if "from imblearn.under_sampling import RandomUnderSampler" not in code:
    code = code.replace("from sklearn.model_selection import TimeSeriesSplit",
                        "from sklearn.model_selection import TimeSeriesSplit\nfrom imblearn.under_sampling import RandomUnderSampler")

# 2. Remove priority from row_features
old_features_dict = """        "event_type": _category(row.get("event_type")),
        "priority": _category(row.get("priority")).lower(),
        "requires_road_closure": "yes" if is_truthy(row.get("requires_road_closure")) else "no","""
new_features_dict = """        "event_type": _category(row.get("event_type")),
        "requires_road_closure": "yes" if is_truthy(row.get("requires_road_closure")) else "no","""
code = code.replace(old_features_dict, new_features_dict)

# 3. Remove priority_is_high and priority_is_critical
old_is_priority = """    features["hotspot_score"] = stats.hotspot_scores.get(junction, stats.hotspot_scores.get(corridor, 0.0))
    features["priority_is_high"] = float(features["priority"] == "high")
    features["priority_is_critical"] = float(features["priority"] == "critical")"""
new_is_priority = """    features["hotspot_score"] = stats.hotspot_scores.get(junction, stats.hotspot_scores.get(corridor, 0.0))"""
code = code.replace(old_is_priority, new_is_priority)

# 4. Remove priority_x_road_closure
old_pxrc = """    is_peak = float(features.get("is_peak_hour", 0.0) == 1.0)
    features["priority_x_road_closure"] = f"{features['priority']}_{int(features['road_closure_flag'])}"
    features["cause_x_peak_hour"] = f"{cause}_{int(is_peak)}\""""
new_pxrc = """    is_peak = float(features.get("is_peak_hour", 0.0) == 1.0)
    features["cause_x_peak_hour"] = f"{cause}_{int(is_peak)}\""""
code = code.replace(old_pxrc, new_pxrc)

# 5. Remove downstream interaction features
old_interactions = """    # Interaction Layout Metrics (Log-wrapped where necessary to squash outlier variance)
    features["critical_closure_interaction"] = float(features["priority_is_critical"] * features["road_closure_flag"])
    features["high_risk_location_event"] = float((features["hotspot_score"] > 50.0) and (features["priority_is_high"] == 1.0 or features["priority_is_critical"] == 1.0))
    features["is_weekend_planned"] = float(features.get("is_weekend", 0.0) == 1.0 and features["is_planned"] == 1.0)
    
    features["density_weighted_distance"] = float(features["dbscan_min_distance_km"] / (features["hotspots_within_2.5km"] + 1.0))
    features["regional_concentration_ratio"] = float((features["hotspots_within_2.5km"] + 1.0) / (features["hotspots_within_5km"] + 1.0))
    
    features["peak_hour_high_priority"] = float(is_peak == 1.0 and (features["priority_is_high"] == 1.0 or features["priority_is_critical"] == 1.0))
    features["peak_road_closure"] = float(is_peak * features["road_closure_flag"])"""
new_interactions = """    # Interaction Layout Metrics (Log-wrapped where necessary to squash outlier variance)
    features["is_weekend_planned"] = float(features.get("is_weekend", 0.0) == 1.0 and features["is_planned"] == 1.0)
    
    features["density_weighted_distance"] = float(features["dbscan_min_distance_km"] / (features["hotspots_within_2.5km"] + 1.0))
    features["regional_concentration_ratio"] = float((features["hotspots_within_2.5km"] + 1.0) / (features["hotspots_within_5km"] + 1.0))
    
    features["peak_road_closure"] = float(is_peak * features["road_closure_flag"])"""
code = code.replace(old_interactions, new_interactions)

# 6. Replace fit_models
old_fit_models = """def fit_models(
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

    return vec, duration_model, severity_model"""

new_fit_models = """def fit_models(
    train_x: list[dict[str, float | str]],
    train_y_duration: np.ndarray,
    train_y_severity: np.ndarray,
    lgb_params: dict[str, object],
) -> tuple[DictVectorizer, lgb.LGBMRegressor, lgb.LGBMClassifier]:
    vec = DictVectorizer(sparse=False)
    X_train = vec.fit_transform(train_x).astype(np.float32, copy=False)
    
    # Force the model to see an even distribution of classes
    sampler = RandomUnderSampler(sampling_strategy='majority')
    X_res, y_sev_res = sampler.fit_resample(X_train, train_y_severity)
    
    # We must match the duration target to the sampled indices
    # This ensures the model doesn't over-rely on 'critical'
    sampled_indices = sampler.sample_indices_
    y_dur_res = train_y_duration[sampled_indices]

    # Engine 1: Continuous Duration Tracker (Regression)
    duration_model = lgb.LGBMRegressor(**lgb_params)
    duration_model.fit(X_res, np.log1p(y_dur_res))

    # Engine 2: Native 4-Class Probability Evaluator (Classification)
    severity_model = lgb.LGBMClassifier(**DEFAULT_CLASSIFIER_PARAMS)
    severity_model.fit(X_res, y_sev_res)

    return vec, duration_model, severity_model"""
code = code.replace(old_fit_models, new_fit_models)

with open("ai-brain/src/train.py", "w") as f:
    f.write(code)
