"""
Layer 4 — Online Conformal Prediction Wrapper

Instead of collapsing three scorer outputs into one number, this layer wraps
the ensemble with split conformal prediction to produce a prediction interval
at CONFIDENCE_LEVEL (default 95%).

Interval width is the primary novel-fraud signal:
  - Narrow interval → models agree → route on point estimate
  - Wide interval   → model disagreement → NOVEL-FLAG regardless of score

Rolling calibration window maintains the CP guarantee under data drift by
continuously recalibrating against confirmed outcomes (not a static set).
The calibration dataset is versioned independently from the base model so
accuracy regressions can be attributed to base model vs calibration drift.
"""
import numpy as np
from collections import deque
from typing import Deque, List, Tuple

CONFIDENCE_LEVEL = 0.95
CALIBRATION_WINDOW_SIZE = 1000
NOVEL_INTERVAL_THRESHOLD = 0.30   # intervals wider than this → NOVEL-FLAG

# Ensemble weights applied before conformal wrapping
_WEIGHTS = {"random_forest": 0.35, "gbt": 0.45, "ewma": 0.20}


def _point_estimate(scorer_outputs: dict) -> float:
    return sum(scorer_outputs.get(k, 0.0) * w for k, w in _WEIGHTS.items())


class RollingCalibrationWindow:
    """Sliding window of (score_vector, confirmed_label) pairs."""

    def __init__(self, maxlen: int = CALIBRATION_WINDOW_SIZE):
        self._data: Deque[Tuple[List[float], int]] = deque(maxlen=maxlen)
        self.version: int = 0

    def add(self, scores: List[float], label: int):
        self._data.append((scores, label))
        self.version += 1

    def __len__(self) -> int:
        return len(self._data)


class ConformalPredictor:
    """
    Online split conformal predictor.

    Nonconformity score = |point_estimate − true_label|.
    The quantile of nonconformity scores at CONFIDENCE_LEVEL gives the
    half-width used to construct the prediction interval.
    """

    def __init__(self, calibration_window_size: int = CALIBRATION_WINDOW_SIZE):
        self.calibration = RollingCalibrationWindow(calibration_window_size)
        self._nonconformity_scores: Deque[float] = deque(maxlen=calibration_window_size)
        self._quantile: float = 0.25   # conservative default before warm-up

    def _recalibrate(self):
        if len(self._nonconformity_scores) < 10:
            return
        arr = np.array(list(self._nonconformity_scores))
        self._quantile = float(np.quantile(arr, CONFIDENCE_LEVEL))

    def predict(
        self, scorer_outputs: dict
    ) -> Tuple[float, float, float, float]:
        """
        Returns (point_estimate, lower_bound, upper_bound, interval_width).
        All values clamped to [0, 1].
        """
        pe = _point_estimate(scorer_outputs)
        half = self._quantile
        lower = max(0.0, pe - half)
        upper = min(1.0, pe + half)
        return pe, lower, upper, upper - lower

    def update_calibration(self, scorer_outputs: dict, true_label: int):
        """
        Called when a confirmed outcome arrives for a past transaction.
        Adds the nonconformity score to the rolling window and recalibrates.
        """
        pe = _point_estimate(scorer_outputs)
        nc = abs(pe - float(true_label))
        self._nonconformity_scores.append(nc)
        self.calibration.add(list(scorer_outputs.values()), true_label)
        self._recalibrate()

    def is_novel(self, interval_width: float) -> bool:
        return interval_width > NOVEL_INTERVAL_THRESHOLD
