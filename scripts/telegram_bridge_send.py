from __future__ import annotations

import argparse
import asyncio
import os
import sys

import httpx


def build_bridge_text(sender: str, text: str) -> str:
    clean_sender = sender.strip() or "bot"
    return f"{clean_sender}:\n{text.strip()}"


async def send_bridge_message(
    *,
    bot_token: str,
    chat_id: str,
    sender: str,
    text: str,
    timeout_seconds: float = 15.0,
) -> None:
    if not bot_token:
        raise RuntimeError("Missing TELEGRAM_BOT_TOKEN")
    if not chat_id:
        raise RuntimeError("Missing TELEGRAM_BRIDGE_CHAT_ID")
    if not text.strip():
        raise RuntimeError("Message text is empty")

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": build_bridge_text(sender, text),
        "disable_web_page_preview": True,
    }
    async with httpx.AsyncClient(timeout=timeout_seconds) as client:
        response = await client.post(url, json=payload)
    if response.status_code >= 400:
        raise RuntimeError(f"Telegram sendMessage failed with HTTP {response.status_code}")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Send a Telegram bridge message from a VPS bot or Codex session."
    )
    parser.add_argument("--sender", default="vps-bot", help="Name shown above the message.")
    parser.add_argument("--text", help="Message text. Reads stdin when omitted.")
    parser.add_argument(
        "--chat-id",
        default=os.environ.get("TELEGRAM_BRIDGE_CHAT_ID", ""),
        help="Telegram chat ID. Defaults to TELEGRAM_BRIDGE_CHAT_ID.",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=float(os.environ.get("TELEGRAM_BRIDGE_TIMEOUT_SECONDS", "15")),
    )
    return parser.parse_args(argv)


async def async_main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    text = args.text if args.text is not None else sys.stdin.read()
    await send_bridge_message(
        bot_token=os.environ.get("TELEGRAM_BOT_TOKEN", ""),
        chat_id=args.chat_id,
        sender=args.sender,
        text=text,
        timeout_seconds=args.timeout_seconds,
    )
    print("Sent Telegram bridge message.")
    return 0


def main() -> None:
    try:
        exit_code = asyncio.run(async_main())
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1) from exc
    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
