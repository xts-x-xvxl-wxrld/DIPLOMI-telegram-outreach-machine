from __future__ import annotations

import argparse
import csv
import io
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.services.seed_import import normalize_telegram_seed  # noqa: E402


@dataclass(frozen=True)
class SeedCsvRow:
    group_name: str
    channel: str
    title: str
    notes: str


class SeedCsvError(ValueError):
    def __init__(self, messages: Sequence[str]) -> None:
        super().__init__("\n".join(messages))
        self.messages = list(messages)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a bot-ready seed CSV from Telegram usernames or public links.",
        epilog=(
            "Examples:\n"
            "  python scripts/make_seed_csv.py --group VUZ '@synergyunivers' -o wiki/seed_examples/VUZ.csv\n"
            "  Get-Content seeds.txt | python scripts/make_seed_csv.py --group \"Hungarian SaaS\" -o seeds.csv"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--group", required=True, help="Seed group name to write on every row.")
    parser.add_argument(
        "-i",
        "--input",
        type=Path,
        help="Text file with one Telegram username or public link per line.",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="Output CSV path. Defaults to stdout.",
    )
    parser.add_argument("--notes", default="", help="Optional notes to write on every row.")
    parser.add_argument(
        "--blank-title",
        action="store_true",
        help="Leave title blank instead of using the parsed Telegram username.",
    )
    parser.add_argument(
        "seeds",
        nargs="*",
        help="Telegram usernames or public links. If omitted, reads --input or stdin.",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        rows = build_rows(
            group_name=args.group,
            seed_lines=collect_seed_lines(args),
            notes=args.notes,
            title_from_username=not args.blank_title,
        )
        csv_text = render_csv(rows)
        if args.output is None:
            print(csv_text, end="")
        else:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(csv_text, encoding="utf-8", newline="")
    except SeedCsvError as exc:
        for message in exc.messages:
            print(f"error: {message}", file=sys.stderr)
        return 1
    return 0


def collect_seed_lines(args: argparse.Namespace) -> list[str]:
    lines: list[str] = []
    if args.input is not None:
        lines.extend(args.input.read_text(encoding="utf-8-sig").splitlines())
    if args.seeds:
        lines.extend(args.seeds)
    if not lines and not sys.stdin.isatty():
        lines.extend(sys.stdin.read().splitlines())
    if not lines:
        raise SeedCsvError(["provide at least one seed via arguments, --input, or stdin"])
    return lines


def build_rows(
    *,
    group_name: str,
    seed_lines: Sequence[str],
    notes: str = "",
    title_from_username: bool = True,
) -> list[SeedCsvRow]:
    clean_group_name = " ".join(group_name.strip().split())
    if not clean_group_name:
        raise SeedCsvError(["--group must not be empty"])

    rows: list[SeedCsvRow] = []
    errors: list[str] = []
    seen: set[str] = set()

    for line_number, seed_line in enumerate(seed_lines, start=1):
        raw_seed = clean_seed_line(seed_line)
        if not raw_seed:
            continue

        try:
            normalized_seed = normalize_telegram_seed(raw_seed)
        except ValueError as exc:
            errors.append(f"line {line_number}: {exc}")
            continue

        if normalized_seed.normalized_key in seen:
            continue
        seen.add(normalized_seed.normalized_key)
        rows.append(
            SeedCsvRow(
                group_name=clean_group_name,
                channel=normalized_seed.telegram_url,
                title=normalized_seed.username if title_from_username else "",
                notes=notes.strip(),
            )
        )

    if errors:
        raise SeedCsvError(errors)
    if not rows:
        raise SeedCsvError(["no valid seeds found"])
    return rows


def clean_seed_line(value: str) -> str:
    cleaned = value.strip().lstrip("\ufeff")
    if not cleaned or cleaned.startswith("#"):
        return ""
    return cleaned


def render_csv(rows: Sequence[SeedCsvRow]) -> str:
    output = io.StringIO(newline="")
    writer = csv.DictWriter(
        output,
        fieldnames=["group_name", "channel", "title", "notes"],
        lineterminator="\n",
    )
    writer.writeheader()
    for row in rows:
        writer.writerow(
            {
                "group_name": row.group_name,
                "channel": row.channel,
                "title": row.title,
                "notes": row.notes,
            }
        )
    return output.getvalue()


if __name__ == "__main__":
    raise SystemExit(main())
