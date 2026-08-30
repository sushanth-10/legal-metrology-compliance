from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import psycopg
from psycopg.rows import dict_row


ROOT = Path(__file__).resolve().parent
STORAGE_DIR = Path(os.getenv("IMAGE_STORAGE_DIR", str(ROOT / "storage"))).resolve()
TOKEN_SECRET = os.getenv("TOKEN_SECRET", "")


def database_url() -> str:
    value = os.getenv("DATABASE_URL", "").strip()
    if not value:
        raise RuntimeError("DATABASE_URL is not configured.")
    return value


def connect() -> psycopg.Connection[Any]:
    return psycopg.connect(database_url(), row_factory=dict_row)


def _password_hash(password: str, salt: bytes | None = None) -> str:
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 210_000)
    return f"pbkdf2_sha256$210000${base64.urlsafe_b64encode(salt).decode()}${base64.urlsafe_b64encode(digest).decode()}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, iterations, salt_text, digest_text = encoded.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        salt = base64.urlsafe_b64decode(salt_text.encode())
        expected = base64.urlsafe_b64decode(digest_text.encode())
        actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, int(iterations))
        return hmac.compare_digest(actual, expected)
    except (TypeError, ValueError):
        return False


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    login_id TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('consumer', 'officer')),
    email TEXT,
    location TEXT,
    officer_id TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS scans (
    scan_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    product_name TEXT,
    overall_status TEXT NOT NULL,
    scanned_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    image_ref TEXT,
    image_metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    extracted_data JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE TABLE IF NOT EXISTS compliance_results (
    id BIGSERIAL PRIMARY KEY,
    scan_id TEXT NOT NULL REFERENCES scans(scan_id) ON DELETE CASCADE,
    check_name TEXT NOT NULL,
    status TEXT NOT NULL,
    extracted_value TEXT,
    applicable_requirement TEXT,
    explanation TEXT NOT NULL,
    evidence TEXT,
    confidence NUMERIC,
    source_image INTEGER
);

CREATE TABLE IF NOT EXISTS reports (
    report_id TEXT PRIMARY KEY,
    scan_id TEXT NOT NULL REFERENCES scans(scan_id) ON DELETE CASCADE,
    generated_by TEXT NOT NULL REFERENCES users(id),
    generated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    pdf_path TEXT NOT NULL,
    status TEXT NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS scans_user_id_scanned_at_idx ON scans(user_id, scanned_at DESC);
CREATE INDEX IF NOT EXISTS compliance_results_scan_id_idx ON compliance_results(scan_id);
CREATE INDEX IF NOT EXISTS reports_generated_at_idx ON reports(generated_at DESC);
"""


def init_db() -> None:
    with connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute(SCHEMA_SQL)
            seed_users(cursor)
        connection.commit()
    STORAGE_DIR.mkdir(parents=True, exist_ok=True)


def seed_users(cursor: psycopg.Cursor[Any]) -> None:
    users = [
        ("user-consumer-demo", "user123", "Demo Consumer", "consumer", "consumer@example.in", None),
        ("user-officer-demo", "officer123", "Demo Officer", "officer", "officer@example.in", "LM-DEMO-001"),
    ]
    for user_id, login_id, name, role, email, officer_id in users:
        cursor.execute(
            """
            INSERT INTO users (id, login_id, name, password_hash, role, email, location, officer_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (login_id) DO NOTHING
            """,
            (user_id, login_id, name, _password_hash("123456"), role, email, "Bengaluru", officer_id),
        )


def create_user(login_id: str, password: str, name: str, role: str, email: str | None = None) -> dict[str, Any]:
    user_id = new_id("user")
    with connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO users (id, login_id, name, password_hash, role, email, location) VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING *",
                (user_id, login_id, name, _password_hash(password), role, email, "Bengaluru"),
            )
            user = cursor.fetchone()
        connection.commit()
    return user


def create_token(user_id: str) -> str:
    secret = TOKEN_SECRET or os.getenv("DATABASE_URL", "niriksha-development-secret")
    payload = {"sub": user_id, "exp": int((datetime.now(UTC) + timedelta(hours=12)).timestamp())}
    encoded = base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode()).decode().rstrip("=")
    signature = hmac.new(secret.encode(), encoded.encode(), hashlib.sha256).hexdigest()
    return f"{encoded}.{signature}"


def user_from_token(token: str) -> dict[str, Any] | None:
    try:
        encoded, signature = token.split(".", 1)
        secret = TOKEN_SECRET or os.getenv("DATABASE_URL", "niriksha-development-secret")
        expected = hmac.new(secret.encode(), encoded.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected):
            return None
        padded = encoded + "=" * (-len(encoded) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded.encode()))
        if int(payload["exp"]) < int(datetime.now(UTC).timestamp()):
            return None
        with connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT * FROM users WHERE id = %s", (payload["sub"],))
                return cursor.fetchone()
    except (ValueError, KeyError, TypeError, json.JSONDecodeError, RuntimeError, psycopg.Error):
        return None


def new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


def json_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_value(item) for item in value]
    if hasattr(value, "value"):
        return value.value
    return value


def iso_datetime(value: Any) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)
