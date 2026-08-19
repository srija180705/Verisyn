"""Logistic Regression fraud classifier.

Trains on the point-in-time features already produced by ml/features.py
(ml/data/training_features.csv) - does not regenerate data or touch the
database. fraud_label is used ONLY as the training target, never as an
input feature.
"""
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    average_precision_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.preprocessing import StandardScaler

FEATURE_COLUMNS = [
    "amount",
    "amount_vs_customer_avg",
    "transactions_last_10m",
    "transactions_last_1h",
    "is_new_device",
    "accounts_per_device",
    "is_new_ip",
    "accounts_per_ip",
    "time_since_last_transaction_seconds",
    "failed_logins_last_10m",
    "location_anomaly",
]
TARGET_COLUMN = "fraud_label"
TRAIN_FRACTION = 0.8

DATA_DIR = Path(__file__).parent / "data"
MODELS_DIR = Path(__file__).parent / "models"
FEATURES_CSV = DATA_DIR / "training_features.csv"
MODEL_PATH = MODELS_DIR / "logistic_regression.joblib"
SCALER_PATH = MODELS_DIR / "scaler.joblib"


def load_training_data() -> pd.DataFrame:
    """Load the existing feature CSV, in its original (chronological) row order."""
    if not FEATURES_CSV.exists():
        raise FileNotFoundError(
            f"{FEATURES_CSV} not found - run `python ml/features.py` first "
            "(Phase 3). This script does not regenerate data."
        )
    df = pd.read_csv(FEATURES_CSV)
    if TARGET_COLUMN not in df.columns:
        raise ValueError(
            f"{FEATURES_CSV} has no '{TARGET_COLUMN}' column - it must be built "
            "with a labels CSV available (see ml/features.py build_training_dataset)."
        )
    # Booleans arrive from CSV as True/False strings -> real bools -> int for sklearn.
    for col in ("is_new_device", "is_new_ip", "location_anomaly"):
        df[col] = df[col].astype(bool).astype(int)
    return df


def temporal_train_test_split(
    df: pd.DataFrame, train_fraction: float = TRAIN_FRACTION
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Split by row position (earlier rows = train, later rows = test).

    No shuffling - shuffling would leak future information into training.
    """
    split_index = int(len(df) * train_fraction)
    train_df = df.iloc[:split_index]
    test_df = df.iloc[split_index:]
    return train_df, test_df


def load_saved_model() -> tuple[LogisticRegression, StandardScaler]:
    """Load the already-trained model + scaler from disk (no retraining).
    Used by the fraud assessment API (Phase 6A) for inference.
    """
    if not MODEL_PATH.exists() or not SCALER_PATH.exists():
        raise FileNotFoundError(
            f"Trained model not found at {MODEL_PATH} - run `python ml/model.py` first."
        )
    model = joblib.load(MODEL_PATH)
    scaler = joblib.load(SCALER_PATH)
    return model, scaler


def train_model(
    train_df: pd.DataFrame,
) -> tuple[LogisticRegression, StandardScaler]:
    """Fit a StandardScaler + class-weighted LogisticRegression on the
    training split. class_weight='balanced' handles the fraud/normal
    imbalance without needing an extra resampling dependency.
    """
    X_train = train_df[FEATURE_COLUMNS]
    y_train = train_df[TARGET_COLUMN]

    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)

    model = LogisticRegression(
        class_weight="balanced", max_iter=1000, random_state=42
    )
    model.fit(X_train_scaled, y_train)
    return model, scaler


def evaluate_model(
    model: LogisticRegression,
    scaler: StandardScaler,
    test_df: pd.DataFrame,
) -> dict:
    X_test = test_df[FEATURE_COLUMNS]
    y_test = test_df[TARGET_COLUMN]
    X_test_scaled = scaler.transform(X_test)

    probabilities = model.predict_proba(X_test_scaled)[:, 1]
    predictions = model.predict(X_test_scaled)

    return {
        "y_test": y_test,
        "probabilities": probabilities,
        "predictions": predictions,
        "precision": precision_score(y_test, predictions, zero_division=0),
        "recall": recall_score(y_test, predictions, zero_division=0),
        "f1": f1_score(y_test, predictions, zero_division=0),
        "roc_auc": roc_auc_score(y_test, probabilities),
        "pr_auc": average_precision_score(y_test, probabilities),
        "confusion_matrix": confusion_matrix(y_test, predictions),
    }


def print_report(train_df, test_df, model, scaler, results: dict) -> None:
    print("=" * 60)
    print("TRAIN / TEST SPLIT (chronological)")
    print("=" * 60)
    train_fraud = train_df[TARGET_COLUMN].sum()
    test_fraud = test_df[TARGET_COLUMN].sum()
    print(
        f"train: {len(train_df)} rows, {train_fraud} fraud "
        f"({100 * train_fraud / len(train_df):.2f}%)"
    )
    print(
        f"test:  {len(test_df)} rows, {test_fraud} fraud "
        f"({100 * test_fraud / len(test_df):.2f}%)"
    )

    print("\n" + "=" * 60)
    print("MODEL METRICS (test set)")
    print("=" * 60)
    print(f"precision: {results['precision']:.4f}")
    print(f"recall:    {results['recall']:.4f}")
    print(f"f1:        {results['f1']:.4f}")
    print(f"roc_auc:   {results['roc_auc']:.4f}")
    print(f"pr_auc:    {results['pr_auc']:.4f}")

    cm = results["confusion_matrix"]
    print("\nconfusion matrix:")
    print("                 predicted_normal  predicted_fraud")
    print(f"actual_normal    {cm[0][0]:>16}  {cm[0][1]:>15}")
    print(f"actual_fraud     {cm[1][0]:>16}  {cm[1][1]:>15}")

    print("\n" + "=" * 60)
    print("FEATURE COEFFICIENTS (on standardized features)")
    print("=" * 60)
    coefs = sorted(
        zip(FEATURE_COLUMNS, model.coef_[0]), key=lambda pair: abs(pair[1]), reverse=True
    )
    for name, coef in coefs:
        direction = "increases" if coef > 0 else "decreases"
        print(f"  {name:<38} {coef:+.4f}  ({direction} fraud probability)")

    print("\n" + "=" * 60)
    print("EXAMPLE PREDICTIONS (first 5 test rows)")
    print("=" * 60)
    y_test = results["y_test"].reset_index(drop=True)
    probs = results["probabilities"]
    preds = results["predictions"]
    for i in range(min(5, len(y_test))):
        print(
            f"  actual={y_test[i]}  predicted={preds[i]}  "
            f"fraud_probability={probs[i]:.4f}"
        )


def main() -> None:
    print("Loading training features (existing CSV, not regenerated)...")
    df = load_training_data()

    train_df, test_df = temporal_train_test_split(df)

    print("Training Logistic Regression (class_weight='balanced')...")
    model, scaler = train_model(train_df)

    results = evaluate_model(model, scaler, test_df)
    print_report(train_df, test_df, model, scaler, results)

    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, MODEL_PATH)
    joblib.dump(scaler, SCALER_PATH)
    print(f"\nSaved model to {MODEL_PATH}")
    print(f"Saved scaler to {SCALER_PATH}")


if __name__ == "__main__":
    main()
