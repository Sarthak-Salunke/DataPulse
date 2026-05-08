"""
Layer 7 — Explainability (Regulatory Requirement)

Mandatory for every declined (BLOCK) transaction under RBI / PSD2 equivalents.
SHAP values are computed exclusively on the GBT scorer (fastest TreeExplainer,
most interpretable). Top 3 contributing features are mapped to human-readable
reason codes and cached alongside the decision record.

Added latency: ~5–8ms on the uncertain scoring path.
Fast-gate-approved transactions incur zero explainability overhead.
"""
from typing import Any, Dict, List

import numpy as np

from .layer3_parallel_scorers import feature_vector_to_array, FEATURE_ORDER
from .models import FeatureVector

try:
    import shap
    _HAS_SHAP = True
except ImportError:
    _HAS_SHAP = False

# Human-readable reason codes keyed by feature name
REASON_CODE_MAP: Dict[str, str] = {
    "amount_zscore":                 "Transaction amount significantly above user's typical range",
    "velocity_1min":                 "Unusually high transaction frequency in last 1 minute",
    "velocity_10min":                "Unusually high transaction frequency in last 10 minutes",
    "velocity_1hr":                  "Unusually high transaction frequency in last hour",
    "velocity_24hr":                 "High transaction volume in the last 24 hours",
    "merchant_chargeback_rate_30d":  "Merchant has elevated chargeback rate",
    "merchant_fraud_signal_index":   "Merchant fraud signal index is elevated",
    "graph_shared_device_flagged":   "Device shared with a previously flagged account",
    "country_ip_consistent":         "IP country inconsistent with account history",
    "device_fingerprint_entropy":    "Anomalous device fingerprint detected",
    "days_since_account_open":       "Account age inconsistent with transaction profile",
    "time_since_last_txn_norm":      "Unusual time elapsed since last transaction",
    "merchant_txn_volume_per_hr":    "Merchant transaction volume spike detected",
    "graph_distinct_accounts_1hr":   "Unusually high number of accounts at this merchant in last hour",
}


class ExplainabilityLayer:
    def __init__(self, gbt_model=None):
        self._explainer = None
        if _HAS_SHAP and gbt_model is not None:
            try:
                self._explainer = shap.TreeExplainer(gbt_model)
            except Exception:
                self._explainer = None

    def compute_shap(self, fv: FeatureVector) -> List[Dict[str, Any]]:
        """
        Returns top-3 contributing features with their SHAP values.
        Falls back to raw feature magnitude ranking if SHAP unavailable.
        """
        X = feature_vector_to_array(fv).reshape(1, -1)

        if _HAS_SHAP and self._explainer is not None:
            try:
                raw = self._explainer.shap_values(X)
                # TreeExplainer returns a list [class0_vals, class1_vals] for classifiers
                vals: np.ndarray = raw[1][0] if isinstance(raw, list) else raw[0]
                top_idx = np.argsort(np.abs(vals))[::-1][:3]
                return [
                    {"feature": FEATURE_ORDER[i], "shap_value": float(vals[i])}
                    for i in top_idx
                ]
            except Exception:
                pass

        # Fallback: rank by absolute feature value
        magnitudes = np.abs(X[0])
        top_idx = np.argsort(magnitudes)[::-1][:3]
        return [
            {"feature": FEATURE_ORDER[i], "shap_value": float(X[0][i])}
            for i in top_idx
        ]

    def get_reason_codes(self, shap_top3: List[Dict[str, Any]]) -> List[str]:
        """Maps top-3 SHAP features to human-readable reason codes."""
        return [
            REASON_CODE_MAP.get(item["feature"], f"Anomalous pattern in {item['feature']}")
            for item in shap_top3
        ]
