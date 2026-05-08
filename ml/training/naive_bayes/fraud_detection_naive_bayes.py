import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split, StratifiedKFold, GridSearchCV
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.naive_bayes import GaussianNB, MultinomialNB, ComplementNB, BernoulliNB
from sklearn.metrics import (
    classification_report, confusion_matrix, roc_auc_score,
    precision_recall_curve, auc, roc_curve, f1_score,
    recall_score, precision_score, make_scorer
)
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
print("FRAUD DETECTION - NAIVE BAYES MODEL")
print("=" * 80)
print("\nNaive Bayes Characteristics:")
print("   - Based on Bayes' Theorem with independence assumption")
print("   - Extremely fast training and prediction")
print("   - Works well with categorical and discrete features")
print("   - Provides natural probability estimates")
print("   - Great for baseline and quick iteration")

# ============================================================
# STEP 1 & 2: Load Data
# ============================================================
print("\nLoading Data...")
customer_df = pd.read_csv(os.path.join(data_dir, 'customer.csv'))
transactions_df = pd.read_csv(os.path.join(data_dir, 'transactions.csv'))

print(f"   Customers: {len(customer_df)} records")
print(f"   Transactions: {len(transactions_df)} records")
print(f"   Fraud Rate: {transactions_df['is_fraud'].mean()*100:.2f}%")

print("\nData Quality:")
print(f"   Missing values: {transactions_df.isnull().sum().sum()}")
print(f"   Duplicates: {transactions_df.duplicated().sum()}")

print("\nClass Distribution:")
print(transactions_df['is_fraud'].value_counts())
print(f"\n   Imbalance Ratio: 1:{(transactions_df['is_fraud']==0).sum()/(transactions_df['is_fraud']==1).sum():.1f}")

# ============================================================
# STEP 3: Feature Engineering for Naive Bayes
# ============================================================
def engineer_features_nb(trans_df, cust_df):
    print("\nEngineering Features for Naive Bayes...")

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

    df['time_category'] = pd.cut(df['hour'],
                                   bins=[-1, 6, 12, 18, 24],
                                   labels=['night', 'morning', 'afternoon', 'evening'])

    df['is_late_night'] = ((df['hour'] >= 23) | (df['hour'] <= 5)).astype(int)
    df['is_business_hours'] = ((df['hour'] >= 9) & (df['hour'] <= 17)).astype(int)
    df['is_rush_hour'] = ((df['hour'].isin([7, 8, 9, 17, 18, 19]))).astype(int)

    # AMOUNT FEATURES (BINNED)
    print("   Amount features (binned for NB)...")
    df['amt_original'] = df['amt']
    df['amt_log'] = np.log1p(df['amt'])

    customer_stats = df.groupby('cc_num')['amt'].agg(['mean', 'std', 'median', 'count']).reset_index()
    customer_stats.columns = ['cc_num', 'cust_amt_mean', 'cust_amt_std', 'cust_amt_median', 'cust_trans_count']
    df = df.merge(customer_stats, on='cc_num', how='left')

    df['amt_category'] = pd.qcut(df['amt'], q=5, labels=['very_low', 'low', 'medium', 'high', 'very_high'], duplicates='drop')

    df['amt_ratio'] = df['amt'] / (df['cust_amt_mean'] + 1)
    df['amt_ratio_category'] = pd.cut(df['amt_ratio'],
                                       bins=[0, 0.5, 0.8, 1.2, 2.0, 100],
                                       labels=['much_below', 'below', 'normal', 'above', 'much_above'])

    df['amt_zscore'] = (df['amt'] - df['cust_amt_mean']) / (df['cust_amt_std'] + 1)
    df['is_amount_anomaly'] = (np.abs(df['amt_zscore']) > 2).astype(int)

    df['is_high_amount'] = (df['amt'] > df['amt'].quantile(0.75)).astype(int)
    df['is_very_high_amount'] = (df['amt'] > df['amt'].quantile(0.95)).astype(int)
    df['is_round_amount'] = (df['amt'] % 100 == 0).astype(int)

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

    df['distance_km'] = haversine_distance(
        df['lat'], df['long'], df['merch_lat'], df['merch_long']
    )

    df['distance_category'] = pd.cut(df['distance_km'],
                                      bins=[0, 10, 50, 100, 500, 10000],
                                      labels=['local', 'nearby', 'regional', 'distant', 'very_distant'])

    df['is_local'] = (df['distance_km'] < 10).astype(int)
    df['is_distant'] = (df['distance_km'] > 100).astype(int)
    df['is_very_distant'] = (df['distance_km'] > 500).astype(int)

    df['merchant_region'] = pd.cut(df['merch_lat'], bins=5, labels=['region_1', 'region_2', 'region_3', 'region_4', 'region_5'])

    # BEHAVIORAL FEATURES
    print("   Behavioral features...")
    df = df.sort_values(['cc_num', 'unix_time']).reset_index(drop=True)
    df['trans_sequence'] = df.groupby('cc_num').cumcount() + 1
    df['is_first_trans'] = (df['trans_sequence'] == 1).astype(int)

    df['trans_frequency_category'] = pd.cut(df['cust_trans_count'],
                                             bins=[0, 50, 100, 150, 200, 1000],
                                             labels=['very_low', 'low', 'medium', 'high', 'very_high'])

    df['time_since_last'] = df.groupby('cc_num')['unix_time'].diff().fillna(0)
    df['time_since_last_hours'] = df['time_since_last'] / 3600

    df['time_gap_category'] = pd.cut(df['time_since_last_hours'],
                                      bins=[-1, 0.1, 1, 6, 24, 168, 10000],
                                      labels=['very_quick', 'quick', 'short', 'normal', 'long', 'very_long'])

    df['is_quick_succession'] = (df['time_since_last_hours'] < 1).astype(int)
    df['is_very_quick'] = (df['time_since_last_hours'] < 0.1).astype(int)

    df['prev_merch_lat'] = df.groupby('cc_num')['merch_lat'].shift(1)
    df['prev_merch_long'] = df.groupby('cc_num')['merch_long'].shift(1)
    df['distance_from_prev'] = haversine_distance(
        df['prev_merch_lat'].fillna(df['merch_lat']),
        df['prev_merch_long'].fillna(df['merch_long']),
        df['merch_lat'], df['merch_long']
    )

    df['velocity'] = df['distance_from_prev'] / (df['time_since_last_hours'] + 0.01)
    df['is_impossible_velocity'] = (df['velocity'] > 800).astype(int)

    # CATEGORY & MERCHANT
    print("   Category and merchant features...")
    category_counts = df.groupby(['cc_num', 'category']).size().reset_index(name='category_usage')
    df = df.merge(category_counts, on=['cc_num', 'category'], how='left')

    top_category = df.groupby('cc_num')['category'].agg(
        lambda x: x.mode()[0] if len(x.mode()) > 0 else x.iloc[0]
    ).reset_index()
    top_category.columns = ['cc_num', 'top_category']
    df = df.merge(top_category, on='cc_num', how='left')

    df['is_top_category'] = (df['category'] == df['top_category']).astype(int)
    df['is_new_category'] = (df['category_usage'] == 1).astype(int)

    merchant_counts = df.groupby(['cc_num', 'merchant']).size().reset_index(name='merchant_usage')
    df = df.merge(merchant_counts, on=['cc_num', 'merchant'], how='left')
    df['is_new_merchant'] = (df['merchant_usage'] == 1).astype(int)
    df['is_repeat_merchant'] = (df['merchant_usage'] > 1).astype(int)

    df['merchant_usage_category'] = pd.cut(df['merchant_usage'],
                                            bins=[0, 1, 3, 5, 10, 1000],
                                            labels=['new', 'occasional', 'regular', 'frequent', 'very_frequent'])

    # RISK FEATURES
    print("   Risk aggregation features...")
    merchant_fraud = df.groupby('merchant')['is_fraud'].mean().reset_index()
    merchant_fraud.columns = ['merchant', 'merchant_fraud_rate']
    df = df.merge(merchant_fraud, on='merchant', how='left')
    df['merchant_fraud_rate'] = df['merchant_fraud_rate'].fillna(df['is_fraud'].mean())

    df['merchant_risk'] = pd.cut(df['merchant_fraud_rate'],
                                  bins=[-0.1, 0.01, 0.05, 0.1, 0.2, 1.1],
                                  labels=['very_low', 'low', 'medium', 'high', 'very_high'])

    category_fraud = df.groupby('category')['is_fraud'].mean().reset_index()
    category_fraud.columns = ['category', 'category_fraud_rate']
    df = df.merge(category_fraud, on='category', how='left')

    df['category_risk'] = pd.cut(df['category_fraud_rate'],
                                  bins=[-0.1, 0.01, 0.05, 0.1, 0.2, 1.1],
                                  labels=['very_low', 'low', 'medium', 'high', 'very_high'])

    hour_fraud = df.groupby('hour')['is_fraud'].mean().reset_index()
    hour_fraud.columns = ['hour', 'hour_fraud_rate']
    df = df.merge(hour_fraud, on='hour', how='left')

    df['hour_risk'] = pd.cut(df['hour_fraud_rate'],
                              bins=[-0.1, 0.01, 0.05, 0.1, 0.2, 1.1],
                              labels=['very_low', 'low', 'medium', 'high', 'very_high'])

    risk_mapping = {'very_low': 0, 'low': 1, 'medium': 2, 'high': 3, 'very_high': 4}
    df['combined_risk_score'] = (
        df['merchant_risk'].map(risk_mapping).fillna(2).astype(float) +
        df['category_risk'].map(risk_mapping).fillna(2).astype(float) +
        df['hour_risk'].map(risk_mapping).fillna(2).astype(float)
    )

    df['combined_risk_category'] = pd.cut(df['combined_risk_score'],
                                           bins=[-1, 2, 4, 6, 8, 15],
                                           labels=['very_low', 'low', 'medium', 'high', 'very_high'])

    print(f"\n   Feature Engineering Complete! Total Columns: {len(df.columns)}")
    return df

df_engineered = engineer_features_nb(transactions_df, customer_df)
print(f"\nEngineered Dataset Shape: {df_engineered.shape}")

# ============================================================
# STEP 4: Feature Preparation for Different NB Variants
# ============================================================
def prepare_features_for_nb(df):
    print("\nPreparing Features for Naive Bayes Variants...")

    continuous_features = [
        'amt_original', 'amt_log', 'amt_ratio', 'amt_zscore',
        'distance_km', 'time_since_last_hours', 'velocity',
        'merchant_fraud_rate', 'category_fraud_rate', 'hour_fraud_rate',
        'cust_amt_mean', 'cust_amt_std', 'cust_trans_count',
        'category_usage', 'merchant_usage', 'trans_sequence',
        'combined_risk_score'
    ]

    binary_features = [
        'is_weekend', 'is_late_night', 'is_business_hours', 'is_rush_hour',
        'is_amount_anomaly', 'is_high_amount', 'is_very_high_amount', 'is_round_amount',
        'is_local', 'is_distant', 'is_very_distant',
        'is_first_trans', 'is_quick_succession', 'is_very_quick', 'is_impossible_velocity',
        'is_top_category', 'is_new_category', 'is_new_merchant', 'is_repeat_merchant'
    ]

    categorical_features = [
        'category', 'gender', 'time_category', 'amt_category', 'amt_ratio_category',
        'distance_category', 'trans_frequency_category', 'time_gap_category',
        'merchant_usage_category', 'merchant_risk', 'category_risk', 'hour_risk',
        'combined_risk_category', 'merchant_region'
    ]

    print(f"   Continuous features: {len(continuous_features)}")
    print(f"   Binary features: {len(binary_features)}")
    print(f"   Categorical features: {len(categorical_features)}")

    for feat in continuous_features:
        if feat in df.columns:
            df[feat] = df[feat].fillna(df[feat].median())
    for feat in binary_features:
        if feat in df.columns:
            df[feat] = df[feat].fillna(0)
    for feat in categorical_features:
        if feat in df.columns:
            if hasattr(df[feat], 'cat'):
                df[feat] = df[feat].cat.add_categories('unknown').fillna('unknown')
            else:
                df[feat] = df[feat].fillna('unknown')

    # 1. GaussianNB (continuous + binary + encoded categorical)
    X_gaussian = df[continuous_features + binary_features].copy()

    # 2. BernoulliNB (binary only)
    X_bernoulli = df[binary_features].copy()

    # 3. MultinomialNB / ComplementNB (continuous + binary + encoded categorical, non-negative)
    X_multinomial = df[continuous_features + binary_features].copy()

    for cat_feat in categorical_features:
        if cat_feat in df.columns:
            dummies = pd.get_dummies(df[cat_feat], prefix=cat_feat, drop_first=True)
            X_gaussian = pd.concat([X_gaussian, dummies], axis=1)
            X_multinomial = pd.concat([X_multinomial, dummies], axis=1)

    # For MultinomialNB, ensure all values are non-negative
    for col in X_multinomial.columns:
        if X_multinomial[col].min() < 0:
            X_multinomial[col] = X_multinomial[col] - X_multinomial[col].min()

    y = df['is_fraud'].values

    print(f"\n   Feature Sets Created:")
    print(f"      GaussianNB features: {X_gaussian.shape[1]}")
    print(f"      BernoulliNB features: {X_bernoulli.shape[1]}")
    print(f"      MultinomialNB features: {X_multinomial.shape[1]}")

    return {
        'gaussian': (X_gaussian, X_gaussian.columns.tolist()),
        'bernoulli': (X_bernoulli, X_bernoulli.columns.tolist()),
        'multinomial': (X_multinomial, X_multinomial.columns.tolist())
    }, y

feature_sets, y = prepare_features_for_nb(df_engineered)

print(f"\nDataset Summary:")
print(f"   Total samples: {len(y)}")
print(f"   Fraud cases: {sum(y)} ({sum(y)/len(y)*100:.2f}%)")
print(f"   Normal cases: {sum(y==0)} ({sum(y==0)/len(y)*100:.2f}%)")

# ============================================================
# STEP 5: Train-Test Split
# ============================================================
print("\nSplitting Data...")

splits = {}
for variant_name, (X, features) in feature_sets.items():
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )
    splits[variant_name] = {
        'X_train': X_train, 'X_test': X_test,
        'y_train': y_train, 'y_test': y_test,
        'features': features
    }
    print(f"   {variant_name.capitalize()}: Train={len(X_train)}, Test={len(X_test)}")

X_train = splits['gaussian']['X_train']
X_test = splits['gaussian']['X_test']
y_train = splits['gaussian']['y_train']
y_test = splits['gaussian']['y_test']

# ============================================================
# STEP 6: Handle Class Imbalance
# ============================================================
print("\n" + "="*80)
print("HANDLING CLASS IMBALANCE")
print("="*80)

print(f"\nOriginal Training Distribution:")
print(f"   Normal: {sum(y_train==0)}")
print(f"   Fraud: {sum(y_train==1)}")
print(f"   Ratio: 1:{sum(y_train==0)/sum(y_train==1):.1f}")

smote = SMOTE(sampling_strategy=0.5, random_state=42)
X_train_smote, y_train_smote = smote.fit_resample(X_train, y_train)

under = RandomUnderSampler(sampling_strategy=0.67, random_state=42)
X_train_balanced, y_train_balanced = under.fit_resample(X_train_smote, y_train_smote)

print(f"\nBalanced Distribution:")
print(f"   Normal: {sum(y_train_balanced==0)}")
print(f"   Fraud: {sum(y_train_balanced==1)}")
print(f"   Total: {len(X_train_balanced)}")

# Prepare balanced sets for other variants
balanced_splits = {}
for variant_name in ['bernoulli', 'multinomial']:
    X_tr = splits[variant_name]['X_train']
    y_tr = splits[variant_name]['y_train']
    X_smote, y_smote = smote.fit_resample(X_tr, y_tr)
    X_bal, y_bal = under.fit_resample(X_smote, y_smote)
    balanced_splits[variant_name] = {
        'X_train_balanced': X_bal, 'y_train_balanced': y_bal,
        'X_test': splits[variant_name]['X_test'],
        'y_test': splits[variant_name]['y_test']
    }

# ============================================================
# STEP 7: Train All Naive Bayes Variants
# ============================================================
print("\n" + "="*80)
print("TRAINING ALL NAIVE BAYES VARIANTS")
print("="*80)

models = {}
results = {}

# 1. GAUSSIAN NAIVE BAYES
print("\n1. GAUSSIAN NAIVE BAYES")
print("   Best for: Continuous features with Gaussian distribution")
start_time = time.time()
gnb = GaussianNB()
gnb.fit(X_train_balanced, y_train_balanced)
train_time = time.time() - start_time
print(f"   Trained in {train_time:.3f} seconds!")
models['gaussian'] = gnb

# 2. COMPLEMENT NAIVE BAYES
print("\n2. COMPLEMENT NAIVE BAYES")
print("   Best for: Imbalanced datasets with count features")
start_time = time.time()
cnb = ComplementNB()
cnb.fit(balanced_splits['multinomial']['X_train_balanced'],
        balanced_splits['multinomial']['y_train_balanced'])
train_time = time.time() - start_time
print(f"   Trained in {train_time:.3f} seconds!")
models['complement'] = cnb

# 3. MULTINOMIAL NAIVE BAYES
print("\n3. MULTINOMIAL NAIVE BAYES")
print("   Best for: Count/frequency features")
start_time = time.time()
mnb = MultinomialNB()
mnb.fit(balanced_splits['multinomial']['X_train_balanced'],
        balanced_splits['multinomial']['y_train_balanced'])
train_time = time.time() - start_time
print(f"   Trained in {train_time:.3f} seconds!")
models['multinomial'] = mnb

# 4. BERNOULLI NAIVE BAYES
print("\n4. BERNOULLI NAIVE BAYES")
print("   Best for: Binary/boolean features only")
start_time = time.time()
bnb = BernoulliNB()
bnb.fit(balanced_splits['bernoulli']['X_train_balanced'],
        balanced_splits['bernoulli']['y_train_balanced'])
train_time = time.time() - start_time
print(f"   Trained in {train_time:.3f} seconds!")
models['bernoulli'] = bnb

print("\nAll 4 Naive Bayes variants trained successfully!")

# ============================================================
# STEP 8: Evaluate All Models
# ============================================================
def evaluate_nb_model(model, X_test, y_test, model_name):
    print(f"\n{'='*80}")
    print(f"{model_name.upper()} - EVALUATION")
    print(f"{'='*80}")

    y_pred = model.predict(X_test)
    y_proba = model.predict_proba(X_test)[:, 1]

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
    print(f"   Precision:    {precision:.4f}")
    print(f"   Recall:       {recall:.4f}")
    print(f"   F1-Score:     {f1:.4f}")
    print(f"   Specificity:  {specificity:.4f}")
    print(f"   ROC-AUC:      {roc_auc:.4f}")
    print(f"   PR-AUC:       {pr_auc:.4f}")

    print(f"\nBusiness Metrics:")
    fpr_val = fp / (fp + tn) * 100
    fnr_val = fn / (fn + tp) * 100 if (fn + tp) > 0 else 0
    print(f"   False Positive Rate: {fpr_val:.2f}%")
    print(f"   False Negative Rate: {fnr_val:.2f}%")
    print(f"   Fraud Detection Rate: {recall*100:.1f}%")

    return {
        'accuracy': accuracy, 'precision': precision, 'recall': recall,
        'f1': f1, 'roc_auc': roc_auc, 'pr_auc': pr_auc,
        'y_pred': y_pred, 'y_proba': y_proba
    }

results['gaussian'] = evaluate_nb_model(models['gaussian'], X_test, y_test, "Gaussian Naive Bayes")

results['complement'] = evaluate_nb_model(
    models['complement'],
    balanced_splits['multinomial']['X_test'],
    balanced_splits['multinomial']['y_test'],
    "Complement Naive Bayes"
)

results['multinomial'] = evaluate_nb_model(
    models['multinomial'],
    balanced_splits['multinomial']['X_test'],
    balanced_splits['multinomial']['y_test'],
    "Multinomial Naive Bayes"
)

results['bernoulli'] = evaluate_nb_model(
    models['bernoulli'],
    balanced_splits['bernoulli']['X_test'],
    balanced_splits['bernoulli']['y_test'],
    "Bernoulli Naive Bayes"
)

# ============================================================
# STEP 9: Hyperparameter Tuning for Gaussian NB
# ============================================================
print("\n" + "="*80)
print("HYPERPARAMETER TUNING - GAUSSIAN NAIVE BAYES")
print("="*80)

print("\nTuning var_smoothing parameter...")

param_grid = {
    'var_smoothing': np.logspace(-12, -6, 20)
}

cv_strategy = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)

grid_search = GridSearchCV(
    GaussianNB(), param_grid, cv=cv_strategy,
    scoring='roc_auc', n_jobs=-1, verbose=1
)

print("\nRunning Grid Search...")
start_time = time.time()
grid_search.fit(X_train_balanced, y_train_balanced)
search_time = time.time() - start_time

print(f"\nGrid Search Complete in {search_time:.1f} seconds!")
print(f"\nBest Parameter:")
print(f"   var_smoothing: {grid_search.best_params_['var_smoothing']:.2e}")
print(f"\nCross-Validation Results:")
print(f"   Best CV ROC-AUC: {grid_search.best_score_:.4f}")
print(f"   Mean CV Score: {grid_search.cv_results_['mean_test_score'].mean():.4f}")

best_gnb = grid_search.best_estimator_

print("\n" + "="*80)
print("OPTIMIZED GAUSSIAN NAIVE BAYES - EVALUATION")
print("="*80)

optimized_results = evaluate_nb_model(best_gnb, X_test, y_test, "Optimized Gaussian NB")

print(f"\nIMPROVEMENT OVER BASELINE GAUSSIAN NB:")
print(f"   ROC-AUC:  {results['gaussian']['roc_auc']:.4f} -> {optimized_results['roc_auc']:.4f} "
      f"({(optimized_results['roc_auc']-results['gaussian']['roc_auc'])*100:+.2f}%)")
print(f"   PR-AUC:   {results['gaussian']['pr_auc']:.4f} -> {optimized_results['pr_auc']:.4f} "
      f"({(optimized_results['pr_auc']-results['gaussian']['pr_auc'])*100:+.2f}%)")
print(f"   F1-Score: {results['gaussian']['f1']:.4f} -> {optimized_results['f1']:.4f} "
      f"({(optimized_results['f1']-results['gaussian']['f1'])*100:+.2f}%)")

# ============================================================
# STEP 10: Comparison Visualization
# ============================================================
fig, axes = plt.subplots(2, 2, figsize=(15, 12))

# ROC Curves
ax = axes[0, 0]
colors = ['blue', 'green', 'red', 'orange']
model_names_list = ['gaussian', 'complement', 'multinomial', 'bernoulli']

for name, color in zip(model_names_list, colors):
    if name in results:
        fpr, tpr, _ = roc_curve(y_test, results[name]['y_proba'])
        roc_auc_val = auc(fpr, tpr)
        ax.plot(fpr, tpr, color=color, lw=2, label=f'{name.capitalize()} (AUC={roc_auc_val:.3f})')

ax.plot([0, 1], [0, 1], 'k--', lw=2, label='Random')
ax.set_xlabel('False Positive Rate', fontsize=11)
ax.set_ylabel('True Positive Rate', fontsize=11)
ax.set_title('ROC Curves - Naive Bayes Variants', fontsize=13, fontweight='bold')
ax.legend(loc='lower right')
ax.grid(True, alpha=0.3)

# PR Curves
ax = axes[0, 1]
for name, color in zip(model_names_list, colors):
    if name in results:
        prec_c, rec_c, _ = precision_recall_curve(y_test, results[name]['y_proba'])
        pr_auc_val = auc(rec_c, prec_c)
        ax.plot(rec_c, prec_c, color=color, lw=2, label=f'{name.capitalize()} (AUC={pr_auc_val:.3f})')

ax.axhline(y=y_test.mean(), color='k', linestyle='--', lw=2, label=f'Baseline ({y_test.mean():.3f})')
ax.set_xlabel('Recall', fontsize=11)
ax.set_ylabel('Precision', fontsize=11)
ax.set_title('Precision-Recall Curves', fontsize=13, fontweight='bold')
ax.legend(loc='best')
ax.grid(True, alpha=0.3)

# Performance Metrics Comparison
ax = axes[1, 0]
metrics = ['roc_auc', 'pr_auc', 'f1', 'precision', 'recall']
metric_labels = ['ROC-AUC', 'PR-AUC', 'F1', 'Precision', 'Recall']
x = np.arange(len(metrics))
width = 0.2

for i, (name, color) in enumerate(zip(model_names_list, colors)):
    if name in results:
        values = [results[name][m] for m in metrics]
        ax.bar(x + i*width, values, width, label=name.capitalize(), color=color, alpha=0.8)

ax.set_xlabel('Metrics', fontsize=11)
ax.set_ylabel('Score', fontsize=11)
ax.set_title('Performance Metrics Comparison', fontsize=13, fontweight='bold')
ax.set_xticks(x + width * 1.5)
ax.set_xticklabels(metric_labels)
ax.legend()
ax.grid(True, alpha=0.3, axis='y')
ax.set_ylim([0, 1])

# Summary Table
ax = axes[1, 1]
ax.axis('off')
table_data = []
for name in model_names_list:
    if name in results:
        table_data.append([
            name.capitalize(),
            f"{results[name]['roc_auc']:.4f}",
            f"{results[name]['pr_auc']:.4f}",
            f"{results[name]['f1']:.4f}",
            f"{results[name]['recall']:.4f}"
        ])

table = ax.table(cellText=table_data,
                colLabels=['Model', 'ROC-AUC', 'PR-AUC', 'F1', 'Recall'],
                cellLoc='center', loc='center', bbox=[0, 0, 1, 1])
table.auto_set_font_size(False)
table.set_fontsize(10)
table.scale(1, 2)

for i in range(5):
    table[(0, i)].set_facecolor('#4472C4')
    table[(0, i)].set_text_props(weight='bold', color='white')
for i in range(1, len(table_data) + 1):
    for j in range(5):
        if i % 2 == 0:
            table[(i, j)].set_facecolor('#F2F2F2')

ax.set_title('Model Performance Summary', fontsize=13, fontweight='bold', pad=20)

plt.tight_layout()
plt.savefig(os.path.join(output_dir, 'naive_bayes_comparison.png'), dpi=300, bbox_inches='tight')
print(f"\nComparison plots saved to output/naive_bayes_comparison.png")
plt.close()

# ============================================================
# STEP 11: Feature Importance Analysis
# ============================================================
print("\n" + "="*80)
print("FEATURE IMPORTANCE ANALYSIS")
print("="*80)

print("\nNote: Naive Bayes uses mean difference between classes as importance proxy\n")

feature_names_gaussian = splits['gaussian']['features']

fraud_mask = y_train_balanced == 1
normal_mask = y_train_balanced == 0

fraud_means = X_train_balanced[fraud_mask].mean()
normal_means = X_train_balanced[normal_mask].mean()

mean_diff = np.abs(fraud_means - normal_means)
mean_diff_sorted = mean_diff.sort_values(ascending=False)

print("Top 20 Most Discriminative Features (by mean difference):")
print("\n" + "-"*70)
print(f"{'Feature':<40} {'Mean Diff':<15} {'Fraud Mean':<15}")
print("-"*70)

for idx, (feature, diff) in enumerate(mean_diff_sorted.head(20).items(), 1):
    fraud_mean = fraud_means[feature]
    print(f"{idx:2d}. {feature:<37} {diff:>10.4f}    {fraud_mean:>10.4f}")

feature_importance = pd.DataFrame({
    'feature': mean_diff.index,
    'mean_difference': mean_diff.values,
    'fraud_mean': fraud_means.values,
    'normal_mean': normal_means.values
}).sort_values('mean_difference', ascending=False)

feature_importance.to_csv(os.path.join(output_dir, 'naive_bayes_feature_importance.csv'), index=False)
print(f"\nFeature importance saved to output/naive_bayes_feature_importance.csv")

# ============================================================
# STEP 12: Threshold Optimization
# ============================================================
print("\n" + "="*80)
print("THRESHOLD OPTIMIZATION")
print("="*80)

thresholds = np.arange(0.05, 0.95, 0.05)
metrics_at_threshold = []

for threshold in thresholds:
    y_pred_t = (optimized_results['y_proba'] >= threshold).astype(int)
    prec = precision_score(y_test, y_pred_t, zero_division=0)
    rec = recall_score(y_test, y_pred_t, zero_division=0)
    f1_val = f1_score(y_test, y_pred_t, zero_division=0)
    metrics_at_threshold.append({
        'threshold': threshold, 'precision': prec, 'recall': rec, 'f1': f1_val
    })

metrics_df = pd.DataFrame(metrics_at_threshold)
optimal_idx = metrics_df['f1'].idxmax()
optimal_threshold = metrics_df.loc[optimal_idx, 'threshold']
optimal_f1 = metrics_df.loc[optimal_idx, 'f1']

fig, ax = plt.subplots(figsize=(12, 6))
ax.plot(metrics_df['threshold'], metrics_df['precision'], 'b-o', label='Precision', linewidth=2)
ax.plot(metrics_df['threshold'], metrics_df['recall'], 'g-s', label='Recall', linewidth=2)
ax.plot(metrics_df['threshold'], metrics_df['f1'], 'r-^', label='F1-Score', linewidth=2)
ax.axvline(optimal_threshold, color='purple', linestyle='--', linewidth=2,
          label=f'Optimal Threshold = {optimal_threshold:.2f}')
ax.set_xlabel('Classification Threshold', fontsize=12)
ax.set_ylabel('Score', fontsize=12)
ax.set_title('Threshold Optimization - Naive Bayes', fontsize=14, fontweight='bold')
ax.legend(loc='best', fontsize=10)
ax.grid(True, alpha=0.3)
ax.set_ylim([0, 1])

plt.tight_layout()
plt.savefig(os.path.join(output_dir, 'naive_bayes_threshold_optimization.png'), dpi=300, bbox_inches='tight')
print(f"   Threshold plot saved to output/naive_bayes_threshold_optimization.png")
plt.close()

print(f"\n   Optimal Threshold: {optimal_threshold:.2f}")
print(f"   F1-Score: {optimal_f1:.4f}")
print(f"   Precision: {metrics_df.loc[optimal_idx, 'precision']:.4f}")
print(f"   Recall: {metrics_df.loc[optimal_idx, 'recall']:.4f}")

# ============================================================
# STEP 13: Final Model Comparison
# ============================================================
print("\n" + "="*80)
print("FINAL MODEL COMPARISON")
print("="*80)

comparison_data = []
for name in ['gaussian', 'complement', 'multinomial', 'bernoulli']:
    if name in results:
        comparison_data.append({
            'Model': name.capitalize() + ' NB',
            'ROC-AUC': results[name]['roc_auc'],
            'PR-AUC': results[name]['pr_auc'],
            'F1-Score': results[name]['f1'],
            'Precision': results[name]['precision'],
            'Recall': results[name]['recall']
        })

comparison_data.append({
    'Model': 'Optimized Gaussian NB',
    'ROC-AUC': optimized_results['roc_auc'],
    'PR-AUC': optimized_results['pr_auc'],
    'F1-Score': optimized_results['f1'],
    'Precision': optimized_results['precision'],
    'Recall': optimized_results['recall']
})

comparison_df = pd.DataFrame(comparison_data)

print("\nPerformance Comparison:")
print(comparison_df.to_string(index=False))

best_model_idx = comparison_df['ROC-AUC'].idxmax()
best_model_name = comparison_df.loc[best_model_idx, 'Model']

print(f"\nBEST PERFORMING MODEL: {best_model_name}")
print(f"   ROC-AUC: {comparison_df.loc[best_model_idx, 'ROC-AUC']:.4f}")
print(f"   PR-AUC: {comparison_df.loc[best_model_idx, 'PR-AUC']:.4f}")

comparison_df.to_csv(os.path.join(output_dir, 'naive_bayes_comparison.csv'), index=False)
print(f"\nComparison saved to output/naive_bayes_comparison.csv")

# ============================================================
# STEP 14: Save Models and Artifacts
# ============================================================
print("\n" + "="*80)
print("SAVING MODELS AND ARTIFACTS")
print("="*80)

for name, model in models.items():
    filename = f'naive_bayes_{name}_model.pkl'
    with open(os.path.join(output_dir, filename), 'wb') as f:
        pickle.dump(model, f)
    print(f"   {name.capitalize()} NB saved to output/{filename}")

with open(os.path.join(output_dir, 'naive_bayes_optimized_model.pkl'), 'wb') as f:
    pickle.dump(best_gnb, f)
print("   Optimized Gaussian NB saved to output/naive_bayes_optimized_model.pkl")

for variant_name in ['gaussian', 'bernoulli', 'multinomial']:
    features = splits[variant_name]['features']
    filename = f'naive_bayes_{variant_name}_features.pkl'
    with open(os.path.join(output_dir, filename), 'wb') as f:
        pickle.dump(features, f)
    print(f"   {variant_name.capitalize()} features saved to output/{filename}")

with open(os.path.join(output_dir, 'naive_bayes_optimal_threshold.pkl'), 'wb') as f:
    pickle.dump(optimal_threshold, f)
print("   Optimal threshold saved to output/naive_bayes_optimal_threshold.pkl")

results_summary = {
    'model_type': 'Naive Bayes (Multiple Variants)',
    'training_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
    'best_model': best_model_name,
    'best_parameters': {
        'var_smoothing': grid_search.best_params_['var_smoothing']
    },
    'dataset_info': {
        'total_samples': len(df_engineered),
        'train_samples': len(X_train_balanced),
        'test_samples': len(X_test),
        'n_features_gaussian': len(splits['gaussian']['features']),
        'fraud_rate': float(y.mean())
    },
    'performance': {
        variant: {
            'roc_auc': results[variant]['roc_auc'],
            'pr_auc': results[variant]['pr_auc'],
            'f1': results[variant]['f1'],
            'precision': results[variant]['precision'],
            'recall': results[variant]['recall']
        } for variant in ['gaussian', 'complement', 'multinomial', 'bernoulli']
    },
    'optimized_performance': {
        'roc_auc': optimized_results['roc_auc'],
        'pr_auc': optimized_results['pr_auc'],
        'f1': optimized_results['f1']
    },
    'optimal_threshold': float(optimal_threshold)
}

with open(os.path.join(output_dir, 'naive_bayes_results_summary.pkl'), 'wb') as f:
    pickle.dump(results_summary, f)
print("   Results summary saved to output/naive_bayes_results_summary.pkl")

print("\n" + "="*80)
print("NAIVE BAYES TRAINING COMPLETE!")
print("="*80)

print(f"\nGenerated Files in output/:")
print(f"   1. naive_bayes_gaussian_model.pkl")
print(f"   2. naive_bayes_complement_model.pkl")
print(f"   3. naive_bayes_multinomial_model.pkl")
print(f"   4. naive_bayes_bernoulli_model.pkl")
print(f"   5. naive_bayes_optimized_model.pkl (recommended)")
print(f"   6. naive_bayes_*_features.pkl (3 files)")
print(f"   7. naive_bayes_optimal_threshold.pkl")
print(f"   8. naive_bayes_results_summary.pkl")
print(f"   9. naive_bayes_comparison.csv")
print(f"   10. naive_bayes_feature_importance.csv")
print(f"   11. naive_bayes_comparison.png")
print(f"   12. naive_bayes_threshold_optimization.png")

print(f"\nBest Model: {best_model_name}")
print(f"   ROC-AUC: {comparison_df.loc[best_model_idx, 'ROC-AUC']:.4f}")
print(f"   PR-AUC: {comparison_df.loc[best_model_idx, 'PR-AUC']:.4f}")
print(f"   F1-Score: {comparison_df.loc[best_model_idx, 'F1-Score']:.4f}")
print(f"   Training Time: < 1 minute")

print("\n" + "="*80)
