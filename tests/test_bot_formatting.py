from __future__ import annotations

from bot.formatting import (
    format_access_denied,
    format_accounts,
    format_candidate_card,
    format_candidates,
    format_community_detail,
    format_created_brief,
    format_engagement_candidate_card,
    format_engagement_candidate_review,
    format_engagement_candidate_revisions,
    format_engagement_candidates,
    format_engagement_action_card,
    format_engagement_actions,
    format_engagement_account_assignment_confirmation,
    format_engagement_home,
    format_engagement_job_response,
    format_engagement_settings,
    format_engagement_settings_lookup,
    format_engagement_semantic_rollout,
    format_engagement_style_rule_card,
    format_engagement_style_rules,
    format_engagement_target_card,
    format_engagement_target_approval_confirmation,
    format_engagement_target_mutation,
    format_engagement_target_permission_confirmation,
    format_engagement_topic_card,
    format_engagement_topics,
    format_job_status,
    format_member_export,
    format_members,
    format_review,
    format_seed_group,
    format_seed_group_resolution,
    format_seed_groups,
    format_seed_import,
    format_snapshot_job,
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
    assert "/snapshot <community_id>" in message
    assert "/members <community_id>" in message
    assert "/exportmembers <community_id>" in message
    assert "/engagement_candidates" in message
    assert "/entity <intake_id>" in message
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

    assert message.endswith("Candidate communities | SaaS Hungary (6-6 of 7)")


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


def test_format_review_includes_snapshot_job_when_present() -> None:
    message = format_review(
        "approve",
        {
            "community": {
                "id": "community-1",
                "title": "Founder Circle",
                "status": "monitoring",
            },
            "job": {"id": "snapshot-1", "type": "community.snapshot", "status": "queued"},
        },
    )

    assert "Founder Circle" in message
    assert "Status: monitoring" in message
    assert "Snapshot job: snapshot-1 (community.snapshot)" in message


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


def test_format_snapshot_job_reports_manual_trigger() -> None:
    message = format_snapshot_job(
        {"job": {"id": "snapshot-1", "type": "community.snapshot", "status": "queued"}},
        community_title="Founder Circle",
    )

    assert "Founder Circle" in message
    assert "snapshot-1 (community.snapshot)" in message


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

    assert message.endswith("Exported 2 visible members for Founder Circle.")


def test_format_engagement_candidates_reports_pending_page() -> None:
    message = format_engagement_candidates({"items": [{"id": "candidate-1"}], "total": 3}, offset=0)

    assert message.endswith("Engagement replies | needs_review (1-1 of 3)")


def test_format_engagement_home_reports_operational_counts() -> None:
    message = format_engagement_home(
        {
            "pending_reply_count": 2,
            "approved_reply_count": 1,
            "failed_candidate_count": 3,
            "active_topic_count": 4,
        }
    )

    assert "Review replies: 2" in message
    assert "Approved to send: 1" in message
    assert "Settings lookup: /engagement_settings <community_id>" in message
    assert "/engagement_topics" in message
    assert "score" not in message.lower()


def test_format_engagement_settings_shows_safe_controls() -> None:
    message = format_engagement_settings(
        {
            "community_id": "community-1",
            "mode": "suggest",
            "allow_join": False,
            "allow_post": False,
            "reply_only": True,
            "require_approval": True,
            "max_posts_per_day": 1,
            "min_minutes_between_posts": 240,
            "quiet_hours_start": "22:00:00",
            "quiet_hours_end": "07:00:00",
            "assigned_account_id": "account-1",
        },
        assigned_account_label="account-1 | +123*****89",
    )

    assert "Posting posture: draft replies for review" in message
    assert "Readiness: Drafting replies" in message
    assert "Joining allowed: no" in message
    assert "Safety floor: reply-only yes, approval required yes" in message
    assert "/set_engagement community-1" in message
    assert "/set_engagement_limits community-1" in message
    assert "/set_engagement_quiet_hours community-1 <HH:MM> <HH:MM>" in message
    assert "/assign_engagement_account community-1 <telegram_account_id>" in message
    assert "Quiet hours: 22:00-07:00" in message
    assert "Engagement account: account-1 | +123*****89" in message
    assert message.index("Readiness: Drafting replies") < message.index("Community ID: community-1")
    assert "phone" not in message.lower()


def test_format_engagement_settings_lookup_points_to_button_led_lookup() -> None:
    message = format_engagement_settings_lookup(
        {"items": [{"community_id": "community-1"}], "total": 3},
        offset=1,
    )

    assert "Settings lookup (2-2 of 3)" in message
    assert "readiness, posting limits, quiet hours, and account assignment" in message
    assert "/engagement_settings <community_id>" in message


def test_format_engagement_target_card_is_compact_by_default_and_audit_friendly_in_detail() -> None:
    target = {
        "id": "target-1",
        "submitted_ref": "username:founders",
        "status": "approved",
        "community_id": "community-1",
        "community_title": "Founder Circle",
        "allow_join": True,
        "allow_detect": True,
        "allow_post": False,
    }
    message = format_engagement_target_card(target, index=1)
    detail = format_engagement_target_card(target, detail=True)

    assert "1. Founder Circle" in message
    assert "Readiness: Drafting replies" in message
    assert "Allowed: watch/draft yes, join yes, post reviewed replies no" in message
    assert "Settings: /engagement_settings community-1" in message
    assert "Target ID: target-1" not in message
    assert "Target ID: target-1" in detail
    assert "Raw permissions: allow_join=yes, allow_detect=yes, allow_post=no" in detail
    assert "/target_detect target-1" in message


def test_format_engagement_target_mutation_shows_before_after_permissions() -> None:
    message = format_engagement_target_mutation(
        action="post enabled",
        before={
            "id": "target-1",
            "submitted_ref": "username:founders",
            "status": "approved",
            "allow_join": True,
            "allow_detect": True,
            "allow_post": False,
        },
        after={
            "id": "target-1",
            "submitted_ref": "username:founders",
            "status": "approved",
            "allow_join": True,
            "allow_detect": True,
            "allow_post": True,
        },
    )

    assert "Before: status=approved, join=yes, detect=yes, post=no" in message
    assert "After: status=approved, join=yes, detect=yes, post=yes" in message
    assert "Readiness: Ready to post with review" in message


def test_format_target_confirmation_cards_show_before_after_state() -> None:
    before = {
        "id": "target-1",
        "submitted_ref": "username:founders",
        "status": "resolved",
        "community_id": "community-1",
        "community_title": "Founder Circle",
        "allow_join": False,
        "allow_detect": False,
        "allow_post": False,
    }
    approval = format_engagement_target_approval_confirmation(
        before=before,
        after={
            **before,
            "status": "approved",
            "allow_join": True,
            "allow_detect": True,
            "allow_post": True,
        },
    )
    posting = format_engagement_target_permission_confirmation(
        permission="post",
        before={**before, "status": "approved", "allow_detect": True},
        after={
            **before,
            "status": "approved",
            "allow_detect": True,
            "allow_post": True,
        },
    )

    assert "Confirm target approval" in approval
    assert "Before: status=resolved, join=no, detect=no, post=no" in approval
    assert "After: status=approved, join=yes, detect=yes, post=yes" in approval
    assert "Confirm target post permission change" in posting
    assert "After: status=approved, join=no, detect=yes, post=yes" in posting


def test_format_account_assignment_confirmation_uses_masked_labels() -> None:
    message = format_engagement_account_assignment_confirmation(
        {"community_id": "community-1"},
        before_account_label="none",
        after_account_label="account-1 | +123*****89",
    )

    assert "Confirm engagement account assignment" in message
    assert "Before: none" in message
    assert "After: account-1 | +123*****89" in message
    assert "+123456789" not in message
    assert "phone" not in message.lower()


def test_format_engagement_topics_and_card_truncate_guidance() -> None:
    message = format_engagement_topics(
        {
            "items": [{"id": "topic-1", "active": True}, {"id": "topic-2", "active": False}],
            "total": 2,
        }
    )
    card = format_engagement_topic_card(
        {
            "id": "topic-1",
            "name": "Open CRM",
            "description": "Discussion of CRM tools",
            "stance_guidance": "Be factual. " * 80,
            "trigger_keywords": ["crm", "sales pipeline"],
            "negative_keywords": ["hiring"],
            "active": True,
        },
        index=1,
    )

    assert message.endswith("Engagement topics (1-2 of 2) | active 1")
    assert "1. Open CRM" in card
    assert "Notice: crm, sales pipeline" in card
    assert "Guidance: " in card
    assert len(card) < 700


def test_format_engagement_topic_card_labels_good_and_bad_examples() -> None:
    card = format_engagement_topic_card(
        {
            "id": "topic-1",
            "name": "Open CRM",
            "stance_guidance": "Be factual.",
            "trigger_keywords": ["crm"],
            "negative_keywords": ["jobs"],
            "example_good_replies": ["Compare export paths first."],
            "example_bad_replies": ["Buy our tool now."],
            "active": True,
        }
    )

    assert "Good examples: #1 Compare export paths first." in card
    assert "Bad examples (avoid copying): #1 Buy our tool now." in card
    assert "/topic_remove_example topic-1 good <index>" in card
    assert "/topic_remove_example topic-1 bad <index>" in card


def test_format_engagement_style_rules_and_card_include_scope_priority_and_commands() -> None:
    message = format_engagement_style_rules(
        {
            "items": [{"id": "rule-1"}],
            "total": 1,
            "scope_type": "community",
            "scope_id": "community-1",
        }
    )
    card = format_engagement_style_rule_card(
        {
            "id": "rule-1",
            "scope_type": "community",
            "scope_id": "community-1",
            "name": "Keep it brief",
            "rule_text": "Keep replies under three sentences.",
            "active": True,
            "priority": 50,
        }
    )

    assert message.endswith("Engagement style rules (1-1 of 1) | community community-1")
    assert "Scope: community community-1" in card
    assert "priority 50" in card
    assert "/engagement_style_rule rule-1" in card
    assert "/edit_style_rule rule-1" in card
    assert "/toggle_style_rule rule-1 off" in card


def test_format_default_topic_and_style_cards_keep_ids_for_detail_views() -> None:
    topic = {
        "id": "topic-1",
        "name": "Open CRM",
        "stance_guidance": "Be factual.",
        "trigger_keywords": ["crm"],
        "active": True,
    }
    rule = {
        "id": "rule-1",
        "scope_type": "community",
        "scope_id": "community-1",
        "name": "Keep it brief",
        "rule_text": "Keep replies under three sentences.",
        "active": True,
        "priority": 50,
    }

    assert "Topic ID: topic-1" not in format_engagement_topic_card(topic)
    assert "Topic ID: topic-1" in format_engagement_topic_card(topic, detail=True)
    assert "Rule ID: rule-1" not in format_engagement_style_rule_card(rule)
    assert "Rule ID: rule-1" in format_engagement_style_rule_card(rule, detail=True)


def test_readiness_uses_backend_block_reasons_without_inventing_detail() -> None:
    settings = format_engagement_settings(
        {
            "community_id": "community-1",
            "mode": "require_approval",
            "allow_join": True,
            "allow_post": True,
            "reply_only": True,
            "require_approval": True,
            "max_posts_per_day": 1,
            "min_minutes_between_posts": 240,
            "quiet_hours_active": True,
        }
    )
    target = format_engagement_target_card(
        {
            "id": "target-1",
            "submitted_ref": "username:founders",
            "status": "approved",
            "allow_join": True,
            "allow_detect": True,
            "allow_post": True,
            "posting_block_reason": "no joined engagement account",
        }
    )

    assert "Readiness: Blocked: quiet hours active" in settings
    assert "Readiness: Blocked: no joined engagement account" in target


def test_format_engagement_job_response_reports_refresh_command() -> None:
    message = format_engagement_job_response(
        {"job": {"id": "send-job", "type": "engagement.send", "status": "queued"}},
        label="Reply send",
        candidate_id="candidate-1",
    )

    assert "Reply send queued." in message
    assert "send-job (engagement.send)" in message
    assert "/job send-job" in message
    assert "Candidate ID: candidate-1" in message


def test_format_engagement_actions_and_card_keep_audit_safe() -> None:
    message = format_engagement_actions({"items": [{"id": "action-1"}], "total": 4}, offset=2)
    card = format_engagement_action_card(
        {
            "id": "action-1",
            "candidate_id": "candidate-1",
            "community_id": "community-1",
            "telegram_account_id": "account-1",
            "action_type": "reply",
            "status": "failed",
            "outbound_text": "Approved public reply " * 30,
            "reply_to_tg_message_id": 123,
            "sent_tg_message_id": None,
            "error_message": "Flood wait " * 40,
            "created_at": "2026-04-19T12:00:00Z",
        },
        index=1,
    )

    assert message.endswith("Engagement audit (3-3 of 4)")
    assert "1. reply | failed" in card
    assert "Candidate ID: candidate-1" in card
    assert "Reply to message: 123" in card
    assert "Flood wait" in card
    assert "phone" not in card.lower()
    assert "sender" not in card.lower()


def test_format_engagement_candidate_card_keeps_review_context() -> None:
    message = format_engagement_candidate_card(
        {
            "id": "candidate-1",
            "community_title": "Founder Circle",
            "topic_name": "Open-source CRM",
            "status": "needs_review",
            "moment_strength": "good",
            "timeliness": "fresh",
            "reply_value": "practical_tip",
            "review_deadline_at": "2026-04-19T13:00:00+00:00",
            "reply_deadline_at": "2026-04-19T13:30:00+00:00",
            "source_excerpt": "The group is comparing CRM tools.",
            "detected_reason": "The group is discussing alternatives.",
            "suggested_reply": "Compare ownership, integrations, and exit paths first.",
            "risk_notes": ["Keep it non-salesy."],
        },
        index=1,
    )

    assert "1. Founder Circle" in message
    assert "Readiness: Needs review" in message
    assert "Topic: Open-source CRM" in message
    assert "Freshness: fresh | moment good | value practical_tip" in message
    assert "Deadlines: review 2026-04-19T13:00:00+00:00 | reply 2026-04-19T13:30:00+00:00" in message
    assert "Source: The group is comparing CRM tools." in message
    assert "Suggested reply: Compare ownership" in message
    assert "/approve_reply candidate-1" in message
    assert "/send_reply candidate-1" not in message
    assert "score" not in message.lower()


def test_format_engagement_candidate_card_uses_state_relevant_actions() -> None:
    message = format_engagement_candidate_card(
        {
            "id": "candidate-1",
            "community_title": "Founder Circle",
            "topic_name": "Open-source CRM",
            "status": "approved",
            "source_excerpt": "The group is comparing CRM tools.",
            "detected_reason": "The group is discussing alternatives.",
            "suggested_reply": "Compare ownership, integrations, and exit paths first.",
        }
    )

    assert "Readiness: Approved, ready to send" in message
    assert "Send: /send_reply candidate-1" in message
    assert "Approve: /approve_reply candidate-1" not in message


def test_format_engagement_candidate_card_shows_retry_without_send_for_failed() -> None:
    message = format_engagement_candidate_card(
        {
            "id": "candidate-1",
            "community_title": "Founder Circle",
            "topic_name": "Open-source CRM",
            "status": "failed",
            "source_excerpt": "The group is comparing CRM tools.",
            "detected_reason": "The group is discussing alternatives.",
            "suggested_reply": "Compare ownership, integrations, and exit paths first.",
        }
    )

    assert "Readiness: Failed, retry may be available" in message
    assert "Retry: /retry_candidate candidate-1" in message
    assert "Send: /send_reply candidate-1" not in message


def test_format_engagement_candidate_review_reports_audit_fields() -> None:
    message = format_engagement_candidate_review(
        "approve",
        {
            "id": "candidate-1",
            "community_title": "Founder Circle",
            "status": "approved",
            "reviewed_by": "telegram:123",
        },
    )

    assert "Decision: approve" in message
    assert "Status: approved" in message
    assert "Reviewed by: telegram:123" in message
    assert "Queue send: /send_reply candidate-1" in message


def test_format_engagement_candidate_revisions_caps_history_and_keeps_editor_metadata() -> None:
    message = format_engagement_candidate_revisions(
        {
            "items": [
                {
                    "id": "revision-1",
                    "candidate_id": "candidate-1",
                    "revision_number": 1,
                    "reply_text": "Edited final reply.",
                    "edited_by": "telegram:123",
                    "edit_reason": "manual edit",
                    "created_at": "2026-04-21T10:00:00Z",
                }
            ],
            "total": 1,
        },
        candidate_id="candidate-1",
    )

    assert "Candidate revisions (1)" in message
    assert "Revision 1" in message
    assert "Edited by: telegram:123" in message
    assert "Reply: Edited final reply." in message


def test_format_engagement_semantic_rollout_is_aggregate_only() -> None:
    message = format_engagement_semantic_rollout(
        {
            "window_days": 14,
            "total_semantic_candidates": 3,
            "reviewed_semantic_candidates": 2,
            "approved": 1,
            "rejected": 1,
            "pending": 1,
            "expired": 0,
            "approval_rate": 0.5,
            "bands": [
                {
                    "label": "0.80-0.89",
                    "total": 1,
                    "approved": 1,
                    "rejected": 0,
                    "pending": 0,
                    "expired": 0,
                    "approval_rate": 1.0,
                },
                {
                    "label": "0.70-0.79",
                    "total": 1,
                    "approved": 0,
                    "rejected": 1,
                    "pending": 0,
                    "expired": 0,
                    "approval_rate": 0.0,
                },
            ],
        }
    )

    assert "Semantic rollout | 14 days" in message
    assert "approved 1, rejected 1, pending 1" in message
    assert "0.80-0.89: 1" in message
    assert "approval 100%" in message
    assert "Candidate ID" not in message
    assert "Source:" not in message
    assert "sender" not in message.lower()
    assert "score" not in message.lower()


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
    assert "Latest snapshot run" in message
    assert "Latest analysis" in message
