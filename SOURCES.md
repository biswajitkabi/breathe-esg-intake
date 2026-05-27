# Sources

Research notes for each data source, sample data rationale,
and what would break in production.

---

## 1. SAP — Fuel & Procurement

### What I researched
SAP MM (Materials Management) module stores goods movements in
table MSEG, linked to document headers in MKPF. The standard
report for extracting material movements is MB51. Export options:

- **IDoc (MATMAS, WMMBID01):** structured EDI format, requires
  outbound partner profile configuration in WE20. Used for
  system-to-system integration. Impractical for one-off ESG
  data extraction.
- **OData service (API_MATERIAL_DOCUMENT_SRV):** available in
  S/4HANA, requires network access and OAuth. Most clients
  will not expose this externally.
- **Flat file via MB51/ME2M:** analyst runs report, selects
  columns, exports to CSV. This is universal across all SAP
  versions (R/3, ECC, S/4HANA) and requires no technical setup.

**Chosen: flat file CSV.** Justification above.

### Column names I found
Real SAP MB51 export columns (German locale):
- WERKS — Werk (Plant)
- MATNR — Materialnummer (Material Number)
- MAKTX — Materialkurztext (Material Description)
- MENGE — Menge (Quantity)
- MEINS — Basismengeneinheit (Base Unit of Measure)
- LIFNR — Lieferant (Vendor)
- BLDAT — Belegdatum (Document Date, format YYYYMMDD)
- BWART — Bewegungsart (Movement Type)
- KOSTL — Kostenstelle (Cost Center)

### What my sample data looks like and why
- Semicolon delimiter — real SAP European locale exports use
  semicolons, not commas, because commas appear in number
  formatting (1.234,56)
- German column headers — real SAP exports in German system
  language
- YYYYMMDD dates — SAP internal date format
- Mixed units (L, KG, M3) — diesel is in litres, LPG in kg,
  natural gas in cubic metres. This is realistic.
- Plant codes 1000/2000/3000/4000 — SAP default plant code
  format is 4-digit numeric
- Intentional bad rows:
  - Row with empty WERKS — missing plant code, common when
    cost center postings bypass plant assignment
  - Row with PCE (piece) unit — non-energy material accidentally
    included in export
  - Row with negative quantity — reversal posting, should be
    excluded from emissions

### What would break in production
- Client uses company-specific movement types — our filter for
  201/101 would miss their fuel movements
- Material descriptions in a third language (Japanese, Chinese)
  — our keyword matching for fuel types would fail entirely
- Client has custom UOM (e.g. "BBL" for barrels) not in our
  normalisation table
- Very large exports (500k+ rows) would be slow without async
  processing and chunked reading
- Some SAP configs export numbers with comma decimal separators
  AND comma thousand separators — our parser handles one but
  not both simultaneously

---

## 2. Utility — Electricity

### What I researched
UK electricity billing for commercial/industrial customers:

- **Portal CSV:** all major UK suppliers (EDF, EON, SSE,
  National Grid, British Gas Business) provide a business
  portal with CSV export. Columns vary but always include
  meter identifier (MPAN in UK), billing period, and kWh.
- **PDF bill:** structured differently per supplier, requires
  OCR or template parsing. Not practical for multi-site.
- **Green Button / ESPI API:** US standard, not available
  from UK suppliers for business customers.
- **NEM12:** Australian interval meter format (30-min reads).
  Useful for load analysis but does not carry billing charges.

**Chosen: portal CSV.** Most universal for UK commercial clients.

UK-specific identifiers:
- MPAN (Meter Point Administration Number) — 21-digit unique
  identifier for each electricity supply point in the UK
- Tariff structures: LV-SME (small business), LV-MED (medium
  commercial), HV-IND (heavy industrial). Industrial sites have
  demand charges (£/kW) on top of consumption charges (£/kWh).
- Time-of-use: peak/off-peak split is standard for medium and
  large commercial customers.

### What my sample data looks like and why
- Billing periods offset from calendar months (e.g. Jan 15 –
  Feb 14) — UK meter reads are scheduled on fixed cycle dates,
  not month boundaries
- Mix of LV and HV tariff codes — realistic for a company with
  offices (LV) and a manufacturing plant (HV)
- Peak/offpeak split — standard for TOU tariffs
- demand_kw column — present for HV-IND sites, blank for SME
- Intentional bad rows:
  - Missing meter_id — site added mid-period, MPAN not yet
    registered on portal
  - 91-day billing period (MTR-006) — quarterly bill, which
    some smaller sites receive. Flagged as suspicious but valid.

### What would break in production
- Client has gas meters in addition to electricity — our parser
  only handles electricity kWh, not gas m3 or therms
- Supplier changes mid-year — new supplier, new portal, different
  CSV column names for same meter
- Half-hourly (HH) interval data instead of period totals —
  our model stores one row per billing period, not per interval
- Multiple supply points on one bill (some suppliers consolidate
  multi-site invoices)
- Non-UK clients with different grid emission factors — we
  hardcode DEFRA 2023 UK factor

---

## 3. Corporate Travel — Concur

### What I researched
SAP Concur exposes travel data via:

- **Itinerary API v4** (GET /travel/v4/trips): returns trip
  objects with typed segments (Air, Hotel, Car, Rail). Each
  air segment includes origin/destination IATA codes, cabin
  class, departure datetime, and a carbon_pounds field.
  The carbon_pounds field uses Concur's internal model —
  it is present but the model is not documented and changes
  without notice.
- **Expense API v3** (GET /expense/v3/reports): returns
  expense reports with line items. Less structured for travel
  — a flight appears as a single expense line, not a segment
  with origin/destination.
- **TripLink**: captures out-of-channel bookings. Same data
  shape as itinerary API but with some fields nulled out for
  privacy.

**Chosen: JSON file mimicking itinerary API v4 batch export.**
A travel manager with admin access can export all company trips
as JSON via the Concur admin portal. This matches the v4 API
response shape and is realistic for quarterly ESG data collection.

Distance calculation:
- Concur provides IATA codes, not distances
- We maintain a lookup table of common routes
- Unknown routes fall back to 1500 km (ICAO average short-haul)
  and are flagged for analyst review
- In production: use an airport distance API (e.g. Aviation
  Edge, or open IATA distance database)

Emission factors:
- We use DEFRA 2023 factors per passenger-km, including
  Radiative Forcing Index (RFI multiplier) which accounts for
  the higher warming impact of contrails at altitude
- Business class factor is 2.76x economy — reflects larger
  seat footprint per passenger

### What my sample data looks like and why
- Mix of cabin classes (ECONOMY, BUSINESS, FIRST,
  PREMIUM_ECONOMY) — realistic for a company where senior
  staff fly business
- Multiple segment types per trip (air + hotel + ground) —
  a real business trip always has multiple legs
- Routes chosen from our distance lookup table so most records
  compute accurately without the fallback flag
- Intentional bad rows (TRIP-006):
  - Empty IATA codes — booking made outside Concur (TripLink
    open booking), origin/destination not captured
  - 36-night hotel stay — data entry error, flagged
  - Zero distance ground transport — distance field not
    populated by travel agency

### What would break in production
- Rail travel in continental Europe — Concur categorises
  Eurostar and TGV bookings differently across regions.
  Our RAIL factor is a UK average and would be wrong for
  high-speed European rail (lower emissions).
- Rideshare (Uber/Lyft) captured via TripLink — distance
  is often not reported, our 20 km default is unreliable
- Multi-passenger bookings — if one booking covers 3
  travellers, Concur reports one trip. We count it as one
  person's emissions. Should be multiplied by passenger count.
- Currency normalisation — expense amounts are in trip
  currency, not normalised. Not used for emissions but
  would be needed for cost-per-tonne reporting.