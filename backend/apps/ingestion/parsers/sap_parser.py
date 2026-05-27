"""
SAP flat-file CSV parser.

Real SAP MM exports (via MB51 or ME2M transaction) use semicolon-delimited
CSVs with German column headers in some configs, YYYYMMDD dates, and mixed
units (L, GAL, KG, M3). We handle a realistic subset of that here.

Columns we expect (tolerating both English and German headers):
  WERKS / Werk         — plant code
  MATNR / Material     — material number
  MAKTX / Bezeichnung  — material description
  MENGE / Menge        — quantity
  MEINS / ME           — unit of measure
  LIFNR / Lieferant    — vendor number
  BLDAT / Belegdatum   — document date (YYYYMMDD or DD.MM.YYYY)
  BWART / Bew.Art      — movement type (101=GR, 201=GI to cost center)
  KOSTL / Kostenstelle — cost center (optional)
"""

import csv
import io
from datetime import datetime, date
from decimal import Decimal, InvalidOperation

# Emission factors kg CO2e per litre (approximate, for prototype)
# Source: IPCC / DEFRA 2023 factors
EMISSION_FACTORS = {
    'DIESEL':   Decimal('2.6391'),
    'PETROL':   Decimal('2.3122'),
    'GASOLINE': Decimal('2.3122'),
    'NATGAS':   Decimal('2.0400'),  # per kg
    'LPG':      Decimal('1.5550'),
    'DEFAULT':  Decimal('2.5000'),
}

# Unit normalisation to litres
UNIT_TO_LITRES = {
    'L':   Decimal('1.0'),
    'LTR': Decimal('1.0'),
    'GAL': Decimal('3.78541'),
    'GL':  Decimal('3.78541'),
    'M3':  Decimal('1000.0'),
    'KG':  None,   # mass — can't convert to litres without density
}

# Header aliases: normalise German/English headers to internal keys
HEADER_MAP = {
    'WERKS': 'plant_code',    'WERK': 'plant_code',
    'MATNR': 'material_no',   'MATERIAL': 'material_no',
    'MAKTX': 'description',   'BEZEICHNUNG': 'description',   'TEXT': 'description',
    'MENGE': 'quantity',      'MENGE_EH': 'quantity',
    'MEINS': 'unit',          'ME': 'unit',                    'EINHEIT': 'unit',
    'LIFNR': 'vendor_no',     'LIEFERANT': 'vendor_no',
    'BLDAT': 'doc_date',      'BELEGDATUM': 'doc_date',        'DATUM': 'doc_date',
    'BWART': 'movement_type', 'BEW_ART': 'movement_type',
    'KOSTL': 'cost_center',   'KOSTENSTELLE': 'cost_center',
}

FUEL_KEYWORDS = ['DIESEL', 'PETROL', 'GASOLINE', 'FUEL', 'KRAFTSTOFF',
                 'LPG', 'NATGAS', 'GAS', 'OIL', 'BENZIN', 'HEIZOL']


def _normalise_header(raw: str) -> str:
    clean = raw.strip().upper().replace(' ', '_').replace('.', '_').replace('-', '_')
    return HEADER_MAP.get(clean, clean.lower())


def _parse_date(raw: str) -> date:
    raw = raw.strip()
    for fmt in ('%Y%m%d', '%d.%m.%Y', '%Y-%m-%d', '%d/%m/%Y', '%m/%d/%Y'):
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"Cannot parse date: {raw!r}")


def _parse_quantity(raw: str) -> Decimal:
    # SAP sometimes uses comma as decimal separator (European locale)
    clean = raw.strip().replace(',', '.')
    # Remove thousand separators (period used as thousand sep in German)
    # Heuristic: if there are multiple dots, treat all but last as thousand sep
    parts = clean.split('.')
    if len(parts) > 2:
        clean = ''.join(parts[:-1]) + '.' + parts[-1]
    return Decimal(clean)


def _infer_emission_factor(description: str, material_no: str) -> tuple[str, Decimal]:
    text = (description + ' ' + material_no).upper()
    for keyword in FUEL_KEYWORDS:
        if keyword in text:
            factor = EMISSION_FACTORS.get(keyword, EMISSION_FACTORS['DEFAULT'])
            return keyword, factor
    return 'DEFAULT', EMISSION_FACTORS['DEFAULT']


def _is_fuel_material(description: str, material_no: str) -> bool:
    text = (description + ' ' + material_no).upper()
    return any(k in text for k in FUEL_KEYWORDS)


def _normalise_to_litres(quantity: Decimal, unit: str) -> tuple[Decimal, str]:
    u = unit.strip().upper()
    factor = UNIT_TO_LITRES.get(u)
    if factor is not None:
        return quantity * factor, 'L'
    # KG or unknown — keep as-is, flag it
    return quantity, unit


def parse_sap_csv(file_content: bytes) -> tuple[list[dict], list[dict]]:
    """
    Parse SAP flat-file CSV.

    Returns:
        records  — list of normalised dicts ready for EmissionRecord creation
        errors   — list of {row: int, raw: dict, reason: str}
    """
    records = []
    errors = []

    # Detect delimiter — SAP exports use semicolon or comma
    sample = file_content[:2048].decode('utf-8', errors='replace')
    delimiter = ';' if sample.count(';') > sample.count(',') else ','

    reader = csv.DictReader(
        io.StringIO(file_content.decode('utf-8', errors='replace')),
        delimiter=delimiter
    )

    # Normalise headers
    raw_fields = reader.fieldnames or []
    norm_fields = {f: _normalise_header(f) for f in raw_fields}

    for row_num, raw_row in enumerate(reader, start=2):   # start=2: row 1 is header
        # Remap keys
        row = {norm_fields.get(k, k.lower()): v for k, v in raw_row.items()}

        try:
            # Required fields
            plant_code  = row.get('plant_code', '').strip()
            material_no = row.get('material_no', '').strip()
            description = row.get('description', '').strip()
            quantity_raw = row.get('quantity', '').strip()
            unit_raw    = row.get('unit', '').strip()
            date_raw    = row.get('doc_date', '').strip()

            if not quantity_raw or not date_raw:
                raise ValueError("Missing quantity or date")

            quantity = _parse_quantity(quantity_raw)
            if quantity <= 0:
                raise ValueError(f"Non-positive quantity: {quantity}")

            doc_date = _parse_date(date_raw)

            # Normalise unit
            qty_normalised, unit_normalised = _normalise_to_litres(quantity, unit_raw)

            # Only include fuel/energy materials for Scope 1
            is_fuel = _is_fuel_material(description, material_no)
            scope = 1 if is_fuel else 1   # procurement is still Scope 1 or 3
            category = 'FUEL' if is_fuel else 'PROCUREMENT'

            # Compute CO2e
            ef_name, ef_value = _infer_emission_factor(description, material_no)
            co2e_kg = qty_normalised * ef_value if unit_normalised == 'L' else None

            # Flag suspicious rows
            flags = []
            if quantity > 100_000:
                flags.append(f"Unusually large quantity: {quantity} {unit_raw}")
            if not plant_code:
                flags.append("Missing plant code (WERKS)")
            if unit_raw.upper() not in UNIT_TO_LITRES:
                flags.append(f"Unknown unit {unit_raw!r} — CO2e not computed")

            records.append({
                'scope': scope,
                'category': category,
                'activity_value': quantity,
                'activity_unit': unit_raw.upper() or 'OTHER',
                'activity_unit_normalized': qty_normalised,
                'co2e_kg': co2e_kg,
                'emission_factor_used': ef_name,
                'period_start': doc_date,
                'period_end': doc_date,
                'facility_name': plant_code,
                'vendor_name': row.get('vendor_no', '').strip(),
                'description': description,
                'flag_reason': '; '.join(flags),
                'status': 'FLAGGED' if flags else 'PENDING',
                '_raw_row': raw_row,
                '_row_num': row_num,
            })

        except (ValueError, InvalidOperation, KeyError) as e:
            errors.append({
                'row': row_num,
                'raw': dict(raw_row),
                'reason': str(e),
            })

    return records, errors