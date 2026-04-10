from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from kaianolevine_api.models import FeatureFlag as DbFeatureFlag
from kaianolevine_api.services.flags import is_enabled


async def test_flags_get_list_meta_total_matches_db_count(client, async_engine) -> None:
    sessionmaker = async_sessionmaker(
        async_engine, expire_on_commit=False, autoflush=False
    )
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

    async with sessionmaker() as session:
        db_total = (
            await session.execute(select(func.count()).select_from(DbFeatureFlag))
        ).scalar_one()

    list_resp = await client.get("/v1/flags")
    assert list_resp.status_code == 200
    list_json = list_resp.json()
    assert list_json["meta"]["total"] == db_total
    assert list_json["meta"]["count"] == len(list_json["data"])
    assert list_json["meta"]["total"] == list_json["meta"]["count"]


async def test_flags_patch_known_flag_and_service_contract(
    client, async_engine
) -> None:
    sessionmaker = async_sessionmaker(
        async_engine, expire_on_commit=False, autoflush=False
    )
    async with sessionmaker() as session:
        session.add(
            DbFeatureFlag(
                owner_id="dev-owner",
                name="flags.deejay_api.ingest_enabled",
                enabled=True,
                description="Enable ingest endpoint",
            )
        )
        await session.commit()

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


async def test_flags_patch_unknown_name_returns_404(client, async_engine) -> None:
    sessionmaker = async_sessionmaker(
        async_engine, expire_on_commit=False, autoflush=False
    )
    async with sessionmaker() as session:
        session.add(
            DbFeatureFlag(
                owner_id="dev-owner",
                name="flags.deejay_api.ingest_enabled",
                enabled=True,
                description="x",
            )
        )
        await session.commit()

    resp = await client.patch(
        "/v1/flags/does-not-exist-flag-name",
        json={"enabled": True},
    )
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "not_found"
