"""
CAPE Model Loader

Loads trained RF and GBT models from disk and returns an initialized
CAPEPipeline. Falls back to untrained placeholder models if no saved
models are found (useful during development and testing).
"""
import os
import pickle
from typing import Optional

from .pipeline import CAPEPipeline
from .layer0_feature_store import FeatureStore

# Default model directory relative to project root
_DEFAULT_MODEL_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "ml", "models", "cape",
)


def _load_pickle(path: str):
    if not os.path.exists(path):
        return None
    with open(path, "rb") as f:
        return pickle.load(f)


def load_pipeline(
    model_dir: Optional[str] = None,
    deployment_day: int = 0,
    feature_store: Optional[FeatureStore] = None,
) -> CAPEPipeline:
    """
    Load trained RF and GBT models from model_dir and return a ready-to-use
    CAPEPipeline. If models are not found, placeholders are used with a
    printed warning.

    Args:
        model_dir:       Directory containing rf_model.pkl and gbt_model.pkl.
                         Defaults to ml/models/cape/.
        deployment_day:  Day since production launch (controls graph bootstrap).
        feature_store:   Optional pre-seeded FeatureStore (e.g. with Redis).
    """
    model_dir = model_dir or _DEFAULT_MODEL_DIR

    rf_path  = os.path.join(model_dir, "rf_model.pkl")
    gbt_path = os.path.join(model_dir, "gbt_model.pkl")

    rf_model  = _load_pickle(rf_path)
    gbt_model = _load_pickle(gbt_path)

    if rf_model is None:
        print(f"[CAPE] Warning: RF model not found at {rf_path} — using placeholder.")
    else:
        print(f"[CAPE] Loaded RF model from {rf_path}")

    if gbt_model is None:
        print(f"[CAPE] Warning: GBT model not found at {gbt_path} — using placeholder.")
    else:
        print(f"[CAPE] Loaded GBT model from {gbt_path}")

    return CAPEPipeline(
        feature_store=feature_store,
        rf_model=rf_model,
        gbt_model=gbt_model,
        deployment_day=deployment_day,
    )
