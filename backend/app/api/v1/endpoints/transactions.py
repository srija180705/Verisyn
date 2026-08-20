"""Transaction listing endpoint - read-only, backs the dashboard's recent
transactions table and investigation panel. No repository/service layer -
the query is a single ORM query (with eager-loaded customer/account), not
worth an extra layer.
"""
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload
from fastapi import APIRouter, Depends, Query

from app.core.database import get_db
from app.models import Transaction
from app.schemas.transaction import TransactionListResponse, TransactionSummary

router = APIRouter(prefix="/transactions", tags=["transactions"])


@router.get("", response_model=TransactionListResponse)
def list_transactions(
    limit: int = Query(20, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> TransactionListResponse:
    total = db.query(func.count(Transaction.id)).scalar()
    rows = (
        db.query(Transaction)
        .options(joinedload(Transaction.customer), joinedload(Transaction.account))
        .order_by(Transaction.occurred_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
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
