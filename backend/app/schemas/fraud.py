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
