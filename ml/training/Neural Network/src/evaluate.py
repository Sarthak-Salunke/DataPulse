# Evaluation functions

import torch
import numpy as np
import matplotlib.pyplot as plt
from sklearn.metrics import roc_auc_score, classification_report, confusion_matrix, roc_curve, accuracy_score, precision_score, recall_score, f1_score, average_precision_score
import seaborn as sns
import os
from src.model import MLP

def evaluate_model(X_test, y_test, model_path='models/best_mlp.pt', 
                   scaler_path='models/scaler.pkl', roc_path='output/roc_curve.png',
                   threshold=0.5):
    """
    Evaluate the trained model on test set.
    
    Args:
        X_test: Test features (scaled)
        y_test: Test labels
        model_path: Path to saved model
        scaler_path: Path to scaler (for input_size)
        roc_path: Path to save ROC curve
        threshold: Decision threshold for probability -> class
    
    Returns:
        dict: Evaluation metrics
    """
    # Load scaler to get input size
    import joblib
    scaler = joblib.load(scaler_path)
    input_size = scaler.n_features_in_
    
    # Load model
    model = MLP(input_size)
    model.load_state_dict(torch.load(model_path))
    model.eval()
    
    # Convert to tensors
    X_test_tensor = torch.FloatTensor(X_test)
    
    # Get predictions
    with torch.no_grad():
        logits = model(X_test_tensor).squeeze().numpy()

    y_pred_proba = 1 / (1 + np.exp(-logits))  # sigmoid transform
    y_pred = (y_pred_proba >= threshold).astype(int)
    
    # Calculate metrics
    auc = roc_auc_score(y_test, y_pred_proba)
    pr_auc = average_precision_score(y_test, y_pred_proba)
    accuracy = accuracy_score(y_test, y_pred)
    precision = precision_score(y_test, y_pred, zero_division=0)
    recall = recall_score(y_test, y_pred, zero_division=0)
    f1 = f1_score(y_test, y_pred, zero_division=0)
    
    cm = confusion_matrix(y_test, y_pred)
    
    # Print formatted results
    print_metrics_summary(auc, pr_auc, accuracy, precision, recall, f1, cm)
    print("\nClassification Report:")
    print(classification_report(y_test, y_pred, zero_division=0))
    
    # Plot ROC curve
    plot_roc_curve(y_test, y_pred_proba, auc, roc_path)
    
    metrics = {
        'auc': auc,
        'pr_auc': pr_auc,
        'accuracy': accuracy,
        'precision': precision,
        'recall': recall,
        'f1': f1,
        'confusion_matrix': cm
    }
    
    return metrics

def plot_roc_curve(y_true, y_proba, auc_score, save_path):
    """
    Plot and save ROC curve.
    
    Args:
        y_true: True labels
        y_proba: Predicted probabilities
        auc_score: AUC score
        save_path: Path to save plot
    """
    fpr, tpr, _ = roc_curve(y_true, y_proba)
    
    plt.figure(figsize=(8, 6))
    plt.plot(fpr, tpr, label=f'AUC = {auc_score:.4f}')
    plt.plot([0, 1], [0, 1], 'k--', label='Random')
    plt.xlabel('False Positive Rate')
    plt.ylabel('True Positive Rate')
    plt.title('ROC Curve')
    plt.legend()
    plt.grid(True)
    
    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    plt.savefig(save_path)
    plt.close()
    print(f"ROC curve saved to {save_path}")


def print_metrics_summary(auc, pr_auc, accuracy, precision, recall, f1, confusion_matrix):
    """Print metrics summary in tabular style similar to dashboard screenshot."""
    print("\n=== LR Model Metrics Summary ===")
    print("Metric       | Score")
    print("------------ | -------")
    print(f"Accuracy     | {accuracy:.4f}")
    print(f"Precision    | {precision:.4f}")
    print(f"Recall       | {recall:.4f}")
    print(f"F1-Score     | {f1:.4f}")
    print(f"ROC-AUC      | {auc:.4f}")
    print(f"PR-AUC       | {pr_auc:.4f}")

    print("\nConfusion Matrix:")
    print(confusion_matrix)

    tn, fp, fn, tp = confusion_matrix.ravel()
    print(f"True Negatives : {tn}")
    print(f"False Positives: {fp}")
    print(f"False Negatives: {fn}")
    print(f"True Positives : {tp}")
    print("Note: if positive class is rare, consider class weighting or threshold tuning.")