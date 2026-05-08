"""
Fraud Analyst Chatbot — two-pass NL-to-SQL architecture.

Pass 1: Vanna + Gemini Flash  →  NL question → SQL → execute → DataFrame
Pass 2: Gemini Flash direct   →  DataFrame preview → analyst-friendly insight

Mount into main_fastapi.py:
    from chatbot import router as chat_router
    app.include_router(chat_router)
"""

import os
from typing import Any, List, Optional

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi import Cookie
from jose import JWTError, jwt
from pydantic import BaseModel

# Vanna imports are lazy (inside _get_vanna) so a missing optional dependency
# only fails when the chatbot endpoint is called, not at server startup.
try:
    import google.generativeai as genai
    _GENAI_AVAILABLE = True
except ImportError:
    _GENAI_AVAILABLE = False

# ─────────────────────────────────────────────────────────────────────────────
# Auth — mirrors main_fastapi.py; reads the same env vars so tokens issued
# by the main app are accepted here without a shared import.
# ─────────────────────────────────────────────────────────────────────────────

_JWT_SECRET = os.getenv("JWT_SECRET_KEY", "change-me-in-production")
_JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")


def get_current_user(
    request: Request,
    access_token: Optional[str] = Cookie(default=None),
) -> dict:
    token = access_token
    if not token:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        payload = jwt.decode(token, _JWT_SECRET, algorithms=[_JWT_ALGORITHM])
        username: Optional[str] = payload.get("sub")
        if not username:
            raise HTTPException(status_code=401, detail="Invalid token")
        return {"username": username, "role": payload.get("role", "viewer")}
    except JWTError:
        raise HTTPException(status_code=401, detail="Token invalid or expired")


# ─────────────────────────────────────────────────────────────────────────────
# Vanna — lazy singleton so a missing API key surfaces as a 503 on the first
# chat request instead of crashing the entire server at import time.
# ─────────────────────────────────────────────────────────────────────────────

_vn = None  # type: ignore


def _build_pg_connection_string() -> str:
    """Build a psycopg2-style connection URL, preferring DATABASE_URL if set."""
    url = os.getenv("DATABASE_URL")
    if url:
        return url
    import urllib.parse
    user = os.getenv("DB_READONLY_USER", "dp_readonly")
    pwd  = urllib.parse.quote(os.getenv("DB_READONLY_PASSWORD", ""), safe="")
    host = os.getenv("DB_HOST", "localhost")
    port = os.getenv("DB_PORT", "5432")
    name = os.getenv("DB_NAME", "fraud_detection")
    return f"postgresql://{user}:{pwd}@{host}:{port}/{name}"


def _get_vanna():
    global _vn
    if _vn is not None:
        return _vn

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise HTTPException(status_code=503, detail="GEMINI_API_KEY is not configured.")

    try:
        from vanna.pgvector import PG_VectorStore
        from vanna.google import GoogleGeminiChat

        class FraudVanna(PG_VectorStore, GoogleGeminiChat):
            def __init__(self, config=None):
                PG_VectorStore.__init__(self, config=config)
                GoogleGeminiChat.__init__(self, config=config)

    except ImportError:
        try:
            from vanna.chromadb import ChromaDB_VectorStore
            from vanna.google import GoogleGeminiChat

            class FraudVanna(ChromaDB_VectorStore, GoogleGeminiChat):  # type: ignore
                def __init__(self, config=None):
                    ChromaDB_VectorStore.__init__(self, config=config)
                    GoogleGeminiChat.__init__(self, config=config)

        except ImportError:
            raise HTTPException(status_code=503, detail="Vanna is not installed.")

    conn_str = _build_pg_connection_string()
    _vn = FraudVanna(config={
        "api_key":           api_key,
        "model":             "gemini-1.5-flash",
        "connection_string": conn_str,
    })
    _vn.connect_to_postgres(
        host=os.getenv("DB_HOST", "localhost"),
        dbname=os.getenv("DB_NAME", "fraud_detection"),
        user=os.getenv("DB_READONLY_USER"),
        password=os.getenv("DB_READONLY_PASSWORD"),
    )
    return _vn


# ─────────────────────────────────────────────────────────────────────────────
# Pass 2 — natural language summary of the query results
# ─────────────────────────────────────────────────────────────────────────────

def _summary_model():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key or not _GENAI_AVAILABLE:
        return None
    import google.generativeai as genai
    genai.configure(api_key=api_key)
    return genai.GenerativeModel("gemini-1.5-flash")


def generate_summary(question: str, df: pd.DataFrame) -> str:
    if df.empty:
        return "No results found for your query."

    model = _summary_model()
    if model is None:
        return f"{len(df)} row(s) returned."

    preview = df.head(10).to_string(index=False)
    prompt = (
        f'You are a fraud analyst assistant. An analyst asked: "{question}"\n\n'
        f"The query returned {len(df)} row(s). Preview:\n{preview}\n\n"
        "Write a single concise insight (1–2 sentences max) summarising the key "
        "finding. Be specific — mention actual numbers, merchant names, or "
        "percentages where relevant. Do not explain the SQL or methodology."
    )
    response = model.generate_content(prompt)
    return response.text.strip()


# ─────────────────────────────────────────────────────────────────────────────
# Visualisation hint — inferred from SQL structure and result shape
# ─────────────────────────────────────────────────────────────────────────────

def suggest_visualization(sql: str, df: pd.DataFrame) -> str:
    if df.empty:
        return "empty"
    sql_upper = sql.upper()
    if "GROUP BY" in sql_upper and len(df) > 1:
        col_names = [c.lower() for c in df.columns]
        if any(k in col_names for k in ["date", "week", "period", "hour", "month"]):
            return "line_chart"
        return "bar_chart"
    if len(df) == 1 and len(df.columns) <= 3:
        return "stat_card"
    return "table"


# ─────────────────────────────────────────────────────────────────────────────
# Pydantic models
# ─────────────────────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str
    conversation_history: List[Any] = []


class ChatResponse(BaseModel):
    summary: str
    sql: str
    rows: List[Any]
    columns: List[str]
    visualization: str
    row_count: int


# ─────────────────────────────────────────────────────────────────────────────
# Router
# ─────────────────────────────────────────────────────────────────────────────

router = APIRouter()


@router.post("/api/chat", response_model=ChatResponse)
def chat_endpoint(
    request: ChatRequest,
    _user: dict = Depends(get_current_user),
) -> ChatResponse:
    try:
        vanna = _get_vanna()

        # Pass 1 — Vanna: NL → SQL → DataFrame
        sql: Optional[str] = vanna.generate_sql(request.message)
        if not sql:
            raise HTTPException(status_code=422, detail="Could not generate SQL for that question.")

        sql = sql.strip()
        if not sql.upper().startswith("SELECT"):
            raise HTTPException(
                status_code=400,
                detail="Only SELECT queries are permitted.",
            )

        df: pd.DataFrame = vanna.run_sql(sql)

        # Pass 2 — Gemini: DataFrame → natural language insight
        summary = generate_summary(request.message, df)
        viz = suggest_visualization(sql, df)

        return ChatResponse(
            summary=summary,
            sql=sql,
            rows=df.to_dict(orient="records"),
            columns=list(df.columns),
            visualization=viz,
            row_count=len(df),
        )

    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
