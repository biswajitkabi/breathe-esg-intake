# Decisions

Every ambiguity resolved during the build, with reasoning.

---

## SAP — Format Choice

**Decision:** Flat file CSV via MB51/ME2M transaction export.

**Alternatives considered:**
- IDoc: powerful but requires SAP BASIS config to set up an outbound port.
  No enterprise client will let you touch their IDoc configuration for
  a prototype integration.
- OData/BAPI: requires network access to the SAP system and OAuth setup.
  Most clients will not open firewall rules for a new vendor.
- Flat file: the SAP team runs a report (MB51 for material movements,
  ME2M for purchase orders), exports to CSV, and drops it in a shared
  folder or emails it. This is what actually happens in 90% of
  real enterprise ESG data collection.

**Subset handled:**
Material movement type 201 (goods issue to cost center) and 101
(goods receipt). This covers fuel drawn from storage and purchased
fuel delivered to site. We do not handle:
- Stock transfers between plants (movement 301/303)
- Returns (movement 122)
- Subcontracting (movement 541)

**German headers:** Real SAP exports in European configurations use
German column names. We handle both German and English via a header
alias map in the parser.

**Date formats:** SAP stores dates as YYYYMMDD internally. Exports
can render as DD.MM.YYYY depending on user locale settings.
We handle both.

---

## Utility — Format Choice

**Decision:** Portal CSV export.

**Alternatives considered:**
- PDF bill parsing: brittle, requires OCR or layout-specific templates.
  Every utility formats their PDF differently. Not practical for
  multi-site, multi-supplier portfolios.
- Utility API (e.g. Green Button / ESPI): only available from a subset
  of US utilities. UK utilities (where our sample client operates) do
  not offer standardised APIs for business customers.
- Portal CSV: every major UK utility (National Grid, EDF, SSE, EON)
  offers CSV export from their business portal. Facilities teams
  download this monthly. It is the realistic lowest-friction option.

**Billing period alignment:** We explicitly capture period_start and
period_end rather than assuming a calendar month. UK utility bills
run on a cycle from the meter read date — typically offset by
10-20 days from month start. We flag periods > 45 days or < 20 days
as suspicious.

**Emission factor:** We use DEFRA 2023 UK grid average
(0.20707 kgCO2e/kWh). In production this would be year-specific
and potentially location-based (different grid mixes by region).

---

## Travel — Format Choice

**Decision:** JSON file upload mimicking Concur itinerary API
batch export.

**Alternatives considered:**
- Live Concur API integration: requires OAuth, company-level token,
  and Concur admin approval. Not feasible for a prototype.
- Concur CSV expense export: available but loses trip structure —
  each expense line item is flat, losing the link between a flight
  and its associated hotel stay.
- JSON batch export: Concur's travel manager UI allows exporting
  itinerary data as JSON. This preserves the trip/segment hierarchy,
  matches the v4 itinerary API response shape, and is realistic
  for a quarterly ESG data collection workflow.

**Distance calculation:** Concur provides carbon in lbs for flights
using their own model, but the field is unreliable (sometimes null,
sometimes uses an outdated model). We recompute using DEFRA 2023
factors and great-circle distance. When origin/destination IATA
codes are present, we look up distance from a curated table.
When unknown, we fall back to 1500 km average and flag the record.

**Scope 3 Category 6:** Per GHG Protocol, business travel includes
flights, hotel stays, and ground transport. We compute and track
all three separately because they have different emission factors
and different data quality characteristics.

---

## Review Workflow

**Decision:** PENDING → APPROVED / REJECTED / FLAGGED, with LOCKED
as a terminal state after audit export.

**Why not auto-approve clean records?**
ESG data going to auditors requires a human in the loop. Auto-approval
would undermine the audit trail. Every approved record has a
reviewed_by and reviewed_at.

**Why FLAGGED as a separate status from REJECTED?**
FLAGGED means "needs attention but not wrong" — e.g. a very large
consumption value that could be correct but warrants a check.
REJECTED means "this row is bad data and should not be included."
Conflating them would lose nuance that auditors care about.

---

## Multi-tenancy

**Decision:** Tenant FK on every major table, enforced at the
query layer.

**What I would ask the PM:**
- Will analysts ever need to see data across multiple tenants
  (e.g. a parent company viewing subsidiaries)?
- Should tenant isolation be enforced at the database row level
  (Row Level Security in Postgres) or is application-layer filtering
  sufficient for this stage?

---

## Emission Factor Strategy

**Decision:** Hardcoded DEFRA 2023 factors in parsers for prototype.

**What I would ask the PM:**
- Do clients need to supply their own emission factors
  (e.g. a supplier-specific factor for their fuel mix)?
- Which reporting year's factors should be used — factors change
  annually and historical data should use the factor from that year.
- Should market-based Scope 2 factors (from energy attribute
  certificates) be supported alongside location-based?

In production, emission factors would be a separate database table
versioned by year, region, and source, not hardcoded constants.

---

## What I Would Ask the PM

1. How do clients actually deliver SAP data — email, SFTP, shared
   drive? This changes the ingestion trigger design.
2. How often does utility data arrive — monthly batch or near-
   real-time? Affects whether we need a scheduler.
3. Should rejected records be resubmittable, or is rejection final?
4. What does "locked for audit" mean operationally — PDF export,
   API handoff to an audit platform, or just a status flag?
5. Do we need to support natural gas and water in addition to
   electricity for utility data?