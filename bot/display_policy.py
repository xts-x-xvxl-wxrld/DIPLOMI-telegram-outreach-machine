from __future__ import annotations

import re

_SLASH_COMMAND_RE = re.compile(r"(?<![\w/:.])/[A-Za-z][A-Za-z0-9_]*")


def hide_slash_commands(text: str) -> str:
    """Render legacy slash-command mentions as plain button-led action labels."""
    return _SLASH_COMMAND_RE.sub(_command_label, text)


def _command_label(match: re.Match[str]) -> str:
    command = match.group(0).removeprefix("/")
    return command.replace("_", " ")
