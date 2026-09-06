"""Unit tests for the agent's streaming loop and trace formatting.

The LLM is never called: agent.stream is patched to yield canned updates, so
these cover the loop, answer extraction and failure handling only.
"""

from unittest.mock import MagicMock, patch

from langgraph.errors import GraphRecursionError

from lumora.agent.graph import (
    MAX_PARSE_RETRIES,
    PREVIEW_CHARS,
    RECURSION_LIMIT,
    _STEP_LIMIT_RESPONSE,
    _is_parse_failure,
    _log_step,
    _preview,
    ask,
    ask_stream,
)

# ask() binds per-request context before streaming; these stand in for the real
# Qdrant collection and cloned-repo path, which the patched agent never touches.
COLLECTION = "test-collection"
REPO_ROOT = "/tmp/test-repo"


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
        assert ask("what is 6*7?", COLLECTION, REPO_ROOT) == "42"


def test_ask_returns_the_last_message_when_several_arrive():
    patcher, _ = stream_yielding(
        {"agent": {"messages": [message(content="thinking")]}},
        {"tools": {"messages": [message(content="tool output", name="search_code")]}},
        {"agent": {"messages": [message(content="final answer")]}},
    )
    with patcher:
        assert ask("q", COLLECTION, REPO_ROOT) == "final answer"


def test_ask_passes_the_question_through_to_the_agent():
    patcher, agent = stream_yielding({"agent": {"messages": [message(content="ok")]}})
    with patcher:
        ask("how does Store work?", COLLECTION, REPO_ROOT)

    payload = agent.stream.call_args.args[0]
    assert payload["messages"][0]["content"] == "how does Store work?"


def test_ask_caps_the_tool_loop_with_a_recursion_limit():
    """A confused agent must not loop indefinitely."""
    patcher, agent = stream_yielding({"agent": {"messages": [message(content="ok")]}})
    with patcher:
        ask("q", COLLECTION, REPO_ROOT)

    assert agent.stream.call_args.kwargs["config"]["recursion_limit"] == RECURSION_LIMIT


def test_ask_returns_a_readable_error_when_the_agent_raises():
    agent = MagicMock()
    agent.stream.side_effect = RuntimeError("groq timeout")

    with patch("lumora.agent.graph.get_agent", return_value=agent):
        result = ask("q", COLLECTION, REPO_ROOT)

    assert result.startswith("Error: agent failed to answer")
    assert "groq timeout" in result


def test_ask_reports_an_empty_stream_rather_than_crashing():
    patcher, _ = stream_yielding()
    with patcher:
        assert ask("q", COLLECTION, REPO_ROOT) == "Error: agent returned no response."


def test_ask_reports_no_response_when_only_tool_updates_arrive():
    patcher, _ = stream_yielding(
        {"tools": {"messages": [message(content="tool only", name="search_code")]}}
    )
    with patcher:
        assert ask("q", COLLECTION, REPO_ROOT) == "Error: agent returned no response."


# --- ask_stream -----------------------------------------------------------------


def test_stream_emits_a_tool_call_event_for_each_call():
    patcher, _ = stream_yielding(
        {"agent": {"messages": [message(tool_calls=[
            {"name": "search_code", "args": {"query": "retry logic"}}
        ])]}},
        {"agent": {"messages": [message(content="done")]}},
    )
    with patcher:
        events = list(ask_stream("q", COLLECTION, REPO_ROOT))

    assert events[0] == {
        "type": "tool_call",
        "name": "search_code",
        # A single-argument tool call is unwrapped to just its value.
        "input": "retry logic",
    }


def test_stream_emits_a_tool_result_event_with_a_preview():
    patcher, _ = stream_yielding(
        {"tools": {"messages": [message(content="class Store:", name="fetch_file")]}},
        {"agent": {"messages": [message(content="done")]}},
    )
    with patcher:
        events = list(ask_stream("q", COLLECTION, REPO_ROOT))

    assert events[0] == {
        "type": "tool_result",
        "name": "fetch_file",
        "preview": "class Store:",
    }


def test_stream_truncates_long_tool_results():
    patcher, _ = stream_yielding(
        {"tools": {"messages": [message(content="x" * 5000, name="fetch_file")]}},
        {"agent": {"messages": [message(content="done")]}},
    )
    with patcher:
        events = list(ask_stream("q", COLLECTION, REPO_ROOT))

    assert events[0]["preview"].endswith("... [truncated]")


def test_stream_ends_with_a_final_answer_event():
    patcher, _ = stream_yielding({"agent": {"messages": [message(content="42")]}})
    with patcher:
        events = list(ask_stream("what is 6*7?", COLLECTION, REPO_ROOT))

    assert events[-1] == {"type": "final_answer", "text": "42", "citation": None}


def test_stream_orders_calls_before_results_before_the_answer():
    patcher, _ = stream_yielding(
        {"agent": {"messages": [message(tool_calls=[
            {"name": "search_code", "args": {"query": "Store"}}
        ])]}},
        {"tools": {"messages": [message(content="hit", name="search_code")]}},
        {"agent": {"messages": [message(content="Store keeps records.")]}},
    )
    with patcher:
        types = [e["type"] for e in ask_stream("q", COLLECTION, REPO_ROOT)]

    assert types == ["tool_call", "tool_result", "final_answer"]


def test_stream_reports_agent_failure_as_a_terminal_answer_event():
    """A crash must still close the stream with a well-formed final event."""
    agent = MagicMock()
    agent.stream.side_effect = RuntimeError("groq timeout")

    with patch("lumora.agent.graph.get_agent", return_value=agent):
        events = list(ask_stream("q", COLLECTION, REPO_ROOT))

    assert events[-1]["type"] == "final_answer"
    assert "groq timeout" in events[-1]["text"]


def test_stream_renders_multi_argument_tool_calls_as_json():
    patcher, _ = stream_yielding(
        {"agent": {"messages": [message(tool_calls=[
            {"name": "fetch_file", "args": {"file_path": "a.py", "max_depth": 2}}
        ])]}},
        {"agent": {"messages": [message(content="done")]}},
    )
    with patcher:
        events = list(ask_stream("q", COLLECTION, REPO_ROOT))

    assert "file_path" in events[0]["input"] and "max_depth" in events[0]["input"]


# --- parse-failure retry ---------------------------------------------------------

# The verbatim Groq 400 body seen in production: the model emitted reasoning
# prose where a structured tool call was required.
PARSE_ERROR = (
    "Error code: 400 - {'error': {'message': \"Parsing failed. The model "
    "generated output that could not be parsed. Please adjust your prompt. "
    "See 'failed_generation' for more details.\", 'type': "
    "'invalid_request_error', 'code': 'output_parse_failed', "
    "'failed_generation': 'The question: \"What CLI arguments does this "
    "project support?\" Let\'s search for other argparse usage.'}}"
)


def stream_failing_then(*updates, error=None):
    """Agent whose first run raises, and whose second yields `updates`."""
    agent = MagicMock()
    calls = {"n": 0}

    def _stream(*_a, **_k):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError(error or PARSE_ERROR)
        return iter(updates)

    agent.stream.side_effect = _stream
    return patch("lumora.agent.graph.get_agent", return_value=agent), agent


def test_parse_failure_is_detected():
    assert _is_parse_failure(RuntimeError(PARSE_ERROR))


def test_unrelated_errors_are_not_treated_as_parse_failures():
    assert not _is_parse_failure(RuntimeError("connection reset by peer"))


def test_a_parse_failure_is_retried_once_and_then_succeeds():
    patcher, agent = stream_failing_then(
        {"agent": {"messages": [message(content="the real answer")]}}
    )
    with patcher:
        events = list(ask_stream("q", COLLECTION, REPO_ROOT))

    assert agent.stream.call_count == 2
    assert events[-1] == {
        "type": "final_answer",
        "text": "the real answer",
        "citation": None,
    }


def test_a_retry_event_precedes_the_second_attempt():
    """The client needs to know to discard steps from the abandoned run."""
    patcher, _ = stream_failing_then(
        {"agent": {"messages": [message(content="ok")]}}
    )
    with patcher:
        events = list(ask_stream("q", COLLECTION, REPO_ROOT))

    retries = [e for e in events if e["type"] == "retry"]
    assert len(retries) == 1
    assert retries[0]["attempt"] == 2
    # It must arrive before the answer, not after it.
    assert events.index(retries[0]) < len(events) - 1


def test_steps_from_the_failed_attempt_are_followed_by_the_retry_marker():
    """A parse failure can land after steps have already streamed."""
    agent = MagicMock()
    calls = {"n": 0}

    def _stream(*_a, **_k):
        calls["n"] += 1
        if calls["n"] == 1:
            def _partial():
                yield {"agent": {"messages": [message(tool_calls=[
                    {"name": "search_code", "args": {"query": "argparse"}}
                ])]}}
                raise RuntimeError(PARSE_ERROR)
            return _partial()
        return iter([{"agent": {"messages": [message(content="done")]}}])

    agent.stream.side_effect = _stream
    with patch("lumora.agent.graph.get_agent", return_value=agent):
        types = [e["type"] for e in ask_stream("q", COLLECTION, REPO_ROOT)]

    assert types == ["tool_call", "retry", "final_answer"]


def test_a_parse_failure_on_both_attempts_surfaces_the_error():
    agent = MagicMock()
    agent.stream.side_effect = RuntimeError(PARSE_ERROR)

    with patch("lumora.agent.graph.get_agent", return_value=agent):
        events = list(ask_stream("q", COLLECTION, REPO_ROOT))

    assert agent.stream.call_count == MAX_PARSE_RETRIES + 1
    assert events[-1]["type"] == "final_answer"
    assert events[-1]["text"].startswith("Error: agent failed to answer")


def test_non_parse_errors_are_not_retried():
    """A network failure gains nothing from an immediate second run."""
    agent = MagicMock()
    agent.stream.side_effect = RuntimeError("connection reset by peer")

    with patch("lumora.agent.graph.get_agent", return_value=agent):
        events = list(ask_stream("q", COLLECTION, REPO_ROOT))

    assert agent.stream.call_count == 1
    assert "connection reset" in events[-1]["text"]


def test_the_step_limit_is_not_retried():
    """Exhausting the tool budget is a real result, not a glitch."""
    agent = MagicMock()
    agent.stream.side_effect = GraphRecursionError("limit")

    with patch("lumora.agent.graph.get_agent", return_value=agent):
        events = list(ask_stream("q", COLLECTION, REPO_ROOT))

    assert agent.stream.call_count == 1
    assert events[-1]["text"] == _STEP_LIMIT_RESPONSE


def test_ask_transparently_benefits_from_the_retry():
    patcher, _ = stream_failing_then(
        {"agent": {"messages": [message(content="recovered")]}}
    )
    with patcher:
        assert ask("q", COLLECTION, REPO_ROOT) == "recovered"
