"""
Train a sklearn RandomForestClassifier with the exact 11-feature vector
used by the Spark streaming job. Replaces PySpark for cloud deployments.

Features (in order):
    cc_num_enc, category_enc, merchant_enc,
    distance, amt, age, hour, dayofweek, is_weekend,
    tx_count_1h, tx_amt_1h

Output:
    ml/models/streaming/sklearn_rf.pkl
    ml/models/streaming/label_encoders.pkl

Usage (from project root):
    python pipeline/train_streaming_model.py
"""

import math
import os
import pickle
from collections import deque
from datetime import datetime, timezone

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report, roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder

_ROOT   = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(_ROOT, "ml", "models", "streaming")
os.makedirs(OUT_DIR, exist_ok=True)

FEATURE_COLS = [
    "cc_num_enc", "category_enc", "merchant_enc",
    "distance", "amt", "age",
    "hour", "dayofweek", "is_weekend",
    "tx_count_1h", "tx_amt_1h",
]


def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0
    rlat1, rlon1, rlat2, rlon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    dlat, dlon = rlat2 - rlat1, rlon2 - rlon1
    a = math.sin(dlat / 2) ** 2 + math.cos(rlat1) * math.cos(rlat2) * math.sin(dlon / 2) ** 2
    return R * 2 * math.asin(math.sqrt(max(0.0, a)))


def spark_dayofweek(unix_ts: float) -> int:
    """Spark dayofweek convention: Sun=1, Mon=2, ..., Sat=7."""
    dt = datetime.fromtimestamp(unix_ts, tz=timezone.utc)
    return (dt.isoweekday() % 7) + 1


def compute_velocity(df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute tx_count_1h and tx_amt_1h matching Spark rangeBetween(-3600, 0),
    which includes the current row. O(n) with deque per card.
    """
    df = df.sort_values(["cc_num", "unix_time"]).reset_index(drop=True)
    tx_count = np.zeros(len(df), dtype=np.int32)
    tx_amt   = np.zeros(len(df), dtype=np.float64)

    for _, grp in df.groupby("cc_num", sort=False):
        idxs  = grp.index.values
        times = grp["unix_time"].values.astype(np.int64)
        amts  = grp["amt"].values.astype(np.float64)
        window: deque = deque()
        win_amt = 0.0
        for i in range(len(idxs)):
            window.append(i)
            win_amt += amts[i]
            cutoff = times[i] - 3600
            while window and times[window[0]] < cutoff:
                win_amt -= amts[window.popleft()]
            tx_count[idxs[i]] = len(window)
            tx_amt[idxs[i]]   = win_amt

    df["tx_count_1h"] = tx_count
    df["tx_amt_1h"]   = tx_amt
    return df


def main() -> None:
    data_dir = os.path.join(_ROOT, "data")

    print("Loading data...")
    txn = pd.read_csv(os.path.join(data_dir, "transactions.csv"))
    cust = pd.read_csv(os.path.join(data_dir, "customer.csv"))

    # Merge on cc_num to get customer lat/long and dob
    df = txn.merge(
        cust[["cc_num", "lat", "long", "dob"]],
        on="cc_num",
        how="left",
    )

    print(f"  {len(df)} transactions, {df['is_fraud'].sum():.0f} fraud ({df['is_fraud'].mean()*100:.2f}%)")

    # ── Distance ───────────────────────────────────────────────────────────────
    print("Computing distance...")
    df["lat"]  = df["lat"].fillna(0.0)
    df["long"] = df["long"].fillna(0.0)
    df["distance"] = df.apply(
        lambda r: haversine(r["lat"], r["long"], r["merch_lat"], r["merch_long"]),
        axis=1,
    )

    # ── Age ────────────────────────────────────────────────────────────────────
    print("Computing age...")
    dob_dt = pd.to_datetime(df["dob"], errors="coerce")
    txn_dt = pd.to_datetime(df["trans_date"], errors="coerce")
    # trans_date has timezone offset (+05:30); strip it so both Series are tz-naive
    if txn_dt.dt.tz is not None:
        txn_dt = txn_dt.dt.tz_convert(None)
    if dob_dt.dt.tz is not None:
        dob_dt = dob_dt.dt.tz_convert(None)
    age_days = (txn_dt - dob_dt).dt.days
    df["age"] = (age_days / 365.2425).fillna(30).clip(18, 100).astype(int)

    # ── Temporal features ──────────────────────────────────────────────────────
    print("Computing temporal features...")
    df["hour"]      = df["unix_time"].apply(lambda t: datetime.fromtimestamp(t, tz=timezone.utc).hour)
    df["dayofweek"] = df["unix_time"].apply(spark_dayofweek)
    df["is_weekend"] = df["dayofweek"].apply(lambda d: 1 if d in (1, 7) else 0)

    # ── Velocity features ──────────────────────────────────────────────────────
    print("Computing velocity features (1-hour rolling window)...")
    df = compute_velocity(df)

    # ── Label encoding ─────────────────────────────────────────────────────────
    print("Encoding categorical features...")
    encoders: dict[str, LabelEncoder] = {}
    for col in ("cc_num", "category", "merchant"):
        le = LabelEncoder()
        df[f"{col}_enc"] = le.fit_transform(df[col].astype(str))
        encoders[col] = le

    # ── Train / test split ─────────────────────────────────────────────────────
    X = df[FEATURE_COLS].values.astype(np.float64)
    y = df["is_fraud"].values.astype(int)

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    print(f"\nTraining: {len(X_train)} rows  |  Test: {len(X_test)} rows")

    # ── Model training ─────────────────────────────────────────────────────────
    print("Training RandomForestClassifier (n_estimators=100, class_weight=balanced)...")
    rf = RandomForestClassifier(
        n_estimators=100,
        max_depth=15,
        class_weight="balanced",
        n_jobs=-1,
        random_state=42,
    )
    rf.fit(X_train, y_train)

    # ── Evaluation ─────────────────────────────────────────────────────────────
    y_prob = rf.predict_proba(X_test)[:, 1]
    y_pred = (y_prob >= 0.40).astype(int)

    print("\n── Evaluation (threshold=0.40) ──────────────────────────────")
    print(classification_report(y_test, y_pred, target_names=["Normal", "Fraud"]))
    auc = roc_auc_score(y_test, y_prob)
    print(f"ROC-AUC: {auc:.4f}")

    # ── Save artifacts ─────────────────────────────────────────────────────────
    model_path    = os.path.join(OUT_DIR, "sklearn_rf.pkl")
    encoders_path = os.path.join(OUT_DIR, "label_encoders.pkl")

    with open(model_path, "wb") as f:
        pickle.dump(rf, f)
    with open(encoders_path, "wb") as f:
        pickle.dump(encoders, f)

    print(f"\nSaved model    → {model_path}")
    print(f"Saved encoders → {encoders_path}")
    print("\nFeature importances:")
    for feat, imp in sorted(zip(FEATURE_COLS, rf.feature_importances_), key=lambda x: -x[1]):
        print(f"  {feat:<20} {imp:.4f}")


if __name__ == "__main__":
    main()
