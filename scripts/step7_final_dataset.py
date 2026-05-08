"""
Step 7 — Final training dataset assembly with all 19 CAPE features
"""
import pandas as pd
import numpy as np
import os
from sklearn.model_selection import train_test_split

DATA_DIR = r"E:\Project\My project\DataPulse - Copy\data"

# CAPE FEATURE_ORDER — DO NOT CHANGE
FEATURE_ORDER = [
    "velocity_1min", "velocity_10min", "velocity_1hr", "velocity_24hr",
    "days_since_account_open", "merchant_txn_volume_per_hr",
    "merchant_chargeback_rate_30d", "merchant_fraud_signal_index",
    "graph_shared_device_flagged", "graph_distinct_accounts_1hr",
    "amount_zscore", "time_since_last_txn_norm", "country_ip_consistent",
    "device_fingerprint_entropy", "spend_cat_0", "spend_cat_1",
    "spend_cat_2", "spend_cat_3", "spend_cat_4"
]

print("=== STEP 7: Final Training Dataset Assembly ===\n")

# 1. Load transactions_features.csv
print("Loading transactions_features.csv...")
df = pd.read_csv(os.path.join(DATA_DIR, "transactions_features.csv"), low_memory=False)
print(f"  Shape: {df.shape}")

# Ensure numeric types
df["amt"] = pd.to_numeric(df["amt"], errors="coerce").fillna(0.0)
df["unix_time"] = pd.to_numeric(df["unix_time"], errors="coerce").fillna(0.0)
df["merch_lat"] = pd.to_numeric(df["merch_lat"], errors="coerce").fillna(0.0)
df["merch_long"] = pd.to_numeric(df["merch_long"], errors="coerce").fillna(0.0)
df["is_fraud"] = pd.to_numeric(df["is_fraud"], errors="coerce").fillna(0).astype(int)

# 2. Load graph features
print("Loading graph_features.csv...")
gf = pd.read_csv(os.path.join(DATA_DIR, "graph_features.csv"), low_memory=False)
print(f"  Graph features shape: {gf.shape}")

# 3. Merge graph features
# Match by closest step: step = unix_time // 3600 for transactions
# Use global merge: for each transaction, find graph_distinct_accounts_1hr
# from graph_features with closest step, isFraud==0 (no data leakage)
print("Merging graph features (by closest step, isFraud==0 rows only)...")
gf_legit = gf[gf["isFraud"] == 0][["step", "graph_distinct_accounts_1hr"]].copy()

# Get median graph_distinct_accounts_1hr per step (avoiding leakage)
step_graph = gf_legit.groupby("step")["graph_distinct_accounts_1hr"].median().reset_index()
step_graph.columns = ["step", "graph_distinct_accounts_1hr"]

# Compute step for each transaction
df["_step"] = (df["unix_time"] // 3600).astype(int)

# Sort step_graph steps for nearest-neighbor lookup
step_arr = step_graph["step"].values
gda_arr = step_graph["graph_distinct_accounts_1hr"].values

def nearest_step_lookup(s):
    """Find graph_distinct_accounts_1hr for nearest step."""
    idx = np.searchsorted(step_arr, s, side="left")
    if idx == 0:
        return int(gda_arr[0])
    if idx >= len(step_arr):
        return int(gda_arr[-1])
    # Compare left and right neighbor
    lo = step_arr[idx - 1]
    hi = step_arr[idx]
    if abs(s - lo) <= abs(s - hi):
        return int(gda_arr[idx - 1])
    else:
        return int(gda_arr[idx])

print("  Computing graph_distinct_accounts_1hr from step lookup...")
df["graph_distinct_accounts_1hr"] = df["_step"].apply(nearest_step_lookup)
df.drop(columns=["_step"], inplace=True)
print(f"  graph_distinct_accounts_1hr stats: mean={df['graph_distinct_accounts_1hr'].mean():.4f}, "
      f"max={df['graph_distinct_accounts_1hr'].max()}")

# 4. Compute all 19 CAPE features
print("\nComputing 19 CAPE features...")

# Sort by cc_num + unix_time for rolling windows
print("  Sorting by cc_num + unix_time...")
df = df.sort_values(["cc_num", "unix_time"]).reset_index(drop=True)

# --- Velocity features (count same cc_num in preceding N seconds) ---
print("  Computing velocity features...")
# Use groupby + cumcount approach:
# velocity_1min: transactions by same cc_num in preceding 60 seconds

def compute_velocity(df, window_seconds, col_name):
    """Count preceding transactions for same cc_num within window_seconds."""
    result = np.zeros(len(df), dtype=np.int32)
    # Group by cc_num
    for cc, group_idx in df.groupby("cc_num").groups.items():
        idx_arr = group_idx.values
        times = df.loc[idx_arr, "unix_time"].values
        for i, (abs_i, t) in enumerate(zip(idx_arr, times)):
            # Binary search for window start
            lo = np.searchsorted(times[:i], t - window_seconds, side="left")
            result[abs_i] = i - lo
    return result

# More efficient: vectorized approach per group
def compute_velocity_vectorized(df, window_seconds):
    """Vectorized velocity computation."""
    result = np.zeros(len(df), dtype=np.float32)
    for cc, grp in df.groupby("cc_num"):
        idx = grp.index.values
        times = grp["unix_time"].values
        n = len(times)
        for i in range(n):
            lo = np.searchsorted(times, times[i] - window_seconds, side="left")
            result[idx[i]] = i - lo  # exclude self (preceding only)
    return result

print("    velocity_1min (60s)...")
df["velocity_1min"] = compute_velocity_vectorized(df, 60)
print("    velocity_10min (600s)...")
df["velocity_10min"] = compute_velocity_vectorized(df, 600)
print("    velocity_1hr (3600s)...")
df["velocity_1hr"] = compute_velocity_vectorized(df, 3600)
print("    velocity_24hr (86400s)...")
df["velocity_24hr"] = compute_velocity_vectorized(df, 86400)

# --- days_since_account_open ---
print("  Computing days_since_account_open...")
cc_min_time = df.groupby("cc_num")["unix_time"].transform("min")
df["days_since_account_open"] = (df["unix_time"] - cc_min_time) / 86400.0

# --- merchant_txn_volume_per_hr ---
print("  Computing merchant_txn_volume_per_hr...")
merchant_stats = df.groupby("merchant")["unix_time"].agg(["count", "min", "max"])
merchant_stats["hours_span"] = (merchant_stats["max"] - merchant_stats["min"]) / 3600.0
merchant_stats["hours_span"] = merchant_stats["hours_span"].clip(lower=1.0)
merchant_stats["merchant_txn_volume_per_hr"] = merchant_stats["count"] / merchant_stats["hours_span"]
df["merchant_txn_volume_per_hr"] = df["merchant"].map(merchant_stats["merchant_txn_volume_per_hr"]).fillna(0.0)

# --- merchant_chargeback_rate_30d (proxy: rolling fraud rate per merchant) ---
print("  Computing merchant_chargeback_rate_30d...")
merchant_fraud_rate = df.groupby("merchant")["is_fraud"].mean()
df["merchant_chargeback_rate_30d"] = df["merchant"].map(merchant_fraud_rate).fillna(0.0)

# --- merchant_fraud_signal_index (same as chargeback_rate_30d as proxy) ---
df["merchant_fraud_signal_index"] = df["merchant_chargeback_rate_30d"]

# --- graph_shared_device_flagged (0 — no device fingerprint data) ---
df["graph_shared_device_flagged"] = 0

# graph_distinct_accounts_1hr already computed above

# --- amount_zscore (expanding per-user mean/std) ---
print("  Computing amount_zscore (expanding window per cc_num)...")
# Efficient: use expanding() after sorting by cc_num, unix_time
amount_zscore = np.zeros(len(df), dtype=np.float32)
for cc, grp in df.groupby("cc_num"):
    idx = grp.index.values
    amounts = grp["amt"].values
    n = len(amounts)
    for i in range(n):
        if i == 0:
            amount_zscore[idx[i]] = 0.0
        else:
            prior = amounts[:i]
            mu = prior.mean()
            std = prior.std()
            if std > 0:
                amount_zscore[idx[i]] = (amounts[i] - mu) / std
            else:
                amount_zscore[idx[i]] = 0.0
df["amount_zscore"] = amount_zscore

# --- time_since_last_txn_norm ---
print("  Computing time_since_last_txn_norm...")
tslt = np.ones(len(df), dtype=np.float32)  # default 1.0
for cc, grp in df.groupby("cc_num"):
    idx = grp.index.values
    times = grp["unix_time"].values
    n = len(times)
    for i in range(1, n):
        delta = (times[i] - times[i-1]) / 86400.0
        tslt[idx[i]] = min(delta, 1.0)
df["time_since_last_txn_norm"] = tslt

# --- country_ip_consistent (default 1) ---
df["country_ip_consistent"] = 1

# --- device_fingerprint_entropy (default 3.0) ---
df["device_fingerprint_entropy"] = 3.0

# --- spend_cat_0..4: user's top-5 category cumulative spend ---
print("  Computing spend_cat_0..4...")
# Get top 5 categories by total spend
top5_cats = df.groupby("category")["amt"].sum().nlargest(5).index.tolist()
print(f"    Top 5 categories: {top5_cats}")

for i, cat in enumerate(top5_cats):
    col_name = f"spend_cat_{i}"
    # Cumulative spend per user in this category
    cat_mask = (df["category"] == cat).astype(float)
    cat_spend = df["amt"] * cat_mask
    df[col_name] = df.groupby("cc_num")[cat_spend.name].transform(
        lambda x: x.cumsum().shift(1, fill_value=0)
    ) if False else 0  # placeholder

# Efficient approach: compute per cc_num per category
for i, cat in enumerate(top5_cats):
    col_name = f"spend_cat_{i}"
    df[col_name] = 0.0
    cat_df = df[df["category"] == cat].copy()
    for cc, grp in df.groupby("cc_num"):
        cat_grp = grp[grp["category"] == cat]
        if len(cat_grp) == 0:
            continue
        cumspend = cat_grp["amt"].cumsum().shift(1, fill_value=0)
        df.loc[cat_grp.index, col_name] = cumspend.values

# Fill remaining spend_cat columns if fewer than 5 categories
for i in range(len(top5_cats), 5):
    col_name = f"spend_cat_{i}"
    if col_name not in df.columns:
        df[col_name] = 0.0

# 5. Ensure EXACTLY the 19 CAPE features + is_fraud
print("\nFinalizing feature columns...")
for feat in FEATURE_ORDER:
    if feat not in df.columns:
        print(f"  WARNING: Missing feature '{feat}', filling with 0")
        df[feat] = 0.0
    else:
        df[feat] = pd.to_numeric(df[feat], errors="coerce").fillna(0.0)

final_df = df[FEATURE_ORDER + ["is_fraud"]].copy()
print(f"  Final shape: {final_df.shape}")
print(f"  Null counts per feature:")
null_counts = final_df.isnull().sum()
print(null_counts[null_counts > 0] if null_counts.any() else "    None")

# 6. Stratified 70/15/15 split
print("\nPerforming stratified 70/15/15 split...")
train_df, temp_df = train_test_split(
    final_df, test_size=0.30, random_state=42, stratify=final_df["is_fraud"]
)
val_df, test_df_out = train_test_split(
    temp_df, test_size=0.50, random_state=42, stratify=temp_df["is_fraud"]
)

# 7. Save
train_path = os.path.join(DATA_DIR, "train.csv")
val_path = os.path.join(DATA_DIR, "val.csv")
test_path = os.path.join(DATA_DIR, "test.csv")

train_df.to_csv(train_path, index=False)
val_df.to_csv(val_path, index=False)
test_df_out.to_csv(test_path, index=False)
print(f"Saved: {train_path}, {val_path}, {test_path}")

# 8. Print shapes and fraud rates
print(f"\n{'='*50}")
print(f"STEP 7 COMPLETE")
print(f"  Train: {train_df.shape}, fraud rate={train_df['is_fraud'].mean():.4f}")
print(f"  Val:   {val_df.shape}, fraud rate={val_df['is_fraud'].mean():.4f}")
print(f"  Test:  {test_df_out.shape}, fraud rate={test_df_out['is_fraud'].mean():.4f}")
print(f"  Features: {FEATURE_ORDER}")
print(f"{'='*50}")
