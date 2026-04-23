from __future__ import annotations

from backend.services.search_deferred_surfaces import (
    POST_SEARCH_SNIPPET_LIMIT,
    TelegramPostSearchHit,
    WebSearchTmeHit,
    normalize_tme_url,
    normalize_web_search_tme_hit,
    telegram_post_evidence,
    telegram_post_search_capability,
    web_search_tme_capability,
)


def test_telegram_post_search_evidence_caps_snippet_and_omits_sender_identity() -> None:
    snippet = "Hungarian SaaS founders " + ("discuss product-led growth " * 20)
    evidence = telegram_post_evidence(
        TelegramPostSearchHit(
            username="HuSaaS",
            source_post_id=123,
            source_post_url="https://t.me/husaas/123",
            snippet=snippet,
            metadata={
                "sender_id": 42,
                "sender_username": "person",
                "phone": "+123",
                "public_metric": "views:10",
            },
        ),
        query_text="hungarian saas founders",
    )

    assert evidence.evidence_type == "post_text_match"
    assert evidence.value is not None
    assert len(evidence.value) <= POST_SEARCH_SNIPPET_LIMIT
    assert evidence.metadata["source_post_id"] == 123
    assert evidence.metadata["source_post_url"] == "https://t.me/husaas/123"
    assert evidence.metadata["matched_terms"] == ["hungarian", "saas", "founders"]
    assert evidence.metadata["public_metric"] == "views:10"
    assert "sender_id" not in evidence.metadata
    assert "sender_username" not in evidence.metadata
    assert "phone" not in evidence.metadata


def test_web_search_tme_hit_normalizes_public_links_and_requires_resolution() -> None:
    normalized = normalize_web_search_tme_hit(
        WebSearchTmeHit(
            url="http://t.me/HuSaaS/987",
            title="Hungarian SaaS",
            snippet="A public web result",
            provider="fixture",
            metadata={"author": "hidden", "result_rank": 1},
        )
    )

    assert normalized["canonical_url"] == "https://t.me/husaas"
    assert normalized["normalized_username"] == "husaas"
    assert normalized["requires_telegram_resolution"] is True
    assert normalized["metadata"] == {"result_rank": 1}
    assert normalize_tme_url("https://t.me/+privateinvite") is None


def test_deferred_surface_capabilities_document_retention_and_provider_policy() -> None:
    post_capability = telegram_post_search_capability()
    web_capability = web_search_tme_capability(provider="fixture", per_query_cap=7)

    assert post_capability.stores_full_message_history is False
    assert post_capability.stores_sender_identity is False
    assert post_capability.required_source_fields == ("source_post_id", "source_post_url")
    assert web_capability.provider == "fixture"
    assert web_capability.per_query_cap == 7
    assert web_capability.requires_telegram_resolution is True
