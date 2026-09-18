# ADOPTAI — General Project Report

*Prepared from a read-only analysis of the AdoptAI repository. No project file was modified to produce this report. All figures below are taken directly from the project's own scripts, notebooks, and generated reports — nothing has been invented. Where information could not be found, this is stated explicitly.*

---

## 1. Executive Summary

**Context.** AdoptAI is an internal, single-team prototype that monitors the performance of Windows machines (CPU, RAM, disk, network, GPU, temperature, etc.) and tries to **predict slowdowns before they happen**, rather than only reporting them after the fact. The project is organized as a four-stage pipeline: `01_Collecte` (data collection), `02_Merge_data` (merging), `03_Nettoyage` (cleaning), `04_Pretraitement_Model` (feature engineering, machine learning, and a live dashboard).

**Problem.** Traditional monitoring tools show *current* CPU/RAM/disk usage. They tell a user a machine is already struggling — but by the time an alert fires, the user has often already lost time. AdoptAI's premise is that sustained resource pressure has an observable signature *before* a full slowdown occurs, and that this signature can be learned from historical telemetry.

**Solution.** A compiled telemetry collector (`AdoptAI-Monitor.exe`) samples ~25 system metrics every 2 seconds and stores them in SQLite. Collected data from 4 machines and 67 runs (~153,500 rows over roughly three weeks) was merged, cleaned, segmented around collection gaps, and used to build a supervised binary classification target: **will a "slowdown" condition occur at any point in the next 5 minutes?** Four models (Logistic Regression, Random Forest, XGBoost, LightGBM) were trained on 62 causal, time-aware engineered features (lags, rolling means/std/max over 30–60 seconds, domain ratios, missing-sensor indicators). **XGBoost** was selected by validation ROC AUC (0.9503) and evaluated once on a held-out, chronologically later test set, achieving **ROC AUC 0.9246, precision 0.8156, recall 0.9256, F1 0.8671**. This model powers a live local dashboard (FastAPI + vanilla JS) that shows real-time telemetry, a slowdown probability gauge, and a threshold-based alert system (low / elevated / high risk).

**Architecture.** Source machine → 2-second telemetry collection → SQLite storage → merge across sessions → cleaning & reliability flagging → gap-aware temporal segmentation → present-time "slowdown" rule definition → forward-looking 5-minute label → causal feature engineering → train/validation/test split (chronological, by whole run) → model training & selection → saved model artifact → live dashboard performing real-time inference, risk scoring, and alerting.

**Results and honesty check.** The model's validation performance (ROC AUC ~0.95, F1 ~0.85) is strong, but several caveats limit how much can be claimed today: (1) the label rule ("Rule C") is explicitly documented in the notebooks as *provisional and requiring manual validation*, and no evidence of that validation being completed was found; (2) the positive rate of the target label shifts sharply across the chronological split (32.5% train → 39.7% validation → 61.3% test), meaning test performance is measured on a materially different class balance than training; (3) the dataset is small and drawn from only 4 machines, one of which has 0% "reliable" samples in the raw data; (4) no baseline model (e.g., majority-class or simple threshold rule) was computed for comparison, so it is not possible to state precisely how much value the ML model adds over a simple heuristic; (5) no PR-AUC or class-imbalance-specific metric was computed.

**Limitations.** Small, single-organization dataset; provisional label definition; no cross-validation; no baseline comparison; local-only deployment (no Docker, no cloud, no CI/CD); dashboard monitors only the single machine it runs on.

**Perspectives.** Short term: validate the label rule manually, add a real baseline comparison, investigate the train→test distribution shift. Medium term: collect more machines and longer time spans, recalibrate risk thresholds, add automated retraining/monitoring. Long term: multi-machine fleet dashboard, containerized deployment, production hardening.

**Business value.** AdoptAI demonstrates, on real (if limited) data, that a lightweight telemetry pipeline can be turned into a forward-looking risk indicator rather than a purely reactive dashboard. The engineering scaffolding — collection, merging, cleaning, leakage-safe feature engineering, model comparison, and a working live inference dashboard — is functionally complete end-to-end. What is not yet proven is generalization beyond the current small dataset and machine set. The natural next step is not a rebuild but a validation and scale-up of what already works.

---

## 2. Project Context

AdoptAI was built as a structured, notebook-and-script pipeline under a project folder tree (`01_Collecte` → `02_Merge_data` → `03_Nettoyage` → `04_Pretraitement_Model`), with each stage documented by its own `README.md`. Internal file paths embedded in the notebooks' saved outputs (e.g. `...\Stage PFA\Ah Digital\preprocessing\labeling\...`) indicate the work was carried out as an internship-style data science project on a personal Windows development machine, developed and executed locally without a shared server or cloud environment. The repository is not currently a Git repository (no `.git` folder was found), and there is no top-level `README.md`, `requirements.txt`, Docker, or CI/CD configuration outside the `04_Pretraitement_Model` subfolder.

## 3. Problem Statement

Classic system monitoring (Task Manager, most dashboards) reports **what is happening right now**. A user or IT team only reacts once CPU/RAM/disk pressure is already visibly high, by which point productivity has already been affected. AdoptAI's stated problem is: *can sustained resource pressure be detected early enough, from raw telemetry, to warn a user or system a few minutes before a perceptible slowdown occurs?*

### Quel problème existait avant ADOPTAI ?
Monitoring tools show current load, not future risk. A spike is only visible after it starts.

### Qu'est-ce qu'ADOPTAI apporte ?
A specific, testable forward-looking target — "will resource pressure reach a defined slowdown condition within the next 5 minutes?" — and a trained model that estimates the probability of that happening from the last ~60 seconds of history, plus a live dashboard that turns that probability into a simple risk gauge and alert.

### Pourquoi utiliser l'IA ?
Because the relationship between five resource signals (CPU, RAM, swap, disk latency, context switches), their recent trend (lags, differences, rolling statistics), and a future outcome is not a simple fixed rule — it is exactly the kind of pattern a supervised classifier can learn from historical examples where the outcome (slowdown or not) is already known.

### Quelle est la différence entre monitoring classique et approche prédictive ?
Classic monitoring: **describes the present** ("CPU is at 95% right now"). AdoptAI's predictive layer: **estimates the near future** ("there is an 82% probability of a slowdown condition within the next 5 minutes, based on the last minute of trend").

## 4. Objectives

Based on the notebooks and code, the objectives actually pursued were:
1. Collect real system telemetry from multiple machines over time (`01_Collecte`).
2. Merge and reconcile telemetry collected across separate SQLite files (`02_Merge_data`).
3. Clean, validate, and flag the reliability of every sample (`03_Nettoyage`).
4. Rigorously define what a "slowdown" is, using only resource metrics (not run outcome/status fields), and compare multiple candidate rules before choosing one (`06_label_definition.ipynb`).
5. Turn that present-time definition into a genuinely future-looking, leakage-checked label at 5- and 10-minute horizons (`07_future_label_creation.ipynb`).
6. Split data chronologically by whole run to avoid any temporal leakage (`09_temporal_split.ipynb`).
7. Engineer a small, interpretable, causal feature set (`10_feature_engineering.ipynb`).
8. Train and compare several classifiers, select the best on validation, and confirm generalization once on a held-out test set (`11_preprocessing_and_modeling.ipynb`).
9. Deploy the trained model behind a live, real-time monitoring dashboard with alerting (`dashboard/`).

The intended user is not explicitly documented anywhere in the project (no persona, no target-market document was found). Based on the dashboard's design (local machine telemetry, single-user web UI, "LOCAL MACHINE" label in the interface), the implemented prototype targets an **individual machine / individual user or IT operator monitoring one endpoint**, not yet a fleet-wide enterprise monitoring product.

## 5. Overall Architecture

The pipeline actually implemented, adapted from the generic template to what the code really does:

```text
SOURCE MACHINE (Windows, psutil + LibreHardwareMonitor + sensors)
       ↓
COLLECTION — AdoptAI-Monitor.exe, samples every ~2s, 8h sessions,
              writes to per-session SQLite (system_metrics, runs, events, capabilities)
       ↓
STORAGE — SQLite (.db files), one per collection session/machine batch
       ↓
MERGE — combin_db.py: merges all .db files, deduplicates, regenerates IDs,
         indexes, outputs metrics_db_fusionnees.db / .csv
       ↓
CLEANING — nettoyage_donees.py: fixes machine_id, normalizes timestamps,
            flags sample_reliable / run_complete, removes duplicate samples
       ↓
EDA & TEMPORAL AUDIT — 01_eda, 03_time_structure_audit: structure, missingness,
                         outliers, gap detection
       ↓
GAP INVESTIGATION & SEGMENTATION — 04/05: segments the timeline so rolling
                                     windows and labels never cross a collection gap
       ↓
LABEL DEFINITION — 06_label_definition: compares 3 candidate "slowdown_now" rules,
                    selects Rule C (resource-threshold based)
       ↓
FUTURE LABEL CREATION — 07_future_label_creation: slowdown_in_5min /
                          slowdown_in_10min (5min = main target)
       ↓
TRAIN/VAL/TEST SPLIT — 09_temporal_split: chronological, whole-run, per machine
       ↓
FEATURE ENGINEERING — 10_feature_engineering: 37 causal features per split
       ↓
MACHINE LEARNING — 11_preprocessing_and_modeling: 4 models compared,
                    XGBoost selected, evaluated once on test
       ↓
MODEL ARTIFACT — models/best_slowdown_model.joblib (pipeline + metadata)
       ↓
LIVE DASHBOARD — dashboard/ (FastAPI + Uvicorn + vanilla JS):
                  live collection → same causal features → XGBoost inference →
                  risk level (low/elevated/high) → alert engine → SQLite storage → UI
```

Two collection paths exist side by side: the **offline historical pipeline** (`01_Collecte` → … → `models/best_slowdown_model.joblib`) used to train the model, and a **separate, independent live collector** built into `dashboard/runtime.py` used at inference time. A dedicated automated test (`tests/test_dashboard.py::test_online_feature_parity`) verifies that the live feature computation produces numerically identical features to the offline training pipeline — this is a real, implemented safeguard against train/serve skew, not just a design intention.

## 6. Data Collection

**Collector.** `01_Collecte/AdoptAI-Monitor.exe` is a compiled Windows executable (~12 MB); its source code is **not included** in this repository, so only its documented behavior and its SQLite output schema could be verified. Per `01_Collecte/README.md`: it runs for 8 hours by default, samples every 2 seconds "when the machine is sufficiently available," never triggers CPU/RAM stress, and labels its rows `monitor`. The `runs` table confirms `collector_version = "2.4.0"` and `sample_interval_seconds = 2.0` for the sampled data, and `run_summary.csv` (produced later) confirms a **median sampling interval of ~2.0 seconds** across all 67 runs, consistent with the documented design.

**Machine identification.** Both the historical collector and the live dashboard collector identify a machine by hashing local system information (hostname, OS, architecture) with SHA-256 and truncating to a 24-character anonymized ID (`dashboard/runtime.py::machine_id()`). The cleaned dataset contains exactly **4 distinct anonymized machine IDs**.

**Multi-machine support.** Yes — the raw `runs` table records `machine_id`, `os_name`, `os_version`, `architecture`, `hostname`, and `python_version` per run, and the merge step in `02_Merge_data` is explicitly designed to combine multiple `.db` files (one per machine/session) into a single dataset. 7 raw `.db` files were found in `01_Collecte/data/`.

**Storage schema.** Each raw SQLite database (verified directly, e.g. `metrics_1.db`) contains 5 tables:
- `schema_meta` — schema version bookkeeping.
- `runs` — one row per monitoring session: `run_id`, `machine_id`, `mode`, `started_at_utc`, `ended_at_utc`, `status`, `stop_reason`, `os_name`, `os_version`, `architecture`, `hostname`, `python_version`, `collector_version`, `sample_interval_seconds`, `config_json`.
- `events` — operational log entries (`event_type`, `phase`, `message`, `details_json`).
- `capabilities` — per-run record of which sensors were detected and their provider (e.g. `cpu`/`memory`/`disk`/`network`/`battery` via `psutil`; `gpu` via `LibreHardwareMonitor` / "Windows GPU Engine"; `temperature` via CPU-specific sensor providers such as "Intel Core i5-8259U / CPU Package").
- `system_metrics` — the actual telemetry rows.

**Metrics collected** (`system_metrics` table / live `Collector.collect()` in `dashboard/runtime.py`), with their purpose:

| Metric | Purpose |
|---|---|
| `cpu_pct`, `cpu_frequency_mhz`, `cpu_per_core_json` | Overall and per-core CPU load — the most direct pressure signal. |
| `ram_pct`, `ram_used_mb`, `ram_available_mb` | Memory pressure; low available RAM is a classic slowdown precursor. |
| `swap_pct`, `swap_used_mb` | Swapping indicates RAM exhaustion is forcing disk-backed memory, a strong slowdown signal. |
| `disk_usage_pct`, `disk_free_gb` | Storage capacity pressure. |
| `disk_read_mb_s`, `disk_write_mb_s`, `disk_latency_ms` | I/O throughput and latency — high latency directly correlates with a "sluggish" system. |
| `net_sent_mb_s`, `net_recv_mb_s`, `network_latency_ms` | Network throughput and reachability latency (measured live via a TCP connection to `1.1.1.1:443`). |
| `process_count`, `thread_count` | Workload intensity / potential resource contention. |
| `context_switches_per_s` | Scheduler pressure — very high context-switch rates indicate CPU contention beyond raw `cpu_pct`. |
| `temperature_c` | Thermal throttling risk (partially available; provider-dependent). |
| `gpu_usage_pct`, `gpu_per_device_json` | GPU load (via `nvidia-smi` in the live collector, or LibreHardwareMonitor/Windows GPU Engine in the historical collector). |
| `battery_pct`, `battery_plugged` | Power state context (laptops). |
| `missed_deadline`, `sensor_errors_json` | Collector self-diagnostics: whether a 2-second sampling deadline was missed, and any sensor read errors — used to flag sample reliability, not as slowdown evidence. |

Two columns, `stress_cpu_target_pct` and `stress_memory_target_mb`, exist in the schema but are **100% missing** in the collected data — they appear to be reserved for an artificial CPU/RAM stress-test mode that was never exercised in this dataset (consistent with the README's statement that the collector "never triggers CPU or RAM stress").

**Live collection libraries** (`dashboard/runtime.py`): `psutil` for CPU/RAM/swap/disk/network/process/context-switch/battery metrics; the standard `socket` module for network latency; `subprocess` calling `nvidia-smi` for GPU usage (60-second cache); `psutil.sensors_temperatures` for temperature.

## 7. Data & Data Quality

The cleaned, EDA-analyzed dataset (`04_Pretraitement_Model/data/processed/cleaned_metrics.csv`, produced by `03_Nettoyage/nettoyage_donees.py`) has:

- **153,521 rows, 39 columns**
- **4 machines, 67 runs**
- Time range: **2026-07-23 to 2026-08-12** (as recorded in the data's own timestamps; roughly a 3-week collection window)
- Sampling: ~2 seconds between consecutive rows within a run (median interval confirmed at 2.0s in `reports/run_summary.csv`)

**Machine distribution is imbalanced**: machine `a0f8c860...` contributes 66,528 rows (43.3%), `0890dcc0...` 35,713 (23.3%), `7232bc53...` 26,191 (17.1%), `d588df12...` 25,089 (16.3%). Runs per machine: 11, 14, 17, 25 respectively.

**Run outcome distribution**: `interrupted` 64.5%, `running` 18.9% (i.e., never properly closed), `completed` only **16.7%** — the large majority of collection sessions did not end cleanly.

**Duplicates**: 0 fully duplicate rows and 0 duplicate `(run_id, timestamp)` pairs in the cleaned dataset (duplicates were removed upstream by the cleaning script).

**Missing values** (from `01_eda.ipynb`, computed on the cleaned dataset):

| Column | Missing % |
|---|---:|
| `stress_cpu_target_pct`, `stress_memory_target_mb`, `legacy_id` | 100.00% (unused/legacy columns) |
| `temperature_c` | 23.63% |
| `gpu_usage_pct` | 23.26% |
| `ended_at_utc` | 18.88% (consistent with the 18.9% of runs still `running`) |
| `context_switches_per_s` | 12.83% |
| `network_latency_ms` | 12.72% |
| `disk_read_mb_s`, `disk_write_mb_s`, `disk_latency_ms`, `net_sent_mb_s`, `net_recv_mb_s` | ~0.04–0.05% |

**Outliers**: the EDA notebook's boxplot analysis for CPU (and by the same method, the other core metrics) explicitly notes "no significant outliers are visible" — the data ranges (e.g. CPU 0–100%) are consistent with valid physical bounds. No formal outlier-removal step was implemented anywhere in the pipeline; extreme values were kept and, where relevant, handled through the reliability flag rather than deletion.

**Data quality / reliability flag (`sample_reliable`)**: computed from `missed_deadline`, `sensor_errors_json`, invalid timestamps, and missing `run_id`. Overall, **58.7% of rows are flagged reliable, 41.3% unreliable**. This is highly uneven across machines — reliability by machine (`01_eda.ipynb`):

| Machine | Reliable samples |
|---|---:|
| `0890dcc046c079acc4de4202` | **0.00%** |
| `7232bc533c21ce408d45d473` | 91.92% |
| `a0f8c86097e55fbfa506d057` | 80.85% |
| `d588df123ac0d0ce20b112ac` | 48.60% |

One machine contributing 23.3% of all rows has **zero** samples flagged reliable — a genuine and material data-quality limitation, not previously resolved in the pipeline (rows are kept and flagged, not removed).

**Collection gaps**: `03_time_structure_audit.ipynb` flags intervals exceeding 5× the normal sampling interval as `large_gap`. `04_gap_investigation.ipynb` and `05_gap_validation.ipynb` investigate 863 such gaps and split the timeline into **930 segments** across 67 runs so that no rolling/label calculation crosses a gap. Gap re-classification (`reports/gap_validation_summary.csv`) found that of the validated gaps, **61.8% were reclassified as `collection_delay_sensor_timeout`**, 23.3% as `weak_resource_pressure`, 6.7% as `small_sampling_delay`, 2.9% as `likely_pause_or_sleep`, 5.3% as `insufficient_evidence`, and **0.0%** as `strong_resource_pressure`. In other words, essentially none of the investigated timing gaps were confirmed to be caused by a genuinely severe resource-pressure stall — most were sensor/collection artifacts.

**Merging and transformation.** `02_Merge_data/combin_db.py` merges all `.db` files found in a `data/` folder, deduplicates each table on a table-specific key (e.g., `system_metrics` on `machine_id, run_id, timestamp`), regenerates auto-increment IDs to avoid cross-file collisions, sorts, indexes, and writes a merged `.db` plus a `.csv` export of `system_metrics`. `03_Nettoyage/nettoyage_donees.py` then aligns `machine_id` to the `runs` table (treated as source of truth), normalizes timestamps to UTC, computes the `sample_reliable` and `run_complete` flags, removes duplicate `(run_id, timestamp)` samples (favoring reliable, more complete rows), and exports the final `cleaned_metrics.csv` used for all downstream analysis.

## 8. Preprocessing

| Step | Where implemented | Why |
|---|---|---|
| `machine_id` correction (align to `runs` table) | `03_Nettoyage/nettoyage_donees.py::fix_machine_id` | Historical hostname values were replaced by an anonymized machine ID; the `runs` table is treated as the source of truth. |
| Timestamp normalization to UTC datetime | `nettoyage_donees.py::normalize_timestamps` | Required for any time-based sorting, rolling window, or gap analysis. |
| Reliability flagging (`sample_reliable`) | `nettoyage_donees.py::flag_reliability` | Marks rows with a missed sampling deadline, a sensor error, an invalid timestamp, or a missing run reference — without deleting them, so downstream steps can decide how to treat them. |
| Run-completion flagging (`run_complete`) | `nettoyage_donees.py::flag_reliability` | Distinguishes runs that ended cleanly (`status` in a recognized "successful" set and a valid `ended_at_utc`) from interrupted/still-running sessions. |
| Duplicate removal on `(run_id, timestamp)` | `nettoyage_donees.py::drop_duplicate_samples` | Keeps the most reliable, most complete row when two samples share the same run and timestamp. |
| Chronological sort by machine/run/timestamp | `nettoyage_donees.py` (final step) | Establishes the ordering required for every later time-aware calculation. |
| Gap detection & thresholding | `03_time_structure_audit.ipynb` | Flags intervals more than 5× the nominal 2-second sampling interval. |
| Segmentation around gaps | `04_gap_investigation.ipynb` → `data/interim/segmented_metrics.csv` | Prevents rolling windows, labels, or features from silently bridging a real collection interruption. |
| Median imputation of missing feature values | `11_preprocessing_and_modeling.ipynb::build_preprocessor` (fit on train only) | Lag/rolling features are undefined at the start of each segment; some sensors (temperature, GPU, context switches, network latency) are intermittently absent. Median is robust to skew. |
| Standardization (`StandardScaler`) | `11_preprocessing_and_modeling.ipynb`, **Logistic Regression only** | Linear models are scale-sensitive; tree-based models (Random Forest, XGBoost, LightGBM) are scale-invariant and were left unscaled. |
| No explicit outlier removal / filtering / resampling step was found in the pipeline. | — | EDA concluded values were within plausible physical ranges; the reliability flag was used instead of outlier deletion. |

## 9. Feature Engineering

Implemented in `10_feature_engineering.ipynb`, applied identically and independently to the train, validation, and test splits, grouped by `(machine_id, run_id, segment_id)` so that **no feature ever uses data from a future row or from a different segment/run/machine**.

For each of the 5 main resource metrics (`cpu_pct`, `ram_pct`, `swap_pct`, `disk_latency_ms`, `context_switches_per_s`), six temporal features are created (30 features total):

| Feature | Formula / logic | Window | Role |
|---|---|---|---|
| `<metric>_lag_1` | Previous row's value in the same segment | 1 step (~2s) | Immediately prior system state. |
| `<metric>_diff_1` | Current − previous value | 1 step | Instantaneous rate of change. |
| `<metric>_mean_30s` | Trailing rolling mean, min. 3 observations | 30 seconds | Short-term sustained pressure. |
| `<metric>_mean_60s` | Trailing rolling mean, min. 3 observations | 60 seconds | Persistent (less noisy) pressure. |
| `<metric>_std_60s` | Trailing rolling standard deviation | 60 seconds | Recent instability/volatility. |
| `<metric>_max_60s` | Trailing rolling maximum | 60 seconds | Recent spikes a mean could hide. |

Three domain features:
- `cpu_ram_interaction` = `(cpu_pct/100) × (ram_pct/100)` — simultaneous CPU+RAM pressure.
- `threads_per_process` = `thread_count / process_count` — workload intensity per process.
- `time_since_segment_start_seconds` — elapsed monitoring time within the current continuous segment.

Four missing-sensor indicators (`network_latency_ms_missing`, `context_switches_per_s_missing`, `temperature_c_missing`, `gpu_usage_pct_missing`) — record sensor availability without imputing or dropping rows.

**Total: 37 new engineered features** (30 temporal + 3 domain + 4 missing-indicators), added on top of the safe raw columns, for **68 columns per split file** and **62 numeric feature columns** actually used by the models (after excluding `id`, `machine_id`, `run_id`, `segment_id`, `timestamp`, and the target).

**Temporal integrity** is explicitly verified by assertions in the notebook: lag/diff values are `NaN` at every segment start (proving no boundary crossing), `time_since_segment_start_seconds` is exactly 0 at every segment start, schemas are identical across the three splits, and no infinite values are produced. The same feature-building function is reused, unmodified, inside the live dashboard (`dashboard/runtime.py::Features.add`), and a dedicated test (`tests/test_dashboard.py::test_online_feature_parity`) checks numerical equality between the two implementations on real data.

## 10. Target Definition

**Type**: Binary classification.

**Present-time definition — `slowdown_now` ("Rule C")**: a row is a "slowdown" moment if, using only CPU, RAM, swap, disk latency, and context-switch rate (never timing/outcome/temperature/GPU fields), **at least one "severe" 60-second sustained signal** occurs (`cpu_pct ≥ 95%`, `ram_pct ≥ 95%`, `swap_pct ≥ 70%`, `disk_latency_ms ≥ 20ms`, or context-switch rate ≥ the run's 99th percentile **and** ≥ 2× the run's median) **OR at least two "moderate" 30-second sustained signals** occur (`cpu_pct ≥ 80%`, `ram_pct ≥ 85%`, `swap_pct ≥ 60%`, `disk_latency_ms ≥ 5ms`, or context-switch rate ≥ the run's 95th percentile **and** ≥ 1.5× the run's median).

Rule C was chosen (`06_label_definition.ipynb`) after comparing 3 candidate rules on positive-rate, event duration, and how concentrated positives were on a single machine/run — Rule C was the only one classified as a "balanced candidate for review" (9.3–24.3% positive rate range across the 3 rules; Rule C = 24.3% of all rows). **The notebook explicitly states this recommendation "requires manual validation and is not the final label rule."** No further evidence of that manual validation being completed was found elsewhere in the repository.

**Future label — `slowdown_in_5min` (main target)**: for each row, look strictly forward (never at the current row) within the same continuous segment; the label is `1` if `slowdown_now = 1` occurs anywhere in `(t, t + 5 minutes]`, `0` otherwise, and **missing (excluded)** if the segment does not extend a full 5 minutes past that row (avoiding false negatives from truncated horizons). A `slowdown_in_10min` label was also produced for comparison only and was **not used for modeling**.

**Horizon**: **5 minutes** is the modeled horizon. 10 minutes exists only as a secondary comparison in reports.

```text
Now
  ↓
Last ~60 seconds of history (lags, 30s/60s rolling mean/std/max
  for CPU, RAM, swap, disk latency, context switches)
  ↓
62 engineered features
  ↓
XGBoost model
  ↓
In the next 5 minutes:
Slowdown? YES / NO  (+ probability, e.g. 82%)
```

**Label prevalence**: after keeping only rows with a complete 5-minute horizon (133,016 of 153,521 rows, 86.6%), the label is **37.9% positive** (50,467 positive / 82,549 negative). Note: the notebook computes its own automatic usability check on this target (`usable_for_next_ml_step`) using thresholds it defines itself (minimum row/positive/negative counts, positive share between 1% and 30%, coverage across ≥2 machines/runs); this check **returned `False`**, specifically because the positive rate (37.9%) exceeds the notebook's own 30% "too many positives" ceiling. The project nonetheless proceeded to the modeling stage with this label.

## 11. Machine Learning

**Data used**: `train_features.csv` (84,184 rows, 29 runs, 4 machines), `val_features.csv` (29,935 rows, 6 runs), `test_features.csv` (16,510 rows, 6 runs) — produced by the chronological, whole-run split described in Section 9/10, then feature-engineered.

**Preprocessing inside the modeling pipeline**: median imputation (fit on train only) for all 62 features; additional `StandardScaler` only for Logistic Regression. All steps are wrapped in a single scikit-learn `Pipeline` per model so the exact same fitted transforms apply at prediction time.

**Class balance on train**: 67.47% negative / 32.53% positive → `scale_pos_weight = 2.0742` computed for XGBoost; `class_weight="balanced"` used for Logistic Regression, Random Forest, and LightGBM.

**Models compared**:

| Model | Library | Key parameters | Class-imbalance handling |
|---|---|---|---|
| Logistic Regression | scikit-learn | `max_iter=2000`, `random_state=42` | `class_weight="balanced"` |
| Random Forest | scikit-learn | `n_estimators=300`, `min_samples_leaf=2`, `random_state=42` | `class_weight="balanced"` |
| XGBoost | xgboost | `n_estimators=300`, `max_depth=6`, `learning_rate=0.05`, `subsample=0.9`, `colsample_bytree=0.9` | `scale_pos_weight=2.0742` |
| LightGBM | lightgbm | `n_estimators=300`, `learning_rate=0.05`, `num_leaves=31`, `random_state=42` | `class_weight="balanced"` |

All four take the same 62 engineered/raw feature columns as input and output a probability of `slowdown_in_5min = 1`. Training: a single `fit()` call per pipeline on the train split only (no cross-validation, no hyperparameter search — the parameters above were used directly, not tuned via a documented search process).

**Model selection**: validation ROC AUC (primary), validation F1 (tie-breaker). No baseline/dummy model (e.g., always-predict-majority-class) was trained or reported anywhere in the project, so a "Baseline" row cannot be filled from real project data.

### Validation results (`reports/model_comparison.csv`)

| Model | Accuracy | Precision | Recall | F1 | ROC AUC | Split |
|---|---:|---:|---:|---:|---:|---|
| Baseline | *Information non trouvée dans le projet* | | | | | |
| Logistic Regression | 0.8792 | 0.8633 | 0.8265 | 0.8445 | 0.9318 | validation |
| Random Forest | 0.9019 | 0.9001 | 0.8466 | 0.8725 | 0.9411 | validation |
| **XGBoost (selected)** | 0.8845 | 0.8492 | 0.8621 | 0.8556 | **0.9503** | validation |
| LightGBM | 0.8017 | 0.7023 | 0.8683 | 0.7766 | 0.9320 | validation |
| **XGBoost (final)** | **0.8262** | **0.8156** | **0.9256** | **0.8671** | **0.9246** | **test (held-out, evaluated once)** |

PR-AUC was not computed anywhere in the project (*Information non trouvée dans le projet*).

Test-set classification report (`11_preprocessing_and_modeling.ipynb`, XGBoost):

| Class | Precision | Recall | F1 | Support |
|---|---:|---:|---:|---:|
| No slowdown (0) | 0.8502 | 0.6688 | 0.7486 | 6,391 |
| Slowdown (1) | 0.8156 | 0.9256 | 0.8671 | 10,119 |

**Artifact**: `models/best_slowdown_model.joblib` (966.8 KB) — a full scikit-learn `Pipeline` (median imputer + XGBClassifier) bundled with metadata: `model_name`, `target_column`, `feature_columns` (62), `identifier_columns`, `random_state=42`, `selection_criteria`, and the validation/test metrics shown above. The live dashboard loads this exact artifact.

## 12. Model Evaluation

**What the results show**: on validation, all four models score reasonably well (ROC AUC 0.93–0.95), and XGBoost was selected because it had the highest validation ROC AUC — even though Random Forest actually scored **higher on validation accuracy (0.9019 vs 0.8845), precision (0.9001 vs 0.8492), and F1 (0.8725 vs 0.8556)**. The selection rule (AUC primary, F1 tie-break) is defensible and stated explicitly in the notebook, but it means the "winning" model was not the best performer on every metric — a nuance worth being transparent about.

**Why performance may be limited / methodological caveats**:
- **Provisional label**: `slowdown_now` (Rule C) is explicitly self-described as provisional and unvalidated. Every downstream metric ultimately measures how well the model predicts *this specific, threshold-based rule* — not an independently confirmed ground truth of "a real slowdown a user would notice."
- **Train→test distribution shift**: the positive rate rises sharply across the chronological split — **32.5% (train) → 39.7% (validation) → 61.3% (test)**. This is a natural consequence of a strict chronological, whole-run split (the most recent runs happen to contain more slowdown-labeled time), but it means the test-set evaluation is not measuring performance on a class balance similar to training. The drop in test accuracy (0.826) and the drop in "no slowdown" class recall (0.669 on test) versus the validation numbers is consistent with this shift, not necessarily evidence that the model itself has degraded.
- **No baseline for comparison**: without a majority-class or simple-threshold-rule baseline computed and reported, it is not possible to state precisely how much predictive value the ML models add beyond a naive rule (e.g., "predict slowdown if CPU is currently above 80%").
- **Data volume and diversity**: 4 machines, 67 runs (53 after the 15-minute minimum-duration filter), ~153,500 rows collected over about 3 weeks. This is a small dataset for a generalizable production model, and one machine contributed 0% "reliable" samples.
- **Missingness handled only by median imputation**: features derived from `context_switches_per_s`, `temperature_c`, `gpu_usage_pct`, and `network_latency_ms` have substantial missingness (up to ~25,000 of 84,184 training rows for the least available sensors). Median imputation is simple and can blur signal exactly when a struggling sensor might itself be informative.
- **No cross-validation, no confidence intervals**: a single fixed split was evaluated once each for model selection (validation) and final confirmation (test); no variance estimate exists for any reported metric.
- **Horizon choice**: 5 minutes was fixed by the notebook's own design and not compared against alternative horizons on model performance (10 minutes was computed only as a label-distribution comparison, never modeled).

**What could be improved**: build and report an explicit baseline (e.g., majority-class or a single-threshold heuristic) for honest comparison; complete and document the manual validation of the label rule; investigate and, if needed, correct for the train/test class-balance shift (e.g., stratified or rolling-window cross-validation across time); collect more machines and a longer time span to reduce the risk that the model has simply learned the idiosyncrasies of these 4 machines; add PR-AUC and calibration analysis given the label imbalance; and formally decide how to treat the machine with 0% sample reliability.

## 13. Risk Score

There is no separately named "risk scoring engine" or documented weighted formula distinct from the model's own probability output. What the live dashboard actually implements (`dashboard/runtime.py::Model.predict`):

```text
XGBoost probability (0–1, from predict_proba)
     ↓
Risk level thresholds:
   probability < 0.40  → "low"
   0.40 ≤ probability < 0.70 → "elevated"
   probability ≥ 0.70  → "high"
     ↓
AlertEngine (severity = risk level)
     ↓
Alert (only on upward transition into elevated/high, or after a 60s cooldown)
```

In addition, purely in the frontend (`dashboard/static/app.js`), a separate, simple **"Health" score (0–100)** is computed for display only: `health = 100 − (max(cpu_pct, ram_pct, disk_usage_pct) × 0.45) − (probability × 25)`. This is a presentational convenience combining current resource pressure and the model's probability into one number for the "Current Health" panel — it is **not** a validated or separately modeled risk score, is not persisted anywhere, and is distinct from the `risk_level` used for alerting.

## 14. Alert Engine

Implemented in `dashboard/runtime.py::AlertEngine`, and covered by an automated test (`tests/test_dashboard.py::test_alert_transition_and_cooldown`).

**Trigger conditions**: an alert event is created when the risk level is `elevated` or `high`, **and** either (a) risk just moved upward (e.g., from `low` to `elevated`, or `elevated` to `high`), or (b) risk remains at `elevated`/`high` and a 60-second cooldown has elapsed since the last alert — this avoids spamming duplicate notifications while risk stays elevated.

**Levels and behavior** (from `DASHBOARD.md`):
- **Low** (probability < 40%): no alert.
- **Elevated** (40–70%): amber mini-notification, event stored.
- **High** (≥ 70%): red mini-notification, event stored.

**Information shown**: each alert stores a timestamp, the triggering sample, severity, probability, a title ("High slowdown risk" / "Elevated slowdown risk"), and a human-readable message ("AdoptAI estimates a NN% chance of slowdown within five minutes."). Alerts are persisted in `data/dashboard.db` (`alerts` table) and can be acknowledged.

**How the user is informed**: a toast/mini-notification appears in the UI when an alert fires, and a dedicated "Critical events" page lists alert history with an "Acknowledge" action per alert.

**Status**: **fully functional**, not a placeholder — it is wired into the live prediction loop, persisted to SQLite, exposed via REST endpoints (`/api/alerts`, `/api/alerts/{id}/acknowledge`), and covered by an automated test.

## 15. Dashboard

**Technology**: Python backend using **FastAPI** + **Uvicorn**, served at `http://127.0.0.1:8765` (API docs auto-generated at `/docs`). Frontend is plain HTML/CSS/vanilla JavaScript (`dashboard/static/index.html`, `app.js`, `styles.css`) — no JS framework, no charting library (the live trend chart is a hand-drawn inline SVG).

**Pages** (`index.html` navigation):
1. **Overview** — slowdown probability gauge ("XGBoost forecast", risk tag: warming/low/elevated/high), a "Current Health" score panel (model name, feature count, inference time, sample count), six live metric cards (CPU, Memory, Disk, Network, Temperature, GPU) with progress bars, and a live SVG line chart of CPU%, RAM%, and risk probability over recent history.
2. **Telemetry** — detailed raw metrics: process count, thread count, context switches/s, disk read/write MB/s, network receive MB/s, swap %, free disk GB.
3. **Critical events** (alerts) — chronological list of elevated/high alerts with severity, message, and an acknowledge button; badge count of unacknowledged alerts in the navigation.
4. **Model health** — active model name, test ROC AUC / recall / F1 (pulled directly from the saved model artifact's metadata), and a model version identifier.

**Data refresh**: the frontend polls `/api/live` every 2 seconds (matching the collection interval).

**API endpoints** (`dashboard/app.py`): `GET /api/live`, `GET /api/health`, `POST /api/collector/start`, `POST /api/collector/stop`, `GET /api/history`, `GET /api/alerts`, `POST /api/alerts/{id}/acknowledge`, `GET /api/model`, `GET /api/model/comparison`.

**User journey**: the user launches `RUN_DASHBOARD.bat` (or `python run_dashboard.py`); the collector starts automatically on server startup; a browser tab opens automatically once the health endpoint responds; the Overview page shows a "warming up" state for the first 2 samples ("Building temporal context") and reports "history maturity" until 60 seconds of local history are available, after which real forecasts begin appearing; the user can switch to Telemetry for raw numbers, Critical events to review/acknowledge past alerts, or Model health to see which model is active and how it performed on the offline test set.

**Screenshots**: none exist in the repository (*Information non trouvée dans le projet* — no `.png`/`.jpg`/`.svg` files were found anywhere). For the presentation, it is recommended to **run the dashboard locally and capture live screenshots** of the four pages listed above (Overview with a populated gauge and chart, Telemetry, Critical events with at least one alert, and Model health).

## 16. Technical Stack

**Programming**
- Python (all notebooks, scripts, and the dashboard backend). The compiled collector (`AdoptAI-Monitor.exe`) is very likely also Python-based (its output schema and library usage — `psutil`, similar naming conventions — match the rest of the project), but its source is not present in the repository, so this cannot be confirmed with certainty.

**Data**
- Pandas, NumPy (all notebooks and scripts)
- SQLite (`sqlite3`), used for raw collection storage, the merged database, and the live dashboard's `dashboard.db`
- CSV as the interchange format between pipeline stages

**Machine Learning**
- scikit-learn (`LogisticRegression`, `RandomForestClassifier`, `Pipeline`, `ColumnTransformer`, `SimpleImputer`, `StandardScaler`, metrics)
- XGBoost (`XGBClassifier`) — the selected production model
- LightGBM (`LGBMClassifier`) — compared, not selected
- joblib — model artifact serialization

**Visualization**
- Matplotlib, Seaborn (notebooks: EDA, ROC curves, confusion matrices, feature importance)
- Hand-written inline SVG (dashboard live chart) — no Plotly/Streamlit/other dashboarding framework was used

**Web / API**
- FastAPI, Uvicorn (`uvicorn[standard]`), `StaticFiles` for serving the frontend

**Testing**
- pytest (`tests/test_dashboard.py`)

**Infrastructure**
- No Docker, docker-compose, CI/CD (GitHub Actions or similar), or cloud deployment configuration was found anywhere in the repository (*Information non trouvée dans le projet*). Deployment is local-only (see Section 17).

## 17. Deployment

**Historical/offline pipeline**: run manually, notebook by notebook, in the documented order `01 → 03 → 04 → 05 → 06 → 07 → 08 → 09 → 10 → 11` (per `04_Pretraitement_Model/README.md`), each stage reading/writing files on the local disk. No orchestration tool (Airflow, Prefect, Makefile, etc.) was found — execution order is manual and documentation-driven.

**Dashboard launch**:
- Windows: double-click `RUN_DASHBOARD.bat`, or
- Command line: `python run_dashboard.py` (optional `--host`, `--port`, `--no-browser` flags; defaults to `127.0.0.1:8765`)
- Dependencies: `pip install -r requirements-dashboard.txt` (`fastapi`, `uvicorn[standard]`, `numpy`, `pandas`, `psutil`, `joblib`, `scikit-learn`, `xgboost`)
- No environment variables or external configuration files were found; the only configurable parameters are the CLI flags above.
- The collector for the live dashboard is built into the FastAPI app's lifespan (`monitor.start()` on startup, `monitor.stop()` on shutdown) — no separate process/service needs to be launched.
- Data collector for historical data collection is the separate standalone `AdoptAI-Monitor.exe` (double-click to run, 8-hour default session).

**What is not present**: no containerization, no cloud hosting configuration, no authentication/HTTPS layer, no process manager (systemd/supervisor) for production use, no automated deployment pipeline. This is a **local, single-machine, developer-run prototype**, not a production deployment.

## 18. Implemented Features

The following are genuinely built, working, and evidenced by code, generated reports, or automated tests:

- Standalone telemetry collector (compiled executable) sampling ~25 metrics every 2 seconds, with run/event/capability metadata, across multiple machines.
- Multi-database merge pipeline with deduplication, ID regeneration, and indexing (`combin_db.py`).
- Data cleaning pipeline with machine-ID reconciliation, timestamp normalization, reliability flagging, and duplicate removal (`nettoyage_donees.py`).
- Structured EDA, temporal-structure audit, and gap investigation/validation, each producing reviewable CSV reports.
- A formally compared, documented, present-time "slowdown" label definition (3 candidate rules, one selected).
- A leakage-checked, forward-looking 5-/10-minute label creation process with explicit boundary and strictness assertions.
- A chronological, whole-run, leakage-validated train/validation/test split.
- A causal (past-only), parity-tested feature engineering pipeline (37 features) shared between offline training and live inference.
- A 4-model comparison (Logistic Regression, Random Forest, XGBoost, LightGBM) with a documented selection rule and a saved model artifact.
- A live monitoring dashboard: FastAPI backend, 4-page web UI, real-time inference every 2 seconds, SQLite persistence of samples/predictions/alerts, and a REST API.
- A working, cooldown-aware alert engine with acknowledgeable alerts.
- Automated tests covering model artifact integrity, alert cooldown behavior, and train/live feature parity.

## 19. Partial / Unimplemented Features

**Partially implemented**:
- Manual validation of the chosen label rule (Rule C) — explicitly flagged as required in the notebooks, but no evidence it was completed.
- Handling of the fully unreliable machine (0% `sample_reliable`) — the row is flagged but no dedicated remediation (exclusion, re-weighting, investigation) was found.
- Model robustness assessment — only a single split was evaluated; no cross-validation, no confidence intervals, no hyperparameter tuning process was documented.
- "Health" score on the dashboard Overview page — a simple presentational heuristic, not a validated or separately trained risk model.

**Not implemented / perspectives only**:
- Containerization (Docker) or any deployment automation.
- Multi-machine fleet view in the dashboard (the current dashboard only monitors the single local machine it runs on, even though the historical pipeline supports multiple machines).
- Production hardening: authentication, HTTPS, secrets management, process supervision.
- Automated model retraining or an MLOps monitoring loop for concept drift.
- A baseline model for honest performance comparison, and imbalance-aware metrics such as PR-AUC.
- Source code for the compiled collector executable is not part of this repository, limiting independent auditability of exactly how each metric is sampled at that layer.

## 20. Results

Summarized from Sections 11–12 (all figures from `reports/model_comparison.csv` and `11_preprocessing_and_modeling.ipynb`):

- Best model: **XGBoost**, selected by validation ROC AUC (0.9503).
- Final, once-only test evaluation: **ROC AUC 0.9246, Accuracy 0.8262, Precision 0.8156, Recall 0.9256, F1 0.8671**.
- The model catches the large majority of true slowdown windows on the test set (recall 92.6% for the positive class) at the cost of a meaningful false-positive rate on "no slowdown" moments (recall only 66.9% for the negative class).
- Random Forest was competitive and even outperformed XGBoost on several individual validation metrics (accuracy, precision, F1), though not on ROC AUC, the chosen selection criterion.
- No baseline/PR-AUC metrics are available for a fuller picture (see Section 12 for why this limits the conclusions that can be drawn).

## 21. Limitations

- **Data volume and diversity**: only 4 machines and 67 collection runs (53 usable after the 15-minute minimum-duration filter), ~153,500 rows over roughly 3 weeks — small for claims of general applicability.
- **Data quality**: one machine has 0% of its samples flagged reliable; run completion rate is only 16.7% (most sessions were interrupted or left running); several sensors (temperature, GPU, context switches, network latency) have double-digit missingness percentages.
- **Label validity**: the "slowdown" definition is explicitly provisional and self-flagged in the notebooks as requiring manual validation that does not appear to have been completed; gap investigation found that essentially none of the anomalous timing gaps were confirmed as genuine severe resource pressure (most were sensor/collection artifacts), which is relevant because the label itself is threshold-based on similar resource signals.
- **Train/test distribution shift**: the positive label rate rises from 32.5% (train) to 61.3% (test) across the chronological split, complicating a clean read of "true" future generalization.
- **No baseline comparison and no PR-AUC**: it cannot currently be stated with confidence how much value the ML model adds over a much simpler heuristic, nor how well it performs specifically on the minority/majority class trade-off beyond the reported precision/recall.
- **No cross-validation / variance estimate**: all reported metrics come from a single fixed split, evaluated once.
- **Horizon and scope are fixed**: only a 5-minute horizon was modeled; only one machine at a time is monitored live.
- **Infrastructure / production readiness**: no containerization, no cloud deployment, no authentication, no retraining pipeline — this is a local prototype, not production infrastructure.

## 22. Perspectives

### Court terme (short term)
- Complete and document the manual validation of the "slowdown_now" label rule (Rule C) before treating current model metrics as final.
- Compute and report an explicit baseline (majority-class and/or single-threshold heuristic) for honest comparison against the ML models.
- Investigate the train→validation→test positive-rate shift (32.5% → 39.7% → 61.3%) and decide whether re-splitting, stratifying, or reporting time-windowed metrics is warranted.
- Decide how to treat the machine with 0% sample reliability (exclude, re-weight, or investigate its collector configuration).

### Moyen terme (medium term)
- Collect more machines and a longer time span to test generalization beyond the current 4-machine, 3-week dataset.
- Add PR-AUC, calibration curves, and confidence intervals (via cross-validation or repeated time-based splits) to the evaluation.
- Improve missing-value handling for high-missingness sensors (context switches, temperature, GPU) beyond simple median imputation.
- Extend the dashboard to a multi-machine fleet view, since the historical pipeline already supports multiple machines.

### Long terme (long term)
- Containerize the dashboard and collector for repeatable deployment (Docker).
- Build a lightweight MLOps loop: scheduled retraining, model versioning, and drift monitoring as more data accumulates.
- Harden the dashboard for production use (authentication, HTTPS, process supervision, centralized storage instead of local SQLite).
- Evaluate additional prediction horizons and richer feature sets (e.g., per-process telemetry) once the current pipeline is validated at scale.

## 23. Business Value

### Quel problème ADOPTAI résout-il ?
It turns raw system telemetry into an early-warning signal: instead of only showing that a machine is currently under stress, it estimates the probability that a slowdown condition will occur in the next 5 minutes.

### Quelle est sa valeur ?
A working, end-to-end pipeline — from a real telemetry collector through to a live, model-driven dashboard with alerting — built and demonstrated on real (if limited) multi-machine data, with careful attention to avoiding data leakage at every stage (a common failure mode in this type of project that was explicitly and repeatedly guarded against here).

### Pourquoi est-ce intéressant pour l'entreprise ?
It is a proof of concept that the company's own telemetry can be transformed into a forward-looking product feature (predictive alerting) rather than a purely descriptive one (classic dashboards), using open-source tooling with no licensing cost, and with the core technical risks (feature/label leakage, train/serve skew) already identified and mitigated in the current implementation.

### Quel gain potentiel apporte une approche prédictive ?
On the test data evaluated here, the model detects 92.6% of labeled slowdown windows before/as they occur, versus a purely reactive tool that could only report a slowdown once it is already underway. The practical business gain (time saved, incidents avoided) has not yet been measured in a real deployment and would need a pilot to quantify.

### Qu'est-ce qui différencie ADOPTAI d'un simple dashboard de monitoring ?
A classic dashboard reports current state. AdoptAI additionally produces a calibrated probability of a future event (5-minute-ahead slowdown), derived from a supervised model trained on causal, time-aware features — and turns that probability into an alerting workflow, not just a chart.

### Quel est le potentiel de passage en production ?
Not immediate. The modeling and dashboard engineering are functionally complete for a single machine, but the label still needs validation, the dataset needs to grow beyond 4 machines, there is no containerized/cloud deployment, and there is no production-grade security or retraining process yet. A realistic path is a pilot on a small, monitored fleet before wider rollout.

### Quelles sont les prochaines étapes nécessaires ?
See Section 22 (Perspectives) — in priority order: validate the label, add a baseline for honest comparison, address the train/test distribution shift, then scale up data collection and harden the deployment.

## 24. Presentation Plan

*A proposed structure for a 12–15 slide presentation, following Problem → Solution → Architecture → Data → AI → Results → Dashboard → Value → Limitations → Perspectives.*

### Slide 1 — Title
**Objectif :** Set context.
**Message principal :** AdoptAI: from reactive monitoring to predictive slowdown detection.
**Contenu à afficher :** Project name, one-line tagline, date, presenter.
**Graphique / schéma recommandé :** None.
**Fichier source à utiliser :** —
**Message oral :** "Today I'll show you how we turned raw system telemetry into a working, forward-looking slowdown predictor."

### Slide 2 — The Problem
**Objectif :** Establish the pain point.
**Message principal :** Classic monitoring only tells you a machine is *already* struggling.
**Contenu à afficher :** "Before AdoptAI" vs "With AdoptAI" — reactive vs predictive framing.
**Graphique / schéma recommandé :** Simple two-column comparison graphic.
**Fichier source à utiliser :** Section 3 of this report.
**Message oral :** "By the time a monitoring tool shows red, the user has often already lost productive time."

### Slide 3 — What AdoptAI Does
**Objectif :** State the solution in one sentence.
**Message principal :** AdoptAI estimates the probability of a slowdown in the next 5 minutes from live telemetry.
**Contenu à afficher :** The "Now → history → features → model → 5-minute forecast" diagram.
**Graphique / schéma recommandé :** The target-definition diagram from Section 10.
**Fichier source à utiliser :** `07_future_label_creation (1).ipynb`, Section 10 of this report.
**Message oral :** "It's a simple question the model answers every 2 seconds: will there be a slowdown in the next 5 minutes?"

### Slide 4 — End-to-End Architecture
**Objectif :** Show the whole pipeline exists and is coherent.
**Message principal :** From a real collector to a live dashboard, every stage is implemented.
**Contenu à afficher :** The full architecture diagram (Section 5).
**Graphique / schéma recommandé :** Vertical pipeline diagram, collector → storage → cleaning → features → model → dashboard.
**Fichier source à utiliser :** Section 5 of this report; `04_Pretraitement_Model/README.md`.
**Message oral :** "Each of these boxes is real, working code — not a plan."

### Slide 5 — Data Collection
**Objectif :** Ground the project in real telemetry.
**Message principal :** ~25 metrics collected every 2 seconds, across 4 machines.
**Contenu à afficher :** Metric list highlights (CPU, RAM, disk latency, context switches...), sampling interval, machine count.
**Graphique / schéma recommandé :** Icon row of metric categories (CPU/RAM/Disk/Network/GPU).
**Fichier source à utiliser :** `01_Collecte/README.md`, Section 6 of this report.
**Message oral :** "This isn't synthetic data — it's real telemetry from real machines, collected over three weeks."

### Slide 6 — Dataset Snapshot
**Objectif :** Show scale and honesty about data quality.
**Message principal :** 153,521 rows, 4 machines, 67 runs — and known quality caveats.
**Contenu à afficher :** Row/machine/run counts, missing-value highlights, the 0%-reliable-machine finding.
**Graphique / schéma recommandé :** Bar chart of rows per machine + reliability % per machine (dataviz skill recommended).
**Fichier source à utiliser :** `01_eda.ipynb`, Section 7 of this report.
**Message oral :** "The dataset is real but modest — and we're being upfront that one machine's data is currently unreliable."

### Slide 7 — Defining "Slowdown"
**Objectif :** Explain the target in plain terms.
**Message principal :** A slowdown is sustained CPU/RAM/swap/disk/context-switch pressure — defined and compared, not guessed.
**Contenu à afficher :** The 3 candidate rules and why Rule C was chosen; explicit "provisional, needs validation" caveat.
**Graphique / schéma recommandé :** Simple threshold table (moderate vs severe) for the 5 signals.
**Fichier source à utiliser :** `06_label_definition.ipynb`, `reports/label_rule_comparison.csv`.
**Message oral :** "We tested three different definitions of 'slowdown' before picking one — and we're transparent that it still needs a final human sign-off."

### Slide 8 — Feature Engineering
**Objectif :** Show the model sees trend, not just a snapshot.
**Message principal :** 37 causal features (lags, 30–60s rolling stats) built without ever peeking at the future.
**Contenu à afficher :** Feature family breakdown (temporal/domain/missing-indicators), leakage-safety guarantee.
**Graphique / schéma recommandé :** Small feature family pie/bar chart (30 temporal / 3 domain / 4 missing-indicator).
**Fichier source à utiliser :** `10_feature_engineering.ipynb`, Section 9 of this report.
**Message oral :** "Every feature only looks backward — this is what lets the model make a genuine forecast, not a description."

### Slide 9 — Model Comparison
**Objectif :** Show rigor in model selection.
**Message principal :** Four models compared fairly on the same validation set; XGBoost selected.
**Contenu à afficher :** The validation metrics table (Section 11).
**Graphique / schéma recommandé :** Grouped bar chart of Accuracy/Precision/Recall/F1/ROC AUC per model.
**Fichier source à utiliser :** `reports/model_comparison.csv`.
**Message oral :** "We didn't just pick one model — we compared four, transparently, on the same held-out data."

### Slide 10 — Final Results
**Objectif :** State the headline result honestly.
**Message principal :** On unseen future data, the model catches 92.6% of true slowdown windows.
**Contenu à afficher :** Test metrics (ROC AUC 0.9246, Precision 0.8156, Recall 0.9256, F1 0.8671) + the classification report.
**Graphique / schéma recommandé :** Confusion matrix (test set) + ROC curve.
**Fichier source à utiliser :** `11_preprocessing_and_modeling.ipynb`.
**Message oral :** "The model rarely misses a real slowdown — the trade-off is a moderate rate of false alarms, which we discuss honestly next."

### Slide 11 — Being Honest About Limits
**Objectif :** Build credibility with the CEO/supervisor by not overselling.
**Message principal :** Small dataset, provisional label, and a class-balance shift between train and test.
**Contenu à afficher :** 3 bullet limitations from Section 21, framed constructively.
**Graphique / schéma recommandé :** Simple "Known limitations" checklist slide.
**Fichier source à utiliser :** Section 21 of this report.
**Message oral :** "We'd rather tell you exactly where this stands today than overstate it."

### Slide 12 — The Live Dashboard
**Objectif :** Make the product tangible.
**Message principal :** A real-time web dashboard already exists and runs the model live.
**Contenu à afficher :** Screenshot of the Overview page (probability gauge, live metrics, chart).
**Graphique / schéma recommandé :** Live screenshot (to be captured — none exist yet in the repo).
**Fichier source à utiliser :** `dashboard/static/index.html` (run locally to capture).
**Message oral :** "This isn't a mockup — you're looking at the actual running application."

### Slide 13 — Alerts in Action
**Objectif :** Show the "so what" — the model drives real action.
**Message principal :** Elevated/high risk automatically triggers a stored, acknowledgeable alert.
**Contenu à afficher :** Screenshot of the Critical events page; alert threshold table (Section 14).
**Graphique / schéma recommandé :** Live screenshot + the low/elevated/high threshold diagram.
**Fichier source à utiliser :** `dashboard/runtime.py`, `DASHBOARD.md`.
**Message oral :** "When risk crosses 70%, the user is notified immediately, with a full history to review afterward."

### Slide 14 — Business Value & Next Steps
**Objectif :** Land the pitch.
**Message principal :** A validated proof of concept, with a clear, prioritized path to production.
**Contenu à afficher :** Short-term/medium-term/long-term roadmap from Section 22.
**Graphique / schéma recommandé :** 3-column roadmap (short/medium/long term).
**Fichier source à utiliser :** Section 22–23 of this report.
**Message oral :** "The foundation works end-to-end. The next steps are about validating and scaling it, not rebuilding it."

### Slide 15 — Questions
**Objectif :** Open the floor.
**Message principal :** —
**Contenu à afficher :** "Questions?" plus contact/repo reference.
**Graphique / schéma recommandé :** None.
**Fichier source à utiliser :** —
**Message oral :** "Happy to go deeper into any part — data, modeling, or the live dashboard."

## 25. CEO Questions & Answers

### Questions CEO / Business

**Q1. What problem does AdoptAI actually solve for us?**
It replaces "wait until a machine is visibly struggling" with "get a warning up to 5 minutes before a slowdown condition, based on real telemetry trends."

**Q2. Is this ready to sell or deploy today?**
No. It's a working proof of concept on a small dataset (4 machines) with a label definition that its own creators flagged as needing manual validation. It proves the approach works technically; it is not production-hardened.

**Q3. How much better is this than what we have today (or a simple dashboard)?**
We can't yet put an exact number on it — no baseline comparison was computed. What we can say: the model catches over 92% of labeled slowdown windows in the held-out test, versus a purely reactive tool that has no forward-looking signal at all.

**Q4. What would it take to get this into production?**
Validate the label definition, expand the dataset beyond 4 machines, add containerized deployment, and add basic production hardening (auth, monitoring, retraining). See the roadmap in Section 22.

**Q5. What's the cost profile — is this expensive to run?**
The full stack is open-source (Python, scikit-learn, XGBoost, FastAPI) with no licensing costs; the main future cost is engineering time to scale data collection and productionize deployment. No cost/infrastructure estimates were found in the project (*Information non trouvée dans le projet*).

**Q6. Could this scale to monitor our whole fleet of machines?**
The historical data pipeline already supports multiple machines. The live dashboard currently monitors only the single machine it runs on — extending it to a fleet view is a defined, but not yet built, next step.

**Q7. What's the biggest risk in this project right now?**
That the label defining "slowdown" is still provisional and unvalidated, and the dataset is small — so today's strong-looking metrics may not fully hold once tested on more data or a confirmed label.

### Questions Data Science / ML

**Q8. Why was XGBoost chosen over Random Forest, which scored higher on some validation metrics?**
Model selection used validation ROC AUC as the primary criterion (a threshold-independent ranking metric, well suited to imbalanced classification), with F1 as a tie-breaker. XGBoost had the highest ROC AUC (0.9503 vs 0.9411 for Random Forest) even though Random Forest had higher accuracy, precision, and F1 on validation — a documented, defensible but debatable trade-off.

**Q9. How was class imbalance handled?**
Via `class_weight="balanced"` for Logistic Regression, Random Forest, and LightGBM, and `scale_pos_weight` (computed from the train negative/positive ratio, ≈2.07) for XGBoost. No resampling (SMOTE, undersampling) was used.

**Q10. Why is test performance lower than validation performance?**
Partly expected generalization gap, but largely explained by a genuine distribution shift: the positive label rate rises from 32.5% (train) to 61.3% (test) because the split is strictly chronological. This makes the test set intrinsically different in composition from train/validation, not just "harder."

**Q11. Was there any data leakage risk, and how was it addressed?**
Yes, and it was addressed explicitly at every stage: features only use past/current rows within the same continuous segment (verified by assertions), the label search window only looks strictly forward, the train/val/test split is by whole run (never split mid-run) and strictly chronological per machine, and preprocessing statistics (imputation medians, scaler parameters) are fit on train only.

**Q12. Was the model cross-validated?**
No. A single fixed split was used, with model selection on validation and one final confirmation on test. No cross-validation or repeated-split variance estimate exists.

### Questions techniques

**Q13. What does the live dashboard actually run in production (technically)?**
A FastAPI + Uvicorn Python server that collects telemetry every 2 seconds via `psutil` (plus `nvidia-smi` for GPU), computes the same 37 engineered features used in training, runs them through the saved XGBoost pipeline (`models/best_slowdown_model.joblib`), evaluates alert thresholds, and stores everything in a local SQLite database (`dashboard.db`). The frontend is plain HTML/CSS/JS polling a REST API every 2 seconds.

**Q14. How do we know the live features match the training features exactly?**
A dedicated automated test (`tests/test_dashboard.py::test_online_feature_parity`) feeds real historical rows through the live feature-computation code and asserts numerical equality (to `1e-9`) against the offline `train_features.csv` values for the same rows.

**Q15. Is this deployed with Docker / in the cloud?**
No. There is no Dockerfile, docker-compose file, or cloud deployment configuration anywhere in the repository. It runs locally via a batch file or a Python command on `127.0.0.1`.

### Questions sur les limites

**Q16. Is the "slowdown" label trustworthy?**
It is a clearly documented, threshold-based rule (Rule C) chosen after comparing three candidates — but the notebooks themselves flag it as provisional and requiring manual validation, which does not appear to have happened yet. Treat current metrics as a strong first pass, not a final validated ground truth.

**Q17. Can these results be trusted to generalize to other machines/environments?**
Not yet with high confidence. The dataset covers only 4 machines over about 3 weeks, and one of those machines has 0% "reliable" samples. More data across more machines and longer periods is needed before generalization claims are safe.

**Q18. What metric is missing that we'd want before trusting this more?**
A baseline comparison (majority-class or simple heuristic) and PR-AUC (more informative than ROC AUC under class imbalance) were not computed in the project and should be added.

## 26. Technical Questions & Answers

*(Additional depth beyond Section 25, for a more technical audience — e.g., a data science supervisor.)*

**Q19. What exactly are the 62 model features, in short?**
Safe raw telemetry columns (elapsed time, CPU/RAM/swap/disk/network/process/thread/context-switch/temperature/GPU/battery readings, plus `missed_deadline` and `sample_reliable`) combined with 37 engineered features: for 5 core metrics (CPU%, RAM%, swap%, disk latency, context switches/s) — a 1-step lag, a 1-step difference, 30s and 60s rolling means, a 60s rolling std, and a 60s rolling max (30 features); plus 3 domain features (CPU×RAM interaction, threads-per-process, time since segment start); plus 4 missing-sensor indicators.

**Q20. How is "segment" defined and why does it matter?**
A segment is a maximal continuous stretch of samples within one run and machine, bounded by detected collection gaps (intervals more than 5× the nominal ~2-second sampling interval). All rolling/lag features and the forward-looking label search are computed strictly within a segment, so a real data-collection interruption can never be mistaken for, or contaminate, a genuine trend.

**Q21. Why 30-second and 60-second windows specifically, and not something else?**
The project's own documentation frames 30 seconds as capturing "short-term sustained pressure" and 60 seconds as "persistent pressure," each requiring a minimum of 3 observations to avoid a single noisy sample triggering a false signal. No systematic window-size sensitivity analysis (comparing e.g. 15s/45s/90s alternatives) was found in the project (*Information non trouvée dans le projet*).

**Q22. Were hyperparameters tuned?**
No documented hyperparameter search (grid/random/Bayesian) was found. The parameters listed in Section 11 (e.g., XGBoost's `n_estimators=300`, `max_depth=6`, `learning_rate=0.05`) were used directly as fixed values.

**Q23. What happens if the model file or a sensor is unavailable at inference time?**
The dashboard is defensive: if the model artifact fails to load, `Model.predict()` returns a `model_unavailable` state instead of crashing; if a sensor value is missing at prediction time, the corresponding `_missing` indicator feature is set and the value is imputed downstream by the pipeline's median imputer (fit on train).

**Q24. How is the model versioned?**
Informally — the "version" shown in the dashboard is derived from the model file's modification time and size (`f"{mtime}-{size}"`), not a formal semantic version or a model registry.

## 27. Final Conclusion

AdoptAI is a coherent, end-to-end proof of concept: a real telemetry collector, a carefully leakage-checked data and labeling pipeline, a fairly compared set of machine learning models, and — notably — a genuinely working live dashboard that runs the trained model in real time with alerting. The engineering discipline around avoiding data leakage (causal features, strict chronological/whole-run splitting, train-only preprocessing fitting, and an automated train/serve parity test) is a real strength and should be highlighted as such.

The project's own documentation is unusually honest about its own limitations — most notably that the core "slowdown" label is explicitly provisional — and this report has preserved and foregrounded that honesty rather than smoothing it over. The headline results (validation ROC AUC ~0.95, test ROC AUC ~0.92, test recall ~93% for slowdown detection) are genuinely strong for a first pass, but they should be presented alongside the caveats in Sections 12 and 21: a small and unevenly reliable dataset, a provisional label, a notable train/test class-balance shift, and the absence of a baseline comparison.

The recommended framing for the CEO and academic supervisor is: **the technical foundation works and is well-engineered; the next phase is about validating the label, adding a baseline for honest comparison, and scaling up data collection — not rebuilding the pipeline.**

---

## Fichiers analysés

- `01_Collecte/README.md`, `01_Collecte/AdoptAI-Monitor.exe` (binary inspected via SQLite schema only), `01_Collecte/data/metrics_1.db` … `metrics_7.db`
- `02_Merge_data/README.md`, `02_Merge_data/combin_db.py`
- `03_Nettoyage/README.md`, `03_Nettoyage/nettoyage_donees.py`
- `04_Pretraitement_Model/README.md`, `04_Pretraitement_Model/DASHBOARD.md`
- `04_Pretraitement_Model/01_eda.ipynb`
- `04_Pretraitement_Model/03_time_structure_audit.ipynb`
- `04_Pretraitement_Model/04_gap_investigation.ipynb`
- `04_Pretraitement_Model/05_gap_validation.ipynb`
- `04_Pretraitement_Model/06_label_definition.ipynb`
- `04_Pretraitement_Model/07_future_label_creation (1).ipynb`
- `04_Pretraitement_Model/08_prepare_dataset_for_split.ipynb`
- `04_Pretraitement_Model/09_temporal_split.ipynb`
- `04_Pretraitement_Model/10_feature_engineering.ipynb`
- `04_Pretraitement_Model/11_preprocessing_and_modeling.ipynb`
- `04_Pretraitement_Model/12_run_dashboard.py`
- `04_Pretraitement_Model/dashboard/app.py`, `dashboard/runtime.py`, `dashboard/static/index.html`, `dashboard/static/app.js`
- `04_Pretraitement_Model/tests/test_dashboard.py`
- `04_Pretraitement_Model/requirements-dashboard.txt`, `RUN_DASHBOARD.bat`, `.gitignore`
- `04_Pretraitement_Model/reports/*.csv` (model_comparison, split_summary, run_summary, segment_summary, time_structure_audit, gap_validation, gap_validation_summary, gap_investigation, label_rule_comparison, label_distribution_by_machine, label_distribution_by_run, future_label_summary, future_label_by_machine, future_label_by_run)
- `04_Pretraitement_Model/models/best_slowdown_model.joblib` (metadata inspected via the dashboard/runtime code path and notebook outputs, not by directly deserializing the file in this analysis)

## Informations manquantes

- Source code of the compiled collector `AdoptAI-Monitor.exe` (not present in the repository).
- Any explicit baseline/dummy model comparison (majority-class or simple heuristic) with the same metrics as the ML models.
- PR-AUC or other imbalance-specific metrics.
- Evidence that the "manual validation" of the slowdown label rule (explicitly requested by the notebooks) was completed.
- Any documented hyperparameter search process (the parameters used appear to be fixed choices, not the output of a tuning procedure).
- A defined target user/persona or market document.
- Cost, infrastructure sizing, or business-case quantification.
- Screenshots or other visual assets of the dashboard (none exist in the repository; recommended to capture before the presentation).
- Confirmation of the exact programming language/framework used inside the compiled collector executable.

## Niveau de confiance

**Élevé** pour les éléments directement vérifiés dans le code, les notebooks (cellules et sorties), les rapports CSV générés, et les schémas SQLite inspectés directement (métriques collectées, définition de la target, comparaison des modèles, résultats chiffrés, architecture du dashboard). **Moyen** pour les éléments qui reposent sur une déduction raisonnable mais non confirmée explicitement dans le projet (par ex. le langage du collecteur compilé, l'intention produit/persona utilisateur). Aucune métrique, technologie, ou fonctionnalité présentée ci-dessus n'a été inventée : lorsque l'information n'était pas disponible, cela a été indiqué explicitement.
