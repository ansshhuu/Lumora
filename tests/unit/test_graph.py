"""Unit tests for the agent's streaming loop and trace formatting.

The LLM is never called: agent.stream is patched to yield canned updates, so
these cover the loop, answer extraction and failure handling only.
"""

from unittest.mock import MagicMock, patch

from lumora.agent.graph import PREVIEW_CHARS, RECURSION_LIMIT, _log_step, _preview, ask


def message(content="", tool_calls=None, name=None):
    msg = MagicMock()
    msg.content = content
    msg.tool_calls = tool_calls or []
    if name is not None:
        msg.name = name
    return msg


# --- _preview -------------------------------------------------------------------


def test_short_text_is_returned_unchanged():
    assert _preview("hello") == "hello"


def test_long_text_is_truncated_with_a_marker():
    result = _preview("x" * (PREVIEW_CHARS + 50))

    assert result.endswith("... [truncated]")
    assert len(result) == PREVIEW_CHARS + len("... [truncated]")


def test_text_at_the_threshold_is_not_truncated():
    assert _preview("x" * PREVIEW_CHARS) == "x" * PREVIEW_CHARS


def test_non_string_input_is_coerced():
    assert _preview(42) == "42"


# --- _log_step ------------------------------------------------------------------


def test_agent_tool_calls_are_traced(capsys):
    update = {"messages": [message(tool_calls=[{"name": "search_code", "args": {"q": "x"}}])]}

    _log_step("agent", update)

    assert "[tool call] search_code" in capsys.readouterr().out


def test_agent_content_is_traced(capsys):
    _log_step("agent", {"messages": [message(content="thinking out loud")]})

    assert "[agent] thinking out loud" in capsys.readouterr().out


def test_tool_results_are_traced_with_the_tool_name(capsys):
    _log_step("tools", {"messages": [message(content="result body", name="fetch_file")]})

    out = capsys.readouterr().out
    assert "[tool result] fetch_file -> result body" in out


def test_an_update_with_no_messages_prints_nothing(capsys):
    _log_step("agent", {})

    assert capsys.readouterr().out == ""


def test_trace_survives_unencodable_characters(capsys):
    """Windows consoles can raise UnicodeEncodeError; the trace must not crash."""
    _log_step("agent", {"messages": [message(content="emoji \U0001f600 here")]})

    assert "[agent]" in capsys.readouterr().out


# --- ask ------------------------------------------------------------------------


def stream_yielding(*updates):
    """Patch get_agent() so ask() consumes canned stream updates."""
    agent = MagicMock()
    agent.stream.return_value = iter(updates)
    return patch("lumora.agent.graph.get_agent", return_value=agent), agent


def test_ask_returns_the_final_agent_message():
    patcher, _ = stream_yielding({"agent": {"messages": [message(content="42")]}})
    with patcher:
        assert ask("what is 6*7?") == "42"


def test_ask_returns_the_last_message_when_several_arrive():
    patcher, _ = stream_yielding(
        {"agent": {"messages": [message(content="thinking")]}},
        {"tools": {"messages": [message(content="tool output", name="search_code")]}},
        {"agent": {"messages": [message(content="final answer")]}},
    )
    with patcher:
        assert ask("q") == "final answer"


def test_ask_passes_the_question_through_to_the_agent():
    patcher, agent = stream_yielding({"agent": {"messages": [message(content="ok")]}})
    with patcher:
        ask("how does Store work?")

    payload = agent.stream.call_args.args[0]
    assert payload["messages"][0]["content"] == "how does Store work?"


def test_ask_caps_the_tool_loop_with_a_recursion_limit():
    """A confused agent must not loop indefinitely."""
    patcher, agent = stream_yielding({"agent": {"messages": [message(content="ok")]}})
    with patcher:
        ask("q")

    assert agent.stream.call_args.kwargs["config"]["recursion_limit"] == RECURSION_LIMIT


def test_ask_returns_a_readable_error_when_the_agent_raises():
    agent = MagicMock()
    agent.stream.side_effect = RuntimeError("groq timeout")

    with patch("lumora.agent.graph.get_agent", return_value=agent):
        result = ask("q")

    assert result.startswith("Error: agent failed to answer")
    assert "groq timeout" in result


def test_ask_reports_an_empty_stream_rather_than_crashing():
    patcher, _ = stream_yielding()
    with patcher:
        assert ask("q") == "Error: agent returned no response."


def test_ask_reports_no_response_when_only_tool_updates_arrive():
    patcher, _ = stream_yielding(
        {"tools": {"messages": [message(content="tool only", name="search_code")]}}
    )
    with patcher:
        assert ask("q") == "Error: agent returned no response."
