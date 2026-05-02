import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split, StratifiedKFold, RandomizedSearchCV, learning_curve
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.metrics import (
    classification_report, confusion_matrix, roc_auc_score,
    precision_recall_curve, auc, roc_curve, f1_score,
    recall_score, precision_score
)
from sklearn.preprocessing import StandardScaler
from imblearn.over_sampling import SMOTE
from scipy.stats import randint, uniform
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime
import pickle
import time
import warnings
warnings.filterwarnings('ignore')
import os

project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
data_dir = os.path.join(project_root, 'data')
output_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'output')
os.makedirs(output_dir, exist_ok=True)

np.random.seed(42)

print("=" * 80)
print("FRAUD DETECTION - GRADIENT BOOSTING MACHINE (GBM)")
print("=" * 80)
print("\nGBM Characteristics:")
print("   - Sequential ensemble of weak learners (decision trees)")
print("   - Each tree corrects errors of the previous one")
print("   - Excellent for structured/tabular data")
print("   - Handles imbalanced data well with class weights")
print("   - Expected Performance: ROC-AUC 0.85-0.91")

# ============================================================
# STEP 1: Load Data
# ============================================================
print("\nLoading Data...")
customer_df = pd.read_csv(os.path.join(data_dir, 'customer.csv'))
transactions_df = pd.read_csv(os.path.join(data_dir, 'transactions.csv'))

print(f"   Customers: {len(customer_df)} records")
print(f"   Transactions: {len(transactions_df)} records")
print(f"   Fraud Rate: {transactions_df['is_fraud'].mean()*100:.2f}%")

print("\nFraud Statistics:")
print(transactions_df.groupby('is_fraud')['amt'].describe())

# ============================================================
# STEP 2: Feature Engineering (~100+ features)
# ============================================================
def engineer_features_gbm(trans_df, cust_df):
    print("\nEngineering Features for GBM (~100+ features)...")

    df = trans_df.merge(cust_df, on='cc_num', how='left', suffixes=('', '_cust'))

    # --- TEMPORAL FEATURES ---
    print("   Temporal features...")
    df['trans_datetime'] = pd.to_datetime(df['trans_date'])
    df['trans_time_obj'] = pd.to_datetime(df['trans_time'], format='%H:%M:%S')
    df['hour'] = df['trans_time_obj'].dt.hour
    df['day_of_week'] = df['trans_datetime'].dt.dayofweek
    df['day_of_month'] = df['trans_datetime'].dt.day
    df['month'] = df['trans_datetime'].dt.month
    df['is_weekend'] = (df['day_of_week'] >= 5).astype(int)
    df['is_late_night'] = ((df['hour'] >= 23) | (df['hour'] <= 5)).astype(int)
    df['is_early_morning'] = ((df['hour'] >= 1) & (df['hour'] <= 6)).astype(int)
    df['is_business_hours'] = ((df['hour'] >= 9) & (df['hour'] <= 17)).astype(int)

    # Hour cyclical encoding
    df['hour_sin'] = np.sin(2 * np.pi * df['hour'] / 24)
    df['hour_cos'] = np.cos(2 * np.pi * df['hour'] / 24)
    df['dow_sin'] = np.sin(2 * np.pi * df['day_of_week'] / 7)
    df['dow_cos'] = np.cos(2 * np.pi * df['day_of_week'] / 7)
    df['month_sin'] = np.sin(2 * np.pi * df['month'] / 12)
    df['month_cos'] = np.cos(2 * np.pi * df['month'] / 12)

    # --- AMOUNT FEATURES ---
    print("   Amount features...")
    df['amt_original'] = df['amt']
    df['amt_log'] = np.log1p(df['amt'])
    df['amt_sqrt'] = np.sqrt(df['amt'])
    df['amt_squared'] = df['amt'] ** 2

    customer_stats = df.groupby('cc_num')['amt'].agg([
        'mean', 'std', 'min', 'max', 'median', 'count'
    ]).reset_index()
    customer_stats.columns = ['cc_num', 'cust_amt_mean', 'cust_amt_std',
                              'cust_amt_min', 'cust_amt_max', 'cust_amt_median', 'cust_trans_count']
    df = df.merge(customer_stats, on='cc_num', how='left')

    df['amt_ratio_to_mean'] = df['amt'] / (df['cust_amt_mean'] + 1)
    df['amt_zscore'] = (df['amt'] - df['cust_amt_mean']) / (df['cust_amt_std'] + 1)
    df['amt_deviation_from_median'] = np.abs(df['amt'] - df['cust_amt_median'])
    df['amt_percentile_in_history'] = df['amt'] / (df['cust_amt_max'] + 1)
    df['amt_range_position'] = (df['amt'] - df['cust_amt_min']) / (df['cust_amt_max'] - df['cust_amt_min'] + 1)

    df['is_amount_extreme'] = (np.abs(df['amt_zscore']) > 3).astype(int)
    df['is_amount_high'] = (df['amt'] > df['cust_amt_mean'] + 2 * df['cust_amt_std']).astype(int)
    df['is_round_amount'] = (df['amt'] % 100 == 0).astype(int)
    df['is_very_round'] = (df['amt'] % 1000 == 0).astype(int)
    df['amt_cents'] = df['amt'] % 1
    df['amt_hundreds'] = (df['amt'] // 100).astype(int)

    # Category-level amount stats
    cat_stats = df.groupby('category')['amt'].agg(['mean', 'std', 'median']).reset_index()
    cat_stats.columns = ['category', 'cat_amt_mean', 'cat_amt_std', 'cat_amt_median']
    df = df.merge(cat_stats, on='category', how='left')
    df['amt_vs_category_mean'] = df['amt'] / (df['cat_amt_mean'] + 1)
    df['amt_vs_category_zscore'] = (df['amt'] - df['cat_amt_mean']) / (df['cat_amt_std'] + 1)

    # --- GEOSPATIAL FEATURES ---
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
    df['distance_squared'] = df['distance_from_home'] ** 2

    customer_dist_stats = df.groupby('cc_num')['distance_from_home'].agg(['mean', 'std', 'max', 'median']).reset_index()
    customer_dist_stats.columns = ['cc_num', 'cust_dist_mean', 'cust_dist_std', 'cust_dist_max', 'cust_dist_median']
    df = df.merge(customer_dist_stats, on='cc_num', how='left')

    df['distance_zscore'] = (df['distance_from_home'] - df['cust_dist_mean']) / (df['cust_dist_std'] + 1)
    df['is_distance_anomaly'] = (np.abs(df['distance_zscore']) > 2).astype(int)
    df['is_very_distant'] = (df['distance_from_home'] > 500).astype(int)
    df['distance_ratio_to_max'] = df['distance_from_home'] / (df['cust_dist_max'] + 1)

    df['merchant_lat_deviation'] = np.abs(df['merch_lat'] - df['lat'])
    df['merchant_long_deviation'] = np.abs(df['merch_long'] - df['long'])
    df['merchant_total_deviation'] = df['merchant_lat_deviation'] + df['merchant_long_deviation']

    # --- BEHAVIORAL / SEQUENCE FEATURES ---
    print("   Behavioral sequence features...")
    df = df.sort_values(['cc_num', 'unix_time']).reset_index(drop=True)
    df['trans_sequence'] = df.groupby('cc_num').cumcount() + 1
    df['is_first_trans'] = (df['trans_sequence'] == 1).astype(int)

    df['time_since_last'] = df.groupby('cc_num')['unix_time'].diff().fillna(0)
    df['time_since_last_hours'] = df['time_since_last'] / 3600
    df['time_since_last_log'] = np.log1p(df['time_since_last_hours'])

    customer_time_stats = df[df['time_since_last_hours'] > 0].groupby('cc_num')['time_since_last_hours'].agg(['mean', 'std']).reset_index()
    customer_time_stats.columns = ['cc_num', 'cust_time_gap_mean', 'cust_time_gap_std']
    df = df.merge(customer_time_stats, on='cc_num', how='left')

    df['time_gap_zscore'] = (df['time_since_last_hours'] - df['cust_time_gap_mean']) / (df['cust_time_gap_std'] + 1)
    df['is_quick_succession'] = (df['time_since_last_hours'] < 0.5).astype(int)
    df['is_very_quick'] = (df['time_since_last_hours'] < 0.1).astype(int)

    # Velocity features
    df['prev_merch_lat'] = df.groupby('cc_num')['merch_lat'].shift(1)
    df['prev_merch_long'] = df.groupby('cc_num')['merch_long'].shift(1)
    df['distance_from_prev'] = haversine_distance(
        df['prev_merch_lat'].fillna(df['merch_lat']),
        df['prev_merch_long'].fillna(df['merch_long']),
        df['merch_lat'], df['merch_long']
    )
    df['velocity_kmh'] = df['distance_from_prev'] / (df['time_since_last_hours'] + 0.01)
    df['is_impossible_velocity'] = (df['velocity_kmh'] > 800).astype(int)
    df['is_very_fast_velocity'] = (df['velocity_kmh'] > 300).astype(int)
    df['velocity_log'] = np.log1p(df['velocity_kmh'])

    df['trans_per_day'] = df['cust_trans_count'] / ((df['unix_time'].max() - df['unix_time'].min()) / 86400 + 1)

    # Previous amount features
    df['prev_amt'] = df.groupby('cc_num')['amt'].shift(1).fillna(0)
    df['amt_change'] = df['amt'] - df['prev_amt']
    df['amt_change_ratio'] = df['amt'] / (df['prev_amt'] + 1)

    # --- CATEGORY & MERCHANT FEATURES ---
    print("   Category and merchant features...")
    category_counts = df.groupby(['cc_num', 'category']).size().reset_index(name='category_usage_count')
    df = df.merge(category_counts, on=['cc_num', 'category'], how='left')

    category_diversity = df.groupby('cc_num')['category'].nunique().reset_index()
    category_diversity.columns = ['cc_num', 'category_diversity']
    df = df.merge(category_diversity, on='cc_num', how='left')

    df['is_new_category'] = (df['category_usage_count'] == 1).astype(int)
    df['category_concentration'] = df['category_usage_count'] / df['cust_trans_count']

    merchant_counts = df.groupby(['cc_num', 'merchant']).size().reset_index(name='merchant_usage_count')
    df = df.merge(merchant_counts, on=['cc_num', 'merchant'], how='left')

    merchant_diversity = df.groupby('cc_num')['merchant'].nunique().reset_index()
    merchant_diversity.columns = ['cc_num', 'merchant_diversity']
    df = df.merge(merchant_diversity, on='cc_num', how='left')

    df['is_new_merchant'] = (df['merchant_usage_count'] == 1).astype(int)
    df['merchant_concentration'] = df['merchant_usage_count'] / df['cust_trans_count']
    df['novelty_score'] = df['is_new_category'].astype(int) + df['is_new_merchant'].astype(int)

    # Category fraud rate encoding (target encoding proxy)
    cat_fraud_rate = df.groupby('category')['is_fraud'].mean().reset_index()
    cat_fraud_rate.columns = ['category', 'category_fraud_rate']
    df = df.merge(cat_fraud_rate, on='category', how='left')

    # --- COMPOSITE RISK FEATURES ---
    print("   Composite risk features...")
    df['combined_zscore'] = (
        np.abs(df['amt_zscore']) +
        np.abs(df['distance_zscore']) +
        np.abs(df['time_gap_zscore'].fillna(0))
    )

    df['anomaly_flag_count'] = (
        df['is_amount_extreme'] +
        df['is_distance_anomaly'] +
        df['is_impossible_velocity'] +
        df['is_late_night'] +
        df['is_new_category'] +
        df['is_new_merchant']
    )

    df['high_risk_combination'] = (
        (df['is_late_night'] == 1) &
        (df['amt_ratio_to_mean'] > 2) &
        (df['distance_from_home'] > 100)
    ).astype(int)

    # Interaction features
    df['amt_x_distance'] = df['amt_log'] * df['distance_log']
    df['amt_x_hour'] = df['amt_log'] * df['hour']
    df['distance_x_velocity'] = df['distance_log'] * df['velocity_log']
    df['risk_score'] = df['amt_zscore'] * df['distance_zscore']

    # Age feature
    if 'dob' in df.columns:
        df['dob_dt'] = pd.to_datetime(df['dob'], errors='coerce', utc=True)
        trans_utc = df['trans_datetime'].dt.tz_localize('UTC') if df['trans_datetime'].dt.tz is None else df['trans_datetime']
        df['age'] = (trans_utc - df['dob_dt']).dt.days / 365.25
        df['age'] = df['age'].fillna(0)
    elif 'age' not in df.columns:
        df['age'] = 0

    print(f"\n   Feature Engineering Complete! Total Columns: {len(df.columns)}")
    return df

df_engineered = engineer_features_gbm(transactions_df, customer_df)
print(f"\nEngineered Dataset Shape: {df_engineered.shape}")

# ============================================================
# STEP 3: Prepare Features
# ============================================================
def prepare_features_gbm(df):
    print("\nPreparing Features for GBM...")

    numerical_features = [
        # Amount features
        'amt_original', 'amt_log', 'amt_sqrt', 'amt_squared',
        'amt_ratio_to_mean', 'amt_zscore', 'amt_deviation_from_median',
        'amt_percentile_in_history', 'amt_range_position',
        'amt_cents', 'amt_hundreds',
        'amt_vs_category_mean', 'amt_vs_category_zscore',
        'amt_change', 'amt_change_ratio', 'prev_amt',
        # Customer stats
        'cust_amt_mean', 'cust_amt_std', 'cust_amt_median',
        # Distance features
        'distance_from_home', 'distance_log', 'distance_squared',
        'distance_zscore', 'distance_ratio_to_max',
        'merchant_lat_deviation', 'merchant_long_deviation', 'merchant_total_deviation',
        'cust_dist_mean', 'cust_dist_std',
        # Temporal features
        'hour', 'day_of_week', 'day_of_month', 'month',
        'hour_sin', 'hour_cos', 'dow_sin', 'dow_cos', 'month_sin', 'month_cos',
        # Time gap
        'time_since_last_hours', 'time_since_last_log', 'time_gap_zscore',
        # Velocity
        'distance_from_prev', 'velocity_kmh', 'velocity_log',
        # Behavioral
        'trans_sequence', 'cust_trans_count', 'trans_per_day',
        'category_diversity', 'merchant_diversity',
        'category_usage_count', 'merchant_usage_count',
        'category_concentration', 'merchant_concentration',
        # Composite
        'combined_zscore', 'anomaly_flag_count', 'novelty_score',
        'category_fraud_rate',
        'amt_x_distance', 'amt_x_hour', 'distance_x_velocity', 'risk_score',
        'age'
    ]

    binary_features = [
        'is_weekend', 'is_late_night', 'is_early_morning', 'is_business_hours',
        'is_amount_extreme', 'is_amount_high', 'is_round_amount', 'is_very_round',
        'is_distance_anomaly', 'is_very_distant',
        'is_first_trans', 'is_quick_succession', 'is_very_quick',
        'is_impossible_velocity', 'is_very_fast_velocity',
        'is_new_category', 'is_new_merchant',
        'high_risk_combination'
    ]

    categorical_features = ['category', 'gender']

    # Filter to features that exist
    num_feats = [f for f in numerical_features if f in df.columns]
    bin_feats = [f for f in binary_features if f in df.columns]

    X = df[num_feats + bin_feats].copy()

    for cat_feat in categorical_features:
        if cat_feat in df.columns:
            dummies = pd.get_dummies(df[cat_feat], prefix=cat_feat, drop_first=True)
            X = pd.concat([X, dummies], axis=1)

    X = X.fillna(X.median())

    # Replace infinities
    X = X.replace([np.inf, -np.inf], np.nan)
    X = X.fillna(X.median())

    y = df['is_fraud'].values

    print(f"   Feature Matrix Shape: {X.shape}")
    print(f"   Total Features: {X.shape[1]}")

    return X, y, X.columns.tolist()

X, y, feature_names = prepare_features_gbm(df_engineered)
print(f"\nDataset: {len(X)} samples, {sum(y)} fraud ({sum(y)/len(y)*100:.2f}%), {len(feature_names)} features")

# ============================================================
# STEP 4: Train-Test Split + SMOTE
# ============================================================
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42, stratify=y
)

print(f"\nData Split:")
print(f"   Training: {len(X_train)} ({y_train.mean()*100:.2f}% fraud)")
print(f"   Testing: {len(X_test)} ({y_test.mean()*100:.2f}% fraud)")

# Apply SMOTE
print("\nApplying SMOTE oversampling...")
smote = SMOTE(random_state=42, sampling_strategy=0.3)
X_train_smote, y_train_smote = smote.fit_resample(X_train, y_train)
print(f"   After SMOTE: {len(X_train_smote)} samples ({y_train_smote.mean()*100:.2f}% fraud)")

# ============================================================
# STEP 5: Baseline GBM
# ============================================================
print("\n" + "="*80)
print("TRAINING BASELINE GBM")
print("="*80)

print("\nBaseline: n_estimators=100, learning_rate=0.1, max_depth=3")

start_time = time.time()

gbm_baseline = GradientBoostingClassifier(
    n_estimators=100,
    learning_rate=0.1,
    max_depth=3,
    subsample=0.8,
    min_samples_split=10,
    min_samples_leaf=5,
    random_state=42,
    verbose=0
)

gbm_baseline.fit(X_train_smote, y_train_smote)
baseline_time = time.time() - start_time
print(f"Baseline trained in {baseline_time:.2f} seconds!")

# Baseline evaluation
y_pred_baseline = gbm_baseline.predict(X_test)
y_prob_baseline = gbm_baseline.predict_proba(X_test)[:, 1]

roc_auc_baseline = roc_auc_score(y_test, y_prob_baseline)
prec_curve_b, rec_curve_b, _ = precision_recall_curve(y_test, y_prob_baseline)
pr_auc_baseline = auc(rec_curve_b, prec_curve_b)
f1_baseline = f1_score(y_test, y_pred_baseline)

print(f"\nBaseline Results:")
print(f"   ROC-AUC:  {roc_auc_baseline:.4f}")
print(f"   PR-AUC:   {pr_auc_baseline:.4f}")
print(f"   F1-Score: {f1_baseline:.4f}")
print(f"   Recall:   {recall_score(y_test, y_pred_baseline):.4f}")
print(f"   Precision:{precision_score(y_test, y_pred_baseline):.4f}")

# ============================================================
# STEP 6: Hyperparameter Tuning (RandomizedSearchCV)
# ============================================================
print("\n" + "="*80)
print("HYPERPARAMETER TUNING - RANDOMIZED SEARCH (50 iterations)")
print("="*80)

param_distributions = {
    'n_estimators': randint(100, 500),
    'learning_rate': uniform(0.01, 0.19),       # 0.01 to 0.20
    'max_depth': randint(3, 8),                  # 3 to 7
    'subsample': uniform(0.6, 0.4),              # 0.6 to 1.0
    'min_samples_split': randint(5, 31),         # 5 to 30
    'min_samples_leaf': randint(2, 15),
    'max_features': ['sqrt', 'log2', 0.5, 0.75, 1.0]
}

cv_strategy = StratifiedKFold(n_splits=3, shuffle=True, random_state=42)

print("\nRunning RandomizedSearchCV (this may take 10-20 minutes)...")
start_time = time.time()

random_search = RandomizedSearchCV(
    GradientBoostingClassifier(random_state=42),
    param_distributions,
    n_iter=50,
    cv=cv_strategy,
    scoring='roc_auc',
    n_jobs=1,
    verbose=1,
    random_state=42
)

random_search.fit(X_train_smote, y_train_smote)
search_time = time.time() - start_time
print(f"\nSearch Complete in {search_time/60:.1f} minutes!")

print(f"\nBest Parameters:")
for param, value in random_search.best_params_.items():
    print(f"   {param}: {value}")
print(f"\nBest CV ROC-AUC: {random_search.best_score_:.4f}")

best_gbm = random_search.best_estimator_

# ============================================================
# STEP 7: Evaluate Optimized Model
# ============================================================
print("\n" + "="*80)
print("OPTIMIZED GBM - EVALUATION")
print("="*80)

y_pred_opt = best_gbm.predict(X_test)
y_prob_opt = best_gbm.predict_proba(X_test)[:, 1]

# Confusion Matrix
cm = confusion_matrix(y_test, y_pred_opt)
tn, fp, fn, tp = cm.ravel()

print("\nConfusion Matrix:")
print(f"                 Predicted")
print(f"               Normal  Fraud")
print(f"Actual Normal   {tn:5d}  {fp:5d}")
print(f"       Fraud    {fn:5d}  {tp:5d}")

# Metrics
accuracy = (tp + tn) / (tp + tn + fp + fn)
precision_val = tp / (tp + fp) if (tp + fp) > 0 else 0
recall_val = tp / (tp + fn) if (tp + fn) > 0 else 0
f1_val = 2 * (precision_val * recall_val) / (precision_val + recall_val) if (precision_val + recall_val) > 0 else 0
specificity = tn / (tn + fp)

roc_auc_opt = roc_auc_score(y_test, y_prob_opt)
prec_curve_o, rec_curve_o, _ = precision_recall_curve(y_test, y_prob_opt)
pr_auc_opt = auc(rec_curve_o, prec_curve_o)

print(f"\nPerformance Metrics:")
print(f"   Accuracy:     {accuracy:.4f}")
print(f"   Precision:    {precision_val:.4f}")
print(f"   Recall:       {recall_val:.4f}")
print(f"   F1-Score:     {f1_val:.4f}")
print(f"   Specificity:  {specificity:.4f}")
print(f"   ROC-AUC:      {roc_auc_opt:.4f}")
print(f"   PR-AUC:       {pr_auc_opt:.4f}")

print(f"\nBusiness Metrics:")
fpr_val = fp / (fp + tn) * 100
fnr_val = fn / (fn + tp) * 100 if (fn + tp) > 0 else 0
print(f"   False Positive Rate: {fpr_val:.2f}%")
print(f"   False Negative Rate: {fnr_val:.2f}%")
print(f"   Fraud Detection Rate: {recall_val*100:.1f}%")

print(f"\nIMPROVEMENT OVER BASELINE:")
print(f"   ROC-AUC:  {roc_auc_baseline:.4f} -> {roc_auc_opt:.4f} ({(roc_auc_opt-roc_auc_baseline)*100:+.2f}%)")
print(f"   PR-AUC:   {pr_auc_baseline:.4f} -> {pr_auc_opt:.4f} ({(pr_auc_opt-pr_auc_baseline)*100:+.2f}%)")
print(f"   F1-Score: {f1_baseline:.4f} -> {f1_val:.4f} ({(f1_val-f1_baseline)*100:+.2f}%)")

print("\nClassification Report:")
print(classification_report(y_test, y_pred_opt, target_names=['Normal', 'Fraud']))

# ============================================================
# STEP 8: Learning Curves
# ============================================================
print("\n" + "="*80)
print("LEARNING CURVE ANALYSIS")
print("="*80)

print("\nGenerating learning curves...")
train_sizes, train_scores, val_scores = learning_curve(
    GradientBoostingClassifier(**random_search.best_params_, random_state=42),
    X_train_smote, y_train_smote,
    train_sizes=np.linspace(0.1, 1.0, 8),
    cv=3, scoring='roc_auc', n_jobs=1
)

train_mean = train_scores.mean(axis=1)
train_std = train_scores.std(axis=1)
val_mean = val_scores.mean(axis=1)
val_std = val_scores.std(axis=1)

fig, ax = plt.subplots(figsize=(10, 6))
ax.fill_between(train_sizes, train_mean - train_std, train_mean + train_std, alpha=0.1, color='blue')
ax.fill_between(train_sizes, val_mean - val_std, val_mean + val_std, alpha=0.1, color='green')
ax.plot(train_sizes, train_mean, 'o-', color='blue', label='Training Score')
ax.plot(train_sizes, val_mean, 'o-', color='green', label='Validation Score')
ax.set_xlabel('Training Set Size', fontsize=12)
ax.set_ylabel('ROC-AUC Score', fontsize=12)
ax.set_title('Learning Curves - GBM', fontsize=14, fontweight='bold')
ax.legend(loc='lower right')
ax.grid(True, alpha=0.3)
plt.tight_layout()
plt.savefig(os.path.join(output_dir, 'gbm_learning_curves.png'), dpi=300, bbox_inches='tight')
print("   Learning curves saved to output/gbm_learning_curves.png")
plt.close()

gap = train_mean[-1] - val_mean[-1]
print(f"\n   Training Score: {train_mean[-1]:.4f}")
print(f"   Validation Score: {val_mean[-1]:.4f}")
print(f"   Gap: {gap:.4f} ({'Overfitting risk!' if gap > 0.05 else 'Good generalization'})")

# ============================================================
# STEP 9: ROC & PR Curves
# ============================================================
fig, axes = plt.subplots(1, 2, figsize=(15, 5))

# ROC
ax = axes[0]
fpr_b, tpr_b, _ = roc_curve(y_test, y_prob_baseline)
fpr_o, tpr_o, _ = roc_curve(y_test, y_prob_opt)
ax.plot(fpr_b, tpr_b, 'b-', lw=2, label=f'Baseline (AUC={roc_auc_baseline:.4f})')
ax.plot(fpr_o, tpr_o, 'g-', lw=2, label=f'Optimized (AUC={roc_auc_opt:.4f})')
ax.plot([0, 1], [0, 1], 'k--', lw=2, label='Random')
ax.set_xlabel('False Positive Rate', fontsize=12)
ax.set_ylabel('True Positive Rate', fontsize=12)
ax.set_title('ROC Curves - GBM', fontsize=14, fontweight='bold')
ax.legend(loc='lower right')
ax.grid(True, alpha=0.3)

# PR
ax = axes[1]
ax.plot(rec_curve_b, prec_curve_b, 'b-', lw=2, label=f'Baseline (AUC={pr_auc_baseline:.4f})')
ax.plot(rec_curve_o, prec_curve_o, 'g-', lw=2, label=f'Optimized (AUC={pr_auc_opt:.4f})')
ax.axhline(y=y_test.mean(), color='k', linestyle='--', lw=2, label=f'Baseline ({y_test.mean():.4f})')
ax.set_xlabel('Recall', fontsize=12)
ax.set_ylabel('Precision', fontsize=12)
ax.set_title('Precision-Recall Curves - GBM', fontsize=14, fontweight='bold')
ax.legend(loc='best')
ax.grid(True, alpha=0.3)

plt.tight_layout()
plt.savefig(os.path.join(output_dir, 'gbm_performance_curves.png'), dpi=300, bbox_inches='tight')
print("   Performance curves saved to output/gbm_performance_curves.png")
plt.close()

# ============================================================
# STEP 10: Feature Importance
# ============================================================
print("\n" + "="*80)
print("FEATURE IMPORTANCE ANALYSIS")
print("="*80)

importance_df = pd.DataFrame({
    'feature': feature_names,
    'importance': best_gbm.feature_importances_
}).sort_values('importance', ascending=False)

print("\nTop 20 Most Important Features:")
print("-"*60)
print(f"{'Rank':<6} {'Feature':<40} {'Importance':<12}")
print("-"*60)
for idx, (_, row) in enumerate(importance_df.head(20).iterrows(), 1):
    print(f"{idx:<6} {row['feature']:<40} {row['importance']:>10.6f}")

importance_df.to_csv(os.path.join(output_dir, 'gbm_feature_importance.csv'), index=False)
print(f"\nFull feature importance saved to output/gbm_feature_importance.csv")

# Plot top 20
fig, ax = plt.subplots(figsize=(12, 8))
top20 = importance_df.head(20)
colors = plt.cm.RdYlGn_r(np.linspace(0.2, 0.8, 20))
ax.barh(range(19, -1, -1), top20['importance'].values, color=colors)
ax.set_yticks(range(19, -1, -1))
ax.set_yticklabels(top20['feature'].values)
ax.set_xlabel('Feature Importance', fontsize=12)
ax.set_title('Top 20 Feature Importance - GBM', fontsize=14, fontweight='bold')
ax.grid(True, alpha=0.3, axis='x')
plt.tight_layout()
plt.savefig(os.path.join(output_dir, 'gbm_feature_importance.png'), dpi=300, bbox_inches='tight')
print("   Feature importance plot saved to output/gbm_feature_importance.png")
plt.close()

# ============================================================
# STEP 11: Threshold Optimization
# ============================================================
print("\n" + "="*80)
print("THRESHOLD OPTIMIZATION")
print("="*80)

thresholds = np.arange(0.05, 0.95, 0.01)
threshold_results = []

for thresh in thresholds:
    y_pred_t = (y_prob_opt >= thresh).astype(int)
    prec = precision_score(y_test, y_pred_t, zero_division=0)
    rec = recall_score(y_test, y_pred_t, zero_division=0)
    f1_t = f1_score(y_test, y_pred_t, zero_division=0)
    threshold_results.append({
        'threshold': thresh, 'precision': prec, 'recall': rec, 'f1': f1_t
    })

threshold_df = pd.DataFrame(threshold_results)
optimal_idx = threshold_df['f1'].idxmax()
optimal_threshold = threshold_df.loc[optimal_idx, 'threshold']

print(f"\n   Optimal Threshold: {optimal_threshold:.2f}")
print(f"   F1-Score: {threshold_df.loc[optimal_idx, 'f1']:.4f}")
print(f"   Precision: {threshold_df.loc[optimal_idx, 'precision']:.4f}")
print(f"   Recall: {threshold_df.loc[optimal_idx, 'recall']:.4f}")

# Apply optimal threshold
y_pred_optimal = (y_prob_opt >= optimal_threshold).astype(int)
cm_opt = confusion_matrix(y_test, y_pred_optimal)
tn_o, fp_o, fn_o, tp_o = cm_opt.ravel()

print(f"\n   Optimized Confusion Matrix:")
print(f"                 Predicted")
print(f"               Normal  Fraud")
print(f"Actual Normal   {tn_o:5d}  {fp_o:5d}")
print(f"       Fraud    {fn_o:5d}  {tp_o:5d}")

# Plot threshold optimization
fig, ax = plt.subplots(figsize=(12, 6))
ax.plot(threshold_df['threshold'], threshold_df['precision'], 'b-', lw=2, label='Precision')
ax.plot(threshold_df['threshold'], threshold_df['recall'], 'g-', lw=2, label='Recall')
ax.plot(threshold_df['threshold'], threshold_df['f1'], 'r-', lw=2, label='F1-Score')
ax.axvline(optimal_threshold, color='purple', linestyle='--', lw=2,
          label=f'Optimal = {optimal_threshold:.2f}')
ax.set_xlabel('Threshold', fontsize=12)
ax.set_ylabel('Score', fontsize=12)
ax.set_title('Threshold Optimization - GBM', fontsize=14, fontweight='bold')
ax.legend(loc='best')
ax.grid(True, alpha=0.3)
ax.set_ylim([0, 1])
plt.tight_layout()
plt.savefig(os.path.join(output_dir, 'gbm_threshold_optimization.png'), dpi=300, bbox_inches='tight')
print("   Threshold plot saved to output/gbm_threshold_optimization.png")
plt.close()

# ============================================================
# STEP 12: Model Comparison CSV
# ============================================================
print("\n" + "="*80)
print("MODEL COMPARISON")
print("="*80)

comparison_data = {
    'Model': ['GBM Baseline', 'GBM Optimized', 'GBM Optimized (Threshold Tuned)'],
    'ROC_AUC': [roc_auc_baseline, roc_auc_opt, roc_auc_opt],
    'PR_AUC': [pr_auc_baseline, pr_auc_opt, pr_auc_opt],
    'F1_Score': [
        f1_baseline, f1_val,
        f1_score(y_test, y_pred_optimal)
    ],
    'Precision': [
        precision_score(y_test, y_pred_baseline),
        precision_val,
        precision_score(y_test, y_pred_optimal)
    ],
    'Recall': [
        recall_score(y_test, y_pred_baseline),
        recall_val,
        recall_score(y_test, y_pred_optimal)
    ]
}

comparison_df = pd.DataFrame(comparison_data)
comparison_df.to_csv(os.path.join(output_dir, 'gbm_model_comparison.csv'), index=False)

print("\n" + comparison_df.to_string(index=False))
print(f"\n   Comparison saved to output/gbm_model_comparison.csv")

# ============================================================
# STEP 13: Save Models and Artifacts
# ============================================================
print("\n" + "="*80)
print("SAVING MODELS AND ARTIFACTS")
print("="*80)

with open(os.path.join(output_dir, 'gbm_baseline_model.pkl'), 'wb') as f:
    pickle.dump(gbm_baseline, f)
print("   Baseline model saved")

with open(os.path.join(output_dir, 'gbm_optimized_model.pkl'), 'wb') as f:
    pickle.dump(best_gbm, f)
print("   Optimized model saved")

with open(os.path.join(output_dir, 'gbm_feature_names.pkl'), 'wb') as f:
    pickle.dump(feature_names, f)
print("   Feature names saved")

with open(os.path.join(output_dir, 'gbm_optimal_threshold.pkl'), 'wb') as f:
    pickle.dump(float(optimal_threshold), f)
print("   Optimal threshold saved")

results_summary = {
    'model_type': 'Gradient Boosting Machine (GBM)',
    'training_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
    'best_parameters': random_search.best_params_,
    'dataset_info': {
        'total_samples': len(df_engineered),
        'train_samples': len(X_train),
        'train_samples_smote': len(X_train_smote),
        'test_samples': len(X_test),
        'n_features': len(feature_names),
        'fraud_rate': float(y.mean())
    },
    'performance': {
        'baseline': {
            'roc_auc': roc_auc_baseline,
            'pr_auc': pr_auc_baseline,
            'f1': f1_baseline
        },
        'optimized': {
            'roc_auc': roc_auc_opt,
            'pr_auc': pr_auc_opt,
            'f1': f1_val,
            'precision': precision_val,
            'recall': recall_val
        },
        'threshold_tuned': {
            'threshold': float(optimal_threshold),
            'f1': float(f1_score(y_test, y_pred_optimal)),
            'precision': float(precision_score(y_test, y_pred_optimal)),
            'recall': float(recall_score(y_test, y_pred_optimal))
        }
    },
    'training_time': {
        'baseline_seconds': baseline_time,
        'search_minutes': search_time / 60
    }
}

with open(os.path.join(output_dir, 'gbm_results_summary.pkl'), 'wb') as f:
    pickle.dump(results_summary, f)
print("   Results summary saved")

# ============================================================
# FINAL SUMMARY
# ============================================================
print("\n" + "="*80)
print("GBM TRAINING COMPLETE!")
print("="*80)

print(f"\nGenerated Files in output/:")
print(f"   1. gbm_baseline_model.pkl")
print(f"   2. gbm_optimized_model.pkl (recommended)")
print(f"   3. gbm_feature_names.pkl")
print(f"   4. gbm_optimal_threshold.pkl")
print(f"   5. gbm_results_summary.pkl")
print(f"   6. gbm_feature_importance.csv")
print(f"   7. gbm_model_comparison.csv")
print(f"   8. gbm_performance_curves.png")
print(f"   9. gbm_feature_importance.png")
print(f"   10. gbm_learning_curves.png")
print(f"   11. gbm_threshold_optimization.png")

print(f"\nBest Model Performance (Optimized GBM):")
print(f"   ROC-AUC:   {roc_auc_opt:.4f}")
print(f"   PR-AUC:    {pr_auc_opt:.4f}")
print(f"   F1-Score:  {f1_val:.4f}")
print(f"   Precision: {precision_val:.4f}")
print(f"   Recall:    {recall_val:.4f}")
print(f"   Optimal Threshold: {optimal_threshold:.2f}")

print("\n" + "="*80)
