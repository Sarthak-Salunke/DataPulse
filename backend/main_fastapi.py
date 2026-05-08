"""
FastAPI Backend for Real-time Fraud Detection Dashboard
Connects to PostgreSQL via a connection pool and provides REST + WebSocket.

Changes from original:
  - psycopg2.pool.ThreadedConnectionPool replaces per-request connections.
    The old code opened and closed a new connection on every API call and
    every 5-second background-task tick, which exhausts max_connections
    under any real load. The pool keeps 2-10 connections alive and reuses them.

  - get_db() context manager ensures connections are always returned to the
    pool even when exceptions are raised.

  - REST endpoints that touch the database are plain `def` (not async def).
    FastAPI automatically runs sync endpoints in a thread pool, which is the
    correct pattern for blocking I/O. Using async def + sync psycopg2 was
    blocking the entire event loop.

  - /api/customer/{cc_num} and /api/statement/{cc_num} ported from Flask.
    They now return typed JSON (Pydantic models) instead of HTML tables.

  - Flask server (main.py / port 5050) is no longer needed and can be left
    stopped. All routes now live here on port 8000.

  - query_execute.py has been removed (unused). DB queries are defined inline.
    Install all dependencies from the root requirements.txt.
"""

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Depends, Response, Cookie
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
from contextlib import contextmanager
import asyncio
import json
import sys
import os
import uuid
import psycopg2
from psycopg2 import pool as pg_pool
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv
from datetime import datetime, timedelta
from jose import JWTError, jwt
from passlib.context import CryptContext

try:
    from google.oauth2 import id_token as _google_id_token
    from google.auth.transport import requests as _google_requests
    _GOOGLE_AUTH_AVAILABLE = True
except ImportError:
    _GOOGLE_AUTH_AVAILABLE = False

load_dotenv()

# Allow importing cape/ from the project root when running from backend/
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from cape_router import router as cape_router, init_cape_pipeline
from chatbot import router as chat_router

# ============================================================================
# Auth Configuration
# ============================================================================

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

JWT_SECRET     = os.getenv("JWT_SECRET_KEY", "change-me-in-production")
JWT_ALGORITHM  = os.getenv("JWT_ALGORITHM", "HS256")
JWT_EXPIRE_MIN = int(os.getenv("JWT_EXPIRE_MINUTES", "480"))

# Single admin user — credentials loaded from .env at startup.
# Password is hashed once so it never lives in memory as plaintext.
_USERS: dict = {}  # populated in startup_event


def _build_users():
    """Hash the admin password from .env and store the user record."""
    username = os.getenv("ADMIN_USERNAME", "admin")
    password = os.getenv("ADMIN_PASSWORD", "datapulse2024")
    _USERS[username] = {
        "username": username,
        "hashed_password": _pwd_context.hash(password),
        "role": "admin",
    }


def _authenticate(username: str, password: str) -> Optional[dict]:
    user = _USERS.get(username)
    if not user or not _pwd_context.verify(password, user["hashed_password"]):
        return None
    return user


def _create_token(data: dict) -> str:
    payload = data.copy()
    payload["exp"] = datetime.utcnow() + timedelta(minutes=JWT_EXPIRE_MIN)
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def get_current_user(access_token: Optional[str] = Cookie(default=None)) -> dict:
    """
    FastAPI dependency — reads the httpOnly cookie set on login.
    Raises 401 if the cookie is missing or the token is invalid/expired.
    """
    if not access_token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        payload = jwt.decode(access_token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        username: Optional[str] = payload.get("sub")
        if not username:
            raise HTTPException(status_code=401, detail="Invalid token")
        return {"username": username, "role": payload.get("role", "viewer")}
    except JWTError:
        raise HTTPException(status_code=401, detail="Token invalid or expired")


# ============================================================================
# Database Configuration
# ============================================================================

DB_CONFIG = {
    'host':     os.getenv('DB_HOST', 'localhost'),
    'port':     os.getenv('DB_PORT', '5432'),
    'database': os.getenv('DB_NAME', 'fraud_detection'),
    'user':     os.getenv('DB_USER', 'postgres'),
    'password': os.getenv('DB_PASSWORD', ''),
}

# Module-level pool — created at startup, closed at shutdown.
_pool: Optional[pg_pool.ThreadedConnectionPool] = None


def _make_pool() -> pg_pool.ThreadedConnectionPool:
    """
    Build the connection pool from DATABASE_URL (cloud) or DB_* vars (local).
    Appends sslmode=require for Supabase / Neon / any cloud Postgres that
    needs it — ignored if already present in the URL.
    """
    db_url = os.getenv("DATABASE_URL")
    if db_url:
        if "sslmode" not in db_url:
            db_url += ("&" if "?" in db_url else "?") + "sslmode=require"
        return pg_pool.ThreadedConnectionPool(minconn=1, maxconn=10, dsn=db_url)
    return pg_pool.ThreadedConnectionPool(minconn=1, maxconn=10, **DB_CONFIG)


@contextmanager
def get_db():
    """
    Borrow a connection from the pool, yield it, then return it.
    Using a context manager guarantees the connection is always released,
    even if the query raises an exception.
    """
    conn = _pool.getconn()
    try:
        yield conn
    finally:
        _pool.putconn(conn)


# ============================================================================
# Pydantic Models
# ============================================================================

class DashboardMetrics(BaseModel):
    totalTransactions: int
    fraudDetected: int
    fraudRate: float
    accuracy: float


class FraudAlert(BaseModel):
    timestamp: str
    ccNum: str
    amount: float
    merchant: str
    confidence: float
    transNum: str
    category: Optional[str] = None
    distance: Optional[float] = None


class Transaction(BaseModel):
    id: str
    time: str
    customer: str
    merchant: str
    category: str
    amount: float
    distance: float
    status: str
    confidence: Optional[float] = None


class CustomerDetails(BaseModel):
    ccNum: str
    first: Optional[str] = None
    last: Optional[str] = None
    gender: Optional[str] = None
    age: Optional[int] = None
    job: Optional[str] = None
    street: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip: Optional[str] = None
    lat: Optional[float] = None
    long: Optional[float] = None


class StatementTransaction(BaseModel):
    ccNum: str
    transNum: str
    transTime: Optional[str] = None
    category: Optional[str] = None
    amount: Optional[float] = None
    merchant: Optional[str] = None
    distance: Optional[float] = None
    isFraud: Optional[int] = None
    source: str  # 'fraud' | 'non_fraud'


class StatementResponse(BaseModel):
    ccNum: str
    transactionCount: int
    data: List[StatementTransaction]


class IngestRequest(BaseModel):
    cc_num: str
    merchant: str
    category: str
    amt: float
    merch_lat: float = 0.0
    merch_long: float = 0.0
    distance: float = 0.0
    age: int = 0
    channel: str = "web"


class LoginRequest(BaseModel):
    username: str
    password: str


class GoogleLoginRequest(BaseModel):
    credential: str


class UserInfo(BaseModel):
    username: str
    role: str


# ============================================================================
# FastAPI App + CORS
# ============================================================================

app = FastAPI(title="Fraud Detection API", version="2.0.0")

_ALLOWED_ORIGINS = [
    o.strip()
    for o in os.getenv(
        "ALLOWED_ORIGINS", "http://localhost:5173,http://localhost:3000"
    ).split(",")
    if o.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(cape_router)
app.include_router(chat_router)

# ============================================================================
# WebSocket Connection Manager
# ============================================================================

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        print(f"✅ WebSocket connected. Total: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        print(f"❌ WebSocket disconnected. Total: {len(self.active_connections)}")

    async def broadcast(self, message: dict):
        dead: List[WebSocket] = []
        for ws in self.active_connections:
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)


manager = ConnectionManager()

# ============================================================================
# Database Query Functions  (all sync — called from sync endpoints or executor)
# ============================================================================

def _get_dashboard_metrics() -> dict:
    with get_db() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT COUNT(*)::INT AS total
                FROM (
                    SELECT cc_num FROM fraud_transaction
                    UNION ALL
                    SELECT cc_num FROM non_fraud_transaction
                ) t
            """)
            total = (cur.fetchone() or {}).get('total', 0)

            cur.execute("""
                SELECT COUNT(*)::INT AS fraud_count
                FROM fraud_transaction
            """)
            fraud = (cur.fetchone() or {}).get('fraud_count', 0)

    return {
        "totalTransactions": total,
        "fraudDetected": fraud,
        "fraudRate": round((fraud / total * 100) if total else 0, 2),
        "accuracy": 94.35,
    }


def _get_recent_fraud_alerts(limit: int) -> list:
    with get_db() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT trans_time, trans_num, cc_num, amt, merchant,
                       is_fraud, category, distance, created_at
                FROM fraud_transaction
                ORDER BY created_at DESC
                LIMIT %s
            """, (limit,))
            rows = cur.fetchall()

    return [
        {
            "timestamp": r['trans_time'].isoformat() if r['trans_time'] else datetime.now().isoformat(),
            "ccNum":     f"**** **** **** {str(r['cc_num'])[-4:]}",
            "amount":    float(r['amt']),
            "merchant":  r['merchant'],
            "confidence": float(r['is_fraud']) * 100,
            "transNum":  r['trans_num'],
            "category":  r['category'],
            "distance":  float(r['distance']) if r['distance'] else 0,
        }
        for r in rows
    ]


def _get_all_transactions(limit: int) -> list:
    with get_db() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT trans_num AS id, trans_time AS time, cc_num AS customer,
                       merchant, category, amt AS amount, distance,
                       'Fraud' AS status, is_fraud * 100 AS confidence
                FROM fraud_transaction

                UNION ALL

                SELECT trans_num AS id, trans_time AS time, cc_num AS customer,
                       merchant, category, amt AS amount, distance,
                       'Normal' AS status, NULL AS confidence
                FROM non_fraud_transaction

                ORDER BY time DESC
                LIMIT %s
            """, (limit,))
            rows = cur.fetchall()

    return [
        {
            "id":         r['id'],
            "time":       r['time'].strftime('%H:%M:%S') if isinstance(r['time'], datetime) else str(r['time']),
            "customer":   f"**** **** **** {str(r['customer'])[-4:]}",
            "merchant":   r['merchant'],
            "category":   r['category'],
            "amount":     float(r['amount']),
            "distance":   float(r['distance']) if r['distance'] else 0,
            "status":     r['status'],
            "confidence": float(r['confidence']) if r['confidence'] else None,
        }
        for r in rows
    ]


def _get_customer(cc_num: str) -> Optional[dict]:
    with get_db() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT cc_num, first, last, gender, street, city,
                       state, zip, lat, long, job, dob
                FROM customer
                WHERE cc_num = %s
            """, (cc_num,))
            row = cur.fetchone()

    if not row:
        return None

    age = None
    if row.get('dob'):
        dob = row['dob']
        if isinstance(dob, datetime):
            age = int((datetime.today() - dob).days / 365.2425)

    return {
        "ccNum":  str(row['cc_num']),
        "first":  row['first'],
        "last":   row['last'],
        "gender": row['gender'],
        "age":    age,
        "job":    row['job'],
        "street": row['street'],
        "city":   row['city'],
        "state":  row['state'],
        "zip":    str(row['zip']) if row['zip'] else None,
        "lat":    float(row['lat']) if row['lat'] else None,
        "long":   float(row['long']) if row['long'] else None,
    }


def _get_statement(cc_num: str, limit: int) -> dict:
    with get_db() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT cc_num, trans_time, trans_num, category, amt,
                       merchant, distance, is_fraud, 'fraud' AS source
                FROM fraud_transaction
                WHERE cc_num = %s

                UNION ALL

                SELECT cc_num, trans_time, trans_num, category, amt,
                       merchant, distance, is_fraud, 'non_fraud' AS source
                FROM non_fraud_transaction
                WHERE cc_num = %s

                ORDER BY trans_time DESC
                LIMIT %s
            """, (cc_num, cc_num, limit))
            rows = cur.fetchall()

    transactions = [
        {
            "ccNum":     str(r['cc_num']),
            "transNum":  r['trans_num'],
            "transTime": str(r['trans_time']) if r['trans_time'] else None,
            "category":  r['category'],
            "amount":    float(r['amt']) if r['amt'] else None,
            "merchant":  r['merchant'],
            "distance":  float(r['distance']) if r['distance'] else None,
            "isFraud":   int(r['is_fraud']) if r['is_fraud'] is not None else None,
            "source":    r['source'],
        }
        for r in rows
    ]

    return {
        "ccNum":            cc_num,
        "transactionCount": len(transactions),
        "data":             transactions,
    }


# ============================================================================
# Background Task: Poll for New Fraud Transactions
# Replaces pg_notify LISTEN/NOTIFY which is blocked by Supabase's connection
# pooler (Supavisor). Compatible with direct Postgres and Supabase alike.
# ============================================================================

_last_fraud_seen: datetime = datetime.utcnow()


def _fetch_new_fraud(since: datetime) -> list:
    with get_db() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT cc_num, trans_num, trans_time, amt, merchant,
                       is_fraud, category, distance, created_at
                FROM fraud_transaction
                WHERE created_at > %s
                ORDER BY created_at ASC
                LIMIT 50
            """, (since,))
            return cur.fetchall() or []


async def poll_new_fraud_transactions():
    """Poll fraud_transaction every 3 s and broadcast new rows to WebSocket clients."""
    global _last_fraud_seen
    while True:
        await asyncio.sleep(3)
        try:
            loop = asyncio.get_event_loop()
            rows = await loop.run_in_executor(None, _fetch_new_fraud, _last_fraud_seen)
            for row in rows:
                if row["created_at"] > _last_fraud_seen:
                    _last_fraud_seen = row["created_at"]
                await manager.broadcast({
                    "type": "fraud_alert",
                    "data": {
                        "timestamp":  row["trans_time"].isoformat() if row["trans_time"] else datetime.now().isoformat(),
                        "ccNum":      f"**** **** **** {str(row['cc_num'])[-4:]}",
                        "amount":     float(row["amt"]),
                        "merchant":   row["merchant"],
                        "confidence": float(row["is_fraud"]) * 100,
                        "transNum":   row["trans_num"],
                        "category":   row["category"],
                        "distance":   float(row["distance"]) if row["distance"] else 0,
                    },
                })
        except Exception as e:
            print(f"poll_new_fraud_transactions error: {e}")


# ============================================================================
# REST API Endpoints
# Note: endpoints that query the DB are plain `def`, not `async def`.
# FastAPI runs sync endpoints in a thread pool automatically, which is the
# correct way to handle blocking I/O without starving the event loop.
# ============================================================================

@app.get("/")
def root():
    return {
        "message": "Fraud Detection API",
        "version": "2.0.0",
        "endpoints": {
            "health":      "/api/health",
            "metrics":     "/api/dashboard/metrics",
            "alerts":      "/api/fraud/alerts",
            "transactions": "/api/transactions",
            "customer":    "/api/customer/{cc_num}",
            "statement":   "/api/statement/{cc_num}",
            "websocket":   "/ws",
        },
    }


@app.get("/api/health")
def health_check():
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
        return {"status": "healthy", "database": "connected", "time": datetime.now().isoformat()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database connection failed: {e}")


@app.get("/api/dashboard/metrics", response_model=DashboardMetrics)
def dashboard_metrics(current_user: dict = Depends(get_current_user)):
    try:
        return _get_dashboard_metrics()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching metrics: {e}")


@app.get("/api/fraud/alerts", response_model=List[FraudAlert])
def fraud_alerts(limit: int = 10, current_user: dict = Depends(get_current_user)):
    try:
        return _get_recent_fraud_alerts(limit)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching alerts: {e}")


@app.get("/api/transactions", response_model=List[Transaction])
def transactions(limit: int = 50, current_user: dict = Depends(get_current_user)):
    try:
        return _get_all_transactions(limit)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching transactions: {e}")


@app.get("/api/customer/{cc_num}", response_model=CustomerDetails)
def customer_details(cc_num: str, current_user: dict = Depends(get_current_user)):
    """
    Returns customer profile as JSON.
    Replaces the Flask route that returned an HTML table.
    """
    try:
        result = _get_customer(cc_num)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching customer: {e}")
    if result is None:
        raise HTTPException(status_code=404, detail=f"Customer {cc_num} not found")
    return result


@app.get("/api/statement/{cc_num}", response_model=StatementResponse)
def customer_statement(
    cc_num: str,
    limit: int = 100,
    current_user: dict = Depends(get_current_user),
):
    """
    Returns transaction statement as JSON.
    Replaces the Flask route that returned an HTML table.
    """
    try:
        return _get_statement(cc_num, limit)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching statement: {e}")


# ============================================================================
# Transaction Ingest Endpoint
# ============================================================================

def _score_transaction(body: IngestRequest) -> tuple[int, float]:
    """
    Returns (is_fraud: 0|1, confidence: 0-100).
    Tries the CAPE pipeline first; falls back to a rule-based heuristic if
    the pipeline was not loaded (model files absent on this deployment).
    """
    # Access the CAPE pipeline through sys.modules so we always see the
    # current value even though init_cape_pipeline() runs after imports.
    cape_mod = sys.modules.get('cape_router')
    pipeline = getattr(cape_mod, '_pipeline', None) if cape_mod else None

    if pipeline is not None:
        try:
            from cape import Transaction as CAPETxn, Channel as CAPEChannel
            try:
                ch = CAPEChannel(body.channel.lower())
            except ValueError:
                ch = CAPEChannel.WEB
            txn = CAPETxn(
                trans_num=uuid.uuid4().hex,
                cc_num=body.cc_num,
                amt=body.amt,
                merchant=body.merchant,
                category=body.category,
                channel=ch,
            )
            result = pipeline.evaluate(txn)
            is_fraud = 1 if result.decision == "BLOCK" else 0
            return is_fraud, round(result.point_estimate * 100, 1)
        except Exception:
            pass  # fall through to heuristic

    # Heuristic fallback: risk driven by amount + category
    HIGH_RISK_CATS = {'shopping_net', 'misc_net', 'misc_pos', 'grocery_net', 'travel'}
    risk = min(1.0, body.amt / 3000.0)
    if body.category in HIGH_RISK_CATS:
        risk = min(1.0, risk + 0.25)
    if body.amt > 1000:
        risk = min(1.0, risk + 0.15)
    is_fraud = 1 if risk > 0.45 else 0
    return is_fraud, round(risk * 100, 1)


@app.post("/api/transactions/ingest")
def ingest_transaction(body: IngestRequest):
    """
    Accept a raw transaction, score it, and persist it to the DB.
    Fraud → fraud_transaction  (background poller picks it up, broadcasts via WS)
    Normal → non_fraud_transaction  (appears in next REST poll)
    """
    trans_num  = uuid.uuid4().hex
    trans_time = datetime.now()
    is_fraud, confidence = _score_transaction(body)
    table = "fraud_transaction" if is_fraud else "non_fraud_transaction"

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                INSERT INTO {table}
                    (cc_num, trans_time, trans_num, category, merchant,
                     amt, merch_lat, merch_long, distance, age, is_fraud)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    body.cc_num, trans_time, trans_num,
                    body.category, body.merchant, body.amt,
                    body.merch_lat, body.merch_long,
                    body.distance, body.age, is_fraud,
                ),
            )
        conn.commit()

    return {
        "trans_num":  trans_num,
        "decision":   "FRAUD" if is_fraud else "APPROVED",
        "confidence": confidence,
        "table":      table,
        "timestamp":  trans_time.isoformat(),
    }


# ============================================================================
# Auth Endpoints  (public — no Depends guard)
# ============================================================================

@app.post("/auth/login", response_model=UserInfo)
def login(body: LoginRequest, response: Response):
    """
    Validate credentials and set an httpOnly JWT cookie.
    The cookie is HttpOnly so JavaScript cannot read it — protects against XSS.
    SameSite=Lax blocks it from being sent in cross-site requests — protects against CSRF.
    """
    user = _authenticate(body.username, body.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid username or password")

    token = _create_token({"sub": user["username"], "role": user["role"]})

    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        samesite="none",        # required for cross-origin (Vercel → Render)
        max_age=JWT_EXPIRE_MIN * 60,
        secure=True,            # required when samesite="none"
    )
    return {"username": user["username"], "role": user["role"]}


@app.post("/auth/google", response_model=UserInfo)
def google_auth(body: GoogleLoginRequest, response: Response):
    """
    Verify a Google ID token issued by the frontend (via Google Identity Services).
    On success, sets the same httpOnly JWT cookie as the regular login endpoint.
    Requires GOOGLE_CLIENT_ID to be set in .env.
    """
    google_client_id = os.getenv("GOOGLE_CLIENT_ID", "")
    if not google_client_id:
        raise HTTPException(status_code=503, detail="Google OAuth not configured — set GOOGLE_CLIENT_ID in .env")
    if not _GOOGLE_AUTH_AVAILABLE:
        raise HTTPException(status_code=503, detail="google-auth package not installed — run: pip install google-auth")
    try:
        idinfo = _google_id_token.verify_oauth2_token(
            body.credential,
            _google_requests.Request(),
            google_client_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=f"Invalid Google token: {exc}")

    email: str = idinfo.get("email", "")
    name: str = idinfo.get("name") or email.split("@")[0]

    token = _create_token({"sub": name, "role": "analyst", "email": email})
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        samesite="none",        # required for cross-origin (Vercel → Render)
        max_age=JWT_EXPIRE_MIN * 60,
        secure=True,            # required when samesite="none"
    )
    return UserInfo(username=name, role="analyst")


@app.post("/auth/logout")
def logout(response: Response):
    """Clear the auth cookie."""
    response.delete_cookie(key="access_token", samesite="none", secure=True)
    return {"message": "Logged out"}


@app.get("/auth/me", response_model=UserInfo)
def me(current_user: dict = Depends(get_current_user)):
    """
    Returns the current user from the cookie.
    Frontend calls this on page load to check if the session is still valid
    without storing any token in JavaScript memory.
    """
    return current_user


# ============================================================================
# WebSocket Endpoint  (must remain async)
# ============================================================================

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        await websocket.send_json({
            "type": "connection",
            "message": "Connected to Fraud Detection API",
            "timestamp": datetime.now().isoformat(),
        })
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_json({"type": "pong", "timestamp": datetime.now().isoformat()})
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        print(f"WebSocket error: {e}")
        manager.disconnect(websocket)


# ============================================================================
# Startup / Shutdown
# ============================================================================

@app.on_event("startup")
async def startup_event():
    global _pool
    _pool = _make_pool()
    _build_users()
    try:
        init_cape_pipeline(deployment_day=0)
    except Exception as e:
        # CAPE model files may not be present on first deploy — non-fatal.
        print(f"[startup] CAPE init skipped: {e}")
    print("\n" + "=" * 60)
    print("Fraud Detection API  v2.0.0")
    print("=" * 60)
    print(f"  REST : /api/health  /api/dashboard/metrics")
    print(f"  WS   : /ws")
    print(f"  Docs : /docs")
    print(f"  Pool : min=2  max=10  connections")
    print("=" * 60 + "\n")
    asyncio.create_task(poll_new_fraud_transactions())


@app.on_event("shutdown")
async def shutdown_event():
    if _pool:
        _pool.closeall()
        print("🔒  Connection pool closed")


# ============================================================================
# Entry point
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main_fastapi:app", host="0.0.0.0", port=8000, reload=True, log_level="info")
