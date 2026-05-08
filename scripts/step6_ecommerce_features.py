"""
Step 6 — Web channel features from E-commerce fraud dataset
"""
import pandas as pd
import numpy as np
import os
from bisect import bisect_left, bisect_right

DATA_DIR = r"E:\Project\My project\DataPulse - Copy\data"
ECOMM_PATH = os.path.join(DATA_DIR, "fraud-ecommerce", "Fraud_Data.csv")

print("=== STEP 6: E-commerce Web Channel Features ===\n")

# 1. Load
print("Loading Fraud_Data.csv...")
df = pd.read_csv(ECOMM_PATH, low_memory=False)
print(f"  Shape: {df.shape}")
print(f"  Columns: {list(df.columns)}")

# 2. Parse datetime columns
print("\nParsing datetime columns...")
df["signup_time"] = pd.to_datetime(df["signup_time"], errors="coerce")
df["purchase_time"] = pd.to_datetime(df["purchase_time"], errors="coerce")
print(f"  signup_time nulls: {df['signup_time'].isna().sum()}")
print(f"  purchase_time nulls: {df['purchase_time'].isna().sum()}")

# 3a. account_age_at_purchase_seconds
df["account_age_at_purchase_seconds"] = (
    df["purchase_time"] - df["signup_time"]
).dt.total_seconds()

# 3b. is_new_account
df["is_new_account"] = (df["account_age_at_purchase_seconds"] < 86400).astype(int)
print(f"\n  is_new_account=1 count: {df['is_new_account'].sum():,}")

# 3c. ip_velocity_1hr — for each row, count distinct purchases from same ip_address
#     within ±1800 seconds of purchase_time (1-hour centred window)
print("Computing ip_velocity_1hr (sorted approach)...")
df["purchase_ts"] = df["purchase_time"].astype(np.int64) // 10**9  # seconds since epoch

# Sort by ip_address then purchase_ts for binary search
df_sorted = df[["ip_address", "purchase_ts"]].copy()
df_sorted = df_sorted.sort_values(["ip_address", "purchase_ts"])

# Group by ip_address, get sorted timestamps
ip_groups = df_sorted.groupby("ip_address")["purchase_ts"].apply(list).to_dict()

# For each row, binary search in ip's sorted timestamps
def compute_ip_velocity(row):
    ip = row["ip_address"]
    ts = row["purchase_ts"]
    if ip not in ip_groups:
        return 1  # just itself
    ts_list = ip_groups[ip]
    lo = bisect_left(ts_list, ts - 1800)
    hi = bisect_right(ts_list, ts + 1800)
    return hi - lo  # includes self

print("  Applying ip_velocity function (may take a moment)...")
df["ip_velocity_1hr"] = df.apply(compute_ip_velocity, axis=1)
print(f"  Max ip_velocity_1hr: {df['ip_velocity_1hr'].max()}")

# 3d. device_seen_before
device_counts = df["device_id"].value_counts()
df["device_seen_before"] = df["device_id"].map(lambda x: 1 if device_counts.get(x, 0) > 1 else 0)
print(f"\n  device_seen_before=1 count: {df['device_seen_before'].sum():,}")

# 4. Save
out_path = os.path.join(DATA_DIR, "ecommerce_features.csv")
df.to_csv(out_path, index=False)
print(f"\nSaved to {out_path}")

# 5. Print fraud rates
fraud_new_acct = df[df["is_new_account"] == 1]["class"].mean() if "class" in df.columns else df[df["is_new_account"] == 1]["Class"].mean() if "Class" in df.columns else None
# Check column name
fraud_col = "class" if "class" in df.columns else "Class"
if fraud_col not in df.columns:
    # try lower
    cols_lower = {c.lower(): c for c in df.columns}
    if "class" in cols_lower:
        fraud_col = cols_lower["class"]
    else:
        fraud_col = None

if fraud_col:
    fraud_new_acct = df[df["is_new_account"] == 1][fraud_col].mean()
    fraud_high_vel = df[df["ip_velocity_1hr"] > 3][fraud_col].mean() if (df["ip_velocity_1hr"] > 3).any() else 0
    overall_fraud = df[fraud_col].mean()
    print(f"\n  Overall fraud rate: {overall_fraud:.4f}")
    print(f"  Fraud rate (is_new_account==1): {fraud_new_acct:.4f} ({(df['is_new_account']==1).sum():,} rows)")
    print(f"  Fraud rate (ip_velocity_1hr > 3): {fraud_high_vel:.4f} ({(df['ip_velocity_1hr']>3).sum():,} rows)")

print(f"\n{'='*50}")
print(f"STEP 6 COMPLETE")
print(f"  Total rows: {len(df):,}")
print(f"  New features: account_age_at_purchase_seconds, is_new_account, ip_velocity_1hr, device_seen_before")
print(f"{'='*50}")
