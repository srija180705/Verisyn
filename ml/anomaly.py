"""Isolation Forest anomaly detector - independent of Logistic Regression.

Trains on the same point-in-time features already produced by
ml/features.py (ml/data/training_features.csv) and the same chronological
80/20 split used for Logistic Regression (reused directly from ml/model.py,
not reimplemented). fraud_label is used only to (a) select the
"legitimate" training subset the forest is fit on, and (b) evaluate
afterward - never as a model input feature.

Isolation Forest finds statistically UNUSUAL transactions, which is a
different thing from "fraud". A transaction can be anomalous without
being fraud (e.g. a genuinely large first-time purchase), and fraud that
closely mimics normal behavior can score low. It is reported here as a
second, independent signal - not a replacement for the classifier.
"""
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.metrics import (
    average_precision_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)

sys.path.append(str(Path(__file__).resolve().parents[1]))

from ml.model import (  # noqa: E402
    FEATURE_COLUMNS,
    TARGET_COLUMN,
    load_training_data,
    temporal_train_test_split,
)

MODELS_DIR = Path(__file__).parent / "models"
MODEL_PATH = MODELS_DIR / "isolation_forest.joblib"

RANDOM_SEED = 42


def load_saved_model() -> tuple[IsolationForest, float, float]:
    """Load the already-trained Isolation Forest + score calibration from
    disk (no retraining). Used by the fraud assessment API (Phase 6A) for
    inference.
    """
    if not MODEL_PATH.exists():
        raise FileNotFoundError(
            f"Trained model not found at {MODEL_PATH} - run `python ml/anomaly.py` first."
        )
    saved = joblib.load(MODEL_PATH)
    return saved["model"], saved["score_min"], saved["score_max"]


def train_anomaly_model(train_df: pd.DataFrame) -> tuple[IsolationForest, float, float]:
    """Fit Isolation Forest on the LEGITIMATE (fraud_label == 0) training
    rows only, so it learns what "normal" looks like. `contamination` is
    set to the training fraud rate - a defensible, reproducible estimate
    of how much of the data is expected to be anomalous, rather than an
    arbitrary constant.

    Returns (model, score_min, score_max) where score_min/score_max are
    the raw anomaly-score range observed on the legitimate training rows,
    used to calibrate the 0-100 output scale.
    """
    normal_train_df = train_df[train_df[TARGET_COLUMN] == 0]
    X_train_normal = normal_train_df[FEATURE_COLUMNS]

    contamination = max(train_df[TARGET_COLUMN].mean(), 0.001)

    model = IsolationForest(
        n_estimators=200,
        contamination=contamination,
        random_state=RANDOM_SEED,
    )
    model.fit(X_train_normal)

    # score_samples: higher = more normal. Negate so higher = more anomalous,
    # then use the legitimate-training distribution to calibrate 0-100.
    raw_scores = -model.score_samples(X_train_normal)
    return model, float(raw_scores.min()), float(raw_scores.max())


def compute_anomaly_scores(
    model: IsolationForest, X: pd.DataFrame, score_min: float, score_max: float
) -> np.ndarray:
    """0-100 anomaly score: 0 = least anomalous, 100 = most anomalous.

    Calibrated against the legitimate-training score range; test rows that
    fall outside that range are clipped to [0, 100] rather than extrapolated.
    """
    raw_scores = -model.score_samples(X)
    span = score_max - score_min
    if span <= 0:
        return np.zeros(len(X))
    scaled = 100 * (raw_scores - score_min) / span
    return np.clip(scaled, 0, 100)


def evaluate_anomaly_model(
    model: IsolationForest,
    score_min: float,
    score_max: float,
    test_df: pd.DataFrame,
) -> dict:
    X_test = test_df[FEATURE_COLUMNS]
    y_test = test_df[TARGET_COLUMN].reset_index(drop=True)

    scores = compute_anomaly_scores(model, X_test, score_min, score_max)
    # IsolationForest.predict: -1 = anomaly, 1 = normal -> map to 1/0.
    raw_predictions = model.predict(X_test)
    predictions = (raw_predictions == -1).astype(int)

    return {
        "y_test": y_test,
        "scores": scores,
        "predictions": predictions,
        "precision": precision_score(y_test, predictions, zero_division=0),
        "recall": recall_score(y_test, predictions, zero_division=0),
        "f1": f1_score(y_test, predictions, zero_division=0),
        "roc_auc": roc_auc_score(y_test, scores),
        "pr_auc": average_precision_score(y_test, scores),
        "confusion_matrix": confusion_matrix(y_test, predictions),
    }


def print_report(train_df, test_df, results: dict) -> None:
    print("=" * 60)
    print("TRAIN / TEST SPLIT (chronological, same split as Logistic Regression)")
    print("=" * 60)
    train_fraud = train_df[TARGET_COLUMN].sum()
    test_fraud = test_df[TARGET_COLUMN].sum()
    print(
        f"train: {len(train_df)} rows, {train_fraud} fraud "
        f"({100 * train_fraud / len(train_df):.2f}%) "
        f"- fit on {len(train_df) - train_fraud} legitimate rows only"
    )
    print(f"test:  {len(test_df)} rows, {test_fraud} fraud")

    scores = results["scores"]
    y_test = results["y_test"]
    print("\n" + "=" * 60)
    print("ANOMALY SCORE DISTRIBUTION (test set, 0-100)")
    print("=" * 60)
    print(
        f"min={scores.min():.2f} max={scores.max():.2f} mean={scores.mean():.2f} "
        f"median={np.median(scores):.2f}"
    )
    fraud_scores = scores[y_test == 1]
    normal_scores = scores[y_test == 0]
    print(f"mean score for actual fraud rows:  {fraud_scores.mean():.2f}")
    print(f"mean score for actual normal rows: {normal_scores.mean():.2f}")

    print("\n" + "=" * 60)
    print("EVALUATION AGAINST HELD-OUT FRAUD LABELS")
    print("(anomaly detection finds UNUSUAL behavior, not fraud directly -")
    print(" this compares that signal against known fraud as a reference point)")
    print("=" * 60)
    print(f"precision: {results['precision']:.4f}")
    print(f"recall:    {results['recall']:.4f}")
    print(f"f1:        {results['f1']:.4f}")
    print(f"roc_auc:   {results['roc_auc']:.4f}")
    print(f"pr_auc:    {results['pr_auc']:.4f}")

    cm = results["confusion_matrix"]
    print("\nconfusion matrix:")
    print("                 predicted_normal  predicted_anomaly")
    print(f"actual_normal    {cm[0][0]:>16}  {cm[0][1]:>17}")
    print(f"actual_fraud     {cm[1][0]:>16}  {cm[1][1]:>17}")

    print("\n" + "=" * 60)
    print("TOP 10 MOST ANOMALOUS TEST TRANSACTIONS")
    print("=" * 60)
    ranked = test_df.reset_index(drop=True).copy()
    ranked["anomaly_score"] = scores
    top = ranked.sort_values("anomaly_score", ascending=False).head(10)
    for _, row in top.iterrows():
        print(
            f"  transaction_id={row['transaction_id']}  "
            f"score={row['anomaly_score']:.2f}  "
            f"actual_fraud={bool(row[TARGET_COLUMN])}"
        )

    print("\n" + "=" * 60)
    print("A FEW NORMAL-SCORING EXAMPLES (lowest scores)")
    print("=" * 60)
    bottom = ranked.sort_values("anomaly_score", ascending=True).head(5)
    for _, row in bottom.iterrows():
        print(
            f"  transaction_id={row['transaction_id']}  "
            f"score={row['anomaly_score']:.2f}  "
            f"actual_fraud={bool(row[TARGET_COLUMN])}"
        )


def main() -> None:
    print("Loading training features (existing CSV, not regenerated)...")
    df = load_training_data()

    train_df, test_df = temporal_train_test_split(df)

    print("Training Isolation Forest on legitimate training transactions only...")
    model, score_min, score_max = train_anomaly_model(train_df)

    results = evaluate_anomaly_model(model, score_min, score_max, test_df)
    print_report(train_df, test_df, results)

    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(
        {"model": model, "score_min": score_min, "score_max": score_max}, MODEL_PATH
    )
    print(f"\nSaved model to {MODEL_PATH}")


if __name__ == "__main__":
    main()
