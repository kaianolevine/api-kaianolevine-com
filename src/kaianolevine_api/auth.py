"""Authentication and authorization — a conformant identity enforcement point.

This module used to carry its own Clerk verification: JWKS fetch and cache,
RS256 decode, M2M opaque verification via Clerk BAPI. Its own docstring said
what to do when a second service needed the same logic —

    "If a second service ever needs to verify Clerk tokens, upstream this
     logic ... and convert this module into a thin consumer rather than
     copying it."

A second enforcement point now exists, so that is what happened. Verification
lives in ``identity.clerk``; the decision lives in ``identity.policy``; the
store lives in ``identity.store``. What remains here is what the contract says
should remain in a service: configuration, and thin FastAPI adapters.

``require_scope(...)`` is the only guard: verify, resolve, authorize, emit
audit, once per request. The earlier dependencies it replaced
(``get_current_caller``, ``require_wcs_admin``, ``require_wcs_service``) are
gone — they encoded authority in a boolean column and in the shape of a token,
which is what roles and scopes now express properly.

Three routes are authenticated-only — a verified credential, no scope — and
this is the whole list (ecosystem-standards AUTH-003):

  POST /v1/wcs/me         where a person first becomes known. It cannot
                          require a principal in order to grant one.
  GET  /v1/wcs/me         reads only the caller's own profile, via
                          ``get_current_owner``, which survives for these
                          two and nowhere else.
  GET  /v1/identity/whoami  reports what verify and resolve saw about the
                          caller and authorizes nothing. Requiring a scope
                          to discover your own identity would make it
                          useless for the case it exists to serve: a caller
                          that has no principal yet.

Any route added to that list needs a reason of the same shape — requiring a
scope would be circular — and needs adding here.
"""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from functools import lru_cache

import httpx
from fastapi import Depends, Header, Request
from identity.apikey import ApiKeyVerifier
from identity.chain import ChainVerifier
from identity.clerk import ClerkIssuer, ClerkVerifier
from identity.errors import CredentialInvalid, IdentityError, IssuerNotTrusted
from identity.policy import authorize as decide
from identity.store import (
    Issuer,
    PrincipalRole,
    SqlAlchemyAuditSink,
    SqlAlchemyPrincipalStore,
    new_audit_event,
)
from identity.store import Principal as PrincipalRow
from identity.types import Principal, VerifiedSubject
from mini_app_polis.logger import (
    LOG_START,
    LOG_WARNING,
    get_logger,
    with_log_prefix,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from . import identity_registry as registry
from .config import Settings, get_settings
from .database import get_db_session
from .schemas import api_error

logger = get_logger()

ENFORCEMENT_POINT = "api-kaianolevine-com"


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


def _issuers_from_settings(settings: Settings) -> list[ClerkIssuer]:
    """Trusted Clerk issuers.

    Multi-issuer via ``CLERK_ISSUERS`` (a JSON array of
    ``{issuer, jwks_url}``); the singular ``CLERK_ISSUER`` /
    ``CLERK_JWKS_URL`` vars remain the one-tenant shorthand this service
    deploys with.

    No secret key: machines hold their own API keys and never authenticate
    through Clerk, so the only thing needed from an issuer is its JWKS.
    """
    raw = getattr(settings, "CLERK_ISSUERS", None)
    if raw:
        entries = json.loads(raw) if isinstance(raw, str) else raw
        return [
            ClerkIssuer(
                issuer=e["issuer"],
                jwks_url=e["jwks_url"],
            )
            for e in entries
        ]
    if settings.CLERK_ISSUER and settings.CLERK_JWKS_URL:
        return [
            ClerkIssuer(
                issuer=settings.CLERK_ISSUER,
                jwks_url=settings.CLERK_JWKS_URL,
            )
        ]
    return []


def build_verifier(settings: Settings, env: Mapping[str, str]) -> ChainVerifier:
    """Assemble the verifier for both populations.

    Machines authenticate with named keys read from configuration; humans with
    Clerk sessions. Routing between them is structural, so machine traffic
    never produces a failed Clerk verification and never leaves the process.
    """
    issuers = _issuers_from_settings(settings)
    return ChainVerifier(
        ApiKeyVerifier(registry.machine_keys(env)),
        ClerkVerifier(issuers) if issuers else None,
    )


@lru_cache(maxsize=1)
def _cached_verifier(cache_key: str) -> ChainVerifier:
    """Cached across requests: the Clerk JWKS cache lives inside it."""
    del cache_key
    return build_verifier(get_settings(), os.environ)


def get_verifier(settings: Settings | None = None) -> ChainVerifier:
    """Return the process verifier, rebuilt when configuration changes."""
    settings = settings or get_settings()
    issuers = _issuers_from_settings(settings)
    # Keyed on configuration identity only. Enumerating machine keys here
    # would re-read the environment — and re-log its warnings — on every
    # request; the declaration and the environment both change only on deploy.
    key = json.dumps(
        {
            "issuers": [[i.issuer, i.jwks_url] for i in issuers],
            "machines": [m.name for m in registry.MACHINES],
        },
        sort_keys=True,
    )
    return _cached_verifier(key)


# ---------------------------------------------------------------------------
# Step 1 — verify
# ---------------------------------------------------------------------------


async def verify_bearer(
    authorization: str | None, settings: Settings
) -> VerifiedSubject:
    """Verify the Authorization header. Raises 401 on any credential failure.

    A transport failure reaching the issuer is not a credential failure and
    raises 503 instead. Verification is offline against cached JWKS, so the
    only request that touches the network is a cold start or the first one
    after the cache TTL expires — but when that request is the one that fails,
    the credential is unjudged rather than bad.

    Header parity with the fleet's client (ecosystem-standards AUTH-002):
    ``KaianoApiClient`` in common-python-utils (``mini_app_polis.api.client``)
    sends ``Authorization: Bearer <key>`` and nothing else — no custom header,
    no token exchange, no issuer on the request path. This function is the
    other half of that agreement, and the scheme comparison below is
    lower-cased so a client that sends ``bearer`` is not rejected on spelling.
    A change to the header on either side is a breaking change to both, so it
    belongs in common-python-utils and here in the same release.

    The failure reason is deliberately not returned to the caller — they are
    unauthenticated by definition at this point. It is logged, and where a
    scope is in play it is recorded on the audit event.
    """
    if authorization:
        scheme, _, token = authorization.partition(" ")
        if scheme.lower() == "bearer" and token:
            try:
                return await get_verifier(settings).verify(token)
            except IssuerNotTrusted as exc:
                logger.warning(with_log_prefix(LOG_WARNING, f"untrusted issuer: {exc}"))
            except (CredentialInvalid, IdentityError) as exc:
                logger.warning(
                    with_log_prefix(LOG_WARNING, f"credential rejected: {exc!r}")
                )
            except httpx.HTTPError as exc:
                # The issuer was unreachable, so the credential was never
                # judged. 401 would say it was judged and found bad, and a
                # client that believes that clears the session and bounces the
                # user to login — turning a blip that self-heals on the next
                # request into a logout. 503 says the same thing this service
                # already says when a dependency it needs is not there.
                logger.warning(
                    with_log_prefix(
                        LOG_WARNING, f"identity provider unreachable: {exc!r}"
                    )
                )
                raise api_error(
                    503,
                    "auth_unavailable",
                    "Identity provider unreachable; retry shortly",
                ) from exc

    raise api_error(401, "unauthorized", "Valid Bearer token required")


# ---------------------------------------------------------------------------
# Issuer-asserted identity attributes
# ---------------------------------------------------------------------------

_EMAIL_CLAIMS = ("email", "primary_email_address", "email_address")
_NAME_CLAIMS = ("name", "full_name")


def identity_from_claims(subject: VerifiedSubject) -> tuple[str, str]:
    """Return ``(email, display_name)`` as the issuer asserted them.

    A request body is not a source of identity. A caller holding a valid
    session token can put any address in one, so a profile built from the body
    records what the caller typed rather than who they are. These claims are
    signed by the issuer, so preferring them makes the profile say what Clerk
    says.

    Both come back ``""`` when the session token does not carry them — Clerk's
    default session token is deliberately minimal and needs a JWT template to
    include ``email``. Callers should treat an empty result as "not asserted"
    and fall back to whatever they have, which is what keeps this safe to ship
    before that template exists and makes it authoritative the moment it does.

    This reads claims only. It never calls Clerk: verification here is offline
    against cached JWKS, and putting the issuer back on the request path to
    look up an address would give that up for a display string.
    """
    claims: Mapping[str, object] = subject.claims

    def _first(keys: tuple[str, ...]) -> str:
        for key in keys:
            value = claims.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return ""

    email = _first(_EMAIL_CLAIMS)

    display_name = _first(_NAME_CLAIMS)
    if not display_name:
        parts = [
            str(claims.get(key) or "").strip() for key in ("first_name", "last_name")
        ]
        display_name = " ".join(part for part in parts if part)
    if not display_name:
        display_name = _first(("username",))

    return email, display_name


# ---------------------------------------------------------------------------
# Legacy dependencies — unchanged contracts, identity-backed internals
# ---------------------------------------------------------------------------


async def get_current_owner(
    authorization: str | None = Header(default=None, alias="Authorization"),
    settings: Settings = Depends(get_settings),
) -> str:
    """Return the issuer subject for the authenticated caller.

    Still the Clerk ``sub``, not the principal id, on purpose: existing rows
    across this database store ``owner_id`` as the Clerk subject, and changing
    what this returns would silently orphan them. Re-keying to principal ids
    is a data migration, not a refactor.
    """
    subject = await verify_bearer(authorization, settings)
    return subject.subject


# ---------------------------------------------------------------------------
# The identity-native path — all four contract functions
# ---------------------------------------------------------------------------


async def resolve_principal(
    subject: VerifiedSubject, session: AsyncSession
) -> Principal | None:
    """Look the verified subject up in this ecosystem's principal store.

    Machines are created by ``identity_registry.reconcile`` at boot, so a
    machine that resolves to nothing is a configuration problem — its key
    authenticated but the declaration never made it a principal — rather than
    a caller that has yet to introduce itself. There is no provisioning here.
    """
    store = SqlAlchemyPrincipalStore(session, enforcement_point=ENFORCEMENT_POINT)
    return await store.resolve(subject)


HUMAN_DEFAULT_ROLE = "wcs-reader"


async def provision_human(
    subject: VerifiedSubject, session: AsyncSession, *, is_admin: bool = False
) -> Principal | None:
    """Ensure a signed-in person has a principal. Idempotent.

    Machines are created at boot from the declaration; people cannot be,
    because the ecosystem does not know a person exists until they sign in.
    This is the human equivalent of that boot-time step, and it runs from
    ``POST /v1/wcs/me`` — the endpoint the site already calls on first sight
    of a user.

    New people get ``wcs-reader`` and nothing else. That fails closed in the
    direction that gets noticed: a provisioning bug shows up as someone seeing
    too little, which they report, rather than too much, which nobody does.

    ``is_admin`` mirrors the existing profile flag on first creation only. It
    is never re-applied, so promoting or demoting someone later is a change to
    their roles rather than a change to a boolean in another table.
    """
    existing = await resolve_principal(subject, session)
    if existing is not None:
        return existing

    issuer_row = (
        (await session.execute(select(Issuer).where(Issuer.issuer == subject.issuer)))
        .scalars()
        .first()
    )
    if issuer_row is None:
        logger.warning(
            with_log_prefix(
                LOG_WARNING, f"cannot provision: issuer {subject.issuer} unknown"
            )
        )
        return None

    row = PrincipalRow(
        kind="human",
        issuer=subject.issuer,
        subject=subject.subject,
        display_name=str(subject.claims.get("email") or ""),
        email=str(subject.claims.get("email") or "") or None,
    )
    session.add(row)
    await session.flush()
    session.add(
        PrincipalRole(
            principal_id=row.id,
            role_name="wcs-admin" if is_admin else HUMAN_DEFAULT_ROLE,
            granted_by="provision_human",
        )
    )
    await session.commit()
    logger.info(
        with_log_prefix(LOG_START, f"provisioned human principal {subject.subject}")
    )
    return await resolve_principal(subject, session)


def require_scope(scope: str, *, resource_param: str | None = None):
    """Build a FastAPI dependency enforcing one scope.

    Runs the full contract: verify, resolve, authorize, emit audit. The audit
    event is written for allow and deny alike — a trail that records only
    denials cannot answer who did the thing.

    ``resource_param`` names a path parameter to use as the instance-level
    resource, for endpoints where an explicit grant can apply.
    """

    async def _dependency(
        request: Request,
        authorization: str | None = Header(default=None, alias="Authorization"),
        settings: Settings = Depends(get_settings),
        session: AsyncSession = Depends(get_db_session),
    ) -> Principal:
        subject = await verify_bearer(authorization, settings)
        # Stamped as soon as it is known, and again once resolution improves
        # it, so the notification feed can attribute a *denied* request too:
        # a machine that verified but holds no role is exactly the failure
        # worth hearing about, and it never reaches the return below.
        request.state.caller = subject.subject
        request.state.caller_kind = subject.kind

        store = SqlAlchemyPrincipalStore(session, enforcement_point=ENFORCEMENT_POINT)
        sink = SqlAlchemyAuditSink(session)

        principal = await store.resolve(subject)
        if principal is not None:
            request.state.caller = principal.display_name or principal.subject
            request.state.caller_kind = principal.kind
        roles = await store.load_roles()
        resource = (
            str(request.path_params.get(resource_param))
            if resource_param and resource_param in request.path_params
            else None
        )
        grants = (
            await store.load_explicit_grants(principal.id)
            if principal is not None and resource is not None
            else set()
        )

        decision = decide(
            principal, scope, roles, resource=resource, explicit_grants=grants or None
        )

        await sink.emit_audit(
            new_audit_event(
                enforcement_point=ENFORCEMENT_POINT,
                scope=scope,
                allowed=decision.allowed,
                reason=decision.reason,
                principal=principal,
                subject=subject,
                resource=resource,
                request_id=request.headers.get("X-Request-Id"),
            )
        )

        if not decision.allowed:
            # An unknown-but-validly-authenticated caller is a 403, not a 401:
            # the credential was good, the ecosystem simply does not know them.
            raise api_error(403, "forbidden", f"Scope {scope} required")

        assert principal is not None  # noqa: S101 - guaranteed by decision.allowed
        return principal

    return _dependency
