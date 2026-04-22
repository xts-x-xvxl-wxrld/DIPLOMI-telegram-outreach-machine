# ruff: noqa: F401,F403,F405
from __future__ import annotations

from backend.workers.engagement_detect_types import *

from backend.workers.engagement_detect_prompt import *


async def detect_with_openai(model_input: dict[str, Any]) -> EngagementDetectionDecision:
    try:
        from openai import AsyncOpenAI
    except ImportError as exc:
        raise RuntimeError("openai must be installed before engagement.detect can run") from exc

    settings = get_settings()
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is required for engagement.detect")

    prompt_runtime = model_input.get("_prompt_runtime")
    if not isinstance(prompt_runtime, dict):
        prompt_runtime = {}
    model = str(prompt_runtime.get("model") or settings.openai_engagement_model)
    instructions = str(prompt_runtime.get("system_prompt") or DETECTION_INSTRUCTIONS)
    rendered_prompt = str(prompt_runtime.get("rendered_user_prompt") or "")
    if not rendered_prompt:
        rendered_prompt = (
            "Review this compact Telegram community context and decide whether a "
            "short public reply would be genuinely useful. Return structured output only.\n\n"
            f"{json.dumps(_public_model_input(model_input), ensure_ascii=True, default=str)}"
        )
    client = AsyncOpenAI(api_key=settings.openai_api_key)
    response = await client.responses.parse(
        model=model,
        instructions=instructions,
        input=[
            {
                "role": "user",
                "content": rendered_prompt,
            }
        ],
        text_format=EngagementDetectionDecision,
        temperature=float(prompt_runtime.get("temperature") or 0.2),
        max_output_tokens=int(prompt_runtime.get("max_output_tokens") or 1000),
    )
    decision = response.output_parsed
    if decision is None:
        raise RuntimeError("OpenAI returned no parsed engagement detection decision")
    return decision


def _public_model_input(model_input: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in model_input.items() if not key.startswith("_")}

__all__ = [
    "detect_with_openai",
]
