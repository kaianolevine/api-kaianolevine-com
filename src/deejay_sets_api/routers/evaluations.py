from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import get_current_owner, get_settings
from ..database import get_db_session
from ..models import PipelineEvaluation as DbEval
from ..schemas import (
    Envelope,
    EvaluationSummaryItem,
    PipelineEvaluationCreate,
    PipelineEvaluationItem,
    success_envelope,
)

router = APIRouter()


@router.get(
    "/evaluations",
    response_model=Envelope[list[PipelineEvaluationItem]],
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
) -> Envelope[list[PipelineEvaluationItem]]:
    settings = get_settings()

    stmt = select(DbEval).order_by(DbEval.evaluated_at.desc())
    if repo:
        stmt = stmt.where(DbEval.repo == repo)
    if dimension:
        stmt = stmt.where(DbEval.dimension == dimension)
    if severity:
        stmt = stmt.where(DbEval.severity == severity)

    stmt = stmt.limit(limit).offset(offset)
    rows = (await session.execute(stmt)).scalars().all()

    data = [
        PipelineEvaluationItem(
            id=row.id,
            run_id=row.run_id,
            repo=row.repo,
            dimension=row.dimension,
            severity=row.severity,
            finding=row.finding or "",
            suggestion=row.suggestion,
            standards_version=row.standards_version,
            evaluated_at=row.evaluated_at,
        )
        for row in rows
    ]

    return success_envelope(data, count=len(data), version=settings.API_VERSION)


@router.get(
    "/evaluations/summary",
    response_model=Envelope[list[EvaluationSummaryItem]],
    summary="Evaluation summary",
    description="Aggregate evaluation findings grouped by dimension.",
)
async def evaluations_summary(
    session: AsyncSession = Depends(get_db_session),
) -> Envelope[list[EvaluationSummaryItem]]:
    settings = get_settings()

    stmt = (
        select(
            DbEval.dimension,
            func.sum(case((DbEval.severity == "ERROR", 1), else_=0)).label("error_count"),
            func.sum(case((DbEval.severity == "WARN", 1), else_=0)).label("warn_count"),
            func.sum(case((DbEval.severity == "INFO", 1), else_=0)).label("info_count"),
            func.max(DbEval.evaluated_at).label("most_recent"),
        )
        .group_by(DbEval.dimension)
        .order_by(func.max(DbEval.evaluated_at).desc())
    )
    rows = (await session.execute(stmt)).all()

    data = [
        EvaluationSummaryItem(
            dimension=d,
            error_count=error_count,
            warn_count=warn_count,
            info_count=info_count,
            most_recent=most_recent,
        )
        for d, error_count, warn_count, info_count, most_recent in rows
    ]
    return success_envelope(data, count=len(data), version=settings.API_VERSION)


@router.post(
    "/evaluations",
    response_model=Envelope[PipelineEvaluationItem],
    summary="Write evaluation findings",
    description="Write pipeline evaluation findings. Protected (owner-based placeholder auth).",
)
async def create_evaluation(
    payload: PipelineEvaluationCreate,
    owner_id: str = Depends(get_current_owner),
    session: AsyncSession = Depends(get_db_session),
) -> Envelope[PipelineEvaluationItem]:
    settings = get_settings()

    # Legacy catch-all field intentionally left empty.
    details = None

    row = DbEval(
        owner_id=owner_id,
        repo=payload.repo,
        dimension=payload.dimension,
        severity=payload.severity,
        details=details,
        run_id=payload.run_id,
        finding=payload.finding,
        suggestion=payload.suggestion,
        standards_version=payload.standards_version,
    )
    session.add(row)
    await session.flush()
    await session.commit()
    await session.refresh(row)

    data = PipelineEvaluationItem(
        id=row.id,
        run_id=row.run_id,
        repo=row.repo,
        dimension=row.dimension,
        severity=row.severity,
        finding=row.finding or "",
        suggestion=row.suggestion,
        standards_version=row.standards_version,
        evaluated_at=row.evaluated_at,
    )
    return success_envelope(data, count=1, version=settings.API_VERSION)
