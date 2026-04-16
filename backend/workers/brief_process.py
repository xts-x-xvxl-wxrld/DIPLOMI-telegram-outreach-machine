from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from backend.core.settings import get_settings
from backend.db.models import AudienceBrief
from backend.db.session import AsyncSessionLocal
from backend.queue.client import QueuedJob, enqueue_discovery
from backend.queue.payloads import BriefProcessPayload


BRIEF_FIELD_CAPS = {
    "keywords": 12,
    "related_phrases": 20,
    "language_hints": 8,
    "geography_hints": 10,
    "exclusion_terms": 12,
    "community_types": 6,
}


class BriefProcessError(RuntimeError):
    pass


class BriefValidationError(BriefProcessError):
    pass


class BriefExtraction(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    keywords: list[str] = Field(default_factory=list)
    related_phrases: list[str] = Field(default_factory=list)
    language_hints: list[str] = Field(default_factory=list)
    geography_hints: list[str] = Field(default_factory=list)
    exclusion_terms: list[str] = Field(default_factory=list)
    community_types: list[str] = Field(default_factory=list)


class NormalizedBrief(BaseModel):
    keywords: list[str]
    related_phrases: list[str]
    language_hints: list[str]
    geography_hints: list[str]
    exclusion_terms: list[str]
    community_types: list[str]


Extractor = Callable[[str], Awaitable[BriefExtraction]]
DiscoveryEnqueuer = Callable[..., QueuedJob]


BRIEF_EXTRACTION_INSTRUCTIONS = """You extract Telegram community discovery search guidance.
Return only structured data that helps find relevant public Telegram channels, groups, or discussions.
Do not include direct outreach instructions.
Do not score or rank people.
Do not infer private or sensitive attributes about individual users.
Prefer concise terms that are likely to appear in Telegram titles, descriptions, usernames, or posts.
Use ISO-like language hints when clear, and plain language labels only when uncertain."""


async def extract_brief_with_openai(raw_input: str) -> BriefExtraction:
    try:
        from openai import AsyncOpenAI
    except ImportError as exc:
        raise BriefProcessError("openai must be installed before brief.process can run") from exc

    settings = get_settings()
    if not settings.openai_api_key:
        raise BriefProcessError("OPENAI_API_KEY is required for brief.process")

    client = AsyncOpenAI(api_key=settings.openai_api_key)
    response = await client.responses.parse(
        model=settings.openai_brief_model,
        instructions=BRIEF_EXTRACTION_INSTRUCTIONS,
        input=[
            {
                "role": "user",
                "content": (
                    "Extract structured Telegram community discovery guidance from this "
                    f"operator audience brief:\n\n{raw_input}"
                ),
            }
        ],
        text_format=BriefExtraction,
        temperature=0.2,
        max_output_tokens=1200,
    )
    extraction = response.output_parsed
    if extraction is None:
        raise BriefValidationError("OpenAI returned no parsed brief extraction")
    return extraction


def normalize_brief_extraction(extraction: BriefExtraction) -> NormalizedBrief:
    normalized = {
        field_name: _normalize_string_list(getattr(extraction, field_name), cap)
        for field_name, cap in BRIEF_FIELD_CAPS.items()
    }
    brief = NormalizedBrief(**normalized)
    _validate_search_signal(brief)
    return brief


async def process_brief(
    payload: dict[str, Any],
    *,
    extractor: Extractor = extract_brief_with_openai,
    enqueue_discovery_fn: DiscoveryEnqueuer = enqueue_discovery,
) -> dict[str, Any]:
    validated_payload = BriefProcessPayload.model_validate(payload)

    async with AsyncSessionLocal() as session:
        brief = await session.get(AudienceBrief, validated_payload.brief_id)
        if brief is None:
            raise BriefProcessError(f"Audience brief not found: {validated_payload.brief_id}")

        extraction = await extractor(brief.raw_input)
        normalized = normalize_brief_extraction(extraction)

        brief.keywords = normalized.keywords
        brief.related_phrases = normalized.related_phrases
        brief.language_hints = normalized.language_hints
        brief.geography_hints = normalized.geography_hints
        brief.exclusion_terms = normalized.exclusion_terms
        brief.community_types = normalized.community_types

        try:
            await session.commit()
        except Exception:
            await session.rollback()
            raise

    discovery_job = None
    if validated_payload.auto_start_discovery:
        discovery_job = enqueue_discovery_fn(
            validated_payload.brief_id,
            requested_by=validated_payload.requested_by,
            limit=50,
            auto_expand=False,
        )

    return {
        "status": "processed",
        "job_type": "brief.process",
        "brief_id": str(validated_payload.brief_id),
        "auto_start_discovery": validated_payload.auto_start_discovery,
        "discovery_job": _serialize_job(discovery_job),
        "fields": normalized.model_dump(),
    }


def run_brief_process_job(payload: dict[str, Any]) -> dict[str, Any]:
    return asyncio.run(process_brief(payload))


def _normalize_string_list(values: list[str], cap: int) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()

    for value in values:
        item = " ".join(value.strip().split())
        if not item:
            continue

        key = item.casefold()
        if key in seen:
            continue

        seen.add(key)
        normalized.append(item)
        if len(normalized) >= cap:
            break

    return normalized


def _validate_search_signal(brief: NormalizedBrief) -> None:
    if not brief.keywords and not brief.related_phrases:
        raise BriefValidationError(
            "Brief extraction must include at least one keyword or related phrase"
        )


def _serialize_job(job: QueuedJob | None) -> dict[str, str] | None:
    if job is None:
        return None
    return {"id": job.id, "type": job.type, "status": job.status}
