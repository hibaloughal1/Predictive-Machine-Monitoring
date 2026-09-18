import numpy as np
import pandas as pd
from dashboard.runtime import AlertEngine,Features,Model,MAIN

def test_model_artifact():
    model=Model(); assert model.ready; assert model.artifact["model_name"]=="XGBoost"; assert len(model.artifact["feature_columns"])==62

def test_alert_transition_and_cooldown():
    engine=AlertEngine()
    assert engine.evaluate({"risk_level":"low","probability":.2}) is None
    first=engine.evaluate({"risk_level":"elevated","probability":.55}); assert first and first["severity"]=="elevated"
    assert engine.evaluate({"risk_level":"elevated","probability":.58}) is None
    high=engine.evaluate({"risk_level":"high","probability":.82}); assert high and high["severity"]=="high"

def test_online_feature_parity():
    raw=pd.read_csv("data/processed/train_dataset.csv"); raw["_t"]=pd.to_datetime(raw.timestamp,format="mixed",utc=True)
    expected=pd.read_csv("data/processed/train_features.csv").set_index("id")
    seg=next(g for _,g in raw.groupby(["machine_id","run_id","segment_id"],sort=False) if len(g)>=40).sort_values("_t").head(40)
    builder=Features(2); t0=seg.iloc[0]._t
    for row in seg.drop(columns="_t").to_dict("records"):
        t=pd.to_datetime(row["timestamp"],format="mixed",utc=True); latest=builder.add(row,1000+(t-t0).total_seconds())
    rid=seg.iloc[-1].id
    cols=[f"{m}_{s}" for m in MAIN for s in ["lag_1","diff_1","mean_30s","mean_60s","std_60s","max_60s"]]+["cpu_ram_interaction","threads_per_process","time_since_segment_start_seconds","network_latency_ms_missing","context_switches_per_s_missing","temperature_c_missing","gpu_usage_pct_missing"]
    for col in cols: assert np.isclose(latest[col],expected.loc[rid,col],equal_nan=True,rtol=1e-9,atol=1e-9),col
