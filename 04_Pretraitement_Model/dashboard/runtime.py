"""Live telemetry, causal features, XGBoost inference, alerts, and storage."""
from __future__ import annotations

import hashlib, json, math, platform, socket, sqlite3, subprocess, threading, time, uuid
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
import psutil

ROOT = Path(__file__).resolve().parents[1]
MODEL_PATH = ROOT / "models" / "best_slowdown_model.joblib"
DB_PATH = ROOT / "data" / "dashboard.db"
REPORT_PATH = ROOT / "reports" / "model_comparison.csv"
MAIN = ["cpu_pct", "ram_pct", "swap_pct", "disk_latency_ms", "context_switches_per_s"]
MISSING = ["network_latency_ms", "context_switches_per_s", "temperature_c", "gpu_usage_pct"]

def now_utc(): return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")
def machine_id(): return hashlib.sha256(f"{platform.node()}|{platform.system()}|{platform.machine()}".encode()).hexdigest()[:24]
def safe(v):
    if isinstance(v, dict): return {k:safe(x) for k,x in v.items()}
    if isinstance(v, (list,tuple)): return [safe(x) for x in v]
    if isinstance(v, (np.integer,np.bool_)): return v.item()
    if isinstance(v, (np.floating,float)):
        x=float(v); return x if math.isfinite(x) else None
    return v

class Collector:
    def __init__(self):
        self.last_time=self.last_disk=self.last_net=self.last_ctx=None
        self.gpu_cache=(None,[]); self.gpu_at=0.0; psutil.cpu_percent(None)
    def _rate(self, current, previous, attr, elapsed, divisor=1):
        if current is None or previous is None or not elapsed: return None
        a,b=getattr(current,attr,None),getattr(previous,attr,None)
        return None if a is None or b is None or a<b else round((a-b)/elapsed/divisor,4)
    def _latency(self):
        start=time.perf_counter()
        try:
            with socket.create_connection(("1.1.1.1",443),.8): pass
            return round((time.perf_counter()-start)*1000,2)
        except OSError: return None
    def _temperature(self):
        fn=getattr(psutil,"sensors_temperatures",None)
        if not callable(fn): return None
        try:
            vals=[float(x.current) for group in (fn() or {}).values() for x in group if x.current is not None]
            return max(vals) if vals else None
        except Exception: return None
    def _gpu(self):
        if time.monotonic()-self.gpu_at<60: return self.gpu_cache
        try:
            r=subprocess.run(["nvidia-smi","--query-gpu=name,utilization.gpu","--format=csv,noheader,nounits"],capture_output=True,text=True,timeout=2,check=False)
            devices=[]
            for line in r.stdout.splitlines():
                name,val=line.rsplit(",",1); devices.append({"name":name.strip(),"usage_pct":float(val)})
            result=(max((x["usage_pct"] for x in devices),default=None),devices)
        except Exception: result=(None,[])
        self.gpu_cache=result; self.gpu_at=time.monotonic(); return result
    def collect(self):
        t=time.monotonic(); elapsed=None if self.last_time is None else t-self.last_time
        mem,swap=psutil.virtual_memory(),psutil.swap_memory(); disk=psutil.disk_io_counters(); net=psutil.net_io_counters(); ctx=psutil.cpu_stats().ctx_switches
        usage=psutil.disk_usage((Path.home().anchor or "C:\\")); freq=psutil.cpu_freq(); battery=psutil.sensors_battery() if hasattr(psutil,"sensors_battery") else None
        latency=None
        if elapsed and disk is not None and self.last_disk is not None:
            ops=(disk.read_count-self.last_disk.read_count)+(disk.write_count-self.last_disk.write_count)
            ms=(disk.read_time-self.last_disk.read_time)+(disk.write_time-self.last_disk.write_time)
            latency=round(ms/ops,3) if ops>0 and ms>=0 else None
        gpu,devices=self._gpu(); threads=0
        for proc in psutil.process_iter(["num_threads"]):
            try: threads+=proc.info.get("num_threads") or 0
            except (psutil.NoSuchProcess,psutil.AccessDenied): pass
        result={
            "cpu_pct":psutil.cpu_percent(None),"cpu_frequency_mhz":getattr(freq,"current",None),
            "ram_pct":mem.percent,"ram_used_mb":round(mem.used/1e6,1),"ram_available_mb":round(mem.available/1e6,1),
            "swap_pct":swap.percent,"swap_used_mb":round(swap.used/1e6,1),"disk_usage_pct":usage.percent,"disk_free_gb":round(usage.free/1024**3,2),
            "disk_read_mb_s":self._rate(disk,self.last_disk,"read_bytes",elapsed,1e6),"disk_write_mb_s":self._rate(disk,self.last_disk,"write_bytes",elapsed,1e6),"disk_latency_ms":latency,
            "net_sent_mb_s":self._rate(net,self.last_net,"bytes_sent",elapsed,1e6),"net_recv_mb_s":self._rate(net,self.last_net,"bytes_recv",elapsed,1e6),"network_latency_ms":self._latency(),
            "process_count":len(psutil.pids()),"thread_count":threads,"context_switches_per_s":None if not elapsed or self.last_ctx is None else round((ctx-self.last_ctx)/elapsed,1),
            "temperature_c":self._temperature(),"gpu_usage_pct":gpu,"gpu_devices":devices,"battery_pct":getattr(battery,"percent",None),"battery_plugged":int(battery.power_plugged) if battery else None,
        }
        self.last_time,self.last_disk,self.last_net,self.last_ctx=t,disk,net,ctx
        return result

class Store:
    def __init__(self,path=DB_PATH):
        path.parent.mkdir(parents=True,exist_ok=True); self.lock=threading.Lock(); self.db=sqlite3.connect(path,check_same_thread=False); self.db.row_factory=sqlite3.Row
        with self.db:
            self.db.executescript("""PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS samples(id INTEGER PRIMARY KEY,timestamp TEXT,run_id TEXT,segment_id TEXT,machine_id TEXT,payload TEXT);
            CREATE TABLE IF NOT EXISTS predictions(id INTEGER PRIMARY KEY,sample_id INTEGER UNIQUE REFERENCES samples(id),probability REAL,predicted_class INTEGER,risk_level TEXT,state TEXT,model_version TEXT,inference_ms REAL);
            CREATE TABLE IF NOT EXISTS alerts(id INTEGER PRIMARY KEY,timestamp TEXT,sample_id INTEGER REFERENCES samples(id),severity TEXT,probability REAL,title TEXT,message TEXT,acknowledged INTEGER DEFAULT 0);
            CREATE INDEX IF NOT EXISTS ix_samples_time ON samples(timestamp); CREATE INDEX IF NOT EXISTS ix_alerts_time ON alerts(timestamp);""")
    def save(self,sample,prediction,alert=None):
        with self.lock,self.db:
            cur=self.db.execute("INSERT INTO samples(timestamp,run_id,segment_id,machine_id,payload) VALUES(?,?,?,?,?)",(sample["timestamp"],sample["run_id"],sample["segment_id"],sample["machine_id"],json.dumps(safe(sample))))
            sid=cur.lastrowid; self.db.execute("INSERT INTO predictions(sample_id,probability,predicted_class,risk_level,state,model_version,inference_ms) VALUES(?,?,?,?,?,?,?)",(sid,prediction.get("probability"),prediction.get("predicted_class"),prediction["risk_level"],prediction["state"],prediction.get("model_version"),prediction.get("inference_ms")))
            if alert:
                cur=self.db.execute("INSERT INTO alerts(timestamp,sample_id,severity,probability,title,message) VALUES(?,?,?,?,?,?)",(sample["timestamp"],sid,alert["severity"],alert["probability"],alert["title"],alert["message"])); alert["id"]=cur.lastrowid
        return sid
    def history(self,limit=600):
        with self.lock: rows=self.db.execute("SELECT s.id,s.timestamp,s.payload,p.probability,p.risk_level FROM samples s JOIN predictions p ON p.sample_id=s.id ORDER BY s.id DESC LIMIT ?",(limit,)).fetchall()
        out=[]
        for r in reversed(rows):
            d=json.loads(r["payload"]); out.append({"id":r["id"],"timestamp":r["timestamp"],"cpu_pct":d.get("cpu_pct"),"ram_pct":d.get("ram_pct"),"disk_usage_pct":d.get("disk_usage_pct"),"probability":r["probability"],"risk_level":r["risk_level"]})
        return out
    def alerts(self,limit=30):
        with self.lock: return [dict(r) for r in self.db.execute("SELECT * FROM alerts ORDER BY id DESC LIMIT ?",(limit,)).fetchall()]
    def acknowledge(self,alert_id):
        with self.lock,self.db: cur=self.db.execute("UPDATE alerts SET acknowledged=1 WHERE id=?",(alert_id,)); return cur.rowcount>0

class Features:
    def __init__(self,interval=2): self.interval=interval; self.rows=deque(maxlen=400); self.previous=None; self.segment=1; self.started=None
    @property
    def segment_id(self): return f"live-seg-{self.segment:03d}"
    def add(self,sample,mono):
        gap=None if self.previous is None else mono-self.previous
        if self.previous is None: self.started=mono
        if gap is not None and gap>max(5*self.interval,20): self.rows.clear(); self.segment+=1; self.started=mono
        self.previous=mono; sample["segment_id"]=self.segment_id; sample["time_since_segment_start_seconds"]=round(mono-self.started,3); self.rows.append(dict(sample))
        df=pd.DataFrame(self.rows); df["timestamp"]=pd.to_datetime(df.timestamp,utc=True); latest=df.iloc[-1].to_dict()
        for metric in MAIN:
            s=pd.to_numeric(df.get(metric),errors="coerce"); indexed=pd.Series(s.to_numpy(),index=df.timestamp)
            latest[f"{metric}_lag_1"]=s.shift().iloc[-1]; latest[f"{metric}_diff_1"]=s.diff().iloc[-1]
            latest[f"{metric}_mean_30s"]=indexed.rolling("30s",min_periods=3).mean().iloc[-1]
            r=indexed.rolling("60s",min_periods=3); latest[f"{metric}_mean_60s"]=r.mean().iloc[-1]; latest[f"{metric}_std_60s"]=r.std().iloc[-1]; latest[f"{metric}_max_60s"]=r.max().iloc[-1]
        latest["cpu_ram_interaction"]=(latest.get("cpu_pct",np.nan)/100)*(latest.get("ram_pct",np.nan)/100)
        latest["threads_per_process"]=latest.get("thread_count",np.nan)/latest.get("process_count",np.nan) if latest.get("process_count") else np.nan
        for col in MISSING: latest[f"{col}_missing"]=int(pd.isna(latest.get(col)))
        return latest

class Model:
    def __init__(self): self.artifact=None; self.error=None; self.load()
    def load(self):
        try:
            a=joblib.load(MODEL_PATH); required={"pipeline","feature_columns","model_name","target_column"}; missing=required-set(a)
            if missing: raise ValueError(f"Missing artifact keys: {sorted(missing)}")
            self.artifact=a; self.error=None
        except Exception as e: self.artifact=None; self.error=f"{type(e).__name__}: {e}"
    @property
    def ready(self): return self.artifact is not None
    @property
    def version(self):
        s=MODEL_PATH.stat() if MODEL_PATH.exists() else None; return f"{int(s.st_mtime)}-{s.st_size}" if s else None
    def info(self):
        a=self.artifact or {}; return safe({"ready":self.ready,"error":self.error,"model_name":a.get("model_name"),"target":a.get("target_column"),"feature_count":len(a.get("feature_columns",[])),"validation_metrics":a.get("validation_metrics",{}),"test_metrics":a.get("test_metrics",{}),"version":self.version})
    def predict(self,row):
        if not self.ready: return {"state":"model_unavailable","risk_level":"unavailable","probability":None,"predicted_class":None,"message":self.error}
        start=time.perf_counter()
        try:
            cols=self.artifact["feature_columns"]; frame=pd.DataFrame([{c:row.get(c,np.nan) for c in cols}]); prob=float(self.artifact["pipeline"].predict_proba(frame)[0,1])
            risk="high" if prob>=.70 else "elevated" if prob>=.40 else "low"
            return {"state":"ready","probability":prob,"predicted_class":int(prob>=.5),"risk_level":risk,"model_version":self.version,"inference_ms":round((time.perf_counter()-start)*1000,3),"message":"Slowdown forecast for the next five minutes."}
        except Exception as e: return {"state":"inference_error","risk_level":"unavailable","probability":None,"predicted_class":None,"message":f"{type(e).__name__}: {e}"}

class AlertEngine:
    """Creates mini-alert events on upward criticality transitions with cooldown."""
    def __init__(self): self.last_level="low"; self.last_at=0.0; self.cooldown=60
    def evaluate(self,pred):
        level=pred.get("risk_level"); prob=pred.get("probability")
        rank={"low":0,"elevated":1,"high":2}; upward=rank.get(level,0)>rank.get(self.last_level,0); cooled=time.monotonic()-self.last_at>=self.cooldown
        alert=None
        if level in ("elevated","high") and (upward or cooled):
            pct=round(prob*100); alert={"severity":level,"probability":prob,"title":"High slowdown risk" if level=="high" else "Elevated slowdown risk","message":f"Predictive Machine Monitoring estimates a {pct}% chance of slowdown within five minutes."}; self.last_at=time.monotonic()
        if level in rank: self.last_level=level
        return alert

class Monitor:
    def __init__(self,interval=2):
        self.interval=interval; self.store=Store(); self.model=Model(); self.features=Features(interval); self.alerts=AlertEngine(); self.latest_sample=self.latest_prediction=self.latest_alert=None; self.run_id=""; self.count=0; self.error=None; self.started_at=None; self._stop=threading.Event(); self._thread=None; self._lock=threading.RLock()
    @property
    def running(self): return bool(self._thread and self._thread.is_alive() and not self._stop.is_set())
    def start(self):
        if self.running:return False
        self._stop.clear(); self.run_id=str(uuid.uuid4()); self.count=0; self.error=None; self.started_at=now_utc(); self.features=Features(self.interval); self.alerts=AlertEngine(); self._thread=threading.Thread(target=self._run,daemon=True,name="predictive-machine-monitor"); self._thread.start(); return True
    def stop(self):
        if not self.running:return False
        self._stop.set(); self._thread.join(timeout=6); return True
    def _run(self):
        collector=Collector(); start=time.monotonic(); deadline=start
        while not self._stop.is_set():
            mono=time.monotonic(); missed=mono>deadline+self.interval*.5
            try:
                sample=collector.collect(); sample.update({"timestamp":now_utc(),"run_id":self.run_id,"machine_id":machine_id(),"elapsed_seconds":round(mono-start,3),"missed_deadline":int(missed),"sample_reliable":int(sample.get("cpu_pct") is not None and sample.get("ram_pct") is not None and not missed)})
                row=self.features.add(sample,mono); sample["segment_id"]=self.features.segment_id
                pred={"state":"warming_up","risk_level":"warming","probability":None,"predicted_class":None,"message":"Building temporal context.","model_version":self.model.version} if self.count<2 else self.model.predict(row)
                pred["history_seconds"]=round(mono-self.features.started,1); pred["history_quality"]="full" if pred["history_seconds"]>=60 else "partial"
                alert=self.alerts.evaluate(pred); self.store.save(sample,pred,alert)
                with self._lock: self.latest_sample=safe(sample); self.latest_prediction=safe(pred); self.latest_alert=safe(alert); self.count+=1; self.error=None
            except Exception as e:
                with self._lock:self.error=f"{type(e).__name__}: {e}"
            deadline+=self.interval; self._stop.wait(max(0,deadline-time.monotonic()))
    def status(self): return {"running":self.running,"run_id":self.run_id or None,"started_at":self.started_at,"sample_count":self.count,"interval_seconds":self.interval,"last_error":self.error}
    def live(self): return {"status":self.status(),"sample":self.latest_sample,"prediction":self.latest_prediction,"alert":self.latest_alert,"model":self.model.info()}

def comparison(): return pd.read_csv(REPORT_PATH).to_dict("records") if REPORT_PATH.exists() else []
