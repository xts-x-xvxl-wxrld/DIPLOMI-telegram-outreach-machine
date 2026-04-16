from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models import SeedChannel, SeedGroup

GROUP_COLUMN_ALIASES = {"group_name", "group", "seed_group", "seed_group_name", "name"}
CHANNEL_COLUMN_ALIASES = {"channel", "username", "link", "url", "telegram", "telegram_link"}
OPTIONAL_COLUMN_ALIASES = {
    "title": {"title", "label"},
    "notes": {"notes", "note", "reason"},
}
MAX_CSV_ROWS = 1000
TELEGRAM_USERNAME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]{4,31}$")


@dataclass(frozen=True)
class SeedImportError:
    row_number: int
    message: str


@dataclass
class SeedImportGroupSummary:
    id: str
    name: str
    imported: int = 0
    updated: int = 0


@dataclass
class SeedImportResult:
    imported: int = 0
    updated: int = 0
    errors: list[SeedImportError] = field(default_factory=list)
    groups: dict[str, SeedImportGroupSummary] = field(default_factory=dict)


@dataclass(frozen=True)
class NormalizedSeed:
    raw_value: str
    normalized_key: str
    username: str
    telegram_url: str


async def import_seed_csv(
    db: AsyncSession,
    csv_text: str,
    *,
    requested_by: str | None = None,
) -> SeedImportResult:
    reader, column_map = _build_reader(csv_text)
    result = SeedImportResult()

    row_count = 0
    for row_number, row in enumerate(reader, start=2):
        row_count += 1
        if row_count > MAX_CSV_ROWS:
            result.errors.append(
                SeedImportError(
                    row_number=row_number,
                    message=f"CSV import is capped at {MAX_CSV_ROWS} seed rows",
                )
            )
            break

        group_name = _cell(row, column_map["group"])
        channel_value = _cell(row, column_map["channel"])
        title = _optional_cell(row, column_map, "title")
        notes = _optional_cell(row, column_map, "notes")

        if not group_name:
            result.errors.append(SeedImportError(row_number=row_number, message="Missing group_name"))
            continue
        if not channel_value:
            result.errors.append(SeedImportError(row_number=row_number, message="Missing channel"))
            continue

        try:
            normalized_seed = normalize_telegram_seed(channel_value)
        except ValueError as exc:
            result.errors.append(SeedImportError(row_number=row_number, message=str(exc)))
            continue

        seed_group = await _get_or_create_group(db, group_name, requested_by=requested_by)
        await _upsert_channel(
            db,
            result,
            seed_group,
            normalized_seed,
            title=title,
            notes=notes,
        )

    return result


def normalize_telegram_seed(raw_value: str) -> NormalizedSeed:
    cleaned = raw_value.strip()
    if not cleaned:
        raise ValueError("Empty channel value")

    candidate = cleaned
    if candidate.startswith("@"):
        candidate = candidate[1:]
    else:
        candidate = _strip_url_prefix(candidate)
        candidate = _strip_telegram_domain(candidate)

    candidate = candidate.strip().strip("/")
    if candidate.startswith("s/"):
        candidate = candidate[2:]

    username = candidate.split("/", 1)[0].strip()
    if username.startswith("+") or username.lower() == "joinchat":
        raise ValueError("Private invite links are not supported as public seeds")
    if not TELEGRAM_USERNAME_RE.match(username):
        raise ValueError(f"Invalid Telegram public username: {cleaned}")

    normalized_username = username.lower()
    return NormalizedSeed(
        raw_value=cleaned,
        normalized_key=f"username:{normalized_username}",
        username=username,
        telegram_url=f"https://t.me/{username}",
    )


def _build_reader(csv_text: str) -> tuple[csv.DictReader[str], dict[str, str]]:
    stream = io.StringIO(csv_text.lstrip("\ufeff"))
    reader = csv.DictReader(stream)
    if not reader.fieldnames:
        raise ValueError("CSV must include a header row")

    normalized_headers = {_normalize_header(header): header for header in reader.fieldnames}
    group_column = _find_column(normalized_headers, GROUP_COLUMN_ALIASES)
    channel_column = _find_column(normalized_headers, CHANNEL_COLUMN_ALIASES)
    if group_column is None:
        raise ValueError("CSV must include a group_name column")
    if channel_column is None:
        raise ValueError("CSV must include a channel column")

    column_map = {"group": group_column, "channel": channel_column}
    for key, aliases in OPTIONAL_COLUMN_ALIASES.items():
        optional_column = _find_column(normalized_headers, aliases)
        if optional_column is not None:
            column_map[key] = optional_column
    return reader, column_map


async def _get_or_create_group(
    db: AsyncSession,
    name: str,
    *,
    requested_by: str | None,
) -> SeedGroup:
    normalized_name = _normalize_group_name(name)
    seed_group = await db.scalar(
        select(SeedGroup).where(SeedGroup.normalized_name == normalized_name)
    )
    if seed_group is not None:
        return seed_group

    seed_group = SeedGroup(
        name=name.strip(),
        normalized_name=normalized_name,
        created_by=requested_by,
    )
    db.add(seed_group)
    await db.flush()
    return seed_group


async def _upsert_channel(
    db: AsyncSession,
    result: SeedImportResult,
    seed_group: SeedGroup,
    normalized_seed: NormalizedSeed,
    *,
    title: str | None,
    notes: str | None,
) -> None:
    seed_channel = await db.scalar(
        select(SeedChannel).where(
            SeedChannel.seed_group_id == seed_group.id,
            SeedChannel.normalized_key == normalized_seed.normalized_key,
        )
    )
    group_summary = _group_summary(result, seed_group)

    if seed_channel is None:
        seed_channel = SeedChannel(
            seed_group_id=seed_group.id,
            raw_value=normalized_seed.raw_value,
            normalized_key=normalized_seed.normalized_key,
            username=normalized_seed.username,
            telegram_url=normalized_seed.telegram_url,
            title=title,
            notes=notes,
        )
        db.add(seed_channel)
        result.imported += 1
        group_summary.imported += 1
        return

    if title:
        seed_channel.title = title
    if notes:
        seed_channel.notes = notes
    seed_channel.raw_value = normalized_seed.raw_value
    seed_channel.username = normalized_seed.username
    seed_channel.telegram_url = normalized_seed.telegram_url
    result.updated += 1
    group_summary.updated += 1


def _group_summary(result: SeedImportResult, seed_group: SeedGroup) -> SeedImportGroupSummary:
    key = str(seed_group.id)
    summary = result.groups.get(key)
    if summary is None:
        summary = SeedImportGroupSummary(id=key, name=seed_group.name)
        result.groups[key] = summary
    return summary


def _find_column(normalized_headers: dict[str, str], aliases: set[str]) -> str | None:
    for alias in aliases:
        if alias in normalized_headers:
            return normalized_headers[alias]
    return None


def _normalize_header(header: str) -> str:
    return header.strip().lower().replace(" ", "_").replace("-", "_")


def _normalize_group_name(name: str) -> str:
    return " ".join(name.strip().split()).casefold()


def _cell(row: dict[str, str | None], column_name: str) -> str:
    value = row.get(column_name)
    if value is None:
        return ""
    return " ".join(value.strip().split())


def _optional_cell(row: dict[str, str | None], column_map: dict[str, str], key: str) -> str | None:
    column_name = column_map.get(key)
    if column_name is None:
        return None
    value = _cell(row, column_name)
    return value or None


def _strip_url_prefix(value: str) -> str:
    lowered = value.lower()
    for prefix in ("https://", "http://"):
        if lowered.startswith(prefix):
            return value[len(prefix) :]
    return value


def _strip_telegram_domain(value: str) -> str:
    lowered = value.lower()
    for domain in ("www.t.me/", "t.me/", "telegram.me/"):
        if lowered.startswith(domain):
            return value[len(domain) :]
    return value
