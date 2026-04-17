from __future__ import annotations

from bot.formatting import (
    format_access_denied,
    format_accounts,
    format_bridge_recorded,
    format_bridge_status,
    format_candidate_card,
    format_candidates,
    format_collection_job,
    format_community_detail,
    format_created_brief,
    format_job_status,
    format_member_export,
    format_members,
    format_review,
    format_seed_group,
    format_seed_group_resolution,
    format_seed_groups,
    format_seed_import,
    format_start,
    format_telegram_entity_intake,
    format_telegram_entity_submission,
    format_whoami,
)


def test_format_start_lists_seed_first_controls() -> None:
    message = format_start()

    assert "/seeds" in message
    assert "/seed <seed_group_id>" in message
    assert "/candidates <seed_group_id>" in message
    assert "/community <community_id>" in message
    assert "/collect <community_id>" in message
    assert "/members <community_id>" in message
    assert "/exportmembers <community_id>" in message
    assert "/entity <intake_id>" in message
    assert "/bridge" in message
    assert "Send @username" in message
    assert "outreach" not in message.lower()
    assert "/whoami" in message


def test_format_whoami_returns_operator_allowlist_id() -> None:
    message = format_whoami(12345, username="researcher")

    assert "User ID: 12345" in message
    assert "Username: @researcher" in message
    assert "TELEGRAM_ALLOWED_USER_IDS" in message


def test_format_access_denied_includes_self_service_id() -> None:
    message = format_access_denied(12345, username="researcher")

    assert "This bot is restricted." in message
    assert "Your Telegram user ID: 12345" in message
    assert "Username: @researcher" in message


def test_format_bridge_status_reports_chat_id_and_path() -> None:
    message = format_bridge_status(
        enabled=True,
        inbox_path="data/telegram_bridge_inbox.jsonl",
        chat_id=12345,
        recent_count=2,
    )

    assert "Status: on" in message
    assert "Chat ID: 12345" in message
    assert "TELEGRAM_BRIDGE_CHAT_ID" in message


def test_format_bridge_recorded_mentions_reply_script() -> None:
    message = format_bridge_recorded({"id": "bridge-1"})

    assert "Bridge message saved." in message
    assert "bridge-1" in message
    assert "telegram_bridge_send.py" in message


def test_format_created_brief_keeps_brief_as_optional_path() -> None:
    message = format_created_brief(
        {
            "brief": {"id": "brief-1"},
            "job": {"id": "job-1", "type": "brief.process", "status": "queued"},
        }
    )

    assert "Optional brief queued." in message
    assert "Brief ID: brief-1" in message
    assert "Processing job: job-1 (brief.process)" in message


def test_format_candidates_outputs_header_for_seed_group_page() -> None:
    message = format_candidates(
        {"items": [{"community": {"id": "community-1"}}], "total": 7},
        seed_group_name="SaaS Hungary",
        offset=5,
    )

    assert "Candidate communities | SaaS Hungary (6-6 of 7)" == message


def test_format_candidate_card_outputs_evidence_summary() -> None:
    message = format_candidate_card(
        {
            "community": {
                "id": "community-1",
                "title": "Founder Circle",
                "username": "founder_circle",
                "member_count": 1200,
                "status": "candidate",
                "match_reason": "Expanded from SaaS Hungary via mention: @founder_circle",
            },
            "source_seed_count": 2,
            "evidence_count": 4,
            "evidence_types": ["manual_seed", "mention"],
        },
        index=1,
    )

    assert "1. Founder Circle" in message
    assert "https://t.me/founder_circle" in message
    assert "Evidence: seeds 2, edges 4 | manual_seed, mention" in message
    assert "score" not in message.lower()


def test_format_job_status_uses_last_error_line() -> None:
    message = format_job_status(
        {
            "id": "job-1",
            "type": "brief.process",
            "status": "failed",
            "error": "Traceback...\nBrief extraction must include at least one keyword",
        }
    )

    assert "Status: failed" in message
    assert "Brief extraction must include at least one keyword" in message
    assert "Traceback" not in message


def test_format_review_includes_collection_job_when_present() -> None:
    message = format_review(
        "approve",
        {
            "community": {
                "id": "community-1",
                "title": "Founder Circle",
                "status": "monitoring",
            },
            "job": {"id": "collection-1", "type": "collection.run", "status": "queued"},
        },
    )

    assert "Founder Circle" in message
    assert "Status: monitoring" in message
    assert "Collection job: collection-1 (collection.run)" in message


def test_format_accounts_uses_masked_phone_from_api() -> None:
    message = format_accounts(
        {
            "counts": {"available": 1, "in_use": 0, "rate_limited": 0, "banned": 0},
            "items": [{"phone": "+123*****89", "status": "available"}],
        }
    )

    assert "+123*****89 - available" in message


def test_format_seed_import_summarizes_groups_and_errors() -> None:
    message = format_seed_import(
        {
            "imported": 2,
            "updated": 1,
            "groups": [
                {
                    "id": "group-1",
                    "name": "SaaS Hungary",
                    "imported": 2,
                    "updated": 1,
                }
            ],
            "errors": [{"row_number": 4, "message": "Invalid Telegram public username"}],
        }
    )

    assert "Imported: 2" in message
    assert "SaaS Hungary" in message
    assert "Open: /seed group-1" in message
    assert "Row 4" in message


def test_format_seed_groups_mentions_card_based_navigation() -> None:
    message = format_seed_groups(
        {
            "total": 1,
            "items": [
                {
                    "id": "group-1",
                    "name": "SaaS Hungary",
                    "seed_count": 12,
                    "resolved_count": 3,
                    "unresolved_count": 8,
                    "failed_count": 1,
                }
            ],
        }
    )

    assert "Seed groups (1)" in message
    assert "Open any group card below" in message


def test_format_seed_group_lists_next_actions() -> None:
    message = format_seed_group(
        {
            "group": {
                "id": "group-1",
                "name": "SaaS Hungary",
                "seed_count": 12,
                "resolved_count": 3,
                "unresolved_count": 8,
                "failed_count": 1,
            }
        }
    )

    assert "Channels: /channels group-1" in message
    assert "Candidates: /candidates group-1" in message
    assert "Resolve: /resolveseeds group-1" in message


def test_format_seed_group_resolution_reports_job() -> None:
    message = format_seed_group_resolution(
        {"job": {"id": "resolve-1", "type": "seed.resolve", "status": "queued"}}
    )

    assert "Seed group resolution queued." in message
    assert "resolve-1 (seed.resolve)" in message
    assert "/job resolve-1" in message


def test_format_telegram_entity_submission_reports_job() -> None:
    message = format_telegram_entity_submission(
        {
            "intake": {
                "id": "intake-1",
                "telegram_url": "https://t.me/example",
            },
            "job": {
                "id": "entity-job-1",
                "type": "telegram_entity.resolve",
                "status": "queued",
            },
        }
    )

    assert "Telegram entity classification queued." in message
    assert "https://t.me/example" in message
    assert "entity-job-1 (telegram_entity.resolve)" in message
    assert "/entity intake-1" in message


def test_format_telegram_entity_intake_links_community_result() -> None:
    message = format_telegram_entity_intake(
        {
            "id": "intake-1",
            "telegram_url": "https://t.me/example",
            "status": "resolved",
            "entity_type": "channel",
            "community_id": "community-1",
            "user_id": None,
        }
    )

    assert "Type: channel" in message
    assert "Community: /community community-1" in message


def test_format_collection_job_reports_manual_trigger() -> None:
    message = format_collection_job(
        {"job": {"id": "collect-1", "type": "collection.run", "status": "queued"}},
        community_title="Founder Circle",
    )

    assert "Founder Circle" in message
    assert "collect-1 (collection.run)" in message


def test_format_members_outputs_safe_member_fields() -> None:
    message = format_members(
        {
            "items": [
                {
                    "tg_user_id": 123,
                    "username": "public_user",
                    "first_name": "Public",
                    "membership_status": "member",
                    "activity_status": "inactive",
                    "first_seen_at": "2026-04-15T10:00:00Z",
                    "last_updated_at": "2026-04-15T11:00:00Z",
                    "last_active_at": None,
                }
            ],
            "total": 1,
        },
        community_title="Founder Circle",
    )

    assert "Visible members | Founder Circle" in message
    assert "Telegram user ID: 123" in message
    assert "Public username: @public_user" in message
    assert "phone" not in message.lower()
    assert "score" not in message.lower()


def test_format_member_export_reports_count() -> None:
    message = format_member_export({"items": [{}, {}], "total": 2}, community_title="Founder Circle")

    assert "Exported 2 visible members for Founder Circle." == message


def test_format_community_detail_includes_snapshot_run_and_analysis() -> None:
    message = format_community_detail(
        {
            "community": {
                "id": "community-1",
                "title": "Founder Circle",
                "username": "founder_circle",
                "status": "monitoring",
                "source": "manual",
                "member_count": 1200,
                "match_reason": "Imported manual seed: SaaS Hungary",
            },
            "latest_snapshot": {
                "collected_at": "2026-04-15T10:00:00Z",
                "member_count": 1200,
                "message_count_7d": 45,
            },
            "latest_analysis": {
                "analyzed_at": "2026-04-15T11:00:00Z",
                "summary": "Active Hungarian founder community.",
                "dominant_themes": ["saas", "growth"],
                "activity_level": "high",
                "centrality": "core",
                "relevance_notes": "Strong fit for the seed context.",
            },
        },
        {
            "items": [
                {
                    "status": "completed",
                    "analysis_status": "skipped",
                    "window_days": 90,
                    "members_seen": 80,
                    "messages_seen": 0,
                }
            ]
        },
    )

    assert "Founder Circle" in message
    assert "Latest snapshot" in message
    assert "Latest collection run" in message
    assert "Latest analysis" in message
