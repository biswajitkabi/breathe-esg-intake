"""
Utility electricity CSV parser.

Real-world source: portal CSV export from utility providers (e.g. PG&E,
National Grid, EDF business portal). Facilities teams download these monthly.

Columns we expect:
  account_number / meter_id  — meter or NMI identifier
  site_name / facility       — human-readable site
  billing_period_start       — date (various formats)
  billing_period_end         — date
  consumption_kwh            — total kWh for period
  peak_kwh                   — peak usage (optional)
  offpeak_kwh                — off-peak usage (optional)
  demand_kw                  — peak demand in kW (optional)
  tariff_code                — rate schedule code
  total_cost                 — billed amount (optional, informational)
  currency                   — GBP/USD/EUR etc.

Key real-world quirks handled:
  - Billing periods don't align to calendar months (e.g. Mar 15 – Apr 14)
  - Some portals export MWh not kWh
  - Tariff code may be absent for smaller sites
  - consumption_kwh sometimes uses comma thousand separators
"""

import csv
import io
from datetime import datetime, date
from decimal import Decimal, InvalidOperation

# UK grid emission factor kg CO2e per kWh (DEFRA 2023 — location-based)
# In production this would be country/year specific
GRID_EMISSION_FACTOR_KG_PER_KWH = Decimal('0.20707')

HEADER_MAP = {
    'ACCOUNT_NUMBER': 'meter_id',   'ACCOUNT': 'meter_id',
    'METER_ID': 'meter_id',         'METER': 'meter_id',
    'NMI': 'meter_id',              'MPAN': 'meter_id',
    'SITE_NAME': 'site_name',       'SITE': 'site_name',
    'FACILITY': 'site_name',        'LOCATION': 'site_name',
    'BILLING_PERIOD_START': 'period_start',  'PERIOD_START': 'period_start',
    'START_DATE': 'period_start',   'FROM': 'period_start',
    'BILLING_PERIOD_END': 'period_end',      'PERIOD_END': 'period_end',
    'END_DATE': 'period_end',       'TO': 'period_end',
    'CONSUMPTION_KWH': 'kwh',       'KWH': 'kwh',
    'USAGE_KWH': 'kwh',             'ENERGY_KWH': 'kwh',
    'CONSUMPTION_MWH': 'mwh',       'MWH': 'mwh',
    'USAGE_MWH': 'mwh',
    'PEAK_KWH': 'peak_kwh',
    'OFFPEAK_KWH': 'offpeak_kwh',   'OFF_PEAK_KWH': 'offpeak_kwh',
    'DEMAND_KW': 'demand_kw',
    'TARIFF_CODE': 'tariff_code',   'RATE': 'tariff_code',
    'TOTAL_COST': 'total_cost',     'AMOUNT': 'total_cost',
    'CURRENCY': 'currency',
}


def _normalise_header(raw: str) -> str:
    clean = raw.strip().upper().replace(' ', '_').replace('-', '_').replace('/', '_')
    return HEADER_MAP.get(clean, clean.lower())


def _parse_date(raw: str) -> date:
    raw = raw.strip()
    for fmt in ('%Y-%m-%d', '%d/%m/%Y', '%m/%d/%Y', '%d-%m-%Y',
                '%d %b %Y', '%d %B %Y', '%Y%m%d'):
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"Cannot parse date: {raw!r}")


def _parse_decimal(raw: str) -> Decimal:
    clean = raw.strip().replace(',', '')  # remove thousand separators
    return Decimal(clean)


def parse_utility_csv(file_content: bytes) -> tuple[list[dict], list[dict]]:
    """
    Parse utility electricity CSV.

    Returns:
        records — list of normalised dicts
        errors  — list of {row, raw, reason}
    """
    records = []
    errors = []

    sample = file_content[:2048].decode('utf-8', errors='replace')
    delimiter = ';' if sample.count(';') > sample.count(',') else ','

    reader = csv.DictReader(
        io.StringIO(file_content.decode('utf-8', errors='replace')),
        delimiter=delimiter
    )

    raw_fields = reader.fieldnames or []
    norm_fields = {f: _normalise_header(f) for f in raw_fields}

    for row_num, raw_row in enumerate(reader, start=2):
        row = {norm_fields.get(k, k.lower()): v for k, v in raw_row.items()}

        try:
            meter_id  = row.get('meter_id', '').strip()
            site_name = row.get('site_name', '').strip()
            start_raw = row.get('period_start', '').strip()
            end_raw   = row.get('period_end', '').strip()
            tariff    = row.get('tariff_code', '').strip()

            if not start_raw or not end_raw:
                raise ValueError("Missing billing period start or end date")

            period_start = _parse_date(start_raw)
            period_end   = _parse_date(end_raw)

            if period_end < period_start:
                raise ValueError(f"period_end {period_end} is before period_start {period_start}")

            # Consumption — prefer kWh, fall back to MWh
            kwh_raw = row.get('kwh', '').strip()
            mwh_raw = row.get('mwh', '').strip()

            if kwh_raw:
                kwh = _parse_decimal(kwh_raw)
            elif mwh_raw:
                kwh = _parse_decimal(mwh_raw) * Decimal('1000')
            else:
                raise ValueError("No consumption value found (expected kwh or mwh column)")

            if kwh <= 0:
                raise ValueError(f"Non-positive consumption: {kwh} kWh")

            co2e_kg = kwh * GRID_EMISSION_FACTOR_KG_PER_KWH

            # Billing period sanity — warn if > 45 days (unusual)
            days = (period_end - period_start).days
            flags = []
            if days > 45:
                flags.append(f"Billing period is {days} days — unusually long")
            if days < 20:
                flags.append(f"Billing period is only {days} days — check dates")
            if kwh > 500_000:
                flags.append(f"Very high consumption: {kwh} kWh")
            if not meter_id:
                flags.append("No meter ID — cannot uniquely identify supply point")

            records.append({
                'scope': 2,
                'category': 'ELECTRICITY',
                'activity_value': kwh,
                'activity_unit': 'KWH',
                'activity_unit_normalized': kwh,
                'co2e_kg': co2e_kg,
                'emission_factor_used': f'DEFRA 2023 grid: {GRID_EMISSION_FACTOR_KG_PER_KWH} kgCO2e/kWh',
                'period_start': period_start,
                'period_end': period_end,
                'facility_name': site_name,
                'meter_id': meter_id,
                'tariff_code': tariff,
                'flag_reason': '; '.join(flags),
                'status': 'FLAGGED' if flags else 'PENDING',
                '_raw_row': raw_row,
                '_row_num': row_num,
            })

        except (ValueError, InvalidOperation) as e:
            errors.append({'row': row_num, 'raw': dict(raw_row), 'reason': str(e)})

    return records, errors