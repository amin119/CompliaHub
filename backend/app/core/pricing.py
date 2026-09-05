"""Phase 7: best-effort Gemini pricing, for the evaluation harness's cost
estimates only — never used for billing/invoicing. Update manually if
pricing changes; same "empirical starting point, not a live-fetched source
of truth" spirit as `agent.py`'s `DEFAULT_MAX_ITERATIONS` or
`retrieval.py`'s `MAX_GRAPH_FACTS`.

Figures are for `gemini-3.1-flash-lite` (this project's one deployed model
across every Gemini call site — classifier/answer/agent/judge all pin the
same model family, see `core/config.py`), USD per 1K tokens.
"""

GEMINI_PRICING_PER_1K_TOKENS = {
    "prompt": 0.0001,
    "completion": 0.0004,
}


def estimate_cost_usd(prompt_tokens: int, completion_tokens: int) -> float:
    pricing = GEMINI_PRICING_PER_1K_TOKENS
    return (prompt_tokens / 1000) * pricing["prompt"] + (completion_tokens / 1000) * pricing[
        "completion"
    ]
