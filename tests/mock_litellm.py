"""
Mock LiteLLM/OpenAI-compatible server for LOCAL pipeline testing ONLY.
NOT shipped, NOT part of the agent. Stands in for the real Qwen brain + Nemotron synth
so we can prove the reason->act->synthesize loop, /health, concurrency, and the answer
contract all work before deploying to the box (where the real models run).

It mimics:
  POST /v1/chat/completions
    - model == BRAIN_MODEL  -> returns tool_calls (planning) based on simple keyword rules,
      or a final "READY" message once tool results are already in the message history.
    - model == DOMAIN_FT_MODEL -> returns a synthesized answer string from the tool results
      it sees in the conversation (simulating the fine-tuned Nemotron).

Run: uvicorn mock_litellm:app --port 4000
"""
import json
import re
import time

from fastapi import FastAPI, Request

app = FastAPI()

BRAIN = "agent-brain"
DOMAIN = "domain-ft"


def _tool_call(cid, name, args):
    return {
        "id": cid, "type": "function",
        "function": {"name": name, "arguments": json.dumps(args)},
    }


def _plan(question):
    """Very small deterministic 'brain': map a question to the right query_data call(s).
    The REAL Qwen does this with reasoning; here we hard-map the public questions so the
    LOOP and CONTRACT get exercised. Returns a list of tool-call dicts."""
    q = question.lower()
    calls = []
    if "how many cash-rate decisions changed" in q or ("changed the rate" in q and "increases" in q):
        calls.append(_tool_call("c1", "query_data", {"dataset": "rba", "metric": "count_changes"}))
    elif "longest" in q and ("held" in q or "stretch" in q or "unchanged" in q):
        calls.append(_tool_call("c1", "query_data", {"dataset": "rba", "metric": "max_hold_streak"}))
    elif "2011" in q and "2013" in q:
        calls.append(_tool_call("c1", "query_data", {"dataset": "rba", "metric": "period_summary",
                                                     "start_year": 2011, "end_year": 2013}))
    elif "dimensions" in q and "asx" in q:
        calls.append(_tool_call("c1", "query_data", {"dataset": "asx", "metric": "dimensions"}))
    elif "best and worst 2018" in q or ("2018 return" in q):
        calls.append(_tool_call("c1", "query_data", {"dataset": "asx", "metric": "rank_annual_returns",
                                                     "year": 2018, "exclude_tabcorp": True}))
    elif "highest average daily volume" in q:
        calls.append(_tool_call("c1", "query_data", {"dataset": "asx", "metric": "avg_volume",
                                                     "exclude_tabcorp": True}))
    elif "drawdown" in q:
        calls.append(_tool_call("c1", "query_data", {"dataset": "asx", "metric": "max_drawdown",
                                                     "exclude_tabcorp": True, "top": 3}))
    elif "unemployment" in q:
        calls.append(_tool_call("c1", "query_data", {"dataset": "afr", "metric": "peak_year_and_month",
                                                     "pattern": r"\bunemployment\b"}))
    elif "travel stocks" in q or "travel shares" in q:
        # sentiment: fetch article + the rate in force
        calls.append(_tool_call("c1", "afr_get_article", {"headline": "travel stocks vaccine rollout",
                                                          "date": "20210223"}))
        calls.append(_tool_call("c2", "query_data", {"dataset": "rba", "metric": "lookup_rate",
                                                     "date": "2021-02-23"}))
    elif "supported" in q and ("2022" in q or "tightening" in q):
        calls.append(_tool_call("c1", "query_data", {"dataset": "meta", "metric": "coverage"}))
    return calls


def _synthesize(question, tool_msgs):
    """Stand-in for fine-tuned Nemotron: build a concise factual answer from tool results.
    The REAL Nemotron writes nicer prose; this proves the results reach synthesis intact."""
    results = []
    for m in tool_msgs:
        try:
            results.append(json.loads(m))
        except Exception:
            pass
    if not results:
        return "The supplied datasets do not support an answer to this question."
    r = results[-1]
    if isinstance(r, dict) and r.get("error"):
        return "The requested data could not be retrieved from the supplied datasets."
    # a couple of readable specializations
    if "changes" in r and "increases" in r:
        return (f"{r['changes']} of the {r['total_records']} decision records changed the rate: "
                f"{r['increases']} increases and {r['decreases']} decreases.")
    if "worst" in r and isinstance(r["worst"], list):
        parts = [f"{i+1}) {w['ticker']} {w['drawdown_pct']}%, {w['peak_date']} to {w['trough_date']}"
                 for i, w in enumerate(r["worst"])]
        return "; ".join(parts) + "."
    return "Verified result: " + json.dumps(r, default=str)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/v1/chat/completions")
async def chat(request: Request):
    body = await request.json()
    model = body.get("model", "")
    messages = body.get("messages", [])

    if model == BRAIN:
        # If tool results already exist in history, we're done planning -> READY.
        has_tool_results = any(m.get("role") == "tool" for m in messages)
        question = next((m["content"] for m in messages if m.get("role") == "user"), "")
        calls = [] if has_tool_results else _plan(question)
        if calls:
            msg = {"role": "assistant", "content": None, "tool_calls": calls}
        else:
            msg = {"role": "assistant", "content": "READY"}
        return _resp(model, msg, finish="tool_calls" if calls else "stop")

    if model == DOMAIN:
        question = next((m["content"] for m in messages if m.get("role") == "user"), "")
        tool_msgs = [m["content"] for m in messages if m.get("role") == "tool"]
        # domain-ft is called with the digest in the user message here
        answer = _synthesize(question, tool_msgs) if tool_msgs else _from_user_digest(question)
        return _resp(model, {"role": "assistant", "content": answer}, finish="stop")

    return _resp(model, {"role": "assistant", "content": "unknown model"}, finish="stop")


def _from_user_digest(user_content):
    """The agent's _synthesize_llm passes results inside the user message text; parse them out."""
    # find JSON-looking dicts in the digest lines
    blobs = re.findall(r"=>\s*(\{.*\})", user_content)
    results = []
    for b in blobs:
        try:
            results.append(json.loads(b))
        except Exception:
            pass
    if not results:
        return "The supplied datasets do not support an answer to this question."
    r = results[-1]
    if isinstance(r, dict) and r.get("error"):
        return "The requested data could not be retrieved."
    if "changes" in r and "increases" in r:
        return (f"{r['changes']} of the {r['total_records']} decision records changed the rate: "
                f"{r['increases']} increases and {r['decreases']} decreases.")
    if "worst" in r and isinstance(r.get("worst"), list):
        parts = [f"{i+1}) {w['ticker']} {w['drawdown_pct']}%, {w['peak_date']} to {w['trough_date']}"
                 for i, w in enumerate(r["worst"])]
        return "; ".join(parts) + "."
    if "highest" in r and isinstance(r.get("highest"), dict):
        h = r["highest"]
        return f"{h['ticker']} has the highest average daily volume at {h['avg_volume']} shares per trading day."
    if "peak_year" in r:
        return (f"It peaked in {r['peak_year']} with {r['peak_year_count']} matching records. "
                f"{r['peak_month']} is the peak month with {r['peak_month_count']}.")
    if r.get("best") and r.get("worst"):
        return (f"{r['best']['ticker']} was best at {r['best']['return_pct']}%; "
                f"{r['worst']['ticker']} was worst at {r['worst']['return_pct']}%.")
    return "Verified result: " + json.dumps(r, default=str)


def _resp(model, message, finish):
    return {
        "id": "mock-1", "object": "chat.completion", "created": int(time.time()),
        "model": model, "choices": [{"index": 0, "message": message, "finish_reason": finish}],
        "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
    }
