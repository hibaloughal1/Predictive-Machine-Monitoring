from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI,HTTPException,Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from dashboard.runtime import Monitor,comparison

STATIC=Path(__file__).parent/"static"; monitor=Monitor()
@asynccontextmanager
async def lifespan(app): monitor.start(); yield; monitor.stop()
app=FastAPI(title="AdoptAI Dashboard",version="2.0",lifespan=lifespan); app.mount("/assets",StaticFiles(directory=STATIC),name="assets")
@app.get("/",include_in_schema=False)
def home(): return FileResponse(STATIC/"index.html")
@app.get("/api/live")
def live(): return monitor.live()
@app.get("/api/health")
def health(): return {"healthy":not monitor.error,"collector":monitor.status(),"model_ready":monitor.model.ready}
@app.post("/api/collector/start")
def start(): return {"changed":monitor.start(),"status":monitor.status()}
@app.post("/api/collector/stop")
def stop(): return {"changed":monitor.stop(),"status":monitor.status()}
@app.get("/api/history")
def history(limit:int=Query(600,ge=10,le=5000)): return {"points":monitor.store.history(limit)}
@app.get("/api/alerts")
def alerts(limit:int=Query(30,ge=1,le=200)): return {"alerts":monitor.store.alerts(limit)}
@app.post("/api/alerts/{alert_id}/acknowledge")
def ack(alert_id:int):
    if not monitor.store.acknowledge(alert_id): raise HTTPException(404,"Alert not found")
    return {"acknowledged":True,"id":alert_id}
@app.get("/api/model")
def model(): return monitor.model.info()
@app.get("/api/model/comparison")
def models(): return {"models":comparison()}
