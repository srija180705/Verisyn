"""Prompt template for explaining an already-computed fraud assessment to
a human investigator.

The evidence dict is prepared entirely by the backend (transaction/
customer/account context plus the scores/features the deterministic
pipeline already produced) - the LLM never sees raw database access, only
this fixed evidence, and its output is only ever displayed as an
explanation. Nothing here feeds back into scoring.
"""

GUARDRAILS = """STRICT RULES:
- Use ONLY the evidence provided below. Do not invent facts, transactions, or history not listed here.
- Do NOT state or imply a different score, risk level, or decision than what is given.
- Do NOT claim to have independently determined that this is or is not fraud - you are explaining an existing automated result, not making a new judgement.
- If the evidence is sparse or inconclusive, say so plainly rather than guessing.
- Keep the explanation concise: 3-5 sentences, plain language, no bullet points, no markdown."""


def build_investigation_prompt(evidence: dict) -> str:
    """Build the prompt for explaining one transaction's fraud assessment.

    `evidence` must contain: amount, currency, transaction_type, status,
    occurred_at, customer_name, customer_external_id, account_type,
    account_external_id, final_risk_score, risk_level, decision, ml_score,
    anomaly_score, rule_score, triggered_rules (list[str]), features (dict).
    """
    triggered = ", ".join(evidence["triggered_rules"]) or "None"
    feature_lines = "\n".join(f"- {key}: {value}" for key, value in evidence["features"].items())

    return f"""You are assisting a fraud analyst at a lending company. You are given the ALREADY-COMPUTED result of an automated fraud detection pipeline (Logistic Regression + Isolation Forest + a rule engine). Your job is ONLY to explain, in plain language, why this transaction received this result.

{GUARDRAILS}

EVIDENCE:
Transaction: {evidence['amount']} {evidence['currency']} ({evidence['transaction_type']}), status={evidence['status']}, occurred_at={evidence['occurred_at']}
Customer: {evidence['customer_name']} ({evidence['customer_external_id']})
Account: {evidence['account_type']} ({evidence['account_external_id']})

Automated result:
- Final risk score: {evidence['final_risk_score']} / 100
- Risk level: {evidence['risk_level']}
- Decision: {evidence['decision']}
- ML model score: {evidence['ml_score']} / 100
- Anomaly score: {evidence['anomaly_score']} / 100
- Rule score: {evidence['rule_score']} / 100
- Triggered rules: {triggered}

Behavioral signals:
{feature_lines}

Write a concise explanation for the analyst of why this transaction received this result, based only on the evidence above."""
