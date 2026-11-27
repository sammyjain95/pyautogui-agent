"""Safety layer for autonomous GUI use.

Three pieces, all optional and composable:

- Dry-run mode: log the action, do not execute it. Available as a
  ``Session(dry_run=True)`` flag and as a ``dry_run_mode()`` context
  manager that restores the previous setting afterwards.
- Action log: every action is recorded with a timestamp, the action
  name, its arguments, and its result (or that it was a dry run, or
  that it was declined).
- Confirmation hook: a callable the owner supplies, invoked before
  actions matching a predicate (for example destructive ones). If the
  hook returns False, the action is not executed and
  ``ActionDeclinedError`` is raised.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime

from .errors import ActionDeclinedError


@dataclass
class ActionRecord:
    """One entry in a session's action log."""

    timestamp: datetime
    action: str
    args: dict
    result: str | None = None
    executed: bool = False
    declined: bool = False


class Session:
    """Holds the safety configuration for a run of actions.

    Args:
        dry_run: when True, actions are logged but never executed.
        confirm_hook: optional callable taking an ActionRecord and
            returning True to allow the action or False to decline it.
        confirm_predicate: optional callable taking an ActionRecord
            and returning True when the confirmation hook should be
            consulted for that action. When None and a hook is set,
            the hook is consulted for every action.
    """

    def __init__(self, dry_run=False, confirm_hook=None,
                 confirm_predicate=None):
        self.dry_run = dry_run
        self.confirm_hook = confirm_hook
        self.confirm_predicate = confirm_predicate
        self.log = []

    def execute(self, action, args, fn, result_summary=None):
        """Run ``fn`` under this session's safety rules and log it.

        Returns the value ``fn`` returned, or None in dry-run mode.
        Raises ActionDeclinedError when the confirmation hook declines.
        """
        record = ActionRecord(timestamp=datetime.now(), action=action,
                              args=dict(args))
        if self.confirm_hook is not None:
            needs_confirm = (self.confirm_predicate is None
                             or self.confirm_predicate(record))
            if needs_confirm and not self.confirm_hook(record):
                record.declined = True
                record.result = "declined by confirmation hook"
                self.log.append(record)
                raise ActionDeclinedError(action, dict(args))
        if self.dry_run:
            record.result = "dry run: not executed"
            self.log.append(record)
            return None
        value = fn()
        record.executed = True
        if result_summary is not None:
            record.result = result_summary
        else:
            record.result = repr(value)
        self.log.append(record)
        return value

    @contextmanager
    def dry_run_mode(self):
        """Temporarily enable dry-run mode, then restore the setting."""
        previous = self.dry_run
        self.dry_run = True
        try:
            yield self
        finally:
            self.dry_run = previous

    def last_action(self):
        """Return the most recent ActionRecord, or None when empty."""
        return self.log[-1] if self.log else None

    def clear_log(self):
        """Empty the action log."""
        self.log.clear()

    def format_log(self):
        """Return the action log as printable lines."""
        lines = []
        for record in self.log:
            state = ("executed" if record.executed
                     else "declined" if record.declined
                     else "dry run")
            lines.append("%s [%s] %s %s -> %s"
                         % (record.timestamp.isoformat(timespec="seconds"),
                            state, record.action, record.args,
                            record.result))
        return lines


_DEFAULT_SESSION = Session()


def get_default_session():
    """Return the process-wide default session."""
    return _DEFAULT_SESSION


def set_default_session(session):
    """Replace the process-wide default session."""
    global _DEFAULT_SESSION
    _DEFAULT_SESSION = session


@contextmanager
def dry_run():
    """Temporarily enable dry-run mode on the default session."""
    with get_default_session().dry_run_mode():
        yield get_default_session()
