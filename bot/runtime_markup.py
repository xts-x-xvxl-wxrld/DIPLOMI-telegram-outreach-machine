# ruff: noqa: F401,F403,F405,E402
from __future__ import annotations

from .runtime_base import *


def _engagement_settings_markup(
    community_id: str,
    data: dict[str, Any],
    *,
    can_manage: bool = True,
) -> Any:
    return engagement_settings_markup(
        community_id,
        allow_join=bool(data.get("allow_join")),
        allow_post=bool(data.get("allow_post")),
        can_manage=can_manage,
    )


def _engagement_target_markup(
    target_id: str,
    data: dict[str, Any],
    *,
    can_manage: bool = True,
) -> Any:
    return engagement_target_actions_markup(
        target_id,
        status=str(data.get("status") or "pending"),
        community_id=str(data["community_id"]) if data.get("community_id") else None,
        allow_join=bool(data.get("allow_join")),
        allow_detect=bool(data.get("allow_detect")),
        allow_post=bool(data.get("allow_post")),
        can_manage=can_manage,
    )


def _engagement_candidate_detail_markup(candidate_id: str, data: dict[str, Any]) -> Any:
    blocked_reason = (
        data.get("send_block_reason")
        or data.get("blocked_reason")
        or data.get("block_reason")
    )
    has_final_reply = bool(str(data.get("final_reply") or "").strip())
    return engagement_candidate_detail_markup(
        candidate_id,
        status=str(data.get("status") or "needs_review"),
        community_id=str(data["community_id"]) if data.get("community_id") else None,
        blocked=bool(blocked_reason) or str(data.get("status") or "") == "failed",
        allow_save_good_example=bool(data.get("topic_id") and has_final_reply),
        allow_create_style_rule=has_final_reply,
    )


__all__ = [
    "_engagement_settings_markup",
    "_engagement_target_markup",
    "_engagement_candidate_detail_markup",
]
