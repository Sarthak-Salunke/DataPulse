"""
Step 3 — Feature engineering from IEEE-CIS dataset
"""
import pandas as pd
import numpy as np
import os

DATA_DIR = r"E:\Project\My project\DataPulse - Copy\data"
IEEE_DIR = os.path.join(DATA_DIR, "ieee-fraud-detection")

print("=== STEP 3: IEEE-CIS Feature Engineering ===\n")

# 1. Load IEEE transaction and identity
print("Loading IEEE train_transaction.csv (relevant cols only)...")
txn_ieee = pd.read_csv(
    os.path.join(IEEE_DIR, "train_transaction.csv"),
    usecols=["TransactionID", "TransactionAmt", "ProductCD"],
    low_memory=False
)
print(f"  IEEE transaction shape: {txn_ieee.shape}")

print("Loading IEEE train_identity.csv...")
# Load identity - check which cols are present
identity_all = pd.read_csv(
    os.path.join(IEEE_DIR, "train_identity.csv"),
    low_memory=False
)
print(f"  IEEE identity all cols: {list(identity_all.columns)}")

# Determine needed cols - id_30 (OS), id_31 (browser), DeviceType, P_emaildomain, R_emaildomain
needed_id_cols = ["TransactionID", "id_30", "id_31", "DeviceType"]
for col in ["P_emaildomain", "R_emaildomain"]:
    if col in identity_all.columns:
        needed_id_cols.append(col)

identity_ieee = identity_all[needed_id_cols].copy()
print(f"  IEEE identity selected shape: {identity_ieee.shape}")
print(f"  Identity cols used: {needed_id_cols}")

# Join on TransactionID
ieee_merged = txn_ieee.merge(identity_ieee, on="TransactionID", how="left")
print(f"  IEEE joined shape: {ieee_merged.shape}")

# 2. Load transactions_merged
print("\nLoading transactions_merged.csv...")
df = pd.read_csv(os.path.join(DATA_DIR, "transactions_merged.csv"), low_memory=False)
print(f"  Shape: {df.shape}")

# 3. Engineer new columns directly on df
print("\nEngineering amt_log and amt_rounded_flag...")
df["amt_log"] = np.log1p(df["amt"].fillna(0).astype(float))
df["amt_rounded_flag"] = (df["amt"].fillna(0).astype(float) % 1 == 0).astype(int)

# 4. Sample device_type and browser from IEEE distributions
print("Sampling device_type from IEEE DeviceType distribution...")

# Get IEEE device type distribution
device_counts = ieee_merged["DeviceType"].value_counts(dropna=True)
device_map = {"desktop": 0, "mobile": 0, "tablet": 0, "unknown": 0}

# Map IEEE device types to our categories
for dev, cnt in device_counts.items():
    dev_lower = str(dev).lower()
    if "desktop" in dev_lower or "pc" in dev_lower or "windows" in dev_lower or "mac" in dev_lower:
        device_map["desktop"] += cnt
    elif "mobile" in dev_lower or "phone" in dev_lower or "android" in dev_lower or "ios" in dev_lower:
        device_map["mobile"] += cnt
    elif "tablet" in dev_lower or "ipad" in dev_lower:
        device_map["tablet"] += cnt
    else:
        device_map["unknown"] += cnt

total_devices = sum(device_map.values())
if total_devices == 0:
    # If no clear mapping, use raw values
    raw_devices = ieee_merged["DeviceType"].dropna().str.lower()
    # mobile/desktop are common in IEEE
    device_map = {"desktop": 0, "mobile": 0, "tablet": 0, "unknown": 0}
    for d in raw_devices:
        d = str(d)
        if d in device_map:
            device_map[d] += 1
        else:
            device_map["unknown"] += 1
    total_devices = sum(device_map.values())

if total_devices == 0:
    device_probs = [0.6, 0.3, 0.05, 0.05]
    device_labels = ["desktop", "mobile", "tablet", "unknown"]
else:
    device_labels = list(device_map.keys())
    device_probs = [v / total_devices for v in device_map.values()]

print(f"  Device distribution: {dict(zip(device_labels, [f'{p:.3f}' for p in device_probs]))}")

np.random.seed(42)
df["device_type"] = np.random.choice(device_labels, size=len(df), p=device_probs)

# 4b. Browser distribution from id_31
print("Sampling browser from IEEE id_31 distribution...")
browser_raw = ieee_merged["id_31"].dropna().str.lower()
browser_map = {"chrome": 0, "firefox": 0, "safari": 0, "edge": 0, "other": 0}
for b in browser_raw:
    b = str(b)
    if "chrome" in b:
        browser_map["chrome"] += 1
    elif "firefox" in b:
        browser_map["firefox"] += 1
    elif "safari" in b:
        browser_map["safari"] += 1
    elif "edge" in b or "ie" in b or "samsung" in b:
        browser_map["edge"] += 1
    else:
        browser_map["other"] += 1

total_browsers = sum(browser_map.values())
if total_browsers == 0:
    browser_probs = [0.6, 0.15, 0.15, 0.05, 0.05]
    browser_labels = ["chrome", "firefox", "safari", "edge", "other"]
else:
    browser_labels = list(browser_map.keys())
    browser_probs = [v / total_browsers for v in browser_map.values()]

print(f"  Browser distribution: {dict(zip(browser_labels, [f'{p:.3f}' for p in browser_probs]))}")

df["browser"] = np.random.choice(browser_labels, size=len(df), p=browser_probs)

# 5. email_domain_match = 0 for all (no email data in transactions)
df["email_domain_match"] = 0

# 6. Save to transactions_features.csv
out_path = os.path.join(DATA_DIR, "transactions_features.csv")
print(f"\nSaving to {out_path}...")
df.to_csv(out_path, index=False)

# 7. Print stats
print(f"\n{'='*50}")
print(f"STEP 3 COMPLETE")
print(f"  Shape: {df.shape}")
print(f"  Columns: {list(df.columns)}")
print(f"\n  Null counts for new columns:")
new_cols = ["amt_log", "amt_rounded_flag", "device_type", "browser", "email_domain_match"]
for c in new_cols:
    print(f"    {c}: {df[c].isna().sum()} nulls")
print(f"{'='*50}")
