# Data Model

## Overview

The data model is designed around four concerns:
1. Multi-tenancy — multiple client companies in one deployment
2. Source-of-truth preservation — raw data is never mutated
3. Normalized emission records — one row per activity event, reviewable
4. Audit trail — every status change is logged with who, what, when

---

## Entity Map

Tenant
└── IngestionBatch (many)
└── RawRecord (many)         ← immutable, source-of-truth
└── EmissionRecord (1) ← normalized, reviewable
└── AuditLog (many)
Tenant
└── PlantLookup (many)             ← SAP WERKS code decoder
Tenant
└── User (many)                    ← analyst/admin accounts

---

## Entities

### Tenant
Represents one client company. All data is scoped to a tenant.
Every query filters by `tenant_id` first — no cross-tenant data leakage.

| Field | Type | Notes |
|-------|------|-------|
| id | UUID | primary key |
| name | varchar | e.g. "Acme Corp" |
| slug | slug | unique, used in URLs |
| created_at | timestamp | |

---

### User
Extends Django's AbstractUser. Scoped to a Tenant.

| Field | Type | Notes |
|-------|------|-------|
| tenant | FK → Tenant | |
| role | enum | ADMIN / ANALYST / VIEWER |

Roles exist but full RBAC is not enforced in this prototype (see TRADEOFFS.md).

---

### IngestionBatch
One batch per file upload. Tracks what came in, from where, and whether
parsing succeeded.

| Field | Type | Notes |
|-------|------|-------|
| id | UUID | |
| tenant | FK | |
| source_type | enum | SAP / UTILITY / TRAVEL |
| uploaded_by | FK → User | nullable — system uploads allowed |
| uploaded_at | timestamp | |
| file_name | varchar | original filename preserved |
| status | enum | PROCESSING / DONE / FAILED |
| row_count | int | successfully parsed rows |
| error_count | int | rows that failed parsing |
| notes | text | error detail if status=FAILED |

---

### RawRecord
**Immutable.** Stores the exact original row as JSON.
Never updated after creation. This is the source-of-truth for auditors —
if an analyst edits a normalized record, the original is always recoverable here.

| Field | Type | Notes |
|-------|------|-------|
| id | UUID | |
| batch | FK → IngestionBatch | |
| raw_json | JSONField | original row, untouched |
| source_row_number | int | row number in original file |
| created_at | timestamp | |

**Why JSONField?** Each source type has a completely different shape.
A typed schema per source would require 3 separate raw tables or a complex
polymorphic setup. JSONField keeps it simple while preserving fidelity.

---

### EmissionRecord
The normalized, analyst-facing row. One per activity event:
one fuel purchase, one utility bill, one flight leg, one hotel stay.

**Scope mapping:**
- SAP fuel → Scope 1 (direct combustion, GHG Protocol)
- Utility electricity → Scope 2 (purchased energy)
- Travel (flights/hotels/ground) → Scope 3, Category 6 (business travel)

| Field | Type | Notes |
|-------|------|-------|
| id | UUID | |
| tenant | FK | |
| batch | FK → IngestionBatch | which upload produced this |
| raw_record | OneToOne → RawRecord | link back to source-of-truth |
| scope | int | 1 / 2 / 3 |
| category | enum | FUEL / PROCUREMENT / ELECTRICITY / FLIGHT / HOTEL / GROUND |
| activity_value | decimal(18,4) | as-ingested quantity |
| activity_unit | enum | L / GAL / KG / KWH / MWH / KM / MI / NIGHTS |
| activity_unit_normalized | decimal(18,4) | always in SI base unit (L, kWh, km) |
| co2e_kg | decimal(18,4) | kg CO2 equivalent, null if EF unavailable |
| emission_factor_used | varchar | e.g. "DEFRA 2023 grid: 0.20707 kgCO2e/kWh" |
| period_start | date | activity start date |
| period_end | date | activity end date |
| facility_name | varchar | plant / site / city |
| location_country | varchar | |
| employee_id | varchar | for travel records |
| vendor_name | varchar | for SAP records |
| description | text | human-readable summary |
| origin_iata | varchar | flights only |
| destination_iata | varchar | flights only |
| travel_class | varchar | flights / ground |
| meter_id | varchar | utility only |
| tariff_code | varchar | utility only |
| status | enum | PENDING / APPROVED / REJECTED / FLAGGED |
| flag_reason | text | auto-populated by parser or analyst |
| reviewed_by | FK → User | nullable |
| reviewed_at | timestamp | nullable |
| is_locked | bool | true after audit export — no edits |
| source_amended | bool | true if edited after ingestion |
| created_at | timestamp | |
| updated_at | timestamp | |

**Why decimal(18,4)?** Emission values span a huge range —
a single flight segment is ~800 kg CO2e, a large plant's annual
fuel is ~500,000 kg. 18 digits with 4 decimal places handles both
without floating-point rounding errors.

**Why separate activity_unit and activity_unit_normalized?**
We preserve the original unit for auditability (an analyst can
verify against the source document) while always having a
comparable normalized value for aggregation.

---

### AuditLog
Every status change or edit to an EmissionRecord is appended here.
Never updated or deleted — append-only.

| Field | Type | Notes |
|-------|------|-------|
| id | UUID | |
| emission_record | FK | |
| user | FK → User | nullable — system actions allowed |
| action | enum | CREATED / APPROVED / REJECTED / FLAGGED / EDITED / LOCKED |
| old_value_json | JSON | state before change |
| new_value_json | JSON | state after change |
| timestamp | timestamp | auto |
| note | text | analyst note |

---

### PlantLookup
Maps SAP WERKS plant codes (e.g. "1000", "4000") to human-readable
names. Required because SAP plant codes mean nothing without a
client-specific lookup table — "1000" at one company is London HQ,
at another it is a German factory.

| Field | Type | Notes |
|-------|------|-------|
| tenant | FK | per-tenant lookup |
| werks_code | varchar | e.g. "1000" |
| plant_name | varchar | e.g. "London HQ" |
| country | varchar | |
| region | varchar | |

Unique constraint on (tenant, werks_code).

---

## Indexes

```sql
INDEX (tenant_id, status)       -- analyst dashboard filter
INDEX (tenant_id, scope)        -- scope breakdown aggregation
INDEX (batch_id)                -- batch detail view
```

---

## Unit Normalisation

| Source unit | Normalised to | Factor |
|-------------|--------------|--------|
| L | L | 1.0 |
| GAL | L | 3.78541 |
| M3 | L | 1000.0 |
| KG | KG | 1.0 (mass, no volume conversion) |
| MWH | KWH | 1000.0 |
| KWH | KWH | 1.0 |
| KM | KM | 1.0 |
| MI | KM | 1.60934 |

---

## Emission Factors Used

| Category | Factor | Source |
|----------|--------|--------|
| Diesel | 2.6391 kg CO2e/L | DEFRA 2023 |
| Petrol/Gasoline | 2.3122 kg CO2e/L | DEFRA 2023 |
| LPG | 1.5550 kg CO2e/L | DEFRA 2023 |
| Natural Gas | 2.0400 kg CO2e/kg | DEFRA 2023 |
| UK Grid Electricity | 0.20707 kg CO2e/kWh | DEFRA 2023 (location-based) |
| Flight Economy | 0.1553 kg CO2e/pkm | DEFRA 2023 with RFI |
| Flight Business | 0.4286 kg CO2e/pkm | DEFRA 2023 with RFI |
| Flight First | 0.5765 kg CO2e/pkm | DEFRA 2023 with RFI |
| Hotel (avg) | 31.0 kg CO2e/room/night | IEA average |
| Ground (taxi/car) | 0.1491 kg CO2e/km | DEFRA 2023 |
| Ground (rail) | 0.0410 kg CO2e/km | DEFRA 2023 |