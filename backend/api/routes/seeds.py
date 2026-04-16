from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import case, desc, func, select

from backend.api.deps import DbSession, require_bot_token
from backend.api.schemas import (
    JobResponse,
    SeedGroupCandidateItem,
    SeedGroupCandidateListResponse,
    SeedGroupDetailResponse,
    SeedChannelListResponse,
    SeedGroupExpansionJobRequest,
    SeedGroupListItem,
    SeedGroupListResponse,
    SeedGroupResolveJobRequest,
    SeedImportErrorOut,
    SeedImportGroupSummaryOut,
    SeedImportRequest,
    SeedImportResponse,
)
from backend.db.enums import CommunityStatus, SeedChannelStatus
from backend.db.models import Community, CommunityDiscoveryEdge, SeedChannel, SeedGroup
from backend.queue.client import QueueUnavailable, enqueue_seed_expansion, enqueue_seed_resolve
from backend.services.seed_import import import_seed_csv

router = APIRouter(dependencies=[Depends(require_bot_token)])


@router.post("/seed-imports/csv", response_model=SeedImportResponse, status_code=201)
async def import_seed_csv_route(payload: SeedImportRequest, db: DbSession) -> SeedImportResponse:
    try:
        result = await import_seed_csv(
            db,
            payload.csv_text,
            requested_by=payload.requested_by or "operator",
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail={"code": "invalid_csv", "message": str(exc)},
        ) from exc

    await db.commit()
    return SeedImportResponse(
        imported=result.imported,
        updated=result.updated,
        errors=[
            SeedImportErrorOut(row_number=error.row_number, message=error.message)
            for error in result.errors
        ],
        groups=[
            SeedImportGroupSummaryOut(
                id=UUID(summary.id),
                name=summary.name,
                imported=summary.imported,
                updated=summary.updated,
            )
            for summary in result.groups.values()
        ],
    )


@router.get("/seed-groups", response_model=SeedGroupListResponse)
async def list_seed_groups(db: DbSession) -> SeedGroupListResponse:
    items = [
        _seed_group_list_item(seed_group, seed_count, resolved_count, unresolved_count, failed_count)
        for seed_group, seed_count, resolved_count, unresolved_count, failed_count in (
            await db.execute(_seed_group_summary_query())
        ).all()
    ]
    return SeedGroupListResponse(items=items, total=len(items))


@router.get("/seed-groups/{seed_group_id}", response_model=SeedGroupDetailResponse)
async def get_seed_group(seed_group_id: UUID, db: DbSession) -> SeedGroupDetailResponse:
    row = (
        await db.execute(
            _seed_group_summary_query().where(SeedGroup.id == seed_group_id).limit(1)
        )
    ).first()
    if row is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "not_found", "message": "Seed group not found"},
        )

    seed_group, seed_count, resolved_count, unresolved_count, failed_count = row
    return SeedGroupDetailResponse(
        group=_seed_group_list_item(
            seed_group,
            seed_count,
            resolved_count,
            unresolved_count,
            failed_count,
        )
    )


@router.get("/seed-groups/{seed_group_id}/channels", response_model=SeedChannelListResponse)
async def list_seed_group_channels(
    seed_group_id: UUID,
    db: DbSession,
) -> SeedChannelListResponse:
    seed_group = await db.get(SeedGroup, seed_group_id)
    if seed_group is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "not_found", "message": "Seed group not found"},
        )

    rows = await db.scalars(
        select(SeedChannel)
        .where(SeedChannel.seed_group_id == seed_group_id)
        .order_by(SeedChannel.created_at)
    )
    items = list(rows)
    return SeedChannelListResponse(items=items, total=len(items))


@router.get(
    "/seed-groups/{seed_group_id}/candidates",
    response_model=SeedGroupCandidateListResponse,
)
async def list_seed_group_candidates(
    seed_group_id: UUID,
    db: DbSession,
    status_value: str | None = Query(default="candidate", alias="status"),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    include_rejected: bool = False,
) -> SeedGroupCandidateListResponse:
    seed_group = await db.get(SeedGroup, seed_group_id)
    if seed_group is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "not_found", "message": "Seed group not found"},
        )

    resolved_seed_rows = (
        await db.execute(
            select(SeedChannel, Community)
            .join(Community, Community.id == SeedChannel.community_id)
            .where(SeedChannel.seed_group_id == seed_group_id)
            .where(SeedChannel.community_id.is_not(None))
        )
    ).all()
    discovered_rows = (
        await db.execute(
            select(CommunityDiscoveryEdge, Community)
            .join(Community, Community.id == CommunityDiscoveryEdge.target_community_id)
            .where(CommunityDiscoveryEdge.seed_group_id == seed_group_id)
        )
    ).all()

    items = _build_seed_group_candidate_items(
        seed_group_id=seed_group_id,
        resolved_seed_rows=resolved_seed_rows,
        discovered_rows=discovered_rows,
        status_value=status_value,
        include_rejected=include_rejected,
    )
    return SeedGroupCandidateListResponse(
        items=items[offset : offset + limit],
        limit=limit,
        offset=offset,
        total=len(items),
    )


@router.post("/seed-groups/{seed_group_id}/resolve-jobs", response_model=JobResponse, status_code=202)
async def start_seed_group_resolution(
    seed_group_id: UUID,
    payload: SeedGroupResolveJobRequest,
    db: DbSession,
) -> JobResponse:
    seed_group = await db.get(SeedGroup, seed_group_id)
    if seed_group is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "not_found", "message": "Seed group not found"},
        )

    eligible_statuses = [SeedChannelStatus.PENDING.value]
    if payload.retry_failed:
        eligible_statuses.extend(
            [
                SeedChannelStatus.FAILED.value,
                SeedChannelStatus.INACCESSIBLE.value,
            ]
        )
    eligible_count = await db.scalar(
        select(func.count(SeedChannel.id))
        .where(SeedChannel.seed_group_id == seed_group_id)
        .where(SeedChannel.status.in_(eligible_statuses))
    )
    if not eligible_count:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "no_seed_channels_to_resolve",
                "message": "Seed group has no seed channels eligible for resolution",
            },
        )

    try:
        job = enqueue_seed_resolve(
            seed_group_id,
            requested_by="operator",
            limit=payload.limit,
            retry_failed=payload.retry_failed,
        )
    except QueueUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return JobResponse(job=job)


def _seed_group_summary_query():
    return (
        select(
            SeedGroup,
            func.count(SeedChannel.id).label("seed_count"),
            func.count(SeedChannel.community_id).label("resolved_count"),
            func.coalesce(
                func.sum(
                    case((SeedChannel.status == SeedChannelStatus.PENDING.value, 1), else_=0)
                ),
                0,
            ).label("unresolved_count"),
            func.coalesce(
                func.sum(
                    case(
                        (
                            SeedChannel.status.in_(
                                [
                                    SeedChannelStatus.INVALID.value,
                                    SeedChannelStatus.INACCESSIBLE.value,
                                    SeedChannelStatus.NOT_COMMUNITY.value,
                                    SeedChannelStatus.FAILED.value,
                                ]
                            ),
                            1,
                        ),
                        else_=0,
                    )
                ),
                0,
            ).label("failed_count"),
        )
        .outerjoin(SeedChannel, SeedChannel.seed_group_id == SeedGroup.id)
        .group_by(SeedGroup.id)
        .order_by(desc(SeedGroup.created_at))
    )


def _seed_group_list_item(
    seed_group: SeedGroup,
    seed_count: int,
    resolved_count: int,
    unresolved_count: int,
    failed_count: int,
) -> SeedGroupListItem:
    return SeedGroupListItem(
        id=seed_group.id,
        name=seed_group.name,
        description=seed_group.description,
        created_by=seed_group.created_by,
        created_at=seed_group.created_at,
        seed_count=seed_count,
        resolved_count=resolved_count,
        unresolved_count=unresolved_count,
        failed_count=failed_count,
    )


def _build_seed_group_candidate_items(
    *,
    seed_group_id: UUID,
    resolved_seed_rows: list[tuple[SeedChannel, Community]],
    discovered_rows: list[tuple[CommunityDiscoveryEdge, Community]],
    status_value: str | None,
    include_rejected: bool,
) -> list[SeedGroupCandidateItem]:
    aggregated: dict[UUID, dict[str, object]] = {}

    for seed_channel, community in resolved_seed_rows:
        bucket = aggregated.setdefault(
            community.id,
            {
                "community": community,
                "seed_ids": set(),
                "evidence_keys": set(),
                "evidence_types": set(),
            },
        )
        seed_ids = bucket["seed_ids"]
        evidence_keys = bucket["evidence_keys"]
        evidence_types = bucket["evidence_types"]
        assert isinstance(seed_ids, set)
        assert isinstance(evidence_keys, set)
        assert isinstance(evidence_types, set)

        seed_ids.add(seed_channel.id)
        evidence_keys.add(("manual_seed", seed_channel.id))
        evidence_types.add("manual_seed")

    for edge, community in discovered_rows:
        bucket = aggregated.setdefault(
            community.id,
            {
                "community": community,
                "seed_ids": set(),
                "evidence_keys": set(),
                "evidence_types": set(),
            },
        )
        seed_ids = bucket["seed_ids"]
        evidence_keys = bucket["evidence_keys"]
        evidence_types = bucket["evidence_types"]
        assert isinstance(seed_ids, set)
        assert isinstance(evidence_keys, set)
        assert isinstance(evidence_types, set)

        if edge.seed_channel_id is not None:
            seed_ids.add(edge.seed_channel_id)
        evidence_keys.add(
            (
                edge.evidence_type,
                edge.evidence_value,
                edge.seed_channel_id,
                edge.source_community_id,
            )
        )
        evidence_types.add(edge.evidence_type)

    items: list[SeedGroupCandidateItem] = []
    for community_id, bucket in aggregated.items():
        community = bucket["community"]
        seed_ids = bucket["seed_ids"]
        evidence_keys = bucket["evidence_keys"]
        evidence_types = bucket["evidence_types"]
        assert isinstance(community, Community)
        assert isinstance(seed_ids, set)
        assert isinstance(evidence_keys, set)
        assert isinstance(evidence_types, set)

        if status_value and community.status != status_value:
            continue
        if not include_rejected and community.status == CommunityStatus.REJECTED.value:
            continue

        evidence_type_list = sorted(str(value) for value in evidence_types)
        source_seed_count = len(seed_ids)
        evidence_count = len(evidence_keys)
        items.append(
            SeedGroupCandidateItem(
                community=community,
                seed_group_id=seed_group_id,
                source_seed_count=source_seed_count,
                evidence_count=evidence_count,
                evidence_types=evidence_type_list,
                candidate_score=_candidate_score(
                    source_seed_count=source_seed_count,
                    evidence_count=evidence_count,
                    evidence_types=evidence_type_list,
                ),
            )
        )

    return sorted(
        items,
        key=lambda item: (
            -item.candidate_score,
            -(item.community.member_count or 0),
            str(item.community.id),
        ),
    )


def _candidate_score(
    *,
    source_seed_count: int,
    evidence_count: int,
    evidence_types: list[str],
) -> int:
    type_bonus = {
        "manual_seed": 24,
        "forward_source": 14,
        "linked_discussion": 12,
        "telegram_link": 10,
        "mention": 8,
    }
    bonus = sum(type_bonus.get(evidence_type, 6) for evidence_type in evidence_types)
    return min(100, source_seed_count * 18 + evidence_count * 10 + bonus)


@router.post("/seed-groups/{seed_group_id}/expansion-jobs", response_model=JobResponse, status_code=202)
async def start_seed_group_expansion(
    seed_group_id: UUID,
    payload: SeedGroupExpansionJobRequest,
    db: DbSession,
) -> JobResponse:
    seed_group = await db.get(SeedGroup, seed_group_id)
    if seed_group is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "not_found", "message": "Seed group not found"},
        )

    resolved_count = await db.scalar(
        select(func.count(SeedChannel.id))
        .where(SeedChannel.seed_group_id == seed_group_id)
        .where(SeedChannel.status == SeedChannelStatus.RESOLVED.value)
        .where(SeedChannel.community_id.is_not(None))
    )
    if not resolved_count:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "no_resolved_seed_communities",
                "message": "Seed group has no resolved communities yet",
            },
        )

    try:
        job = enqueue_seed_expansion(
            seed_group_id,
            payload.brief_id,
            depth=payload.depth,
            requested_by="operator",
        )
    except QueueUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return JobResponse(job=job)
