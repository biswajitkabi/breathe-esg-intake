# Breathe ESG — Data Intake Prototype

A Django REST + React prototype for ingesting, normalizing, and reviewing 
emissions data from three enterprise sources before it goes to auditors.

Built by Biswajit Kabi

---

## What It Does

Enterprise ESG data arrives in messy, inconsistent formats from multiple 
systems. This app ingests that data, normalizes it into a common emissions 
model, and gives analysts a dashboard to review, flag, and approve rows 
before they're locked for audit.

---

## Three Data Sources

| Source | Format | Ingestion | Scope |
|--------|--------|-----------|-------|
| SAP Fuel & Procurement | Semicolon-delimited CSV (MB51 export) | File upload | Scope 1 |
| Utility Electricity | Portal CSV export | File upload | Scope 2 |
| Corporate Travel (Concur) | JSON batch export | File upload | Scope 3 |

Each source was researched from real-world formats before any code was written.
See `SOURCES.md` for full research notes.

---

## Architecture
Frontend (React + Vite + Tailwind) → Vercel
Backend (Django REST Framework)    → Railway
Database (PostgreSQL)              → Neon

---

## Key Design Decisions

- **RawRecord is immutable** — original data is never mutated, always recoverable
- **EmissionRecord is normalized** — one row per activity event with scope, 
  unit normalization, and computed CO2e
- **AuditLog is append-only** — every approve/reject/edit is tracked with user and timestamp
- **Multi-tenant from day one** — all data scoped to a Tenant, no cross-client leakage

Full reasoning in `DECISIONS.md`, `MODEL.md`, `TRADEOFFS.md`.

---

## Live Demo

- **App:** https://breathe-esg-intake.vercel.app
- **Backend:** https://breathe-esg-intake-production.up.railway.app

**Login credentials:**
username: admin
password: Admin@123

---

## How to Use

1. **Login** with the credentials above
2. Go to **Upload Data** — upload sample files from `sample_data/` folder:
   - `sap_fuel_export.csv` → select SAP source
   - `utility_electricity.csv` → select Utility source
   - `travel_concur_export.json` → select Travel source
3. Go to **Records** — see all ingested rows with scope, CO2e, and status
4. Use filters to find **FLAGGED** rows — these were auto-flagged by the parser
5. **Approve**, **Reject**, or **Flag** rows individually or in bulk
6. Go to **Dashboard** — see summary stats by scope and source

---

## Sample Data

Sample files are in `sample_data/`. Each file includes intentionally problematic 
rows to demonstrate parser flagging:

- **SAP:** missing plant code, negative quantity, unknown unit (PCE)
- **Utility:** missing meter ID, 91-day billing period
- **Travel:** missing IATA codes, 36-night hotel stay, zero-distance ground transport

---

## Local Setup

```bash
# Backend
cd backend
python -m venv venv
venv\Scripts\activate        # Windows
pip install -r requirements.txt
cp .env.example .env         # fill in DATABASE_URL
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver

# Frontend
cd frontend
npm install
npm run dev
```

---

## Project Structure
breathe-esg-intake/
├── backend/
│   ├── apps/
│   │   ├── core/          # models, auth, audit
│   │   ├── ingestion/     # parsers + upload API
│   │   └── review/        # review dashboard API
│   └── config/            # Django settings
├── frontend/
│   └── src/
│       ├── pages/         # Dashboard, Upload, Records, Login
│       └── components/    # StatCard, StatusBadge, ScopeBadge
├── sample_data/           # realistic test files
├── MODEL.md
├── DECISIONS.md
├── TRADEOFFS.md
└── SOURCES.md

---

## Documentation

| File | Contents |
|------|----------|
| `MODEL.md` | Full data model with reasoning |
| `DECISIONS.md` | Every ambiguity resolved and why |
| `TRADEOFFS.md` | Three things deliberately not built |
| `SOURCES.md` | Real-world research per data source |