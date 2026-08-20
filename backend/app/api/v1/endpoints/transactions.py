"""Transaction listing + ingestion endpoints.

Listing is read-only, backs the dashboard's recent transactions table,
the Transactions browse tab, and the investigation panel - a single ORM
query (with eager-loaded customer/account), not worth an extra layer.

Ingestion (POST) stores a new transaction and immediately runs it through
the existing fraud pipeline via app.services.fraud_assessment.
assess_transaction - no scoring logic lives here, this only stores the
row and calls that same function /fraud/assess already uses.
"""
import logging
from datetime import datetime, timezone

from sqlalchemy import cast, func, or_
from sqlalchemy.dialects.postgresql import INET
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload
from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.database import get_db
from app.models import Account, Customer, Device, IPIdentity, Transaction
from app.schemas.fraud import FraudAssessResponse
from app.schemas.transaction import (
    TransactionCreateRequest,
    TransactionCreateResponse,
    TransactionListResponse,
    TransactionSummary,
)
from app.services.fraud_assessment import assess_transaction

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/transactions", tags=["transactions"])


@router.get("", response_model=TransactionListResponse)
def list_transactions(
    limit: int = Query(20, ge=1, le=200),
    offset: int = Query(0, ge=0),
    search: str | None = Query(
        None, description="Matches transaction ID, customer name, or customer external ID"
    ),
    status: str | None = Query(None, description="Exact transaction status match"),
    db: Session = Depends(get_db),
) -> TransactionListResponse:
    query = db.query(Transaction).options(
        joinedload(Transaction.customer), joinedload(Transaction.account)
    )

    if search:
        # Search is DB-native fields only (no risk/decision - those are
        # computed on demand per transaction, not filterable at this scale).
        pattern = f"%{search}%"
        query = query.join(Customer).filter(
            or_(
                Transaction.external_transaction_id.ilike(pattern),
                Customer.external_customer_id.ilike(pattern),
                (Customer.first_name + " " + Customer.last_name).ilike(pattern),
            )
        )
    if status:
        query = query.filter(Transaction.status == status)

    total = query.with_entities(func.count(Transaction.id)).scalar()
    rows = query.order_by(Transaction.occurred_at.desc()).offset(offset).limit(limit).all()

    items = [
        TransactionSummary(
            id=row.id,
            external_transaction_id=row.external_transaction_id,
            amount=float(row.amount),
            currency=row.currency,
            transaction_type=row.transaction_type,
            status=row.status,
            occurred_at=row.occurred_at,
            customer_external_id=row.customer.external_customer_id,
            customer_name=f"{row.customer.first_name} {row.customer.last_name}",
            account_external_id=row.account.external_account_id,
            account_type=row.account.account_type,
        )
        for row in rows
    ]
    return TransactionListResponse(total=total, items=items)


@router.post("", response_model=TransactionCreateResponse, status_code=status.HTTP_201_CREATED)
def create_transaction(
    payload: TransactionCreateRequest, db: Session = Depends(get_db)
) -> TransactionCreateResponse:
    """Store a new transaction and immediately assess it with the existing
    fraud pipeline - the synchronous request/response IS the real-time
    path for this prototype (see module docstring).
    """
    account = (
        db.query(Account)
        .options(joinedload(Account.customer))
        .filter(Account.external_account_id == payload.external_account_id)
        .first()
    )
    if account is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")

    device = None
    if payload.device_identifier:
        device = (
            db.query(Device)
            .filter(Device.device_identifier == payload.device_identifier)
            .first()
        )
        if device is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device not found")

    ip_identity = None
    if payload.ip_address:
        # psycopg3 doesn't auto-cast a plain string for INET column
        # comparison - cast the bind parameter explicitly.
        ip_identity = (
            db.query(IPIdentity)
            .filter(IPIdentity.ip_address == cast(payload.ip_address, INET))
            .first()
        )
        if ip_identity is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="IP identity not found"
            )

    txn = Transaction(
        external_transaction_id=payload.external_transaction_id,
        customer_id=account.customer_id,
        account_id=account.id,
        device_id=device.id if device else None,
        ip_identity_id=ip_identity.id if ip_identity else None,
        amount=payload.amount,
        currency=payload.currency,
        transaction_type=payload.transaction_type.value,
        occurred_at=payload.occurred_at or datetime.now(timezone.utc),
    )
    db.add(txn)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A transaction with this external_transaction_id already exists",
        )
    db.refresh(txn)

    try:
        assessment = assess_transaction(db, txn.id)
    except FileNotFoundError:
        logger.error("Fraud model artifacts missing - run ml/model.py and ml/anomaly.py")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Fraud model is not available",
        )

    summary = TransactionSummary(
        id=txn.id,
        external_transaction_id=txn.external_transaction_id,
        amount=float(txn.amount),
        currency=txn.currency,
        transaction_type=txn.transaction_type,
        status=txn.status,
        occurred_at=txn.occurred_at,
        customer_external_id=account.customer.external_customer_id,
        customer_name=f"{account.customer.first_name} {account.customer.last_name}",
        account_external_id=account.external_account_id,
        account_type=account.account_type,
    )
    return TransactionCreateResponse(
        transaction=summary, assessment=FraudAssessResponse(**assessment)
    )
