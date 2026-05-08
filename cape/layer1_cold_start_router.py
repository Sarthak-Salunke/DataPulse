"""
Layer 1 — Cold-Start Router

New users (<20 txns) and new merchants (<7 days active) bypass the fast gate
entirely and receive tighter static block/review thresholds.
"""
from typing import Tuple, Dict

from .models import Transaction
from .layer0_feature_store import FeatureStore

COLD_START_USER_TXN_THRESHOLD = 20
COLD_START_MERCHANT_DAYS_THRESHOLD = 7

# Tighter thresholds applied while entity is in cold-start
COLD_START_BLOCK_THRESHOLD = 0.40
COLD_START_REVIEW_THRESHOLD = 0.20

# Steady-state thresholds (used when not in cold-start)
STEADY_BLOCK_THRESHOLD = 0.70
STEADY_REVIEW_THRESHOLD = 0.40


def is_cold_start_user(feature_store: FeatureStore, user_id: str) -> bool:
    return feature_store.get_user_txn_count(user_id) < COLD_START_USER_TXN_THRESHOLD


def is_cold_start_merchant(feature_store: FeatureStore, merchant_id: str) -> bool:
    return feature_store.get_merchant_active_days(merchant_id) < COLD_START_MERCHANT_DAYS_THRESHOLD


def route_cold_start(
    txn: Transaction, feature_store: FeatureStore
) -> Tuple[bool, Dict[str, float]]:
    """
    Returns (is_cold_start, thresholds).
    If is_cold_start is True the caller must skip the fast gate and use
    the returned tighter thresholds for routing.
    """
    user_cold = is_cold_start_user(feature_store, str(txn.cc_num))
    merchant_cold = is_cold_start_merchant(feature_store, txn.merchant)
    is_cold = user_cold or merchant_cold

    if is_cold:
        return True, {
            "block": COLD_START_BLOCK_THRESHOLD,
            "review": COLD_START_REVIEW_THRESHOLD,
        }
    return False, {
        "block": STEADY_BLOCK_THRESHOLD,
        "review": STEADY_REVIEW_THRESHOLD,
    }
