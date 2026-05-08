"""
Layer 5 — Dual-Signal Drift Detection

Two complementary detectors run in parallel on the continuous feature stream:

  CUSUM — detects rapid shifts in ~50 transactions (coordinated attacks)
  PSI   — detects slow structural shifts over 1,000–5,000 transactions

When either fires, thresholds are adjusted using the exact formula from the spec:
  adjusted_threshold = base_threshold − (drift_signal_magnitude × 0.15)
  floor: adjusted_threshold ≥ MINIMUM_FLOOR

PSI exceeding PSI_ALERT_THRESHOLD also triggers an automated retrain request.
"""
import numpy as np
from collections import deque
from typing import Deque, Optional, Tuple

# CUSUM parameters
CUSUM_H = 5.0    # decision threshold; fires when cumulative sum exceeds this
CUSUM_K = 0.5    # allowance / slack parameter
CUSUM_WARMUP = 50  # minimum observations before CUSUM is active

# PSI parameters
PSI_ALERT_THRESHOLD = 0.20   # > 0.2 = significant shift → trigger retrain
PSI_WARN_THRESHOLD = 0.10    # 0.1–0.2 = moderate shift → warning
PSI_WINDOW_SIZE = 1000
PSI_REFERENCE_SIZE = 5000

# Threshold adjustment
ADJUSTMENT_COEFFICIENT = 0.15  # as specified in CAPE architecture
MINIMUM_FLOOR = 0.10           # adjusted threshold never goes below this


def _compute_psi(
    reference: np.ndarray, current: np.ndarray, n_bins: int = 10
) -> float:
    """Population Stability Index between two 1-D distributions."""
    lo = min(reference.min(), current.min())
    hi = max(reference.max(), current.max()) + 1e-9
    bins = np.linspace(lo, hi, n_bins + 1)
    ref_counts, _ = np.histogram(reference, bins=bins)
    cur_counts, _ = np.histogram(current, bins=bins)
    # Avoid log(0) by adding epsilon
    ref_pct = ref_counts / (ref_counts.sum() + 1e-9) + 1e-9
    cur_pct = cur_counts / (cur_counts.sum() + 1e-9) + 1e-9
    return float(np.sum((cur_pct - ref_pct) * np.log(cur_pct / ref_pct)))


class CUSUMDetector:
    """Cumulative Sum control chart; detects shift in ~50 transactions."""

    def __init__(self, h: float = CUSUM_H, k: float = CUSUM_K):
        self.h = h
        self.k = k
        self._s_pos: float = 0.0
        self._s_neg: float = 0.0
        self._ref_mean: Optional[float] = None
        self._warmup: Deque[float] = deque(maxlen=CUSUM_WARMUP)

    def update(self, value: float) -> Tuple[bool, float]:
        """Returns (drift_detected, magnitude)."""
        if self._ref_mean is None:
            self._warmup.append(value)
            if len(self._warmup) >= CUSUM_WARMUP:
                self._ref_mean = float(np.mean(self._warmup))
            return False, 0.0

        deviation = value - self._ref_mean
        self._s_pos = max(0.0, self._s_pos + deviation - self.k)
        self._s_neg = max(0.0, self._s_neg - deviation - self.k)
        magnitude = max(self._s_pos, self._s_neg)

        if magnitude > self.h:
            # Reset after firing so the detector keeps running
            self._s_pos = 0.0
            self._s_neg = 0.0
            return True, magnitude
        return False, magnitude

    def reset(self):
        self._s_pos = 0.0
        self._s_neg = 0.0


class PSIDetector:
    """PSI-based slow drift detection over sliding windows of 1,000–5,000 transactions."""

    def __init__(
        self,
        reference_size: int = PSI_REFERENCE_SIZE,
        window_size: int = PSI_WINDOW_SIZE,
    ):
        self._reference_size = reference_size
        self._window_size = window_size
        self._reference: Deque[float] = deque(maxlen=reference_size)
        self._current: Deque[float] = deque(maxlen=window_size)
        self._ref_frozen = False
        self.last_psi: float = 0.0

    def update(self, value: float) -> Tuple[bool, float, str]:
        """Returns (alert_fired, psi_value, level: 'warmup'|'ok'|'warn'|'alert')."""
        if not self._ref_frozen:
            self._reference.append(value)
            if len(self._reference) >= self._reference_size:
                self._ref_frozen = True
            return False, 0.0, "warmup"

        self._current.append(value)
        if len(self._current) < self._window_size:
            return False, 0.0, "ok"

        psi = _compute_psi(
            np.array(list(self._reference)),
            np.array(list(self._current)),
        )
        self.last_psi = psi

        if psi > PSI_ALERT_THRESHOLD:
            return True, psi, "alert"
        if psi > PSI_WARN_THRESHOLD:
            return False, psi, "warn"
        return False, psi, "ok"


class DriftDetector:
    """Orchestrates CUSUM + PSI and applies threshold adjustments."""

    def __init__(
        self,
        base_block_threshold: float = 0.70,
        base_review_threshold: float = 0.40,
    ):
        self.cusum = CUSUMDetector()
        self.psi = PSIDetector()
        self.base_block_threshold = base_block_threshold
        self.base_review_threshold = base_review_threshold
        self._block_threshold = base_block_threshold
        self._review_threshold = base_review_threshold
        self.retrain_requested: bool = False

    def _adjust(self, magnitude: float):
        """
        Exact formula: adjusted = base − (magnitude × 0.15), clamped to floor.
        """
        self._block_threshold = max(
            MINIMUM_FLOOR,
            self.base_block_threshold - (magnitude * ADJUSTMENT_COEFFICIENT),
        )
        self._review_threshold = max(
            MINIMUM_FLOOR,
            self.base_review_threshold - (magnitude * ADJUSTMENT_COEFFICIENT),
        )

    def update(self, feature_value: float) -> dict:
        """Feed one observation; returns current drift state."""
        cusum_fired, cusum_mag = self.cusum.update(feature_value)
        psi_fired, psi_val, psi_level = self.psi.update(feature_value)

        if cusum_fired:
            # Normalise CUSUM magnitude to [0,1] by dividing by threshold
            self._adjust(cusum_mag / CUSUM_H)

        if psi_fired:
            self._adjust(psi_val)
            self.retrain_requested = True

        return {
            "cusum_fired": cusum_fired,
            "cusum_magnitude": cusum_mag,
            "psi_value": psi_val,
            "psi_level": psi_level,
            "block_threshold": self._block_threshold,
            "review_threshold": self._review_threshold,
            "retrain_requested": self.retrain_requested,
        }

    @property
    def block_threshold(self) -> float:
        return self._block_threshold

    @property
    def review_threshold(self) -> float:
        return self._review_threshold

    def acknowledge_retrain(self):
        self.retrain_requested = False
