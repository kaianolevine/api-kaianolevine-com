from __future__ import annotations

from sqlalchemy.ext.asyncio import async_sessionmaker

from deejay_sets_api.models import FeatureFlag as DbFeatureFlag
from deejay_sets_api.services.flags import is_enabled


async def test_flags_endpoints_and_service_contract(client, async_engine) -> None:
    sessionmaker = async_sessionmaker(async_engine, expire_on_commit=False, autoflush=False)
    async with sessionmaker() as session:
        session.add(
            DbFeatureFlag(
                owner_id="dev-owner",
                name="flags.deejay_api.ingest_enabled",
                enabled=True,
                description="Enable ingest endpoint",
            )
        )
        session.add(
            DbFeatureFlag(
                owner_id="dev-owner",
                name="flags.deejay_api.public_catalog_enabled",
                enabled=True,
                description="Enable public catalog endpoints",
            )
        )
        await session.commit()

    list_resp = await client.get("/v1/flags")
    assert list_resp.status_code == 200
    list_json = list_resp.json()
    assert "data" in list_json and "meta" in list_json
    assert list_json["meta"]["count"] == len(list_json["data"])
    assert any(item["name"] == "flags.deejay_api.ingest_enabled" for item in list_json["data"])

    patch_resp = await client.patch(
        "/v1/flags/flags.deejay_api.ingest_enabled",
        json={"enabled": False},
    )
    assert patch_resp.status_code == 200
    patched = patch_resp.json()["data"]
    assert patched["name"] == "flags.deejay_api.ingest_enabled"
    assert patched["enabled"] is False

    async with sessionmaker() as session:
        assert await is_enabled("flags.deejay_api.unknown_flag", session) is True
        assert await is_enabled("flags.deejay_api.ingest_enabled", session) is False

