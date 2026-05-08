"""
CAPE Model Training Script

Trains scikit-learn RandomForest and LightGBM models on the DataPulse
transaction dataset using CAPE's 19-feature vector.

Runtime features (device entropy, IP consistency, typing cadence) cannot be
computed from a static CSV — they are set to safe defaults here and will be
replaced by real values during inference via the FeatureStore.

Output: ml/models/cape/rf_model.pkl  and  ml/models/cape/gbt_model.pkl
Run:    python -m ml.training.cape.train_cape_models
"""
import os
import math
import pickle
import warnings
import time as _time
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import (
    roc_auc_score, classification_report, precision_recall_curve, auc
)

try:
    import lightgbm as lgb
    _HAS_LGB = True
except ImportError:
    from sklearn.ensemble import GradientBoostingClassifier
    _HAS_LGB = False

# ── paths ──────────────────────────────────────────────────────────────────
_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)
))))
DATA_DIR   = os.path.join(_ROOT, "data")
OUTPUT_DIR = os.path.join(_ROOT, "ml", "models", "cape")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# CAPE feature order — must match cape/layer3_parallel_scorers.FEATURE_ORDER
FEATURE_COLS = [
    "velocity_1min",
    "velocity_10min",
    "velocity_1hr",
    "velocity_24hr",
    "days_since_account_open",
    "merchant_txn_volume_per_hr",
    "merchant_chargeback_rate_30d",
    "merchant_fraud_signal_index",
    "graph_shared_device_flagged",
    "graph_distinct_accounts_1hr",
    "amount_zscore",
    "time_since_last_txn_norm",
    "country_ip_consistent",
    "device_fingerprint_entropy",
    "spend_cat_0",
    "spend_cat_1",
    "spend_cat_2",
    "spend_cat_3",
    "spend_cat_4",
]
assert len(FEATURE_COLS) == 19, "Feature count mismatch — update to match N_FEATURES"


# ── feature engineering ─────────────────────────────────────────────────────

def _velocity(df: pd.DataFrame, window_secs: int) -> pd.Series:
    """Count of same-user transactions within the preceding window_secs."""
    result = []
    grouped = df.groupby("cc_num")
    for _, grp in grouped:
        times = grp["unix_time"].values
        counts = []
        for i, t in enumerate(times):
            cutoff = t - window_secs
            cnt = int(np.sum(times[:i] >= cutoff))
            counts.append(cnt)
        result.append(pd.Series(counts, index=grp.index))
    return pd.concat(result).sort_index()


def _amount_zscore(df: pd.DataFrame) -> pd.Series:
    """Per-user expanding z-score of transaction amount (Welford-equivalent)."""
    result = []
    for _, grp in df.groupby("cc_num"):
        amts = grp["amt"].values.astype(float)
        zscores = []
        for i, a in enumerate(amts):
            if i < 2:
                zscores.append(0.0)
                continue
            hist = amts[:i]
            std = hist.std()
            zscores.append((a - hist.mean()) / std if std > 0 else 0.0)
        result.append(pd.Series(zscores, index=grp.index))
    return pd.concat(result).sort_index()


def _time_since_last(df: pd.DataFrame) -> pd.Series:
    """Seconds since user's previous transaction, normalised to [0, 1] over 24h."""
    result = []
    for _, grp in df.groupby("cc_num"):
        times = grp["unix_time"].values
        diffs = []
        for i in range(len(times)):
            if i == 0:
                diffs.append(86400.0)   # first txn: cap at 24h
            else:
                diffs.append(float(times[i] - times[i - 1]))
        result.append(pd.Series(diffs, index=grp.index))
    raw = pd.concat(result).sort_index()
    return (raw.clip(upper=86400.0) / 86400.0)


def _merchant_fraud_rate(df: pd.DataFrame) -> pd.Series:
    """Per-merchant historical fraud rate (proxy for chargeback rate and fraud index)."""
    rates = df.groupby("merchant")["is_fraud"].transform("mean")
    return rates


def _merchant_volume_per_hr(df: pd.DataFrame) -> pd.Series:
    """Per-merchant txn count normalised by total time span in hours."""
    def vol(grp):
        span_hrs = max((grp["unix_time"].max() - grp["unix_time"].min()) / 3600, 1.0)
        return len(grp) / span_hrs
    vol_map = df.groupby("merchant").apply(vol)
    return df["merchant"].map(vol_map)


def _graph_distinct_accounts_1hr(df: pd.DataFrame) -> pd.Series:
    """Distinct cc_nums seen at same merchant in preceding 3600s."""
    result = []
    grouped = df.groupby("merchant")
    for _, grp in grouped:
        times  = grp["unix_time"].values
        users  = grp["cc_num"].values
        counts = []
        for i in range(len(times)):
            cutoff = times[i] - 3600
            mask = times[:i] >= cutoff
            counts.append(int(len(set(users[:i][mask]))))
        result.append(pd.Series(counts, index=grp.index))
    return pd.concat(result).sort_index()


def _days_since_account_open(df: pd.DataFrame) -> pd.Series:
    """Approximate: days elapsed since user's first transaction in the dataset."""
    first_seen = df.groupby("cc_num")["unix_time"].transform("min")
    return ((df["unix_time"] - first_seen) / 86400).clip(lower=0)


def _user_top5_category_spend(df: pd.DataFrame) -> pd.DataFrame:
    """User's cumulative spend split into top-5 categories (zero-padded)."""
    categories = sorted(df["category"].unique())
    dummies = pd.get_dummies(df["category"]).reindex(columns=categories, fill_value=0)
    dummies = dummies.multiply(df["amt"].values, axis=0)

    # rolling cumulative spend per category per user
    result_cols = {}
    for cat in categories:
        col_vals = []
        for _, grp in df.groupby("cc_num"):
            idx = grp.index
            col_vals.append(pd.Series(
                dummies.loc[idx, cat].expanding().sum().values,
                index=idx
            ))
        result_cols[cat] = pd.concat(col_vals).sort_index()

    spend_df = pd.DataFrame(result_cols)

    # keep only the top-5 categories by total spend, zero-pad the rest
    top5 = spend_df.sum().nlargest(5).index.tolist()
    out = spend_df[top5].copy()
    while out.shape[1] < 5:
        out[f"spend_pad_{out.shape[1]}"] = 0.0
    out.columns = ["spend_cat_0", "spend_cat_1", "spend_cat_2", "spend_cat_3", "spend_cat_4"]
    return out


# ── main ────────────────────────────────────────────────────────────────────

def build_feature_matrix(transactions_df: pd.DataFrame) -> pd.DataFrame:
    df = transactions_df.sort_values(["cc_num", "unix_time"]).copy()
    df = df.reset_index(drop=True)

    print("  Computing velocities…")
    df["velocity_1min"]  = _velocity(df, 60)
    df["velocity_10min"] = _velocity(df, 600)
    df["velocity_1hr"]   = _velocity(df, 3600)
    df["velocity_24hr"]  = _velocity(df, 86400)

    print("  Computing amount z-scores…")
    df["amount_zscore"] = _amount_zscore(df)

    print("  Computing time-since-last…")
    df["time_since_last_txn_norm"] = _time_since_last(df)

    print("  Computing merchant signals…")
    df["merchant_chargeback_rate_30d"] = _merchant_fraud_rate(df)
    df["merchant_fraud_signal_index"]  = _merchant_fraud_rate(df)
    df["merchant_txn_volume_per_hr"]   = _merchant_volume_per_hr(df)

    print("  Computing graph features…")
    df["graph_distinct_accounts_1hr"] = _graph_distinct_accounts_1hr(df)
    df["graph_shared_device_flagged"] = 0.0  # not available from static CSV

    print("  Computing account-open days…")
    df["days_since_account_open"] = _days_since_account_open(df)

    # Runtime-only signals — set to mid-range defaults for training
    df["country_ip_consistent"]    = 1.0   # assume consistent
    df["device_fingerprint_entropy"] = 3.0  # mid-range entropy

    print("  Computing category spend…")
    spend = _user_top5_category_spend(df)
    df = df.join(spend)

    return df


def evaluate(y_true, y_prob, label: str):
    auc_roc = roc_auc_score(y_true, y_prob)
    prec, rec, _ = precision_recall_curve(y_true, y_prob)
    auc_pr = auc(rec, prec)
    print(f"\n{label}")
    print(f"  ROC-AUC   : {auc_roc:.4f}")
    print(f"  PR-AUC    : {auc_pr:.4f}")
    print(classification_report(y_true, (y_prob >= 0.5).astype(int),
                                 target_names=["legit", "fraud"], digits=4))
    return auc_roc


def main():
    print("=" * 65)
    print("CAPE Model Training")
    print(f"  Features : {len(FEATURE_COLS)}")
    print(f"  Output   : {OUTPUT_DIR}")
    print("=" * 65)

    # Load data
    print("\n[1/5] Loading data…")
    txn = pd.read_csv(os.path.join(DATA_DIR, "transactions.csv"))
    cust = pd.read_csv(os.path.join(DATA_DIR, "customer.csv"))
    txn = txn.merge(cust[["cc_num", "dob"]], on="cc_num", how="left")
    print(f"  Transactions : {len(txn):,}  |  Fraud rate: {txn['is_fraud'].mean()*100:.2f}%")

    # Feature engineering
    print("\n[2/5] Engineering CAPE features…")
    t0 = _time.time()
    df = build_feature_matrix(txn)
    print(f"  Done in {_time.time()-t0:.1f}s")

    X = df[FEATURE_COLS].fillna(0.0).astype(np.float32)
    y = df["is_fraud"].astype(int)
    print(f"  Feature matrix: {X.shape}")

    # Train / test split (stratified to preserve fraud rate)
    print("\n[3/5] Splitting data…")
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.20, random_state=42, stratify=y
    )
    print(f"  Train: {len(X_train):,}  |  Test: {len(X_test):,}")

    # ── Random Forest ────────────────────────────────────────────
    print("\n[4/5] Training Random Forest…")
    rf = RandomForestClassifier(
        n_estimators=100,
        max_depth=10,
        min_samples_leaf=5,
        class_weight="balanced",
        n_jobs=-1,
        random_state=42,
    )
    rf.fit(X_train, y_train)
    rf_path = os.path.join(OUTPUT_DIR, "rf_model.pkl")
    with open(rf_path, "wb") as f:
        pickle.dump(rf, f)
    print(f"  Saved → {rf_path}")
    evaluate(y_test, rf.predict_proba(X_test)[:, 1], "Random Forest (test)")

    # ── GBT (LightGBM or sklearn fallback) ──────────────────────
    print("\n[5/5] Training GBT…")
    gbt_path = os.path.join(OUTPUT_DIR, "gbt_model.pkl")

    if _HAS_LGB:
        train_data = lgb.Dataset(X_train, label=y_train)
        valid_data = lgb.Dataset(X_test,  label=y_test, reference=train_data)
        params = {
            "objective":    "binary",
            "metric":       "auc",
            "num_leaves":   31,
            "learning_rate": 0.05,
            "feature_fraction": 0.8,
            "bagging_fraction": 0.8,
            "bagging_freq":  5,
            "min_child_samples": 20,
            "scale_pos_weight": (y_train == 0).sum() / max((y_train == 1).sum(), 1),
            "verbose":      -1,
        }
        gbt = lgb.train(
            params, train_data,
            num_boost_round=200,
            valid_sets=[valid_data],
            callbacks=[lgb.early_stopping(20, verbose=False), lgb.log_evaluation(50)],
        )
        with open(gbt_path, "wb") as f:
            pickle.dump(gbt, f)
        gbt_prob = gbt.predict(X_test.values)
        print(f"  Saved LightGBM → {gbt_path}")
    else:
        from sklearn.ensemble import GradientBoostingClassifier
        gbt = GradientBoostingClassifier(
            n_estimators=100, max_depth=4, learning_rate=0.1,
            subsample=0.8, random_state=42,
        )
        gbt.fit(X_train, y_train)
        with open(gbt_path, "wb") as f:
            pickle.dump(gbt, f)
        gbt_prob = gbt.predict_proba(X_test)[:, 1]
        print(f"  Saved sklearn GBT → {gbt_path}")

    evaluate(y_test, gbt_prob, "GBT (test)")

    print("\n" + "=" * 65)
    print("Training complete.")
    print(f"  RF  model → {rf_path}")
    print(f"  GBT model → {gbt_path}")
    print("Load into CAPE via: from cape.model_loader import load_pipeline")
    print("=" * 65)


if __name__ == "__main__":
    main()
