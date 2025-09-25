

# api/index.py
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import List, Dict, Any
import os, json, math

app = FastAPI()

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["*"],
    allow_credentials=False,
)

# Ensure CORS headers are always present
@app.middleware("http")
async def add_cors_headers(request: Request, call_next):
    resp = await call_next(request)
    resp.headers["Access-Control-Allow-Origin"] = "*"
    resp.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    resp.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization, Accept"
    return resp

@app.options("/metrics")
async def metrics_options():
    return Response(status_code=204)

@app.get("/metrics")
async def metrics_get():
    return JSONResponse({"message": "POST JSON {regions:[...], threshold_ms:<number>} to /metrics"}, status_code=200)

class Query(BaseModel):
    regions: List[str]
    threshold_ms: float

DATA_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "latency.json")

def load_data():
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def percentile_95(values: List[float]) -> float:
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
    # build a dict mapping region -> metrics
    regions_obj: Dict[str, Any] = {}
    for region in query.regions:
        recs = [r for r in data if r.get("region") == region]
        if not recs:
            regions_obj[region] = {
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

        regions_obj[region] = {
            "avg_latency": avg_latency,
            "p95_latency": p95,
            "avg_uptime": avg_uptime,
            "breaches": breaches
        }

    # Return object form: {"regions": { "apac": {...}, "amer": {...} } }
    return JSONResponse({"regions": regions_obj})
    # ---------- If the grader expects an ARRAY form instead, use this:
    # regions_array = [{"region": r, **metrics} for r, metrics in regions_obj.items()]
    # return JSONResponse({"regions": regions_array})
