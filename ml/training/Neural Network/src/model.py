# MLP model definition

import torch
import torch.nn as nn
from sklearn.neural_network import MLPClassifier

class MLP(nn.Module):
    """
    PyTorch Multi-Layer Perceptron for binary classification.
    
    Architecture: Input -> 128 (ReLU, Dropout 0.3) -> 64 (ReLU, Dropout 0.3) -> 32 (ReLU, Dropout 0.2) -> 1 (logit)
    Note: output is raw logit; apply sigmoid in evaluation.
    """
    def __init__(self, input_size):
        super(MLP, self).__init__()
        self.network = nn.Sequential(
            nn.Linear(input_size, 128),
            nn.ReLU(),
            nn.Dropout(0.3),
            
            nn.Linear(128, 64),
            nn.ReLU(),
            nn.Dropout(0.3),
            
            nn.Linear(64, 32),
            nn.ReLU(),
            nn.Dropout(0.2),
            
            nn.Linear(32, 1)
        )
    
    def forward(self, x):
        return self.network(x)

def create_sklearn_mlp():
    """
    Create sklearn MLPClassifier with similar architecture for baseline.
    
    Returns:
        MLPClassifier: Configured model
    """
    model = MLPClassifier(
        hidden_layer_sizes=(128, 64, 32),
        activation='relu',
        solver='adam',
        alpha=0.0001,  # L2 regularization
        max_iter=200,
        early_stopping=True,
        validation_fraction=0.15,
        random_state=42
    )
    return model