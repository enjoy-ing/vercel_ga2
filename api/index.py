# api/index.py
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os, json, math
from typing import List, Dict, Any

app = FastAPI()

# Allow POST from any origin
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["POST", "OPTIONS"],
    allow_headers=["*"],
)

DATA_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "latency.json")

class Query(BaseModel):
    regions: List[str]
    threshold_ms: float

def load_data() -> List[Dict[str, Any]]:
    # read bundled JSON file (packaged with the repo)
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def percentile_95(values: List[float]) -> float:
    n = len(values)
    if n == 0:
        return 0.0
    vals = sorted(values)
    # linear interpolation method
    k = (n - 1) * 0.95
    f = math.floor(k)
    c = math.ceil(k)
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
            # return empty metrics for region (or choose to raise error)
            resp[region] = {
                "avg_latency": None,
                "p95_latency": None,
                "avg_uptime": None,
                "breaches": 0
            }
            continue

        latencies = [float(r.get("latency_ms", 0)) for r in recs]
        uptimes = [float(r.get("uptime_pct", 0)) for r in recs]

        avg_latency = sum(latencies) / len(latencies)
        p95 = percentile_95(latencies)
        avg_uptime = sum(uptimes) / len(uptimes)
        breaches = sum(1 for x in latencies if x > query.threshold_ms)

        resp[region] = {
            "avg_latency": avg_latency,
            "p95_latency": p95,
            "avg_uptime": avg_uptime,
            "breaches": breaches
        }
    return resp
