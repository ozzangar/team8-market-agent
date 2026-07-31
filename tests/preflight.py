#!/usr/bin/env python3
"""
Pre-submission verifier — checks EVERY item on the official Submission Checklist
(Participant_Package/submission-guide.md) mechanically. Read-only; makes no changes.

Run ON THE BOX from the repo root:
    python3 tests/preflight.py                 # checks repo structure + submission.json + live endpoints
    AGENT_URL=http://10.3.0.211:5000 python3 tests/preflight.py   # override endpoint

Exit code 0 only if no FAIL. MANUAL items are printed for a human to confirm.
"""
import json
import os
import re
import subprocess
import sys
import time
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = F = M = 0

def ok(msg):    global P; P += 1; print(f"  \033[32mPASS\033[0m  {msg}")
def bad(msg):   global F; F += 1; print(f"  \033[31mFAIL\033[0m  {msg}")
def manual(msg):global M; M += 1; print(f"  \033[33mMANUAL\033[0m {msg}")
def head(t):    print(f"\n\033[1m{t}\033[0m")

def exists(rel):
    return os.path.exists(os.path.join(ROOT, rel))

# ── 1. Required repository structure ──────────────────────────────────────────
head("1. Required repository structure")
REQUIRED = [
    "README.md", "submission.json", "src", "training", "logs",
    "Participant_Package/answer_template.json",
    "Participant_Package/Challenge_Brief.md",
    "Participant_Package/public_questions.jsonl",
    "Participant_Package/questions_template.json",
    "Participant_Package/Setup_Instructions.md",
    "Participant_Package/submission-guide.md",
    "Participant_Package/submission_template.json",
    "Participant_Package/validate.json",
    "Participant_Package/handout/01_training_guide.md",
    "Participant_Package/handout/02_execution_guide.md",
    "Participant_Package/handout/03_scoring_and_examples.md",
]
for r in REQUIRED:
    (ok if exists(r) else bad)(f"{r} present")

# src/ and training/ should have real content (not just .gitkeep)
for d in ("src", "training", "logs"):
    p = os.path.join(ROOT, d)
    files = [f for f in (os.listdir(p) if os.path.isdir(p) else []) if not f.startswith(".")]
    if d == "logs":
        (ok if files else manual)(f"{d}/ has content ({len(files)} items) — logs optional but recommended")
    else:
        (ok if files else bad)(f"{d}/ has real content ({len(files)} items)")

# ── 2. submission.json validity ───────────────────────────────────────────────
head("2. submission.json")
sj_path = os.path.join(ROOT, "submission.json")
sj = None
if exists("submission.json"):
    try:
        sj = json.load(open(sj_path))
        ok("submission.json is valid JSON")
    except Exception as e:
        bad(f"submission.json not valid JSON: {e}")
if sj:
    for field in ("team_id", "team_name", "github_url", "commit_sha"):
        (ok if sj.get(field) else bad)(f"top-level '{field}' set: {sj.get(field)!r}")
    if " " in str(sj.get("team_id", "")):
        bad("team_id must have NO spaces")
    sha = str(sj.get("commit_sha", ""))
    if re.fullmatch(r"[0-9a-f]{40}", sha):
        ok(f"commit_sha is a 40-char hash")
    else:
        bad(f"commit_sha is NOT a pinned 40-char hash (got {sha!r}) — PIN before submit")
    ag = sj.get("agent", {})
    for f_ in ("endpoint", "health_path", "query_path", "timeout_seconds"):
        (ok if ag.get(f_) is not None else bad)(f"agent.{f_} set: {ag.get(f_)!r}")
    ep = str(ag.get("endpoint", ""))
    if "localhost" in ep or "127.0.0.1" in ep:
        bad(f"agent.endpoint uses localhost — MUST be the box IP ({ep})")
    elif re.search(r"\d+\.\d+\.\d+\.\d+", ep):
        ok(f"agent.endpoint uses an IP ({ep})")
    if ag.get("timeout_seconds") != 300:
        manual(f"agent.timeout_seconds is {ag.get('timeout_seconds')} (guide says 300)")
    mdl = sj.get("model", {})
    (ok if mdl.get("model_name") else bad)(f"model.model_name set: {mdl.get('model_name')!r}")
    (ok if mdl.get("endpoint") else manual)(f"model.endpoint set: {mdl.get('endpoint')!r}")

# ── 3. Live endpoint checks (against the endpoint in submission.json) ──────────
head("3. Live endpoints (health gate + query contract)")
base = os.environ.get("AGENT_URL")
if not base and sj:
    base = str(sj.get("agent", {}).get("endpoint", "")).rstrip("/")
if not base:
    manual("no agent endpoint to test (set AGENT_URL or submission.json)")
else:
    hp = (sj or {}).get("agent", {}).get("health_path", "/health")
    qp = (sj or {}).get("agent", {}).get("query_path", "/query")
    # health
    try:
        r = urllib.request.urlopen(base + hp, timeout=8)
        (ok if r.status == 200 else bad)(f"GET {base}{hp} -> {r.status} (must be 200 — HARD GATE)")
    except Exception as e:
        bad(f"GET {base}{hp} failed: {e} (HARD GATE — team skipped if not 200)")
    # query contract + latency
    try:
        body = json.dumps({"question": "How many cash-rate decisions changed the rate, and how many were increases versus decreases?"}).encode()
        req = urllib.request.Request(base + qp, data=body, headers={"Content-Type": "application/json"})
        t0 = time.time()
        r = urllib.request.urlopen(req, timeout=310)
        dt = time.time() - t0
        d = json.loads(r.read())
        if isinstance(d.get("answer"), str) and d["answer"].strip():
            ok(f"POST {qp} returns non-empty 'answer' ({len(d['answer'])} chars)")
        else:
            bad(f"POST {qp} 'answer' missing/empty — scores zero")
        (ok if dt <= 60 else manual)(f"latency {dt:.1f}s ({'<=60s full credit' if dt<=60 else '>60s = -20% penalty'})")
        print(f"        sample answer: {d.get('answer','')[:120]}")
    except Exception as e:
        bad(f"POST {qp} failed: {e}")

# ── 4. Secret scan (repo is public) ───────────────────────────────────────────
head("4. Secrets / forbidden content (repo is PUBLIC)")
try:
    tracked = subprocess.check_output(["git", "-C", ROOT, "ls-files"], text=True).splitlines()
    leak = 0
    # Real key shapes only: sk- followed by many key-ish chars (not prose like "sk-format").
    pat = re.compile(r"(sk-[a-zA-Z0-9]{16,}|nvapi-[a-zA-Z0-9]{8,}|lsv2_[a-z]{2}_[a-zA-Z0-9]{10,}|password\s*=\s*['\"]?\S{6,}|Cognitivo_g\d+!)")
    ALLOW = {"sk-local-cluster"}
    for fp in tracked:
        full = os.path.join(ROOT, fp)
        if not os.path.isfile(full): continue
        try:
            txt = open(full, encoding="utf-8", errors="ignore").read()
        except Exception:
            continue
        for m_ in pat.finditer(txt):
            if m_.group(0) in ALLOW: continue
            leak += 1
            print(f"        ⚠ {fp}: {m_.group(0)[:30]}")
    (ok if leak == 0 else bad)(f"no committed secrets ({leak} suspicious matches)")
    # team.env / bash_history must NOT be tracked
    for forbidden in ("team.env", ".bash_history"):
        (bad if any(forbidden in t for t in tracked) else ok)(f"{forbidden} not tracked")
    # datasets must not be committed (size)
    big = [t for t in tracked if t.startswith("data set") or "/AFR_" in t or t.endswith(".nemo")]
    (ok if not big else bad)(f"no datasets/model weights committed ({len(big)} found)")
except Exception as e:
    manual(f"secret scan skipped: {e}")

# ── 5. Repo is public + commit is pushed ──────────────────────────────────────
head("5. Public repo + pinned commit reachable")
if sj and sj.get("github_url"):
    manual(f"confirm {sj['github_url']} is PUBLIC and clonable with no credentials")
try:
    local_head = subprocess.check_output(["git", "-C", ROOT, "rev-parse", "HEAD"], text=True).strip()
    if sj and sj.get("commit_sha") == local_head:
        ok(f"submission.json commit_sha == current HEAD ({local_head[:12]})")
    else:
        manual(f"submission.json commit_sha vs HEAD ({local_head[:12]}) — pin to the commit you push LAST")
    # is HEAD pushed?
    subprocess.check_output(["git", "-C", ROOT, "fetch", "origin"], stderr=subprocess.DEVNULL)
    remote = subprocess.check_output(["git", "-C", ROOT, "branch", "-r", "--contains", "HEAD"], text=True).strip()
    (ok if remote else bad)(f"HEAD is pushed to remote ({remote or 'NOT PUSHED'})")
except Exception as e:
    manual(f"git checks skipped: {e}")

# ── 6. Architecture / DOMAIN_PREDICT_MODE (manual-ish) ────────────────────────
head("6. Architecture & fine-tune-in-use (manual confirmation)")
manual("DOMAIN_PREDICT_MODE=llm is set (NOT mock) so the fine-tuned model is actually used")
manual("verify a live /query answer came from the FT Nemotron, not the mock fallback (check tool_trace has no _synth_error)")
manual("README documents architecture (Qwen plan / runtime exec / Nemotron synth) + base-vs-tuned results + run cmd + limitations")
manual("training/ contains: scripts, config/hyperparams, logs, model summary, base-vs-tuned comparison")
manual("PORT: confirmed with organizer whether harness hits the registered port (:5000) vs the ':8001 head-node' note in Setup Instructions")
manual("concurrency: agent safely handles >=3 simultaneous /query (harness default --workers 3)")

# ── Summary ───────────────────────────────────────────────────────────────────
print(f"\n{'='*60}")
print(f"  \033[32m{P} PASS\033[0m   \033[31m{F} FAIL\033[0m   \033[33m{M} MANUAL\033[0m")
print(f"{'='*60}")
if F:
    print("  ❌ Fix all FAILs before submitting.")
else:
    print("  ✅ No automated FAILs. Confirm every MANUAL item by hand.")
sys.exit(1 if F else 0)
