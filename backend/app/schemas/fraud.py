"""Request/response schemas for the fraud assessment endpoint."""
import uuid

from pydantic import BaseModel


class FraudAssessRequest(BaseModel):
    transaction_id: uuid.UUID


class FraudAssessResponse(BaseModel):
    transaction_id: uuid.UUID
    ml_score: float
    anomaly_score: float
    rule_score: float
    final_risk_score: float
    risk_level: str
    decision: str
    triggered_rules: list[str]
    # The point-in-time behavioral feature values that were fed into the
    # model/anomaly/rules for this assessment - lets an analyst see WHY,
    # not just the resulting scores. Already computed as part of scoring;
    # this only exposes them, it does not add any extra computation.
    features: dict[str, float | int | bool]


class RuleConfig(BaseModel):
    name: str
    weight: int
    condition: str


class RulesConfigResponse(BaseModel):
    """Read-only view of the deterministic rule engine and risk aggregation
    constants (ml/rules.py, ml/risk.py) - values are read directly from
    those modules, never duplicated by hand here.
    """

    rules: list[RuleConfig]
    max_rule_score: int
    signal_weights: dict[str, float]
    risk_level_thresholds: dict[str, int]
    decision_by_risk_level: dict[str, str]


class AIExplanationResponse(BaseModel):
    """Advisory-only: a plain-language explanation of an already-computed
    assessment. `available=False` when no LLM provider is configured or
    the provider call failed - explanation is still a friendly message in
    that case, never a stack trace or provider error detail.
    """

    transaction_id: uuid.UUID
    available: bool
    explanation: str
