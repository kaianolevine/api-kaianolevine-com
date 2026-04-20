from __future__ import annotations

import html
from typing import Any
from urllib.parse import parse_qs

import httpx
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, RedirectResponse
from starlette.responses import Response

from ..config import get_settings
from ..schemas import ErrorDetail, ErrorEnvelope

router = APIRouter()

# Fields that are infrastructure/routing concerns and should not appear
# in the email body as generic "extra fields".
_RESERVED_FIELDS: frozenset[str] = frozenset(
    {
        # Turnstile / infra
        "cf-turnstile-response",
        "turnstileToken",
        "token",
        # Identity / routing (shown at top or used elsewhere)
        "email",
        "replyTo",
        "reply_to",
        "originSite",
        "origin_site",
        "site",
        "source",
        "type",
        # Honeypot
        "website",
        "url",
    }
)


def _pick(fields: dict[str, str], keys: list[str]) -> str | None:
    for k in keys:
        v = fields.get(k, "")
        if v.strip():
            return v.strip()
    return None


def _derive_reply_name(fields: dict[str, str]) -> str | None:
    preferred = _pick(fields, ["preferredName", "preferred_name", "preferred"])
    last = _pick(fields, ["lastName", "last_name", "last"])
    if preferred and last:
        return f"{preferred} {last}"
    if preferred:
        return preferred

    name = _pick(fields, ["name"])
    if name:
        return name

    first = _pick(fields, ["firstName", "first_name", "first"])
    if first and last:
        return f"{first} {last}"
    if first:
        return first

    return None


def _parse_bool(v: Any, default: bool) -> bool:
    if isinstance(v, bool):
        return v
    if isinstance(v, int):
        return v != 0
    if isinstance(v, str):
        s = v.strip().lower()
        if s in {"true", "1", "yes", "y"}:
            return True
        if s in {"false", "0", "no", "n"}:
            return False
    return default


async def _read_fields(
    request: Request,
) -> tuple[dict[str, str], Any] | tuple[None, str]:
    """
    Parse request body as JSON or form data.
    Returns (fields_dict, redirect_raw) on success, or (None, error_message) on failure.
    """
    content_type = request.headers.get("content-type", "")
    fields: dict[str, str] = {}
    redirect_raw: Any = None

    if "application/json" in content_type:
        try:
            body: dict[str, Any] = await request.json()
        except Exception:
            return None, "Invalid JSON"

        if isinstance(body, dict):
            redirect_raw = body.get("redirect")
            for k, v in body.items():
                if k == "redirect":
                    continue
                if isinstance(v, str | int | float | bool):
                    fields[k] = str(v)
    else:
        # Starlette's request.form() requires `python-multipart` which isn't always
        # available in minimal environments. For the common
        # `application/x-www-form-urlencoded` case, parse the body ourselves.
        if "application/x-www-form-urlencoded" in content_type:
            try:
                body_bytes = await request.body()
                body_text = body_bytes.decode("utf-8", errors="replace")
            except Exception:
                return None, "Invalid form data"

            parsed = parse_qs(body_text, keep_blank_values=True)
            for k, vals in parsed.items():
                if vals:
                    fields[k] = str(vals[0])
            redirect_raw = fields.get("redirect")
            return fields, redirect_raw

        try:
            form = await request.form()
        except Exception:
            return None, "Invalid form data"

        for k, v in form.multi_items():
            if isinstance(v, str):
                fields[k] = v
        redirect_raw = fields.get("redirect")

    return fields, redirect_raw


async def _verify_turnstile(token: str, secret: str, remote_ip: str | None) -> bool:
    data = {"secret": secret, "response": token}
    if remote_ip:
        data["remoteip"] = remote_ip

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://challenges.cloudflare.com/turnstile/v0/siteverify",
            data=data,
            timeout=10.0,
        )
        result = resp.json()
        return bool(result.get("success"))


async def _send_brevo_email(
    *,
    api_key: str,
    from_email: str,
    to_email: str,
    subject: str,
    html_content: str,
    reply_to_email: str,
    reply_to_name: str | None,
) -> tuple[bool, str | None]:
    payload: dict[str, Any] = {
        "to": [{"email": to_email}],
        "sender": {"email": from_email, "name": "Kaiano API"},
        "subject": subject,
        "htmlContent": html_content,
        "replyTo": {"email": reply_to_email},
    }
    if reply_to_name:
        payload["replyTo"]["name"] = reply_to_name

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://api.brevo.com/v3/smtp/email",
            json=payload,
            headers={"api-key": api_key, "content-type": "application/json"},
            timeout=15.0,
        )

    if resp.is_success:
        return True, None
    return False, resp.text


def _error_response(
    status: int,
    code: str,
    message: str,
    details: dict | str | None = None,
) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        content=ErrorEnvelope(
            error=ErrorDetail(code=code, message=message, details=details)
        ).model_dump(),
    )


@router.post(
    "/contact",
    summary="Submit a contact form",
    description=(
        "Accepts JSON or multipart/form-data. Validates a Cloudflare "
        "Turnstile token, then sends an email via Brevo. Only allowed "
        "from configured CORS_ORIGINS. Intentionally public (no auth "
        "required): the origin allowlist and Turnstile challenge are "
        "the gatekeepers, not a bearer token."
    ),
    response_model=None,
    status_code=200,
)
async def submit_contact(request: Request) -> Response:
    """Submit a contact form. Intentionally public — gated by CORS allowlist and Turnstile, not by bearer token."""
    settings = get_settings()

    # --- Origin allow-list ---
    origin = request.headers.get("origin", "").strip()
    allowed = settings.CORS_ORIGINS
    if allowed and "*" not in allowed and origin not in allowed:
        return _error_response(403, "forbidden", "Origin not permitted")

    # --- Parse body ---
    result = await _read_fields(request)
    fields, redirect_raw = result
    if fields is None:
        # redirect_raw holds the error string in the failure case
        return _error_response(400, "parse_error", str(redirect_raw))

    # --- Honeypot ---
    honeypot = _pick(fields, ["website", "url"])
    if honeypot:
        # Silent success — do not reveal spam detection
        return JSONResponse(status_code=200, content={"status": "ok"})

    # --- Required field extraction ---
    submission_type = _pick(fields, ["type"])
    origin_site = _pick(fields, ["originSite", "origin_site", "site", "source"])
    email = _pick(fields, ["email", "replyTo", "reply_to"])
    token = _pick(fields, ["turnstileToken", "token", "cf-turnstile-response"])
    # Only redirect when explicitly requested; if the field is omitted, default to no redirect.
    redirect = _parse_bool(redirect_raw, False)

    _field_keys = {
        "type": ["type"],
        "originSite": ["originSite", "origin_site", "site", "source"],
        "email": ["email", "replyTo", "reply_to"],
        "turnstileToken": ["turnstileToken", "token", "cf-turnstile-response"],
    }
    missing = [
        f
        for f in ["type", "originSite", "email", "turnstileToken"]
        if not _pick(fields, _field_keys[f])
    ]
    if missing:
        return _error_response(
            400,
            "validation_error",
            "Missing required fields",
            details={"missing": missing},
        )

    # --- Turnstile verification ---
    remote_ip = request.client.host if request.client else None
    turnstile_ok = await _verify_turnstile(
        token=token,  # type: ignore[arg-type]
        secret=settings.TURNSTILE_SECRET_KEY,
        remote_ip=remote_ip,
    )
    if not turnstile_ok:
        return _error_response(
            400,
            "turnstile_failed",
            "CAPTCHA verification failed — please refresh and try again",
        )

    # --- Build email ---
    reply_name = _derive_reply_name(fields)

    fields_html = "\n".join(
        f"<p><strong>{html.escape(k)}:</strong><br/>{html.escape(v)}</p>"
        for k, v in fields.items()
        if k not in _RESERVED_FIELDS
    )
    html_content = (
        f"<p><strong>Origin Site:</strong> {html.escape(origin_site)}</p>\n"  # type: ignore[arg-type]
        f"<p><strong>Submission Type:</strong> {html.escape(submission_type)}</p>\n"  # type: ignore[arg-type]
        f"<p><strong>Reply-To:</strong> {html.escape(email)}</p>\n"  # type: ignore[arg-type]
        f"<hr/>\n"
        f"{fields_html or '<p><em>No additional fields captured.</em></p>'}"
    )

    # --- Send via Brevo ---
    if not all(
        [settings.BREVO_API_KEY, settings.CONTACT_TO_EMAIL, settings.CONTACT_FROM_EMAIL]
    ):
        return _error_response(500, "config_error", "Email configuration missing")

    sent, error_detail = await _send_brevo_email(
        api_key=settings.BREVO_API_KEY,  # type: ignore[arg-type]
        from_email=settings.CONTACT_FROM_EMAIL,  # type: ignore[arg-type]
        to_email=settings.CONTACT_TO_EMAIL,  # type: ignore[arg-type]
        subject=f"New {submission_type} Submission from {origin_site}",
        html_content=html_content,
        reply_to_email=email,  # type: ignore[arg-type]
        reply_to_name=reply_name,
    )

    if not sent:
        return _error_response(
            502, "email_failed", "Failed to send email", details=error_detail
        )

    # --- Redirect or plain OK ---
    if redirect and origin:
        return RedirectResponse(
            url=f"{origin}/thanks/",
            status_code=303,
            headers={"cache-control": "no-store"},
        )

    return JSONResponse(status_code=200, content={"status": "ok"})
