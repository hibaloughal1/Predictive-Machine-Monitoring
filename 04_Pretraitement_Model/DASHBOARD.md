# Predictive Machine Monitoring Dashboard v2

Start by double-clicking `RUN_DASHBOARD.bat`, or run:

```powershell
python 12_run_dashboard.py
```

Open `http://127.0.0.1:8765`. API documentation is available at `/docs`.

The dashboard uses the replacement `models/best_slowdown_model.joblib`, whose XGBoost pipeline expects 62 features. It collects machine telemetry every two seconds, creates causal temporal features, performs inference, stores samples/predictions in `data/dashboard.db`, and displays mini notifications when criticality rises to elevated or high.

Alert behavior:

- Low: probability below 40%; no alert event.
- Elevated: 40% to below 70%; amber mini notification and stored event.
- High: 70% or above; red mini notification and stored event.
- A 60-second cooldown avoids duplicate notifications while risk remains elevated.
- Alerts can be reviewed and acknowledged on the Critical Events page.
