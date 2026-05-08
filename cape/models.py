"""Shared data models for the CAPE pipeline."""
import time
from dataclasses import dataclass, field
from typing import Optional, Dict, List, Any
from enum import Enum


class RoutingDecision(str, Enum):
    BLOCK = "BLOCK"
    APPROVE = "APPROVE"
    NOVEL_FLAG = "NOVEL-FLAG"


class Channel(str, Enum):
    WEB = "web"
    MOBILE = "mobile"
    POS = "pos"
    ATM = "atm"
    RECURRING = "recurring"
    B2B_BATCH = "b2b_batch"


@dataclass
class Transaction:
    trans_num: str
    cc_num: str
    amt: float
    merchant: str
    category: str
    channel: Channel = Channel.WEB
    device_fingerprint: str = ""
    typing_cadence_hash: str = ""
    network_anomaly_flag: bool = False
    ip_country: str = ""
    merchant_lat: float = 0.0
    merchant_long: float = 0.0
    timestamp: float = field(default_factory=time.time)


@dataclass
class FeatureVector:
    version: str
    # Pre-computed (<1ms)
    user_spend_30d_by_category: Dict[str, float]
    velocity_1min: int
    velocity_10min: int
    velocity_1hr: int
    velocity_24hr: int
    days_since_account_open: int
    device_history_hash: str
    merchant_txn_volume_per_hr: float
    merchant_chargeback_rate_30d: float
    merchant_fraud_signal_index: float
    graph_distinct_accounts_1hr: int
    graph_shared_device_flagged: bool
    # On-the-fly (<5ms)
    amount_zscore: float
    time_since_last_txn: float
    country_ip_consistent: bool
    device_fingerprint_entropy: float


@dataclass
class CAPEDecision:
    trans_num: str
    decision: RoutingDecision
    point_estimate: float
    interval_lower: float
    interval_upper: float
    interval_width: float
    feature_version: str
    shap_top3: Optional[List[Dict[str, Any]]] = None
    reason_codes: Optional[List[str]] = None
    channel_action: Optional[str] = None
    scorer_scores: Optional[Dict[str, float]] = None
    drift_adjusted_threshold: Optional[float] = None
