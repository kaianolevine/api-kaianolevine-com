"""Declared machine principals — the source of truth for who the cogs are.

Adding a machine to the fleet is a code change here and nothing else. No
manual seeding, no database access, no script run against production. The
declaration below is reconciled into the principal store on every boot, so a
deploy is what applies it.

Revocation is a code change too: delete the entry, or remove a role from one,
and the next deploy takes the grant away. That is the point of declaring it
rather than seeding it — the grant lives in git, reviewable and reversible,
instead of in whatever state someone left the database in.

Two deliberate limits on what reconciliation touches:

  * Only machines. Human principals are backfilled from wcs_user_profiles and
    granted through the admin UI; a code deploy must never silently re-grant
    or revoke a person's access.

  * Only grants it made itself. Role rows carry ``granted_by``, and
    reconciliation only ever removes rows it wrote (``identity_registry``).
    A role granted by hand for a one-off is left alone rather than being
    quietly reverted by the next unrelated deploy.

Machines are declared by **name**, and the name is the whole identity. Each
holds an API key of its own, kept in deployment configuration, and presenting
that key is what proves the name. Nothing is asserted by the caller and
nothing has to be discovered at runtime, so every declared machine's principal
can exist before it ever makes a request.

Key material is never stored here or in the database. This file says which
machines exist and what they may do; configuration says what proves them.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from identity.apikey import API_KEY_ISSUER, MachineKey
from identity.store import Issuer as IssuerRow
from identity.store import Principal as PrincipalRow
from identity.store import PrincipalRole
from identity.store import Role as RoleRow
from mini_app_polis.logger import LOG_FAILURE, LOG_WARNING, get_logger, with_log_prefix
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

_log = get_logger()

#: Marks role grants this module owns. Reconciliation only removes these.
GRANTED_BY = "identity_registry"

#: Issuer recorded for key-authenticated machines. Humans keep the Clerk
#: issuer; the store is multi-issuer by design so both live in one table.
ISSUER_MACHINES = API_KEY_ISSUER


@dataclass(frozen=True)
class Machine:
    """One declared machine principal, identified by name.

    ``name`` is what the cog calls itself when it registers, and what it is
    called in this file, in logs, and in the audit trail. The Clerk subject is
    discovered at registration and never written here.
    """

    name: str
    roles: tuple[str, ...]
    notes: str = ""

    @property
    def key_env_var(self) -> str:
        """Environment variable holding this machine's key.

        Derived from the name so there is one convention rather than a second
        thing to declare and keep in step: ``deejay-cog`` -> ``DEEJAY_COG_API_KEY``.
        """
        return f"{self.name.upper().replace('-', '_')}_API_KEY"


# ---------------------------------------------------------------------------
# The fleet. Add a machine by adding an entry.
# ---------------------------------------------------------------------------

MACHINES: tuple[Machine, ...] = (
    # Every machine holds "notifier". Its one scope, notify.messages.send,
    # posts a message to a Discord channel and does nothing else — it reads
    # nothing, writes to no table, and grants no one anything. A cog that
    # cannot say "I failed" is a cog whose failures are found later than they
    # need to be, and making that conditional on remembering to add a role
    # here is the kind of friction that ends with the notification never being
    # added. Least privilege is about what a leaked key can do; this one can
    # embarrass the channel.
    Machine(
        name="deejay-cog",
        roles=("catalog-ingest", "notifier"),
        notes="POST /v1/ingest, /v1/live-plays, /v1/spotify/playlists.",
    ),
    Machine(
        name="transcription-cog",
        roles=("wcs-writer", "pipeline-writer", "notifier"),
        notes="POST /v1/wcs/sources, /v1/wcs/transcripts, /v1/evaluations.",
    ),
    Machine(
        name="evaluator-cog",
        roles=("pipeline-writer", "catalog-ingest", "wcs-writer", "notifier"),
        notes="POST /v1/pipeline, /v1/evaluations, /v1/catalog, /v1/wcs/admin/notes.",
    ),
    Machine(
        name="wiki-curator-cog",
        roles=("corpus-reader", "pipeline-writer", "notifier"),
        notes=(
            "GET /v1/wcs/wiki/export (full corpus, unfiltered) and POST "
            "/v1/evaluations. Reads everything, but reading is not admin: no "
            "wcs.grants.write."
        ),
    ),
    # The identity for notifications that belong to no cog — a shell script, a
    # local one-off, a GitHub Action. It exists so those do not have to borrow
    # a cog's key, which would attribute the message to the wrong caller and
    # hand a scratch script that cog's write scopes.
    Machine(
        name="ops-notifier",
        roles=("notifier",),
        notes="POST /v1/notify. Ad-hoc Discord messages from scripts and one-offs.",
    ),
    # watcher-cog polls Drive and calls no API endpoint but its own
    # notifications. It was declared with no roles at all until /v1/notify
    # existed; "notifier" is the first thing it has ever had a use for.
    Machine(
        name="watcher-cog",
        roles=("notifier",),
        notes="Polls Drive. Calls no API endpoint except /v1/notify.",
    ),
)


def machine_keys(env: Mapping[str, str]) -> list[MachineKey]:
    """Read each declared machine's key from configuration.

    A machine whose variable is absent or blank yields no key, so it simply
    cannot authenticate. That is the safe reading of a missing secret: the
    alternative — treating it as an empty key — would match a caller sending
    nothing at all.

    Machines declared with no roles are still given keys. A principal that can
    do nothing is the right state for a caller that asks for nothing, and it
    means the identity exists the moment that changes.
    """
    keys: list[MachineKey] = []
    for machine in MACHINES:
        value = (env.get(machine.key_env_var) or "").strip()
        if value:
            keys.append(MachineKey(name=machine.name, key=value))
        else:
            _log.warning(
                with_log_prefix(
                    LOG_WARNING,
                    f"[identity] {machine.name} has no {machine.key_env_var}; "
                    "it cannot authenticate",
                )
            )
    return keys


def declared(name: str) -> Machine | None:
    """The declared machine with this name, or None if it is not declared.

    Registration consults this: a caller may only claim a name that already
    appears in the file, so registering can never invent a principal the fleet
    did not intend to have.
    """
    for machine in MACHINES:
        if machine.name == name:
            return machine
    return None


async def reconcile(session: AsyncSession) -> dict[str, int]:
    """Make the store match the declaration. Idempotent, runs on every boot.

    With named keys a machine's identity is knowable from this file alone —
    the name *is* the subject — so principals are created here rather than
    discovered when a cog first calls. Every declared machine exists before it
    makes a request, and there is no first-request special case to get wrong.

    Only machines are touched, and only grants this module made itself. A
    role granted by hand for a one-off survives; a person's access is never
    altered by a deploy.

    Never raises into startup: failing to grant is already fail-closed, since
    an ungranted principal is denied by the ordinary authorization path.
    """
    created = granted = revoked = 0
    by_name = {m.name: m for m in MACHINES}

    known_roles = set((await session.execute(select(RoleRow.name))).scalars().all())

    if MACHINES:
        issuer = (
            (
                await session.execute(
                    select(IssuerRow).where(IssuerRow.issuer == ISSUER_MACHINES)
                )
            )
            .scalars()
            .first()
        )
        if issuer is None:
            _log.error(
                with_log_prefix(
                    LOG_FAILURE,
                    f"[identity] issuer {ISSUER_MACHINES!r} is missing; "
                    "run the migration that adds it",
                )
            )
            return {"created": 0, "granted": 0, "revoked": 0}

    for machine in MACHINES:
        missing = set(machine.roles) - known_roles
        if missing:
            # Refuse rather than create: the role vocabulary comes from a
            # migration, and inventing one here would let a typo mint a role
            # that grants nothing and looks correct in the file.
            _log.error(
                with_log_prefix(
                    LOG_FAILURE,
                    f"[identity] {machine.name} declares unknown role(s) "
                    f"{sorted(missing)}; skipping",
                )
            )
            continue

        row = (
            (
                await session.execute(
                    select(PrincipalRow).where(
                        PrincipalRow.issuer == ISSUER_MACHINES,
                        PrincipalRow.subject == machine.name,
                    )
                )
            )
            .scalars()
            .first()
        )

        if row is None:
            row = PrincipalRow(
                kind="machine",
                issuer=ISSUER_MACHINES,
                subject=machine.name,
                display_name=machine.name,
            )
            session.add(row)
            await session.flush()
            created += 1

        current = {
            name: by
            for name, by in (
                await session.execute(
                    select(PrincipalRole.role_name, PrincipalRole.granted_by).where(
                        PrincipalRole.principal_id == row.id
                    )
                )
            ).all()
        }

        for name in set(machine.roles) - set(current):
            session.add(
                PrincipalRole(
                    principal_id=row.id, role_name=name, granted_by=GRANTED_BY
                )
            )
            granted += 1

        for name, granted_by in current.items():
            if name not in machine.roles and granted_by == GRANTED_BY:
                stale = (
                    (
                        await session.execute(
                            select(PrincipalRole).where(
                                PrincipalRole.principal_id == row.id,
                                PrincipalRole.role_name == name,
                            )
                        )
                    )
                    .scalars()
                    .first()
                )
                if stale is not None:
                    await session.delete(stale)
                    revoked += 1

    # A machine removed from the file loses the roles this module gave it. The
    # principal row is left in place so the audit trail still resolves.
    for row in (
        (
            await session.execute(
                select(PrincipalRow).where(
                    PrincipalRow.kind == "machine",
                    PrincipalRow.issuer == ISSUER_MACHINES,
                )
            )
        )
        .scalars()
        .all()
    ):
        if row.subject in by_name:
            continue
        for stale in (
            (
                await session.execute(
                    select(PrincipalRole).where(
                        PrincipalRole.principal_id == row.id,
                        PrincipalRole.granted_by == GRANTED_BY,
                    )
                )
            )
            .scalars()
            .all()
        ):
            await session.delete(stale)
            revoked += 1

    await session.commit()
    return {"created": created, "granted": granted, "revoked": revoked}
