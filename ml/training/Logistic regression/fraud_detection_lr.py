import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split, StratifiedKFold, GridSearchCV
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    classification_report, confusion_matrix, roc_auc_score,
    precision_recall_curve, auc, roc_curve, f1_score,
    recall_score, precision_score
)
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')
import pickle
import os

project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
data_dir = os.path.join(project_root, 'data')
output_dir = os.path.join(project_root, 'training', 'output')
os.makedirs(output_dir, exist_ok=True)

np.random.seed(42)

print("=" * 80)
print("FRAUD DETECTION - LOGISTIC REGRESSION MODEL")
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
# STEP 2: Quick EDA
# ============================================================
print("\nMissing Values Check:")
print(f"   Customer data: {customer_df.isnull().sum().sum()} missing values")
print(f"   Transaction data: {transactions_df.isnull().sum().sum()} missing values")

print("\nFraud Statistics:")
fraud_stats = transactions_df.groupby('is_fraud')['amt'].describe()
print(fraud_stats)

# ============================================================
# STEP 3: Feature Engineering
# ============================================================
def engineer_features(trans_df, cust_df):
    print("\nEngineering Features...")

    df = trans_df.merge(cust_df, on='cc_num', how='left', suffixes=('_trans', '_cust'))

    # TEMPORAL FEATURES
    print("   Creating temporal features...")
    df['trans_datetime'] = pd.to_datetime(df['trans_date'])
    df['trans_time_obj'] = pd.to_datetime(df['trans_time'], format='%H:%M:%S')
    df['hour'] = df['trans_time_obj'].dt.hour
    df['day_of_week'] = df['trans_datetime'].dt.dayofweek
    df['day_of_month'] = df['trans_datetime'].dt.day
    df['month'] = df['trans_datetime'].dt.month
    df['is_weekend'] = (df['day_of_week'] >= 5).astype(int)
    df['time_of_day'] = pd.cut(df['hour'],
                                bins=[0, 6, 12, 18, 24],
                                labels=['night', 'morning', 'afternoon', 'evening'])
    df['is_high_risk_hour'] = ((df['hour'] >= 23) | (df['hour'] <= 5)).astype(int)

    # AMOUNT FEATURES
    print("   Creating amount-based features...")
    df['amt_log'] = np.log1p(df['amt'])
    customer_amt_stats = df.groupby('cc_num')['amt'].agg([
        'mean', 'std', 'min', 'max', 'median'
    ]).reset_index()
    customer_amt_stats.columns = ['cc_num', 'cust_amt_mean', 'cust_amt_std',
                                   'cust_amt_min', 'cust_amt_max', 'cust_amt_median']
    df = df.merge(customer_amt_stats, on='cc_num', how='left')
    df['amt_ratio_to_avg'] = df['amt'] / (df['cust_amt_mean'] + 1)
    df['amt_deviation'] = (df['amt'] - df['cust_amt_mean']) / (df['cust_amt_std'] + 1)
    df['amt_above_median'] = (df['amt'] > df['cust_amt_median']).astype(int)

    # GEOSPATIAL FEATURES
    print("   Creating geospatial features...")
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
    df['is_local_transaction'] = (df['distance_from_home'] < 10).astype(int)
    df['is_distant_transaction'] = (df['distance_from_home'] > 100).astype(int)

    # BEHAVIORAL FEATURES
    print("   Creating behavioral features...")
    df = df.sort_values(['cc_num', 'unix_time']).reset_index(drop=True)
    df['customer_trans_count'] = df.groupby('cc_num').cumcount() + 1
    df['time_since_last_trans'] = df.groupby('cc_num')['unix_time'].diff()
    df['time_since_last_trans'] = df['time_since_last_trans'].fillna(0)
    df['time_since_last_trans_hours'] = df['time_since_last_trans'] / 3600
    df['is_quick_succession'] = (df['time_since_last_trans'] < 300).astype(int)

    # CATEGORY FEATURES
    print("   Creating category features...")
    customer_category_counts = df.groupby(['cc_num', 'category']).size().reset_index(name='category_count')
    df = df.merge(customer_category_counts, on=['cc_num', 'category'], how='left')
    customer_top_category = df.groupby('cc_num')['category'].agg(
        lambda x: x.mode()[0] if len(x.mode()) > 0 else x.iloc[0]
    ).reset_index()
    customer_top_category.columns = ['cc_num', 'customer_top_category']
    df = df.merge(customer_top_category, on='cc_num', how='left')
    df['is_typical_category'] = (df['category'] == df['customer_top_category']).astype(int)

    # MERCHANT FEATURES
    print("   Creating merchant features...")
    merchant_customer_count = df.groupby(['cc_num', 'merchant']).size().reset_index(name='merchant_usage_count')
    df = df.merge(merchant_customer_count, on=['cc_num', 'merchant'], how='left')
    df['is_new_merchant'] = (df['merchant_usage_count'] == 1).astype(int)

    # AGGREGATE RISK FEATURES
    print("   Creating risk features...")
    merchant_fraud_rate = df.groupby('merchant')['is_fraud'].mean().reset_index()
    merchant_fraud_rate.columns = ['merchant', 'merchant_fraud_rate']
    df = df.merge(merchant_fraud_rate, on='merchant', how='left')
    df['merchant_fraud_rate'] = df['merchant_fraud_rate'].fillna(df['is_fraud'].mean())

    category_fraud_rate = df.groupby('category')['is_fraud'].mean().reset_index()
    category_fraud_rate.columns = ['category', 'category_fraud_rate']
    df = df.merge(category_fraud_rate, on='category', how='left')

    print(f"\n   Feature Engineering Complete! Total columns: {len(df.columns)}")
    return df

df_engineered = engineer_features(transactions_df, customer_df)

# ============================================================
# STEP 4: Feature Selection and Preparation
# ============================================================
def prepare_features(df):
    print("\nPreparing Features for Modeling...")

    numerical_features = [
        'amt', 'amt_log', 'hour', 'day_of_week', 'day_of_month', 'month',
        'is_weekend', 'is_high_risk_hour', 'amt_ratio_to_avg', 'amt_deviation',
        'amt_above_median', 'distance_from_home', 'is_local_transaction',
        'is_distant_transaction', 'customer_trans_count', 'time_since_last_trans_hours',
        'is_quick_succession', 'category_count', 'is_typical_category',
        'merchant_usage_count', 'is_new_merchant', 'merchant_fraud_rate',
        'category_fraud_rate'
    ]

    categorical_features = ['category', 'gender', 'time_of_day']

    print(f"   Numerical features: {len(numerical_features)}")
    print(f"   Categorical features: {len(categorical_features)}")

    X = df[numerical_features].copy()

    for cat_feature in categorical_features:
        if cat_feature in df.columns:
            dummies = pd.get_dummies(df[cat_feature], prefix=cat_feature, drop_first=True)
            X = pd.concat([X, dummies], axis=1)

    y = df['is_fraud'].values
    X = X.fillna(X.median())

    print(f"\n   Final Feature Matrix Shape: {X.shape}")
    print(f"   Class Distribution:")
    print(f"      Normal: {sum(y==0)} ({sum(y==0)/len(y)*100:.2f}%)")
    print(f"      Fraud: {sum(y==1)} ({sum(y==1)/len(y)*100:.2f}%)")

    return X, y, X.columns.tolist()

X, y, feature_names = prepare_features(df_engineered)

# ============================================================
# STEP 5: Train-Test Split
# ============================================================
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42, stratify=y
)

print(f"\nData Split:")
print(f"   Training set: {len(X_train)} samples")
print(f"   Test set: {len(X_test)} samples")
print(f"   Training fraud rate: {y_train.mean()*100:.2f}%")
print(f"   Test fraud rate: {y_test.mean()*100:.2f}%")

# ============================================================
# STEP 6: Feature Scaling
# ============================================================
scaler = StandardScaler()
X_train_scaled = scaler.fit_transform(X_train)
X_test_scaled = scaler.transform(X_test)

print("\nFeature Scaling Applied (StandardScaler)")

# ============================================================
# STEP 7: Handle Class Imbalance - SMOTE + Undersampling
# ============================================================
from imblearn.over_sampling import SMOTE
from imblearn.under_sampling import RandomUnderSampler

print("\nHandling Class Imbalance...")

smote = SMOTE(sampling_strategy=0.5, random_state=42)
under = RandomUnderSampler(sampling_strategy=0.67, random_state=42)

X_train_resampled, y_train_resampled = smote.fit_resample(X_train_scaled, y_train)
X_train_resampled, y_train_resampled = under.fit_resample(X_train_resampled, y_train_resampled)

print(f"   Original training set: Normal={sum(y_train==0)}, Fraud={sum(y_train==1)}")
print(f"   After resampling: Normal={sum(y_train_resampled==0)}, Fraud={sum(y_train_resampled==1)}")
print(f"   New training set size: {len(X_train_resampled)} samples")
print(f"   New fraud rate: {y_train_resampled.mean()*100:.2f}%")

# ============================================================
# STEP 8: Train Baseline Logistic Regression
# ============================================================
print("\n" + "="*80)
print("TRAINING BASELINE LOGISTIC REGRESSION MODEL")
print("="*80)

lr_baseline = LogisticRegression(
    random_state=42, max_iter=1000, class_weight='balanced', solver='lbfgs'
)
lr_baseline.fit(X_train_resampled, y_train_resampled)

y_train_pred = lr_baseline.predict(X_train_scaled)
y_test_pred = lr_baseline.predict(X_test_scaled)
y_test_proba = lr_baseline.predict_proba(X_test_scaled)[:, 1]

print("\nBaseline Model Trained!")

# ============================================================
# STEP 9: Evaluate Model
# ============================================================
def evaluate_model(y_true, y_pred, y_proba, dataset_name="Test"):
    print(f"\n{'='*80}")
    print(f"{dataset_name.upper()} SET EVALUATION")
    print(f"{'='*80}")

    cm = confusion_matrix(y_true, y_pred)
    print("\nConfusion Matrix:")
    print(f"                 Predicted")
    print(f"               Normal  Fraud")
    print(f"Actual Normal   {cm[0,0]:5d}  {cm[0,1]:5d}")
    print(f"       Fraud    {cm[1,0]:5d}  {cm[1,1]:5d}")

    tn, fp, fn, tp = cm.ravel()
    accuracy = (tp + tn) / (tp + tn + fp + fn)
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0
    f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0
    specificity = tn / (tn + fp) if (tn + fp) > 0 else 0
    roc_auc = roc_auc_score(y_true, y_proba)
    precision_curve, recall_curve, _ = precision_recall_curve(y_true, y_proba)
    pr_auc = auc(recall_curve, precision_curve)

    print(f"\nPerformance Metrics:")
    print(f"   Accuracy:             {accuracy:.4f}")
    print(f"   Precision:            {precision:.4f}  (Of flagged transactions, {precision*100:.1f}% were actually fraud)")
    print(f"   Recall (Sensitivity): {recall:.4f}  (Caught {recall*100:.1f}% of all fraud cases)")
    print(f"   F1-Score:             {f1:.4f}")
    print(f"   Specificity:          {specificity:.4f}  (Correctly identified {specificity*100:.1f}% of normal transactions)")
    print(f"   ROC-AUC Score:        {roc_auc:.4f}")
    print(f"   PR-AUC Score:         {pr_auc:.4f}  (Most important for imbalanced data)")

    print(f"\nBusiness Metrics:")
    print(f"   False Positive Rate: {(fp/(fp+tn)*100):.2f}%  (Normal transactions flagged)")
    print(f"   False Negative Rate: {(fn/(fn+tp)*100):.2f}%  (Fraud cases missed)")
    print(f"   True Positives:      {tp} fraud cases caught")
    print(f"   False Negatives:     {fn} fraud cases missed")

    return {
        'accuracy': accuracy, 'precision': precision, 'recall': recall,
        'f1': f1, 'roc_auc': roc_auc, 'pr_auc': pr_auc, 'confusion_matrix': cm
    }

baseline_metrics = evaluate_model(y_test, y_test_pred, y_test_proba, "Baseline Test")

# ============================================================
# STEP 10: Hyperparameter Tuning with GridSearchCV
# ============================================================
print("\n" + "="*80)
print("HYPERPARAMETER TUNING WITH GRID SEARCH")
print("="*80)

param_grid = {
    'C': [0.001, 0.01, 0.1, 1, 10, 100],
    'penalty': ['l1', 'l2'],
    'solver': ['liblinear', 'saga'],
    'class_weight': ['balanced', None],
    'max_iter': [1000]
}

cv_strategy = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)

grid_search = GridSearchCV(
    LogisticRegression(random_state=42),
    param_grid, cv=cv_strategy, scoring='roc_auc', n_jobs=-1, verbose=1
)

print("\nRunning Grid Search...")
grid_search.fit(X_train_resampled, y_train_resampled)

print(f"\nGrid Search Complete!")
print(f"\nBest Parameters:")
for param, value in grid_search.best_params_.items():
    print(f"   {param}: {value}")
print(f"\nBest Cross-Validation ROC-AUC Score: {grid_search.best_score_:.4f}")

best_lr_model = grid_search.best_estimator_

# ============================================================
# STEP 11: Evaluate Optimized Model
# ============================================================
y_test_pred_opt = best_lr_model.predict(X_test_scaled)
y_test_proba_opt = best_lr_model.predict_proba(X_test_scaled)[:, 1]

print("\n" + "="*80)
print("OPTIMIZED MODEL PERFORMANCE")
print("="*80)

optimized_metrics = evaluate_model(y_test, y_test_pred_opt, y_test_proba_opt, "Optimized Test")

print(f"\nIMPROVEMENT OVER BASELINE:")
print(f"   ROC-AUC:  {baseline_metrics['roc_auc']:.4f} -> {optimized_metrics['roc_auc']:.4f} ({(optimized_metrics['roc_auc']-baseline_metrics['roc_auc'])*100:+.2f}%)")
print(f"   PR-AUC:   {baseline_metrics['pr_auc']:.4f} -> {optimized_metrics['pr_auc']:.4f} ({(optimized_metrics['pr_auc']-baseline_metrics['pr_auc'])*100:+.2f}%)")
print(f"   F1-Score: {baseline_metrics['f1']:.4f} -> {optimized_metrics['f1']:.4f} ({(optimized_metrics['f1']-baseline_metrics['f1'])*100:+.2f}%)")

# ============================================================
# STEP 12: Feature Importance Analysis
# ============================================================
print("\n" + "="*80)
print("FEATURE IMPORTANCE ANALYSIS")
print("="*80)

coefficients = best_lr_model.coef_[0]
feature_importance = pd.DataFrame({
    'feature': feature_names,
    'coefficient': coefficients,
    'abs_coefficient': np.abs(coefficients)
}).sort_values('abs_coefficient', ascending=False)

print("\nTop 15 Most Important Features:")
print(feature_importance.head(15).to_string(index=False))

feature_importance.to_csv(os.path.join(output_dir, 'feature_importance_lr.csv'), index=False)
print(f"\nFeature importance saved to output/feature_importance_lr.csv")

# ============================================================
# STEP 13: ROC and Precision-Recall Curves
# ============================================================
fig, axes = plt.subplots(1, 2, figsize=(14, 5))

fpr, tpr, _ = roc_curve(y_test, y_test_proba_opt)
roc_auc_val = auc(fpr, tpr)
axes[0].plot(fpr, tpr, color='darkorange', lw=2, label=f'ROC Curve (AUC = {roc_auc_val:.4f})')
axes[0].plot([0, 1], [0, 1], color='navy', lw=2, linestyle='--', label='Random Classifier')
axes[0].set_xlim([0.0, 1.0])
axes[0].set_ylim([0.0, 1.05])
axes[0].set_xlabel('False Positive Rate')
axes[0].set_ylabel('True Positive Rate')
axes[0].set_title('ROC Curve - Logistic Regression')
axes[0].legend(loc="lower right")
axes[0].grid(True, alpha=0.3)

prec_curve, rec_curve, _ = precision_recall_curve(y_test, y_test_proba_opt)
pr_auc_val = auc(rec_curve, prec_curve)
axes[1].plot(rec_curve, prec_curve, color='darkgreen', lw=2, label=f'PR Curve (AUC = {pr_auc_val:.4f})')
axes[1].axhline(y=y_test.mean(), color='navy', linestyle='--', lw=2, label=f'Baseline (Fraud Rate = {y_test.mean():.4f})')
axes[1].set_xlim([0.0, 1.0])
axes[1].set_ylim([0.0, 1.05])
axes[1].set_xlabel('Recall')
axes[1].set_ylabel('Precision')
axes[1].set_title('Precision-Recall Curve - Logistic Regression')
axes[1].legend(loc="best")
axes[1].grid(True, alpha=0.3)

plt.tight_layout()
curves_path = os.path.join(output_dir, 'lr_performance_curves.png')
plt.savefig(curves_path, dpi=300, bbox_inches='tight')
print(f"\nPerformance curves saved to output/lr_performance_curves.png")
plt.close()

# ============================================================
# STEP 14: Threshold Optimization
# ============================================================
print("\n" + "="*80)
print("THRESHOLD OPTIMIZATION")
print("="*80)

thresholds = np.arange(0.1, 0.9, 0.05)
f1_scores_list = []
for threshold in thresholds:
    y_pred_t = (y_test_proba_opt >= threshold).astype(int)
    f1_scores_list.append(f1_score(y_test, y_pred_t))

optimal_idx = np.argmax(f1_scores_list)
optimal_threshold = thresholds[optimal_idx]
optimal_f1 = f1_scores_list[optimal_idx]

print(f"\nOptimal Threshold for F1-Score:")
print(f"   Threshold: {optimal_threshold:.2f}")
print(f"   F1-Score: {optimal_f1:.4f}")

y_test_pred_optimal = (y_test_proba_opt >= optimal_threshold).astype(int)
print(f"\nPerformance with Optimal Threshold ({optimal_threshold:.2f}):")
final_metrics = evaluate_model(y_test, y_test_pred_optimal, y_test_proba_opt, "Final (Optimized Threshold)")

# ============================================================
# STEP 15: Save Model and Results
# ============================================================
print("\n" + "="*80)
print("SAVING MODEL AND RESULTS")
print("="*80)

with open(os.path.join(output_dir, 'logistic_regression_fraud_model.pkl'), 'wb') as f:
    pickle.dump(best_lr_model, f)
print("\nModel saved to output/logistic_regression_fraud_model.pkl")

with open(os.path.join(output_dir, 'feature_scaler.pkl'), 'wb') as f:
    pickle.dump(scaler, f)
print("Scaler saved to output/feature_scaler.pkl")

with open(os.path.join(output_dir, 'feature_names.pkl'), 'wb') as f:
    pickle.dump(feature_names, f)
print("Feature names saved to output/feature_names.pkl")

results_summary = {
    'model_type': 'Logistic Regression',
    'training_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
    'dataset_size': {
        'total_transactions': len(df_engineered),
        'training_samples': len(X_train_resampled),
        'test_samples': len(X_test)
    },
    'best_parameters': grid_search.best_params_,
    'performance_metrics': {
        'test_accuracy': optimized_metrics['accuracy'],
        'test_precision': optimized_metrics['precision'],
        'test_recall': optimized_metrics['recall'],
        'test_f1': optimized_metrics['f1'],
        'test_roc_auc': optimized_metrics['roc_auc'],
        'test_pr_auc': optimized_metrics['pr_auc']
    },
    'optimal_threshold': float(optimal_threshold),
    'n_features': len(feature_names)
}

with open(os.path.join(output_dir, 'model_results_summary.pkl'), 'wb') as f:
    pickle.dump(results_summary, f)
print("Results summary saved to output/model_results_summary.pkl")

print("\n" + "="*80)
print("TRAINING COMPLETE!")
print("="*80)
print(f"\nSaved Files in output/:")
print(f"   1. logistic_regression_fraud_model.pkl")
print(f"   2. feature_scaler.pkl")
print(f"   3. feature_names.pkl")
print(f"   4. model_results_summary.pkl")
print(f"   5. feature_importance_lr.csv")
print(f"   6. lr_performance_curves.png")
