# Week 3 Day 5 — Manual Test Results & Notes

Ran `tests/test_week3_manual.py` against the indexed `requests` repo
(`test_repos/requests`, Qdrant collection `requests_repo`, 807 points).
Model: `openai/gpt-oss-120b` via Groq (`ChatGroq`).

## Results

| # | Type | Question | Result | Correctness |
|---|------|----------|--------|-------------|
| 1 | Location | Where is HTTP redirect handling implemented? | ✅ Answered | **Correct.** Identified `SessionRedirectMixin.resolve_redirects` / `get_redirect_target` in `sessions.py` and `Response.is_redirect` in `models.py` — matches actual source exactly. |
| 2 | Dependency | What does the `Session` class depend on/import? | ❌ Failed (413 rate limit) | Not answered — Groq TPM limit hit after `fetch_file` returned the full `sessions.py`. |
| 3 | Explanation | Explain how authentication works. | ⚠️ Hit step cap | Agent was on a reasonable path (fetched `auth.py`, found `prepare_auth`) but exhausted its step budget before producing a final answer; got LangGraph's built-in `"Sorry, need more steps to process this request."` instead of real content. |
| 4 | Enumeration | List all HTTP method functions in `api.py`. | ✅ Answered | **Correct.** Listed `get`, `options`, `head`, `post`, `put`, `patch`, `delete` (+ generic `request`) with accurate signatures — matches `api.py` exactly. |
| 5 | Hard/ambiguous | How does this repo implement OAuth2 token refresh? | ⚠️ Hit step cap | Correctly found nothing relevant after 3 searches (`OAuth2`, `oauth`, `token refresh`) — core `requests` genuinely doesn't implement OAuth2 (that's `requests-oauthlib`, a separate package). No hallucination occurred, but the agent hit the step cap before it could produce our system prompt's intended "I couldn't find X" honesty message — it fell through to the generic LangGraph fallback string instead. |

**Bottom line:** on the two questions that completed normally, both answers were verified correct against the actual `requests` source. On the hard/ambiguous question, the agent never fabricated an OAuth2 implementation that doesn't exist — the *intent* of the honesty instruction held even though the *wording* it produced was LangGraph's generic fallback rather than our custom phrasing.

## Tool-call inefficiency observed (flag for later tuning, not fixed now)

1. **`fetch_file` blows the token budget fast.** Returning a full file's contents (uncapped up to 50KB) into a Groq free-tier request with an 8000 TPM limit is enough on its own to trigger a 413 (`sessions.py` alone pushed a request to ~9000–9950 tokens). Once `search_code` results are also in context, headroom disappears. Options for later: summarize/truncate `fetch_file` output more aggressively when the agent doesn't need the whole file, or have the agent prefer `search_code`/`find_function` (which already return trimmed snippets) over `fetch_file` for exploratory questions.
2. **Redundant tool calls.** Q1 called `search_code({'query': 'redirect'})` twice with the identical query and got the identical result both times — a wasted round trip. Q4 called `search_code({'query': 'def .*('})` twice in a row, also identical and unhelpful (regex-style query doesn't work against semantic search, and the model didn't seem to learn from the first miss). Worth prompting the agent not to repeat an identical tool call, or de-duplicating repeat calls in the tool layer.
3. **The `recursion_limit=10` hard cap is working as designed** (no runaway loops — confirmed), but its interaction with LangGraph's internal step budget is tighter than expected: Q3 hit the cap after only 4 tool calls + partial reasoning, not near what "10" suggests. The generic `"Sorry, need more steps..."` fallback message also bypasses our custom system-prompt honesty wording entirely, since LangGraph short-circuits before the model gets a final turn. For later: consider raising `RECURSION_LIMIT` modestly, or shortening tool-result previews so more reasoning fits in the same step budget, or catching this specific fallback string and rephrasing it to match the intended honest-uncertainty tone.
4. **Groq's free-tier TPM (8000/min) is the dominant bottleneck**, not the agent logic — every failure above traces back to it, either directly (413) or indirectly (had to add 60s spacing between test questions just to get clean runs). Not an agent-code issue, but worth noting since it shapes what "efficient" tool use needs to look like on this model/tier.

## Environment notes (not agent-related, for future reference)

- The `lumora` package wasn't actually installed into the Poetry-managed environment (only `poetry install`'s dependency step had run, not the project install) — running `poetry run python tests/test_week3_manual.py` from a subdirectory failed with `ModuleNotFoundError` until `poetry install` was re-run. Root-relative script paths happened to work before only because the script's own directory coincided with the repo root.
- Qdrant wasn't running (Docker Desktop was stopped); started it manually and mounted the existing `qdrant_storage/` volume to restore the real `requests_repo`/`test_pipeline_repo` collections rather than re-ingesting.
