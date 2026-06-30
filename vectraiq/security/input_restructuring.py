"""Layer 5: Input restructuring — tiktoken-based truncation."""

from __future__ import annotations

import logging

from vectraiq.config import settings

logger = logging.getLogger(__name__)


def count_tokens(text: str) -> int:
    """Count tokens using tiktoken if available, otherwise approximate via word count."""
    try:
        import tiktoken
        enc = tiktoken.get_encoding("cl100k_base")
        return len(enc.encode(text))
    except Exception:
        return len(text.split())


def truncate_text(text: str, max_tokens: int = 3_000) -> tuple[str, str]:
    """Truncate text to max_tokens. Returns (truncated, method_label)."""
    if count_tokens(text) <= max_tokens:
        return text, "original"
    try:
        import tiktoken
        enc = tiktoken.get_encoding("cl100k_base")
        encoded = enc.encode(text)
        return enc.decode(encoded[:max_tokens]), "truncated"
    except Exception:
        words = text.split()
        return " ".join(words[:max_tokens]), "truncated"


def truncate_to_token_limit(text: str, target_tokens: int = 3_000) -> tuple[str, str]:
    """Greedy sentence selection to fit within target_tokens.

    Named deliberately — this is NOT an LLM summarization, it is greedy selection.
    Returns (selected_text, method_label).
    """
    import re

    sentences = re.split(r"(?<=[.!?])\s+", text)
    parts: list[str] = []
    current_tokens = 0

    for sentence in sentences:
        sentence_tokens = count_tokens(sentence)
        if current_tokens + sentence_tokens > target_tokens and parts:
            break
        parts.append(sentence)
        current_tokens += sentence_tokens

    return " ".join(parts), "summarized"


def restructure_input(text: str) -> tuple[str, str]:
    """Apply input restructuring based on token count.

    Rules:
    - ≤ effective_limit tokens: original
    - effective_limit – 2× effective_limit: truncated
    - > 2× effective_limit: greedy sentence selection
    """
    tokens = count_tokens(text)
    max_input = settings.max_input_tokens
    reserved = settings.reserved_context_tokens
    effective_limit = max_input - reserved

    if tokens <= effective_limit:
        return text, "original"
    if tokens <= effective_limit * 2:
        return truncate_text(text, effective_limit)
    return truncate_to_token_limit(text, effective_limit)
