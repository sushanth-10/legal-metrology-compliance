# NIRIKSHA

NIRIKSHA is an AI-powered compliance monitoring platform for packaged commodities under Indian legal metrology requirements. The system helps organizations, officers, and administrators assess product compliance by scanning packaging, extracting key information from labels, validating it against legal rules, and generating compliance reports and complaint workflows.

## Project Overview

The platform is designed around a role-based workflow:

- Organization users register and scan packaged products
- Officers manage inspections and review outcomes
- Admins monitor complaints, update status, and oversee compliance operations
- The backend stores scanned data, compliance outcomes, reports, complaints, and evidence in PostgreSQL/Supabase

The application combines OCR, AI extraction, rule-based validation, document generation, and secure storage into a single compliance workflow.

## Core Features

- Product image upload and scan intake
- OCR-based extraction using Google Cloud Vision
- AI interpretation using Google Gemini
- Rule-based compliance evaluation through the Python compliance engine
- Organization, officer, and admin authentication flows
- Complaint registration and admin-driven status management
- Report generation in PDF format
- Evidence image storage and scan history tracking
- Supabase-backed cloud storage and database persistence

## Technology Stack

### Frontend
- React
- TypeScript
- Vite
- Tailwind CSS
- JavaScript/HTML/CSS
- Lucide React icons

### Backend
- Python
- FastAPI
- Uvicorn
- PostgreSQL access through psycopg
- Token-based authentication and secure session handling

### AI and OCR
- Google Cloud Vision OCR
- Google Gemini AI
- Python compliance engine for validation logic

### Database and Storage
- PostgreSQL
- Supabase Postgres
- Supabase Storage
- Prisma tooling for project configuration

### Reporting and Documents
- ReportLab for PDF generation
- jsPDF for frontend document handling

### Supporting Tools
- Python dotenv for environment management
- ESLint for frontend linting
- Node.js tooling for Vite and project setup

## Architecture

The application follows a modular flow:

1. User uploads a product image or package image
2. Backend validates the request and authenticates the user
3. OCR extracts text from the label and packaging
4. Gemini interprets the extracted content
5. Python compliance engine compares results to legal metrology rules
6. Compliance results are stored in PostgreSQL
7. A PDF report is generated and saved
8. Evidence images and scan metadata are stored in Supabase Storage
9. Complaints and status updates are tracked for admin/officer review

## Role-Based Model

The application is structured around three main operational roles:

- Organization: registers and scans products, manages its compliance records
- Officer: reviews and supports compliance operations
- Admin: manages complaints, updates workflow status, and oversees system operations

## Security Considerations

- Sensitive credentials are kept in environment variables, not in frontend code
- PostgreSQL and Gemini keys are not exposed to the browser
- Passwords are stored using PBKDF2 hashing
- Supabase keys and storage are managed through backend configuration

## Project Structure

- `server.py` — FastAPI backend and API routes
- `database.py` — database initialization, schema creation, auth helpers, and seed users
- `pdf_reports.py` — PDF report generation
- `compliance_engine/` — rule-based compliance evaluation logic
- `project/` — React frontend application
- `storage/` — local storage for evidence and reports
- `tests/` — application test files

## Local Setup

1. Install Python dependencies:

   ```powershell
   py -3 -m pip install -r requirements.txt
   ```

2. Configure environment variables in `.env` with your database, Gemini, and Supabase values.

3. Initialize the database schema:

   ```powershell
   py -3 db_init.py
   ```

4. Start the backend:

   ```powershell
   py -3 -m uvicorn server:app --host 127.0.0.1 --port 8001
   ```

5. Start the frontend from the `project` folder:

   ```powershell
   cd project
   npm install
   npm run dev
   ```

## Notes

This project combines AI-based classification, OCR, rule validation, organizational workflows, and evidence tracking into a practical compliance system intended for legal metrology enforcement. It is designed to support both operational oversight and compliance reporting in a real-world government/regulatory environment.
