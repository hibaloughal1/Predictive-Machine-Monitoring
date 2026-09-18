# Predictive Machine Monitoring

A predictive maintenance prototype that estimates, from live system telemetry, the probability that a monitored machine will hit a defined "slowdown" condition within the next 5 minutes — and turns that probability into a live risk gauge and alerts.

## Overview

Classic monitoring describes the present ("CPU is at 95% right now"). This project instead trains a model to answer a forward-looking question — "is there a rising probability of a slowdown condition in the next 5 minutes, based on the last ~60 seconds of trend?" — and serves that estimate through a live dashboard.

## Architecture

```
Machine → telemetry collection (every 2s) → SQLite storage
        → merge across collection sessions
        → cleaning & reliability flagging
        → gap-aware temporal segmentation
        → present-time "slowdown" rule definition
        → forward-looking 5-minute label
        → causal feature engineering
        → chronological train/validation/test split (by whole run)
        → model training & selection
        → saved model artifact
        → live dashboard: real-time inference, risk scoring, alerting
```

## Data Pipeline

- **`01_Collecte`** — a Windows monitoring agent samples system metrics every 2 seconds for an 8-hour session by default, without ever triggering artificial CPU/RAM load, and stores the readings in a local SQLite database. The agent is distributed as a compiled executable; its source is not included in this repository.
- **`02_Merge_data`** — `combin_db.py` finds every collection-session database, merges the `schema_meta`, `runs`, `events`, `capabilities` and `system_metrics` tables, deduplicates and re-indexes them, and writes a single merged database + CSV.
- **`03_Nettoyage`** — `nettoyage_donees.py` validates and corrects `machine_id`s and timestamps, flags unreliable samples, deduplicates, sorts by machine/run/timestamp, and exports the cleaned dataset.
- **`04_Pretraitement_Model`** — ten ordered notebooks carry the cleaned dataset through EDA, temporal-structure auditing, gap investigation/validation, label definition, feature engineering, dataset splitting, and modeling (see below).

## EDA

`01_eda.ipynb` loads the cleaned dataset, checks structure/types, converts timestamps, checks for duplicates and missing values, and reviews distributions and outliers. Notebooks `03`–`05` specifically audit the temporal structure (per-machine/run gaps, overlaps, invalid or duplicated timestamps) before any labeling is attempted.

## Feature Engineering

`10_feature_engineering.ipynb` builds causal features (the model only ever sees information available at or before the prediction time) from roughly the last 60 seconds of history per row. The deployed model pipeline consumes 62 features in total (per `04_Pretraitement_Model/DASHBOARD.md`).

## Machine Learning

**Label**: `slowdown_in_5min` — for each row, look strictly forward (never at the current row) within the same continuous segment; the label is `1` if a present-time "slowdown" condition occurs anywhere in the next 5 minutes, `0` otherwise, and the row is excluded if its segment doesn't extend a full 5 minutes forward (to avoid false negatives from a truncated horizon). A `slowdown_in_10min` variant was also produced but used only as a secondary comparison in reports, never for modeling.

**Split**: chronological, by whole run (no shuffling), to avoid temporal leakage between train/validation/test.

**Models compared**: Logistic Regression (baseline), Random Forest, XGBoost, and LightGBM.

## Model Evaluation

Validation set:

| Model | Accuracy | Precision | Recall | F1 | ROC AUC |
|---|---|---|---|---|---|
| Logistic Regression | 0.879 | 0.863 | 0.826 | 0.844 | 0.932 |
| Random Forest | 0.902 | 0.900 | 0.847 | 0.873 | 0.941 |
| XGBoost | 0.885 | 0.849 | 0.862 | 0.856 | 0.950 |
| LightGBM | 0.802 | 0.702 | 0.868 | 0.777 | 0.932 |

**XGBoost was the model carried forward to the held-out test set** (Random Forest scored marginally higher on some validation metrics; this project does not claim XGBoost was the top validation performer — it is reported here as the model actually evaluated on test).

Held-out test set:

| Model | Accuracy | Precision | Recall | F1 | ROC AUC |
|---|---|---|---|---|---|
| XGBoost | 0.826 | 0.816 | 0.926 | 0.867 | 0.925 |

The trained pipeline is saved at `04_Pretraitement_Model/models/best_slowdown_model.joblib`.

## Results

A live dashboard (`04_Pretraitement_Model/dashboard/`) consumes the saved model to score the monitored machine in real time:

- **Low** risk: probability below 40% — no alert.
- **Elevated**: 40%–70% — amber notification, event stored.
- **High**: 70% or above — red notification, event stored.
- A 60-second cooldown prevents duplicate notifications while risk stays elevated; past alerts can be reviewed and acknowledged on a Critical Events page.

## Installation

```bash
cd 04_Pretraitement_Model
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -r requirements-dashboard.txt
```

The notebooks additionally require `pandas`, `scikit-learn`, `xgboost`, `lightgbm`, and `jupyter` (no single pinned requirements file for the notebook stage exists in this repository).

**Data**: the real collected telemetry (`01_Collecte/data`, `02_Merge_data/data`, `03_Nettoyage/data`, `04_Pretraitement_Model/data`) is intentionally excluded from this repository, as it is real machine-usage data. The notebooks and dashboard code are shared to document the methodology and are not runnable end-to-end without supplying your own equivalent dataset.

## Usage

```bash
cd 04_Pretraitement_Model
python 12_run_dashboard.py
# or double-click RUN_DASHBOARD.bat
```

Open `http://127.0.0.1:8765` (API docs at `/docs`).

## Project Structure

```
01_Collecte/            # monitoring agent (compiled) + collected session databases (excluded)
02_Merge_data/          # database-merging script
03_Nettoyage/           # cleaning script
04_Pretraitement_Model/ # EDA, labeling, feature engineering, modeling notebooks + dashboard
  ├── 01_eda.ipynb ... 11_preprocessing_and_modeling.ipynb
  ├── dashboard/        # live inference + alerting app
  ├── models/           # saved model artifact
  └── reports/          # aggregate, anonymized run/label/model-comparison reports
```

## Limitations

Per the project's own analysis: a small, single-organization dataset; a provisional label definition; no cross-validation; no baseline-model comparison beyond the four listed above; local-only deployment (no Docker, no cloud, no CI/CD); the dashboard monitors only the single machine it runs on.

## Future Improvements

- Cross-validation and a documented baseline comparison.
- Validate the label definition against real incident/outage data rather than a rule derived from resource metrics alone.
- Collect data across multiple machines/organizations to test generalization.
- Multi-machine dashboard support and containerized/cloud deployment.
