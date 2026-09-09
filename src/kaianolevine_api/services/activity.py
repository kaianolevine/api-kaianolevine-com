"""The running list — what changed, and what broke.

Everything this service does that is worth hearing about arrives in one
Discord channel, in one shape, from one place. Two producers feed it.

**Data changes.** A SQLAlchemy listener tallies every ORM insert, update
and delete that actually committed, and the middleware posts one message
per request summarising them. It is wired to the session rather than to
the routes on purpose: a route added later is covered without anyone
remembering to cover it, which is the only version of this that stays
true. A hand-maintained list of "routes that notify" decays, and its
cheapest failure mode is silence.

**Faults.** The same middleware reports every 5xx and every unhandled
exception, plus any 4xx returned to a machine caller. A human hitting a
guard is the guard working and is not news. A cog getting a 400 or a 403
is a broken contract between two things this ecosystem owns.

What this does not see, stated here rather than left to be discovered:
``session.execute(text(...))``, and anything writing through a connection
this service did not open. ORM-enabled Core ``insert()``, ``update()``
and ``delete()`` are seen, but their row counts are not — the event that
names the table fires before the statement runs — so they are counted as
statements and rendered as such. An exception raised after the response
has started — a lazily streamed body, e.g. ``GET /v1/resume`` pulling the
PDF from Drive — never reaches this middleware either: Starlette re-raises
it after ``dispatch_func`` has already returned, so the middleware takes
its success branch and the caller sees a truncated 200. Sentry's ASGI
integration does catch it; Discord cannot without wrapping every streaming
response body.

The one machine failure this cannot attribute is a credential that does
not verify: the 401 happens before the caller is identified. That case is
covered on the caller's side, not here.

Delivery is fire-and-forget. Nothing is retried and nothing here claims a
success it did not get; ``services.discord`` owns what happens to a
failed delivery. Durable delivery would mean an outbox row written inside
the change's own transaction and a drain to empty it — deferred, and the
thing that changes the decision is wanting to answer "what changed on
Tuesday" from the record rather than from the channel. Nothing derived
from row data reaches the channel. A fault message carries the
exception's type and a Sentry id and nothing else, because a DBAPI
error's string representation contains the statement and its bound
parameters, and this channel is a chat room.
"""

from __future__ import annotations

import asyncio
from collections import Counter
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Any

import sentry_sdk
from fastapi import Request
from mini_app_polis.logger import LOG_WARNING, get_logger, with_log_prefix
from sqlalchemy import event
from sqlalchemy.orm import Session

from ..config import Settings, get_settings
from . import discord

logger = get_logger()

#: Embed colours. Blue for a change, GitHub's red for a fault — the same
#: red the workflow embeds already use, so severity reads the same way
#: whichever producer put the message in the channel.
_CHANGE_COLOR = 0x58A6FF
_FAULT_COLOR = 0xDA3633

CREATED = "created"
UPDATED = "updated"
DELETED = "deleted"
BULK = "bulk"

#: Render order and mark for each operation. Fixed order so two messages
#: about the same table are comparable at a glance.
_MARKS: tuple[tuple[str, str], ...] = (
    (CREATED, "+"),
    (UPDATED, "~"),
    (DELETED, "-"),
    (BULK, "*"),
)

_LEGEND = "+ created · ~ updated · - deleted · * bulk statement (rows not counted)"

#: Discord's code fence, built rather than written literally so this module's
#: own source can be pasted inside one.
_FENCE = "`" * 3


@dataclass
class Recorder:
    """One request's tally of what its transaction actually changed.

    Two buckets, because a flush is not a commit. Work lands in ``pending``
    when the unit of work is flushed and moves to ``committed`` only when
    the transaction commits, so a rolled-back request reports nothing
    rather than reporting what it tried.
    """

    pending: dict[str, Counter] = field(default_factory=dict)
    committed: dict[str, Counter] = field(default_factory=dict)

    def record(self, table: str | None, op: str) -> None:
        """Tally one operation against one table."""
        if not table:
            return
        self.pending.setdefault(table, Counter())[op] += 1

    def promote(self) -> None:
        """Move flushed work into the committed tally."""
        for table, ops in self.pending.items():
            self.committed.setdefault(table, Counter()).update(ops)
        self.pending.clear()

    def discard(self) -> None:
        """Forget flushed work that was rolled back."""
        self.pending.clear()

    def summary(self, suppressed: set[str]) -> str:
        """Render the committed tally, or an empty string if nothing is left.

        An empty string is the signal not to send: a request that changed
        only suppressed tables is indistinguishable from one that changed
        nothing, and neither is worth a message.
        """
        lines: list[str] = []
        for table in sorted(self.committed):
            if table in suppressed:
                continue
            ops = self.committed[table]
            marks = " ".join(f"{mark}{ops[op]}" for op, mark in _MARKS if ops.get(op))
            if marks:
                lines.append(f"`{table}` {marks}")
        return "\n".join(lines)

    def has_bulk(self) -> bool:
        """Whether anything in the tally is a statement rather than a row."""
        return any(ops.get(BULK) for ops in self.committed.values())


#: The request's recorder. Set by the middleware before the downstream app
#: runs, which is what makes it visible to the ORM listeners: Starlette
#: copies the context into the downstream task, and SQLAlchemy's asyncio
#: bridge copies it into the greenlet the listeners run in. Nothing writes
#: this variable below the middleware — the listeners mutate the Recorder
#: object, which is shared, rather than rebinding the variable, which is not.
_recorder: ContextVar[Recorder | None] = ContextVar("activity_recorder", default=None)

#: Live delivery tasks. Held so the event loop does not garbage-collect a
#: send that is still in flight — a fire-and-forget task with no strong
#: reference is a fire-and-maybe.
_in_flight: set[asyncio.Task] = set()


# ---------------------------------------------------------------------------
# Capture
# ---------------------------------------------------------------------------


def _table_of(obj: Any) -> str | None:
    """The table an ORM instance belongs to, or None if it is not mapped."""
    table = getattr(type(obj), "__tablename__", None)
    return str(table) if table else None


@event.listens_for(Session, "after_flush")
def _capture_flush(session: Session, _flush_context: Any) -> None:
    """Tally the unit of work while the session still describes it.

    ``after_flush`` is the one moment where the statements have been
    emitted and ``session.new`` / ``dirty`` / ``deleted`` still hold what
    produced them. By the time the flush completes those collections are
    empty, and ``before_flush`` would tally work that a failing statement
    could still take back.
    """
    recorder = _recorder.get()
    if recorder is None:
        return
    for obj in session.new:
        recorder.record(_table_of(obj), CREATED)
    for obj in session.deleted:
        recorder.record(_table_of(obj), DELETED)
    for obj in session.dirty:
        if session.is_modified(obj, include_collections=False):
            recorder.record(_table_of(obj), UPDATED)


@event.listens_for(Session, "do_orm_execute")
def _capture_bulk(state: Any) -> None:
    """Tally ORM-enabled Core DML, which never passes through a flush.

    ``update(Model).where(...)`` and its siblings write rows without ever
    loading them, so the unit of work never sees them. This event does —
    but it fires before the statement runs, so the row count does not
    exist yet. One statement is counted as one statement, and the message
    says so rather than implying a row count it does not have.
    """
    if not (state.is_insert or state.is_update or state.is_delete):
        return
    recorder = _recorder.get()
    if recorder is None:
        return
    table = getattr(getattr(state.statement, "table", None), "name", None)
    recorder.record(str(table) if table else None, BULK)


@event.listens_for(Session, "after_commit")
def _capture_commit(_session: Session) -> None:
    """Promote flushed work once the transaction is actually durable."""
    recorder = _recorder.get()
    if recorder is not None:
        recorder.promote()


@event.listens_for(Session, "after_soft_rollback")
def _capture_rollback(_session: Session, _previous_transaction: Any) -> None:
    """Drop flushed work the transaction took back."""
    recorder = _recorder.get()
    if recorder is not None:
        recorder.discard()


# ---------------------------------------------------------------------------
# Policy
# ---------------------------------------------------------------------------


def is_notifiable_fault(
    status_code: int, caller_kind: str | None, settings: Settings
) -> bool:
    """Whether this response is a fault worth reporting.

    A 5xx is always this service's problem. A 4xx is the guard working —
    unless the caller is a machine, in which case two things this
    ecosystem owns disagree about the contract between them, and that is
    exactly the failure that otherwise sits undetected for a day.
    """
    if not settings.NOTIFY_FAULTS:
        return False
    if status_code >= 500:
        return True
    if 400 <= status_code < 500:
        return settings.NOTIFY_MACHINE_CLIENT_ERRORS and caller_kind == "machine"
    return False


def _excluded(path: str, settings: Settings) -> bool:
    """Whether this path is outside the feed entirely."""
    return any(
        path == prefix or path.startswith(f"{prefix}/")
        for prefix in settings.NOTIFY_EXCLUDED_PATHS
    )


def _caller(request: Request) -> tuple[str, str | None]:
    """The caller's display name and kind, as far as auth got before answering."""
    name = getattr(request.state, "caller", None)
    kind = getattr(request.state, "caller_kind", None)
    return (str(name) if name else "anonymous"), (str(kind) if kind else None)


# ---------------------------------------------------------------------------
# Delivery
# ---------------------------------------------------------------------------


def _dispatch(coro: Any) -> None:
    """Send without making the caller wait, and without losing the task."""
    try:
        task = asyncio.create_task(coro)
    except RuntimeError:  # no running loop — nothing to send from
        coro.close()
        logger.warning(
            with_log_prefix(LOG_WARNING, "activity notification dropped: no event loop")
        )
        return
    _in_flight.add(task)
    task.add_done_callback(_in_flight.discard)


async def emit_change(
    *,
    settings: Settings,
    method: str,
    path: str,
    actor: str,
    summary: str,
    legend: bool,
) -> None:
    """Post one message summarising what a request committed."""
    footer = f"{method} {path} · {actor} · {settings.ENVIRONMENT}"
    if legend:
        footer = f"{footer}\n{_LEGEND}"
    await discord.send_message(
        settings=settings,
        payload={
            "embeds": [
                {
                    "title": "data changed",
                    "color": _CHANGE_COLOR,
                    "description": summary,
                    "footer": {"text": footer},
                }
            ]
        },
    )


async def emit_fault(
    *,
    settings: Settings,
    method: str,
    path: str,
    actor: str,
    status_code: int,
    detail: str | None,
) -> None:
    """Post one message about a request that failed on this side of the line."""
    description = f"`{method} {path}`"
    if detail:
        description = f"{description}\n{_FENCE}{detail[:1500]}{_FENCE}"
    await discord.send_message(
        settings=settings,
        payload={
            "embeds": [
                {
                    "title": f"fault · {status_code}",
                    "color": _FAULT_COLOR,
                    "description": description,
                    "footer": {"text": f"{actor} · {settings.ENVIRONMENT}"},
                }
            ]
        },
    )


# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------


def _fault_detail(exc: BaseException) -> str:
    """The exception's identity, and deliberately not its message.

    A DBAPI error's ``str()`` carries the failing statement and its bound
    parameters — ``hide_parameters`` defaults to False — so formatting
    the exception into this message put note titles, instructor and
    student names and whole ``notes_json`` payloads into a chat channel.

    The type name is what a person reads to decide whether to go and
    look. The Sentry id is how they find the rest, behind auth. Nothing
    that reaches Discord is derived from row data.
    """
    event_id = sentry_sdk.capture_exception(exc)
    name = type(exc).__name__
    return f"{name} · sentry {event_id}" if event_id else name


async def activity_middleware(request: Request, call_next: Any) -> Any:
    """Open a recorder for the request, and report what it did on the way out.

    Sits outside the routers and outside the exception handlers that turn
    an ``HTTPException`` into a response, so it sees the status that
    actually went on the wire. It sits *inside* Starlette's server-error
    middleware, which is where an unhandled exception is finally turned
    into a 500 — so an unhandled exception reaches here as a raise, not as
    a response, and is caught, reported and re-raised unchanged.

    Committed changes are reported on both paths. A request that wrote
    successfully and then failed rendering its response still changed the
    data, and the channel is a record of what changed.
    """
    settings = get_settings()
    if _excluded(request.url.path, settings):
        return await call_next(request)

    method = request.method
    path = request.url.path
    recorder = Recorder()
    token = _recorder.set(recorder)
    try:
        try:
            response = await call_next(request)
        except Exception as exc:
            actor, _ = _caller(request)
            _report_changes(settings, recorder, method, path, actor)
            if settings.NOTIFY_FAULTS:
                _dispatch(
                    emit_fault(
                        settings=settings,
                        method=method,
                        path=path,
                        actor=actor,
                        status_code=500,
                        detail=_fault_detail(exc),
                    )
                )
            raise

        actor, kind = _caller(request)
        _report_changes(settings, recorder, method, path, actor)
        if is_notifiable_fault(response.status_code, kind, settings):
            _dispatch(
                emit_fault(
                    settings=settings,
                    method=method,
                    path=path,
                    actor=actor,
                    status_code=response.status_code,
                    detail=None,
                )
            )
        return response
    finally:
        _recorder.reset(token)


def _report_changes(
    settings: Settings, recorder: Recorder, method: str, path: str, actor: str
) -> None:
    """Post the change summary, if the request committed anything worth saying."""
    if not settings.NOTIFY_DATA_CHANGES:
        return
    summary = recorder.summary(set(settings.NOTIFY_SUPPRESSED_TABLES))
    if not summary:
        return
    _dispatch(
        emit_change(
            settings=settings,
            method=method,
            path=path,
            actor=actor,
            summary=summary,
            legend=recorder.has_bulk(),
        )
    )
