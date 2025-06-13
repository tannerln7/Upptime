#!/usr/bin/env python3
import os
import sys
import time
import yaml
import requests
from datetime import datetime
from nntp import NNTPClient, NNTPError  # from pynntp

# ─── CONFIG ──────────────────────────────────────────────────────────────
SERVER      = os.getenv("UN_SERVER")
PORT        = int(os.getenv("UN_PORT", "563"))
USER        = os.getenv("UN_USERNAME")
PASS        = os.getenv("UN_PASSWORD")
GROUP       = "alt.binaries.pictures"
SLUG        = "unet"                                 # must match your .upptimerc.yml slug
OUT         = f"history/{SLUG}.yml"
VALID_TAG   = "nntp"                                 # our “marker” label
SITE_NAME   = "Usenet Server"
SITE_URL    = f"nntps://{SERVER}"
# GitHub API setup
GITHUB_TOKEN      = os.getenv("GITHUB_TOKEN")
REPO_FULL_NAME    = os.getenv("GITHUB_REPOSITORY")   # e.g. "tannerln7/Upptime"
# ────────────────────────────────────────────────────────────────────────────

if not all([SERVER, USER, PASS, GITHUB_TOKEN, REPO_FULL_NAME]):
    print("❌ Missing one of: UN_SERVER, UN_USERNAME, UN_PASSWORD, GITHUB_TOKEN, or GITHUB_REPOSITORY")
    sys.exit(1)

OWNER, REPO = REPO_FULL_NAME.split("/")
ISSUES_URL  = f"https://api.github.com/repos/{OWNER}/{REPO}/issues"
HEADERS     = {
    "Authorization": f"token {GITHUB_TOKEN}",
    "Accept":        "application/vnd.github.v3+json",
}

# ─── 1) LOAD PREVIOUS startTime (so outages accumulate) ────────────────────
start_time = datetime.utcnow()
try:
    with open(OUT) as f:
        prev = yaml.safe_load(f)
        if prev.get("status") != "up":
            start_time = datetime.fromisoformat(prev["startTime"])
except Exception:
    pass

# ─── 2) PERFORM THE NNTP CHECK & MEASURE RTT ──────────────────────────────
start_perf = time.perf_counter()
try:
    client = NNTPClient(
        host=SERVER,
        port=PORT,
        username=USER,
        password=PASS,
        use_ssl=True,
        timeout=10,
    )
    grp = client.group(GROUP)
    # handle 4- or 5-tuple return
    if len(grp) == 5:
        _, count, _, _, name = grp
    elif len(grp) == 4:
        count, _, _, name = grp
    else:
        raise RuntimeError(f"Unexpected GROUP response: {grp}")
    status, code = "up", 200
    detail       = f"Group {name} has {count} articles"
    client.quit()
except (NNTPError, Exception) as e:
    status, code    = "down", 0
    detail           = str(e)
finally:
    response_time = int((time.perf_counter() - start_perf) * 1000)

now = datetime.utcnow().isoformat()

# ─── 3) WRITE the Upptime-compatible history/<slug>.yml ───────────────────
data = {
    "url":           SITE_URL,
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

# ─── 4) ISSUE HANDLING ───────────────────────────────────────────────────

def list_open_status_issues():
    """All open issues labeled status,<slug>."""
    params = {"state": "open", "labels": f"status,{SLUG}", "per_page": 100}
    r = requests.get(ISSUES_URL, headers=HEADERS, params=params)
    r.raise_for_status()
    return r.json()

def delete_issue_via_graphql(node_id: str):
    q = """
    mutation($id: ID!) {
      deleteIssue(input: {issueId: $id}) {
        clientMutationId
      }
    }
    """
    r = requests.post(
        "https://api.github.com/graphql",
        headers=HEADERS,
        json={"query": q, "variables": {"id": node_id}},
    )
    r.raise_for_status()
    print(f"🗑️ Deleted issue {node_id}")

def close_and_lock_issue(num):
    """Close & lock issue #num."""
    url = f"{ISSUES_URL}/{num}"
    requests.patch(url, headers=HEADERS, json={"state": "closed"}).raise_for_status()
    requests.put(f"{url}/lock", headers=HEADERS, json={"lock_reason":"resolved"}).raise_for_status()

def create_issue(title, body):
    """Open a new NNTP downtime issue."""
    payload = {"title": title, "body": body, "labels": ["status", SLUG, VALID_TAG]}
    r = requests.post(ISSUES_URL, headers=HEADERS, json=payload)
    r.raise_for_status()
    return r.json()

try:
    # 4a) Strip out any default HTTP-check issues by removing the slug label
    all_issues = list_open_status_issues()
    for issue in all_issues:
        labels = [l["name"] for l in issue["labels"]]
        if VALID_TAG not in labels:
            # this is a default Upptime stub → delete it entirely
            node_id = issue["node_id"]
            delete_issue_via_graphql(node_id)

    # 4b) Fetch only our “valid” NNTP issues
    valid_issues = [
        i for i in list_open_status_issues()
        if VALID_TAG in [l["name"] for l in i["labels"]]
    ]

    # 4c) Manage them based on current status
    commit_sha = os.getenv("GITHUB_SHA", "")[:7]

    if status != "up":
        # if down and no valid issue open → create one
        if not valid_issues:
            emoji = "🛑" if status == "down" else "⚠️"
            title = f"{emoji} {SITE_NAME} is {status}"
            body  = (
                f"In [`{commit_sha}`]"
                f"(https://github.com/{OWNER}/{REPO}/commit/{commit_sha}), "
                f"{SITE_NAME} ({SITE_URL}) was **{status}**:\n"
                f"- code: {code}\n"
                f"- responseTime: {response_time} ms\n"
            )
            print("🚨 Creating NNTP downtime issue")
            create_issue(title, body)
        else:
            print("ℹ️  NNTP issue already open")
    else:
        # if up → close & lock any valid issue
        for issue in valid_issues:
            num = issue["number"]
            print(f"✅ Closing NNTP issue #{num}")
            close_and_lock_issue(num)

except Exception as e:
    print("⚠️ Issue handling error:", e)

# ─── 5) EXIT ──────────────────────────────────────────────────────────────
# Always exit 0 so the workflow can commit history/unet.yml & continue.
print(f"✅ Completed NNTP check: {status} – {detail}")
sys.exit(0)