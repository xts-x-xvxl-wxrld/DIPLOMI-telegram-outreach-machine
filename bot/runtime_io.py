# ruff: noqa: F401,F403,F405,E402
from __future__ import annotations

from .runtime_base import *


async def _callback_reply(update: Any, text: str, reply_markup: Any | None = None) -> None:
    query = update.callback_query
    if query is not None and query.message is not None:
        await query.message.reply_text(text, reply_markup=reply_markup)
        return
    await _reply(update, text, reply_markup=reply_markup)


async def _edit_callback_message(update: Any, text: str, reply_markup: Any | None = None) -> None:
    query = update.callback_query
    if query is not None:
        await query.edit_message_text(text=text, reply_markup=reply_markup)


async def _reply(update: Any, text: str, reply_markup: Any | None = None) -> None:
    if update.message is not None:
        await update.message.reply_text(text, reply_markup=reply_markup)


async def _reply_document(
    update: Any,
    *,
    document_bytes: bytes,
    file_name: str,
    caption: str,
) -> None:
    if update.message is None:
        return
    document = io.BytesIO(document_bytes)
    document.name = file_name
    await update.message.reply_document(document=document, filename=file_name, caption=caption)


async def _fetch_all_community_members(client: BotApiClient, community_id: str) -> dict[str, Any]:
    offset = 0
    total: int | None = None
    items: list[dict[str, Any]] = []
    while total is None or offset < total:
        page = await client.list_community_members(
            community_id,
            limit=MEMBER_EXPORT_PAGE_SIZE,
            offset=offset,
        )
        page_items = page.get("items") or []
        if not page_items:
            total = page.get("total", len(items))
            break
        items.extend(page_items)
        total = int(page.get("total", len(items)))
        offset += len(page_items)
    return {"items": items, "total": total if total is not None else len(items)}


def _members_csv_bytes(items: list[dict[str, Any]]) -> bytes:
    output = io.StringIO()
    fieldnames = [
        "tg_user_id",
        "username",
        "first_name",
        "membership_status",
        "activity_status",
        "first_seen_at",
        "last_updated_at",
        "last_active_at",
    ]
    writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    for item in items:
        writer.writerow({field: item.get(field) for field in fieldnames})
    return output.getvalue().encode("utf-8")


__all__ = [
    "_callback_reply",
    "_edit_callback_message",
    "_reply",
    "_reply_document",
    "_fetch_all_community_members",
    "_members_csv_bytes",
]
