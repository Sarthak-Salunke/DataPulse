"""
Layer 3 — Parallel Scorers

Three independent scorers run concurrently and output a probability vector.
Each scorer is isolated — they do NOT share intermediate state.

  1. RandomForestScorer  — tabular feature interactions
  2. GBTScorer           — non-linear patterns (LightGBM preferred, sklearn fallback)
  3. EWMAScorer          — recency-weighted past fraud score; O(1), stateless lookup
"""
from typing import Dict, Optional

import numpy as np
from sklearn.ensemble import RandomForestClassifier

from .models import FeatureVector
from .layer0_feature_store import FeatureStore

try:
    import lightgbm as lgb
    _HAS_LGB = True
except ImportError:
    _HAS_LGB = False

# Feature ordering must stay consistent between training and inference
FEATURE_ORDER = [
    "velocity_1min",
    "velocity_10min",
    "velocity_1hr",
    "velocity_24hr",
    "days_since_account_open",
    "merchant_txn_volume_per_hr",
    "merchant_chargeback_rate_30d",
    "merchant_fraud_signal_index",
    "graph_shared_device_flagged",
    "graph_distinct_accounts_1hr",
    "amount_zscore",
    "time_since_last_txn_norm",   # normalised to [0, 1]
    "country_ip_consistent",
    "device_fingerprint_entropy",
    # top-5 category spend values (zero-padded)
    "spend_cat_0", "spend_cat_1", "spend_cat_2", "spend_cat_3", "spend_cat_4",
]
N_FEATURES = len(FEATURE_ORDER)  # 19


def feature_vector_to_array(fv: FeatureVector) -> np.ndarray:
    cat_spend = list(fv.user_spend_30d_by_category.values())[:5]
    while len(cat_spend) < 5:
        cat_spend.append(0.0)
    return np.array([
        fv.velocity_1min,
        fv.velocity_10min,
        fv.velocity_1hr,
        fv.velocity_24hr,
        fv.days_since_account_open,
        fv.merchant_txn_volume_per_hr,
        fv.merchant_chargeback_rate_30d,
        fv.merchant_fraud_signal_index,
        float(fv.graph_shared_device_flagged),
        float(fv.graph_distinct_accounts_1hr),
        fv.amount_zscore,
        min(fv.time_since_last_txn, 86400.0) / 86400.0,
        float(fv.country_ip_consistent),
        fv.device_fingerprint_entropy,
        *cat_spend,
    ], dtype=np.float32)


def _dummy_fit(clf, n_features: int):
    X = np.zeros((10, n_features))
    y = np.array([0, 1] * 5)
    clf.fit(X, y)


class RandomForestScorer:
    def __init__(self, model: Optional[RandomForestClassifier] = None):
        if model is not None:
            self.model = model
        else:
            self.model = RandomForestClassifier(n_estimators=10, random_state=42)
            _dummy_fit(self.model, N_FEATURES)

    def score(self, fv: FeatureVector) -> float:
        X = feature_vector_to_array(fv).reshape(1, -1)
        proba = self.model.predict_proba(X)[0]
        return float(proba[1]) if len(proba) > 1 else 0.5

    def get_model(self):
        return self.model


class GBTScorer:
    def __init__(self, model=None):
        if model is not None:
            self.model = model
            self._use_lgb = _HAS_LGB and isinstance(model, lgb.Booster if _HAS_LGB else type(None))
        elif _HAS_LGB:
            # Placeholder LGB dataset — replaced by a real trained model at load time
            X = np.zeros((10, N_FEATURES))
            y = np.array([0, 1] * 5)
            train_data = lgb.Dataset(X, label=y)
            params = {"objective": "binary", "num_leaves": 4, "verbose": -1}
            self.model = lgb.train(params, train_data, num_boost_round=5)
            self._use_lgb = True
        else:
            from sklearn.ensemble import GradientBoostingClassifier
            self.model = GradientBoostingClassifier(n_estimators=10, random_state=42)
            _dummy_fit(self.model, N_FEATURES)
            self._use_lgb = False

    def score(self, fv: FeatureVector) -> float:
        X = feature_vector_to_array(fv).reshape(1, -1)
        try:
            if self._use_lgb:
                prob = float(self.model.predict(X)[0])
                return max(0.0, min(1.0, prob))
            proba = self.model.predict_proba(X)[0]
            return float(proba[1]) if len(proba) > 1 else 0.5
        except Exception:
            return 0.5

    def get_model(self):
        return self.model


class EWMAScorer:
    """
    Recency-weighted EWMA of past fraud scores stored in the feature store.
    O(1) — reads one float, no stateful session lookup required.
    """
    def __init__(self, alpha: float = 0.3):
        self.alpha = alpha

    def score(self, user_id: str, feature_store: FeatureStore) -> float:
        return feature_store.get_ewma_score(user_id)


class ParallelScorers:
    def __init__(self, rf_model=None, gbt_model=None, ewma_alpha: float = 0.3):
        self.rf = RandomForestScorer(rf_model)
        self.gbt = GBTScorer(gbt_model)
        self.ewma = EWMAScorer(ewma_alpha)

    def score(
        self, fv: FeatureVector, user_id: str, feature_store: FeatureStore
    ) -> Dict[str, float]:
        """Returns probability vector {model_name: fraud_probability}."""
        return {
            "random_forest": self.rf.score(fv),
            "gbt": self.gbt.score(fv),
            "ewma": self.ewma.score(user_id, feature_store),
        }
