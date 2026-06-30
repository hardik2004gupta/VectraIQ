"""
Query endpoints.

POST /query              — main AI query (RAG / SQL / Hybrid), full security pipeline
POST /query/sql/execute  — resume a LangGraph thread after SQL approval

Security pipeline (in order):
  1. JWT authentication          (get_current_user dependency)
  2. Per-user rate limiting      (sliding window via Redis)
  3. Daily token budget          (per-user cap via Redis)
  4. Input restructuring         (tiktoken truncation)
  5. LLM-Guard input scan        (injection + toxicity)
  6. Content moderation + PII    (regex / llm-guard)
  7. LangGraph invocation
  8. Output PII redaction
"""

from __future__ import annotations

import asyncio
import json
import uuid
from typing import AsyncGenerator

from fastapi import APIRouter, Depends, status
from fastapi.responses import StreamingResponse
from loguru import logger

from vectraiq.config import settings
from vectraiq.exceptions import (
    ContentBlockedError,
    InjectionDetectedError,
    RateLimitError,
    TokenBudgetError,
)
from vectraiq.logging_config import get_request_id
from vectraiq.middleware.auth import User, get_current_user
from vectraiq.middleware.rate_limiter import is_allowed_user
from vectraiq.models import ChatResponse, PendingSQLBlock, QueryRequest, ResponseMetadata, SqlApprovalRequest
from vectraiq.observability import timer
from vectraiq.security.content_moderation import moderate_and_redact
from vectraiq.security.input_guard import check_input_safe
from vectraiq.security.input_restructuring import count_tokens, restructure_input
from vectraiq.security.token_budget import check_budget, consume_budget

router = APIRouter(tags=["query"])


def _estimate_tokens(question: str) -> int:
    return count_tokens(question) + settings.reserved_output_tokens


def _apply_security_pipeline(question: str, user_id: str, estimated_tokens: int) -> str:
    """Apply all pre-invocation security checks. Returns the moderated input text.

    Raises VectraIQError subclasses (handled globally in main.py).
    """
    # Rate limit
    allowed, _, _ = is_allowed_user(
        user_id,
        limit=settings.rate_limit_requests,
        window_seconds=settings.rate_limit_window_seconds,
    )
    if not allowed:
        raise RateLimitError()

    # Token budget
    ok, remaining = check_budget(user_id, estimated_tokens)
    if not ok:
        raise TokenBudgetError(remaining=remaining, required=estimated_tokens)

    # Input restructuring
    restructured, method = restructure_input(question)
    if method != "original":
        logger.debug("Input restructured | user={} method={}", user_id, method)

    # LLM-Guard input scan
    guard_ok, guard_reason = check_input_safe(restructured)
    if not guard_ok:
        raise InjectionDetectedError(guard_reason)

    # Content moderation input
    mod_ok, moderated, mod_reason = moderate_and_redact(restructured)
    if not mod_ok:
        raise ContentBlockedError(mod_reason)

    return moderated


@router.post(
    "/query",
    response_model=ChatResponse,
    status_code=status.HTTP_200_OK,
    summary="Submit a natural language question",
    description=(
        "Runs the full VectraIQ pipeline: intent routing → RAG / SQL / Hybrid "
        "retrieval → answer generation. SQL queries trigger a human-in-the-loop "
        "approval step; the response will contain `pending_sql` instead of `answer`."
    ),
    responses={
        400: {"description": "Input blocked by security scan"},
        401: {"description": "Missing or invalid JWT token"},
        429: {"description": "Rate limit or daily token budget exceeded"},
    },
)
async def query_endpoint(
    body: QueryRequest,
    user: User = Depends(get_current_user),
) -> ChatResponse:
    t = timer()
    rid = get_request_id()
    estimated = _estimate_tokens(body.question)

    moderated_question = _apply_security_pipeline(body.question, user.username, estimated)

    flags = {
        "top_k": body.top_k,
        "search_mode": body.search_mode,
        "enable_rerank": body.enable_rerank,
        "enable_hyde": body.enable_hyde,
        "enable_crag": body.enable_crag,
        "enable_self_reflective": body.enable_self_reflective,
    }
    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}

    # Lazy import to avoid circular deps at module load
    from vectraiq.core.graph import graph

    result = graph.invoke(
        {"question": moderated_question, "user_id": user.username, "flags": flags},
        config=config,
    )

    # SQL approval interrupt
    if "__interrupt__" in result:
        intr = result["__interrupt__"][0].value
        logger.info(
            "SQL approval pending | rid={} user={} thread={} latency={:.1f}ms",
            rid, user.username, thread_id, t.elapsed_ms(),
        )
        return ChatResponse(
            answer="",
            sources=[],
            confidence=0.0,
            request_id=rid,
            pending_sql=PendingSQLBlock(
                sql=intr.get("sql", ""),
                query_id=thread_id,
                explanation=intr.get("explanation", ""),
            ),
        )

    # Output PII redaction
    out_ok, redacted, _ = moderate_and_redact(result.get("final_answer", ""))
    if not out_ok:
        raise ContentBlockedError("Answer blocked by output moderation")

    consume_budget(user.username, estimated)

    logger.info(
        "Query complete | rid={} user={} intent={} cache={} latency={:.1f}ms",
        rid,
        user.username,
        result.get("intent", "rag"),
        result.get("cache_hit", False),
        t.elapsed_ms(),
    )

    meta = result.get("metadata", {})
    if isinstance(meta, dict):
        meta = ResponseMetadata(**meta)

    return ChatResponse(
        answer=redacted,
        sources=result.get("sources", []),
        confidence=result.get("confidence", 0.0),
        cache_hit=result.get("cache_hit", False),
        request_id=rid,
        metadata=meta if isinstance(meta, ResponseMetadata) else ResponseMetadata(),
    )


def _sse(event: str, data: dict) -> str:
    """Format a server-sent event frame."""
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


@router.post(
    "/query/stream",
    summary="Submit a question with streaming status updates",
    description=(
        "Same pipeline as POST /query but returns a Server-Sent Events stream. "
        "Sends `status` events during processing and a final `result` event with "
        "the full ChatResponse payload. The stream ends with a `done` event."
    ),
    responses={
        200: {"content": {"text/event-stream": {}}},
        400: {"description": "Input blocked by security scan"},
        401: {"description": "Missing or invalid JWT token"},
        429: {"description": "Rate limit or daily token budget exceeded"},
    },
)
async def query_stream(
    body: QueryRequest,
    user: User = Depends(get_current_user),
) -> StreamingResponse:
    """Return a text/event-stream of pipeline status + final answer."""
    rid = get_request_id()
    estimated = _estimate_tokens(body.question)

    async def _event_stream() -> AsyncGenerator[str, None]:
        try:
            yield _sse("status", {"stage": "security", "message": "Scanning input…"})
            moderated_question = _apply_security_pipeline(body.question, user.username, estimated)

            yield _sse("status", {"stage": "routing", "message": "Classifying intent…"})
            flags = {
                "top_k": body.top_k,
                "search_mode": body.search_mode,
                "enable_rerank": body.enable_rerank,
                "enable_hyde": body.enable_hyde,
                "enable_crag": body.enable_crag,
                "enable_self_reflective": body.enable_self_reflective,
            }
            thread_id = str(uuid.uuid4())
            config = {"configurable": {"thread_id": thread_id}}

            from vectraiq.core.graph import graph

            yield _sse("status", {"stage": "retrieval", "message": "Retrieving documents…"})

            # Run the graph in a thread so we don't block the event loop
            loop = asyncio.get_running_loop()
            result = await loop.run_in_executor(
                None,
                lambda: graph.invoke(
                    {"question": moderated_question, "user_id": user.username, "flags": flags},
                    config=config,
                ),
            )

            if "__interrupt__" in result:
                intr = result["__interrupt__"][0].value
                payload = ChatResponse(
                    answer="",
                    sources=[],
                    confidence=0.0,
                    request_id=rid,
                    pending_sql=PendingSQLBlock(
                        sql=intr.get("sql", ""),
                        query_id=thread_id,
                        explanation=intr.get("explanation", ""),
                    ),
                )
                yield _sse("result", payload.model_dump())
                yield _sse("done", {})
                return

            yield _sse("status", {"stage": "moderation", "message": "Applying output filters…"})
            out_ok, redacted, _ = moderate_and_redact(result.get("final_answer", ""))
            if not out_ok:
                yield _sse("error", {"code": "content_blocked", "message": "Answer blocked by output moderation"})
                yield _sse("done", {})
                return

            consume_budget(user.username, estimated)
            meta = result.get("metadata", {})
            if isinstance(meta, dict):
                meta = ResponseMetadata(**meta)

            payload = ChatResponse(
                answer=redacted,
                sources=result.get("sources", []),
                confidence=result.get("confidence", 0.0),
                cache_hit=result.get("cache_hit", False),
                request_id=rid,
                metadata=meta if isinstance(meta, ResponseMetadata) else ResponseMetadata(),
            )
            yield _sse("result", payload.model_dump())
            yield _sse("done", {})

        except Exception as exc:
            logger.exception("Stream error | rid={} user={}", rid, user.username)
            yield _sse("error", {"code": "internal_error", "message": str(exc)})
            yield _sse("done", {})

    return StreamingResponse(
        _event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "X-Request-ID": rid,
        },
    )


@router.post(
    "/query/sql/execute",
    response_model=ChatResponse,
    status_code=status.HTTP_200_OK,
    summary="Approve or reject a pending SQL query",
    description=(
        "Resume a LangGraph thread after SQL approval. "
        "Pass `approved: true` to execute the generated SQL, "
        "or `approved: false` to cancel without running anything."
    ),
    responses={
        401: {"description": "Missing or invalid JWT token"},
    },
)
async def execute_sql(
    body: SqlApprovalRequest,
    user: User = Depends(get_current_user),
) -> ChatResponse:
    from langgraph.types import Command
    from vectraiq.core.graph import graph

    rid = get_request_id()
    t = timer()

    config = {"configurable": {"thread_id": body.query_id}}
    result = graph.invoke(
        Command(resume={"approved": body.approved}),
        config=config,
    )

    action = "approved" if body.approved else "rejected"
    logger.info(
        "SQL {} | rid={} user={} thread={} latency={:.1f}ms",
        action, rid, user.username, body.query_id, t.elapsed_ms(),
    )

    return ChatResponse(
        answer=result.get("final_answer", "SQL query was not approved."),
        sources=result.get("sources", []),
        confidence=result.get("confidence", 0.0),
        cache_hit=result.get("cache_hit", False),
        request_id=rid,
    )
