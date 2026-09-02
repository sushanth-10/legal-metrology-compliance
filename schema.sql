-- Reference schema for NIRIKSHA. The backend applies the same idempotent DDL
-- automatically at startup and seeds three development accounts.
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
CREATE INDEX IF NOT EXISTS complaints_status_idx ON complaints(status);
CREATE INDEX IF NOT EXISTS complaints_jurisdiction_created_idx ON complaints(state, district, created_at DESC);
CREATE UNIQUE INDEX IF NOT EXISTS complaints_auto_scan_unique_idx ON complaints(scan_id) WHERE source = 'AUTO_SCAN_VIOLATION' AND scan_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS complaint_history_complaint_id_idx ON complaint_status_history(complaint_id, changed_at DESC);
