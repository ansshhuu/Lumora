"""
Week 3 Day 5 manual test — run with:
poetry run python tests/test_week3_manual.py

Runs 5 real questions against the ReAct agent over the indexed `requests`
repo (test_repos/requests / collection "requests_repo") and prints the full
reasoning trace + final answer for each, so results can be eyeballed against
the actual repo source.

Requires Qdrant running with the requests_repo collection populated
(see tests/test_week2_manual.py for how it was built).
"""
import sys
import time

# Windows consoles default to cp1252, which can't render every character the
# model emits (em dashes, etc.) — widen stdout instead of crashing mid-run.
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from dotenv import load_dotenv

load_dotenv()

from lumora.agent.graph import ask

QUESTIONS = [
    # Location question
    "Where is HTTP redirect handling implemented in this codebase?",
    # Dependency question
    "What does the Session class in sessions.py depend on / import?",
    # Explanation question
    "Explain how authentication works in this library.",
    # Enumeration question
    "List all the HTTP method functions exposed in api.py (get, post, etc).",
    # Deliberately hard/ambiguous — not actually in this repo
    "How does this repository implement OAuth2 token refresh?",
]

for i, question in enumerate(QUESTIONS, start=1):
    if i > 1:
        # Space calls out to stay under Groq's free-tier TPM limit — see
        # WEEK3_NOTES.md for the rate-limit behavior observed without this.
        time.sleep(60)

    print(f"\n{'=' * 70}")
    print(f"Q{i}: {question}")
    print("=" * 70)

    answer = ask(question)

    print(f"\n--- FINAL ANSWER (Q{i}) ---")
    print(answer)

print(f"\n{'=' * 70}")
print("Done. Eyeball each answer above against test_repos/requests source.")
print("=" * 70)
