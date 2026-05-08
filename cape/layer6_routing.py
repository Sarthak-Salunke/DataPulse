"""
Layer 6 — Routing Decision

Every transaction that reaches this layer exits with exactly one of three outcomes:

  BLOCK       — high fraud score + narrow interval (confident fraud)
  APPROVE     — low fraud score  + narrow interval (confident legitimate)
  NOVEL-FLAG  — wide interval OR score in review band (model uncertainty)

NOVEL-FLAG actions are channel-aware because step-up authentication is not
possible on all channels (POS, ATM, recurring billing).
"""
from typing import Optional

from .models import RoutingDecision, Channel, CAPEDecision

# Channel-specific action for NOVEL-FLAG decisions
CHANNEL_ACTIONS = {
    Channel.WEB:       "step_up_auth_otp",
    Channel.MOBILE:    "step_up_auth_biometric",
    Channel.POS:       "soft_decline_retry_pin",
    Channel.ATM:       "hard_hold_contact_customer",
    Channel.RECURRING: "manual_review_do_not_block",
    Channel.B2B_BATCH: "analyst_queue_4hr_sla",
}

# Default action when channel is unknown
_FALLBACK_ACTION = "analyst_queue_4hr_sla"


def route(
    trans_num: str,
    point_estimate: float,
    interval_lower: float,
    interval_upper: float,
    interval_width: float,
    feature_version: str,
    channel: Channel,
    block_threshold: float = 0.70,
    review_threshold: float = 0.40,
    novel_interval_threshold: float = 0.30,
    scorer_scores: Optional[dict] = None,
    shap_top3: Optional[list] = None,
    reason_codes: Optional[list] = None,
    drift_adjusted_threshold: Optional[float] = None,
) -> CAPEDecision:
    """
    Applies routing logic and returns a fully populated CAPEDecision.

    Logic:
      1. Wide interval → NOVEL-FLAG regardless of point estimate
      2. High score + narrow → BLOCK
      3. Low score  + narrow → APPROVE
      4. Score in review band → NOVEL-FLAG
    """
    is_novel = interval_width > novel_interval_threshold
    in_review_band = review_threshold <= point_estimate < block_threshold

    if is_novel or in_review_band:
        decision = RoutingDecision.NOVEL_FLAG
        channel_action = CHANNEL_ACTIONS.get(channel, _FALLBACK_ACTION)
    elif point_estimate >= block_threshold:
        decision = RoutingDecision.BLOCK
        channel_action = None
    else:
        decision = RoutingDecision.APPROVE
        channel_action = None

    return CAPEDecision(
        trans_num=trans_num,
        decision=decision,
        point_estimate=point_estimate,
        interval_lower=interval_lower,
        interval_upper=interval_upper,
        interval_width=interval_width,
        feature_version=feature_version,
        scorer_scores=scorer_scores,
        shap_top3=shap_top3,
        reason_codes=reason_codes,
        channel_action=channel_action,
        drift_adjusted_threshold=drift_adjusted_threshold,
    )
