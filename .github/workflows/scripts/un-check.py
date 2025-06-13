#!/usr/bin/env python3
import os, ssl, sys, nntplib, socket, yaml, time
from datetime import datetime

# ── CONFIG ────────────────────────────────────────────────────
SERVER = os.getenv("UN_SERVER")
PORT   = int(os.getenv("UN_PORT"))
USER   = os.getenv("UN_USERNAME")
PASS   = os.getenv("UN_PASSWORD")
GROUP  = "alt.binaries.pictures"
SLUG   = "unet"
OUT    = f"history/{SLUG}.yml"
# ───────────────────────────────────────────────────────────────

if not all([SERVER, USER, PASS]):
    print("❌ Missing NNTP credentials")
    sys.exit(1)

# Load previous startTime if it exists
start_time = datetime.utcnow()
try:
    with open(OUT) as f:
        prev = yaml.safe_load(f)
        if prev.get("status") != "up":
            start_time = datetime.fromisoformat(prev["startTime"])
except Exception:
    pass

# Perform the NNTP SSL + login + group query
start_perf = time.perf_counter()
try:
    ctx = ssl.create_default_context()
    with nntplib.NNTP_SSL(SERVER, PORT, user=USER, password=PASS,
                          ssl_context=ctx, timeout=10) as s:
        resp, count, first, last, name = s.group(GROUP)
    status = "up"
    code   = 200
    detail = f"Group {name} has {count} articles"
except Exception as e:
    status = "down"
    code   = 0
    detail = str(e)
finally:
    elapsed = time.perf_counter() - start_perf
    response_time = int(elapsed * 1000)

now = datetime.utcnow().isoformat()

# Build the exact same structure Upptime expects:
data = {
    "url":           f"nntps://{SERVER}",
    "status":        status,
    "code":          code,
    "responseTime":  response_time,
    "lastUpdated":   now,
    "startTime":     start_time.isoformat(),
    "generator":     "Upptime <https://github.com/upptime/upptime>",
}

# Write history/usenet.yml
os.makedirs("history", exist_ok=True)
with open(OUT, "w") as f:
    yaml.safe_dump(data, f, sort_keys=False)

# Exit non-zero to mark the job failed if “down”
if status != "up":
    print("❌ Usenet check failed:", detail)
    sys.exit(1)
else:
    print("✅ Usenet is up –", detail)
    sys.exit(0)