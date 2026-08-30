# NIRIKSHA Legal Metrology Compliance

AI-powered compliance checking of packaged commodities under Legal Metrology rules. The existing Gemini extraction and Python `compliance_engine` remain the source of scan results; PostgreSQL stores the authenticated users, real scans, rule outcomes, and generated reports.

## Local setup

1. Create or open your Supabase project. In the Supabase dashboard, open **Connect**, choose **Shared Pooler → Session mode**, and copy its PostgreSQL connection string. Session mode uses the IPv4-compatible Supavisor endpoint and is suitable for this persistent Python backend.
2. Install Python dependencies from the repository root:

   ```powershell
   py -3 -m pip install -r requirements.txt
   ```

3. Copy `.env.example` to `.env` and set `DATABASE_URL`, `TOKEN_SECRET`, and `GEMINI_API_KEY`. Keep `.env` private; it is ignored by Git. Set `VITE_API_BASE_URL` in `project/.env` to the same port used by Uvicorn (for example, `http://127.0.0.1:8003`). Restart Vite after changing it.
4. Initialize the schema and idempotent demo users in Supabase:

   ```powershell
   py -3 db_init.py
   ```

   The backend also runs the same initialization automatically at startup. The created PostgreSQL tables are `users`, `scans`, `compliance_results`, and `reports`.
5. Start the backend from the repository root:

   ```powershell
   py -3 -m uvicorn server:app --host 127.0.0.1 --port 8003
   ```

6. In a second terminal, install and start the frontend:

   ```powershell
   cd project
   npm install
   npm run dev
   ```

## Development accounts

- Officer: `officer123` / `123456` — can generate, view, and download official reports.
- Consumer: `user123` / `123456` — can scan and view only their own scan history; official report generation is unavailable.

The login screen's CAPTCHA remains a presentation-level prototype control. Passwords are stored as PBKDF2 hashes, and the API issues a signed short-lived session token. PostgreSQL credentials and Gemini keys are never sent to the browser.

## Persistence workflow

`POST /api/scan` authenticates the user, runs the unchanged Gemini → `compliance_engine` flow, stores the actual extracted observations and rule outcomes, and returns the persisted scan. Officers can call `POST /api/reports/{scan_id}` to generate a real ReportLab PDF stored under `IMAGE_STORAGE_DIR/reports`; report metadata and its `scan_id` are stored in PostgreSQL. The reports and PDF endpoints enforce officer access.
