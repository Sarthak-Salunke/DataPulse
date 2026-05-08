"""
Step 2 — Fix class imbalance using SMOTE
"""
import pandas as pd
import numpy as np
import json
import os

from imblearn.over_sampling import SMOTE

DATA_DIR = r"E:\Project\My project\DataPulse - Copy\data"

print("=== STEP 2: SMOTE Class Balancing ===\n")

# 1. Load merged dataset
print("Loading transactions_merged.csv...")
df = pd.read_csv(os.path.join(DATA_DIR, "transactions_merged.csv"), low_memory=False)
print(f"  Shape: {df.shape}")

before_rows = len(df)
before_fraud_rate = df["is_fraud"].mean()
n_fraud_before = (df["is_fraud"] == 1).sum()
n_legit_before = (df["is_fraud"] == 0).sum()
print(f"  Before SMOTE: {before_rows:,} rows, fraud={n_fraud_before:,}, legit={n_legit_before:,}, rate={before_fraud_rate:.4f}")

# 2. Apply SMOTE on 4 numeric features only
NUMERIC_FEATURES = ["amt", "unix_time", "merch_lat", "merch_long"]
CATEGORICAL_COLS = ["cc_num", "first", "last", "trans_num", "trans_date", "trans_time", "category", "merchant"]

# Ensure numeric cols are float
for c in NUMERIC_FEATURES:
    df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0.0)

X_num = df[NUMERIC_FEATURES].values
y = df["is_fraud"].fillna(0).astype(int).values

print(f"\nApplying SMOTE with sampling_strategy=0.20...")
smote = SMOTE(sampling_strategy=0.20, random_state=42, k_neighbors=5)
X_res, y_res = smote.fit_resample(X_num, y)

print(f"  After SMOTE numeric: X_res shape={X_res.shape}, fraud={y_res.sum():,}, legit={(y_res==0).sum():,}")

# Build new DataFrame
n_original = len(df)
n_synthetic = len(X_res) - n_original

# For synthetic fraud rows, copy categorical values from real fraud rows
fraud_mask_original = (df["is_fraud"] == 1).values
real_fraud_df = df[fraud_mask_original][CATEGORICAL_COLS].reset_index(drop=True)

# Identify synthetic rows: they are appended at the end by SMOTE for fraud class
# y_res has original rows first, then synthetic fraud rows at the end
# Number of synthetic rows
synthetic_indices = range(n_original, len(X_res))
n_syn = len(synthetic_indices)

print(f"  Synthetic fraud rows to create: {n_syn:,}")

# Sample categorical values from real fraud rows with replacement
np.random.seed(42)
cat_sample_idx = np.random.choice(len(real_fraud_df), size=n_syn, replace=True)
synthetic_cats = real_fraud_df.iloc[cat_sample_idx].reset_index(drop=True)

# Build synthetic rows DataFrame
synthetic_df = pd.DataFrame(X_res[n_original:], columns=NUMERIC_FEATURES)
for c in CATEGORICAL_COLS:
    synthetic_df[c] = synthetic_cats[c].values
synthetic_df["is_fraud"] = y_res[n_original:]

# Combine original + synthetic
result_df = pd.concat([df, synthetic_df], ignore_index=True)

# Verify
after_rows = len(result_df)
after_fraud_rate = result_df["is_fraud"].mean()
n_fraud_after = (result_df["is_fraud"] == 1).sum()
n_legit_after = (result_df["is_fraud"] == 0).sum()

print(f"\nAfter SMOTE + categorical fill: {after_rows:,} rows, fraud={n_fraud_after:,}, legit={n_legit_after:,}, rate={after_fraud_rate:.4f}")

# 3. Compute class weights
n_total = after_rows
n_fraud = n_fraud_after
n_legit = n_legit_after

class_weight_0 = float(n_fraud) / float(n_total)
class_weight_1 = float(n_legit) / float(n_total)
scale_pos_weight = float(n_legit) / float(n_fraud)

print(f"\nClass weights:")
print(f"  class_weight[0]: {class_weight_0:.6f}")
print(f"  class_weight[1]: {class_weight_1:.6f}")
print(f"  scale_pos_weight: {scale_pos_weight:.4f}")

# 4. Save balanced dataset
balanced_path = os.path.join(DATA_DIR, "transactions_balanced.csv")
result_df.to_csv(balanced_path, index=False)
print(f"\nSaved balanced dataset to {balanced_path}")

# 5. Save class weights
weights_path = os.path.join(DATA_DIR, "class_weights.json")
weights_data = {
    "class_weight": {
        "0": class_weight_0,
        "1": class_weight_1
    },
    "scale_pos_weight": scale_pos_weight
}
with open(weights_path, "w") as f:
    json.dump(weights_data, f, indent=2)
print(f"Saved class weights to {weights_path}")

# 6. Print summary
print(f"\n{'='*50}")
print(f"STEP 2 COMPLETE")
print(f"  Before SMOTE: {before_rows:,} rows, fraud rate={before_fraud_rate:.4f}")
print(f"  After SMOTE:  {after_rows:,} rows, fraud rate={after_fraud_rate:.4f}")
print(f"  Fraud count:  {n_fraud:,} | Legit count: {n_legit:,}")
print(f"  scale_pos_weight: {scale_pos_weight:.4f}")
print(f"{'='*50}")
