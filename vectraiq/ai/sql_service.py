import datetime
import decimal
import json
import re
import uuid
from typing import Any

import psycopg2

from vectraiq.config import settings
from vectraiq.ai.llm_service import generate
from vectraiq.cache.query_cache import query_cache


def _serialize_value(value: Any) -> Any:
    if isinstance(value, datetime.datetime):
        return value.isoformat()
    if isinstance(value, datetime.date):
        return value.isoformat()
    if isinstance(value, datetime.time):
        return value.isoformat()
    if isinstance(value, datetime.timedelta):
        return str(value)
    if isinstance(value, decimal.Decimal):
        return float(value)
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


def _serialize_row(row: dict[str, Any]) -> dict[str, Any]:
    return {k: _serialize_value(v) for k, v in row.items()}


def is_select_only(sql: str) -> bool:
    """Return True only if the SQL is a pure SELECT statement.

    Strips comments and checks each semicolon-separated statement.
    """
    # Strip single-line and block comments
    cleaned = re.sub(r"--[^\n]*", "", sql)
    cleaned = re.sub(r"/\*.*?\*/", "", cleaned, flags=re.DOTALL)
    cleaned = cleaned.strip()

    # Must start with SELECT
    if not cleaned.lower().startswith("select"):
        return False

    # Reject multi-statement (split on unquoted semicolons)
    if re.search(r";\s*\S", cleaned):
        return False

    # Reject any DML/DDL keywords
    forbidden = [
        "insert", "update", "delete", "drop", "alter",
        "create", "truncate", "grant", "revoke", "exec", "execute",
    ]
    for kw in forbidden:
        if re.search(rf"\b{kw}\b", cleaned, re.IGNORECASE):
            return False

    return True


class SQLService:
    def __init__(self) -> None:
        self._schema_context: str | None = None

    def _build_schema_context(self) -> str:
        if self._schema_context is not None:
            return self._schema_context

        conn = psycopg2.connect(settings.database_url)
        cur = conn.cursor()
        cur.execute("""
            SELECT table_name, column_name, data_type
            FROM information_schema.columns
            WHERE table_schema = 'public'
            ORDER BY table_name, ordinal_position;
        """)
        rows = cur.fetchall()
        cur.close()
        conn.close()

        tables: dict[str, list[str]] = {}
        for table, col, dtype in rows:
            tables.setdefault(table, []).append(f"{col} ({dtype})")

        lines = ["Database schema:"]
        for table, cols in tables.items():
            lines.append(f"  {table}: {', '.join(cols)}")

        self._schema_context = "\n".join(lines)
        return self._schema_context

    def generate_sql(self, question: str) -> dict:
        cached = query_cache.get_sql_generation(question)
        if cached is not None:
            return {"sql": cached, "explanation": "Loaded from SQL generation cache."}

        schema = self._build_schema_context()
        system = (
            "You are a SQL expert. Given a database schema and a question, "
            "generate a valid PostgreSQL SELECT query. Return JSON with keys: sql, explanation."
        )
        user = f"{schema}\n\nQuestion: {question}\n\nReturn only the JSON."
        result = generate(
            system, user,
            model=settings.sql_llm_model,
            temperature=settings.sql_temperature,
        )
        text = result["text"].strip()
        if text.startswith("```"):
            text = "\n".join(text.splitlines()[1:-1]).strip()
        data = json.loads(text)
        payload = {
            "sql": data.get("sql", ""),
            "explanation": data.get("explanation", ""),
        }
        query_cache.set_sql_generation(question, payload["sql"])
        return payload

    def execute_sql(self, sql: str) -> list[dict]:
        if not is_select_only(sql):
            raise ValueError("Only SELECT statements are allowed")

        cached = query_cache.get_sql_result(sql)
        if cached is not None:
            return cached

        conn = psycopg2.connect(settings.database_url)
        cur = conn.cursor()
        cur.execute(sql)
        columns = [desc[0] for desc in cur.description] if cur.description else []
        rows = cur.fetchall()
        cur.close()
        conn.close()

        result = [_serialize_row(dict(zip(columns, row, strict=True))) for row in rows]
        query_cache.set_sql_result(sql, result)
        return result
