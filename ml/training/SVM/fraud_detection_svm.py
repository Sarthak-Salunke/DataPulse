import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split, StratifiedKFold, RandomizedSearchCV
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC
from sklearn.metrics import (
    classification_report, confusion_matrix, roc_auc_score,
    precision_recall_curve, auc, roc_curve, f1_score,
    recall_score, precision_score, make_scorer
)
from sklearn.calibration import CalibratedClassifierCV
from sklearn.decomposition import PCA
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime
import pickle
import time
import warnings
warnings.filterwarnings('ignore')

from imblearn.over_sampling import SMOTE
from imblearn.under_sampling import RandomUnderSampler

import os

project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
data_dir = os.path.join(project_root, 'data')
output_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'output')
os.makedirs(output_dir, exist_ok=True)

np.random.seed(42)

print("=" * 80)
print("FRAUD DETECTION - SUPPORT VECTOR MACHINE (SVM) MODEL")
print("=" * 80)
print("\nSVM Characteristics:")
print("   - Uses kernel trick for non-linear classification")
print("   - Finds optimal hyperplane with maximum margin")
print("   - Excellent for complex decision boundaries")
print("   - Requires feature scaling (critical!)")

# ============================================================
# STEP 1 & 2: Load Data
# ============================================================
print("\nLoading Data...")
customer_df = pd.read_csv(os.path.join(data_dir, 'customer.csv'))
transactions_df = pd.read_csv(os.path.join(data_dir, 'transactions.csv'))

print(f"   Customers: {len(customer_df)} records")
print(f"   Transactions: {len(transactions_df)} records")
print(f"   Fraud Rate: {transactions_df['is_fraud'].mean()*100:.2f}%")

print("\nData Quality Check:")
print(f"   Customer missing values: {customer_df.isnull().sum().sum()}")
print(f"   Transaction missing values: {transactions_df.isnull().sum().sum()}")
print(f"   Duplicate transactions: {transactions_df.duplicated(subset='trans_num').sum()}")

# ============================================================
# STEP 3: Feature Engineering
# ============================================================
def engineer_features(trans_df, cust_df):
    print("\nEngineering Features for SVM...")

    df = trans_df.merge(cust_df, on='cc_num', how='left', suffixes=('', '_cust'))

    # TEMPORAL FEATURES
    print("   Temporal features...")
    df['trans_datetime'] = pd.to_datetime(df['trans_date'])
    df['trans_time_obj'] = pd.to_datetime(df['trans_time'], format='%H:%M:%S')
    df['hour'] = df['trans_time_obj'].dt.hour
    df['day_of_week'] = df['trans_datetime'].dt.dayofweek
    df['day_of_month'] = df['trans_datetime'].dt.day
    df['month'] = df['trans_datetime'].dt.month
    df['is_weekend'] = (df['day_of_week'] >= 5).astype(int)

    # Cyclical encoding for hour (important for SVM)
    df['hour_sin'] = np.sin(2 * np.pi * df['hour'] / 24)
    df['hour_cos'] = np.cos(2 * np.pi * df['hour'] / 24)
    df['day_sin'] = np.sin(2 * np.pi * df['day_of_week'] / 7)
    df['day_cos'] = np.cos(2 * np.pi * df['day_of_week'] / 7)

    # High-risk time windows
    df['is_late_night'] = ((df['hour'] >= 23) | (df['hour'] <= 5)).astype(int)
    df['is_business_hours'] = ((df['hour'] >= 9) & (df['hour'] <= 17)).astype(int)

    # AMOUNT FEATURES
    print("   Amount-based features...")
    df['amt_log'] = np.log1p(df['amt'])
    df['amt_sqrt'] = np.sqrt(df['amt'])

    customer_stats = df.groupby('cc_num')['amt'].agg([
        'mean', 'std', 'min', 'max', 'median', 'count'
    ]).reset_index()
    customer_stats.columns = ['cc_num', 'cust_amt_mean', 'cust_amt_std',
                              'cust_amt_min', 'cust_amt_max', 'cust_amt_median', 'cust_trans_count']
    df = df.merge(customer_stats, on='cc_num', how='left')

    df['amt_ratio_to_avg'] = df['amt'] / (df['cust_amt_mean'] + 1)
    df['amt_zscore'] = (df['amt'] - df['cust_amt_mean']) / (df['cust_amt_std'] + 1)
    df['amt_above_median'] = (df['amt'] > df['cust_amt_median']).astype(int)
    df['amt_percentile'] = df['amt'] / (df['cust_amt_max'] + 1)

    df['is_high_amount'] = (df['amt'] > df['amt'].quantile(0.75)).astype(int)
    df['is_very_high_amount'] = (df['amt'] > df['amt'].quantile(0.95)).astype(int)

    # GEOSPATIAL FEATURES
    print("   Geospatial features...")
    def haversine_distance(lat1, lon1, lat2, lon2):
        R = 6371
        lat1, lon1, lat2, lon2 = map(np.radians, [lat1, lon1, lat2, lon2])
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        a = np.sin(dlat/2)**2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon/2)**2
        c = 2 * np.arcsin(np.sqrt(a))
        return R * c

    df['distance_from_home'] = haversine_distance(
        df['lat'], df['long'], df['merch_lat'], df['merch_long']
    )
    df['distance_log'] = np.log1p(df['distance_from_home'])
    df['is_local'] = (df['distance_from_home'] < 10).astype(int)
    df['is_distant'] = (df['distance_from_home'] > 100).astype(int)
    df['is_very_distant'] = (df['distance_from_home'] > 500).astype(int)

    df['merchant_lat_bin'] = pd.cut(df['merch_lat'], bins=10, labels=False)
    df['merchant_long_bin'] = pd.cut(df['merch_long'], bins=10, labels=False)

    # BEHAVIORAL FEATURES
    print("   Behavioral features...")
    df = df.sort_values(['cc_num', 'unix_time']).reset_index(drop=True)
    df['trans_sequence'] = df.groupby('cc_num').cumcount() + 1

    df['time_since_last'] = df.groupby('cc_num')['unix_time'].diff().fillna(0)
    df['time_since_last_hours'] = df['time_since_last'] / 3600
    df['time_since_last_log'] = np.log1p(df['time_since_last_hours'])

    df['is_very_quick'] = (df['time_since_last'] < 300).astype(int)
    df['is_quick'] = (df['time_since_last'] < 3600).astype(int)

    # Distance from previous transaction
    df['prev_merch_lat'] = df.groupby('cc_num')['merch_lat'].shift(1)
    df['prev_merch_long'] = df.groupby('cc_num')['merch_long'].shift(1)
    df['distance_from_prev'] = haversine_distance(
        df['prev_merch_lat'].fillna(df['merch_lat']),
        df['prev_merch_long'].fillna(df['merch_long']),
        df['merch_lat'], df['merch_long']
    )

    # Velocity
    df['transaction_velocity'] = df['distance_from_prev'] / (df['time_since_last_hours'] + 0.01)
    df['is_impossible_velocity'] = (df['transaction_velocity'] > 800).astype(int)

    # CATEGORY & MERCHANT
    print("   Category and merchant features...")
    category_counts = df.groupby(['cc_num', 'category']).size().reset_index(name='category_usage_count')
    df = df.merge(category_counts, on=['cc_num', 'category'], how='left')

    top_category = df.groupby('cc_num')['category'].agg(
        lambda x: x.mode()[0] if len(x.mode()) > 0 else x.iloc[0]
    ).reset_index()
    top_category.columns = ['cc_num', 'top_category']
    df = df.merge(top_category, on='cc_num', how='left')

    df['is_top_category'] = (df['category'] == df['top_category']).astype(int)
    df['is_new_category'] = (df['category_usage_count'] == 1).astype(int)

    merchant_counts = df.groupby(['cc_num', 'merchant']).size().reset_index(name='merchant_usage_count')
    df = df.merge(merchant_counts, on=['cc_num', 'merchant'], how='left')
    df['is_new_merchant'] = (df['merchant_usage_count'] == 1).astype(int)

    # RISK AGGREGATES
    print("   Risk aggregation features...")
    merchant_fraud = df.groupby('merchant')['is_fraud'].agg(['mean', 'count']).reset_index()
    merchant_fraud.columns = ['merchant', 'merchant_fraud_rate', 'merchant_total_trans']
    df = df.merge(merchant_fraud, on='merchant', how='left')
    df['merchant_fraud_rate'] = df['merchant_fraud_rate'].fillna(df['is_fraud'].mean())

    category_fraud = df.groupby('category')['is_fraud'].agg(['mean', 'count']).reset_index()
    category_fraud.columns = ['category', 'category_fraud_rate', 'category_total_trans']
    df = df.merge(category_fraud, on='category', how='left')

    hour_fraud = df.groupby('hour')['is_fraud'].mean().reset_index()
    hour_fraud.columns = ['hour', 'hour_fraud_rate']
    df = df.merge(hour_fraud, on='hour', how='left')

    df['merchant_category_risk'] = df['merchant_fraud_rate'] * df['category_fraud_rate']
    df['time_amount_risk'] = df['hour_fraud_rate'] * df['amt_zscore']

    print(f"\n   Feature Engineering Complete! Total Columns: {len(df.columns)}")
    return df

df_engineered = engineer_features(transactions_df, customer_df)

# ============================================================
# STEP 4: Feature Selection for SVM
# ============================================================
def prepare_svm_features(df):
    print("\nPreparing Features for SVM...")

    numerical_features = [
        'amt', 'amt_log', 'amt_sqrt', 'amt_ratio_to_avg', 'amt_zscore',
        'amt_percentile',
        'hour_sin', 'hour_cos', 'day_sin', 'day_cos',
        'day_of_month', 'month',
        'distance_from_home', 'distance_log', 'distance_from_prev',
        'transaction_velocity',
        'trans_sequence', 'time_since_last_hours', 'time_since_last_log',
        'cust_trans_count', 'category_usage_count', 'merchant_usage_count',
        'merchant_fraud_rate', 'category_fraud_rate', 'hour_fraud_rate',
        'merchant_category_risk', 'merchant_total_trans',
        'merchant_lat_bin', 'merchant_long_bin'
    ]

    binary_features = [
        'is_weekend', 'is_late_night', 'is_business_hours',
        'amt_above_median', 'is_high_amount', 'is_very_high_amount',
        'is_local', 'is_distant', 'is_very_distant',
        'is_very_quick', 'is_quick', 'is_impossible_velocity',
        'is_top_category', 'is_new_category', 'is_new_merchant'
    ]

    categorical_features = ['category', 'gender']

    print(f"   Numerical features: {len(numerical_features)}")
    print(f"   Binary features: {len(binary_features)}")
    print(f"   Categorical features: {len(categorical_features)}")

    X = df[numerical_features + binary_features].copy()

    for cat_feature in categorical_features:
        if cat_feature in df.columns:
            dummies = pd.get_dummies(df[cat_feature], prefix=cat_feature, drop_first=True)
            X = pd.concat([X, dummies], axis=1)

    X = X.fillna(X.median())
    y = df['is_fraud'].values

    print(f"\n   Feature Matrix Shape: {X.shape}")
    print(f"   Total Features: {X.shape[1]}")
    print(f"   Fraud Rate: {y.mean()*100:.2f}%")

    return X, y, X.columns.tolist()

X, y, feature_names = prepare_svm_features(df_engineered)

print(f"\nFinal Dataset:")
print(f"   Samples: {len(X)}")
print(f"   Features: {len(feature_names)}")
print(f"   Normal: {sum(y==0)} ({sum(y==0)/len(y)*100:.1f}%)")
print(f"   Fraud: {sum(y==1)} ({sum(y==1)/len(y)*100:.1f}%)")

# ============================================================
# STEP 5: Train-Test Split
# ============================================================
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42, stratify=y
)

print(f"\nData Split:")
print(f"   Training: {len(X_train)} samples ({y_train.mean()*100:.2f}% fraud)")
print(f"   Testing: {len(X_test)} samples ({y_test.mean()*100:.2f}% fraud)")

# ============================================================
# STEP 6: Feature Scaling (CRITICAL for SVM)
# ============================================================
print("\n" + "="*80)
print("FEATURE SCALING (CRITICAL FOR SVM)")
print("="*80)

scaler = StandardScaler()
X_train_scaled = scaler.fit_transform(X_train)
X_test_scaled = scaler.transform(X_test)

print(f"\nScaling Applied:")
print(f"   Training set - Mean: {X_train_scaled.mean():.6f}, Std: {X_train_scaled.std():.6f}")
print(f"   Test set - Mean: {X_test_scaled.mean():.6f}, Std: {X_test_scaled.std():.6f}")

# ============================================================
# STEP 7: Handle Class Imbalance
# ============================================================
print("\n" + "="*80)
print("HANDLING CLASS IMBALANCE")
print("="*80)

print(f"\nOriginal Distribution:")
print(f"   Normal: {sum(y_train==0)}")
print(f"   Fraud: {sum(y_train==1)}")
print(f"   Ratio: 1:{sum(y_train==0)/sum(y_train==1):.1f}")

smote = SMOTE(sampling_strategy=0.5, random_state=42, k_neighbors=5)
X_train_smote, y_train_smote = smote.fit_resample(X_train_scaled, y_train)

under = RandomUnderSampler(sampling_strategy=0.67, random_state=42)
X_train_balanced, y_train_balanced = under.fit_resample(X_train_smote, y_train_smote)

print(f"\nBalanced Distribution:")
print(f"   Normal: {sum(y_train_balanced==0)}")
print(f"   Fraud: {sum(y_train_balanced==1)}")
print(f"   Ratio: 1:{sum(y_train_balanced==0)/sum(y_train_balanced==1):.1f}")
print(f"   Total Training Samples: {len(X_train_balanced)}")

# ============================================================
# STEP 8: Train Baseline SVM
# ============================================================
print("\n" + "="*80)
print("TRAINING BASELINE SVM MODEL")
print("="*80)

print("\nBaseline Configuration:")
print("   Kernel: RBF (Radial Basis Function)")
print("   C: 1.0 (regularization)")
print("   gamma: 'scale' (automatic)")
print("   class_weight: 'balanced'")

svm_baseline = SVC(
    kernel='rbf', C=1.0, gamma='scale', class_weight='balanced',
    probability=True, random_state=42, verbose=False
)

print("\nTraining baseline SVM...")
start_time = time.time()
svm_baseline.fit(X_train_balanced, y_train_balanced)
training_time = time.time() - start_time
print(f"Training Complete in {training_time:.1f} seconds")

print(f"\nSupport Vector Statistics:")
print(f"   Total Support Vectors: {svm_baseline.n_support_.sum()}")
print(f"   Class 0 (Normal): {svm_baseline.n_support_[0]}")
print(f"   Class 1 (Fraud): {svm_baseline.n_support_[1]}")
print(f"   Percentage of training data: {svm_baseline.n_support_.sum()/len(X_train_balanced)*100:.1f}%")

# ============================================================
# STEP 9: Evaluate Model
# ============================================================
def evaluate_svm_model(model, X_test_scaled, y_test, model_name="SVM"):
    print(f"\n{'='*80}")
    print(f"{model_name.upper()} - TEST SET EVALUATION")
    print(f"{'='*80}")

    y_pred = model.predict(X_test_scaled)
    y_proba = model.predict_proba(X_test_scaled)[:, 1]

    cm = confusion_matrix(y_test, y_pred)
    tn, fp, fn, tp = cm.ravel()

    print("\nConfusion Matrix:")
    print(f"                 Predicted")
    print(f"               Normal  Fraud")
    print(f"Actual Normal   {tn:5d}  {fp:5d}")
    print(f"       Fraud    {fn:5d}  {tp:5d}")

    accuracy = (tp + tn) / (tp + tn + fp + fn)
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0
    f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0
    specificity = tn / (tn + fp) if (tn + fp) > 0 else 0

    roc_auc = roc_auc_score(y_test, y_proba)
    precision_curve, recall_curve, _ = precision_recall_curve(y_test, y_proba)
    pr_auc = auc(recall_curve, precision_curve)

    print(f"\nPerformance Metrics:")
    print(f"   Accuracy:     {accuracy:.4f}")
    print(f"   Precision:    {precision:.4f}  ({precision*100:.1f}% of flagged are fraud)")
    print(f"   Recall:       {recall:.4f}  (Caught {recall*100:.1f}% of fraud)")
    print(f"   F1-Score:     {f1:.4f}")
    print(f"   Specificity:  {specificity:.4f}  ({specificity*100:.1f}% normal correctly classified)")
    print(f"   ROC-AUC:      {roc_auc:.4f}")
    print(f"   PR-AUC:       {pr_auc:.4f}")

    print(f"\nBusiness Metrics:")
    fpr_val = fp / (fp + tn) * 100
    fnr_val = fn / (fn + tp) * 100
    print(f"   False Positive Rate: {fpr_val:.2f}% ({fp} normal flagged)")
    print(f"   False Negative Rate: {fnr_val:.2f}% ({fn} fraud missed)")
    print(f"   Fraud Detection Rate: {recall*100:.1f}%")

    return {
        'accuracy': accuracy, 'precision': precision, 'recall': recall,
        'f1': f1, 'roc_auc': roc_auc, 'pr_auc': pr_auc,
        'confusion_matrix': cm, 'predictions': y_pred, 'probabilities': y_proba
    }

baseline_results = evaluate_svm_model(svm_baseline, X_test_scaled, y_test, "Baseline SVM")

# ============================================================
# STEP 10: Hyperparameter Tuning
# ============================================================
print("\n" + "="*80)
print("HYPERPARAMETER TUNING - RANDOMIZED SEARCH")
print("="*80)

param_distributions = {
    'C': [0.1, 1, 10, 50, 100],
    'gamma': ['scale', 'auto', 0.001, 0.01, 0.1, 1],
    'kernel': ['rbf', 'poly'],
    'degree': [2, 3, 4],
    'class_weight': ['balanced', {0: 1, 1: 20}, {0: 1, 1: 30}]
}

print("\nSearch Space:")
for param, values in param_distributions.items():
    print(f"   {param}: {values}")

cv_strategy = StratifiedKFold(n_splits=3, shuffle=True, random_state=42)

random_search = RandomizedSearchCV(
    SVC(probability=True, random_state=42),
    param_distributions=param_distributions,
    n_iter=50, cv=cv_strategy, scoring='roc_auc',
    n_jobs=-1, verbose=2, random_state=42
)

print("\nRunning Randomized Search (50 iterations, 3-fold CV)...")
start_time = time.time()
random_search.fit(X_train_balanced, y_train_balanced)
search_time = time.time() - start_time

print(f"\nSearch Complete in {search_time/60:.1f} minutes!")

print(f"\nBest Parameters Found:")
for param, value in random_search.best_params_.items():
    print(f"   {param}: {value}")

print(f"\nCross-Validation Performance:")
print(f"   Best CV ROC-AUC: {random_search.best_score_:.4f}")
print(f"   Mean CV Score: {random_search.cv_results_['mean_test_score'].mean():.4f}")
print(f"   Std CV Score: {random_search.cv_results_['std_test_score'].mean():.4f}")

best_svm = random_search.best_estimator_

print(f"\nBest Model Support Vectors:")
print(f"   Total: {best_svm.n_support_.sum()}")
print(f"   Class 0: {best_svm.n_support_[0]}")
print(f"   Class 1: {best_svm.n_support_[1]}")

# ============================================================
# STEP 11: Evaluate Optimized Model
# ============================================================
print("\n" + "="*80)
print("OPTIMIZED SVM PERFORMANCE")
print("="*80)

optimized_results = evaluate_svm_model(best_svm, X_test_scaled, y_test, "Optimized SVM")

print(f"\nIMPROVEMENT OVER BASELINE:")
print(f"   ROC-AUC:  {baseline_results['roc_auc']:.4f} -> {optimized_results['roc_auc']:.4f} "
      f"({(optimized_results['roc_auc']-baseline_results['roc_auc'])*100:+.2f}%)")
print(f"   PR-AUC:   {baseline_results['pr_auc']:.4f} -> {optimized_results['pr_auc']:.4f} "
      f"({(optimized_results['pr_auc']-baseline_results['pr_auc'])*100:+.2f}%)")
print(f"   F1-Score: {baseline_results['f1']:.4f} -> {optimized_results['f1']:.4f} "
      f"({(optimized_results['f1']-baseline_results['f1'])*100:+.2f}%)")
print(f"   Recall:   {baseline_results['recall']:.4f} -> {optimized_results['recall']:.4f} "
      f"({(optimized_results['recall']-baseline_results['recall'])*100:+.2f}%)")

# ============================================================
# STEP 12: Probability Calibration
# ============================================================
print("\n" + "="*80)
print("PROBABILITY CALIBRATION")
print("="*80)

print("\nCalibrating probabilities with Platt scaling...")
calibrated_svm = CalibratedClassifierCV(best_svm, method='sigmoid', cv=3)
calibrated_svm.fit(X_train_balanced, y_train_balanced)
print("Calibration Complete!")

calibrated_results = evaluate_svm_model(calibrated_svm, X_test_scaled, y_test, "Calibrated SVM")

print(f"\nCALIBRATED vs OPTIMIZED:")
print(f"   ROC-AUC:  {optimized_results['roc_auc']:.4f} -> {calibrated_results['roc_auc']:.4f}")
print(f"   PR-AUC:   {optimized_results['pr_auc']:.4f} -> {calibrated_results['pr_auc']:.4f}")

# ============================================================
# STEP 13: ROC and PR Curves
# ============================================================
fig, axes = plt.subplots(1, 2, figsize=(15, 5))

models = [
    ('Baseline SVM', baseline_results['probabilities'], 'blue'),
    ('Optimized SVM', optimized_results['probabilities'], 'green'),
    ('Calibrated SVM', calibrated_results['probabilities'], 'red')
]

for name, proba, color in models:
    fpr, tpr, _ = roc_curve(y_test, proba)
    roc_auc_val = auc(fpr, tpr)
    axes[0].plot(fpr, tpr, color=color, lw=2, label=f'{name} (AUC = {roc_auc_val:.4f})')

axes[0].plot([0, 1], [0, 1], 'k--', lw=2, label='Random')
axes[0].set_xlabel('False Positive Rate', fontsize=12)
axes[0].set_ylabel('True Positive Rate', fontsize=12)
axes[0].set_title('ROC Curves - SVM Models', fontsize=14, fontweight='bold')
axes[0].legend(loc='lower right')
axes[0].grid(True, alpha=0.3)

for name, proba, color in models:
    prec_c, rec_c, _ = precision_recall_curve(y_test, proba)
    pr_auc_val = auc(rec_c, prec_c)
    axes[1].plot(rec_c, prec_c, color=color, lw=2, label=f'{name} (AUC = {pr_auc_val:.4f})')

axes[1].axhline(y=y_test.mean(), color='k', linestyle='--', lw=2,
                label=f'Baseline (Fraud Rate = {y_test.mean():.4f})')
axes[1].set_xlabel('Recall', fontsize=12)
axes[1].set_ylabel('Precision', fontsize=12)
axes[1].set_title('Precision-Recall Curves - SVM Models', fontsize=14, fontweight='bold')
axes[1].legend(loc='best')
axes[1].grid(True, alpha=0.3)

plt.tight_layout()
plt.savefig(os.path.join(output_dir, 'svm_performance_curves.png'), dpi=300, bbox_inches='tight')
print(f"\nPerformance curves saved to output/svm_performance_curves.png")
plt.close()

# ============================================================
# STEP 14: Decision Boundary Visualization (2D PCA)
# ============================================================
print("\nVisualizing Decision Boundary (2D PCA projection)...")
pca = PCA(n_components=2, random_state=42)
X_test_2d = pca.fit_transform(X_test_scaled)

h = 0.02
x_min, x_max = X_test_2d[:, 0].min() - 1, X_test_2d[:, 0].max() + 1
y_min, y_max = X_test_2d[:, 1].min() - 1, X_test_2d[:, 1].max() + 1
xx, yy = np.meshgrid(np.arange(x_min, x_max, h), np.arange(y_min, y_max, h))

svm_2d = SVC(kernel='rbf', C=best_svm.C, gamma='scale', probability=True, random_state=42)
svm_2d.fit(X_test_2d, y_test)

Z = svm_2d.predict_proba(np.c_[xx.ravel(), yy.ravel()])[:, 1]
Z = Z.reshape(xx.shape)

plt.figure(figsize=(12, 8))
plt.contourf(xx, yy, Z, alpha=0.4, cmap='RdYlGn_r', levels=20)
plt.colorbar(label='Fraud Probability')

scatter = plt.scatter(X_test_2d[:, 0], X_test_2d[:, 1],
                     c=y_test, cmap='RdYlGn_r',
                     edgecolors='black', linewidth=0.5, s=50, alpha=0.7)

plt.xlabel(f'PC1 ({pca.explained_variance_ratio_[0]*100:.1f}% variance)', fontsize=12)
plt.ylabel(f'PC2 ({pca.explained_variance_ratio_[1]*100:.1f}% variance)', fontsize=12)
plt.title('SVM Decision Boundary (2D PCA Projection)', fontsize=14, fontweight='bold')
plt.legend(*scatter.legend_elements(), title="Class", labels=['Normal', 'Fraud'])
plt.grid(True, alpha=0.3)

plt.savefig(os.path.join(output_dir, 'svm_decision_boundary.png'), dpi=300, bbox_inches='tight')
print("   Decision boundary saved to output/svm_decision_boundary.png")
plt.close()

# ============================================================
# STEP 15: Threshold Optimization
# ============================================================
print("\n" + "="*80)
print("THRESHOLD OPTIMIZATION")
print("="*80)

thresholds = np.arange(0.1, 0.9, 0.05)
f1_scores_list = []
for threshold in thresholds:
    y_pred_t = (calibrated_results['probabilities'] >= threshold).astype(int)
    f1_scores_list.append(f1_score(y_test, y_pred_t))

optimal_idx = np.argmax(f1_scores_list)
optimal_threshold_f1 = thresholds[optimal_idx]
optimal_f1 = f1_scores_list[optimal_idx]

plt.figure(figsize=(10, 6))
plt.plot(thresholds, f1_scores_list, 'b-', linewidth=2, marker='o')
plt.axvline(optimal_threshold_f1, color='r', linestyle='--', linewidth=2,
            label=f'Optimal Threshold = {optimal_threshold_f1:.2f}')
plt.xlabel('Classification Threshold', fontsize=12)
plt.ylabel('F1 Score', fontsize=12)
plt.title('Threshold Optimization for F1', fontsize=14, fontweight='bold')
plt.legend()
plt.grid(True, alpha=0.3)
plt.savefig(os.path.join(output_dir, 'svm_threshold_optimization_f1.png'), dpi=300, bbox_inches='tight')
print(f"   Threshold plot saved to output/svm_threshold_optimization_f1.png")
plt.close()

print(f"\n   Optimal Threshold: {optimal_threshold_f1:.2f}")
print(f"   F1 Score: {optimal_f1:.4f}")

y_pred_optimal = (calibrated_results['probabilities'] >= optimal_threshold_f1).astype(int)
cm = confusion_matrix(y_test, y_pred_optimal)
tn, fp, fn, tp = cm.ravel()

print(f"\nPerformance with Optimized Threshold ({optimal_threshold_f1:.2f}):")
print(f"   Precision: {tp/(tp+fp):.4f}" if (tp+fp) > 0 else "   Precision: N/A")
print(f"   Recall: {tp/(tp+fn):.4f}" if (tp+fn) > 0 else "   Recall: N/A")
print(f"   F1-Score: {optimal_f1:.4f}")
print(f"   Fraud Detection Rate: {tp/(tp+fn)*100:.1f}%" if (tp+fn) > 0 else "   Fraud Detection Rate: N/A")
print(f"   False Positive Rate: {fp/(fp+tn)*100:.2f}%" if (fp+tn) > 0 else "   False Positive Rate: N/A")

# ============================================================
# STEP 16: Model Comparison Summary
# ============================================================
print("\n" + "="*80)
print("FINAL MODEL COMPARISON SUMMARY")
print("="*80)

comparison_df = pd.DataFrame({
    'Model': ['Baseline SVM', 'Optimized SVM', 'Calibrated SVM'],
    'ROC-AUC': [baseline_results['roc_auc'], optimized_results['roc_auc'], calibrated_results['roc_auc']],
    'PR-AUC': [baseline_results['pr_auc'], optimized_results['pr_auc'], calibrated_results['pr_auc']],
    'F1-Score': [baseline_results['f1'], optimized_results['f1'], calibrated_results['f1']],
    'Recall': [baseline_results['recall'], optimized_results['recall'], calibrated_results['recall']],
    'Precision': [baseline_results['precision'], optimized_results['precision'], calibrated_results['precision']]
})

print("\nPerformance Comparison:")
print(comparison_df.to_string(index=False))

comparison_df.to_csv(os.path.join(output_dir, 'svm_model_comparison.csv'), index=False)
print("\nComparison saved to output/svm_model_comparison.csv")

# ============================================================
# STEP 17: Save Models and Artifacts
# ============================================================
print("\n" + "="*80)
print("SAVING MODELS AND ARTIFACTS")
print("="*80)

with open(os.path.join(output_dir, 'svm_fraud_model_calibrated.pkl'), 'wb') as f:
    pickle.dump(calibrated_svm, f)
print("\nCalibrated SVM saved to output/svm_fraud_model_calibrated.pkl")

with open(os.path.join(output_dir, 'svm_fraud_model_optimized.pkl'), 'wb') as f:
    pickle.dump(best_svm, f)
print("Optimized SVM saved to output/svm_fraud_model_optimized.pkl")

with open(os.path.join(output_dir, 'svm_feature_scaler.pkl'), 'wb') as f:
    pickle.dump(scaler, f)
print("Feature scaler saved to output/svm_feature_scaler.pkl")

with open(os.path.join(output_dir, 'svm_feature_names.pkl'), 'wb') as f:
    pickle.dump(feature_names, f)
print("Feature names saved to output/svm_feature_names.pkl")

with open(os.path.join(output_dir, 'svm_optimal_threshold.pkl'), 'wb') as f:
    pickle.dump(optimal_threshold_f1, f)
print("Optimal threshold saved to output/svm_optimal_threshold.pkl")

results_summary = {
    'model_type': 'Support Vector Machine (SVM)',
    'training_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
    'kernel': random_search.best_params_['kernel'],
    'best_parameters': random_search.best_params_,
    'dataset_info': {
        'total_samples': len(df_engineered),
        'train_samples': len(X_train_balanced),
        'test_samples': len(X_test),
        'n_features': len(feature_names),
        'fraud_rate': float(y.mean())
    },
    'performance': {
        'baseline': {
            'roc_auc': baseline_results['roc_auc'],
            'pr_auc': baseline_results['pr_auc'],
            'f1': baseline_results['f1']
        },
        'optimized': {
            'roc_auc': optimized_results['roc_auc'],
            'pr_auc': optimized_results['pr_auc'],
            'f1': optimized_results['f1']
        },
        'calibrated': {
            'roc_auc': calibrated_results['roc_auc'],
            'pr_auc': calibrated_results['pr_auc'],
            'f1': calibrated_results['f1']
        }
    },
    'optimal_threshold': float(optimal_threshold_f1),
    'support_vectors': {
        'total': int(best_svm.n_support_.sum()),
        'class_0': int(best_svm.n_support_[0]),
        'class_1': int(best_svm.n_support_[1])
    }
}

with open(os.path.join(output_dir, 'svm_results_summary.pkl'), 'wb') as f:
    pickle.dump(results_summary, f)
print("Results summary saved to output/svm_results_summary.pkl")

print("\n" + "="*80)
print("SVM TRAINING COMPLETE!")
print("="*80)

print(f"\nGenerated Files in output/:")
print(f"   1. svm_fraud_model_calibrated.pkl (recommended for deployment)")
print(f"   2. svm_fraud_model_optimized.pkl")
print(f"   3. svm_feature_scaler.pkl")
print(f"   4. svm_feature_names.pkl")
print(f"   5. svm_optimal_threshold.pkl")
print(f"   6. svm_results_summary.pkl")
print(f"   7. svm_model_comparison.csv")
print(f"   8. svm_performance_curves.png")
print(f"   9. svm_decision_boundary.png")
print(f"   10. svm_threshold_optimization_f1.png")

print(f"\nBest Model Performance (Calibrated SVM):")
print(f"   ROC-AUC:   {calibrated_results['roc_auc']:.4f}")
print(f"   PR-AUC:    {calibrated_results['pr_auc']:.4f}")
print(f"   F1-Score:  {calibrated_results['f1']:.4f}")
print(f"   Recall:    {calibrated_results['recall']:.4f}")
print(f"   Precision: {calibrated_results['precision']:.4f}")

print("\n" + "="*80)
