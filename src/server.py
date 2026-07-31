"""
FastAPI agent server — the endpoints the evaluation harness calls.

  GET  /health  -> 200 {"status":"ok"}   HARD GATE: not 200 => team skipped, zero hidden pts.
  POST /query   -> {"answer": str, "steps": int, "tool_trace": [...]}  (validate.json)

Concurrency: the harness sends up to 3 simultaneous /query. answer_question() is stateless
(fresh model client per call, no shared mutable state), and we run the blocking work in a
threadpool so concurrent requests don't head-of-line block. Always returns valid JSON with a
non-empty answer, even on internal error (an empty/missing answer scores zero).

Run:  uvicorn server:app --host 0.0.0.0 --port $AGENT_PORT
  (from the src/ dir; or `python -m server`)
"""
import asyncio

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from agent import config
from agent.agent import answer_question

app = FastAPI(title="Team8 Market-Signal Agent")


class Query(BaseModel):
    question: str = ""


@app.get("/health")
def health():
    # Liveness only — must be fast and always 200 when the process is up.
    return {"status": "ok"}


@app.get("/ready")
def ready():
    # Deeper readiness (config snapshot) for our own diagnostics — not the harness gate.
    return {"status": "ok", "config": config.summary()}


@app.post("/query")
async def query(q: Query):
    question = (q.question or "").strip()
    if not question:
        return JSONResponse({"answer": "No question was provided.", "steps": 0, "tool_trace": []})
    try:
        # run the blocking pipeline off the event loop so 3 concurrent calls truly parallelize
        result = await asyncio.to_thread(answer_question, question)
    except Exception as e:
        return JSONResponse({
            "answer": "An internal error prevented a grounded answer for this question.",
            "steps": 0,
            "tool_trace": [{"tool": "_server_error", "args": {}, "result": str(e)[:300]}],
        })
    # Return only the contract fields (drop our private _diagnostics from the wire? keep steps/trace).
    return JSONResponse({
        "answer": result["answer"],
        "steps": result["steps"],
        "tool_trace": result["tool_trace"],
    })


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=config.AGENT_HOST, port=config.AGENT_PORT)
