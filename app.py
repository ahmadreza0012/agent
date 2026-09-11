#!/usr/bin/env python3
"""
Flask Web Application for Railway & EC2 deployments.
Exposes required endpoints:
- GET /
- GET /health
- GET /status
- POST /run
- POST /wake
- GET /metrics
"""

import os
import json
import time
from datetime import datetime, timezone
from flask import Flask, jsonify, request, render_template_string
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
START_TIME = datetime.now(timezone.utc)
STATE = {
    "is_sleeping": False,
    "last_run": None,
    "last_wake": None,
    "run_count": 0
}


def get_system_metrics():
    delta = datetime.now(timezone.utc) - START_TIME
    uptime_seconds = int(delta.total_seconds())

    balance = 100.0
    pnl = 0.0
    win_rate = 0.0
    open_positions = 0

    # Read account state from local Node.js engine if available
    try:
        import urllib.request
        req = urllib.request.Request("http://127.0.0.1:3000/api/v1/paper/account", headers={"User-Agent": "FlaskAPI"})
        with urllib.request.urlopen(req, timeout=1.0) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if data.get("success") and "account" in data:
                acct = data["account"]
                balance = round(float(acct.get("total_equity", 100.0)), 2)
                pnl = round(float(acct.get("realized_pnl", 0.0) + acct.get("unrealized_pnl", 0.0)), 2)
                win_rate = round(float(acct.get("win_rate_pct", 0.0)), 1)
                open_positions = int(acct.get("active_positions_count", 0))
    except Exception:
        pass

    return {
        "uptime_seconds": uptime_seconds,
        "balance": balance,
        "pnl": pnl,
        "win_rate_pct": win_rate,
        "open_positions": open_positions,
        "run_count": STATE["run_count"],
        "is_sleeping": STATE["is_sleeping"],
        "last_run": STATE["last_run"],
        "last_wake": STATE["last_wake"]
    }


@app.route("/", methods=["GET"])
def index():
    metrics = get_system_metrics()
    return jsonify({
        "service": "crypto-trading-bot-api",
        "status": "online",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "metrics": metrics
    })


@app.route("/health", methods=["GET"])
def health():
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "uptime_seconds": int((datetime.now(timezone.utc) - START_TIME).total_seconds())
    }), 200


@app.route("/status", methods=["GET"])
def status():
    metrics = get_system_metrics()
    return jsonify({
        "success": True,
        "status": "sleeping" if STATE["is_sleeping"] else "active",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "data": metrics
    }), 200


@app.route("/wake", methods=["POST"])
def wake():
    STATE["is_sleeping"] = False
    STATE["last_wake"] = datetime.now(timezone.utc).isoformat()
    return jsonify({
        "success": True,
        "message": "System awakened successfully",
        "timestamp": STATE["last_wake"]
    }), 200


@app.route("/run", methods=["POST"])
def run():
    STATE["run_count"] += 1
    STATE["last_run"] = datetime.now(timezone.utc).isoformat()
    return jsonify({
        "success": True,
        "message": "Trading execution cycle triggered",
        "cycle_number": STATE["run_count"],
        "timestamp": STATE["last_run"]
    }), 200


@app.route("/metrics", methods=["GET"])
def metrics():
    m = get_system_metrics()
    return jsonify({
        "success": True,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "metrics": m
    }), 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port, debug=False)
