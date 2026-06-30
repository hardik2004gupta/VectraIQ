import datetime
import decimal
import json
import uuid
from typing import Any

import psycopg
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from vectraiq.config import settings
from vectraiq.core.state import GraphState
from vectraiq.security.spotlighting import build_spotlighted_context
from vectraiq.security.system_prompt import build_system_prompt
from vectraiq.ai.llm_service import generate
from vectraiq.ai.rag_service import run_rag
from vectraiq.ai.router_service import classify_intent
from vectraiq.ai.sql_service import SQLService


sql_service = SQLService()


def _safe_json_default(obj: Any) -> Any:
    if isinstance(obj, datetime.datetime):
        return obj.isoformat()
    if isinstance(obj, datetime.date):
        return obj.isoformat()
    if isinstance(obj, datetime.time):
        return obj.isoformat()
    if isinstance(obj, datetime.timedelta):
        return str(obj)
    if isinstance(obj, decimal.Decimal):
        return float(obj)
    if isinstance(obj, uuid.UUID):
        return str(obj)
    if isinstance(obj, bytes):
        return obj.decode("utf-8", errors="replace")
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


def _safe_json_dumps(obj: Any, **kwargs: Any) -> str:
    return json.dumps(obj, default=_safe_json_default, **kwargs)


def route_intent(state: GraphState) -> dict:
    intent = classify_intent(state["question"])
    return {"intent": intent}


def retrieve_rag(state: GraphState) -> dict:
    response = run_rag(state["question"], flags=state.get("flags", {}))
    return {
        "retrieved_chunks": response.sources,
        "spotlighted_context": build_spotlighted_context([
            type("Chunk", (), {"text": s, "source": s, "score": 0.0})()
            for s in response.sources
        ]),
    }


def generate_sql_node(state: GraphState) -> dict:
    result = sql_service.generate_sql(state["question"])
    return {
        "generated_sql": result["sql"],
        "sql_explanation": result["explanation"],
    }


def request_sql_approval(state: GraphState) -> dict:
    approval = interrupt({
        "type": "sql_approval_required",
        "sql": state["generated_sql"],
        "explanation": state["sql_explanation"],
    })
    return {"sql_approved": approval.get("approved", False)}


def execute_sql(state: GraphState) -> dict:
    if not state.get("sql_approved"):
        return {"sql_rows": [], "final_answer": "SQL query was not approved."}
    sql = state.get("generated_sql", "")
    try:
        rows = sql_service.execute_sql(sql)
        return {"sql_rows": rows}
    except Exception as exc:
        return {"sql_rows": [], "final_answer": f"SQL execution failed: {exc}"}


def generate_answer(state: GraphState) -> dict:
    intent = state.get("intent", "rag")

    if intent == "sql":
        rows = state.get("sql_rows", [])
        if not rows:
            return {
                "final_answer": state.get("final_answer", "No results."),
                "sources": ["database query"],
                "confidence": 0.9,
            }
        answer = f"Query results:\n```\n{_safe_json_dumps(rows, indent=2)}\n```"
        return {"final_answer": answer, "sources": ["database query"], "confidence": 0.9}

    if intent == "hybrid":
        return _generate_hybrid_answer(state)

    response = run_rag(state["question"], flags=state.get("flags", {}))
    return {
        "final_answer": response.answer,
        "sources": response.sources,
        "confidence": response.confidence,
        "cache_hit": response.cache_hit,
        "chunk_previews": [c.model_dump() for c in response.metadata.retrieved_chunks],
        "metadata": response.metadata.model_dump(),
        "reflection_iterations": response.metadata.reflection_iterations,
        "refined_question": response.metadata.refined_question,
    }


def _generate_hybrid_answer(state: GraphState) -> dict:
    rows = state.get("sql_rows", [])
    rag_context = state.get("spotlighted_context", "")

    sql_section = ""
    if rows:
        sql_section = f"=== Database Query Results ===\n```\n{_safe_json_dumps(rows, indent=2)}\n```\n"

    rag_section = f"=== Retrieved Documents ===\n{rag_context}\n" if rag_context else ""

    # Use the hardened system prompt so hybrid path has same security policy as RAG path
    system = (
        build_system_prompt()
        + "\n\nSynthesize the database query results and retrieved documents below into a "
        "single coherent answer. Cite sources using [database query] for SQL results "
        "and [source_name] for documents."
    )
    result = generate(system, f"{sql_section}{rag_section}\n\nQuestion: {state['question']}")
    return {
        "final_answer": result["text"],
        "sources": ["database query"] + state.get("retrieved_chunks", []),
        "confidence": 0.85,
    }


def finalize(state: GraphState) -> dict:
    return {}


def _get_checkpointer():
    conn = psycopg.connect(settings.database_url, autocommit=True)
    saver = PostgresSaver(conn=conn)
    saver.setup()
    return saver


def build_graph():
    builder = StateGraph(GraphState)
    builder.add_node("route_intent", route_intent)
    builder.add_node("retrieve_rag", retrieve_rag)
    builder.add_node("generate_sql_node", generate_sql_node)
    builder.add_node("request_sql_approval", request_sql_approval)
    builder.add_node("execute_sql", execute_sql)
    builder.add_node("generate_answer", generate_answer)
    builder.add_node("finalize", finalize)

    builder.add_edge(START, "route_intent")
    builder.add_conditional_edges(
        "route_intent",
        lambda s: s.get("intent", "rag"),
        {"sql": "generate_sql_node", "rag": "generate_answer", "hybrid": "retrieve_rag"},
    )
    builder.add_edge("retrieve_rag", "generate_sql_node")
    builder.add_edge("generate_sql_node", "request_sql_approval")
    builder.add_edge("request_sql_approval", "execute_sql")
    builder.add_edge("execute_sql", "generate_answer")
    builder.add_edge("generate_answer", "finalize")
    builder.add_edge("finalize", END)

    checkpointer = _get_checkpointer()
    return builder.compile(checkpointer=checkpointer)


graph = build_graph()
