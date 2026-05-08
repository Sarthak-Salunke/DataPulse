# MLP Binary Classification Project

This project implements a Multi-Layer Perceptron (MLP) for binary classification using PyTorch, following the architecture recommendations from Section 4.8.

## Target Performance
- AUC-ROC: 0.82–0.88
- Accuracy: 78%–85%
- F1-Score: 0.75–0.84

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Place your dataset CSV file at `data/raw/dataset.csv` with a column named `target` for the binary labels.

3. Run the complete pipeline:
```bash
python main.py
```

## Project Structure

- `data/raw/`: Raw dataset
- `data/processed/`: Processed data (if needed)
- `models/`: Saved models and scalers
- `src/`: Source code
  - `preprocess.py`: Data loading and preprocessing
  - `model.py`: MLP architecture
  - `train.py`: Training functions
  - `evaluate.py`: Evaluation metrics
- `outputs/`: Plots and results
- `notebooks/`: Jupyter notebooks for exploration

## Architecture

- Input: Number of features
- Hidden Layer 1: 128 neurons, ReLU, Dropout(0.3)
- Hidden Layer 2: 64 neurons, ReLU, Dropout(0.3)
- Hidden Layer 3: 32 neurons, ReLU, Dropout(0.2)
- Output: 1 neuron, Sigmoid

## Training

- Optimizer: Adam (lr=0.001)
- Loss: Binary Cross-Entropy
- Early Stopping: Patience=15
- Max Epochs: 200

## Evaluation

The model is evaluated on a held-out test set with:
- AUC-ROC
- Accuracy, Precision, Recall, F1-Score
- Confusion Matrix
- ROC Curve plot

## Troubleshooting

If AUC-ROC < 0.82:
- Check feature scaling
- Try hyperparameter tuning
- Ensure stratified splits
- Consider class balancing if imbalanced

## Hyperparameter Tuning

Use the `hyperparameter_tuning` function in `src/train.py` for basic grid search over learning rate and dropout rates.