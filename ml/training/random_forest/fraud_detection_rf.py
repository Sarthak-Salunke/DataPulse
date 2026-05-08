import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    classification_report, confusion_matrix, roc_auc_score,
    precision_recall_curve, auc, roc_curve, f1_score,
    recall_score, precision_score
)
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import math
import pickle
import os
import warnings
warnings.filterwarnings('ignore')

project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
data_dir = os.path.join(project_root, 'data')
output_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'output')
os.makedirs(output_dir, exist_ok=True)

np.random.seed(42)

print("=" * 80)
print("FRAUD DETECTION - RANDOM FOREST MODEL (Standalone)")
print("Mirrors Spark RF config: 100 trees, maxDepth=10, 6 features")
print("=" * 80)

# ============================================================
# STEP 1: Load Data
# ============================================================
customer_df = pd.read_csv(os.path.join(data_dir, 'customer.csv'))
transactions_df = pd.read_csv(os.path.join(data_dir, 'transactions.csv'))

print(f"\nData Loaded:")
print(f"   Customers: {len(customer_df)} records")
print(f"   Transactions: {len(transactions_df)} records")
print(f"   Fraud Rate: {transactions_df['is_fraud'].mean()*100:.2f}%")

# ============================================================
# STEP 2: Feature Engineering (same 6 features as Spark RF)
# ============================================================
print("\nEngineering Features (matching Spark RF pipeline)...")

df = transactions_df.merge(customer_df, on='cc_num', how='left', suffixes=('_trans', '_cust'))

# Compute distance using Haversine (same as Spark utils.py)
def haversine(lat1, lon1, lat2, lon2):
    if pd.isna(lat1) or pd.isna(lon1) or pd.isna(lat2) or pd.isna(lon2):
        return 0.0
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    c = 2 * math.asin(math.sqrt(a))
    return 6371 * c

df['distance'] = df.apply(lambda r: haversine(r['lat'], r['long'], r['merch_lat'], r['merch_long']), axis=1)

# Compute age from dob
df['dob'] = pd.to_datetime(df['dob'], utc=True)
df['age'] = (pd.to_datetime(df['trans_date'], utc=True) - df['dob']).dt.days // 365

# The 6 features used by Spark RF: cc_num, category, merchant, distance, amt, age
feature_cols = ['cc_num', 'category', 'merchant', 'distance', 'amt', 'age']

print(f"   Features: {feature_cols}")
print(f"   Total samples: {len(df)}")

# ============================================================
# STEP 3: Encode categorical features (same as Spark StringIndexer)
# ============================================================
print("\nEncoding categorical features...")

le_category = LabelEncoder()
le_merchant = LabelEncoder()
le_ccnum = LabelEncoder()

df['category_encoded'] = le_category.fit_transform(df['category'])
df['merchant_encoded'] = le_merchant.fit_transform(df['merchant'])
df['cc_num_encoded'] = le_ccnum.fit_transform(df['cc_num'])

# Fill missing values (same defaults as Spark script)
df['distance'] = df['distance'].fillna(0.0)
df['amt'] = df['amt'].fillna(50.0)
df['age'] = df['age'].fillna(40)

encoded_features = ['cc_num_encoded', 'category_encoded', 'merchant_encoded', 'distance', 'amt', 'age']
X = df[encoded_features].values
y = df['is_fraud'].values

print(f"   Fraud: {y.sum()} ({y.mean()*100:.2f}%)")
print(f"   Non-fraud: {(y==0).sum()} ({(1-y.mean())*100:.2f}%)")

# ============================================================
# STEP 4: Balance dataset (random undersampling, same as Spark)
# ============================================================
print("\nBalancing dataset (random undersampling)...")

fraud_idx = np.where(y == 1)[0]
non_fraud_idx = np.where(y == 0)[0]

np.random.shuffle(non_fraud_idx)
balanced_non_fraud_idx = non_fraud_idx[:len(fraud_idx)]

balanced_idx = np.concatenate([fraud_idx, balanced_non_fraud_idx])
np.random.shuffle(balanced_idx)

X_balanced = X[balanced_idx]
y_balanced = y[balanced_idx]

print(f"   Balanced dataset: {len(y_balanced)} samples")
print(f"   Fraud: {y_balanced.sum()}, Non-fraud: {(y_balanced==0).sum()}")

# ============================================================
# STEP 5: Train/Test Split (70/30, same as Spark)
# ============================================================
X_train, X_test, y_train, y_test = train_test_split(
    X_balanced, y_balanced, test_size=0.3, random_state=42, stratify=y_balanced
)

print(f"\nTrain/Test Split:")
print(f"   Training: {len(y_train)} samples")
print(f"   Test: {len(y_test)} samples")

# ============================================================
# STEP 6: Train Random Forest (same config as Spark)
# ============================================================
print("\nTraining Random Forest (100 trees, maxDepth=10)...")

rf = RandomForestClassifier(
    n_estimators=100,
    max_depth=10,
    random_state=42,
    n_jobs=-1
)

rf.fit(X_train, y_train)

# ============================================================
# STEP 7: Evaluate
# ============================================================
print("\n" + "=" * 80)
print(" MODEL EVALUATION RESULTS")
print("=" * 80)

y_pred = rf.predict(X_test)
y_proba = rf.predict_proba(X_test)[:, 1]

accuracy = (y_pred == y_test).mean()
f1 = f1_score(y_test, y_pred)
precision = precision_score(y_test, y_pred)
recall = recall_score(y_test, y_pred)
roc_auc = roc_auc_score(y_test, y_proba)
pr_precision, pr_recall, _ = precision_recall_curve(y_test, y_proba)
pr_auc = auc(pr_recall, pr_precision)

print(f"\n   Accuracy:   {accuracy*100:.2f}%")
print(f"   F1-Score:   {f1:.4f}")
print(f"   Precision:  {precision:.4f}")
print(f"   Recall:     {recall:.4f}")
print(f"   ROC-AUC:    {roc_auc:.4f}")
print(f"   PR-AUC:     {pr_auc:.4f}")

print(f"\nClassification Report:")
print(classification_report(y_test, y_pred, target_names=['Non-Fraud', 'Fraud']))

print(f"Confusion Matrix:")
cm = confusion_matrix(y_test, y_pred)
print(cm)

# Feature importance
print(f"\nFeature Importances:")
for name, imp in sorted(zip(encoded_features, rf.feature_importances_), key=lambda x: -x[1]):
    print(f"   {name}: {imp:.4f}")

# ============================================================
# STEP 8: Save outputs
# ============================================================

# Save comparison CSV
results_df = pd.DataFrame([{
    'Model': 'Random Forest (6 features)',
    'ROC-AUC': roc_auc,
    'PR-AUC': pr_auc,
    'F1-Score': f1,
    'Precision': precision,
    'Recall': recall
}])
results_df.to_csv(os.path.join(output_dir, 'rf_model_comparison.csv'), index=False)

# Save feature importance
feat_imp_df = pd.DataFrame({
    'feature': encoded_features,
    'importance': rf.feature_importances_
}).sort_values('importance', ascending=False)
feat_imp_df.to_csv(os.path.join(output_dir, 'rf_feature_importance.csv'), index=False)

# Save performance curves
fig, axes = plt.subplots(1, 2, figsize=(14, 5))

# ROC Curve
fpr, tpr, _ = roc_curve(y_test, y_proba)
axes[0].plot(fpr, tpr, 'b-', label=f'RF (AUC = {roc_auc:.4f})')
axes[0].plot([0, 1], [0, 1], 'k--', label='Random')
axes[0].set_xlabel('False Positive Rate')
axes[0].set_ylabel('True Positive Rate')
axes[0].set_title('ROC Curve - Random Forest')
axes[0].legend()

# PR Curve
axes[1].plot(pr_recall, pr_precision, 'g-', label=f'RF (AUC = {pr_auc:.4f})')
axes[1].axhline(y=y_test.mean(), color='k', linestyle='--', label=f'Baseline (Fraud Rate = {y_test.mean():.4f})')
axes[1].set_xlabel('Recall')
axes[1].set_ylabel('Precision')
axes[1].set_title('Precision-Recall Curve - Random Forest')
axes[1].legend()

plt.tight_layout()
plt.savefig(os.path.join(output_dir, 'rf_performance_curves.png'), dpi=150)
plt.close()

# Save model
with open(os.path.join(output_dir, 'rf_model.pkl'), 'wb') as f:
    pickle.dump(rf, f)

# Save results summary
results_summary = {
    'accuracy': accuracy,
    'f1_score': f1,
    'precision': precision,
    'recall': recall,
    'roc_auc': roc_auc,
    'pr_auc': pr_auc,
    'confusion_matrix': cm
}
with open(os.path.join(output_dir, 'rf_results_summary.pkl'), 'wb') as f:
    pickle.dump(results_summary, f)

print(f"\nOutputs saved to: {output_dir}")
print("=" * 80)
print("TRAINING COMPLETE")
print("=" * 80)
