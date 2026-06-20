import sys, os
sys.path.insert(0, os.path.dirname(__file__))
import numpy as np
import lightgbm as lgb
from sklearn.ensemble import RandomForestRegressor, HistGradientBoostingRegressor
from sklearn.metrics import r2_score, mean_absolute_error, mean_squared_error
from sklearn.model_selection import train_test_split
from sklearn.feature_extraction import DictVectorizer
from astram_data import read_csv_rows, fit_aggregate_stats
from train import load_supervised_rows, build_v2_target_maps, build_dataset

csv_path = os.path.join(os.path.dirname(__file__), "..", "dataset", "Astram event data_anonymized - Astram event data_anonymizedb40ac87 (2).csv")
rows = read_csv_rows(csv_path)
rows = load_supervised_rows(rows)

# time split
split_idx = int(len(rows) * 0.8)
train_rows = rows[:split_idx]
test_rows = rows[split_idx:]

stats = fit_aggregate_stats(train_rows)
v2_maps = build_v2_target_maps(train_rows, stats.global_duration_median, stats.duration_by_cause)

train_x, train_y_duration, _ = build_dataset(train_rows, stats, v2_maps, upper_winsor_limit=480)
test_x, test_y_duration, _ = build_dataset(test_rows, stats, v2_maps, upper_winsor_limit=480)

vec = DictVectorizer(sparse=False)
X_tr = vec.fit_transform(train_x)
X_te = vec.transform(test_x)

y_tr_log = np.log1p(train_y_duration)

def evaluate(model, name):
    model.fit(X_tr, y_tr_log)
    preds = np.expm1(model.predict(X_te))
    preds = np.clip(preds, 0, 480)
    mae = mean_absolute_error(test_y_duration, preds)
    rmse = np.sqrt(mean_squared_error(test_y_duration, preds))
    r2 = r2_score(test_y_duration, preds)
    print(f"{name:20s}: MAE={mae:.1f}, RMSE={rmse:.1f}, R2={r2:.4f}")

import warnings
warnings.filterwarnings('ignore')

evaluate(lgb.LGBMRegressor(n_estimators=100, random_state=42, verbose=-1), "LGBM Default")
evaluate(RandomForestRegressor(n_estimators=100, random_state=42), "RandomForest")
evaluate(HistGradientBoostingRegressor(random_state=42), "HistGradientBoosting")
