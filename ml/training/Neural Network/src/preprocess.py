# Data preprocessing functions

import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
import joblib
import os

def load_data(filepath='data/raw/dataset.csv', target_column='target'):
    """
    Load dataset from CSV, handle missing values, separate features and target.
    
    Args:
        filepath (str): Path to the CSV file
        target_column (str): Name of the target column
    
    Returns:
        X (pd.DataFrame): Features
        y (pd.Series): Target labels
    """
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"Dataset not found at {filepath}")
    
    df = pd.read_csv(filepath)
    print(f"Dataset shape: {df.shape}")
    
    # Handle missing values - fill numeric with mean, categorical with mode
    for col in df.columns:
        if df[col].dtype in ['int64', 'float64']:
            df[col] = df[col].fillna(df[col].mean())
        else:
            mode_val = df[col].mode()
            df[col] = df[col].fillna(mode_val.iloc[0] if len(mode_val) > 0 else np.nan)
    
    # Separate features and target
    if target_column not in df.columns:
        fallback_names = ['target', 'label', 'y', 'class']
        for name in fallback_names:
            if name in df.columns:
                target_column = name
                print(f"Using fallback target column '{name}'")
                break

    if target_column not in df.columns:
        # fallback to last column as target if reasonable
        target_column = df.columns[-1]
        print(f"Target column not found, using last column '{target_column}' as target")

    X = df.drop(columns=[target_column])
    y = df[target_column]
    
    print(f"Features shape: {X.shape}")
    print(f"Target distribution:\n{y.value_counts()}")
    
    return X, y

def split_data(X, y, train_size=0.7, val_size=0.15, test_size=0.15, random_state=42):
    """
    Split data into train, validation, and test sets with stratification.
    
    Args:
        X: Features
        y: Target
        train_size, val_size, test_size: Proportions
        random_state: Random seed
    
    Returns:
        X_train, X_val, X_test, y_train, y_val, y_test
    """
    # First split: train and temp (val+test)
    X_train, X_temp, y_train, y_temp = train_test_split(
        X, y, test_size=(val_size + test_size), random_state=random_state, stratify=y
    )
    
    # Second split: val and test from temp
    val_ratio = val_size / (val_size + test_size)
    X_val, X_test, y_val, y_test = train_test_split(
        X_temp, y_temp, test_size=(1 - val_ratio), random_state=random_state, stratify=y_temp
    )
    
    print(f"Train set: {X_train.shape[0]} samples")
    print(f"Validation set: {X_val.shape[0]} samples")
    print(f"Test set: {X_test.shape[0]} samples")
    
    return X_train, X_val, X_test, y_train, y_val, y_test

def scale_features(X_train, X_val, X_test, scaler_path='models/scaler.pkl'):
    """
    Apply StandardScaler to features. Fit on train, transform all.
    
    Args:
        X_train, X_val, X_test: Feature sets
        scaler_path: Path to save the fitted scaler
    
    Returns:
        Scaled X_train, X_val, X_test
    """
    scaler = StandardScaler()
    
    X_train_scaled = scaler.fit_transform(X_train)
    X_val_scaled = scaler.transform(X_val)
    X_test_scaled = scaler.transform(X_test)
    
    # Save scaler
    os.makedirs(os.path.dirname(scaler_path), exist_ok=True)
    joblib.dump(scaler, scaler_path)
    print(f"Scaler saved to {scaler_path}")
    
    return X_train_scaled, X_val_scaled, X_test_scaled