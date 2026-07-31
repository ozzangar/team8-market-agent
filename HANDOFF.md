# HANDOFF — Cognitivo Hackathon, Team 8 (Hub24) · Day 3, 31 Jul 2026

> **You are a fresh Claude Code session running ON the team's GB10 box (currently boxes 07/08
> after a mid-day re-allocation — see §6).** This doc is your complete brief. Read it fully
> before acting. It was written by the prior session on the user's Mac (which drove the box
> over a flaky Cloudflare SSH tunnel — you're local, so no tunnel dependency).
>
> **⏰ HARD STOP 4:00 PM. Freeze building ~15:00, last hour = demo + write-up.**

---

## GIT — get the code, then ship work (do this FIRST)

This repo is the team's working **and** submission repo. It **must stay PUBLIC** (organizers
clone it at a pinned SHA for the 30% arch/repo score). Its `tools/` already contains the
**proven `query_data` engine** and this handoff.

**Repo URL:** `https://github.com/ozzangar/team8-market-agent`  (public — this IS the working
+ submission repo; keep it public and secret-free).
> ⚠️ For the OFFICIAL submission, the repo may need to live under a team/org account rather
> than `ozzangar`. If organizers require that, create it there and push the same contents;
> otherwise this repo is fine. Register the final URL + pinned SHA in `submission.json`.

### 1. Get onto the code
```bash
git clone https://github.com/ozzangar/team8-market-agent ~/team-agent
cd ~/team-agent
git config user.name  "<you>"          # if not already set on the box
git config user.email "<you@…>"
```
(If already cloned: `cd ~/team-agent && git pull`.)

### 2. Confirm the engine works with ON-BOX data (30 seconds)
```bash
# point at the on-box 'data set' dir (see §6 to locate it), then:
export HACKATHON_DATA_DIR="<abs path to 'data set'>"
python3 tests/test_public.py          # MUST print "54 passed, 0 failed"
```
If it's not 54/54, the dataset path/format differs — fix that before building anything on top.

### 3. The work loop — commit + push OFTEN
The box reset once already today and the SSH tunnel is flaky, so **treat every push as your backup.**
```bash
# after ANY change to query_data.py, re-prove it:
python3 tests/test_public.py          # 54/54 or DON'T commit the tool change
git add -A
git commit -m "clear message"
git push
```

### 4. Secret hygiene — the repo is PUBLIC
**NEVER commit:** `team.env`, the LiteLLM key (`sk-…`), `~/.bash_history`, any `nvapi-…` NGC key,
or the cloudflared tunnel token. Confirm `.gitignore` contains at least:
```
team.env
*.env
.env
__pycache__/
*.pyc
data set/          # datasets are large + organizer-supplied — never commit them
models/
checkpoints/
logs/*.log
```
Eyeball `git status` before each push. If a secret ever gets committed, rotate it after the event.

### 5. At submission time
```bash
git rev-parse HEAD                     # the exact 40-char SHA
```
Put that SHA in `submission.json` → `commit_sha` (pinned). The organizers judge THAT commit.

### If the repo isn't pushed yet (placeholder still shows)
The Mac session may not have created the public repo. From the Mac (has `gh` authed as `ozzangar`):
```bash
cd <mac>/aitraining/hackathon-build
git init -b main && git add -A && git commit -m "handoff + proven query_data engine"
gh repo create <team-repo-name> --public --source=. --push
```
Then paste the resulting URL into this file's "Repo URL" line and push again. Until then, the
files can also be moved by `scp` from the Mac, but git is the durable path.

---

## 0. WHO / WHAT / GOAL

- **Event:** Cognitivo × NVIDIA × Anthropic × LangChain hackathon, UNSW Sydney. Team 8, org Hub24.
- **Goal:** WIN. Build & fine-tune an evidence-grounded market-signal agent over RBA / ASX / AFR data.
- **Team:** 2 strong SWEs + non-SWEs (non-SWEs use Claude Code as directors/verifiers).
- **The user is a mobile team lead** — explain with tech analogies when teaching, but here just execute.

## 1. SCORING (drives every priority) — from the official brief

```
final = 0.30 * fine_tuned_model_quality
      + 0.30 * architecture_and_repo_quality
      + 0.40 * hidden_question_accuracy   ← BIGGEST LEVER
```

- **40% hidden accuracy** = component-based, 10 pts/question, partial credit per `expected_fact`, YES/NO by an LLM judge (Qwen). Won by **deterministic tools producing exact numbers** — NOT by the models reasoning. This is where most points live and it's the most controllable.
- **30% fine-tune quality** = measurable delta vs base Nemotron, training-data prep, config, base-vs-tuned comparison, and PROOF the fine-tuned model is actually used at inference.
- **30% arch+repo** = clean role separation, `/health`+`/query` compliance, README, PINNED commit SHA, training artifacts/logs, no secrets.
- Historical reference: integrated pipeline ≈**74%** on 75 questions vs **0%** un-integrated baseline.

## 2. THE PRESCRIBED ARCHITECTURE (not our choice — required)

```
POST /query {"question": "..."}
  → Qwen3.6-35B-A3B-FP8 "agent-brain" plans + emits tool calls   (DO NOT fine-tune Qwen)
  → agent runtime EXECUTES query_data / retrieve                 (deterministic Python)
  → tool results returned to Qwen; loop until Qwen is done       (max ~3 calls; ≤60s!)
  → fine-tuned Nemotron-8B "domain-ft" SYNTHESIZES final answer  (the ONLY model we train)
  → return {"answer": <ONLY scored field>, "steps": int?, "tool_trace": [...]?}
```

- **Qwen = brain**: planning, tool selection, tool-call generation. Owns routing. Don't train it.
- **Runtime = us**: validate + execute the tool calls Qwen requests. This is `src/`.
- **Nemotron-8B = synthesizer ONLY**: reads (question + verified tool results) → concise grounded answer. Learns: read query_data JSON, AU-finance terms, preserve exact numbers/signs/units, include every requested component, state limits. NOT tool routing.
- Route article-grounded **sentiment** questions through Nemotron with the AFR article text + applicable RBA rate; it returns sentiment (positive/negative/mixed) + likely market direction. Do NOT force a made-up numeric forecast.

## 3. ⭐ THE 40% ENGINE IS ALREADY BUILT AND PROVEN — `query_data`

**Location (in the repo):** `src/agent/query_data.py`
Pure Python stdlib (no deps). **Verified: reproduces ALL 15 public reference answers EXACTLY
(54/54 checks pass).** Run `python3 tests/test_public.py` to confirm.

Set `HACKATHON_DATA_DIR` to the on-box dataset path before using (see §6).

Signature: `query_data(dataset, metric, **params)`. Metrics implemented & tested:

| dataset | metrics |
|---|---|
| `rba` | `count`, `count_changes` (→total/changes/increases/decreases), `count_increases`, `count_decreases`, `extremes` (hi/lo rate + first date + record count), `lookup_rate(date=)`, `max_hold_streak`, `period_summary(start_year=,end_year=)` (cuts/hikes/by_year/cumulative/endpoints), `list(year=)` |
| `asx` | `dimensions`, `annual_return(ticker=,year=)`, `full_sample_return(ticker=)`, `rank_annual_returns(year=,exclude_tabcorp=True)`, `rank_full_sample_returns`, `avg_volume(exclude_tabcorp=True)`, `max_drawdown(ticker=` or ranked `top=3)`, `window_return(ticker=,start=,end=)`, `basket_window_return(start=,end=,tickers=?)`, `volatility(ticker=,year=?)`, `correlation(ticker_a=,ticker_b=)`, `quote(ticker=,date=)` |
| `afr` | `count(pattern=)`, `count_by_year`, `count_by_month`, `count_year(pattern=,year=)`, `peak_year_and_month`, `share(pattern=,year=?)`, `find_article(headline=,date=?)` |
Plus `coverage()` for the "is this cross-dataset question supportable?" case (MHQ090).
`find_article` is **paraphrase-robust**: exact-substring fast-path, else keyword-overlap +
finance synonym expansion (stocks↔shares, vaccine↔immunisation…) ranked over HEADLINE(×3)+INTRO,
date-anchored. Verified: finds all 3 public sentiment articles from reworded prompts, even with no date.

### 3.5 THE AGENT IS ALREADY BUILT + TESTED (in `src/`)
The full prescribed pipeline is written and **proven end-to-end locally against a mock Qwen/Nemotron**:
- `src/server.py` — FastAPI `GET /health` (200) + `POST /query`. Concurrency-safe (runs the blocking
  pipeline via `asyncio.to_thread`; verified 3 simultaneous). Always returns non-empty valid JSON.
- `src/agent/agent.py` — the reason→act→synthesize loop. Qwen brain emits tool calls → runtime
  dispatches to `query_data` → results back to brain (loop, capped) → synthesis. `mock` mode uses a
  deterministic synthesizer (no FT model needed); `llm` mode routes synthesis through Nemotron.
  Never raises — FT-down falls back to mock rendering so `/query` always answers.
- `src/agent/tool_schema.py` — OpenAI tool schema + brain system prompt (embeds the reproducibility
  rules) + runtime dispatcher. Accepts reference-agent arg aliases (`date_from`, `exclude_tickers`).
- `src/agent/config.py` — all endpoints/keys/port/mode from env (nothing hard-coded).
- `tests/mock_litellm.py` — stand-in OpenAI server for local testing (NOT shipped/served).
**Proven:** MHQ001/055/049/061 returned exact correct answers through real `POST /query`; `/health`=200;
3 concurrent OK; mock-mode + FT-down both still answer. So on box 7 this is **deploy + wire**, not build.

### 🔴 REPRODUCIBILITY RULES (baked into the tool; a judge scores 0 on the component if broken)
- **EXCLUDE Tabcorp (`TAH.AX`)** from ASX rankings/baskets/extremes/avg-volume unless explicitly asked. Its +2660% return is a flagged artifact; it also has the highest raw volume (would wrongly win MHQ049).
- **ASX return = first-to-last CLOSE, simple** `((last/first)-1)*100`. **Basket = arithmetic mean of the 17 non-Tabcorp constituents' individual returns.**
- **Max drawdown** = min over rows of `(close/running_peak - 1)`; report peak & trough dates. Dates formatted `"20 Mar 2015"` (day not zero-padded).
- **AFR search**: case-insensitive, across **HEADLINE+SUBHEAD+INTRO+TEXT COMBINED**, **once per record**. Whole-word patterns MUST use `\bword\b` anchors (e.g. `\bQBE\b`, `\bunemployment\b`, `\bNAB\b`). Substrings inflate counts.
- **RBA "rate in force on date D"** = Cash rate target of the latest row with Effective Date ≤ D.
- **Tolerances** (per public tolerance_notes): dates/counts/rates/rankings **EXACT**; returns/drawdowns/vol/shares ±0.02pp; correlations ±0.001; closes ±0.0001; avg volume ±1 share.
- **Cross-dataset coverage**: AFR & ASX end **Dec 2021**; RBA runs to **Jun 2026**. If a question needs AFR/ASX past 2021, the correct answer is that it's **unsupported by the evidence** (MHQ090 wants "No" + the coverage-mismatch explanation).

## 4. DATA FORMATS (verified byte-level)

- **RBA** `RBA-rates.csv`: **no BOM**; `RBA-rates.jsonl`: **has BOM** (use `utf-8-sig`). Fields (exact): `Effective Date` (`3 Feb 2010`), `Change % points` (`+0.25`/`-0.25`/`0.00`), `Cash rate target%` (no space before %). 175 rows, 41 non-zero changes, to Jun 2026 (last 12 rows are a forward extension into 2026 — reason about, don't treat as confirmed history).
- **ASX** 18 files `<Name>-ASX-2015-2021.jsonl`, each 1774 rows. Fields: `ticker,date(YYYY-MM-DD),open,high,low,close,volume`. **The `ticker` field inside the file is authoritative** (Qantas→QAN.AX, Rio→RIO.AX, Tabcorp→TAH.AX, Aurizon→AZJ.AX, Cromwell→CMW.AX, Stockland→SGP.AX, Suncorp→SUN.AX, Transurban→TCL.AX; rest are obvious). Full float precision — keep it, round only at output.
- **AFR** 85 monthly files `AFR_YYYYMMDD-YYYYMMDD.jsonl`, ~219,538 articles total. Fields: `HEADLINE, SUBHEAD (can be empty), INTRO, TEXT, NEWSPAPER, PUBLICATIONDATE (YYYYMMDD string)`. Records not necessarily chronological within a file.

## 5. WHAT'S LEFT TO DO (priority order) — the agent is BUILT + TESTED, mostly wiring now

The FastAPI agent is **already written and proven end-to-end locally** (see §3.5). Remaining:

1. **[40%] Deploy + wire the agent on box 7** (code exists in `src/`, don't rebuild):
   - `python3 -m venv .venv && .venv/bin/pip install -r requirements.txt` (query_data itself is stdlib).
   - `export HACKATHON_DATA_DIR="$HOME/projects/AI_Industry_Training_Hackathon/data set"` then `python3 tests/test_public.py` → **must be 54/54** with on-box data.
   - Run in **mock mode now** (brain down): `DOMAIN_PREDICT_MODE=mock (cd src && uvicorn server:app --host 0.0.0.0 --port <PORT>)` → `curl :PORT/health` = 200, `POST /query` returns answers. Proves deploy.
   - When Qwen+LiteLLM are back: `source ~/team.env`, set `DOMAIN_PREDICT_MODE=llm`, point `LITELLM_BASE_URL` at `:4000`, re-test one public Q end-to-end.
   - Contract already handled in code: `/health` 200, `/query` JSON, `steps`/`tool_trace`, ≥3 concurrency (asyncio.to_thread), ≤60s (short loop), always-non-empty answer, mock/FT-down graceful fallback.
   - **⚠️ PORT: §9 landmine unresolved — :8001-on-head vs :5000. Set `AGENT_PORT` accordingly once confirmed; env-driven, no code change.**
2. **[30%] Fine-tune Nemotron-8B on box 8** — scripted (§7). smoke test → train → eval step-20 → serve on `10.0.1.11:8001` → flip `DOMAIN_PREDICT_MODE=llm` → base-vs-tuned comparison. (docker works; need box-8 SSH per §6.4 or a keyboard operator; locate the scaffold per §6.3.)
3. **[30%] Repo hygiene** — this repo IS the submission repo (public). Add `submission.json` at root (pinned 40-char SHA, agent endpoint IP:PORT, model endpoint :8001), flesh out README (arch, run cmd, endpoints, training summary, base-vs-tuned, limitations), copy `Participant_Package/` in, `training/`+`logs/` evidence, **NO secrets**.
4. **Optional insurance (only if time):** a semantic `retrieve` fallback for title-less AFR sentiment Qs. `find_article` already does keyword+synonym+date ranking (handles paraphrase), so this is low priority.

## 6. BOX / CLUSTER FACTS

> ⚠️ **ALLOCATION CHANGED DURING THE DAY.** Team bounced 07→13/14→back to **07/08** (boxes 13/14
> were rebooting every ~15-90 min + console login broke; 07/08 were stable earlier). The facts
> below were re-verified on **box 07 (`aitopatom-2b06`, user `cognitivo_g07`)**. If you're on a
> different box, RE-CHECK the two things that move per-box: **(a) the LiteLLM `agent-brain` IP**
> and **(b) where the datasets + fine-tune scaffold live.** Everything in `src/` reads endpoints
> from env vars, so only config changes — never code.

### ✅ BOX-ROLE DECISION (verified on box 07 via `ip addr` + LiteLLM config + live ports)
- **BOX 7 = AGENT + BRAIN (head node).** Dual-homed: `10.0.1.10` (internal cluster link to box 8) **and** `10.3.0.211`. LiteLLM routes `agent-brain` → `10.3.0.211:8000` = **box 7's own interface**, so Qwen serves here. **Run the FastAPI agent server (`src/server.py`) HERE.** `cognitivo_g07` user.
- **BOX 8 = FINE-TUNE + serve Nemotron (`10.0.1.11:8001`).** `domain-ft` routes here; `:8001` already returned HTTP 200 when probed. **Run the LoRA fine-tune + vLLM serving HERE.** Matches the official execution guide (brain node serves Qwen+agent; model node serves FT Nemotron on :8001).
- This split is the organizers' intended layout, not a guess — the config, the network interfaces, and the guide all agree.

### CONFIRMED FACTS (box 07, this session)
- SSH alias `team-atom` → `ssh-gigabyte07.uiof.ai` / `cognitivo_g07` (in Mac `~/.ssh/config`, passwordless). Box 07 hostname = `aitopatom-2b06`.
- **✅ DATASETS ARE ON BOX 7:** `~/projects/AI_Industry_Training_Hackathon/data set/` (AFR/ASX/RBA all present). → `export HACKATHON_DATA_DIR="$HOME/projects/AI_Industry_Training_Hackathon/data set"`.
- **✅ Nemotron-8B on disk (2 copies):** `~/local-llm-setup/models/Llama-3.1-Nemotron-Nano-8B-v1` and `~/Desktop/Setup_folder/models/Llama-3.1-Nemotron-Nano-8B-v1`.
- **✅ docker WORKS for `cognitivo_g07`** (in the docker group — NO sudo needed). Fine-tune + vLLM serving are UNBLOCKED. (This was the big blocker on box 13; gone here.)
- **✅ Python 3.12**, ports bindable (:5000 free). Repo cloned at `~/team-agent`.
- **LiteLLM config** `~/litellm/config.yaml`: `agent-brain`→`10.3.0.211:8000`, `domain-ft`→`10.0.1.11:8001`.

### 🔴 STILL BLOCKED (organizer / setup actions — a box-7 session can't fix these alone)
1. **Qwen brain + LiteLLM are DOWN** — `:8000` and `:4000` both returned `000` (box rebooted, organizer services didn't restart). **Agent can't run end-to-end until staff restart `agent-brain` + LiteLLM.** Build/test in `mock` mode meanwhile.
2. **`~/team.env` MISSING** on box 7 (LiteLLM key + endpoints). Ask staff to drop it; source before serving.
3. **Fine-tune scaffold** (`~/Cognitivo_Training/finagent-finetune-participant/` — scripts + prepared 48k/6k/6k data) was on box 13, **not confirmed on 07/08**. Locate (`find ~ -maxdepth 3 -type d -iname "*ognitivo_Training*"`) or copy it over before training. Nemotron weights ARE present (above).
4. **Box 8 SSH from box 7** = `Permission denied (publickey)`. To drive box-8 training from a box-7 session: on box 7 run `ssh-copy-id cognitivo_g07@10.0.1.11` (needs box 8 password once), then `ssh 10.0.1.11` works. OR run training at box 8's keyboard.

### ⚠️ Permissions (tested on 13; re-verify on 07/08 — likely same pattern)
- Home writable, Python 3.12 + pip (user site) work, ports bindable, peer node reachable over SSH. **All agent-building works with no sudo.**
- **`docker` needs a PASSWORD sudo** (user not in docker group). Blocks NeMo training + vLLM serving containers. **FIX: ask staff `sudo usermod -aG docker $USER` + re-login**, or run container scripts at the keyboard. (On box 07 the user is `cognitivo_g07`.)

## 7. FINE-TUNE CHEAT-SHEET (scaffold: `~/Cognitivo_Training/finagent-finetune-participant/`)

- Training data ALREADY prepared: `data/{train,val,test}.jsonl` (48k/6k/6k) + `data/smoke/`.
- Scripts: `02_smoke_test.sh` (~30s, ALWAYS first), `03_train_1node.sh` / `07_train_8b_quicktest.sh` (100 steps ~2-3h, run in **tmux**), `04_export_and_serve.sh` (vLLM :8001, LoRA at runtime, NO merge), `05_evaluate.py` / `06_eval_8b.sh` (base vs FT).
- **Baseline config (confirmed +110% vs base, best ckpt = step 20, val loss 0.098):**
  `MODEL_PATH=/models/Llama-3.1-Nemotron-Nano-8B-v1, MAX_STEPS=100, BATCH_SIZE=2, GRAD_ACCUM=4, LORA_RANK=32, LR=5e-5 (NOT 1e-4=loss spike), MAX_SEQ_LEN=512 (>512 OOM), WARMUP=50, NEMO_IMAGE=nvcr.io/nvidia/nemo:25.09 (NOT 25.04=crash), CHECKPOINT_EVERY=20`.
- **EVAL STEP-20 EARLY** — don't wait for 100 steps. One clean proven delta = banked, then stop.
- ⚠️ The scaffold's `lora_finance.yaml` targets **49B** and `agent/*.py` is a **yfinance/Gradio red-herring demo** (uses live web data + hardcoded rates — WRONG, do not reuse for the agent). Point training at the **8B**; build the real agent fresh in `src/` using `query_data`.
- tmux mandatory (earlyoom kills training). Nothing saved before step 20.

## 8. ENV VARS (source `~/team.env` first — org-provided; harness does NOT inject vars)

```
LITELLM_BASE_URL / LITELLM_URL = http://localhost:4000/v1
LITELLM_KEY = sk-local-cluster           # (in team.env; keep out of git)
BRAIN_MODEL = agent-brain
DOMAIN_FT_MODEL = domain-ft
DOMAIN_PREDICT_MODE = mock  →  FLIP TO llm after adapter served (or you submit the STUB!)
QDRANT_URL / QDRANT_COLLECTION = optional AFR retrieval
MAX_AGENT_STEPS = <cap>
```
Agent server launch: `uvicorn <module>:app --host 0.0.0.0 --port <PORT>` (see port landmine §9).

## 9. 🚨 OPEN QUESTIONS — ASK AN ORGANIZER BEFORE OFFICIAL EVAL

1. **PORT CONTRADICTION.** Live Setup Instructions say: *agent HTTP server on **:8001** of the head node, harness connects to **localhost:8001***. But execution guide + `submission_template.json` say agent on **:5000** registered by **IP** (harness "on a different machine"), and **:8001 is the Nemotron vLLM port**. → **ASK: which port does the agent bind on the head node, and does the harness hit localhost or the registered IP?** Wrong = skipped = ZERO hidden points. (Likely: agent :8001 on brain node, Nemotron :8001 on the *other* node — different machines. Confirm.)
2. **`~/team.env` not present on box 7** — need it for LiteLLM key + endpoints. Ask staff to drop it.
3. **Qwen brain + LiteLLM DOWN on box 7** (`:8000`/`:4000` = `000` after reboot) — ask staff to restart the organizer `agent-brain` + LiteLLM services. (docker is NOT a blocker here — `cognitivo_g07` has docker access.)

## 10. SUBMISSION CONTRACT

- Repo **fully PUBLIC** whole event. Structure: `README.md`, `submission.json` (at root), `src/`, `training/`, `logs/`, `Participant_Package/` (copy templates+handouts+`validate.json` in).
- `submission.json`: `team_id`(no spaces), `team_name`, `github_url`, `commit_sha`(exact 40-char PINNED), `agent{endpoint(IP not localhost), health_path:/health, query_path:/query, timeout_seconds:300}`, `model{endpoint :8001/v1, model_name}`.
- Response validated vs `Participant_Package/validate.json`: `answer` required non-empty string; `steps` int≥0 optional; `tool_trace` array optional.
- **NO secrets committed** (team.env, LiteLLM key, and the cloudflared tunnel token that's sitting in `~/.bash_history` — rotate after event).

## 11. SECURITY / HYGIENE (user's standing rules)
- Keep personal/prep OUT of the public repo. Secret-scan before every commit. Commit + push OFTEN (box reset once already today; tunnel flaky).
- Don't run destructive things on the box. The box password is NOT written anywhere (don't ask for it in files).
- NGC key was once exposed in a `ps` line + cloudflared token in bash_history → rotate both after the event.

## 12. STATE / MEMORY
- Full evolving plan is in the Mac session's memory: `day3-hackathon-plan.md` (locked decisions, all brief facts, reproducibility rules, port landmine).
- Official repo cloned at (Mac) `aitraining/AI_Industry_Training_Hackathon/` — the 15 public Qs, templates, `validate.json`, all guides.
- **DONE (Mac session):** SSH working; official repo cloned; brief fully parsed; `query_data` built + **54/54 verified**; `find_article` upgraded to paraphrase-robust; **full FastAPI agent built + proven end-to-end (mock Qwen/Nemotron): /health 200, correct /query answers, 3-concurrent, FT-down fallback**; box roles decided (7=agent, 8=train); repo public + cloned to box 7 `~/team-agent`.
- **NEXT (box 7 session):** venv + deps → 54/54 on-box → run agent in mock mode (deploy proof) → [staff: restart Qwen/LiteLLM + drop team.env] → wire llm mode + end-to-end → [box 8: fine-tune] → submission.json + README.

---
**First moves on the box 7 session (in order):**
1. `cd ~/team-agent && git pull` (get the latest — agent code + this handoff).
2. `python3 -m venv .venv && .venv/bin/pip install -r requirements.txt`.
3. `export HACKATHON_DATA_DIR="$HOME/projects/AI_Industry_Training_Hackathon/data set"` → `.venv/bin/python tests/test_public.py` → confirm **54/54**.
4. **Deploy proof (no brain needed):** `DOMAIN_PREDICT_MODE=mock` → `cd src && ../.venv/bin/uvicorn server:app --host 0.0.0.0 --port <PORT>`; `curl :PORT/health` = 200, `POST /query` returns answers.
5. Ask staff the **§9 items** (port decision, restart Qwen/LiteLLM, `team.env`). In parallel, set up box-8 SSH (§6.4) and start the **fine-tune** (long pole).
6. When brain's back: `source ~/team.env`, `DOMAIN_PREDICT_MODE=llm`, end-to-end on a public Q.

Paths assume the repo is at `~/team-agent` → engine at `~/team-agent/src/agent/query_data.py`,
tests at `~/team-agent/tests/test_public.py`, server at `~/team-agent/src/server.py`.
