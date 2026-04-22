from __future__ import annotations

import runpy
import sys


def test_bot_main_module_runs_polling_entrypoint(monkeypatch) -> None:
    import bot.app as bot_app

    called = False

    def fake_main() -> None:
        nonlocal called
        called = True

    monkeypatch.setattr(bot_app, "main", fake_main)

    original_module = sys.modules.pop("bot.main", None)
    try:
        runpy.run_module("bot.main", run_name="__main__")
    finally:
        if original_module is not None:
            sys.modules["bot.main"] = original_module

    assert called is True
