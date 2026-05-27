"""
Corporate travel JSON parser.

Real-world source: Concur Expense/Itinerary API export batch (v3/v4).
Travel managers export this periodically as a JSON file from the TMC dashboard.

We parse a JSON array of trip records. Each record may contain segments:
  - air     : origin_iata, destination_iata, cabin_class, departure_date
  - hotel   : check_in, check_out, city, country, nights
  - ground  : transport_type (taxi/rental/rail), distance_km, date

Concur's own carbon field (carbon_pounds) is present for flights
in the itinerary API but unreliable — we recompute using DEFRA factors.

Scope 3, Category 6 (Business Travel) per GHG Protocol.
"""

import json
from datetime import datetime, date, timedelta
from decimal import Decimal

# Flight emission factors kg CO2e per passenger-km (DEFRA 2023, with RFI)
FLIGHT_FACTORS = {
    'ECONOMY':        Decimal('0.1553'),
    'PREMIUM_ECONOMY':Decimal('0.2360'),
    'BUSINESS':       Decimal('0.4286'),
    'FIRST':          Decimal('0.5765'),
    'UNKNOWN':        Decimal('0.1953'),  # weighted average
}

# Hotel emission factors kg CO2e per room per night (IEA/DEFRA region averages)
HOTEL_FACTOR_PER_NIGHT = Decimal('31.0')

# Ground transport kg CO2e per km
GROUND_FACTORS = {
    'TAXI':     Decimal('0.1491'),
    'RENTAL':   Decimal('0.1680'),
    'RAIL':     Decimal('0.0410'),
    'BUS':      Decimal('0.0890'),
    'RIDESHARE':Decimal('0.1491'),
    'UNKNOWN':  Decimal('0.1491'),
}

# Approximate great-circle distances for common routes (km)
# In production: use an airport distance API
IATA_DISTANCES = {
    ('LHR', 'JFK'): 5540, ('JFK', 'LHR'): 5540,
    ('LHR', 'DXB'): 5480, ('DXB', 'LHR'): 5480,
    ('BOM', 'DEL'): 1150, ('DEL', 'BOM'): 1150,
    ('SFO', 'ORD'): 2960, ('ORD', 'SFO'): 2960,
    ('CDG', 'FRA'): 450,  ('FRA', 'CDG'): 450,
    ('SYD', 'MEL'): 710,  ('MEL', 'SYD'): 710,
}
AVG_FLIGHT_DISTANCE_KM = Decimal('1500')   # fallback if codes unknown


def _estimate_flight_distance(origin: str, dest: str) -> Decimal:
    key = (origin.upper(), dest.upper())
    dist = IATA_DISTANCES.get(key)
    return Decimal(str(dist)) if dist else AVG_FLIGHT_DISTANCE_KM


def _parse_date(raw) -> date:
    if isinstance(raw, date):
        return raw
    raw = str(raw).strip()
    for fmt in ('%Y-%m-%d', '%Y-%m-%dT%H:%M:%S', '%Y-%m-%dT%H:%M:%SZ',
                '%d/%m/%Y', '%m/%d/%Y'):
        try:
            return datetime.strptime(raw[:19], fmt[:len(raw[:19])]).date()
        except ValueError:
            continue
    raise ValueError(f"Cannot parse date: {raw!r}")


def _parse_air_segment(seg: dict, row_num: int) -> dict:
    origin  = str(seg.get('origin_iata') or seg.get('origin') or '').strip().upper()
    dest    = str(seg.get('destination_iata') or seg.get('destination') or '').strip().upper()
    cabin   = str(seg.get('cabin_class') or seg.get('class') or 'UNKNOWN').strip().upper()
    dep_raw = seg.get('departure_date') or seg.get('date') or ''
    emp_id  = str(seg.get('employee_id') or seg.get('traveler_id') or '')

    dep_date = _parse_date(dep_raw)
    distance_km = _estimate_flight_distance(origin, dest)
    ef = FLIGHT_FACTORS.get(cabin, FLIGHT_FACTORS['UNKNOWN'])
    co2e_kg = distance_km * ef

    flags = []
    if not origin or not dest:
        flags.append("Missing origin or destination IATA code — using average distance")
    if cabin == 'UNKNOWN':
        flags.append("Cabin class unknown — using weighted average emission factor")
    if distance_km == AVG_FLIGHT_DISTANCE_KM:
        flags.append(f"Route {origin}→{dest} not in distance table — using fallback {AVG_FLIGHT_DISTANCE_KM} km")

    return {
        'scope': 3,
        'category': 'FLIGHT',
        'activity_value': distance_km,
        'activity_unit': 'KM',
        'activity_unit_normalized': distance_km,
        'co2e_kg': co2e_kg,
        'emission_factor_used': f'DEFRA 2023 flight {cabin}: {ef} kgCO2e/pkm',
        'period_start': dep_date,
        'period_end': dep_date,
        'origin_iata': origin,
        'destination_iata': dest,
        'travel_class': cabin,
        'employee_id': emp_id,
        'description': f"Flight {origin}→{dest} ({cabin})",
        'flag_reason': '; '.join(flags),
        'status': 'FLAGGED' if flags else 'PENDING',
    }


def _parse_hotel_segment(seg: dict, row_num: int) -> dict:
    check_in_raw  = seg.get('check_in') or seg.get('start_date') or ''
    check_out_raw = seg.get('check_out') or seg.get('end_date') or ''
    city    = str(seg.get('city') or '').strip()
    country = str(seg.get('country') or '').strip()
    emp_id  = str(seg.get('employee_id') or seg.get('traveler_id') or '')

    check_in  = _parse_date(check_in_raw)
    check_out = _parse_date(check_out_raw)
    nights = max((check_out - check_in).days, 1)

    co2e_kg = Decimal(str(nights)) * HOTEL_FACTOR_PER_NIGHT

    flags = []
    if nights > 30:
        flags.append(f"Stay of {nights} nights — check dates")

    return {
        'scope': 3,
        'category': 'HOTEL',
        'activity_value': Decimal(str(nights)),
        'activity_unit': 'NIGHTS',
        'activity_unit_normalized': Decimal(str(nights)),
        'co2e_kg': co2e_kg,
        'emission_factor_used': f'IEA hotel avg: {HOTEL_FACTOR_PER_NIGHT} kgCO2e/room/night',
        'period_start': check_in,
        'period_end': check_out,
        'location_country': country,
        'facility_name': city,
        'employee_id': emp_id,
        'description': f"Hotel in {city}, {country} ({nights} nights)",
        'flag_reason': '; '.join(flags),
        'status': 'FLAGGED' if flags else 'PENDING',
    }


def _parse_ground_segment(seg: dict, row_num: int) -> dict:
    transport_type = str(seg.get('transport_type') or 'UNKNOWN').strip().upper()
    distance_raw   = seg.get('distance_km') or seg.get('distance') or 0
    date_raw       = seg.get('date') or seg.get('travel_date') or ''
    emp_id         = str(seg.get('employee_id') or seg.get('traveler_id') or '')

    distance_km = Decimal(str(distance_raw)) if distance_raw else Decimal('20')
    travel_date = _parse_date(date_raw)

    ef = GROUND_FACTORS.get(transport_type, GROUND_FACTORS['UNKNOWN'])
    co2e_kg = distance_km * ef

    flags = []
    if not distance_raw:
        flags.append("Distance not provided — using 20 km default")
    if transport_type == 'UNKNOWN':
        flags.append("Transport type unknown")

    return {
        'scope': 3,
        'category': 'GROUND',
        'activity_value': distance_km,
        'activity_unit': 'KM',
        'activity_unit_normalized': distance_km,
        'co2e_kg': co2e_kg,
        'emission_factor_used': f'DEFRA 2023 ground {transport_type}: {ef} kgCO2e/km',
        'period_start': travel_date,
        'period_end': travel_date,
        'employee_id': emp_id,
        'description': f"{transport_type} ({distance_km} km)",
        'travel_class': transport_type,
        'flag_reason': '; '.join(flags),
        'status': 'FLAGGED' if flags else 'PENDING',
    }


def parse_travel_json(file_content: bytes) -> tuple[list[dict], list[dict]]:
    """
    Parse Concur-style travel JSON export.
    Expects a JSON array of trip objects, each with a 'segments' list.

    Returns:
        records — list of normalised dicts (one per segment)
        errors  — list of {row, raw, reason}
    """
    records = []
    errors = []

    try:
        data = json.loads(file_content.decode('utf-8', errors='replace'))
    except json.JSONDecodeError as e:
        return [], [{'row': 0, 'raw': {}, 'reason': f"JSON parse error: {e}"}]

    if isinstance(data, dict) and 'trips' in data:
        trips = data['trips']
    elif isinstance(data, list):
        trips = data
    else:
        return [], [{'row': 0, 'raw': {}, 'reason': "Expected JSON array or object with 'trips' key"}]

    row_num = 1
    for trip in trips:
        segments = trip.get('segments', [])
        if not segments:
            # Try flat structure (single-segment trip)
            segments = [trip]

        for seg in segments:
            seg_type = str(seg.get('type') or seg.get('segment_type') or '').strip().upper()
            seg['employee_id'] = seg.get('employee_id') or trip.get('employee_id', '')

            try:
                if seg_type in ('AIR', 'FLIGHT'):
                    rec = _parse_air_segment(seg, row_num)
                elif seg_type in ('HOTEL', 'ACCOMMODATION'):
                    rec = _parse_hotel_segment(seg, row_num)
                elif seg_type in ('GROUND', 'CAR', 'RAIL', 'TAXI', 'RENTAL'):
                    rec = _parse_ground_segment(seg, row_num)
                else:
                    # Try to infer from fields present
                    if 'origin_iata' in seg or 'departure_date' in seg:
                        rec = _parse_air_segment(seg, row_num)
                    elif 'check_in' in seg or 'nights' in seg:
                        rec = _parse_hotel_segment(seg, row_num)
                    else:
                        rec = _parse_ground_segment(seg, row_num)

                rec['_raw_row'] = seg
                rec['_row_num'] = row_num
                records.append(rec)

            except (ValueError, KeyError) as e:
                errors.append({'row': row_num, 'raw': seg, 'reason': str(e)})

            row_num += 1

    return records, errors