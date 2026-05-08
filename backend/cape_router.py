"""
CAPE FastAPI Router

Exposes the CAPE pipeline via two endpoints:
  POST /api/cape/score     — score a single transaction
  GET  /api/cape/status    — pipeline health / calibration info

The pipeline singleton is initialised once at FastAPI startup via the
`init_cape_pipeline()` function called from main_fastapi.py.
"""
from __future__ import annotations

import os
import sys
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

# Allow imports from project root when running from backend/
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from cape import CAPEPipeline, Transaction, Channel
from cape.model_loader import load_pipeline

router = APIRouter(prefix="/api/cape", tags=["CAPE"])

# Module-level singleton — set by init_cape_pipeline() at startup
_pipeline: Optional[CAPEPipeline] = None


def init_cape_pipeline(deployment_day: int = 0) -> None:
    """Called once at FastAPI startup. Loads trained models if available."""
    global _pipeline
    _pipeline = load_pipeline(deployment_day=deployment_day)


def _get_pipeline() -> CAPEPipeline:
    if _pipeline is None:
        raise HTTPException(status_code=503, detail="CAPE pipeline not initialised")
    return _pipeline


# ── Request / Response models ────────────────────────────────────────────────

class CAPEScoreRequest(BaseModel):
    trans_num: str
    cc_num: str
    amt: float = Field(..., gt=0)
    merchant: str
    category: str
    channel: str = "web"
    device_fingerprint: str = ""
    typing_cadence_hash: str = ""
    network_anomaly_flag: bool = False
    ip_country: str = ""


class CAPEScoreResponse(BaseModel):
    trans_num: str
    decision: str                        # BLOCK | APPROVE | NOVEL-FLAG
    point_estimate: float
    interval_lower: float
    interval_upper: float
    interval_width: float
    feature_version: str
    channel_action: Optional[str]
    scorer_scores: Optional[Dict[str, float]]
    reason_codes: Optional[List[str]]
    shap_top3: Optional[List[Dict[str, Any]]]
    drift_adjusted_threshold: Optional[float]


class CAPEStatusResponse(BaseModel):
    status: str
    calibration_samples: int
    calibration_version: int
    graph_features_enabled: bool
    analyst_queue_depth: int
    retrain_requested: bool


# ── Endpoints ────────────────────────────────────────────────────────────────

@router.post("/score", response_model=CAPEScoreResponse)
def score_transaction(
    body: CAPEScoreRequest,
    pipeline: CAPEPipeline = Depends(_get_pipeline),
):
    """
    Score a single transaction through the full CAPE pipeline.
    Returns routing decision, confidence interval, and reason codes.
    """
    try:
        channel = Channel(body.channel.lower())
    except ValueError:
        channel = Channel.WEB

    txn = Transaction(
        trans_num=body.trans_num,
        cc_num=body.cc_num,
        amt=body.amt,
        merchant=body.merchant,
        category=body.category,
        channel=channel,
        device_fingerprint=body.device_fingerprint,
        typing_cadence_hash=body.typing_cadence_hash,
        network_anomaly_flag=body.network_anomaly_flag,
        ip_country=body.ip_country,
    )

    try:
        decision = pipeline.evaluate(txn)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Scoring error: {exc}")

    return CAPEScoreResponse(
        trans_num=decision.trans_num,
        decision=decision.decision.value,
        point_estimate=round(decision.point_estimate, 4),
        interval_lower=round(decision.interval_lower, 4),
        interval_upper=round(decision.interval_upper, 4),
        interval_width=round(decision.interval_width, 4),
        feature_version=decision.feature_version,
        channel_action=decision.channel_action,
        scorer_scores=decision.scorer_scores,
        reason_codes=decision.reason_codes,
        shap_top3=decision.shap_top3,
        drift_adjusted_threshold=decision.drift_adjusted_threshold,
    )


@router.post("/feedback/chargeback")
def record_chargeback(
    trans_num: str,
    rf_score: float = 0.5,
    gbt_score: float = 0.5,
    ewma_score: float = 0.5,
    pipeline: CAPEPipeline = Depends(_get_pipeline),
):
    """
    Register a chargeback outcome for a past transaction.
    Updates conformal calibration and adds to retrain dataset.
    """
    pipeline.on_chargeback(
        trans_num,
        {"random_forest": rf_score, "gbt": gbt_score, "ewma": ewma_score},
        true_label=1,
    )
    return {"status": "recorded", "trans_num": trans_num, "label": 1}


@router.post("/feedback/step_up_cleared")
def record_step_up_cleared(
    trans_num: str,
    rf_score: float = 0.5,
    gbt_score: float = 0.5,
    ewma_score: float = 0.5,
    pipeline: CAPEPipeline = Depends(_get_pipeline),
):
    """Register a successful step-up authentication (legitimate transaction)."""
    pipeline.on_step_up_cleared(
        trans_num,
        {"random_forest": rf_score, "gbt": gbt_score, "ewma": ewma_score},
    )
    return {"status": "recorded", "trans_num": trans_num, "label": 0}


@router.get("/status", response_model=CAPEStatusResponse)
def pipeline_status(pipeline: CAPEPipeline = Depends(_get_pipeline)):
    """Returns calibration health and operational state of the CAPE pipeline."""
    return CAPEStatusResponse(
        status="healthy",
        calibration_samples=len(pipeline.conformal.calibration),
        calibration_version=pipeline.conformal.calibration.version,
        graph_features_enabled=pipeline._graph_enabled,
        analyst_queue_depth=len(pipeline.feedback.get_analyst_queue()),
        retrain_requested=pipeline.drift.retrain_requested,
    )
