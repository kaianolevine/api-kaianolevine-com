from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

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
    with patch(
        "kaianolevine_api.routers.contact._verify_turnstile", new_callable=AsyncMock
    ) as mock_ts:
        mock_ts.return_value = True
        resp = await client.post(
            "/v1/contact",
            json=VALID_JSON_BODY,
            headers={"origin": "https://evil.example.com"},
        )

    # The conftest sets CONTACT_ALLOWED_ORIGINS=["https://kaianolevine.com"]
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "forbidden"


@pytest.mark.asyncio
async def test_contact_allowed_origin(client: AsyncClient) -> None:
    """Requests from an allowed origin proceed past the origin check."""
    with (
        patch(
            "kaianolevine_api.routers.contact._verify_turnstile", new_callable=AsyncMock
        ) as mock_ts,
        patch(
            "kaianolevine_api.routers.contact._send_brevo_email", new_callable=AsyncMock
        ) as mock_brevo,
    ):
        mock_ts.return_value = True
        mock_brevo.return_value = (True, None)
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
    with patch(
        "kaianolevine_api.routers.contact._send_brevo_email", new_callable=AsyncMock
    ) as mock_brevo:
        resp = await client.post(
            "/v1/contact",
            json=body,
            headers={"origin": "https://kaianolevine.com"},
        )
        mock_brevo.assert_not_called()

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


@pytest.mark.asyncio
async def test_contact_turnstile_failure(client: AsyncClient) -> None:
    with patch(
        "kaianolevine_api.routers.contact._verify_turnstile", new_callable=AsyncMock
    ) as mock_ts:
        mock_ts.return_value = False
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


@pytest.mark.asyncio
async def test_contact_brevo_failure(client: AsyncClient) -> None:
    with (
        patch(
            "kaianolevine_api.routers.contact._verify_turnstile", new_callable=AsyncMock
        ) as mock_ts,
        patch(
            "kaianolevine_api.routers.contact._send_brevo_email", new_callable=AsyncMock
        ) as mock_brevo,
    ):
        mock_ts.return_value = True
        mock_brevo.return_value = (False, "upstream error")
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


@pytest.mark.asyncio
async def test_contact_form_data(client: AsyncClient) -> None:
    """Endpoint accepts application/x-www-form-urlencoded in addition to JSON."""
    with (
        patch(
            "kaianolevine_api.routers.contact._verify_turnstile", new_callable=AsyncMock
        ) as mock_ts,
        patch(
            "kaianolevine_api.routers.contact._send_brevo_email", new_callable=AsyncMock
        ) as mock_brevo,
    ):
        mock_ts.return_value = True
        mock_brevo.return_value = (True, None)
        resp = await client.post(
            "/v1/contact",
            data=VALID_FORM_BODY,
            headers={"origin": "https://kaianolevine.com"},
        )

    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Redirect
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_contact_redirect_true(client: AsyncClient) -> None:
    """redirect=true returns a 303 to {origin}/thanks/."""
    body = {**VALID_JSON_BODY, "redirect": True}
    with (
        patch(
            "kaianolevine_api.routers.contact._verify_turnstile", new_callable=AsyncMock
        ) as mock_ts,
        patch(
            "kaianolevine_api.routers.contact._send_brevo_email", new_callable=AsyncMock
        ) as mock_brevo,
    ):
        mock_ts.return_value = True
        mock_brevo.return_value = (True, None)
        resp = await client.post(
            "/v1/contact",
            json=body,
            headers={"origin": "https://kaianolevine.com"},
            follow_redirects=False,
        )

    assert resp.status_code == 303
    assert resp.headers["location"] == "https://kaianolevine.com/thanks/"


@pytest.mark.asyncio
async def test_contact_redirect_false(client: AsyncClient) -> None:
    """redirect=false returns plain 200 JSON."""
    body = {**VALID_JSON_BODY, "redirect": False}
    with (
        patch(
            "kaianolevine_api.routers.contact._verify_turnstile", new_callable=AsyncMock
        ) as mock_ts,
        patch(
            "kaianolevine_api.routers.contact._send_brevo_email", new_callable=AsyncMock
        ) as mock_brevo,
    ):
        mock_ts.return_value = True
        mock_brevo.return_value = (True, None)
        resp = await client.post(
            "/v1/contact",
            json=body,
            headers={"origin": "https://kaianolevine.com"},
            follow_redirects=False,
        )

    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
