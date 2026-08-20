"""Tests for the reviewer feedback endpoint - submission, update-not-
duplicate semantics, and that feedback never touches an existing
assessment. Uses a plain committed session (like ml/data/seed_demo.py)
rather than the rollback-wrapped fixture in test_models.py, since these
tests go through TestClient's own separate DB session and need the setup
rows to actually be visible to it.
"""
import uuid
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app.core.database import SessionLocal
from app.main import app
from app.models import Account, Customer, Transaction, TransactionFeedback

client = TestClient(app)


@pytest.fixture
def feedback_transaction():
    """A minimal, self-contained test-only transaction - cleaned up after
    the test, never touching the original or demo datasets."""
    db = SessionLocal()
    suffix = uuid.uuid4().hex[:8]

    customer = Customer(
        external_customer_id=f"TEST-FEEDBACK-CUST-{suffix}",
        first_name="Test",
        last_name="Feedback",
        email=f"test.feedback.{suffix}@example.test",
    )
    db.add(customer)
    db.flush()

    account = Account(
        external_account_id=f"TEST-FEEDBACK-ACCT-{suffix}",
        customer_id=customer.id,
        account_type="checking",
    )
    db.add(account)
    db.flush()

    txn = Transaction(
        external_transaction_id=f"TEST-FEEDBACK-TXN-{suffix}",
        customer_id=customer.id,
        account_id=account.id,
        amount=42.00,
        currency="USD",
        transaction_type="payment",
        occurred_at=datetime.now(timezone.utc),
    )
    db.add(txn)
    db.commit()
    txn_id = txn.id

    yield txn_id

    db.query(TransactionFeedback).filter(TransactionFeedback.transaction_id == txn_id).delete()
    db.query(Transaction).filter(Transaction.id == txn_id).delete()
    db.query(Account).filter(Account.id == account.id).delete()
    db.query(Customer).filter(Customer.id == customer.id).delete()
    db.commit()
    db.close()


def test_submit_confirmed_fraud_feedback(feedback_transaction) -> None:
    response = client.post(
        "/api/v1/feedback",
        json={"transaction_id": str(feedback_transaction), "label": "confirmed_fraud"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["label"] == "confirmed_fraud"
    assert body["transaction_id"] == str(feedback_transaction)


def test_submit_confirmed_genuine_feedback(feedback_transaction) -> None:
    response = client.post(
        "/api/v1/feedback",
        json={"transaction_id": str(feedback_transaction), "label": "confirmed_genuine"},
    )
    assert response.status_code == 200
    assert response.json()["label"] == "confirmed_genuine"


def test_resubmitting_feedback_updates_not_duplicates(feedback_transaction) -> None:
    client.post(
        "/api/v1/feedback",
        json={"transaction_id": str(feedback_transaction), "label": "confirmed_fraud"},
    )
    response = client.post(
        "/api/v1/feedback",
        json={"transaction_id": str(feedback_transaction), "label": "confirmed_genuine"},
    )
    assert response.status_code == 200
    assert response.json()["label"] == "confirmed_genuine"

    db = SessionLocal()
    count = (
        db.query(TransactionFeedback)
        .filter(TransactionFeedback.transaction_id == feedback_transaction)
        .count()
    )
    db.close()
    assert count == 1


def test_feedback_does_not_change_assessment(feedback_transaction) -> None:
    before = client.post(
        "/api/v1/fraud/assess", json={"transaction_id": str(feedback_transaction)}
    )
    assert before.status_code == 200
    before_body = before.json()

    client.post(
        "/api/v1/feedback",
        json={"transaction_id": str(feedback_transaction), "label": "confirmed_fraud"},
    )

    after = client.post(
        "/api/v1/fraud/assess", json={"transaction_id": str(feedback_transaction)}
    )
    assert after.status_code == 200
    after_body = after.json()

    for key in (
        "ml_score",
        "anomaly_score",
        "rule_score",
        "final_risk_score",
        "risk_level",
        "decision",
        "triggered_rules",
    ):
        assert before_body[key] == after_body[key]


def test_feedback_for_unknown_transaction_returns_404() -> None:
    response = client.post(
        "/api/v1/feedback",
        json={"transaction_id": str(uuid.uuid4()), "label": "confirmed_fraud"},
    )
    assert response.status_code == 404


def test_get_feedback_before_submission_returns_404(feedback_transaction) -> None:
    response = client.get(f"/api/v1/feedback/{feedback_transaction}")
    assert response.status_code == 404
