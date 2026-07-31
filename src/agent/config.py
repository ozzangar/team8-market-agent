"""
Central config — reads everything from environment (source ~/team.env first).
Never hard-code endpoints/keys (repo is public). Defaults match the Setup Instructions
so the agent runs on the box with team.env sourced, and runs locally for testing.
"""
import os


def _env(name, default=None):
    v = os.environ.get(name)
    return v if v is not None and v != "" else default


# ── LiteLLM gateway (the OpenAI-compatible proxy on the brain node) ────────────
# Both models are reached THROUGH LiteLLM by alias, per the execution guide.
LITELLM_BASE_URL = _env("LITELLM_BASE_URL", _env("LITELLM_URL", "http://localhost:4000/v1"))
LITELLM_KEY      = _env("LITELLM_KEY", "sk-local-cluster")

# ── Model aliases (LiteLLM routes these to the real vLLM endpoints) ────────────
BRAIN_MODEL      = _env("BRAIN_MODEL", "agent-brain")        # Qwen — planning + tool calls
DOMAIN_FT_MODEL  = _env("DOMAIN_FT_MODEL", "domain-ft")      # fine-tuned Nemotron — synthesis
BASE_MODEL       = _env("BASE_MODEL", "domain-base")         # base Nemotron — for A/B comparison only

# mock  = bootstrap default; synthesis is a deterministic template (no FT model needed)
# llm   = REQUIRED before official eval; synthesis routed through fine-tuned Nemotron
DOMAIN_PREDICT_MODE = _env("DOMAIN_PREDICT_MODE", "mock").lower()

# ── Optional AFR retrieval (Qdrant) — only if used ─────────────────────────────
QDRANT_URL        = _env("QDRANT_URL")
QDRANT_COLLECTION = _env("QDRANT_COLLECTION")
EMBED_MODEL       = _env("EMBED_MODEL")

# ── Agent behavior ─────────────────────────────────────────────────────────────
# Keep the loop short: ≤3 tool calls keeps us under the 60s full-credit bar.
MAX_AGENT_STEPS = int(_env("MAX_AGENT_STEPS", "6"))
# Per-request wall-clock budget (soft) — we still always return an answer.
REQUEST_BUDGET_S = float(_env("REQUEST_BUDGET_S", "55"))

# ── Server ─────────────────────────────────────────────────────────────────────
# ⚠️ PORT: Setup Instructions (live) say agent on :8001 of the head node; the
# submission template says :5000. CONFIRM WITH ORGANIZER (HANDOFF §9). Env-driven
# so we flip with one export, no code change.
AGENT_HOST = _env("AGENT_HOST", "0.0.0.0")
AGENT_PORT = int(_env("AGENT_PORT", "5000"))

# ── Data location for query_data ───────────────────────────────────────────────
HACKATHON_DATA_DIR = _env("HACKATHON_DATA_DIR")  # query_data reads this directly too

# Sampling for model calls — low temp for determinism/consistency.
BRAIN_TEMPERATURE  = float(_env("BRAIN_TEMPERATURE", "0.0"))
SYNTH_TEMPERATURE  = float(_env("SYNTH_TEMPERATURE", "0.1"))
BRAIN_MAX_TOKENS   = int(_env("BRAIN_MAX_TOKENS", "1024"))
SYNTH_MAX_TOKENS   = int(_env("SYNTH_MAX_TOKENS", "400"))


def summary():
    """Non-secret snapshot for /health and logs."""
    return {
        "litellm_base_url": LITELLM_BASE_URL,
        "brain_model": BRAIN_MODEL,
        "domain_ft_model": DOMAIN_FT_MODEL,
        "domain_predict_mode": DOMAIN_PREDICT_MODE,
        "max_agent_steps": MAX_AGENT_STEPS,
        "agent_port": AGENT_PORT,
        "data_dir": HACKATHON_DATA_DIR or "(query_data default)",
    }
