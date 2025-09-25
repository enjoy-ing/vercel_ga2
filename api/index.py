# api/index.py
from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Any
import os, json, math

app = FastAPI()

# --- CORS: allow all origins for POST + preflight
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # allow all origins (safe since we don't use credentials)
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
    allow_credentials=False,  # must be False when allow_origins=["*"]
)

@app.options("/metrics")
async def metrics_options():
    # explicit preflight handler (returns allowed headers via middleware)
    return Response(status_code=204)

class Query(BaseModel):
    regions: List[str]
    threshold_ms: float

DATA_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "latency.json")

def load_data():
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def percentile_95(values):
    if not values:
        return 0.0
    vals = sorted(values)
    n = len(vals)
    k = (n - 1) * 0.95
    f = int(math.floor(k))
    c = int(math.ceil(k))
    if f == c:
        return float(vals[int(k)])
    d = k - f
    return float(vals[f] + (vals[c] - vals[f]) * d)

@app.post("/metrics")
def metrics(query: Query):
    data = load_data()
    resp = {}
    for region in query.regions:
        recs = [r for r in data if r.get("region") == region]
        if not recs:
            resp[region] = {"avg_latency": None, "p95_latency": None, "avg_uptime": None, "breaches": 0}
            continue
        latencies = [float(r.get("latency_ms", 0)) for r in recs]
        uptimes = [float(r.get("uptime_pct", 0)) for r in recs]
        resp[region] = {
            "avg_latency": sum(latencies) / len(latencies),
            "p95_latency": percentile_95(latencies),
            "avg_uptime": sum(uptimes) / len(uptimes),
            "breaches": sum(1 for x in latencies if x > query.threshold_ms),
        }
    return resp
