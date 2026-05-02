from __future__ import annotations

from typing import Any


TOPIC_BRIEF_WIZARD_RULE_NAME = "Draft instruction wizard"
_TOPIC_BRIEF_WIZARD_RULE_NAME_KEY = TOPIC_BRIEF_WIZARD_RULE_NAME.casefold()


def _split_topic_brief_style_rule(rule_text: str) -> tuple[str, str]:
    normalized = rule_text.strip()
    if not normalized:
        return "", ""
    voice_prefix = "Voice:"
    avoid_prefix = "Avoid:"
    if voice_prefix in normalized and avoid_prefix in normalized:
        voice_text = normalized.split(voice_prefix, 1)[1].split(avoid_prefix, 1)[0].strip()
        avoid_text = normalized.split(avoid_prefix, 1)[1].strip()
        return voice_text, avoid_text
    return normalized, ""


def _topic_brief_rule_text(style_guidance: str, avoid_rules: str) -> str:
    sections: list[str] = []
    voice = style_guidance.strip()
    avoid = avoid_rules.strip()
    if voice:
        sections.append(f"Voice:\n{voice}")
    if avoid:
        sections.append(f"Avoid:\n{avoid}")
    return "\n\n".join(sections)


def _topic_brief_has_guidance(style_guidance: str, avoid_rules: str) -> bool:
    return bool(_topic_brief_rule_text(style_guidance, avoid_rules))


async def _find_topic_brief_style_rule(client: Any, topic_id: str) -> dict[str, Any] | None:
    data = await client.list_engagement_style_rules(
        scope_type="topic",
        scope_id=topic_id,
        limit=20,
        offset=0,
    )
    items = data.get("items") or []
    for item in items:
        if str(item.get("name") or "").casefold() == _TOPIC_BRIEF_WIZARD_RULE_NAME_KEY:
            return item
    return items[0] if items else None


def _topic_brief_selection_state(style_rule: dict[str, Any] | None) -> dict[str, Any]:
    if not style_rule:
        return {}
    name = str(style_rule.get("name") or TOPIC_BRIEF_WIZARD_RULE_NAME).strip() or TOPIC_BRIEF_WIZARD_RULE_NAME
    mode = "wizard" if name.casefold() == _TOPIC_BRIEF_WIZARD_RULE_NAME_KEY else "existing"
    return {
        "style_rule_id": str(style_rule.get("id") or "") or None,
        "style_rule_name": name,
        "style_rule_target_mode": mode,
        "style_rule_scope_type": str(style_rule.get("scope_type") or "topic"),
        "style_rule_scope_id": str(style_rule.get("scope_id") or "") or None,
    }


def _ensure_topic_brief_style_target(
    state: dict[str, Any],
    *,
    topic_id: str | None,
    community_id: str | None,
) -> dict[str, Any]:
    updated = dict(state)
    style_guidance = str(updated.get("style_guidance") or "")
    avoid_rules = str(updated.get("avoid_rules") or "")
    if not _topic_brief_has_guidance(style_guidance, avoid_rules):
        return updated

    scope_type = str(updated.get("style_rule_scope_type") or "").strip() or "topic"
    target_mode = str(updated.get("style_rule_target_mode") or "").strip() or "wizard"
    if target_mode not in {"wizard", "existing"}:
        target_mode = "wizard"
    if scope_type not in {"topic", "community"}:
        scope_type = "topic"

    updated["style_rule_target_mode"] = target_mode
    updated["style_rule_scope_type"] = scope_type
    if scope_type == "community" and community_id:
        updated["style_rule_scope_id"] = community_id
    elif scope_type == "topic" and topic_id:
        updated["style_rule_scope_id"] = topic_id

    if target_mode == "wizard":
        updated["style_rule_id"] = None
        updated["style_rule_name"] = TOPIC_BRIEF_WIZARD_RULE_NAME
    else:
        existing_name = str(updated.get("style_rule_name") or "").strip()
        if not existing_name:
            updated["style_rule_name"] = TOPIC_BRIEF_WIZARD_RULE_NAME
    return updated


def _topic_brief_style_target_summary(payload: dict[str, Any]) -> str | None:
    style_guidance = str(payload.get("style_guidance") or "")
    avoid_rules = str(payload.get("avoid_rules") or "")
    if not _topic_brief_has_guidance(style_guidance, avoid_rules):
        return None

    scope_type = str(payload.get("style_rule_scope_type") or "topic")
    target_mode = str(payload.get("style_rule_target_mode") or "wizard")
    name = str(payload.get("style_rule_name") or TOPIC_BRIEF_WIZARD_RULE_NAME).strip() or TOPIC_BRIEF_WIZARD_RULE_NAME
    scope_label = "community" if scope_type == "community" else "topic"
    if target_mode == "existing":
        return f"existing {scope_label} rule: {name}"
    return f"{scope_label} rule: {TOPIC_BRIEF_WIZARD_RULE_NAME}"


async def _load_topic_brief_style_targets(
    client: Any,
    *,
    topic_id: str | None,
    community_id: str | None,
) -> list[dict[str, Any]]:
    targets: list[dict[str, Any]] = [
        {
            "target_mode": "wizard",
            "scope_type": "topic",
            "scope_id": topic_id,
            "style_rule_id": None,
            "style_rule_name": TOPIC_BRIEF_WIZARD_RULE_NAME,
            "label": "Topic rule",
            "callback": ("scope", "topic"),
        }
    ]
    if community_id:
        targets.append(
            {
                "target_mode": "wizard",
                "scope_type": "community",
                "scope_id": community_id,
                "style_rule_id": None,
                "style_rule_name": TOPIC_BRIEF_WIZARD_RULE_NAME,
                "label": "Community rule",
                "callback": ("scope", "community"),
            }
        )
    targets.extend(
        await _topic_brief_existing_style_targets(
            client,
            topic_id=topic_id,
            community_id=community_id,
        )
    )
    return targets


async def _topic_brief_existing_style_targets(
    client: Any,
    *,
    topic_id: str | None,
    community_id: str | None,
) -> list[dict[str, Any]]:
    targets: list[dict[str, Any]] = []
    seen_rule_ids: set[str] = set()
    for scope_type, scope_id, prefix in (
        ("topic", topic_id, "Use topic rule"),
        ("community", community_id, "Use community rule"),
    ):
        if not scope_id:
            continue
        data = await client.list_engagement_style_rules(
            scope_type=scope_type,
            scope_id=scope_id,
            limit=10,
            offset=0,
        )
        for item in data.get("items") or []:
            rule_id = str(item.get("id") or "").strip()
            if not rule_id or rule_id in seen_rule_ids:
                continue
            seen_rule_ids.add(rule_id)
            name = str(item.get("name") or "").strip() or "Untitled rule"
            if name.casefold() == _TOPIC_BRIEF_WIZARD_RULE_NAME_KEY:
                continue
            targets.append(
                {
                    "target_mode": "existing",
                    "scope_type": scope_type,
                    "scope_id": str(item.get("scope_id") or "") or None,
                    "style_rule_id": rule_id,
                    "style_rule_name": name,
                    "label": f"{prefix}: {name}",
                    "callback": ("attach", rule_id),
                }
            )
    return targets


def _apply_topic_brief_style_target(
    state: dict[str, Any],
    target: dict[str, Any],
) -> dict[str, Any]:
    updated = dict(state)
    updated["style_rule_target_mode"] = target.get("target_mode") or "wizard"
    updated["style_rule_scope_type"] = target.get("scope_type") or "topic"
    updated["style_rule_scope_id"] = target.get("scope_id")
    updated["style_rule_id"] = target.get("style_rule_id")
    updated["style_rule_name"] = target.get("style_rule_name") or TOPIC_BRIEF_WIZARD_RULE_NAME
    return updated


async def _upsert_topic_brief_style_rule(
    client: Any,
    *,
    topic_id: str,
    style_guidance: str,
    avoid_rules: str,
    reviewer: str,
    operator_user_id: int | None,
    target_mode: str = "wizard",
    scope_type: str = "topic",
    scope_id: str | None = None,
    style_rule_id: str | None = None,
) -> None:
    rule_text = _topic_brief_rule_text(style_guidance, avoid_rules)
    if not rule_text:
        return

    if target_mode == "existing" and style_rule_id:
        await client.update_engagement_style_rule(
            style_rule_id,
            rule_text=rule_text,
            updated_by=reviewer,
            operator_user_id=operator_user_id,
        )
        return

    resolved_scope_type = scope_type if scope_type in {"topic", "community"} else "topic"
    resolved_scope_id = topic_id if resolved_scope_type == "topic" else scope_id
    if resolved_scope_type != "topic" and not resolved_scope_id:
        resolved_scope_type = "topic"
        resolved_scope_id = topic_id

    existing_rule = None
    data = await client.list_engagement_style_rules(
        scope_type=resolved_scope_type,
        scope_id=resolved_scope_id,
        limit=20,
        offset=0,
    )
    for item in data.get("items") or []:
        if str(item.get("name") or "").casefold() == _TOPIC_BRIEF_WIZARD_RULE_NAME_KEY:
            existing_rule = item
            break

    if existing_rule is not None:
        await client.update_engagement_style_rule(
            str(existing_rule.get("id") or ""),
            name=TOPIC_BRIEF_WIZARD_RULE_NAME,
            rule_text=rule_text,
            updated_by=reviewer,
            operator_user_id=operator_user_id,
        )
        return

    await client.create_engagement_style_rule(
        scope_type=resolved_scope_type,
        scope_id=resolved_scope_id,
        name=TOPIC_BRIEF_WIZARD_RULE_NAME,
        priority=150,
        rule_text=rule_text,
        created_by=reviewer,
        operator_user_id=operator_user_id,
    )
