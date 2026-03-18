from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import get_current_owner, get_settings
from ..database import get_db_session
from ..models import PipelineEvaluation as DbEval
from ..schemas import (
    Envelope,
    EvaluationCreateRequest,
    EvaluationFinding,
    EvaluationSummaryItem,
    success_envelope,
)

router = APIRouter()


@router.get(
    "/evaluations",
    response_model=Envelope[list[EvaluationFinding]],
    summary="List evaluation findings",
    description="List pipeline evaluation findings with optional filtering.",
)
async def list_evaluations(
    repo: Annotated[str | None, Query()] = None,
    dimension: Annotated[str | None, Query()] = None,
    severity: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    session: AsyncSession = Depends(get_db_session),
) -> Envelope[list[EvaluationFinding]]:
    settings = get_settings()

    stmt = select(DbEval).order_by(DbEval.created_at.desc())
    if repo:
        stmt = stmt.where(DbEval.repo == repo)
    if dimension:
        stmt = stmt.where(DbEval.dimension == dimension)
    if severity:
        stmt = stmt.where(DbEval.severity == severity)

    stmt = stmt.limit(limit).offset(offset)
    rows = (await session.execute(stmt)).scalars().all()

    data = [
        EvaluationFinding(
            id=row.id,
            repo=row.repo,
            dimension=row.dimension,
            severity=row.severity,
            details=row.details,
            created_at=row.created_at,
        )
        for row in rows
    ]

    return success_envelope(data, count=len(data), version=settings.API_VERSION)


@router.get(
    "/evaluations/summary",
    response_model=Envelope[list[EvaluationSummaryItem]],
    summary="Evaluation summary",
    description="Aggregate evaluation findings grouped by severity and dimension.",
)
async def evaluations_summary(
    session: AsyncSession = Depends(get_db_session),
) -> Envelope[list[EvaluationSummaryItem]]:
    settings = get_settings()

    stmt = (
        select(DbEval.severity, DbEval.dimension, func.count(DbEval.id).label("count"))
        .group_by(DbEval.severity, DbEval.dimension)
        .order_by(func.count(DbEval.id).desc())
    )
    rows = (await session.execute(stmt)).all()

    data = [EvaluationSummaryItem(severity=s, dimension=d, count=c) for s, d, c in rows]
    return success_envelope(data, count=len(data), version=settings.API_VERSION)


@router.post(
    "/evaluations",
    response_model=Envelope[EvaluationFinding],
    summary="Write evaluation findings",
    description="Write pipeline evaluation findings. Protected (owner-based placeholder auth).",
)
async def create_evaluation(
    payload: EvaluationCreateRequest,
    owner_id: str = Depends(get_current_owner),
    session: AsyncSession = Depends(get_db_session),
) -> Envelope[EvaluationFinding]:
    settings = get_settings()

    # Persist as plain text when details isn't a dict. (SQLite JSON support isn't required.)
    details: str | None
    if payload.details is None:
        details = None
    elif isinstance(payload.details, str):
        details = payload.details
    else:
        # Store dict as a stable JSON-ish string representation.
        details = str(payload.details)

    row = DbEval(
        owner_id=owner_id,
        repo=payload.repo,
        dimension=payload.dimension,
        severity=payload.severity,
        details=details,
    )
    session.add(row)
    await session.flush()
    await session.commit()

    data = EvaluationFinding(
        id=row.id,
        repo=row.repo,
        dimension=row.dimension,
        severity=row.severity,
        details=row.details,
        created_at=row.created_at,
    )
    return success_envelope(data, count=1, version=settings.API_VERSION)
