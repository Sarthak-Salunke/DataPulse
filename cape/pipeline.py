"""
CAPE Pipeline Orchestrator

Wires all 9 layers into a single evaluate() call.

Evaluation order:
  L0  build feature vector (versioned)
  L5  feed drift detectors first so thresholds are updated before routing
  L1  cold-start check — may override thresholds and skip L2
  L2  fast gate — ~70-75% of traffic exits here as APPROVE
  L3  parallel scorers (RF + GBT + EWMA)
  L4  conformal prediction wrapper → (point_estimate, interval)
  L7  SHAP explainability (for non-fast-pass decisions)
  L6  routing decision (BLOCK / APPROVE / NOVEL-FLAG)
  L8  enqueue NOVEL-FLAG for analyst review; update online state

Graph features are disabled for the first GRAPH_BOOTSTRAP_DAYS to avoid
the bootstrap problem (no graph history on a fresh deployment).
"""
from typing import Optional

from .models import Transaction, CAPEDecision, RoutingDecision
from .layer0_feature_store import FeatureStore
from .layer1_cold_start_router import (
    route_cold_start,
    STEADY_BLOCK_THRESHOLD,
    STEADY_REVIEW_THRESHOLD,
)
from .layer2_fast_gate import FastGate
from .layer3_parallel_scorers import ParallelScorers
from .layer4_conformal import ConformalPredictor
from .layer5_drift_detection import DriftDetector
from .layer6_routing import route
from .layer7_explainability import ExplainabilityLayer
from .layer8_feedback import FeedbackLoop

GRAPH_BOOTSTRAP_DAYS = 30  # graph features inactive for first 30 days of production


class CAPEPipeline:
    def __init__(
        self,
        feature_store: Optional[FeatureStore] = None,
        rf_model=None,
        gbt_model=None,
        deployment_day: int = 0,
        ewma_alpha: float = 0.3,
    ):
        self.feature_store = feature_store or FeatureStore()
        self.fast_gate = FastGate()
        self.scorers = ParallelScorers(rf_model=rf_model, gbt_model=gbt_model, ewma_alpha=ewma_alpha)
        self.conformal = ConformalPredictor()
        self.drift = DriftDetector(
            base_block_threshold=STEADY_BLOCK_THRESHOLD,
            base_review_threshold=STEADY_REVIEW_THRESHOLD,
        )
        self.explainability = ExplainabilityLayer(gbt_model=self.scorers.gbt.get_model())
        self.feedback = FeedbackLoop()
        self.deployment_day = deployment_day
        self._graph_enabled = deployment_day >= GRAPH_BOOTSTRAP_DAYS

    # ------------------------------------------------------------------
    # Primary entry point
    # ------------------------------------------------------------------

    def evaluate(self, txn: Transaction) -> CAPEDecision:
        user_id = str(txn.cc_num)

        # --- Layer 0: Build versioned feature vector ---
        fv = self.feature_store.build_feature_vector(txn)

        # Disable graph features during bootstrap period
        if not self._graph_enabled:
            fv.graph_distinct_accounts_1hr = 0
            fv.graph_shared_device_flagged = False

        # --- Layer 5: Update drift on amount z-score ---
        drift_state = self.drift.update(fv.amount_zscore)
        block_threshold = drift_state["block_threshold"]
        review_threshold = drift_state["review_threshold"]

        # --- Layer 1: Cold-start routing ---
        is_cold_start, cold_thresholds = route_cold_start(txn, self.feature_store)
        if is_cold_start:
            # Tighter thresholds override drift-adjusted ones for cold-start entities
            block_threshold = cold_thresholds["block"]
            review_threshold = cold_thresholds["review"]

        # --- Layer 2: Fast gate (cold-start always bypasses) ---
        if not is_cold_start:
            should_escalate, _gate_reason = self.fast_gate.evaluate(
                txn, fv, self.feature_store
            )
            if not should_escalate:
                # Fast-pass: statistically ordinary transaction — approve immediately
                self._update_online_state(user_id, txn.amt, 0.05)
                return CAPEDecision(
                    trans_num=txn.trans_num,
                    decision=RoutingDecision.APPROVE,
                    point_estimate=0.05,
                    interval_lower=0.0,
                    interval_upper=0.10,
                    interval_width=0.10,
                    feature_version=fv.version,
                )

        # --- Layer 3: Parallel scoring ---
        scorer_outputs = self.scorers.score(fv, user_id, self.feature_store)

        # --- Layer 4: Conformal prediction ---
        pe, lower, upper, width = self.conformal.predict(scorer_outputs)

        # --- Layer 7: Explainability (mandatory for all non-fast-pass decisions) ---
        shap_top3 = self.explainability.compute_shap(fv)
        reason_codes = self.explainability.get_reason_codes(shap_top3)

        # --- Layer 6: Routing ---
        decision = route(
            trans_num=txn.trans_num,
            point_estimate=pe,
            interval_lower=lower,
            interval_upper=upper,
            interval_width=width,
            feature_version=fv.version,
            channel=txn.channel,
            block_threshold=block_threshold,
            review_threshold=review_threshold,
            scorer_scores=scorer_outputs,
            shap_top3=shap_top3,
            reason_codes=reason_codes,
            drift_adjusted_threshold=drift_state.get("block_threshold"),
        )

        # --- Layer 8: Analyst queue for novel flags ---
        if decision.decision == RoutingDecision.NOVEL_FLAG:
            self.feedback.enqueue_for_review(decision, txn.amt)

        # Update online state
        self._update_online_state(user_id, txn.amt, pe)

        return decision

    # ------------------------------------------------------------------
    # Feedback integration
    # ------------------------------------------------------------------

    def on_chargeback(self, trans_num: str, scorer_outputs: dict, true_label: int = 1):
        """Called when a chargeback is confirmed for a past transaction."""
        self.feedback.record_chargeback(trans_num)
        self.conformal.update_calibration(scorer_outputs, true_label)

    def on_step_up_cleared(self, trans_num: str, scorer_outputs: dict):
        """Called when a step-up authentication succeeds."""
        self.feedback.record_step_up_cleared(trans_num)
        self.conformal.update_calibration(scorer_outputs, 0)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _update_online_state(self, user_id: str, amount: float, fraud_score: float):
        self.feature_store.update_welford(user_id, amount)
        self.feature_store.update_last_txn_time(user_id)
        self.feature_store.update_ewma_score(user_id, fraud_score)

    def enable_graph_features(self):
        """Call after GRAPH_BOOTSTRAP_DAYS to activate graph signals."""
        self._graph_enabled = True
