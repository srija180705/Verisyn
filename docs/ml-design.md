# ML Design

## Status

No models are trained or implemented yet. This document records the
**agreed target design** for the ML layer.

## Detection Mechanisms

The fraud engine will combine three mechanisms:

1. **Rule-based detection** - deterministic checks for known fraud patterns.
2. **Supervised ML** - Logistic Regression initially, trained on labeled
   historical data. XGBoost may be evaluated later if justified, but is
   not part of the initial implementation.
3. **Anomaly detection** - Isolation Forest, to catch previously unseen
   fraud patterns that don't match known rules or labeled examples.

## Candidate Features

Approximate feature set for the future fraud engine:

- `amount`
- `amount_vs_customer_avg`
- `transactions_last_10m`
- `transactions_last_1h`
- `applications_last_10m`
- `is_new_device`
- `accounts_per_device`
- `is_new_ip`
- `accounts_per_ip`
- `time_since_last_transaction`
- `location_anomaly`
- `failed_logins_last_10m`

## Risk Aggregation

```
Final Risk Score = 70% x ML Score + 20% x Anomaly Score + 10% x Rule Score
```

All components normalized to 0-100.

| Score Range | Risk Level |
|-------------|------------|
| 0-29        | LOW        |
| 30-59       | MODERATE   |
| 60-79       | HIGH       |
| 80-100      | CRITICAL   |

## Decision Mapping

| Risk Level | Decision       |
|------------|----------------|
| LOW        | ALLOW          |
| MODERATE   | STEP_UP        |
| HIGH       | MANUAL_REVIEW  |
| CRITICAL   | BLOCK          |

These weights, thresholds, and mappings are prototype policies and must be
implemented as configuration, not hardcoded throughout the application, so
they can be tuned without code changes.

## Package Layout (`ml/`)

- `data/` - synthetic dataset generation.
- `features/` - feature definitions shared by training and inference.
- `training/` - model training scripts. Never executed from the real-time
  API request path.
- `evaluation/` - model evaluation scripts.
- `models/` - trained model artifacts (not tracked in git).
- `inference/` - utilities for loading a trained model into the real-time
  API.

Package structure exists today; data generation, training, and feature
implementation are later phases.
