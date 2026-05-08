"""
Step 4 — Calibration set from ULB creditcard.csv for CAPE
"""
import pandas as pd
import numpy as np
import os
from sklearn.model_selection import train_test_split

DATA_DIR = r"E:\Project\My project\DataPulse - Copy\data"
ULB_PATH = os.path.join(DATA_DIR, "credit-card-fraud-detection", "creditcard.csv")

print("=== STEP 4: CAPE Calibration Set from ULB ===\n")

# 1. Load ULB creditcard.csv
print("Loading creditcard.csv...")
df = pd.read_csv(ULB_PATH, low_memory=False)
print(f"  Shape: {df.shape}")
print(f"  Columns: {list(df.columns)}")
print(f"  Fraud rate: {df['Class'].mean():.6f} ({df['Class'].mean()*100:.4f}%)")

# 2. Stratified split: 70% calibration, 30% test
print("\nSplitting 70% calibration / 30% test...")
calib, test_df = train_test_split(
    df,
    test_size=0.30,
    random_state=42,
    stratify=df["Class"]
)

print(f"  Calibration shape: {calib.shape}")
print(f"  Test shape: {test_df.shape}")

# 3. Save
calib_path = os.path.join(DATA_DIR, "cape_calibration.csv")
test_path = os.path.join(DATA_DIR, "cape_test.csv")

calib.to_csv(calib_path, index=False)
test_df.to_csv(test_path, index=False)
print(f"\nSaved calibration to {calib_path}")
print(f"Saved test to {test_path}")

# 4. Print stats
calib_fraud_rate = calib["Class"].mean()
test_fraud_rate = test_df["Class"].mean()

print(f"\n  Amount statistics:")
for name, d in [("Calibration", calib), ("Test", test_df)]:
    amt = d["Amount"]
    print(f"  {name}: mean={amt.mean():.2f}, std={amt.std():.2f}, min={amt.min():.2f}, max={amt.max():.2f}")

print(f"\n{'='*50}")
print(f"STEP 4 COMPLETE")
print(f"  Calibration: {len(calib):,} rows, fraud rate={calib_fraud_rate:.6f}")
print(f"  Test:        {len(test_df):,} rows, fraud rate={test_fraud_rate:.6f}")
print(f"{'='*50}")
