# Market-Signal Agent — Cognitivo Hackathon (Team 8 / Hub24)

Evidence-grounded financial Q&A agent over **RBA / ASX / AFR** data.

**Architecture (prescribed):** Qwen3.6-35B `agent-brain` plans + emits tool calls →
runtime executes deterministic `query_data` tools → fine-tuned **Nemotron-8B** synthesizes
the final grounded answer → `POST /query`.

## Start here
Read **[`HANDOFF.md`](HANDOFF.md)** — the complete brief: scoring, pipeline, reproducibility
rules, cluster/port facts, fine-tune cheat-sheet, submission contract, and the git workflow.

## The deterministic engine (the 40% hidden-question score)
`tools/query_data.py` — pure-Python-stdlib tool layer. Computes every exact figure the
graded questions require (RBA rate changes/streaks, ASX returns/drawdowns/volatility, AFR
regex counts). Models never do math.

**Verified:** reproduces all 15 public reference answers exactly.
```bash
export HACKATHON_DATA_DIR="<path to the 'data set' dir>"
python3 tools/test_public.py      # → 54 passed, 0 failed
```

## Layout (grows toward the submission structure)
```
HANDOFF.md            # full brief + git workflow — read first
tools/query_data.py   # deterministic metrics engine (proven)
tools/test_public.py  # 54/54 verification vs public reference answers
src/                  # agent server (FastAPI /health + /query) — to build
training/             # fine-tune scripts, config, logs, base-vs-tuned evidence — to add
```
