"""
Step 5 — Graph features from PaySim
"""
import pandas as pd
import numpy as np
import os

DATA_DIR = r"E:\Project\My project\DataPulse - Copy\data"
PAYSIM_PATH = os.path.join(DATA_DIR, "synthetic-financial-datasets-for-fraud-detection",
                           "PS_20174392719_1491204439457_log.csv")
CAPE_FILE = r"E:\Project\My project\DataPulse - Copy\cape\layer0_feature_store.py"

print("=== STEP 5: Graph Features from PaySim ===\n")

# 1. Load PaySim
print("Loading PaySim dataset (this may take a moment)...")
df = pd.read_csv(PAYSIM_PATH, low_memory=False)
print(f"  Shape: {df.shape}")
print(f"  Columns: {list(df.columns)}")
print(f"  Fraud rate: {df['isFraud'].mean():.6f}")
print(f"  Steps range: {df['step'].min()} to {df['step'].max()}")

# 2. Sort by nameOrig and step for rolling window computation
print("\nSorting by nameOrig and step...")
df = df.sort_values(["nameOrig", "step"]).reset_index(drop=True)

# 3. Compute rolling features using groupby + cumulative approach
# For each row, count transactions of same nameOrig in PRECEDING 1 step
# Step is integer (1 hour = 1 step)
# Preceding 1 step means: rows where same nameOrig AND step in [current_step - 1, current_step)

print("Computing graph features (preceding 1-step window per nameOrig)...")
print("  Using groupby+shift approach for efficiency...")

# Efficient approach: for each (nameOrig, step), compute stats from step-1
# Group by nameOrig+step to get per-step aggregates
# Then merge with step-1 data

# Aggregate per nameOrig per step
step_agg = df.groupby(["nameOrig", "step"]).agg(
    distinct_dest=("nameDest", "nunique"),
    outflow_amt=("amount", "sum"),
    tx_count=("amount", "count")
).reset_index()

# For each row, we want stats from (step - 1) for same nameOrig
# So shift: create prev_step aggregates
step_agg_prev = step_agg.copy()
step_agg_prev["step"] = step_agg_prev["step"] + 1  # align to "next step" = current step
step_agg_prev.rename(columns={
    "distinct_dest": "graph_distinct_accounts_1hr",
    "outflow_amt": "graph_outflow_amt_1hr",
    "tx_count": "graph_tx_count_1hr"
}, inplace=True)

# Merge onto original df
print("  Merging graph features onto original df...")
df = df.merge(
    step_agg_prev[["nameOrig", "step", "graph_distinct_accounts_1hr",
                   "graph_outflow_amt_1hr", "graph_tx_count_1hr"]],
    on=["nameOrig", "step"],
    how="left"
)

# Fill NaN (first step for each nameOrig has no preceding step)
df["graph_distinct_accounts_1hr"] = df["graph_distinct_accounts_1hr"].fillna(0).astype(int)
df["graph_outflow_amt_1hr"] = df["graph_outflow_amt_1hr"].fillna(0.0)
df["graph_tx_count_1hr"] = df["graph_tx_count_1hr"].fillna(0).astype(int)

print(f"  Done. Shape: {df.shape}")

# 4. Save
out_path = os.path.join(DATA_DIR, "graph_features.csv")
output_df = df[["nameOrig", "step", "graph_distinct_accounts_1hr",
                "graph_outflow_amt_1hr", "graph_tx_count_1hr", "isFraud"]].copy()
output_df.to_csv(out_path, index=False)
print(f"\nSaved graph features to {out_path}")

# 5. Print stats
print("\nTop 10 rows sorted by graph_distinct_accounts_1hr DESC:")
top10 = output_df.sort_values("graph_distinct_accounts_1hr", ascending=False).head(10)
print(top10.to_string(index=False))

high_dist = output_df[output_df["graph_distinct_accounts_1hr"] > 5]
fraud_rate_high = high_dist["isFraud"].mean() if len(high_dist) > 0 else 0
print(f"\nFraud rate where graph_distinct_accounts_1hr > 5: {fraud_rate_high:.6f} ({len(high_dist):,} rows)")

print(f"\n{'='*50}")
print(f"STEP 5 COMPLETE")
print(f"  Total rows: {len(output_df):,}")
print(f"  Max distinct accounts (1hr): {output_df['graph_distinct_accounts_1hr'].max()}")
print(f"  Fraud rate overall: {output_df['isFraud'].mean():.6f}")
print(f"{'='*50}")
