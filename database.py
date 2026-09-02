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
from dotenv import load_dotenv
from psycopg.rows import dict_row

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")
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
    -- Legacy consumer rows are retained for data preservation, but the API
    -- only permits organization, officer, and admin authentication.
    role TEXT NOT NULL CHECK (role IN ('consumer', 'organization', 'officer', 'admin')),
    email TEXT,
    location TEXT,
    state TEXT,
    district TEXT,
    officer_id TEXT,
    organization_id TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS organizations (
    id TEXT PRIMARY KEY,
    organization_name TEXT NOT NULL,
    organization_type TEXT,
    official_email TEXT,
    official_mobile TEXT,
    password_hash TEXT NOT NULL,
    registered_address TEXT,
    state TEXT,
    district TEXT,
    pin_code TEXT,
    gstin TEXT,
    registration_number TEXT,
    authorized_representative_name TEXT,
    authorized_representative_designation TEXT,
    authorized_representative_contact TEXT,
    website TEXT,
    industry TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS admins (
    id TEXT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    admin_name TEXT NOT NULL,
    official_email TEXT,
    department TEXT,
    state TEXT,
    district TEXT,
    administrative_role TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS scans (
    scan_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    organization_id TEXT REFERENCES organizations(id) ON DELETE SET NULL,
    product_name TEXT,
    overall_status TEXT NOT NULL,
    scanned_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    image_ref TEXT,
    image_metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    extracted_data JSONB NOT NULL DEFAULT '{}'::jsonb,
    compliance_score INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS scan_images (
    scan_image_id TEXT PRIMARY KEY,
    scan_id TEXT NOT NULL REFERENCES scans(scan_id) ON DELETE CASCADE,
    image_ref TEXT NOT NULL,
    filename TEXT,
    mime_type TEXT,
    sort_index INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
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
    organization_id TEXT REFERENCES organizations(id) ON DELETE SET NULL,
    generated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    pdf_path TEXT NOT NULL,
    status TEXT NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE TABLE IF NOT EXISTS complaints (
    complaint_id TEXT PRIMARY KEY,
    scan_id TEXT,
    organization_id TEXT REFERENCES organizations(id) ON DELETE SET NULL,
    product_name TEXT NOT NULL,
    product_category TEXT,
    complaint_category TEXT,
    complaint_description TEXT,
    complaint_location TEXT,
    state TEXT,
    district TEXT,
    submitted_by TEXT,
    status TEXT NOT NULL DEFAULT 'NEW',
    source TEXT NOT NULL DEFAULT 'USER_SUBMITTED',
    priority TEXT DEFAULT 'MEDIUM',
    admin_remark TEXT,
    evidence_images JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS complaint_status_history (
    history_id TEXT PRIMARY KEY,
    complaint_id TEXT NOT NULL REFERENCES complaints(complaint_id) ON DELETE CASCADE,
    previous_status TEXT,
    new_status TEXT NOT NULL,
    changed_by TEXT REFERENCES users(id),
    administrative_remark TEXT,
    changed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS scans_user_id_scanned_at_idx ON scans(user_id, scanned_at DESC);
CREATE INDEX IF NOT EXISTS scans_organization_id_idx ON scans(organization_id);
CREATE INDEX IF NOT EXISTS compliance_results_scan_id_idx ON compliance_results(scan_id);
CREATE INDEX IF NOT EXISTS reports_generated_at_idx ON reports(generated_at DESC);
CREATE INDEX IF NOT EXISTS reports_organization_id_idx ON reports(organization_id);
CREATE INDEX IF NOT EXISTS scan_images_scan_id_idx ON scan_images(scan_id, sort_index);
CREATE INDEX IF NOT EXISTS complaints_status_idx ON complaints(status);
CREATE INDEX IF NOT EXISTS complaints_jurisdiction_created_idx ON complaints(state, district, created_at DESC);
CREATE UNIQUE INDEX IF NOT EXISTS complaints_auto_scan_unique_idx ON complaints(scan_id) WHERE source = 'AUTO_SCAN_VIOLATION' AND scan_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS complaint_history_complaint_id_idx ON complaint_status_history(complaint_id, changed_at DESC);
"""

def _column_exists(cursor: psycopg.Cursor[Any], table_name: str, column_name: str) -> bool:
    cursor.execute(
        "SELECT 1 FROM information_schema.columns WHERE table_schema = 'public' AND table_name = %s AND column_name = %s",
        (table_name, column_name),
    )
    return cursor.fetchone() is not None


def _add_column_if_missing(cursor: psycopg.Cursor[Any], table_name: str, column_name: str, column_sql: str) -> None:
    if _column_exists(cursor, table_name, column_name):
        return
    cursor.execute(column_sql)


def _ensure_role_constraint(cursor: psycopg.Cursor[Any]) -> None:
    cursor.execute("ALTER TABLE users DROP CONSTRAINT IF EXISTS users_role_check")
    cursor.execute(
        "ALTER TABLE users ADD CONSTRAINT users_role_check CHECK (role IN ('consumer', 'organization', 'officer', 'admin'))"
    )


def init_db() -> None:
    with connect() as connection:
        with connection.cursor() as cursor:
            for table_sql in [
                """
                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY,
                    login_id TEXT NOT NULL UNIQUE,
                    name TEXT NOT NULL,
                    password_hash TEXT NOT NULL,
                    role TEXT NOT NULL CHECK (role IN ('consumer', 'organization', 'officer', 'admin')),
                    email TEXT,
                    location TEXT,
                    state TEXT,
                    district TEXT,
                    officer_id TEXT,
                    organization_id TEXT,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS organizations (
                    id TEXT PRIMARY KEY,
                    organization_name TEXT NOT NULL,
                    organization_type TEXT,
                    official_email TEXT,
                    official_mobile TEXT,
                    password_hash TEXT NOT NULL,
                    registered_address TEXT,
                    state TEXT,
                    district TEXT,
                    pin_code TEXT,
                    gstin TEXT,
                    registration_number TEXT,
                    authorized_representative_name TEXT,
                    authorized_representative_designation TEXT,
                    authorized_representative_contact TEXT,
                    website TEXT,
                    industry TEXT,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS admins (
                    id TEXT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
                    admin_name TEXT NOT NULL,
                    official_email TEXT,
                    department TEXT,
                    state TEXT,
                    district TEXT,
                    administrative_role TEXT,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS scans (
                    scan_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    organization_id TEXT REFERENCES organizations(id) ON DELETE SET NULL,
                    product_name TEXT,
                    overall_status TEXT NOT NULL,
                    scanned_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    image_ref TEXT,
                    image_metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
                    extracted_data JSONB NOT NULL DEFAULT '{}'::jsonb,
                    compliance_score INTEGER NOT NULL DEFAULT 0
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS scan_images (
                    scan_image_id TEXT PRIMARY KEY,
                    scan_id TEXT NOT NULL REFERENCES scans(scan_id) ON DELETE CASCADE,
                    image_ref TEXT NOT NULL,
                    filename TEXT,
                    mime_type TEXT,
                    sort_index INTEGER NOT NULL DEFAULT 1,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """,
                """
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
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS reports (
                    report_id TEXT PRIMARY KEY,
                    scan_id TEXT NOT NULL REFERENCES scans(scan_id) ON DELETE CASCADE,
                    generated_by TEXT NOT NULL REFERENCES users(id),
                    organization_id TEXT REFERENCES organizations(id) ON DELETE SET NULL,
                    generated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    pdf_path TEXT NOT NULL,
                    status TEXT NOT NULL,
                    metadata JSONB NOT NULL DEFAULT '{}'::jsonb
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS complaints (
                    complaint_id TEXT PRIMARY KEY,
                    scan_id TEXT,
                    organization_id TEXT REFERENCES organizations(id) ON DELETE SET NULL,
                    product_name TEXT NOT NULL,
                    product_category TEXT,
                    complaint_category TEXT,
                    complaint_description TEXT,
                    complaint_location TEXT,
                    state TEXT,
                    district TEXT,
                    submitted_by TEXT,
                    status TEXT NOT NULL DEFAULT 'NEW',
                    source TEXT NOT NULL DEFAULT 'USER_SUBMITTED',
                    priority TEXT DEFAULT 'MEDIUM',
                    admin_remark TEXT,
                    evidence_images JSONB NOT NULL DEFAULT '[]'::jsonb,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS complaint_status_history (
                    history_id TEXT PRIMARY KEY,
                    complaint_id TEXT NOT NULL REFERENCES complaints(complaint_id) ON DELETE CASCADE,
                    previous_status TEXT,
                    new_status TEXT NOT NULL,
                    changed_by TEXT REFERENCES users(id),
                    administrative_remark TEXT,
                    changed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """,
            ]:
                cursor.execute(table_sql)

            _add_column_if_missing(cursor, 'users', 'role', "ALTER TABLE users ADD COLUMN IF NOT EXISTS role TEXT NOT NULL DEFAULT 'organization' CHECK (role IN ('consumer', 'organization', 'officer', 'admin'))")
            _add_column_if_missing(cursor, 'users', 'state', 'ALTER TABLE users ADD COLUMN IF NOT EXISTS state TEXT')
            _add_column_if_missing(cursor, 'users', 'district', 'ALTER TABLE users ADD COLUMN IF NOT EXISTS district TEXT')
            _add_column_if_missing(cursor, 'users', 'organization_id', 'ALTER TABLE users ADD COLUMN IF NOT EXISTS organization_id TEXT')
            _add_column_if_missing(cursor, 'scans', 'organization_id', 'ALTER TABLE scans ADD COLUMN IF NOT EXISTS organization_id TEXT')
            _add_column_if_missing(cursor, 'reports', 'organization_id', 'ALTER TABLE reports ADD COLUMN IF NOT EXISTS organization_id TEXT')
            _add_column_if_missing(cursor, 'scans', 'compliance_score', 'ALTER TABLE scans ADD COLUMN IF NOT EXISTS compliance_score INTEGER NOT NULL DEFAULT 0')
            _add_column_if_missing(cursor, 'organizations', 'organization_type', 'ALTER TABLE organizations ADD COLUMN IF NOT EXISTS organization_type TEXT')
            _add_column_if_missing(cursor, 'organizations', 'official_mobile', 'ALTER TABLE organizations ADD COLUMN IF NOT EXISTS official_mobile TEXT')
            _add_column_if_missing(cursor, 'organizations', 'registered_address', 'ALTER TABLE organizations ADD COLUMN IF NOT EXISTS registered_address TEXT')
            _add_column_if_missing(cursor, 'organizations', 'state', 'ALTER TABLE organizations ADD COLUMN IF NOT EXISTS state TEXT')
            _add_column_if_missing(cursor, 'organizations', 'district', 'ALTER TABLE organizations ADD COLUMN IF NOT EXISTS district TEXT')
            _add_column_if_missing(cursor, 'organizations', 'pin_code', 'ALTER TABLE organizations ADD COLUMN IF NOT EXISTS pin_code TEXT')
            _add_column_if_missing(cursor, 'organizations', 'gstin', 'ALTER TABLE organizations ADD COLUMN IF NOT EXISTS gstin TEXT')
            _add_column_if_missing(cursor, 'organizations', 'registration_number', 'ALTER TABLE organizations ADD COLUMN IF NOT EXISTS registration_number TEXT')
            _add_column_if_missing(cursor, 'organizations', 'authorized_representative_name', 'ALTER TABLE organizations ADD COLUMN IF NOT EXISTS authorized_representative_name TEXT')
            _add_column_if_missing(cursor, 'organizations', 'authorized_representative_designation', 'ALTER TABLE organizations ADD COLUMN IF NOT EXISTS authorized_representative_designation TEXT')
            _add_column_if_missing(cursor, 'organizations', 'authorized_representative_contact', 'ALTER TABLE organizations ADD COLUMN IF NOT EXISTS authorized_representative_contact TEXT')
            _add_column_if_missing(cursor, 'organizations', 'website', 'ALTER TABLE organizations ADD COLUMN IF NOT EXISTS website TEXT')
            _add_column_if_missing(cursor, 'organizations', 'industry', 'ALTER TABLE organizations ADD COLUMN IF NOT EXISTS industry TEXT')
            _add_column_if_missing(cursor, 'complaints', 'scan_id', 'ALTER TABLE complaints ADD COLUMN IF NOT EXISTS scan_id TEXT')
            _add_column_if_missing(cursor, 'complaints', 'organization_id', 'ALTER TABLE complaints ADD COLUMN IF NOT EXISTS organization_id TEXT')
            _add_column_if_missing(cursor, 'complaints', 'state', 'ALTER TABLE complaints ADD COLUMN IF NOT EXISTS state TEXT')
            _add_column_if_missing(cursor, 'complaints', 'district', 'ALTER TABLE complaints ADD COLUMN IF NOT EXISTS district TEXT')
            _add_column_if_missing(cursor, 'complaints', 'admin_remark', 'ALTER TABLE complaints ADD COLUMN IF NOT EXISTS admin_remark TEXT')
            _add_column_if_missing(cursor, 'complaints', 'source', "ALTER TABLE complaints ADD COLUMN IF NOT EXISTS source TEXT NOT NULL DEFAULT 'USER_SUBMITTED'")
            _add_column_if_missing(cursor, 'complaints', 'updated_at', 'ALTER TABLE complaints ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()')
            _add_column_if_missing(cursor, 'complaint_status_history', 'administrative_remark', 'ALTER TABLE complaint_status_history ADD COLUMN IF NOT EXISTS administrative_remark TEXT')
            _add_column_if_missing(cursor, 'complaint_status_history', 'changed_at', 'ALTER TABLE complaint_status_history ADD COLUMN IF NOT EXISTS changed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()')
            _ensure_role_constraint(cursor)

            if _column_exists(cursor, 'scans', 'organization_id'):
                cursor.execute("CREATE INDEX IF NOT EXISTS scans_organization_id_idx ON scans(organization_id)")
            if _column_exists(cursor, 'reports', 'organization_id'):
                cursor.execute("CREATE INDEX IF NOT EXISTS reports_organization_id_idx ON reports(organization_id)")
            if _column_exists(cursor, 'scan_images', 'scan_id'):
                cursor.execute("CREATE INDEX IF NOT EXISTS scan_images_scan_id_idx ON scan_images(scan_id, sort_index)")
            if _column_exists(cursor, 'complaints', 'status'):
                cursor.execute("CREATE INDEX IF NOT EXISTS complaints_status_idx ON complaints(status)")
            if _column_exists(cursor, 'complaints', 'state') and _column_exists(cursor, 'complaints', 'district'):
                cursor.execute("CREATE INDEX IF NOT EXISTS complaints_jurisdiction_created_idx ON complaints(state, district, created_at DESC)")
            if _column_exists(cursor, 'complaints', 'source') and _column_exists(cursor, 'complaints', 'scan_id'):
                cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS complaints_auto_scan_unique_idx ON complaints(scan_id) WHERE source = 'AUTO_SCAN_VIOLATION' AND scan_id IS NOT NULL")
            if _column_exists(cursor, 'complaint_status_history', 'complaint_id'):
                cursor.execute("CREATE INDEX IF NOT EXISTS complaint_history_complaint_id_idx ON complaint_status_history(complaint_id, changed_at DESC)")

            if _column_exists(cursor, 'scans', 'user_id'):
                cursor.execute("CREATE INDEX IF NOT EXISTS scans_user_id_scanned_at_idx ON scans(user_id, scanned_at DESC)")
            if _column_exists(cursor, 'compliance_results', 'scan_id'):
                cursor.execute("CREATE INDEX IF NOT EXISTS compliance_results_scan_id_idx ON compliance_results(scan_id)")
            if _column_exists(cursor, 'reports', 'generated_at'):
                cursor.execute("CREATE INDEX IF NOT EXISTS reports_generated_at_idx ON reports(generated_at DESC)")

            seed_demo_users(cursor)

        connection.commit()
    STORAGE_DIR.mkdir(parents=True, exist_ok=True)


def seed_demo_users(cursor: psycopg.Cursor[Any]) -> None:
    demo_password = "Niriksha@123"
    demo_users = [
        ("demo-organization", "demo.organization@niriksha.in", "Demo Organization", "organization", "demo.organization@niriksha.in", None),
        ("demo-officer", "OFFICER001", "Demo Officer", "officer", "demo.officer@niriksha.in", "OFFICER001"),
        ("demo-admin", "ADMIN001", "Demo Administrator", "admin", "demo.admin@niriksha.in", None),
    ]
    for user_id, login_id, name, role, email, officer_id in demo_users:
        cursor.execute(
            """
            INSERT INTO users (id, login_id, name, password_hash, role, email, location, state, district, officer_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (login_id) DO NOTHING
            """,
            (user_id, login_id, name, _password_hash(demo_password), role, email, "Bengaluru", "Karnataka", "Bengaluru", officer_id),
        )

    cursor.execute(
        """
        INSERT INTO organizations (id, organization_name, organization_type, official_email, password_hash, registered_address, state, district)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (id) DO NOTHING
        """,
        ("demo-organization-record", "Demo Organization", "Private Company", "demo.organization@niriksha.in", _password_hash(demo_password), "Bengaluru", "Karnataka", "Bengaluru"),
    )
    cursor.execute("UPDATE users SET organization_id = %s WHERE id = %s AND organization_id IS NULL", ("demo-organization-record", "demo-organization"))

    cursor.execute(
        """
        INSERT INTO admins (id, admin_name, official_email, department, state, district, administrative_role)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (id) DO NOTHING
        """,
        ("demo-admin", "Demo Administrator", "demo.admin@niriksha.in", "Legal Metrology", "Karnataka", "Bengaluru", "District Admin"),
    )


def create_user(login_id: str, password: str, name: str, role: str, email: str | None = None, *, state: str | None = None, district: str | None = None, organization_name: str | None = None, organization_type: str | None = None, official_mobile: str | None = None, registered_address: str | None = None, pin_code: str | None = None, gstin: str | None = None, registration_number: str | None = None, authorized_representative_name: str | None = None, authorized_representative_designation: str | None = None, authorized_representative_contact: str | None = None, website: str | None = None, industry: str | None = None) -> dict[str, Any]:
    user_id = new_id("user")
    with connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO users (id, login_id, name, password_hash, role, email, location, state, district) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING *",
                (user_id, login_id, name, _password_hash(password), role, email, registered_address or district or state or "", state, district),
            )
            user = cursor.fetchone()
            if role == "organization":
                organization_id = new_id("org")
                cursor.execute(
                    "INSERT INTO organizations (id, organization_name, organization_type, official_email, official_mobile, password_hash, registered_address, state, district, pin_code, gstin, registration_number, authorized_representative_name, authorized_representative_designation, authorized_representative_contact, website, industry) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                    (organization_id, organization_name or name, organization_type or "Other", email or "", official_mobile or "", _password_hash(password), registered_address or "", state or "", district or "", pin_code or "", gstin or "", registration_number or "", authorized_representative_name or "", authorized_representative_designation or "", authorized_representative_contact or "", website or "", industry or ""),
                )
                cursor.execute("UPDATE users SET organization_id = %s WHERE id = %s", (organization_id, user_id))
                user["organization_id"] = organization_id
            if role == "admin":
                cursor.execute(
                    "INSERT INTO admins (id, admin_name, official_email, department, state, district, administrative_role) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                    (user_id, name, email or "", "Legal Metrology", state or "Bengaluru", district or "Bengaluru", "District Admin"),
                )
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
                cursor.execute("SELECT u.*, COALESCE(NULLIF(u.state, ''), a.state) AS state, COALESCE(NULLIF(u.district, ''), a.district) AS district FROM users u LEFT JOIN admins a ON a.id = u.id WHERE u.id = %s", (payload["sub"],))
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
