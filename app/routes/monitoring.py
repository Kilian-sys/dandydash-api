from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required
import urllib.request, json, urllib.parse

monitoring_bp = Blueprint("monitoring", __name__)

PROMETHEUS_URL = "http://192.168.40.10:9090"

def prom_query(query):
    try:
        url = f"{PROMETHEUS_URL}/api/v1/query?query={urllib.parse.quote(query)}"
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=5) as r:
            return json.loads(r.read())
    except Exception as e:
        return {"status": "error", "error": str(e), "data": {"result": []}}

def prom_range(query, start, end, step="60"):
    try:
        params = urllib.parse.urlencode({
            "query": query, "start": start, "end": end, "step": step
        })
        url = f"{PROMETHEUS_URL}/api/v1/query_range?{params}"
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read())
    except Exception as e:
        return {"status": "error", "error": str(e), "data": {"result": []}}


@monitoring_bp.route("/query", methods=["GET"])
@jwt_required()
def query():
    q = request.args.get("q", "up")
    return jsonify(prom_query(q))


@monitoring_bp.route("/range", methods=["GET"])
@jwt_required()
def query_range():
    q     = request.args.get("q", "up")
    start = request.args.get("start", "1h")
    end   = request.args.get("end", "now")
    step  = request.args.get("step", "60")

    import time
    now = int(time.time())
    if start.endswith("h"):
        start_ts = now - int(start[:-1]) * 3600
    elif start.endswith("m"):
        start_ts = now - int(start[:-1]) * 60
    else:
        start_ts = int(start)
    end_ts = now if end == "now" else int(end)

    return jsonify(prom_range(q, start_ts, end_ts, step))


@monitoring_bp.route("/overview", methods=["GET"])
@jwt_required()
def overview():
    """Devuelve un resumen completo de todas las métricas"""
    queries = {
        "cpu":    '100-(avg by(hostname)(rate(node_cpu_seconds_total{mode="idle"}[5m]))*100)',
        "ram":    '(1-(node_memory_MemAvailable_bytes/node_memory_MemTotal_bytes))*100',
        "disk":   '(1-(node_filesystem_avail_bytes{fstype!="tmpfs",mountpoint="/"}/node_filesystem_size_bytes{fstype!="tmpfs",mountpoint="/"}))*100',
        "quotas": 'dandydash_quota_percent',
        "up":     'up'
    }
    result = {}
    for key, q in queries.items():
        result[key] = prom_query(q).get("data", {})
    return jsonify(result)
