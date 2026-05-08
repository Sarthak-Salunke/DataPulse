"""
Step 8 — Retrain LightGBM and RandomForest models
"""
import pandas as pd
import numpy as np
import json
import os
import joblib

import lightgbm as lgb
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    roc_auc_score, f1_score, precision_score, recall_score, confusion_matrix
)

DATA_DIR = r"E:\Project\My project\DataPulse - Copy\data"
ML_MODELS_DIR = r"E:\Project\My project\DataPulse - Copy\ml\models"
CAPE_MODELS_DIR = r"E:\Project\My project\DataPulse - Copy\ml\models\cape"

# Ensure directories exist
os.makedirs(ML_MODELS_DIR, exist_ok=True)
os.makedirs(CAPE_MODELS_DIR, exist_ok=True)

FEATURE_ORDER = [
    "velocity_1min", "velocity_10min", "velocity_1hr", "velocity_24hr",
    "days_since_account_open", "merchant_txn_volume_per_hr",
    "merchant_chargeback_rate_30d", "merchant_fraud_signal_index",
    "graph_shared_device_flagged", "graph_distinct_accounts_1hr",
    "amount_zscore", "time_since_last_txn_norm", "country_ip_consistent",
    "device_fingerprint_entropy", "spend_cat_0", "spend_cat_1",
    "spend_cat_2", "spend_cat_3", "spend_cat_4"
]

print("=== STEP 8: Model Training ===\n")

# 1. Load train and val
print("Loading train.csv and val.csv...")
train_df = pd.read_csv(os.path.join(DATA_DIR, "train.csv"))
val_df = pd.read_csv(os.path.join(DATA_DIR, "val.csv"))
print(f"  Train: {train_df.shape}, Val: {val_df.shape}")

X_train = train_df[FEATURE_ORDER].values
y_train = train_df["is_fraud"].values
X_val = val_df[FEATURE_ORDER].values
y_val = val_df["is_fraud"].values

print(f"  Train fraud rate: {y_train.mean():.4f}")
print(f"  Val fraud rate:   {y_val.mean():.4f}")

# 2. Load class weights
print("\nLoading class_weights.json...")
with open(os.path.join(DATA_DIR, "class_weights.json")) as f:
    weights_data = json.load(f)
scale_pos_weight = weights_data["scale_pos_weight"]
print(f"  scale_pos_weight: {scale_pos_weight:.4f}")

# 3. Train LightGBM
print("\n--- Training LightGBM ---")
params = {
    "objective": "binary",
    "metric": "auc",
    "num_leaves": 31,
    "learning_rate": 0.05,
    "feature_fraction": 0.8,
    "bagging_fraction": 0.8,
    "bagging_freq": 5,
    "min_child_samples": 20,
    "scale_pos_weight": scale_pos_weight,
    "verbose": -1,
}

dtrain = lgb.Dataset(X_train, label=y_train, feature_name=FEATURE_ORDER)
dval = lgb.Dataset(X_val, label=y_val, feature_name=FEATURE_ORDER, reference=dtrain)

callbacks = [
    lgb.early_stopping(stopping_rounds=20, verbose=True),
    lgb.log_evaluation(period=25),
]

lgbm_model = lgb.train(
    params,
    dtrain,
    num_boost_round=200,
    valid_sets=[dval],
    valid_names=["val"],
    callbacks=callbacks,
)

print(f"  Best iteration: {lgbm_model.best_iteration}")
print(f"  Best val AUC: {lgbm_model.best_score['val']['auc']:.4f}")

# 4. Train RandomForest
print("\n--- Training RandomForestClassifier ---")
rf_model = RandomForestClassifier(
    n_estimators=200,
    max_depth=10,
    class_weight="balanced",
    n_jobs=-1,
    random_state=42
)
rf_model.fit(X_train, y_train)
print("  RandomForest training complete.")

# 5. Evaluate both models on val
print("\n--- Evaluation on Val Set ---")

def evaluate_model(name, y_true, y_pred_proba, threshold=0.5):
    y_pred = (y_pred_proba >= threshold).astype(int)
    auc = roc_auc_score(y_true, y_pred_proba)
    f1 = f1_score(y_true, y_pred, zero_division=0)
    prec = precision_score(y_true, y_pred, zero_division=0)
    rec = recall_score(y_true, y_pred, zero_division=0)
    cm = confusion_matrix(y_true, y_pred)
    print(f"\n  [{name}]")
    print(f"    AUC-ROC:      {auc:.4f}")
    print(f"    F1 (fraud):   {f1:.4f}")
    print(f"    Precision:    {prec:.4f}")
    print(f"    Recall:       {rec:.4f}")
    print(f"    Confusion Matrix:")
    print(f"      TN={cm[0,0]:,}  FP={cm[0,1]:,}")
    print(f"      FN={cm[1,0]:,}  TP={cm[1,1]:,}")
    return auc, f1, prec, rec

lgbm_proba = lgbm_model.predict(X_val)
rf_proba = rf_model.predict_proba(X_val)[:, 1]

lgbm_auc, lgbm_f1, lgbm_prec, lgbm_rec = evaluate_model("LightGBM", y_val, lgbm_proba)
rf_auc, rf_f1, rf_prec, rf_rec = evaluate_model("RandomForest", y_val, rf_proba)

# 6. Save models
print("\n--- Saving Models ---")

# Primary location
lgbm_path = os.path.join(ML_MODELS_DIR, "lgbm_model.pkl")
rf_path = os.path.join(ML_MODELS_DIR, "rf_model.pkl")
joblib.dump(lgbm_model, lgbm_path)
joblib.dump(rf_model, rf_path)
print(f"  Saved: {lgbm_path}")
print(f"  Saved: {rf_path}")

# CAPE location
lgbm_cape_path = os.path.join(CAPE_MODELS_DIR, "lgbm_model.pkl")
rf_cape_path = os.path.join(CAPE_MODELS_DIR, "rf_model.pkl")
joblib.dump(lgbm_model, lgbm_cape_path)
joblib.dump(rf_model, rf_cape_path)
print(f"  Saved: {lgbm_cape_path}")
print(f"  Saved: {rf_cape_path}")

print(f"\n{'='*50}")
print(f"STEP 8 COMPLETE")
print(f"  LightGBM  — AUC: {lgbm_auc:.4f}, F1: {lgbm_f1:.4f}, Prec: {lgbm_prec:.4f}, Recall: {lgbm_rec:.4f}")
print(f"  RandomForest — AUC: {rf_auc:.4f}, F1: {rf_f1:.4f}, Prec: {rf_prec:.4f}, Recall: {rf_rec:.4f}")
print(f"{'='*50}")
