"""
Step 1 — Merge Sparkov (fraudTrain + fraudTest) into main transactions.csv
"""
import pandas as pd
import os

DATA_DIR = r"E:\Project\My project\DataPulse - Copy\data"

print("=== STEP 1: Merging Sparkov data into transactions.csv ===\n")

# 1. Load Sparkov datasets
print("Loading fraudTrain.csv...")
train = pd.read_csv(os.path.join(DATA_DIR, "synthetic-credit-card-transactions-fraud-detection-dataset", "fraudTrain.csv"), low_memory=False)
print(f"  fraudTrain shape: {train.shape}")

print("Loading fraudTest.csv...")
test_df = pd.read_csv(os.path.join(DATA_DIR, "synthetic-credit-card-transactions-fraud-detection-dataset", "fraudTest.csv"), low_memory=False)
print(f"  fraudTest shape: {test_df.shape}")

# 2. Drop Unnamed: 0
for df in [train, test_df]:
    if "Unnamed: 0" in df.columns:
        df.drop(columns=["Unnamed: 0"], inplace=True)

print(f"\nColumns in fraudTrain after drop: {list(train.columns)}")

# 3. Split trans_date_trans_time into trans_date and trans_time
# trans_date_trans_time format: "2019-01-01 00:00:18" or similar
for df in [train, test_df]:
    dt_col = "trans_date_trans_time"
    if dt_col in df.columns:
        parsed = pd.to_datetime(df[dt_col], errors="coerce")
        df["trans_date"] = parsed.dt.strftime("%Y-%m-%d")
        df["trans_time"] = parsed.dt.strftime("%H:%M:%S")
        df.drop(columns=[dt_col], inplace=True)

# 4. Select and reorder columns to match transactions.csv schema
TARGET_COLS = ["cc_num", "first", "last", "trans_num", "trans_date", "trans_time",
               "unix_time", "category", "merchant", "amt", "merch_lat", "merch_long", "is_fraud"]

# Check what columns are available in Sparkov
print(f"\nAvailable cols in train: {list(train.columns)}")

# Map columns: Sparkov uses same names mostly
# Handle any missing columns by filling with NaN
for df_name, df in [("train", train), ("test_df", test_df)]:
    missing = [c for c in TARGET_COLS if c not in df.columns]
    if missing:
        print(f"  Missing in {df_name}: {missing}")
        for c in missing:
            df[c] = None

sparkov_combined = pd.concat([
    train[TARGET_COLS],
    test_df[TARGET_COLS]
], ignore_index=True)

print(f"\nSparkov combined shape: {sparkov_combined.shape}")
print(f"Sparkov fraud rate: {sparkov_combined['is_fraud'].mean():.4f}")

# 5. Load existing transactions.csv
print("\nLoading existing transactions.csv...")
txn = pd.read_csv(os.path.join(DATA_DIR, "transactions.csv"), low_memory=False)
print(f"  transactions.csv shape: {txn.shape}")
print(f"  transactions.csv columns: {list(txn.columns)}")

# Ensure same column set
for c in TARGET_COLS:
    if c not in txn.columns:
        txn[c] = None

txn = txn[TARGET_COLS]

# 6. Concatenate and drop duplicates
merged = pd.concat([txn, sparkov_combined], ignore_index=True)
print(f"\nAfter concat: {merged.shape}")

before_dedup = len(merged)
merged.drop_duplicates(subset=["cc_num", "trans_time"], inplace=True)
after_dedup = len(merged)
print(f"After dedup on (cc_num, trans_time): {after_dedup} rows (dropped {before_dedup - after_dedup})")

# 7. Save merged result
out_path = os.path.join(DATA_DIR, "transactions_merged.csv")
merged.to_csv(out_path, index=False)
print(f"\nSaved to {out_path}")

# 8. Overwrite transactions_producer.csv
producer_path = os.path.join(DATA_DIR, "transactions_producer.csv")
merged.to_csv(producer_path, index=False)
print(f"Saved to {producer_path}")

# 9. Print stats
total_rows = len(merged)
unique_cc = merged["cc_num"].nunique()
fraud_rate = merged["is_fraud"].mean()

print(f"\n{'='*50}")
print(f"STEP 1 COMPLETE")
print(f"  Total rows:    {total_rows:,}")
print(f"  Unique cc_num: {unique_cc:,}")
print(f"  Fraud rate:    {fraud_rate:.4f} ({fraud_rate*100:.2f}%)")
print(f"{'='*50}")
