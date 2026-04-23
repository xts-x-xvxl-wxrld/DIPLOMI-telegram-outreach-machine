from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Protocol

from backend.db.enums import SearchAdapter, SearchEvidenceType
from backend.services.search_retrieval import EntitySearchEvidence, canonical_telegram_url, normalize_telegram_username

POST_SEARCH_SNIPPET_LIMIT = 240
WEB_SEARCH_RESULT_CACHE_POLICY = "query_result_urls_only_until_telegram_resolution"
DEFERRED_SEARCH_ADAPTERS = {
    SearchAdapter.TELEGRAM_POST_SEARCH.value,
    SearchAdapter.WEB_SEARCH_TME.value,
}
DEFERRED_MODEL_QUERY_EXPANSION_SOURCE = "model_query_expansion"
_TME_HOST_PATTERN = re.compile(r"^(?:https?://)?(?:www\.)?(?:t\.me|telegram\.me)/(?P<path>[^?#]+)", re.I)


@dataclass(frozen=True)
class TelegramPostSearchCapability:
    adapter: str = SearchAdapter.TELEGRAM_POST_SEARCH.value
    snippet_limit: int = POST_SEARCH_SNIPPET_LIMIT
    stores_full_message_history: bool = False
    stores_sender_identity: bool = False
    retention: str = "candidate_evidence_only"
    required_source_fields: tuple[str, ...] = ("source_post_id", "source_post_url")


@dataclass(frozen=True)
class WebSearchTmeCapability:
    adapter: str = SearchAdapter.WEB_SEARCH_TME.value
    provider: str = "unconfigured"
    per_query_cap: int = 10
    result_cache_policy: str = WEB_SEARCH_RESULT_CACHE_POLICY
    requires_telegram_resolution: bool = True


@dataclass(frozen=True)
class TelegramPostSearchHit:
    tg_id: int | None = None
    username: str | None = None
    canonical_url: str | None = None
    title: str | None = None
    source_post_id: int | None = None
    source_post_url: str | None = None
    snippet: str | None = None
    matched_terms: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class WebSearchTmeHit:
    url: str
    title: str | None = None
    snippet: str | None = None
    provider: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class TelegramPostSearchAdapter(Protocol):
    async def search_posts(
        self,
        query_text: str,
        *,
        limit: int,
        snippet_limit: int = POST_SEARCH_SNIPPET_LIMIT,
    ) -> list[TelegramPostSearchHit]:
        pass


class WebSearchTmeAdapter(Protocol):
    async def search_tme_links(self, query_text: str, *, limit: int) -> list[WebSearchTmeHit]:
        pass


def telegram_post_search_capability() -> TelegramPostSearchCapability:
    return TelegramPostSearchCapability()


def web_search_tme_capability(*, provider: str = "unconfigured", per_query_cap: int = 10) -> WebSearchTmeCapability:
    return WebSearchTmeCapability(provider=provider, per_query_cap=per_query_cap)


def telegram_post_evidence(hit: TelegramPostSearchHit, *, query_text: str) -> EntitySearchEvidence:
    terms = hit.matched_terms or _matched_terms(query_text, hit.snippet)
    metadata = _public_post_metadata(hit, terms=terms)
    return EntitySearchEvidence(
        SearchEvidenceType.POST_TEXT_MATCH.value,
        _truncate_snippet(hit.snippet),
        metadata,
    )


def normalize_web_search_tme_hit(hit: WebSearchTmeHit) -> dict[str, Any]:
    canonical_url = normalize_tme_url(hit.url)
    return {
        "canonical_url": canonical_url,
        "normalized_username": username_from_tme_url(canonical_url),
        "title": hit.title,
        "snippet": _truncate_snippet(hit.snippet),
        "provider": hit.provider,
        "requires_telegram_resolution": True,
        "evidence_type": SearchEvidenceType.WEB_RESULT.value,
        "metadata": _without_private_keys(hit.metadata),
    }


def normalize_tme_url(value: str) -> str | None:
    match = _TME_HOST_PATTERN.match(value.strip())
    if match is None:
        return None
    path = match.group("path").strip("/")
    if not path or path.startswith(("+", "joinchat/")):
        return None
    handle = path.split("/", 1)[0]
    normalized_username = normalize_telegram_username(handle)
    if normalized_username is None:
        return None
    return canonical_telegram_url(username=normalized_username)


def username_from_tme_url(value: str | None) -> str | None:
    if value is None:
        return None
    match = _TME_HOST_PATTERN.match(value)
    if match is None:
        return None
    return normalize_telegram_username(match.group("path").split("/", 1)[0])


def _public_post_metadata(hit: TelegramPostSearchHit, *, terms: tuple[str, ...]) -> dict[str, Any]:
    metadata = {
        "source_post_id": hit.source_post_id,
        "source_post_url": hit.source_post_url,
        "matched_terms": list(terms),
        "username": normalize_telegram_username(hit.username),
        "canonical_url": canonical_telegram_url(
            username=normalize_telegram_username(hit.username),
            canonical_url=hit.canonical_url,
        ),
        **_without_private_keys(hit.metadata),
    }
    return {key: value for key, value in metadata.items() if value is not None}


def _matched_terms(query_text: str, snippet: str | None) -> tuple[str, ...]:
    if not snippet:
        return ()
    snippet_folded = snippet.casefold()
    seen: set[str] = set()
    terms: list[str] = []
    for term in query_text.split():
        normalized = term.strip().casefold()
        if not normalized or normalized in seen:
            continue
        if normalized in snippet_folded:
            terms.append(normalized)
            seen.add(normalized)
    return tuple(terms)


def _truncate_snippet(value: str | None, limit: int = POST_SEARCH_SNIPPET_LIMIT) -> str | None:
    if value is None or len(value) <= limit:
        return value
    return f"{value[: limit - 3].rstrip()}..."


def _without_private_keys(metadata: dict[str, Any]) -> dict[str, Any]:
    blocked_fragments = ("sender", "author", "phone", "user_id", "tg_user_id")
    return {
        key: value
        for key, value in dict(metadata or {}).items()
        if not any(fragment in key.casefold() for fragment in blocked_fragments)
    }


__all__ = [
    "DEFERRED_MODEL_QUERY_EXPANSION_SOURCE",
    "DEFERRED_SEARCH_ADAPTERS",
    "POST_SEARCH_SNIPPET_LIMIT",
    "TelegramPostSearchAdapter",
    "TelegramPostSearchCapability",
    "TelegramPostSearchHit",
    "WebSearchTmeAdapter",
    "WebSearchTmeCapability",
    "WebSearchTmeHit",
    "normalize_tme_url",
    "normalize_web_search_tme_hit",
    "telegram_post_evidence",
    "telegram_post_search_capability",
    "username_from_tme_url",
    "web_search_tme_capability",
]
