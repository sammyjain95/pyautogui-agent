"""Tests for the safety layer: dry-run, action log, confirmation hook."""

import pytest

from pyautogui_agent.errors import ActionDeclinedError
from pyautogui_agent.safety import (
    Session,
    dry_run,
    get_default_session,
    set_default_session,
)


def test_execute_runs_and_logs():
    session = Session()
    calls = []
    result = session.execute("click_point", {"x": 1, "y": 2},
                             lambda: calls.append("ran") or "ok")
    assert result == "ok"
    assert calls == ["ran"]
    assert len(session.log) == 1
    record = session.log[0]
    assert record.action == "click_point"
    assert record.args == {"x": 1, "y": 2}
    assert record.executed is True
    assert record.declined is False
    assert record.result == "'ok'"


def test_dry_run_does_not_execute():
    session = Session(dry_run=True)
    calls = []
    result = session.execute("click_point", {"x": 1, "y": 2},
                             lambda: calls.append("ran"))
    assert result is None
    assert calls == []
    record = session.log[0]
    assert record.executed is False
    assert "dry run" in record.result


def test_dry_run_mode_context_manager_restores():
    session = Session(dry_run=False)
    with session.dry_run_mode():
        assert session.dry_run is True
    assert session.dry_run is False

    sticky = Session(dry_run=True)
    with sticky.dry_run_mode():
        assert sticky.dry_run is True
    assert sticky.dry_run is True


def test_confirmation_hook_allows():
    seen = []
    session = Session(confirm_hook=lambda record: seen.append(record) or True)
    result = session.execute("type", {"text": "hi"}, lambda: "typed")
    assert result == "typed"
    assert len(seen) == 1
    assert seen[0].action == "type"


def test_confirmation_hook_declines_and_does_not_execute():
    calls = []
    session = Session(confirm_hook=lambda record: False)
    with pytest.raises(ActionDeclinedError) as excinfo:
        session.execute("click_point", {"x": 9, "y": 9},
                        lambda: calls.append("ran"))
    assert calls == []
    assert excinfo.value.action == "click_point"
    record = session.log[0]
    assert record.declined is True
    assert record.executed is False


def test_confirmation_predicate_limits_hook():
    calls = []
    session = Session(
        confirm_hook=lambda record: False,
        confirm_predicate=lambda record: record.action == "click_point")
    # A non-matching action runs without consulting the hook.
    session.execute("type", {"text": "hi"}, lambda: calls.append("typed"))
    assert calls == ["typed"]
    # A matching action is declined.
    with pytest.raises(ActionDeclinedError):
        session.execute("click_point", {"x": 1, "y": 1},
                        lambda: calls.append("clicked"))
    assert calls == ["typed"]


def test_default_session_round_trip():
    original = get_default_session()
    try:
        custom = Session(dry_run=True)
        set_default_session(custom)
        assert get_default_session() is custom
    finally:
        set_default_session(original)


def test_module_level_dry_run_context_manager():
    session = get_default_session()
    previous = session.dry_run
    try:
        with dry_run():
            assert session.dry_run is True
        assert session.dry_run is previous
    finally:
        session.dry_run = previous


def test_format_log_and_last_action():
    session = Session(dry_run=True)
    assert session.last_action() is None
    session.execute("click_point", {"x": 1, "y": 2}, lambda: None)
    assert session.last_action().action == "click_point"
    lines = session.format_log()
    assert len(lines) == 1
    assert "click_point" in lines[0]
    assert "dry run" in lines[0]
    session.clear_log()
    assert session.log == []
