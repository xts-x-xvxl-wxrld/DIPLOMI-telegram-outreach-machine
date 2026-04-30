"""Enforce wiki and code fragmentation size guardrails."""

from __future__ import annotations

import argparse
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path, PurePosixPath


ROOT_MARKER = "pyproject.toml"

WIKI_INDEX_CAP = 150
TOP_LEVEL_SPEC_CAP = 300
PLAN_CAP = 200
PRODUCTION_PY_CAP = 800
TEST_PY_CAP = 1_000

APPEND_ONLY_EXEMPTIONS = {
    "wiki/log.md",
}

GRANDFATHERED_LIMITS = {
    # Existing oversized files. These are allowed to remain, but not grow.
    "backend/api/schemas.py": 1_090,
    "bot/api_client.py": 961,
    "bot/callback_handlers.py": 920,
    "bot/engagement_commands_config.py": 890,
    "bot/engagement_wizard_flow.py": 947,
    "bot/ui_engagement.py": 819,
    "tests/test_bot_api_client.py": 1_082,
    "tests/test_bot_engagement_handlers.py": 2_770,
    "tests/test_engagement_api.py": 2_265,
    "tests/test_queue_payloads.py": 1_073,
    "wiki/plan/bot-engagement-controls/slices-6-10.md": 209,
    "wiki/plan/engagement-admin-control-plane.md": 202,
    "wiki/plan/engagement-operator-controls/slices.md": 228,
}


@dataclass(frozen=True)
class FragmentationRule:
    name: str
    cap: int
    hint: str


@dataclass(frozen=True)
class Violation:
    path: str
    lines: int
    rule: FragmentationRule
    grandfathered_limit: int | None = None


def find_repo_root(start: Path) -> Path:
    current = start.resolve()
    for candidate in (current, *current.parents):
        if (candidate / ROOT_MARKER).is_file() and (candidate / ".git").exists():
            return candidate
    raise RuntimeError("Could not find repository root")


def tracked_files(root: Path) -> list[str]:
    result = subprocess.run(
        ["git", "-C", str(root), "ls-files"],
        check=True,
        capture_output=True,
        text=True,
    )
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def expand_paths(root: Path, paths: list[str]) -> list[str]:
    expanded: list[str] = []
    for raw_path in paths:
        path = (root / raw_path).resolve()
        if path.is_dir():
            expanded.extend(
                relative_to_root(root, child)
                for child in path.rglob("*")
                if child.is_file() and ".git" not in child.parts
            )
        elif path.is_file():
            expanded.append(relative_to_root(root, path))
    return sorted(set(expanded))


def relative_to_root(root: Path, path: Path) -> str:
    return path.resolve().relative_to(root).as_posix()


def line_count(path: Path) -> int:
    with path.open("rb") as file:
        return sum(1 for _ in file)


def rule_for(path: str) -> FragmentationRule | None:
    posix = PurePosixPath(path)
    parts = posix.parts

    if path in APPEND_ONLY_EXEMPTIONS:
        return None

    if path == "wiki/index.md":
        return FragmentationRule(
            "wiki index",
            WIKI_INDEX_CAP,
            "Move detail into spec, plan, or implementation-root shards and keep the index routable.",
        )

    if len(parts) == 3 and parts[:2] == ("wiki", "spec") and posix.suffix == ".md":
        return FragmentationRule(
            "top-level wiki spec",
            TOP_LEVEL_SPEC_CAP,
            "Move detail into a focused shard under wiki/spec/<module>/ and link it from the parent.",
        )

    if len(parts) >= 3 and parts[:2] == ("wiki", "plan") and posix.suffix == ".md":
        return FragmentationRule(
            "wiki plan",
            PLAN_CAP,
            "Split long plans into slice files under wiki/plan/<feature>/.",
        )

    if posix.suffix == ".py" and parts and parts[0] == "tests":
        return FragmentationRule(
            "test file",
            TEST_PY_CAP,
            "Split tests by public behavior surface or route/handler shard.",
        )

    if posix.suffix == ".py" and parts and parts[0] in {"backend", "bot", "scripts", "alembic"}:
        return FragmentationRule(
            "production Python file",
            PRODUCTION_PY_CAP,
            "Split by operational boundary before adding feature-sized behavior.",
        )

    return None


def check_file(root: Path, path: str) -> Violation | None:
    rule = rule_for(path)
    if rule is None:
        return None

    target = root / path
    if not target.is_file():
        return None

    lines = line_count(target)
    if lines <= rule.cap:
        return None

    grandfathered_limit = GRANDFATHERED_LIMITS.get(path)
    if grandfathered_limit is not None and lines <= grandfathered_limit:
        return None

    return Violation(path, lines, rule, grandfathered_limit)


def check_paths(root: Path, paths: list[str]) -> list[Violation]:
    return [violation for path in paths if (violation := check_file(root, path)) is not None]


def format_violation(violation: Violation) -> str:
    if violation.grandfathered_limit is not None:
        limit_text = f"grandfathered ceiling {violation.grandfathered_limit}"
    else:
        limit_text = f"cap {violation.rule.cap}"

    return (
        f"{violation.path}: {violation.lines} lines exceeds {limit_text} "
        f"for {violation.rule.name}. {violation.rule.hint}"
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "paths",
        nargs="*",
        help="Optional files or directories to check. Defaults to all tracked files.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    root = find_repo_root(Path.cwd())
    paths = expand_paths(root, args.paths) if args.paths else tracked_files(root)
    violations = check_paths(root, paths)

    if not violations:
        print(f"Fragmentation guardrail passed for {len(paths)} files.")
        return 0

    print("Fragmentation guardrail failed:", file=sys.stderr)
    for violation in violations:
        print(f"- {format_violation(violation)}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
