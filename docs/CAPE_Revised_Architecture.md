# CAPE: Confidence-Aware Progressive Escalation
## Revised Architecture — Incorporating Critique Fixes

---

## Overview

CAPE is a fraud detection architecture built around a single core insight: **model uncertainty is a first-class signal**. Instead of collapsing ensemble predictions into one number, CAPE routes transactions based on *how confident the system is* in its own prediction — not just whether the prediction is fraudulent or not.

The original design was conceptually sound. This revised version fixes all critical production failures, closes identified gaps, and preserves the architectural intent.

---

## What Changed and Why

| Original Design | Problem | Revised Design |
|---|---|---|
| Count-Min Sketch as the gate | CMS counts frequency, cannot determine normality | Welford per-user baseline + CMS for velocity only |
| 5-feature Isolation Forest gate | Adversarially fragile; probeable | Welford baseline + invisible device signals + velocity CMS |
| LSTM sequence embedder | Breaks stateless scaling; requires stateful Redis lookup on critical path | EWMA recency feature — O(1), fully stateless |
| No cold-start handling | New users/merchants are highest-risk; no profile to deviate from | Explicit cold-start path with tighter static thresholds |
| Static CP calibration set | CP guarantees collapse under the exact drift PSI detects | Online conformal prediction with rolling calibration window |
| PSI-only drift detection | PSI is batch; lags minutes-to-hours during live attacks | PSI (slow drift) + CUSUM (fast drift, detects in ~50 transactions) |
| Vague threshold widening | "Widens thresholds" is undefined; unpredictable under drift | PSI-magnitude-proportional threshold adjustment with explicit cap |
| Novel-flag → step-up (all channels) | Step-up is impossible on POS, ATM, recurring billing | Channel-aware action map per novel-flag routing |
| No feedback loop specification | "Feed labels back" is not an architecture | Analyst queue, triage SLA, outcome-based automated labeling |
| No feature store | Feature computation is the hardest problem; train-serve skew risk | Explicit feature store layer (pre-computed + on-the-fly) |
| No graph signal | Fraud rings are completely invisible | Lightweight pre-computed graph features |
| No explainability | Regulatory requirement under RBI/PSD2 for declined transactions | SHAP values computed and cached per decision |
| No deployment strategy | Every retrain is a hard cutover; production risk event | Shadow scoring path + blue-green traffic rollout |

---

## Revised Architecture

### Layer 0 — Feature Store

All features originate here. This layer is explicit in the revised design because train-serve skew — where features computed at training time differ from features computed at inference time — is the most common source of silent accuracy degradation in production fraud systems.

**Pre-computed features (updated async, available in <1ms):**
- Per-user: 30-day spend by merchant category, transaction velocity buckets (1min / 10min / 1hr / 24hr), days-since-account-open, device history hash set
- Per-merchant: transaction volume per hour, chargeback rate (rolling 30-day), fraud signal index
- Graph features: count of distinct accounts using this merchant in the last hour, flag if device is shared with any previously flagged account

**On-the-fly features (computed per transaction, <5ms):**
- Amount deviation from user's Welford baseline (z-score)
- Time-since-last-transaction
- Country/IP consistency flag
- Device fingerprint entropy

All features are versioned. The feature store version is logged alongside every model decision to enable post-hoc debugging.

---

### Layer 1 — Cold-Start Router

Before the fast gate, new users and new merchants are identified and routed separately.

**Cold-start criteria:**
- User has fewer than 20 transactions in history
- Merchant has been active for fewer than 7 days

**Cold-start behavior:**
- Bypasses the fast gate entirely — always runs full scoring
- Applies tighter static block/review thresholds (tuned separately from steady-state thresholds)
- Graduated exit: user/merchant transitions to normal routing after cold-start criteria are cleared

This is not optional. New users and merchants are disproportionately targeted precisely because they have no behavioral baseline to deviate from.

---

### Layer 2 — Fast Gate (Revised)

The gate's job is to identify transactions that are so statistically ordinary for this specific user that running the full scoring pipeline adds no value. It must output a binary: **escalate** or **pass**.

**Gate components:**

1. **Welford per-user baseline checker** (~100 bytes per user, O(1) update)
   - Maintains online mean and variance for each feature per user
   - Transaction clears the gate only if all key features fall within N standard deviations of the user's historical distribution
   - N is a tunable parameter; default N=2.5 (approximately 99% of normal traffic)

2. **Velocity CMS** (Count-Min Sketch, ~2KB per user)
   - Counts transactions in sliding windows (1min, 10min, 1hr)
   - Velocity spike in any window sends the transaction to escalation regardless of Welford result
   - CMS is used only for velocity, not for normality — this is the correct use of the data structure

3. **Invisible device signals** (adversarial robustness requirement)
   - At least 2–3 signals that are not observable by the transacting party: device fingerprint entropy, typing cadence hash (where available), network-layer anomaly flag
   - These prevent a fraud operation from probing the gate's 5 observable features and learning to mimic a safe profile

**Gate output:**
- ~70–75% of traffic passes (sub-1ms path ends here, transaction approved)
- ~25–30% escalates to Layer 3

**Cold-start users never reach this gate.** They are already on the full-scoring path from Layer 1.

---

### Layer 3 — Parallel Scorers

Transactions that do not clear the fast gate are scored by three models in parallel:

1. **Random Forest** — strong on tabular feature interactions, interpretable
2. **Gradient Boosted Trees (XGBoost/LightGBM)** — strong on non-linear patterns, well-calibrated probabilities
3. **Recency-weighted transaction scorer** — replaces the original LSTM

**Why the LSTM was removed:**

The LSTM required per-user transaction history to be fetched from a shared session store (Redis or Cassandra) on the critical path. Under traffic spikes, that lookup becomes the bottleneck and breaks the scalability claim. The replacement is an **Exponentially Weighted Moving Average (EWMA)** of the user's past fraud scores, updated with each transaction. It captures recency-weighted behavioral drift in O(1) with no stateful lookup — just one number stored per user in the feature store.

Each scorer outputs a probability score independently. These three scores are passed to Layer 4 as a vector, not collapsed into a single number.

---

### Layer 4 — Online Conformal Prediction Wrapper

This is the architectural core of CAPE. Instead of a Logistic Regression meta-learner that collapses the three scores into one number, CAPE uses **Online Conformal Prediction (CP)** to wrap the ensemble.

**What CP produces:**

Instead of `fraud_prob = 0.73`, the CP wrapper produces:

```
fraud_prob ∈ [0.61, 0.89] at 95% confidence
interval_width = 0.28
```

**Why interval width matters:**

The width of the interval is an orthogonal signal to the point estimate:
- **Narrow interval** (e.g., 0.71–0.75): the models agree. The score is reliable. Route on the point estimate.
- **Wide interval** (e.g., 0.30–0.85): the models fundamentally disagree. This transaction looks like nothing they were trained on. This is the novel fraud signal — not a high score, but genuine model uncertainty.

This replaces the role of Isolation Forest in the main scoring path. Novel fraud produces wide intervals because the models were never trained on it.

**Critical fix from the critique — online calibration:**

The original design used a static calibration set. CP's mathematical coverage guarantee requires **exchangeability** — calibration data and test data must come from the same distribution. When PSI detects drift (Layer 5), that assumption is violated, and the guarantee collapses.

The fix: maintain a **rolling calibration window** of the most recent N transactions with confirmed outcomes. The CP wrapper recalibrates against this rolling window continuously, not just at training time. This is implemented via `MAPIE` with online update support or equivalent. The rolling calibration set is versioned separately from the base model — independent update schedules, so accuracy changes can be diagnosed as originating from the base model or the calibration.

---

### Layer 5 — Drift Detection (Dual-Signal)

The original design used PSI alone. PSI is a batch metric calculated over windows — it can lag minutes to hours depending on window size. During a coordinated fraud attack, that lag is the entire attack window.

**Revised design uses two complementary signals:**

| Signal | Speed | What it detects |
|---|---|---|
| **CUSUM** (Cumulative Sum control chart) | Fast — detects shift in ~50 transactions | Sudden coordinated attacks, rapid pattern change |
| **PSI** (Population Stability Index) | Slow — detects over sliding window of 1,000–5,000 transactions | Gradual fraud evolution, structural feature distribution shifts |

Both run continuously on the feature stream. Each has its own alert threshold.

**Threshold adjustment formula (fixing the "widens thresholds" vagueness):**

When PSI or CUSUM fires, the block/review thresholds are adjusted as:

```
adjusted_threshold = base_threshold − (drift_signal_magnitude × adjustment_coefficient)
adjustment_coefficient = tunable parameter, default 0.15
cap = adjusted_threshold must not fall below minimum_floor
```

This means severe drift triggers a larger conservative shift. The minimum floor prevents the system from flagging everything during extreme drift — it caps conservatism at a defined level and triggers an urgent retrain alert instead.

**Effect of threshold adjustment:**
- More transactions are routed to the novel-flag bucket
- Fewer are auto-approved
- System degrades gracefully under distribution shift rather than silently producing wrong answers

**Retrain trigger:** PSI exceeding a defined threshold triggers an automated retrain job. The new model enters shadow scoring (Layer 6) before going live.

---

### Layer 6 — Routing Decision and Outputs

Every transaction that reaches this layer exits with one of three outcomes:

**1. BLOCK**
- High fraud score + narrow interval (models confidently agree this is fraud)
- Immediate decline

**2. NOVEL-FLAG**
- Wide interval (models uncertain — transaction looks unlike training data)
- OR: moderate fraud score that falls in the review band
- Action depends on channel (see channel-aware action map below)

**3. APPROVE**
- Low fraud score + narrow interval (models confidently agree this is legitimate)

**Channel-aware action map for NOVEL-FLAG:**

| Channel | Action |
|---|---|
| Web / mobile app | Step-up authentication (OTP, biometric prompt) |
| In-store POS | Soft decline with reason code; card-present retry with PIN |
| ATM withdrawal | Hard hold; contact customer via registered mobile |
| Recurring billing | Flag for manual review; do not block until review complete |
| B2B batch payments | Queue for analyst review; SLA = 4 hours |

Step-up authentication cannot interrupt all channels. This map must be maintained and updated as channels change.

---

### Layer 7 — Explainability (Regulatory Requirement)

Under RBI guidelines, EU PSD2, and equivalent regulations, every declined transaction requires a human-readable reason. This is not optional.

**Implementation:**
- SHAP values are computed for the GBT scorer output (fastest to compute, most interpretable)
- Top 3 contributing features are extracted and mapped to human-readable reason codes
- Reason codes and SHAP values are cached alongside the decision record
- Added latency: ~5–8ms on the uncertain scoring path; zero on fast-gate-approved transactions

**Example output:**
```
Decision: BLOCK
Reason: Transaction amount significantly above user's typical range;
        Merchant category inconsistent with user's 90-day history;
        High transaction velocity in last 10 minutes.
```

---

### Layer 8 — Feedback Loop (Operationalized)

The original design described a feedback loop without specifying the operational pipeline. This is fixed here.

**Two labeling paths:**

1. **Automated outcome-based labeling** (primary, ~85% of labels)
   - Transactions that subsequently result in a chargeback are labeled as fraud automatically
   - Transactions that clear step-up authentication successfully are labeled as legitimate
   - Typical latency: hours to days depending on chargeback reporting cycle

2. **Manual analyst review** (secondary, for novel-flag cases without automatic outcomes)
   - Novel-flag transactions without a clear automated outcome enter the analyst queue
   - SLA: 4 hours for high-value transactions, 24 hours for standard
   - Analyst decisions produce a label with confidence score (certain / probable / uncertain)
   - Uncertain labels are excluded from retraining data

**Why the novel-flag bucket is the most valuable label source:**

Novel-flag transactions are, by definition, things the model hasn't seen before. Labeled outcomes from this bucket specifically expand the model's coverage of emerging fraud patterns. This is the self-feeding knowledge acquisition loop that makes CAPE improve over time rather than decay.

**Model deployment (fixing the hard-cutover risk):**

Every retrained model enters a **shadow scoring** phase before going live:
1. New model runs in parallel with the current production model
2. New model's outputs are logged but not acted on
3. Offline metrics (AUC, precision/recall at operating thresholds) are computed on shadow decisions
4. If metrics are stable or better: gradual traffic rollout (10% → 25% → 50% → 100% over 24–48 hours)
5. If metrics degrade: automatic rollback, alert to model owners

---

## System Properties After Revisions

| Constraint | How CAPE handles it |
|---|---|
| **Accuracy** | Online CP catches novel fraud via interval width; feedback loop with operationalized labeling continuously expands training coverage; SHAP output enables regulatory compliance |
| **Simplicity** | Each layer has one job; no MoE routing complexity; EWMA replaces LSTM complexity; CP wrapper is a thin statistical layer |
| **Scalability** | Fast gate eliminates ~70–75% of traffic before heavy models; Welford and CMS are stateless and scale horizontally with zero coordination; EWMA removes stateful session store from critical path |
| **Reliability under load** | Gate absorbs traffic spikes; dual CUSUM+PSI detects distribution shift at two timescales; threshold adjustment is formulaic and capped; shadow deployment prevents retrain-induced outages |

---

## Honest Tradeoffs

**The fast gate is not perfectly adversarially robust.** Adding invisible device signals significantly raises the bar, but a sufficiently patient fraud operation with access to real device fingerprints (e.g., compromised devices) can still probe the gate over time. Periodic gate feature rotation should be part of the operational playbook.

**Online conformal prediction adds complexity to the calibration pipeline.** Rolling calibration windows require careful management — the window size controls the speed/accuracy tradeoff (smaller window adapts faster but is noisier). This is operational overhead that the original static CP did not have.

**The conformal prediction latency applies to 25–30% of traffic.** The fast-gate-approved majority sees sub-1ms latency. The uncertain minority sees ~10–15ms total (parallel scoring + CP wrapper + SHAP). For most payment systems this is acceptable, but it should be measured in production.

**Graph features have a bootstrap problem.** A new deployment has no graph history. The graph feature layer should be flagged as inactive for the first 30 days of production and enabled once sufficient transaction volume has been recorded.

---

## Implementation Notes

All components use production-ready libraries:

- **Welford baseline:** custom O(1) update, ~100 bytes per user, backed by Redis hash
- **Count-Min Sketch:** Redis HyperLogLog or custom CMS implementation
- **Random Forest / GBT:** `scikit-learn`, `XGBoost`, or `LightGBM`
- **Online Conformal Prediction:** `MAPIE` library with online calibration support
- **CUSUM:** `ruptures` or custom 10-line implementation
- **PSI:** custom 10-line calculation over sliding window
- **SHAP:** `shap` library, TreeExplainer for GBT models
- **Feature store:** `Feast`, `Tecton`, or Redis-backed custom store
- **Shadow deployment:** MLflow, SageMaker, or equivalent model serving platform

None of these components are exotic or experimental. The novelty in CAPE is in how they are wired together and what role each component plays — not in the components themselves.
