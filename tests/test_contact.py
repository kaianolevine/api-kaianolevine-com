from __future__ import annotations

import pytest
import respx
from httpx import AsyncClient, Response

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

VALID_JSON_BODY = {
    "type": "contact",
    "originSite": "kaianolevine.com",
    "email": "sender@example.com",
    "turnstileToken": "valid-token",
    "name": "Test User",
    "message": "Hello there",
}

VALID_FORM_BODY = {
    "type": "contact",
    "originSite": "kaianolevine.com",
    "email": "sender@example.com",
    "turnstileToken": "valid-token",
    "name": "Test User",
    "message": "Hello there",
}


def _turnstile_ok(*args, **kwargs):  # noqa: ANN001
    return True


def _turnstile_fail(*args, **kwargs):  # noqa: ANN001
    return False


async def _brevo_ok(**kwargs):  # noqa: ANN001
    return True, None


async def _brevo_fail(**kwargs):  # noqa: ANN001
    return False, "Brevo error detail"


# ---------------------------------------------------------------------------
# Origin allow-list
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_contact_blocked_origin(client: AsyncClient) -> None:
    """Requests from disallowed origins are rejected with 403."""
    resp = await client.post(
        "/v1/contact",
        json=VALID_JSON_BODY,
        headers={"origin": "https://evil.example.com"},
    )

    # The conftest sets CONTACT_ALLOWED_ORIGINS=["https://kaianolevine.com"]
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "forbidden"


@respx.mock
@pytest.mark.asyncio
async def test_contact_allowed_origin(client: AsyncClient) -> None:
    """Requests from an allowed origin proceed past the origin check."""
    respx.post("https://challenges.cloudflare.com/turnstile/v0/siteverify").mock(
        return_value=Response(200, json={"success": True})
    )
    respx.post("https://api.brevo.com/v3/smtp/email").mock(
        return_value=Response(201, json={"messageId": "ok"})
    )
    resp = await client.post(
        "/v1/contact",
        json=VALID_JSON_BODY,
        headers={"origin": "https://kaianolevine.com"},
    )

    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


# ---------------------------------------------------------------------------
# Honeypot
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_contact_honeypot_silent_ok(client: AsyncClient) -> None:
    """Filled honeypot field returns 200 silently without sending email."""
    body = {**VALID_JSON_BODY, "website": "http://spam.example.com"}
    resp = await client.post(
        "/v1/contact",
        json=body,
        headers={"origin": "https://kaianolevine.com"},
    )

    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "missing_field", ["type", "originSite", "email", "turnstileToken"]
)
async def test_contact_missing_required_field(
    client: AsyncClient, missing_field: str
) -> None:
    body = {k: v for k, v in VALID_JSON_BODY.items() if k != missing_field}
    resp = await client.post(
        "/v1/contact",
        json=body,
        headers={"origin": "https://kaianolevine.com"},
    )
    assert resp.status_code == 400
    payload = resp.json()
    assert payload["error"]["code"] == "validation_error"
    assert payload["error"]["details"]["missing"] == [missing_field]


# ---------------------------------------------------------------------------
# Turnstile
# ---------------------------------------------------------------------------


@respx.mock
@pytest.mark.asyncio
async def test_contact_turnstile_failure(client: AsyncClient) -> None:
    respx.post("https://challenges.cloudflare.com/turnstile/v0/siteverify").mock(
        return_value=Response(200, json={"success": False})
    )
    resp = await client.post(
        "/v1/contact",
        json=VALID_JSON_BODY,
        headers={"origin": "https://kaianolevine.com"},
    )

    assert resp.status_code == 400
    err = resp.json()["error"]
    assert err["code"] == "turnstile_failed"
    assert (
        err["message"] == "CAPTCHA verification failed — please refresh and try again"
    )


# ---------------------------------------------------------------------------
# Brevo
# ---------------------------------------------------------------------------


@respx.mock
@pytest.mark.asyncio
async def test_contact_brevo_failure(client: AsyncClient) -> None:
    respx.post("https://challenges.cloudflare.com/turnstile/v0/siteverify").mock(
        return_value=Response(200, json={"success": True})
    )
    respx.post("https://api.brevo.com/v3/smtp/email").mock(
        return_value=Response(500, text="upstream error")
    )
    resp = await client.post(
        "/v1/contact",
        json=VALID_JSON_BODY,
        headers={"origin": "https://kaianolevine.com"},
    )

    assert resp.status_code == 502
    body = resp.json()
    assert body["error"]["code"] == "email_failed"
    assert "details" in body["error"]
    assert body["error"]["details"] == "upstream error"


# ---------------------------------------------------------------------------
# Form data
# ---------------------------------------------------------------------------


@respx.mock
@pytest.mark.asyncio
async def test_contact_form_data(client: AsyncClient) -> None:
    """Endpoint accepts application/x-www-form-urlencoded in addition to JSON."""
    respx.post("https://challenges.cloudflare.com/turnstile/v0/siteverify").mock(
        return_value=Response(200, json={"success": True})
    )
    respx.post("https://api.brevo.com/v3/smtp/email").mock(
        return_value=Response(201, json={"messageId": "ok"})
    )
    resp = await client.post(
        "/v1/contact",
        data=VALID_FORM_BODY,
        headers={"origin": "https://kaianolevine.com"},
    )

    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Redirect
# ---------------------------------------------------------------------------


@respx.mock
@pytest.mark.asyncio
async def test_contact_redirect_true(client: AsyncClient) -> None:
    """redirect=true returns a 303 to {origin}/thanks/."""
    body = {**VALID_JSON_BODY, "redirect": True}
    respx.post("https://challenges.cloudflare.com/turnstile/v0/siteverify").mock(
        return_value=Response(200, json={"success": True})
    )
    respx.post("https://api.brevo.com/v3/smtp/email").mock(
        return_value=Response(201, json={"messageId": "ok"})
    )
    resp = await client.post(
        "/v1/contact",
        json=body,
        headers={"origin": "https://kaianolevine.com"},
        follow_redirects=False,
    )

    assert resp.status_code == 303
    assert resp.headers["location"] == "https://kaianolevine.com/thanks/"


@respx.mock
@pytest.mark.asyncio
async def test_contact_redirect_false(client: AsyncClient) -> None:
    """redirect=false returns plain 200 JSON."""
    body = {**VALID_JSON_BODY, "redirect": False}
    respx.post("https://challenges.cloudflare.com/turnstile/v0/siteverify").mock(
        return_value=Response(200, json={"success": True})
    )
    respx.post("https://api.brevo.com/v3/smtp/email").mock(
        return_value=Response(201, json={"messageId": "ok"})
    )
    resp = await client.post(
        "/v1/contact",
        json=body,
        headers={"origin": "https://kaianolevine.com"},
        follow_redirects=False,
    )

    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
