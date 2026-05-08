"""
Layer 8 — Feedback Loop & Deployment

Two labeling paths:
  1. Automated outcome-based labeling (~85% of labels)
     - Chargeback confirmed → label = fraud
     - Step-up auth cleared → label = legitimate
  2. Manual analyst queue (NOVEL-FLAG without automated outcome)
     - SLA: 4h high-value  /  24h standard
     - Uncertain analyst labels are EXCLUDED from retrain data

Shadow deployment:
  - Retrained models run in parallel (shadow path) without affecting traffic
  - If offline metrics are stable, trigger blue-green rollout: 10%→25%→50%→100%
  - Automatic rollback on metric degradation
"""
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional

from .models import CAPEDecision, RoutingDecision


class AnalystConfidence(str, Enum):
    CERTAIN = "certain"
    PROBABLE = "probable"
    UNCERTAIN = "uncertain"   # excluded from retrain data


@dataclass
class AutomatedLabel:
    trans_num: str
    label: int  # 0 = legitimate, 1 = fraud
    source: str  # "chargeback" | "step_up_cleared"
    timestamp: float = field(default_factory=time.time)


@dataclass
class AnalystLabel:
    trans_num: str
    label: int
    confidence: AnalystConfidence
    timestamp: float = field(default_factory=time.time)


@dataclass
class ShadowScore:
    trans_num: str
    production_decision: RoutingDecision
    shadow_decision: RoutingDecision
    shadow_score: float
    timestamp: float = field(default_factory=time.time)


# Blue-green rollout stages (percentage of live traffic)
ROLLOUT_STAGES = [10, 25, 50, 100]


class FeedbackLoop:
    """Operationalized feedback loop with analyst queue and automated labeling."""

    HIGH_VALUE_THRESHOLD = 500.0   # USD; transactions above this get 4h SLA
    HIGH_VALUE_SLA_HRS = 4
    STANDARD_SLA_HRS = 24

    def __init__(self):
        self._analyst_queue: List[Dict] = []
        self._automated_labels: List[AutomatedLabel] = []
        self._analyst_labels: List[AnalystLabel] = []
        self._shadow_scores: List[ShadowScore] = []
        self._retrain_dataset: List[Dict] = []
        self._rollout_stage_idx: int = 0
        self._shadow_model_active: bool = False

    # ------------------------------------------------------------------
    # Automated labeling
    # ------------------------------------------------------------------

    def record_chargeback(self, trans_num: str):
        """Chargeback confirmed → automated fraud label."""
        lbl = AutomatedLabel(trans_num=trans_num, label=1, source="chargeback")
        self._automated_labels.append(lbl)
        self._retrain_dataset.append(
            {"trans_num": trans_num, "label": 1, "source": "automated_chargeback"}
        )

    def record_step_up_cleared(self, trans_num: str):
        """Step-up auth cleared → automated legitimate label."""
        lbl = AutomatedLabel(trans_num=trans_num, label=0, source="step_up_cleared")
        self._automated_labels.append(lbl)
        self._retrain_dataset.append(
            {"trans_num": trans_num, "label": 0, "source": "automated_step_up"}
        )

    # ------------------------------------------------------------------
    # Analyst queue
    # ------------------------------------------------------------------

    def enqueue_for_review(self, decision: CAPEDecision, amount: float):
        """Routes NOVEL-FLAG cases without automated outcomes to analyst queue."""
        sla = (
            self.HIGH_VALUE_SLA_HRS
            if amount >= self.HIGH_VALUE_THRESHOLD
            else self.STANDARD_SLA_HRS
        )
        self._analyst_queue.append(
            {
                "trans_num": decision.trans_num,
                "decision": decision.decision.value,
                "score": decision.point_estimate,
                "interval_width": decision.interval_width,
                "reason_codes": decision.reason_codes,
                "queued_at": time.time(),
                "sla_hours": sla,
            }
        )

    def submit_analyst_label(
        self, trans_num: str, label: int, confidence: AnalystConfidence
    ):
        """
        Record analyst decision.
        Uncertain labels are stored for audit but NOT added to retrain data.
        """
        al = AnalystLabel(trans_num=trans_num, label=label, confidence=confidence)
        self._analyst_labels.append(al)
        if confidence != AnalystConfidence.UNCERTAIN:
            self._retrain_dataset.append(
                {
                    "trans_num": trans_num,
                    "label": label,
                    "source": f"analyst_{confidence.value}",
                }
            )

    # ------------------------------------------------------------------
    # Shadow deployment
    # ------------------------------------------------------------------

    def activate_shadow_model(self):
        self._shadow_model_active = True
        self._rollout_stage_idx = 0

    def record_shadow_score(
        self,
        trans_num: str,
        production_decision: RoutingDecision,
        shadow_decision: RoutingDecision,
        shadow_score: float,
    ):
        self._shadow_scores.append(
            ShadowScore(
                trans_num=trans_num,
                production_decision=production_decision,
                shadow_decision=shadow_decision,
                shadow_score=shadow_score,
            )
        )

    def advance_rollout(self) -> Optional[int]:
        """Advance to next traffic split stage. Returns new pct or None if complete."""
        if self._rollout_stage_idx < len(ROLLOUT_STAGES) - 1:
            self._rollout_stage_idx += 1
        return ROLLOUT_STAGES[self._rollout_stage_idx]

    def rollback(self):
        """Revert shadow model; production model retakes 100% of traffic."""
        self._shadow_model_active = False
        self._rollout_stage_idx = 0

    @property
    def live_traffic_pct(self) -> int:
        return ROLLOUT_STAGES[self._rollout_stage_idx] if self._shadow_model_active else 0

    # ------------------------------------------------------------------
    # Data access
    # ------------------------------------------------------------------

    def get_retrain_dataset(self) -> List[Dict]:
        return list(self._retrain_dataset)

    def get_analyst_queue(self) -> List[Dict]:
        return list(self._analyst_queue)

    def get_shadow_scores(self) -> List[ShadowScore]:
        return list(self._shadow_scores)
