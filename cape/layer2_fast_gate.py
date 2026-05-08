"""
Layer 2 — Fast Gate

Three-component gate that evaluates statistical normality and outputs
a binary ESCALATE / PASS decision.

Components:
  1. Welford per-user baseline: amount must stay within N std-devs
  2. Velocity CMS: Count-Min Sketch sliding windows (1m / 10m / 1h)
  3. Invisible device signals: entropy, typing cadence, network anomaly
"""
import hashlib
import time
from typing import Dict, Tuple

from .models import Transaction, FeatureVector
from .layer0_feature_store import FeatureStore, WelfordState

# --- Welford gate ---
WELFORD_N_STDEV = 2.5  # transactions beyond this many std-devs escalate

# --- Count-Min Sketch ---
CMS_WIDTH = 1000
CMS_DEPTH = 4

# --- Velocity spike thresholds (transactions per window) ---
VELOCITY_SPIKE = {"1min": 3, "10min": 10, "1hr": 30}

# --- Device signal bounds ---
DEVICE_ENTROPY_MIN = 1.0   # below this → fingerprint too uniform (suspicious)
DEVICE_ENTROPY_MAX = 5.5   # above this → fingerprint looks randomly generated


class CountMinSketch:
    """Approximate frequency counter. O(width × depth) space."""

    def __init__(self, width: int = CMS_WIDTH, depth: int = CMS_DEPTH):
        self.width = width
        self.depth = depth
        self.table = [[0] * width for _ in range(depth)]
        self._seeds = [i * 2654435761 for i in range(1, depth + 1)]

    def _hash(self, key: str, seed: int) -> int:
        digest = int(hashlib.md5(f"{seed}{key}".encode()).hexdigest(), 16)
        return digest % self.width

    def add(self, key: str, count: int = 1):
        for d, seed in enumerate(self._seeds):
            self.table[d][self._hash(key, seed)] += count

    def query(self, key: str) -> int:
        return min(self.table[d][self._hash(key, seed)] for d, seed in enumerate(self._seeds))


class VelocityCMS:
    """Sliding-window velocity tracker backed by CMS event lists."""

    _WINDOWS = [("1min", 60), ("10min", 600), ("1hr", 3600)]

    def __init__(self):
        # key: f"{window_name}:{user_id}" → {"cms": CMS, "events": [(ts, user_id)]}
        self._buckets: Dict[str, dict] = {}

    def record_and_count(self, user_id: str) -> Dict[str, int]:
        """Records the current transaction and returns counts per window."""
        now = time.time()
        counts: Dict[str, int] = {}
        for window_name, window_secs in self._WINDOWS:
            key = f"{window_name}:{user_id}"
            if key not in self._buckets:
                self._buckets[key] = {"cms": CountMinSketch(), "events": []}
            bucket = self._buckets[key]
            cutoff = now - window_secs
            bucket["events"] = [(ts, u) for ts, u in bucket["events"] if ts > cutoff]
            bucket["events"].append((now, user_id))
            bucket["cms"].add(user_id)
            counts[window_name] = len(bucket["events"])
        return counts


class FastGate:
    def __init__(self):
        self.velocity_cms = VelocityCMS()

    # ------------------------------------------------------------------

    def _welford_pass(self, welford: WelfordState, amount: float) -> bool:
        if welford.n < 2:
            return False  # no baseline yet — must escalate
        return abs(welford.zscore(amount)) <= WELFORD_N_STDEV

    def _velocity_pass(self, counts: Dict[str, int]) -> bool:
        return all(counts.get(w, 0) <= spike for w, spike in VELOCITY_SPIKE.items())

    def _device_pass(self, txn: Transaction, fv: FeatureVector) -> bool:
        entropy = fv.device_fingerprint_entropy
        if not (DEVICE_ENTROPY_MIN <= entropy <= DEVICE_ENTROPY_MAX):
            return False
        if txn.network_anomaly_flag:
            return False
        # Typing cadence hash expected on web/mobile channels
        if not txn.typing_cadence_hash and txn.channel.value in ("web", "mobile"):
            return False
        return True

    # ------------------------------------------------------------------

    def evaluate(
        self, txn: Transaction, fv: FeatureVector, feature_store: FeatureStore
    ) -> Tuple[bool, str]:
        """
        Returns (should_escalate, reason).
        False = transaction passes the gate (approve without full scoring).
        True  = escalate to Layer 3.
        """
        user_id = str(txn.cc_num)
        welford = feature_store.get_welford_state(user_id)
        counts = self.velocity_cms.record_and_count(user_id)

        if not self._welford_pass(welford, txn.amt):
            return True, "welford_deviation"
        # Velocity spike overrides Welford pass
        if not self._velocity_pass(counts):
            return True, "velocity_spike"
        if not self._device_pass(txn, fv):
            return True, "device_signal_anomaly"
        return False, "pass"
