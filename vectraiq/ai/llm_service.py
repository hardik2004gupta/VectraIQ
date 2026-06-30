"""
OpenAI LLM wrapper.

Module-level client singleton — avoids connection overhead on every call.
Both functions record AI call metrics via the observability module so
future monitoring integrations (Langfuse, OTEL) can be added at one site.
"""

from __future__ import annotations

from openai import OpenAI

from vectraiq.config import settings
from vectraiq.observability import timed_ai_call

# Module-level singleton — created once at import time
_client = OpenAI(api_key=settings.openai_api_key)


def generate(
    system_prompt: str,
    user_message: str,
    model: str | None = None,
    temperature: float = 0.0,
) -> dict:
    """Call the chat completion API and return {"text": str, "usage": dict}."""
    model = model or settings.llm_model_answer

    with timed_ai_call("generate", model=model, provider="openai") as m:
        response = _client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            temperature=temperature,
        )
        text = response.choices[0].message.content or ""
        usage = {
            "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
            "completion_tokens": response.usage.completion_tokens if response.usage else 0,
            "total_tokens": response.usage.total_tokens if response.usage else 0,
        }
        # Feed token counts into the observability record
        m.prompt_tokens = usage["prompt_tokens"]
        m.completion_tokens = usage["completion_tokens"]
        m.total_tokens = usage["total_tokens"]
        m.model = model

    return {"text": text, "usage": usage}


def generate_with_json(
    system_prompt: str,
    user_message: str,
    model: str | None = None,
    temperature: float = 0.0,
) -> dict:
    """Like generate() but forces JSON response format (for grader calls)."""
    model = model or settings.llm_model_grader

    with timed_ai_call("generate_json", model=model, provider="openai") as m:
        response = _client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            temperature=temperature,
            response_format={"type": "json_object"},
        )
        text = response.choices[0].message.content or ""
        usage = {
            "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
            "completion_tokens": response.usage.completion_tokens if response.usage else 0,
            "total_tokens": response.usage.total_tokens if response.usage else 0,
        }
        m.prompt_tokens = usage["prompt_tokens"]
        m.completion_tokens = usage["completion_tokens"]
        m.total_tokens = usage["total_tokens"]
        m.model = model

    return {"text": text, "usage": usage}
