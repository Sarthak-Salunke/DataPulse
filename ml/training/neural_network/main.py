# Main script to run the MLP training pipeline on project dataset

import os
import sys
import numpy as np
import pandas as pd

sys.path.append('src')

from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
import joblib

from train import train_mlp
from evaluate import evaluate_model

project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
data_dir = os.path.join(project_root, 'data')
output_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'output')
model_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'models')
os.makedirs(output_dir, exist_ok=True)
os.makedirs(model_dir, exist_ok=True)

np.random.seed(42)


def engineer_features(trans_df, cust_df):
    """Feature engineering matching other project models (LR, SVM, etc.)."""
    print("   Engineering features...")

    df = trans_df.merge(cust_df, on='cc_num', how='left', suffixes=('_trans', '_cust'))

    # Temporal
    df['trans_datetime'] = pd.to_datetime(df['trans_date'])
    df['trans_time_obj'] = pd.to_datetime(df['trans_time'], format='%H:%M:%S')
    df['hour'] = df['trans_time_obj'].dt.hour
    df['day_of_week'] = df['trans_datetime'].dt.dayofweek
    df['day_of_month'] = df['trans_datetime'].dt.day
    df['month'] = df['trans_datetime'].dt.month
    df['is_weekend'] = (df['day_of_week'] >= 5).astype(int)
    df['time_of_day'] = pd.cut(df['hour'], bins=[0, 6, 12, 18, 24],
                                labels=['night', 'morning', 'afternoon', 'evening'])
    df['is_high_risk_hour'] = ((df['hour'] >= 23) | (df['hour'] <= 5)).astype(int)

    # Amount
    df['amt_log'] = np.log1p(df['amt'])
    cust_amt = df.groupby('cc_num')['amt'].agg(['mean', 'std', 'median']).reset_index()
    cust_amt.columns = ['cc_num', 'cust_amt_mean', 'cust_amt_std', 'cust_amt_median']
    df = df.merge(cust_amt, on='cc_num', how='left')
    df['amt_ratio_to_avg'] = df['amt'] / (df['cust_amt_mean'] + 1)
    df['amt_deviation'] = (df['amt'] - df['cust_amt_mean']) / (df['cust_amt_std'] + 1)
    df['amt_above_median'] = (df['amt'] > df['cust_amt_median']).astype(int)

    # Geospatial
    def haversine(lat1, lon1, lat2, lon2):
        R = 6371
        lat1, lon1, lat2, lon2 = map(np.radians, [lat1, lon1, lat2, lon2])
        dlat, dlon = lat2 - lat1, lon2 - lon1
        a = np.sin(dlat/2)**2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon/2)**2
        return R * 2 * np.arcsin(np.sqrt(a))

    df['distance_from_home'] = haversine(df['lat'], df['long'], df['merch_lat'], df['merch_long'])
    df['is_local_transaction'] = (df['distance_from_home'] < 10).astype(int)
    df['is_distant_transaction'] = (df['distance_from_home'] > 100).astype(int)

    # Behavioral
    df = df.sort_values(['cc_num', 'unix_time']).reset_index(drop=True)
    df['customer_trans_count'] = df.groupby('cc_num').cumcount() + 1
    df['time_since_last_trans'] = df.groupby('cc_num')['unix_time'].diff().fillna(0)
    df['time_since_last_trans_hours'] = df['time_since_last_trans'] / 3600
    df['is_quick_succession'] = (df['time_since_last_trans'] < 300).astype(int)

    # Category
    cat_counts = df.groupby(['cc_num', 'category']).size().reset_index(name='category_count')
    df = df.merge(cat_counts, on=['cc_num', 'category'], how='left')

    # Merchant
    merch_counts = df.groupby(['cc_num', 'merchant']).size().reset_index(name='merchant_usage_count')
    df = df.merge(merch_counts, on=['cc_num', 'merchant'], how='left')
    df['is_new_merchant'] = (df['merchant_usage_count'] == 1).astype(int)

    # Risk
    merch_fraud = df.groupby('merchant')['is_fraud'].mean().reset_index()
    merch_fraud.columns = ['merchant', 'merchant_fraud_rate']
    df = df.merge(merch_fraud, on='merchant', how='left')
    df['merchant_fraud_rate'] = df['merchant_fraud_rate'].fillna(df['is_fraud'].mean())

    cat_fraud = df.groupby('category')['is_fraud'].mean().reset_index()
    cat_fraud.columns = ['category', 'category_fraud_rate']
    df = df.merge(cat_fraud, on='category', how='left')

    return df


def prepare_features(df):
    """Select and encode features for modeling."""
    numerical_features = [
        'amt', 'amt_log', 'hour', 'day_of_week', 'day_of_month', 'month',
        'is_weekend', 'is_high_risk_hour', 'amt_ratio_to_avg', 'amt_deviation',
        'amt_above_median', 'distance_from_home', 'is_local_transaction',
        'is_distant_transaction', 'customer_trans_count', 'time_since_last_trans_hours',
        'is_quick_succession', 'category_count', 'merchant_usage_count',
        'is_new_merchant', 'merchant_fraud_rate', 'category_fraud_rate'
    ]

    categorical_features = ['category', 'gender', 'time_of_day']

    X = df[numerical_features].copy()
    for cat in categorical_features:
        if cat in df.columns:
            dummies = pd.get_dummies(df[cat], prefix=cat, drop_first=True)
            X = pd.concat([X, dummies], axis=1)

    y = df['is_fraud'].values
    # Ensure all columns are numeric
    X = X.apply(pd.to_numeric, errors='coerce').fillna(0)

    print(f"   Features: {X.shape[1]}, Samples: {X.shape[0]}")
    return X, y


def main():
    """
    MLP training pipeline using project dataset (data/transactions.csv + data/customer.csv).
    Same feature engineering as LR, SVM, NB, etc. for fair comparison.
    """
    print("=" * 80)
    print("FRAUD DETECTION - NEURAL NETWORK (MLP) MODEL")
    print("Dataset: Project data (transactions.csv + customer.csv)")
    print("=" * 80)

    # Step 1: Load data
    print("\n1. Loading data...")
    customer_df = pd.read_csv(os.path.join(data_dir, 'customer.csv'))
    transactions_df = pd.read_csv(os.path.join(data_dir, 'transactions.csv'))
    print(f"   Customers: {len(customer_df)}, Transactions: {len(transactions_df)}")
    print(f"   Fraud Rate: {transactions_df['is_fraud'].mean()*100:.2f}%")

    # Step 2: Feature engineering
    print("\n2. Feature engineering...")
    df = engineer_features(transactions_df, customer_df)

    # Step 3: Prepare features
    print("\n3. Preparing features...")
    X, y = prepare_features(df)

    # Step 4: Split (70/15/15 - train/val/test)
    print("\n4. Splitting data...")
    X_train, X_temp, y_train, y_temp = train_test_split(
        X, y, test_size=0.3, random_state=42, stratify=y
    )
    X_val, X_test, y_val, y_test = train_test_split(
        X_temp, y_temp, test_size=0.5, random_state=42, stratify=y_temp
    )
    print(f"   Train: {len(y_train)}, Val: {len(y_val)}, Test: {len(y_test)}")

    # Step 5: Scale
    print("\n5. Scaling features...")
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_val_scaled = scaler.transform(X_val)
    X_test_scaled = scaler.transform(X_test)
    scaler_path = os.path.join(model_dir, 'scaler.pkl')
    joblib.dump(scaler, scaler_path)

    # Step 6: Train
    print("\n6. Training MLP (128->64->32, early stopping)...")
    model_path = os.path.join(model_dir, 'best_mlp.pt')
    plot_path = os.path.join(output_dir, 'training_curve.png')
    model, history = train_mlp(
        X_train_scaled, y_train,
        X_val_scaled, y_val,
        input_size=X_train_scaled.shape[1],
        model_path=model_path,
        plot_path=plot_path
    )

    # Step 7: Evaluate
    print("\n7. Evaluating on test set...")
    roc_path = os.path.join(output_dir, 'roc_curve.png')
    metrics = evaluate_model(
        X_test_scaled, y_test,
        model_path=model_path,
        scaler_path=scaler_path,
        roc_path=roc_path
    )

    # Save comparison CSV
    print("\n" + "=" * 80)
    print("RESULTS SUMMARY")
    print("=" * 80)
    print(f"   ROC-AUC:    {metrics['auc']:.4f}")
    print(f"   PR-AUC:     {metrics['pr_auc']:.4f}")
    print(f"   F1-Score:   {metrics['f1']:.4f}")
    print(f"   Precision:  {metrics['precision']:.4f}")
    print(f"   Recall:     {metrics['recall']:.4f}")

    results_df = pd.DataFrame([{
        'Model': 'Neural Network (MLP)',
        'ROC-AUC': metrics['auc'],
        'PR-AUC': metrics['pr_auc'],
        'F1-Score': metrics['f1'],
        'Precision': metrics['precision'],
        'Recall': metrics['recall']
    }])
    results_df.to_csv(os.path.join(output_dir, 'nn_model_comparison.csv'), index=False)

    print(f"\nOutputs saved to: {output_dir}")
    print("=" * 80)
    print("TRAINING COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    main()