"""
OpenAI tool-calling schema handed to the Qwen brain, plus the runtime dispatcher.

The brain (Qwen) chooses tools + args from these schemas; the RUNTIME (this file)
validates and executes them against query_data. Neither model does math.

Arg-name tolerance: the alpha reference agent used `date_from=` and
`exclude_tickers=["TAH.AX"]`. We accept those aliases AND our canonical names so the
brain cannot phrase itself into a failure.
"""
from . import query_data as qd

# ── System prompt for the brain ────────────────────────────────────────────────
BRAIN_SYSTEM_PROMPT = """You are the planning brain of a financial-data agent for RBA, ASX, and AFR datasets (all 2015-2021 for AFR/ASX; RBA 2010-2026).

Your ONLY job: decide which query_data tool calls answer the question, emit them with exact arguments, read the structured results, and call more tools if needed. You do NOT write the final prose answer and you do NOT do arithmetic yourself — the tools compute exact numbers.

RULES:
- Every dataset-derived number MUST come from a query_data call. Never estimate.
- Exclude Tabcorp (TAH.AX) from ASX rankings/baskets/averages/extremes unless the question explicitly includes it.
- AFR pattern counts: pass a Python regex with word boundaries, e.g. "\\bQBE\\b", "\\bunemployment\\b". Search is across all article fields, once per record — the tool handles that.
- For "rate in force on <date>" use rba lookup_rate with that date.
- Cross-dataset: AFR and ASX end Dec 2021; RBA runs to 2026. If a question needs AFR/ASX data after 2021, the answer is that it is unsupported — call query_data(dataset="meta", metric="coverage") to confirm and stop.
- Be efficient: aim for <=3 tool calls. Do not call "list" on large data.
- When you have all the numbers needed, STOP calling tools and reply with a short plain-text note like "READY" (the synthesis model then writes the final answer)."""

# ── Tool definitions (OpenAI function-calling format) ──────────────────────────
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "query_data",
            "description": (
                "Deterministic query over RBA / ASX / AFR datasets. Returns exact structured "
                "numbers and dates. Pick the dataset and metric that matches the question."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "dataset": {
                        "type": "string",
                        "enum": ["rba", "asx", "afr", "meta"],
                        "description": "rba=cash-rate decisions; asx=18-company OHLCV; afr=news corpus; meta=dataset coverage.",
                    },
                    "metric": {
                        "type": "string",
                        "description": (
                            "RBA: count | count_changes (total/increases/decreases) | extremes "
                            "(highest/lowest rate + first date + record count) | lookup_rate (needs date) "
                            "| max_hold_streak (longest gap between non-zero changes, days+dates+rates) "
                            "| period_summary (needs start_year,end_year -> cuts/hikes/by_year/cumulative/endpoints) | list (needs year). "
                            "ASX: dimensions | annual_return (ticker,year) | full_sample_return (ticker) "
                            "| rank_annual_returns (year) | rank_full_sample_returns | avg_volume "
                            "| max_drawdown (ticker OR ranked worst, top=N) | window_return (ticker,start,end) "
                            "| basket_window_return (start,end) | volatility (ticker[,year]) "
                            "| correlation (ticker_a,ticker_b) | quote (ticker,date). "
                            "AFR: count (pattern) | count_year (pattern,year) | count_by_year (pattern) "
                            "| count_by_month (pattern) | peak_year_and_month (pattern) | share (pattern[,year]). "
                            "META: coverage."
                        ),
                    },
                    "ticker": {"type": "string", "description": "ASX ticker like BHP.AX, QAN.AX, AMP.AX."},
                    "ticker_a": {"type": "string"},
                    "ticker_b": {"type": "string"},
                    "year": {"type": "integer"},
                    "start_year": {"type": "integer"},
                    "end_year": {"type": "integer"},
                    "date": {"type": "string", "description": "YYYY-MM-DD (or '3 Feb 2010')."},
                    "start": {"type": "string", "description": "window start YYYY-MM-DD."},
                    "end": {"type": "string", "description": "window end YYYY-MM-DD."},
                    "pattern": {"type": "string", "description": "AFR regex with word boundaries, e.g. \\bQBE\\b."},
                    "top": {"type": "integer", "description": "for ranked max_drawdown, how many to return."},
                    "exclude_tabcorp": {"type": "boolean", "description": "default true; set false only if the question includes Tabcorp."},
                },
                "required": ["dataset", "metric"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "afr_get_article",
            "description": (
                "Fetch a specific AFR article's text by (partial) headline and optional date "
                "(YYYYMMDD). Use for article-grounded SENTIMENT questions, then the synthesis "
                "model classifies sentiment + likely market direction."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "headline": {"type": "string"},
                    "date": {"type": "string", "description": "PUBLICATIONDATE as YYYYMMDD, optional."},
                },
                "required": ["headline"],
            },
        },
    },
]

# ── Arg normalization: accept reference-agent aliases ──────────────────────────
_TICKER_ALIASES = {  # tolerate full names / no-suffix if the brain slips
    "tabcorp": "TAH.AX", "qantas": "QAN.AX", "rio": "RIO.AX", "transurban": "TCL.AX",
    "aurizon": "AZJ.AX", "cromwell": "CMW.AX", "stockland": "SGP.AX", "suncorp": "SUN.AX",
}


def _norm_ticker(t):
    if not t:
        return t
    low = t.strip().lower().replace(".ax", "")
    if low in _TICKER_ALIASES:
        return _TICKER_ALIASES[low]
    t = t.strip().upper()
    return t if t.endswith(".AX") else t + ".AX"


def _normalize_args(name, args):
    a = dict(args or {})
    # date aliases used by the reference agent
    if "date_from" in a and "date" not in a:
        a["date"] = a.pop("date_from")
    if "date_to" in a and "end" not in a:
        a["end"] = a.pop("date_to")
    # exclude_tickers=["TAH.AX"] -> exclude_tabcorp
    if "exclude_tickers" in a:
        ex = a.pop("exclude_tickers") or []
        if any(str(x).upper().startswith("TAH") for x in ex):
            a.setdefault("exclude_tabcorp", True)
    for k in ("ticker", "ticker_a", "ticker_b"):
        if k in a:
            a[k] = _norm_ticker(a[k])
    return a


def dispatch(name, args):
    """Execute a tool call the brain requested. Returns a JSON-serializable dict."""
    a = _normalize_args(name, args)
    try:
        if name == "query_data":
            ds = a.pop("dataset")
            metric = a.pop("metric")
            if ds == "meta" or metric == "coverage":
                return qd.coverage()
            return qd.query_data(ds, metric, **a)
        if name == "afr_get_article":
            return qd.query_data("afr", "find_article", headline=a.get("headline", ""),
                                 date=a.get("date"))
        return {"error": f"unknown tool '{name}'"}
    except Exception as e:  # never crash the loop; report so the brain can adapt
        return {"error": f"{type(e).__name__}: {e}", "tool": name, "args": a}
