# HANDOFF — Cognitivo Hackathon, Team 8 (Hub24) · Day 3, 31 Jul 2026

> **You are a fresh Claude Code session running ON box 13 (`spark-2b60`, the brain node).**
> This doc is your complete brief. Read it fully before acting. It was written by the
> prior session running on the user's Mac (which drove the box over a flaky Cloudflare
> SSH tunnel — you don't have that problem, you're local).
>
> **⏰ HARD STOP 4:00 PM. Freeze building ~15:00, last hour = demo + write-up.**

---

## GIT — get the code, then ship work (do this FIRST)

This repo is the team's working **and** submission repo. It **must stay PUBLIC** (organizers
clone it at a pinned SHA for the 30% arch/repo score). Its `tools/` already contains the
**proven `query_data` engine** and this handoff.

**Repo URL:** `<TEAM_REPO_URL>`  ← filled in when the Mac session pushes; if still a placeholder,
see "If the repo isn't pushed yet" below.

### 1. Get onto the code
```bash
git clone <TEAM_REPO_URL> ~/team-agent
cd ~/team-agent
git config user.name  "<you>"          # if not already set on the box
git config user.email "<you@…>"
```
(If already cloned: `cd ~/team-agent && git pull`.)

### 2. Confirm the engine works with ON-BOX data (30 seconds)
```bash
# point at the on-box 'data set' dir (see §6 to locate it), then:
export HACKATHON_DATA_DIR="<abs path to 'data set'>"
python3 tools/test_public.py          # MUST print "54 passed, 0 failed"
```
If it's not 54/54, the dataset path/format differs — fix that before building anything on top.

### 3. The work loop — commit + push OFTEN
The box reset once already today and the SSH tunnel is flaky, so **treat every push as your backup.**
```bash
# after ANY change to query_data.py, re-prove it:
python3 tools/test_public.py          # 54/54 or DON'T commit the tool change
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

**Location (on this box, copied here by git):** `hackathon-build/tools/query_data.py`
Pure Python stdlib (no deps). **Verified: reproduces ALL 15 public reference answers EXACTLY
(54/54 checks pass).** Run `python3 hackathon-build/tools/test_public.py` to confirm.

Set `HACKATHON_DATA_DIR` to the on-box dataset path before using (see §6).

Signature: `query_data(dataset, metric, **params)`. Metrics implemented & tested:

| dataset | metrics |
|---|---|
| `rba` | `count`, `count_changes` (→total/changes/increases/decreases), `count_increases`, `count_decreases`, `extremes` (hi/lo rate + first date + record count), `lookup_rate(date=)`, `max_hold_streak`, `period_summary(start_year=,end_year=)` (cuts/hikes/by_year/cumulative/endpoints), `list(year=)` |
| `asx` | `dimensions`, `annual_return(ticker=,year=)`, `full_sample_return(ticker=)`, `rank_annual_returns(year=,exclude_tabcorp=True)`, `rank_full_sample_returns`, `avg_volume(exclude_tabcorp=True)`, `max_drawdown(ticker=` or ranked `top=3)`, `window_return(ticker=,start=,end=)`, `basket_window_return(start=,end=,tickers=?)`, `volatility(ticker=,year=?)`, `correlation(ticker_a=,ticker_b=)`, `quote(ticker=,date=)` |
| `afr` | `count(pattern=)`, `count_by_year`, `count_by_month`, `count_year(pattern=,year=)`, `peak_year_and_month`, `share(pattern=,year=?)`, `find_article(headline=,date=?)` |
Plus `coverage()` for the "is this cross-dataset question supportable?" case (MHQ090).

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

## 5. WHAT'S LEFT TO BUILD (priority order)

1. **[40%] Wrap `query_data` in the agent** — build the FastAPI server in `src/`:
   - `GET /health` → `{"status":"ok"}` (HARD GATE: not 200 = team skipped = zero hidden points).
   - `POST /query` {"question"} → run the Qwen→tools→Nemotron loop → `{"answer",steps?,tool_trace?}`.
   - Qwen (agent-brain) gets a system prompt with the `query_data` tool schema + metric docs + the reproducibility rules, and emits tool calls. Runtime dispatches to `query_data`. Feed results back; when Qwen stops calling tools, hand (question + accumulated results) to Nemotron for synthesis.
   - **Concurrency: ≥3 simultaneous /query, thread-safe, no shared mutable state** (harness uses `--workers 3`).
   - **≤60s/answer** (else −20%; >300s = 0). Aim **≤3 tool calls/question**. Don't `list` big datasets into the model.
   - Every question returns an answer (state the limitation if evidence insufficient; never empty/invented).
2. **[30%] Fine-tune Nemotron-8B** — mostly scripted (§7). Run smoke test → train → eval step-20 → serve on :8001 → flip `DOMAIN_PREDICT_MODE=llm` → produce base-vs-tuned comparison.
3. **[30%] Repo hygiene** — public repo, `submission.json` at root with pinned 40-char SHA, README (arch, run cmd, endpoints, training summary, base-vs-tuned, limitations), `training/` + `logs/` evidence, copy `Participant_Package/` in, **NO secrets**.
4. Wire `mock→llm`, verify one public question end-to-end through the full pipeline.

## 6. BOX / CLUSTER FACTS

- **This box 13 = `spark-2b60` = `10.0.1.10` = BRAIN/agent/head node.** Serves Qwen on `:8000`, runs LiteLLM `:4000`, the agent server, and the eval harness.
- **Box 14 = `10.0.1.11` = FINE-TUNE/model node.** Serves fine-tuned Nemotron on `:8001`. Reachable from box 13 (`ssh 10.0.1.11`, port 22 open).
- **Qwen IS already serving on `:8000`** (`Qwen3.6-35B-A3B-Instruct-FP8`, vLLM, `max_model_len=4096` ⚠️ keep prompts tight). Leave it running.
- **Models on disk:** `~/local-llm-setup/models/{Llama-3.1-Nemotron-Nano-8B-v1, Qwen3.6-35b-A3B-FP8}`.
- **Scaffold:** `~/Cognitivo_Training/finagent-finetune-participant/` (training scripts + data + config).
- **Datasets on box:** NOT yet located in home (guide references `~/Downloads/Jasonl format DataSets/...`). **FIND them:** `find / -iname "AFR_2015*" 2>/dev/null` etc., then `export HACKATHON_DATA_DIR=<the parent 'data set' dir>`. If not on box, the full datasets are in the cloned repo (`AI_Industry_Training_Hackathon/data set/`) — copy them over.
- **LiteLLM config** (`~/litellm/config.yaml`) routes `agent-brain`→`10.0.1.10:8000`, `domain-ft`→`10.0.1.11:8001`.

### ⚠️ Permissions (tested)
- Home is writable, Python 3.12 + pip (user site) work, ports bindable, box 14 reachable. **All agent-building works with no sudo.**
- **`docker` needs a PASSWORD sudo** (`cognitivo_g13` not in docker group). Blocks NeMo training + vLLM serving containers. **FIX: ask staff `sudo usermod -aG docker cognitivo_g13` + re-login**, or run the container scripts at the physical keyboard.

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
2. **`~/team.env` not present on box 13** — need it for LiteLLM key + endpoints. Ask staff to drop it.
3. **docker group** — get `cognitivo_g13` added (see §6) to unblock train/serve headless.

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
- **DONE this session:** SSH working, repo cloned, brief fully parsed, `query_data` built + 54/54 verified, this handoff.
- **NEXT:** find on-box datasets → build `src/` FastAPI agent (Qwen→query_data→Nemotron) → smoke-test fine-tune → serve :8001 → mock→llm → end-to-end on public Qs → repo + submission.json.

---
**First moves on the box (in order):**
1. **GIT section above** — clone the repo, run `tools/test_public.py`, confirm **54/54**.
2. Resolve the **3 open questions in §9** with an organizer (port, team.env, docker group).
3. Locate on-box datasets (§6) and set `HACKATHON_DATA_DIR`.
4. Start the `src/` agent (§5). **Build the agent FIRST — it's the 40% and it gates the fine-tune eval.**

Paths in this doc assume you `git clone`d to `~/team-agent`, so `query_data` lives at
`~/team-agent/tools/query_data.py`. Adjust if you cloned elsewhere.
