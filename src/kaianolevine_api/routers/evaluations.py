from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import case, func, select, union
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import get_current_owner
from ..config import get_settings
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


def _eligible_latest_evaluation_ids_subquery():
    """
    Rows that belong to the latest "run" per (repo, source).

    Prefer run_id: at max(evaluated_at), take distinct non-null run_id; return all
    rows with that run_id for the repo+source. If the latest rows only have
    run_id NULL, fall back to rows exactly at max(evaluated_at).
    """
    latest_ts = (
        select(
            DbEval.repo,
            DbEval.source,
            func.max(DbEval.evaluated_at).label("latest_at"),
        )
        .group_by(DbEval.repo, DbEval.source)
        .subquery()
    )

    latest_run_ids = (
        select(
            DbEval.repo,
            DbEval.source,
            DbEval.run_id,
        )
        .join(
            latest_ts,
            (DbEval.repo == latest_ts.c.repo)
            & (DbEval.source == latest_ts.c.source)
            & (DbEval.evaluated_at == latest_ts.c.latest_at),
        )
        .where(DbEval.run_id.isnot(None))
        .distinct()
        .subquery()
    )

    has_run_id_at_latest = (
        select(latest_run_ids.c.repo, latest_run_ids.c.source).distinct().subquery()
    )

    eligible_by_run = select(DbEval.id).join(
        latest_run_ids,
        (DbEval.repo == latest_run_ids.c.repo)
        & (DbEval.source == latest_run_ids.c.source)
        & (DbEval.run_id == latest_run_ids.c.run_id),
    )

    eligible_by_ts = (
        select(DbEval.id)
        .join(
            latest_ts,
            (DbEval.repo == latest_ts.c.repo)
            & (DbEval.source == latest_ts.c.source)
            & (DbEval.evaluated_at == latest_ts.c.latest_at),
        )
        .outerjoin(
            has_run_id_at_latest,
            (DbEval.repo == has_run_id_at_latest.c.repo)
            & (DbEval.source == has_run_id_at_latest.c.source),
        )
        .where(has_run_id_at_latest.c.repo.is_(None))
    )

    return union(eligible_by_run, eligible_by_ts)


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
    run_id: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    session: AsyncSession = Depends(get_db_session),
) -> Envelope[list[PipelineEvaluationItem]]:
    settings = get_settings()

    eligible = _eligible_latest_evaluation_ids_subquery()
    stmt = (
        select(DbEval)
        .where(DbEval.id.in_(eligible))
        .order_by(DbEval.evaluated_at.desc())
    )
    if repo:
        stmt = stmt.where(DbEval.repo == repo)
    if dimension:
        stmt = stmt.where(DbEval.dimension == dimension)
    if severity:
        stmt = stmt.where(DbEval.severity == severity)
    if run_id is not None:
        stmt = stmt.where(DbEval.run_id == run_id)

    total_stmt = select(func.count()).select_from(DbEval).where(DbEval.id.in_(eligible))
    if repo:
        total_stmt = total_stmt.where(DbEval.repo == repo)
    if dimension:
        total_stmt = total_stmt.where(DbEval.dimension == dimension)
    if severity:
        total_stmt = total_stmt.where(DbEval.severity == severity)
    if run_id is not None:
        total_stmt = total_stmt.where(DbEval.run_id == run_id)
    total = (await session.execute(total_stmt)).scalar_one()

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
            source=row.source,
            flow_name=row.flow_name,
            evaluated_at=row.evaluated_at,
        )
        for row in rows
    ]

    return success_envelope(
        data, count=len(data), total=total, version=settings.API_VERSION
    )


@router.get(
    "/evaluations/summary",
    response_model=Envelope[list[EvaluationSummaryItem]],
    summary="Evaluation summary",
    description="Aggregate evaluation findings grouped by dimension.",
)
async def evaluations_summary(
    run_id: Annotated[str | None, Query()] = None,
    session: AsyncSession = Depends(get_db_session),
) -> Envelope[list[EvaluationSummaryItem]]:
    settings = get_settings()

    eligible = _eligible_latest_evaluation_ids_subquery()
    stmt = (
        select(
            DbEval.dimension,
            func.sum(case((DbEval.severity == "ERROR", 1), else_=0)).label(
                "error_count"
            ),
            func.sum(case((DbEval.severity == "WARN", 1), else_=0)).label("warn_count"),
            func.sum(case((DbEval.severity == "INFO", 1), else_=0)).label("info_count"),
            func.max(DbEval.evaluated_at).label("most_recent"),
        )
        .where(DbEval.id.in_(eligible))
        .group_by(DbEval.dimension)
        .order_by(func.max(DbEval.evaluated_at).desc())
    )
    if run_id is not None:
        stmt = stmt.where(DbEval.run_id == run_id)
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
    return success_envelope(
        data, count=len(data), total=len(data), version=settings.API_VERSION
    )


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
        source=payload.source,
        flow_name=payload.flow_name,
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
        source=row.source,
        flow_name=row.flow_name,
        evaluated_at=row.evaluated_at,
    )
    return success_envelope(data, count=1, total=1, version=settings.API_VERSION)
