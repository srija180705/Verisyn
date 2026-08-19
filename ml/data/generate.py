"""Synthetic lending/fraud data generator.
Generates a relational dataset (customers, accounts, devices, IP
identities, loan applications, transactions, events) that mirrors the
Phase 2A database schema, with realistic normal behavior plus
deliberately injected suspicious scenarios for later feature engineering
and model training.

Ground-truth fraud labels are produced ONLY as a separate CSV for ML
training - the operational tables (esp. transactions) carry no fraud
label, matching the real system where the label is not known upfront.
"""
import argparse
import csv
import random
import sys
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[2]))
\
ANCHOR_TIME = datetime(2026, 8, 19, 12, 0, 0, tzinfo=timezone.utc)
HISTORY_DAYS = 180

FIRST_NAMES = [
    "James", "Mary", "Robert", "Patricia", "John", "Jennifer", "Michael", "Linda",
    "David", "Elizabeth", "William", "Barbara", "Richard", "Susan", "Joseph", "Jessica",
    "Thomas", "Sarah", "Charles", "Karen", "Priya", "Wei", "Fatima", "Carlos",
    "Amara", "Hiroshi", "Elena", "Omar", "Ingrid", "Kwame", "Sofia", "Dmitri",
    "Aisha", "Lucas", "Mei", "Diego", "Nadia", "Sven", "Yuki", "Ravi",
]
LAST_NAMES = [
    "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis",
    "Rodriguez", "Martinez", "Hernandez", "Lopez", "Gonzalez", "Wilson", "Anderson",
    "Thomas", "Taylor", "Moore", "Jackson", "Martin", "Lee", "Perez", "Thompson",
    "White", "Harris", "Sanchez", "Clark", "Ramirez", "Lewis", "Robinson", "Walker",
    "Patel", "Kim", "Nguyen", "Chen", "Okafor", "Ivanov", "Muller", "Andersson",
]
DEVICE_TYPES = ["mobile", "desktop", "tablet"]
OPERATING_SYSTEMS = {
    "mobile": ["iOS", "Android"],
    "desktop": ["Windows", "macOS", "Linux"],
    "tablet": ["iOS", "Android"],
}
HOME_LOCATIONS = ["US-NY", "US-CA", "US-TX", "US-FL", "US-IL", "US-WA", "US-MA"]
UNUSUAL_LOCATIONS = ["RU-MOW", "NG-LA", "CN-SH", "RO-BU", "VN-HN"]

ACCOUNT_TYPES = ["checking", "savings", "credit", "loan"]
TRANSACTION_TYPES = ["deposit", "withdrawal", "transfer", "payment", "refund"]
APPLICATION_TYPES = ["personal", "auto", "home", "business"]


@dataclass
class GenerationConfig:
    """Configurable dataset sizes and random seed."""

    seed: int = 42
    num_customers: int = 2000
    num_accounts: int = 3000
    num_devices: int = 1000
    num_ip_identities: int = 1000
    num_loan_applications: int = 2000
    num_transactions: int = 20000
    num_events: int = 20000

    suspicious_customer_ratio: float = 0.05
    shared_device_count: int = 15
    shared_ip_count: int = 15


@dataclass
class GeneratedDataset:
    """All generated rows, ready for bulk insert, plus ML labels."""

    customers: list = field(default_factory=list)
    devices: list = field(default_factory=list)
    ip_identities: list = field(default_factory=list)
    accounts: list = field(default_factory=list)
    loan_applications: list = field(default_factory=list)
    transactions: list = field(default_factory=list)
    events: list = field(default_factory=list)
    labels: list = field(default_factory=list)  # ML-only ground truth


def _random_timestamp(rng: random.Random, days_back: int = HISTORY_DAYS) -> datetime:
    """A random timestamp within the last `days_back` days before ANCHOR_TIME."""
    seconds_back = rng.uniform(0, days_back * 24 * 3600)
    return ANCHOR_TIME - timedelta(seconds=seconds_back)


def _random_ip(rng: random.Random) -> str:
    """A plausible-looking public IPv4 address (not exhaustively RFC-valid)."""
    return f"{rng.randint(1, 223)}.{rng.randint(0, 255)}.{rng.randint(0, 255)}.{rng.randint(1, 254)}"


def generate_customers(rng: random.Random, config: GenerationConfig) -> list[dict]:
    customers = []
    for i in range(config.num_customers):
        first = rng.choice(FIRST_NAMES)
        last = rng.choice(LAST_NAMES)
        created_at = _random_timestamp(rng, days_back=HISTORY_DAYS + 365)
        status = rng.choices(
            ["active", "inactive", "suspended"], weights=[90, 7, 3], k=1
        )[0]
        customers.append(
            {
                "id": uuid.uuid4(),
                "external_customer_id": f"CUST-{i:06d}",
                "first_name": first,
                "last_name": last,
                "email": f"{first.lower()}.{last.lower()}.{i}@example.com",
                "phone": f"+1-555-{rng.randint(1000, 9999)}",
                "date_of_birth": (
                    ANCHOR_TIME - timedelta(days=rng.randint(18, 75) * 365)
                ).date(),
                "status": status,
                "created_at": created_at,
                "updated_at": created_at,
                # generator-only fields, stripped before DB insert
                "_home_location": rng.choice(HOME_LOCATIONS),
                "_typical_amount": rng.lognormvariate(4.2, 0.8),  # ~ $50-$300 median
            }
        )
    return customers


def generate_devices(rng: random.Random, config: GenerationConfig) -> list[dict]:
    devices = []
    for i in range(config.num_devices):
        device_type = rng.choice(DEVICE_TYPES)
        first_seen = _random_timestamp(rng, days_back=HISTORY_DAYS + 90)
        last_seen = first_seen + timedelta(
            seconds=rng.uniform(0, (ANCHOR_TIME - first_seen).total_seconds())
        )
        devices.append(
            {
                "id": uuid.uuid4(),
                "device_identifier": f"DEVICE-{i:06d}",
                "device_type": device_type,
                "operating_system": rng.choice(OPERATING_SYSTEMS[device_type]),
                "first_seen_at": first_seen,
                "last_seen_at": last_seen,
                "created_at": first_seen,
                "updated_at": last_seen,
            }
        )
    return devices


def generate_ip_identities(rng: random.Random, config: GenerationConfig) -> list[dict]:
    ip_identities = []
    seen_addresses: set[str] = set()
    while len(ip_identities) < config.num_ip_identities:
        address = _random_ip(rng)
        if address in seen_addresses:
            continue
        seen_addresses.add(address)
        first_seen = _random_timestamp(rng, days_back=HISTORY_DAYS + 90)
        last_seen = first_seen + timedelta(
            seconds=rng.uniform(0, (ANCHOR_TIME - first_seen).total_seconds())
        )
        ip_identities.append(
            {
                "id": uuid.uuid4(),
                "ip_address": address,
                "ip_version": "v4",
                "first_seen_at": first_seen,
                "last_seen_at": last_seen,
                "created_at": first_seen,
                "updated_at": last_seen,
            }
        )
    return ip_identities


def generate_accounts(
    rng: random.Random, config: GenerationConfig, customers: list[dict]
) -> list[dict]:
    """Every customer gets >=1 account; remaining accounts distributed randomly."""
    accounts = []
    account_index = 0

    def make_account(customer: dict) -> dict:
        nonlocal account_index
        created_at = customer["created_at"] + timedelta(
            seconds=rng.uniform(0, 3600 * 24 * 30)
        )
        account = {
            "id": uuid.uuid4(),
            "external_account_id": f"ACCT-{account_index:06d}",
            "customer_id": customer["id"],
            "account_type": rng.choices(
                ACCOUNT_TYPES, weights=[40, 30, 20, 10], k=1
            )[0],
            "status": rng.choices(
                ["active", "inactive", "closed", "suspended"],
                weights=[88, 6, 4, 2],
                k=1,
            )[0],
            "created_at": created_at,
            "updated_at": created_at,
        }
        account_index += 1
        return account

    for customer in customers:
        accounts.append(make_account(customer))

    remaining = config.num_accounts - len(customers)
    for _ in range(max(remaining, 0)):
        customer = rng.choice(customers)
        accounts.append(make_account(customer))

    return accounts


def generate_loan_applications(
    rng: random.Random,
    config: GenerationConfig,
    customers: list[dict],
    accounts_by_customer: dict,
) -> list[dict]:
    applications = []
    for i in range(config.num_loan_applications):
        customer = rng.choice(customers)
        customer_accounts = accounts_by_customer.get(customer["id"], [])
        has_account = customer_accounts and rng.random() < 0.8
        account = rng.choice(customer_accounts) if has_account else None

        submitted_at = _random_timestamp(rng)
        applications.append(
            {
                "id": uuid.uuid4(),
                "external_application_id": f"APP-{i:06d}",
                "customer_id": customer["id"],
                "account_id": account["id"] if account else None,
                "application_amount": round(rng.lognormvariate(8.7, 0.7), 2),
                "application_type": rng.choices(
                    APPLICATION_TYPES, weights=[45, 25, 20, 10], k=1
                )[0],
                "status": rng.choices(
                    ["submitted", "under_review", "approved", "rejected", "closed"],
                    weights=[15, 15, 40, 20, 10],
                    k=1,
                )[0],
                "submitted_at": submitted_at,
                "created_at": submitted_at,
                "updated_at": submitted_at,
            }
        )
    return applications


def _new_transaction_row(
    external_id: str,
    customer: dict,
    account: dict,
    device_id,
    ip_identity_id,
    amount: float,
    occurred_at: datetime,
    transaction_type: str = "payment",
    status: str = "completed",
) -> dict:
    return {
        "id": uuid.uuid4(),
        "external_transaction_id": external_id,
        "customer_id": customer["id"],
        "account_id": account["id"],
        "device_id": device_id,
        "ip_identity_id": ip_identity_id,
        "amount": round(max(amount, 1.0), 2),
        "currency": "USD",
        "transaction_type": transaction_type,
        "status": status,
        "occurred_at": occurred_at,
        "created_at": occurred_at,
        "updated_at": occurred_at,
    }


def generate_transactions_and_labels(
    rng: random.Random,
    config: GenerationConfig,
    customers: list[dict],
    accounts_by_customer: dict,
    devices: list[dict],
    ip_identities: list[dict],
) -> tuple[list[dict], list[dict]]:
    """Generate transactions with normal behavior plus injected fraud scenarios.

    Returns (transactions, labels) where labels is the ML-only ground truth
    (transaction_id, external_transaction_id, is_suspicious, scenario_type).
    """
    transactions: list[dict] = []
    labels: list[dict] = []
    txn_counter = 0

    def next_external_id() -> str:
        nonlocal txn_counter
        eid = f"TXN-{txn_counter:07d}"
        txn_counter += 1
        return eid

    def label(txn: dict, is_suspicious: bool, scenario: str) -> None:
        labels.append(
            {
                "transaction_id": txn["id"],
                "external_transaction_id": txn["external_transaction_id"],
                "customer_id": txn["customer_id"],
                "is_suspicious": int(is_suspicious),
                "scenario_type": scenario,
            }
        )

    num_suspicious_customers = max(
        1, int(len(customers) * config.suspicious_customer_ratio)
    )
    suspicious_customers = set(
        c["id"] for c in rng.sample(customers, num_suspicious_customers)
    )

    # Give each customer 1-2 "familiar" devices/IPs so normal transactions
    # look consistent, and unfamiliar ones stand out for injected scenarios.
    familiar_devices: dict = {}
    familiar_ips: dict = {}
    for customer in customers:
        familiar_devices[customer["id"]] = rng.sample(
            devices, k=min(2, len(devices))
        )
        familiar_ips[customer["id"]] = rng.sample(
            ip_identities, k=min(2, len(ip_identities))
        )

    # --- Normal transaction history, spread across all customers ---
    target_normal = config.num_transactions
    per_customer = max(1, target_normal // len(customers))

    for customer in customers:
        account = rng.choice(accounts_by_customer.get(customer["id"], [None]))
        if account is None:
            continue
        baseline = customer["_typical_amount"]

        for _ in range(per_customer):
            occurred_at = _random_timestamp(rng)
            device = rng.choice(familiar_devices[customer["id"]])
            ip_identity = rng.choice(familiar_ips[customer["id"]])
            amount = max(1.0, rng.gauss(baseline, baseline * 0.3))
            txn = _new_transaction_row(
                next_external_id(),
                customer,
                account,
                device["id"],
                ip_identity["id"],
                amount,
                occurred_at,
                transaction_type=rng.choices(
                    TRANSACTION_TYPES, weights=[20, 20, 25, 30, 5], k=1
                )[0],
                status=rng.choices(
                    ["completed", "pending", "failed"], weights=[90, 5, 5], k=1
                )[0],
            )
            transactions.append(txn)
            label(txn, is_suspicious=False, scenario="normal")

    # --- Inject suspicious scenarios for the flagged customers ---
    scenario_pool = [
        "large_amount",
        "velocity_burst",
        "new_device_large_amount",
        "combo",
    ]
    for customer in customers:
        if customer["id"] not in suspicious_customers:
            continue
        account = rng.choice(accounts_by_customer.get(customer["id"], [None]))
        if account is None:
            continue
        baseline = customer["_typical_amount"]
        scenario = rng.choice(scenario_pool)
        # Full HISTORY_DAYS range (not just the most recent 30 days) so
        # suspicious scenarios are spread across the whole timeline, not
        # concentrated at the end where an 80/20 chronological split would
        # put almost all of them in the test set.
        base_time = _random_timestamp(rng)

        if scenario == "large_amount":
            txn = _new_transaction_row(
                next_external_id(),
                customer,
                account,
                rng.choice(familiar_devices[customer["id"]])["id"],
                rng.choice(familiar_ips[customer["id"]])["id"],
                baseline * rng.uniform(8, 20),
                base_time,
            )
            transactions.append(txn)
            label(txn, is_suspicious=True, scenario="large_amount")

        elif scenario == "velocity_burst":
            burst_size = rng.randint(5, 15)
            for j in range(burst_size):
                occurred_at = base_time + timedelta(seconds=rng.uniform(0, 600))
                txn = _new_transaction_row(
                    next_external_id(),
                    customer,
                    account,
                    rng.choice(familiar_devices[customer["id"]])["id"],
                    rng.choice(familiar_ips[customer["id"]])["id"],
                    rng.gauss(baseline, baseline * 0.2),
                    occurred_at,
                )
                transactions.append(txn)
                label(txn, is_suspicious=True, scenario="velocity_burst")

        elif scenario == "new_device_large_amount":
            unfamiliar_device = rng.choice(devices)
            unfamiliar_ip = rng.choice(ip_identities)
            txn = _new_transaction_row(
                next_external_id(),
                customer,
                account,
                unfamiliar_device["id"],
                unfamiliar_ip["id"],
                baseline * rng.uniform(6, 15),
                base_time,
            )
            transactions.append(txn)
            label(txn, is_suspicious=True, scenario="new_device_large_amount")

        elif scenario == "combo":
            # Unfamiliar device + large amount + a short velocity burst.
            unfamiliar_device = rng.choice(devices)
            unfamiliar_ip = rng.choice(ip_identities)
            burst_size = rng.randint(3, 6)
            for j in range(burst_size):
                occurred_at = base_time + timedelta(seconds=rng.uniform(0, 300))
                amount = baseline * rng.uniform(5, 12)
                txn = _new_transaction_row(
                    next_external_id(),
                    customer,
                    account,
                    unfamiliar_device["id"],
                    unfamiliar_ip["id"],
                    amount,
                    occurred_at,
                )
                transactions.append(txn)
                label(txn, is_suspicious=True, scenario="combo")

    # --- Device/IP sharing across multiple customers ---
    eligible_customers = [c for c in customers if accounts_by_customer.get(c["id"])]

    shared_devices = rng.sample(devices, k=min(config.shared_device_count, len(devices)))
    for shared_device in shared_devices:
        victims = rng.sample(eligible_customers, k=min(rng.randint(3, 6), len(eligible_customers)))
        for customer in victims:
            account = rng.choice(accounts_by_customer[customer["id"]])
            occurred_at = _random_timestamp(rng)
            txn = _new_transaction_row(
                next_external_id(),
                customer,
                account,
                shared_device["id"],
                rng.choice(familiar_ips[customer["id"]])["id"],
                customer["_typical_amount"] * rng.uniform(0.8, 1.5),
                occurred_at,
            )
            transactions.append(txn)
            label(txn, is_suspicious=True, scenario="device_sharing")

    shared_ips = rng.sample(ip_identities, k=min(config.shared_ip_count, len(ip_identities)))
    for shared_ip in shared_ips:
        victims = rng.sample(eligible_customers, k=min(rng.randint(3, 6), len(eligible_customers)))
        for customer in victims:
            account = rng.choice(accounts_by_customer[customer["id"]])
            occurred_at = _random_timestamp(rng)
            txn = _new_transaction_row(
                next_external_id(),
                customer,
                account,
                rng.choice(familiar_devices[customer["id"]])["id"],
                shared_ip["id"],
                customer["_typical_amount"] * rng.uniform(0.8, 1.5),
                occurred_at,
            )
            transactions.append(txn)
            label(txn, is_suspicious=True, scenario="ip_sharing")

    return transactions, labels


def generate_events(
    rng: random.Random,
    config: GenerationConfig,
    customers: list[dict],
    accounts_by_customer: dict,
    transactions: list[dict],
    labels_by_txn_id: dict,
    suspicious_customer_ids: set,
) -> list[dict]:
    events = []
    event_counter = 0

    def next_external_id() -> str:
        nonlocal event_counter
        eid = f"EVT-{event_counter:07d}"
        event_counter += 1
        return eid

    # ~75% of events mirror a transaction ("transaction.completed"/"failed").
    txn_event_target = int(config.num_events * 0.75)
    sampled_transactions = rng.sample(
        transactions, k=min(txn_event_target, len(transactions))
    )
    customers_by_id = {c["id"]: c for c in customers}

    for txn in sampled_transactions:
        occurred_at = txn["occurred_at"] + timedelta(seconds=rng.uniform(1, 30))
        received_at = occurred_at + timedelta(seconds=rng.uniform(0.1, 5))
        customer = customers_by_id[txn["customer_id"]]
        is_suspicious = labels_by_txn_id.get(txn["id"], {}).get("is_suspicious", 0)
        location = (
            rng.choice(UNUSUAL_LOCATIONS)
            if is_suspicious and rng.random() < 0.6
            else customer["_home_location"]
        )
        events.append(
            {
                "id": uuid.uuid4(),
                "external_event_id": next_external_id(),
                "event_type": (
                    "transaction.completed"
                    if txn["status"] == "completed"
                    else "transaction.failed"
                ),
                "customer_id": txn["customer_id"],
                "account_id": txn["account_id"],
                "transaction_id": txn["id"],
                "occurred_at": occurred_at,
                "received_at": received_at,
                "payload": {"location": location, "channel": "online"},
                "created_at": received_at,
                "updated_at": received_at,
            }
        )

    # Remaining budget: login events (incl. failed-login bursts) and
    # a few application/account lifecycle events.
    remaining = max(config.num_events - len(events), 0)
    login_budget = int(remaining * 0.7)
    lifecycle_budget = remaining - login_budget

    # Failed-login bursts for a subset of the customers actually flagged as
    # suspicious (not an arbitrary random sample), so this signal is
    # meaningfully associated with the fraud/suspicious label it represents.
    suspicious_list = [c for c in customers if c["id"] in suspicious_customer_ids]
    num_burst_customers = max(1, int(len(suspicious_list) * 0.3)) if suspicious_list else 0
    burst_customers = (
        rng.sample(suspicious_list, k=min(num_burst_customers, len(suspicious_list)))
        if suspicious_list
        else []
    )
    burst_events_used = 0
    for customer in burst_customers:
        base_time = _random_timestamp(rng)
        burst_size = rng.randint(5, 10)
        for _ in range(burst_size):
            if burst_events_used >= login_budget:
                break
            occurred_at = base_time + timedelta(seconds=rng.uniform(0, 600))
            events.append(
                {
                    "id": uuid.uuid4(),
                    "external_event_id": next_external_id(),
                    "event_type": "login.failed",
                    "customer_id": customer["id"],
                    "account_id": None,
                    "transaction_id": None,
                    "occurred_at": occurred_at,
                    "received_at": occurred_at + timedelta(seconds=rng.uniform(0.1, 1)),
                    "payload": {"reason": "invalid_password"},
                    "created_at": occurred_at,
                    "updated_at": occurred_at,
                }
            )
            burst_events_used += 1

    # Fill the rest of the login budget with normal login.success events.
    for _ in range(max(login_budget - burst_events_used, 0)):
        customer = rng.choice(customers)
        occurred_at = _random_timestamp(rng)
        events.append(
            {
                "id": uuid.uuid4(),
                "external_event_id": next_external_id(),
                "event_type": "login.success",
                "customer_id": customer["id"],
                "account_id": None,
                "transaction_id": None,
                "occurred_at": occurred_at,
                "received_at": occurred_at + timedelta(seconds=rng.uniform(0.1, 1)),
                "payload": {"location": customer["_home_location"]},
                "created_at": occurred_at,
                "updated_at": occurred_at,
            }
        )

    # Lifecycle events (account created).
    for _ in range(max(lifecycle_budget, 0)):
        customer = rng.choice(customers)
        customer_accounts = accounts_by_customer.get(customer["id"], [])
        if not customer_accounts:
            continue
        account = rng.choice(customer_accounts)
        occurred_at = account["created_at"]
        events.append(
            {
                "id": uuid.uuid4(),
                "external_event_id": next_external_id(),
                "event_type": "account.created",
                "customer_id": customer["id"],
                "account_id": account["id"],
                "transaction_id": None,
                "occurred_at": occurred_at,
                "received_at": occurred_at + timedelta(seconds=rng.uniform(0.1, 2)),
                "payload": None,
                "created_at": occurred_at,
                "updated_at": occurred_at,
            }
        )

    return events


def _strip_generator_only_fields(customers: list[dict]) -> list[dict]:
    """Return customer rows without the ML/generation-only helper fields."""
    columns = {
        "id", "external_customer_id", "first_name", "last_name", "email",
        "phone", "date_of_birth", "status", "created_at", "updated_at",
    }
    return [{k: v for k, v in c.items() if k in columns} for c in customers]


def generate_dataset(config: GenerationConfig) -> GeneratedDataset:
    """Generate the full relational synthetic dataset."""
    rng = random.Random(config.seed)

    customers = generate_customers(rng, config)
    devices = generate_devices(rng, config)
    ip_identities = generate_ip_identities(rng, config)
    accounts = generate_accounts(rng, config, customers)

    accounts_by_customer: dict = {}
    for account in accounts:
        accounts_by_customer.setdefault(account["customer_id"], []).append(account)

    loan_applications = generate_loan_applications(
        rng, config, customers, accounts_by_customer
    )
    transactions, labels = generate_transactions_and_labels(
        rng, config, customers, accounts_by_customer, devices, ip_identities
    )
    labels_by_txn_id = {row["transaction_id"]: row for row in labels}
    suspicious_customer_ids = {
        row["customer_id"] for row in labels if row["is_suspicious"]
    }
    events = generate_events(
        rng,
        config,
        customers,
        accounts_by_customer,
        transactions,
        labels_by_txn_id,
        suspicious_customer_ids,
    )

    return GeneratedDataset(
        customers=_strip_generator_only_fields(customers),
        devices=devices,
        ip_identities=ip_identities,
        accounts=accounts,
        loan_applications=loan_applications,
        transactions=transactions,
        events=events,
        labels=labels,
    )


def write_labels_csv(dataset: GeneratedDataset, output_path: Path) -> None:
    """Write the ML-only ground-truth labels to CSV (not loaded into Postgres)."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "transaction_id",
                "external_transaction_id",
                "customer_id",
                "is_suspicious",
                "scenario_type",
            ],
        )
        writer.writeheader()
        for row in dataset.labels:
            writer.writerow(row)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate synthetic fraud dataset.")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--customers", type=int, default=2000)
    parser.add_argument("--accounts", type=int, default=3000)
    parser.add_argument("--devices", type=int, default=1000)
    parser.add_argument("--ip-identities", type=int, default=1000)
    parser.add_argument("--loan-applications", type=int, default=2000)
    parser.add_argument("--transactions", type=int, default=20000)
    parser.add_argument("--events", type=int, default=20000)
    parser.add_argument(
        "--skip-load",
        action="store_true",
        help="Generate data and write labels CSV, but don't load into Postgres.",
    )
    args = parser.parse_args()

    config = GenerationConfig(
        seed=args.seed,
        num_customers=args.customers,
        num_accounts=args.accounts,
        num_devices=args.devices,
        num_ip_identities=args.ip_identities,
        num_loan_applications=args.loan_applications,
        num_transactions=args.transactions,
        num_events=args.events,
    )

    print(f"Generating synthetic dataset (seed={config.seed})...")
    dataset = generate_dataset(config)

    print(f"  customers:          {len(dataset.customers)}")
    print(f"  devices:            {len(dataset.devices)}")
    print(f"  ip_identities:      {len(dataset.ip_identities)}")
    print(f"  accounts:           {len(dataset.accounts)}")
    print(f"  loan_applications:  {len(dataset.loan_applications)}")
    print(f"  transactions:       {len(dataset.transactions)}")
    print(f"  events:             {len(dataset.events)}")
    suspicious_count = sum(1 for row in dataset.labels if row["is_suspicious"])
    print(f"  labels (suspicious): {suspicious_count} / {len(dataset.labels)}")

    labels_path = Path(__file__).parent / "training_labels.csv"
    write_labels_csv(dataset, labels_path)
    print(f"Wrote ML training labels to {labels_path}")

    if not args.skip_load:
        from ml.data.load import load_into_database

        print("Loading operational data into PostgreSQL...")
        load_into_database(dataset)
        print("Load complete.")


if __name__ == "__main__":
    main()
