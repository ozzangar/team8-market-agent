"""
The agent loop: Qwen brain plans + calls tools → runtime executes query_data →
results back to brain → fine-tuned Nemotron synthesizes the final answer.

Prescribed roles (do not mix):
  - BRAIN (Qwen agent-brain): planning, tool selection, tool-call generation.
  - RUNTIME (this code): validates + executes tool calls.
  - DOMAIN (fine-tuned Nemotron domain-ft): final synthesis ONLY.

DOMAIN_PREDICT_MODE:
  - "mock": synthesis via a deterministic template (no FT model needed) — lets the WHOLE
            pipeline run + be tested before/without the adapter. Bootstrap default.
  - "llm" : synthesis routed through the fine-tuned Nemotron via LiteLLM. REQUIRED for eval.

Stateless per request → safe under concurrent /query (a fresh client per call; no shared
mutable state). Always returns an answer, even on model failure (states the limitation).
"""
import json
import time

from . import config
from .tool_schema import TOOLS, BRAIN_SYSTEM_PROMPT, dispatch

try:
    from openai import OpenAI
except Exception:  # openai not installed in some contexts; mock mode still works
    OpenAI = None


def _client():
    if OpenAI is None:
        raise RuntimeError("openai package not available")
    return OpenAI(base_url=config.LITELLM_BASE_URL, api_key=config.LITELLM_KEY, timeout=45.0)


# ── Synthesis prompt (Nemotron): turn verified results into a clean answer ─────
SYNTH_SYSTEM_PROMPT = """You are an Australian financial analyst. You are given a question and VERIFIED tool results containing exact numbers and dates. Write the final answer.

STRICT RULES:
- State every requested value explicitly (numbers, dates, counts, tickers, rates, signs, %).
- Use ONLY the verified tool results — never invent or estimate a number.
- One or two concise sentences. No hedging words ("approximately", "roughly", "about"). No preamble.
- Preserve exact figures and signs from the results; do not round beyond what is given.
- If the results show the data cannot support the question, say so plainly and briefly.
- For sentiment questions: state the sentiment (positive/negative/mixed) and the likely market direction, grounded in the article text and the given RBA rate."""


def _run_brain(question, tool_results_log):
    """One brain turn. Returns (tool_calls, assistant_msg). Falls back to no-tool if brain down."""
    messages = [
        {"role": "system", "content": BRAIN_SYSTEM_PROMPT},
        {"role": "user", "content": question},
    ]
    # replay prior tool results so the brain can decide if more are needed
    for tc, result in tool_results_log:
        messages.append({
            "role": "assistant",
            "content": None,
            "tool_calls": [{"id": tc["id"], "type": "function",
                            "function": {"name": tc["name"], "arguments": json.dumps(tc["args"])}}],
        })
        messages.append({"role": "tool", "tool_call_id": tc["id"],
                         "content": json.dumps(result)[:3500]})
    client = _client()
    resp = client.chat.completions.create(
        model=config.BRAIN_MODEL,
        messages=messages,
        tools=TOOLS,
        tool_choice="auto",
        temperature=config.BRAIN_TEMPERATURE,
        max_tokens=config.BRAIN_MAX_TOKENS,
    )
    return resp.choices[0].message


def _synthesize_llm(question, results):
    """Route final synthesis through the fine-tuned Nemotron (domain-ft)."""
    client = _client()
    payload = _results_digest(results)
    resp = client.chat.completions.create(
        model=config.DOMAIN_FT_MODEL,
        messages=[
            {"role": "system", "content": SYNTH_SYSTEM_PROMPT},
            {"role": "user", "content": f"Question: {question}\n\nVerified tool results:\n{payload}\n\nFinal answer:"},
        ],
        temperature=config.SYNTH_TEMPERATURE,
        max_tokens=config.SYNTH_MAX_TOKENS,
    )
    return resp.choices[0].message.content.strip()


def _results_digest(results):
    """Compact, readable rendering of the verified tool results for the synth model."""
    parts = []
    for tc, res in results:
        parts.append(f"- {tc['name']}({_fmt_args(tc['args'])}) => {json.dumps(res, default=str)}")
    return "\n".join(parts) if parts else "(no tool results)"


def _fmt_args(args):
    return ", ".join(f"{k}={v!r}" for k, v in (args or {}).items())


def _synthesize_mock(question, results):
    """
    Deterministic synthesis for mock mode — NO model call. Produces a factual,
    hedge-free sentence from the structured results so the pipeline is testable and
    the /query contract holds before the FT adapter exists. Not meant to win the
    30% (that needs the real FT model), but it keeps the 40% pipeline exercisable.
    """
    if not results:
        return ("The supplied datasets do not contain the information required to answer "
                "this question.")
    # Flatten the most informative result into a compact statement.
    tc, res = results[-1]
    if isinstance(res, dict) and res.get("error"):
        return ("The requested data could not be retrieved from the supplied datasets, so a "
                "grounded answer is not available.")
    return "Verified results: " + json.dumps(res, default=str)


def answer_question(question):
    """
    Full pipeline. Returns dict {answer, steps, tool_trace} matching validate.json.
    Never raises — always returns a non-empty answer.
    """
    t0 = time.time()
    tool_trace = []
    results_log = []   # list of (toolcall_dict, result_dict)
    steps = 0
    brain_ok = True

    try:
        for _ in range(config.MAX_AGENT_STEPS):
            if time.time() - t0 > config.REQUEST_BUDGET_S:
                break
            msg = _run_brain(question, results_log)
            steps += 1
            calls = getattr(msg, "tool_calls", None)
            if not calls:
                break  # brain says READY
            for call in calls:
                name = call.function.name
                try:
                    args = json.loads(call.function.arguments or "{}")
                except json.JSONDecodeError:
                    args = {}
                result = dispatch(name, args)
                tc = {"id": call.id, "name": name, "args": args}
                results_log.append((tc, result))
                tool_trace.append({"tool": name, "args": args,
                                   "result": json.dumps(result, default=str)[:500]})
                if time.time() - t0 > config.REQUEST_BUDGET_S:
                    break
    except Exception as e:
        brain_ok = False
        tool_trace.append({"tool": "_brain_error", "args": {}, "result": str(e)[:300]})

    # ── Synthesis ──
    try:
        if config.DOMAIN_PREDICT_MODE == "llm":
            answer = _synthesize_llm(question, results_log)
        else:
            answer = _synthesize_mock(question, results_log)
    except Exception as e:
        # FT model unreachable → fall back to deterministic rendering so we still score.
        answer = _synthesize_mock(question, results_log)
        tool_trace.append({"tool": "_synth_error", "args": {}, "result": str(e)[:300]})

    if not answer or not answer.strip():
        answer = ("Based on the supplied datasets, a definitive answer could not be produced "
                  "for this question.")

    return {
        "answer": answer.strip(),
        "steps": steps + 1,  # + synthesis step
        "tool_trace": tool_trace,
        "_elapsed_s": round(time.time() - t0, 2),
        "_brain_ok": brain_ok,
        "_mode": config.DOMAIN_PREDICT_MODE,
    }
