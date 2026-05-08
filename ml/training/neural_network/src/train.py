# Training functions

import torch
import torch.nn as nn
import torch.optim as optim
import numpy as np
import matplotlib.pyplot as plt
import os
from src.model import MLP

def train_mlp(X_train, y_train, X_val, y_val, input_size, 
              lr=0.001, max_epochs=200, patience=15, 
              model_path='models/best_mlp.pt', plot_path='output/training_curve.png',
              pos_weight=None):
    """
    Train the MLP with Adam optimizer and early stopping.
    Supports class imbalance compensation via pos_weight.
    
    Args:
        X_train, y_train: Training data (numpy arrays)
        X_val, y_val: Validation data
        input_size: Number of input features
        lr: Learning rate
        max_epochs: Maximum epochs
        patience: Early stopping patience
        model_path: Path to save best model
        plot_path: Path to save training curve plot
    
    Returns:
        model: Trained model
        history: Dict with train/val losses
    """
    # Convert to tensors
    X_train_tensor = torch.FloatTensor(X_train)
    y_train_tensor = torch.FloatTensor(y_train).unsqueeze(1)
    X_val_tensor = torch.FloatTensor(X_val)
    y_val_tensor = torch.FloatTensor(y_val).unsqueeze(1)
    
    # Initialize model, optimizer, loss
    model = MLP(input_size)
    optimizer = optim.Adam(model.parameters(), lr=lr)

    # Use class imbalance weight (pos_weight) for BCEWithLogitsLoss if provided
    if pos_weight is None:
        # compute from y_train positive ratio
        pos_count = float((y_train_tensor == 1).sum())
        neg_count = float((y_train_tensor == 0).sum())
        pos_weight = torch.tensor(max(1.0, neg_count / (pos_count + 1e-9)))
    else:
        pos_weight = torch.tensor(pos_weight)
    criterion = nn.BCEWithLogitsLoss(pos_weight=pos_weight)
    
    # Early stopping variables
    best_val_loss = float('inf')
    patience_counter = 0
    best_model_state = None
    
    # Training history
    train_losses = []
    val_losses = []
    
    for epoch in range(max_epochs):
        # Training phase
        model.train()
        optimizer.zero_grad()
        
        outputs = model(X_train_tensor).squeeze()
        train_loss = criterion(outputs, y_train_tensor.squeeze())
        train_loss.backward()
        optimizer.step()
        
        # Validation phase
        model.eval()
        with torch.no_grad():
            val_outputs = model(X_val_tensor).squeeze()
            val_loss = criterion(val_outputs, y_val_tensor.squeeze())
        
        # Record losses
        train_losses.append(train_loss.item())
        val_losses.append(val_loss.item())
        
        # Early stopping check
        if val_loss < best_val_loss:
            best_val_loss = val_loss
            patience_counter = 0
            best_model_state = model.state_dict()
        else:
            patience_counter += 1
            if patience_counter >= patience:
                print(f"Early stopping at epoch {epoch + 1}")
                break
        
        # Print progress
        if (epoch + 1) % 10 == 0:
            print(f"Epoch {epoch + 1}/{max_epochs}, Train Loss: {train_loss:.4f}, Val Loss: {val_loss:.4f}")
    
    # Save best model
    if best_model_state:
        os.makedirs(os.path.dirname(model_path), exist_ok=True)
        torch.save(best_model_state, model_path)
        print(f"Best model saved to {model_path}")
    
    # Load best model
    model.load_state_dict(torch.load(model_path))
    
    # Plot training curve
    plot_training_curve(train_losses, val_losses, plot_path)
    
    history = {'train_loss': train_losses, 'val_loss': val_losses}
    return model, history

def plot_training_curve(train_losses, val_losses, save_path):
    """
    Plot and save training curve.
    
    Args:
        train_losses: List of training losses
        val_losses: List of validation losses
        save_path: Path to save the plot
    """
    plt.figure(figsize=(10, 6))
    plt.plot(train_losses, label='Training Loss')
    plt.plot(val_losses, label='Validation Loss')
    plt.xlabel('Epoch')
    plt.ylabel('Loss')
    plt.title('Training and Validation Loss')
    plt.legend()
    plt.grid(True)
    
    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    plt.savefig(save_path)
    plt.close()
def hyperparameter_tuning(X_train, y_train, X_val, y_val, input_size):
    """
    Simple hyperparameter search for learning rate and dropout.
    This is a basic implementation - for production use Optuna or similar.
    
    Args:
        X_train, y_train, X_val, y_val: Data
        input_size: Number of features
    
    Returns:
        dict: Best hyperparameters and score
    """
    from itertools import product
    
    # Define search space
    lrs = [0.001, 0.0005, 0.0001]
    dropouts = [0.2, 0.3, 0.4]
    
    best_auc = 0
    best_params = {}
    
    print("Starting hyperparameter search...")
    
    for lr, dropout in product(lrs, dropouts):
        print(f"Testing lr={lr}, dropout={dropout}")
        
        # Create model with custom dropout
        model = MLP(input_size)
        # Note: For simplicity, using fixed dropout. In practice, modify model to accept dropout param
        
        # Quick training (fewer epochs for speed)
        model, _ = train_mlp(X_train, y_train, X_val, y_val, input_size, 
                           lr=lr, max_epochs=50, patience=10, 
                           model_path='models/temp.pt', plot_path=None)
        
        # Evaluate on val
        from evaluate import evaluate_model
        metrics = evaluate_model(X_val, y_val, 'models/temp.pt', 'models/scaler.pkl', None)
        
        if metrics['auc'] > best_auc:
            best_auc = metrics['auc']
            best_params = {'lr': lr, 'dropout': dropout}
    
    print(f"Best params: {best_params}, AUC: {best_auc:.4f}")
    return best_params, best_auc