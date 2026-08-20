"""Tests for core business models: Customer, Account, LoanApplication, Device, IPIdentity, Transaction, Event."""
import uuid
from datetime import datetime, timezone, timedelta

import pytest
from sqlalchemy import exc
from sqlalchemy.orm import Session

from app.core.database import Base, engine, SessionLocal
from app.models import (
    Customer,
    Account,
    LoanApplication,
    Device,
    IPIdentity,
    Transaction,
    Event,
    CustomerStatus,
    AccountType,
    AccountStatus,
    ApplicationStatus,
    ApplicationType,
    TransactionStatus,
    TransactionType,
)


@pytest.fixture
def db_session() -> Session:
    """Provide a fresh database session for each test."""
    connection = engine.connect()
    transaction = connection.begin()
    session = SessionLocal(bind=connection)

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def sample_customer(db_session: Session) -> Customer:
    """Create a sample customer."""
    customer = Customer(
        external_customer_id="cust_001",
        first_name="John",
        last_name="Doe",
        email="john@example.com",
        phone="+1-555-0100",
        date_of_birth=datetime(1990, 1, 1).date(),
        status=CustomerStatus.ACTIVE,
    )
    db_session.add(customer)
    db_session.commit()
    return customer


@pytest.fixture
def sample_account(db_session: Session, sample_customer: Customer) -> Account:
    """Create a sample account."""
    account = Account(
        external_account_id="acc_001",
        customer_id=sample_customer.id,
        account_type=AccountType.CHECKING,
        status=AccountStatus.ACTIVE,
    )
    db_session.add(account)
    db_session.commit()
    return account


@pytest.fixture
def sample_device(db_session: Session) -> Device:
    """Create a sample device."""
    now = datetime.now(timezone.utc)
    device = Device(
        device_identifier="dev_abc123",
        device_type="mobile",
        operating_system="iOS",
        first_seen_at=now,
        last_seen_at=now,
    )
    db_session.add(device)
    db_session.commit()
    return device


@pytest.fixture
def sample_ip(db_session: Session) -> IPIdentity:
    """Create a sample IP identity."""
    now = datetime.now(timezone.utc)
    ip = IPIdentity(
        ip_address="192.0.2.1",
        ip_version="v4",
        first_seen_at=now,
        last_seen_at=now,
    )
    db_session.add(ip)
    db_session.commit()
    return ip


class TestCustomer:
    def test_customer_creation(self, db_session: Session) -> None:
        customer = Customer(
            external_customer_id="test_cust",
            first_name="Jane",
            last_name="Smith",
            email="jane@example.com",
        )
        db_session.add(customer)
        db_session.commit()

        retrieved = db_session.query(Customer).filter_by(
            external_customer_id="test_cust"
        ).first()
        assert retrieved is not None
        assert retrieved.first_name == "Jane"

    def test_customer_unique_external_id(
        self, db_session: Session, sample_customer: Customer
    ) -> None:
        duplicate = Customer(
            external_customer_id=sample_customer.external_customer_id,
            first_name="Duplicate",
            last_name="Customer",
            email="dup@example.com",
        )
        db_session.add(duplicate)
        with pytest.raises(exc.IntegrityError):
            db_session.commit()

    def test_customer_timestamps(self, db_session: Session) -> None:
        customer = Customer(
            external_customer_id="time_test",
            first_name="Time",
            last_name="Tester",
            email="time@example.com",
        )
        db_session.add(customer)
        db_session.commit()

        assert customer.created_at is not None
        assert customer.updated_at is not None
        assert customer.created_at == customer.updated_at


class TestAccount:
    def test_account_creation(self, db_session: Session, sample_customer: Customer) -> None:
        account = Account(
            external_account_id="test_acc",
            customer_id=sample_customer.id,
            account_type=AccountType.SAVINGS,
        )
        db_session.add(account)
        db_session.commit()

        retrieved = db_session.query(Account).filter_by(
            external_account_id="test_acc"
        ).first()
        assert retrieved is not None
        assert retrieved.account_type == AccountType.SAVINGS

    def test_account_unique_external_id(
        self, db_session: Session, sample_account: Account
    ) -> None:
        duplicate = Account(
            external_account_id=sample_account.external_account_id,
            customer_id=sample_account.customer_id,
            account_type=AccountType.CREDIT,
        )
        db_session.add(duplicate)
        with pytest.raises(exc.IntegrityError):
            db_session.commit()

    def test_account_foreign_key_cascade(
        self, db_session: Session, sample_customer: Customer
    ) -> None:
        account = Account(
            external_account_id="cascade_test",
            customer_id=sample_customer.id,
            account_type=AccountType.LOAN,
        )
        db_session.add(account)
        db_session.commit()

        db_session.delete(sample_customer)
        db_session.commit()

        retrieved = db_session.query(Account).filter_by(id=account.id).first()
        assert retrieved is None  # cascaded delete

    def test_account_customer_relationship(
        self, db_session: Session, sample_account: Account
    ) -> None:
        retrieved_account = db_session.query(Account).filter_by(
            id=sample_account.id
        ).first()
        assert retrieved_account.customer is not None
        assert retrieved_account.customer.external_customer_id == "cust_001"


class TestLoanApplication:
    def test_loanapp_creation(
        self, db_session: Session, sample_customer: Customer, sample_account: Account
    ) -> None:
        app = LoanApplication(
            external_application_id="app_001",
            customer_id=sample_customer.id,
            account_id=sample_account.id,
            application_amount=5000.00,
            application_type=ApplicationType.PERSONAL,
            submitted_at=datetime.now(timezone.utc),
        )
        db_session.add(app)
        db_session.commit()

        retrieved = db_session.query(LoanApplication).filter_by(
            external_application_id="app_001"
        ).first()
        assert retrieved is not None
        assert float(retrieved.application_amount) == 5000.00

    def test_loanapp_negative_amount_rejected(
        self, db_session: Session, sample_customer: Customer
    ) -> None:
        app = LoanApplication(
            external_application_id="bad_amount",
            customer_id=sample_customer.id,
            application_amount=-1000.00,
            application_type=ApplicationType.AUTO,
            submitted_at=datetime.now(timezone.utc),
        )
        db_session.add(app)
        with pytest.raises(exc.IntegrityError):
            db_session.commit()


class TestDevice:
    def test_device_creation(self, db_session: Session) -> None:
        now = datetime.now(timezone.utc)
        device = Device(
            device_identifier="dev_xyz",
            device_type="laptop",
            operating_system="Windows",
            first_seen_at=now,
            last_seen_at=now,
        )
        db_session.add(device)
        db_session.commit()

        retrieved = db_session.query(Device).filter_by(
            device_identifier="dev_xyz"
        ).first()
        assert retrieved is not None
        assert retrieved.device_type == "laptop"

    def test_device_unique_identifier(self, db_session: Session, sample_device: Device) -> None:
        duplicate = Device(
            device_identifier=sample_device.device_identifier,
            device_type="tablet",
            operating_system="Android",
            first_seen_at=datetime.now(timezone.utc),
            last_seen_at=datetime.now(timezone.utc),
        )
        db_session.add(duplicate)
        with pytest.raises(exc.IntegrityError):
            db_session.commit()


class TestIPIdentity:
    def test_ip_creation(self, db_session: Session) -> None:
        now = datetime.now(timezone.utc)
        ip = IPIdentity(
            ip_address="203.0.113.42",
            ip_version="v4",
            first_seen_at=now,
            last_seen_at=now,
        )
        db_session.add(ip)
        db_session.commit()

        # Query by id, not the INET column: psycopg3 doesn't auto-cast a
        # plain string bind parameter for comparison against INET, so
        # filter_by(ip_address="...") fails at the database level
        # (unrelated to whether the row was actually created correctly).
        retrieved = db_session.query(IPIdentity).filter_by(id=ip.id).first()
        assert retrieved is not None
        assert str(retrieved.ip_address) == "203.0.113.42"

    def test_ip_unique_address(self, db_session: Session, sample_ip: IPIdentity) -> None:
        duplicate = IPIdentity(
            ip_address=str(sample_ip.ip_address),
            ip_version="v4",
            first_seen_at=datetime.now(timezone.utc),
            last_seen_at=datetime.now(timezone.utc),
        )
        db_session.add(duplicate)
        with pytest.raises(exc.IntegrityError):
            db_session.commit()


class TestTransaction:
    def test_transaction_creation(
        self,
        db_session: Session,
        sample_customer: Customer,
        sample_account: Account,
        sample_device: Device,
        sample_ip: IPIdentity,
    ) -> None:
        txn = Transaction(
            external_transaction_id="txn_001",
            customer_id=sample_customer.id,
            account_id=sample_account.id,
            device_id=sample_device.id,
            ip_identity_id=sample_ip.id,
            amount=100.50,
            currency="USD",
            transaction_type=TransactionType.TRANSFER,
            occurred_at=datetime.now(timezone.utc),
        )
        db_session.add(txn)
        db_session.commit()

        retrieved = db_session.query(Transaction).filter_by(
            external_transaction_id="txn_001"
        ).first()
        assert retrieved is not None
        assert float(retrieved.amount) == 100.50

    def test_transaction_without_device_ip(
        self, db_session: Session, sample_customer: Customer, sample_account: Account
    ) -> None:
        txn = Transaction(
            external_transaction_id="txn_no_device",
            customer_id=sample_customer.id,
            account_id=sample_account.id,
            device_id=None,
            ip_identity_id=None,
            amount=50.00,
            currency="USD",
            transaction_type=TransactionType.DEPOSIT,
            occurred_at=datetime.now(timezone.utc),
        )
        db_session.add(txn)
        db_session.commit()

        retrieved = db_session.query(Transaction).filter_by(
            external_transaction_id="txn_no_device"
        ).first()
        assert retrieved is not None
        assert retrieved.device_id is None
        assert retrieved.ip_identity_id is None

    def test_transaction_negative_amount_rejected(
        self, db_session: Session, sample_customer: Customer, sample_account: Account
    ) -> None:
        txn = Transaction(
            external_transaction_id="bad_txn",
            customer_id=sample_customer.id,
            account_id=sample_account.id,
            amount=-99.99,
            currency="USD",
            transaction_type=TransactionType.WITHDRAWAL,
            occurred_at=datetime.now(timezone.utc),
        )
        db_session.add(txn)
        with pytest.raises(exc.IntegrityError):
            db_session.commit()

    def test_transaction_recent_history_query(
        self, db_session: Session, sample_customer: Customer, sample_account: Account
    ) -> None:
        now = datetime.now(timezone.utc)
        for i in range(3):
            txn = Transaction(
                external_transaction_id=f"history_{i}",
                customer_id=sample_customer.id,
                account_id=sample_account.id,
                amount=10.00 * (i + 1),
                currency="USD",
                transaction_type=TransactionType.PAYMENT,
                occurred_at=now - timedelta(hours=i),
            )
            db_session.add(txn)
        db_session.commit()

        recent = (
            db_session.query(Transaction)
            .filter_by(customer_id=sample_customer.id)
            .order_by(Transaction.occurred_at.desc())
            .limit(5)
            .all()
        )
        assert len(recent) == 3
        assert float(recent[0].amount) == 10.00


class TestEvent:
    def test_event_creation_with_all_refs(
        self,
        db_session: Session,
        sample_customer: Customer,
        sample_account: Account,
    ) -> None:
        now = datetime.now(timezone.utc)
        txn = Transaction(
            external_transaction_id="evt_txn",
            customer_id=sample_customer.id,
            account_id=sample_account.id,
            amount=25.00,
            currency="USD",
            transaction_type=TransactionType.WITHDRAWAL,
            occurred_at=now,
        )
        db_session.add(txn)
        db_session.commit()

        event = Event(
            external_event_id="evt_001",
            event_type="transaction.completed",
            customer_id=sample_customer.id,
            account_id=sample_account.id,
            transaction_id=txn.id,
            occurred_at=now,
            received_at=now,
            payload={"status": "completed"},
        )
        db_session.add(event)
        db_session.commit()

        retrieved = db_session.query(Event).filter_by(
            external_event_id="evt_001"
        ).first()
        assert retrieved is not None
        assert retrieved.transaction_id == txn.id

    def test_event_without_transaction(
        self, db_session: Session, sample_customer: Customer
    ) -> None:
        now = datetime.now(timezone.utc)
        event = Event(
            external_event_id="evt_no_txn",
            event_type="account.created",
            customer_id=sample_customer.id,
            account_id=None,
            transaction_id=None,
            occurred_at=now,
            received_at=now,
        )
        db_session.add(event)
        db_session.commit()

        retrieved = db_session.query(Event).filter_by(
            external_event_id="evt_no_txn"
        ).first()
        assert retrieved is not None
        assert retrieved.transaction_id is None
        assert retrieved.account_id is None

    def test_event_recent_history_query(
        self, db_session: Session, sample_customer: Customer
    ) -> None:
        now = datetime.now(timezone.utc)
        for i in range(3):
            event = Event(
                external_event_id=f"evt_hist_{i}",
                event_type="test.event",
                customer_id=sample_customer.id,
                occurred_at=now - timedelta(minutes=i),
                received_at=now,
            )
            db_session.add(event)
        db_session.commit()

        recent = (
            db_session.query(Event)
            .filter_by(customer_id=sample_customer.id)
            .order_by(Event.occurred_at.desc())
            .limit(10)
            .all()
        )
        assert len(recent) == 3
