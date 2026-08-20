"""AI investigation explanation for a single transaction - advisory only.

Wires together the existing deterministic fraud pipeline (via
app.services.fraud_assessment.assess_transaction - reused as-is, not
reimplemented) with the existing ai/ abstraction (ai/llm/provider.py,
ai/prompts/investigation.py).

CRITICAL: this module only ever READS the already-computed assessment and
DB context to build a prompt, and returns whatever text the LLM produces
as a plain string for display. There is no path from here back into
scoring: nothing in fraud_assessment.py, ml/, or the database is ever
written to based on the LLM's output.

Model artifacts and DB access are unchanged from the existing assessment
flow; this module adds no new database queries beyond a customer/account
join identical in spirit to the one already used by the transactions
listing endpoint.
"""
import logging
import sys
from pathlib import Path
from uuid import UUID

from sqlalchemy.orm import Session, joinedload

sys.path.append(str(Path(__file__).resolve().parents[3]))  # repo root

from ai.llm.provider import BedrockLLMProvider, GroqLLMProvider, LLMProvider  # noqa: E402
from ai.prompts.investigation import build_investigation_prompt  # noqa: E402

from app.core.config import Settings, get_settings
from app.models import Transaction
from app.services.fraud_assessment import TransactionNotFoundError, assess_transaction

logger = logging.getLogger(__name__)

UNAVAILABLE_NO_PROVIDER = "AI explanation is not available: no LLM provider is configured."
UNAVAILABLE_PROVIDER_ERROR = "AI explanation is temporarily unavailable. Please try again later."


def _select_provider(settings: Settings) -> LLMProvider | None:
    """Exactly one explicitly-selected provider, or None if AI_PROVIDER is
    unset/invalid or that provider's required config is missing. No
    fallback between providers - a misconfigured selection just means no
    explanation is available (see generate_explanation below).
    """
    if settings.ai_provider == "groq":
        if not settings.groq_api_key:
            return None
        kwargs = {"api_key": settings.groq_api_key}
        if settings.groq_model:
            kwargs["model"] = settings.groq_model
        return GroqLLMProvider(**kwargs)

    if settings.ai_provider == "bedrock":
        if not settings.bedrock_model_id:
            return None
        return BedrockLLMProvider(region=settings.aws_region, model_id=settings.bedrock_model_id)

    return None


def generate_explanation(db: Session, transaction_id: UUID) -> dict:
    """Build the evidence for one transaction from the existing pipeline +
    DB context, then ask the LLM to explain it. Raises
    TransactionNotFoundError (same as assess_transaction) if the
    transaction doesn't exist.
    """
    # Reuses the existing, already-fast (no full-history replay) assessment
    # path - this is the single source of truth for scores/decision/features.
    assessment = assess_transaction(db, transaction_id)

    txn_row = (
        db.query(Transaction)
        .options(joinedload(Transaction.customer), joinedload(Transaction.account))
        .filter(Transaction.id == transaction_id)
        .first()
    )
    if txn_row is None:
        # Can't happen in practice (assess_transaction above already
        # confirmed existence), but keep the same error type either way.
        raise TransactionNotFoundError(str(transaction_id))

    evidence = {
        "amount": float(txn_row.amount),
        "currency": txn_row.currency,
        "transaction_type": txn_row.transaction_type,
        "status": txn_row.status,
        "occurred_at": txn_row.occurred_at.isoformat(),
        "customer_name": f"{txn_row.customer.first_name} {txn_row.customer.last_name}",
        "customer_external_id": txn_row.customer.external_customer_id,
        "account_type": txn_row.account.account_type,
        "account_external_id": txn_row.account.external_account_id,
        "final_risk_score": assessment["final_risk_score"],
        "risk_level": assessment["risk_level"],
        "decision": assessment["decision"],
        "ml_score": assessment["ml_score"],
        "anomaly_score": assessment["anomaly_score"],
        "rule_score": assessment["rule_score"],
        "triggered_rules": assessment["triggered_rules"],
        "features": assessment["features"],
    }

    settings = get_settings()
    provider = _select_provider(settings)
    if provider is None:
        return {
            "transaction_id": transaction_id,
            "available": False,
            "explanation": UNAVAILABLE_NO_PROVIDER,
        }

    prompt = build_investigation_prompt(evidence)
    try:
        explanation = provider.generate(prompt)
    except Exception:
        # Never leak provider/network error details (or the key) to the
        # client - log server-side only, return a generic message.
        logger.exception("AI explanation provider call failed for transaction %s", transaction_id)
        return {
            "transaction_id": transaction_id,
            "available": False,
            "explanation": UNAVAILABLE_PROVIDER_ERROR,
        }

    return {
        "transaction_id": transaction_id,
        "available": True,
        "explanation": explanation,
    }
