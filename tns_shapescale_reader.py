"""
TNS Multidimensional Analysis System
Task 2: ShapeScale Google Sheet / CSV Reader

Reads ShapeScale data from:
  (a) A list of dicts returned by the Google Sheets API (primary path in Colab)
  (b) A CSV export of the "ShapeScale Entry" sheet (fallback)
  (c) A pandas DataFrame if already loaded (convenience)

All values are converted to metric (kg, cm, cm³).
Column names are normalised to the pipeline convention (ss_ prefix).

Usage
-----
    # Option A — Google Sheets API rows (list of dicts):
    from tns_shapescale_reader import parse_shapescale_sheet
    scans = parse_shapescale_sheet(sheet_rows)   # sheet_rows from gspread

    # Option B — CSV file export:
    from tns_shapescale_reader import parse_shapescale_csv
    scans = parse_shapescale_csv("shapescale_export.csv")

    print(scans[0]["ss_waist_cm"])    # waist in cm
    print(scans[0]["ss_weight_kg"])   # weight in kg
"""

from __future__ import annotations

import csv
import io
from datetime import datetime
from pathlib import Path
from typing import Union

# ── Conversion factors ───────────────────────────────────────────────────────
LB_TO_KG: float = 1 / 2.20462
IN_TO_CM: float = 2.54
CU_IN_TO_CU_CM: float = 16.387       # 1 cubic inch = 16.387 cm³

# ── Visceral fat rating → numeric encoding ───────────────────────────────────
VISCERAL_FAT_RATING_MAP: dict[str, int] = {
    "very poor": 1,
    "poor": 2,
    "fair": 3,
    "good": 4,
    "excellent": 5,
}

# ── Column name mapping: ShapeScale Entry sheet header → pipeline name ───────
# Sheet headers should match the TNS_Scan_Data_Master.xlsx "ShapeScale Entry" tab.
# The map handles minor capitalisation variants.
SHAPESCALE_MAP: dict[str, tuple[str, str]] = {
    # (pipeline_name, conversion_type)
    # Conversion types: "lb_kg", "in_cm", "cu_in_cu_cm", "as_is", "date", "vfr_encode"

    # ── SUMMARY ──
    "client_id":            ("ss_client_id",         "as_is"),
    "scan_date":            ("ss_scan_date",          "date"),
    "weight_lb":            ("ss_weight_kg",          "lb_kg"),
    "body_fat_pct":         ("ss_bf_pct",             "as_is"),
    "lean_mass_lb":         ("ss_lean_mass_kg",       "lb_kg"),
    "bmi":                  ("ss_bmi",                "as_is"),
    "bmr_cal":              ("ss_bmr_kcal",           "as_is"),   # ShapeScale uses kcal
    "shape_score":          ("ss_shape_score",        "as_is"),
    "health_score":         ("ss_health_score",       "as_is"),
    "body_age":             ("ss_body_age",           "as_is"),
    "visceral_fat_rating":  ("ss_visceral_fat_num",   "vfr_encode"),

    # ── CIRCUMFERENCES (inches → cm) ──
    "neck_in":              ("ss_neck_cm",            "in_cm"),
    "shoulders_in":         ("ss_shoulders_cm",       "in_cm"),
    "chest_in":             ("ss_chest_cm",           "in_cm"),
    "waist_in":             ("ss_waist_cm",           "in_cm"),
    "hips_in":              ("ss_hips_cm",            "in_cm"),
    "bicep_l_in":           ("ss_bicep_l_cm",         "in_cm"),
    "bicep_r_in":           ("ss_bicep_r_cm",         "in_cm"),
    "thigh_l_in":           ("ss_thigh_l_cm",         "in_cm"),
    "thigh_r_in":           ("ss_thigh_r_cm",         "in_cm"),
    "calf_l_in":            ("ss_calf_l_cm",          "in_cm"),
    "calf_r_in":            ("ss_calf_r_cm",          "in_cm"),

    # ── VOLUMES (cubic inches → cm³) ──
    "vol_trunk_cu_in":      ("ss_vol_trunk_cm3",      "cu_in_cu_cm"),
    "vol_upper_leg_l_cu_in":("ss_vol_upper_leg_l_cm3","cu_in_cu_cm"),
    "vol_upper_leg_r_cu_in":("ss_vol_upper_leg_r_cm3","cu_in_cu_cm"),
    "vol_lower_leg_l_cu_in":("ss_vol_lower_leg_l_cm3","cu_in_cu_cm"),
    "vol_lower_leg_r_cu_in":("ss_vol_lower_leg_r_cm3","cu_in_cu_cm"),
    "vol_upper_arm_l_cu_in":("ss_vol_upper_arm_l_cm3","cu_in_cu_cm"),
    "vol_upper_arm_r_cu_in":("ss_vol_upper_arm_r_cm3","cu_in_cu_cm"),

    # ── RATIOS (pre-computed, unit-free) ──
    "whr":                  ("ss_whr",                "as_is"),
    "whtr":                 ("ss_whtr",               "as_is"),
    "shoulder_waist":       ("ss_shoulder_waist",     "as_is"),
    "thigh_waist":          ("ss_thigh_waist",        "as_is"),
    "neck_waist":           ("ss_neck_waist",         "as_is"),
}

# Build a case-insensitive lookup by normalising all keys
_SS_MAP_LOWER: dict[str, tuple[str, str]] = {
    k.lower().replace(" ", "_"): v for k, v in SHAPESCALE_MAP.items()
}


# ── Internal helpers ─────────────────────────────────────────────────────────

def _normalise_header(h: str) -> str:
    """Lower-case, strip, replace spaces with underscores."""
    return h.strip().lower().replace(" ", "_")


def _parse_date_flexible(raw: str) -> str | None:
    """
    Parse a ShapeScale date field. Handles:
      - ISO: "2026-04-13"
      - US:  "04/13/2026"
      - MX:  "13/04/2026"
    Returns ISO string or None.
    """
    raw = raw.strip()
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y", "%Y%m%d"):
        try:
            return datetime.strptime(raw, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


def _to_float_or_none(val: str) -> float | None:
    v = val.strip() if isinstance(val, str) else str(val).strip()
    if v in ("", "-", "N/A", "NA", "n/a", "—", "None"):
        return None
    try:
        return float(v)
    except (ValueError, TypeError):
        return None


def _apply_conversion(value: float | None, conv: str, raw_str: str = "") -> object:
    """Apply the appropriate conversion and return the result."""
    if conv == "date":
        return _parse_date_flexible(raw_str)
    if conv == "as_is":
        return value
    if conv == "lb_kg" and value is not None:
        return round(value * LB_TO_KG, 4)
    if conv == "in_cm" and value is not None:
        return round(value * IN_TO_CM, 3)
    if conv == "cu_in_cu_cm" and value is not None:
        return round(value * CU_IN_TO_CU_CM, 2)
    if conv == "vfr_encode":
        return VISCERAL_FAT_RATING_MAP.get(raw_str.strip().lower())
    return value


def _process_row(row: dict[str, str]) -> dict:
    """Convert one row dict (raw strings) → fully parsed pipeline record."""
    record: dict = {}

    for raw_key, raw_val in row.items():
        norm_key = _normalise_header(raw_key)
        if norm_key in _SS_MAP_LOWER:
            pipeline_name, conv_type = _SS_MAP_LOWER[norm_key]
            if conv_type == "date":
                record[pipeline_name] = _parse_date_flexible(raw_val)
            elif conv_type == "as_is":
                record[pipeline_name] = _to_float_or_none(raw_val)
            elif conv_type == "vfr_encode":
                record[pipeline_name] = VISCERAL_FAT_RATING_MAP.get(
                    raw_val.strip().lower()
                )
            else:
                num = _to_float_or_none(raw_val)
                record[pipeline_name] = _apply_conversion(num, conv_type)
        else:
            # Preserve unmapped columns
            record[f"raw_{norm_key}"] = raw_val.strip() if isinstance(raw_val, str) else raw_val

    return record


# ── Public API ───────────────────────────────────────────────────────────────

def parse_shapescale_sheet(sheet_data: list[dict]) -> list[dict]:
    """
    Parse ShapeScale data from a list of dicts (Google Sheets API output).

    Parameters
    ----------
    sheet_data : list[dict]
        Each dict is one row from the "ShapeScale Entry" sheet.
        Keys are the column header strings exactly as they appear in the sheet.

    Returns
    -------
    list[dict]
        One dict per scan with ss_* pipeline keys and all values in metric units.
        Rows with no scan_date and no client_id are skipped (likely blank rows).
    """
    results: list[dict] = []
    for row in sheet_data:
        if not any(str(v).strip() for v in row.values()):
            continue  # skip empty rows
        record = _process_row({str(k): str(v) for k, v in row.items()})
        # Skip header-lookalike rows that got through
        if record.get("ss_scan_date") == "scan_date":
            continue
        results.append(record)
    return results


def parse_shapescale_csv(csv_path: Union[str, Path]) -> list[dict]:
    """
    Parse ShapeScale data from a CSV export of the "ShapeScale Entry" sheet.

    Parameters
    ----------
    csv_path : str or Path
        Path to the CSV file.

    Returns
    -------
    list[dict]
        Same schema as parse_shapescale_sheet().
    """
    path = Path(csv_path)
    if not path.exists():
        raise FileNotFoundError(f"ShapeScale CSV not found: {path}")

    results: list[dict] = []
    with path.open(encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            clean = {k.strip(): v.strip() for k, v in row.items() if k}
            if not any(clean.values()):
                continue
            results.append(_process_row(clean))
    return results


def parse_shapescale_csv_string(csv_text: str) -> list[dict]:
    """Parse ShapeScale data from a raw CSV string (Colab paste variant)."""
    if csv_text.startswith("\ufeff"):
        csv_text = csv_text[1:]
    results: list[dict] = []
    reader = csv.DictReader(io.StringIO(csv_text))
    for row in reader:
        clean = {k.strip(): v.strip() for k, v in row.items() if k}
        if not any(clean.values()):
            continue
        results.append(_process_row(clean))
    return results


def shapescale_summary(scan: dict) -> str:
    """One-line verification summary for Colab output."""
    parts = [
        f"Date: {scan.get('ss_scan_date', 'N/A')}",
        f"Weight: {scan.get('ss_weight_kg', 'N/A'):.1f} kg"
            if scan.get("ss_weight_kg") else "Weight: N/A",
        f"BF%: {scan.get('ss_bf_pct', 'N/A')}%",
        f"Waist: {scan.get('ss_waist_cm', 'N/A'):.1f} cm"
            if scan.get("ss_waist_cm") else "Waist: N/A",
        f"WHR: {scan.get('ss_whr', 'N/A')}",
        f"Shape: {scan.get('ss_shape_score', 'N/A')}",
    ]
    return " | ".join(parts)


# ── Smoke test ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import json

    DEMO_ROW = {
        "client_id": "garcia_jesus",
        "scan_date": "2026-04-13",
        "weight_lb": "215.3",
        "body_fat_pct": "34.5",
        "lean_mass_lb": "140.9",
        "bmi": "33.8",
        "bmr_cal": "1685",
        "shape_score": "72",
        "health_score": "65",
        "body_age": "46",
        "visceral_fat_rating": "Poor",
        "neck_in": "16.5",
        "shoulders_in": "51.2",
        "chest_in": "44.1",
        "waist_in": "44.0",
        "hips_in": "44.0",
        "bicep_l_in": "14.8",
        "bicep_r_in": "15.0",
        "thigh_l_in": "25.1",
        "thigh_r_in": "25.3",
        "calf_l_in": "15.9",
        "calf_r_in": "16.1",
        "whr": "1.00",
        "whtr": "0.564",
        "shoulder_waist": "1.165",
    }

    results = parse_shapescale_sheet([DEMO_ROW])
    for r in results:
        print(shapescale_summary(r))
        print()
        print(json.dumps(
            {k: v for k, v in r.items() if not k.startswith("raw_")},
            indent=2, default=str
        ))
