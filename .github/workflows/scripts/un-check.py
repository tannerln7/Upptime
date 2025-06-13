#!/usr/bin/env python3
import os, sys, time, yaml
from datetime import datetime
from nntp import NNTPClient, NNTPError  # from pynntp

# ─── CONFIG ─────────────────────────────────────────────────────
SERVER = os.getenv("UN_SERVER")
PORT   = int(os.getenv("UN_PORT", "563"))
USER   = os.getenv("UN_USERNAME")
PASS   = os.getenv("UN_PASSWORD")
GROUP  = "alt.binaries.pictures"
SLUG   = "unet"                           # must match your .upptimerc.yml slug
OUT    = f"history/{SLUG}.yml"
# ─────────────────────────────────────────────────────────────────

if not all([SERVER, USER, PASS]):
    print("❌ Missing NNTP credentials (UN_SERVER, UN_USERNAME, UN_PASSWORD)")
    sys.exit(1)

# Preserve existing startTime if we were already down
start_time = datetime.utcnow()
try:
    with open(OUT) as f:
        prev = yaml.safe_load(f)
        if prev.get("status") != "up":
            start_time = datetime.fromisoformat(prev["startTime"])
except Exception:
    pass

# Perform the NNTP SSL + login + GROUP query
start_perf = time.perf_counter()
try:
    client = NNTPClient(
        host=SERVER,
        port=PORT,
        user=USER,
        password=PASS,
        use_ssl=True,
    )
    # at this point we’re connected & authenticated
    resp, count, first, last, name = client.group(GROUP)
    status = "up"
    code   = 200
    detail = f"Group {name} has {count} articles"
    client.quit()
except (NNTPError, Exception) as e:
    status = "down"
    code   = 0
    detail = str(e)
finally:
    elapsed = time.perf_counter() - start_perf
    response_time = int(elapsed * 1000)  # in ms

now = datetime.utcnow().isoformat()

# Build the Upptime-compatible history entry
data = {
    "url":           f"nntps://{SERVER}",
    "status":        status,
    "code":          code,
    "responseTime":  response_time,
    "lastUpdated":   now,
    "startTime":     start_time.isoformat(),
    "generator":     "Upptime <https://github.com/upptime/upptime>",
}

os.makedirs("history", exist_ok=True)
with open(OUT, "w") as f:
    yaml.safe_dump(data, f, sort_keys=False)

if status != "up":
    print("❌ check failed:", detail)
    sys.exit(1)

print("✅ Server is up –", detail)
sys.exit(0)