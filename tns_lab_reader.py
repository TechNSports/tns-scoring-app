"""
TNS Multidimensional Analysis System
Lab Reader + Unit Conversion Utilities

Parses lab data from three sources:
  1. Lab Entry sheet row (dict from TNS_Scan_Data_Master.xlsx)
  2. Raw dict with arbitrary unit keys (auto-converted to NHANES units)
  3. Future: PDF parser output (see Phase A spec, Lab PDF Parser sprint)

All output values are in NHANES-standard units:
  - Cholesterol / glucose / triglycerides: mg/dL
  - HbA1c: %
  - Insulin: µIU/mL
  - hs-CRP: mg/L
  - Blood pressure: mmHg

Usage
-----
    from tns_lab_reader import parse_lab_row, convert_lab_units

    # From Lab Entry sheet row (already in NHANES units):
    lab_dict = parse_lab_row(sheet_row)

    # From a raw dict that might use mmol/L for glucose:
    lab_dict = convert_lab_units({
        "glucose_mmol": 6.2,         # → lab_glucose = 111.7 mg/dL
        "total_chol_mmol": 5.1,      # → lab_total_chol = 197.2 mg/dL
    })
"""

from __future__ import annotations
from typing import Optional

# ── NHANES unit conversions from common alternative units ────────────────────
# Format: (source_key_suffix, target_key, factor)
# "suffix" is matched at end of key name after stripping lab_ prefix
_UNIT_CONVERSIONS: dict[str, tuple[str, float]] = {
    # Cholesterol/lipids: mmol/L → mg/dL (multiply by 38.67)
    "total_chol_mmol":    ("lab_total_chol",    38.67),
    "hdl_mmol":           ("lab_hdl",           38.67),
    "ldl_mmol":           ("lab_ldl",           38.67),
    "triglycerides_mmol": ("lab_triglycerides", 88.57),
    # Glucose: mmol/L → mg/dL (multiply by 18.02)
    "glucose_mmol":       ("lab_glucose",       18.02),
    # HbA1c: mmol/mol (IFCC) → % (NGSP): formula = (mmol/mol / 10.929) + 2.15
    # Handled separately below due to non-linear conversion
    # Insulin: pmol/L → µIU/mL (divide by 6.945)
    "insulin_pmol":       ("lab_insulin",       1 / 6.945),
    # hs-CRP: nmol/L → mg/L (divide by 9.524)
    "hscrp_nmol":         ("lab_hscrp",         1 / 9.524),
}

# Direct-pass keys (already in NHANES units, just need normalisation)
_DIRECT_KEYS: dict[str, str] = {
    "total_chol":    "lab_total_chol",
    "hdl":           "lab_hdl",
    "ldl":           "lab_ldl",
    "triglycerides": "lab_triglycerides",
    "glucose":       "lab_glucose",
    "hba1c":         "lab_hba1c",
    "insulin":       "lab_insulin",
    "hscrp":         "lab_hscrp",
    "hs_crp":        "lab_hscrp",
    "sbp":           "lab_sbp",
    "dbp":           "lab_dbp",
    # With lab_ prefix already:
    "lab_total_chol":    "lab_total_chol",
    "lab_hdl":           "lab_hdl",
    "lab_ldl":           "lab_ldl",
    "lab_triglycerides": "lab_triglycerides",
    "lab_glucose":       "lab_glucose",
    "lab_hba1c":         "lab_hba1c",
    "lab_insulin":       "lab_insulin",
    "lab_hscrp":         "lab_hscrp",
    "lab_sbp":           "lab_sbp",
    "lab_dbp":           "lab_dbp",
}

# Clinical range bounds (for validation / flagging out-of-range entries)
LAB_BOUNDS: dict[str, tuple[float, float]] = {
    "lab_total_chol":    (50, 500),
    "lab_hdl":           (10, 200),
    "lab_ldl":           (20, 400),
    "lab_triglycerides": (20, 2000),
    "lab_glucose":       (30, 500),
    "lab_hba1c":         (3, 18),
    "lab_insulin":       (0, 300),
    "lab_hscrp":         (0.01, 100),
    "lab_sbp":           (70, 250),
    "lab_dbp":           (40, 150),
}

# All output lab keys (canonical set)
ALL_LAB_KEYS: tuple[str, ...] = (
    "lab_total_chol", "lab_hdl", "lab_ldl", "lab_triglycerides",
    "lab_glucose", "lab_hba1c", "lab_insulin", "lab_hscrp",
    "lab_sbp", "lab_dbp",
)


def _to_float_or_none(val) -> Optional[float]:
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return float(val) if not (isinstance(val, float) and val != val) else None
    s = str(val).strip()
    if s in ("", "-", "N/A", "NA", "—", "None"):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _validate_bounds(key: str, val: float) -> Optional[str]:
    """Return a warning string if val is outside expected range, else None."""
    if key in LAB_BOUNDS:
        lo, hi = LAB_BOUNDS[key]
        if val < lo or val > hi:
            return f"{key} = {val} is outside expected range [{lo}, {hi}]"
    return None


def parse_lab_row(row: dict, validate: bool = True) -> dict:
    """
    Parse a Lab Entry sheet row into a canonical lab dict.

    Parameters
    ----------
    row : dict
        One row from the Lab Entry sheet, keys = column headers.
        Expected keys (from TNS_Scan_Data_Master Lab Entry sheet):
          client_id, scan_date, lab_source,
          lab_total_chol, HDL, LDL, lab_triglycerides, lab_glucose,
          lab_HbA1c (or lab_hba1c), lab_insulin, lab_hs-CRP (or lab_hscrp),
          lab_SBP, lab_DBP, notes
    validate : bool
        If True, print warnings for out-of-range values.

    Returns
    -------
    dict
        {lab_total_chol, lab_hdl, ..., lab_dbp} — all in NHANES units.
        Missing values are None.
    """
    result: dict = {}
    warnings: list[str] = []

    # Column aliases: sheet uses capitalised versions for some
    aliases = {
        "HDL":          "lab_hdl",
        "LDL":          "lab_ldl",
        "lab_HbA1c":    "lab_hba1c",
        "lab_hba1c":    "lab_hba1c",
        "lab_hs-CRP":   "lab_hscrp",
        "lab_hscrp":    "lab_hscrp",
        "lab_SBP":      "lab_sbp",
        "lab_DBP":      "lab_dbp",
        "lab_sbp":      "lab_sbp",
        "lab_dbp":      "lab_dbp",
    }
    for src, canonical in aliases.items():
        if src in row:
            val = _to_float_or_none(row[src])
            if val is not None:
                result[canonical] = val

    # Direct-match remaining lab keys
    for key in row:
        norm = key.strip().lower().replace(" ", "_").replace("-", "_")
        canonical = _DIRECT_KEYS.get(norm) or _DIRECT_KEYS.get(key)
        if canonical and canonical not in result:
            val = _to_float_or_none(row[key])
            if val is not None:
                result[canonical] = val

    # Fill missing with None
    for k in ALL_LAB_KEYS:
        result.setdefault(k, None)

    if validate:
        for k, v in result.items():
            if v is not None:
                warn = _validate_bounds(k, v)
                if warn:
                    warnings.append(warn)

    if warnings:
        print("[LAB VALIDATION WARNINGS]")
        for w in warnings:
            print(f"  ⚠️  {w}")

    return result


def convert_lab_units(raw: dict, validate: bool = True) -> dict:
    """
    Convert a lab dict with arbitrary unit keys to NHANES-standard units.

    Handles:
      - Direct mg/dL values (most common for Mexican labs)
      - mmol/L values (European format — suffix: _mmol)
      - pmol/L insulin (_pmol)
      - nmol/L hs-CRP (_nmol)
      - IFCC HbA1c mmol/mol (_ifcc)

    Parameters
    ----------
    raw : dict
        Arbitrary-keyed dict of lab values.

    Returns
    -------
    dict
        Canonical lab_* keys in NHANES units.
    """
    result: dict = {}

    for key, val in raw.items():
        norm = key.strip().lower().replace(" ", "_")
        float_val = _to_float_or_none(val)
        if float_val is None:
            continue

        # Check conversion table first
        if norm in _UNIT_CONVERSIONS:
            canonical, factor = _UNIT_CONVERSIONS[norm]
            result[canonical] = round(float_val * factor, 2)
        # Special case: IFCC HbA1c (mmol/mol) → NGSP (%)
        elif norm in ("hba1c_ifcc", "lab_hba1c_ifcc"):
            result["lab_hba1c"] = round(float_val / 10.929 + 2.15, 2)
        # Direct-pass
        elif norm in _DIRECT_KEYS:
            result[_DIRECT_KEYS[norm]] = float_val

    # Fill missing with None
    for k in ALL_LAB_KEYS:
        result.setdefault(k, None)

    if validate:
        for k, v in result.items():
            if v is not None:
                warn = _validate_bounds(k, v)
                if warn:
                    print(f"  ⚠️  {warn}")

    return result


def lab_summary(lab_dict: dict) -> str:
    """One-line summary for Colab verification output."""
    provided = {k: v for k, v in lab_dict.items() if k in ALL_LAB_KEYS and v is not None}
    if not provided:
        return "Labs: none provided"
    parts = [f"{k.replace('lab_', '').upper()}={v}" for k, v in provided.items()]
    return f"Labs ({len(provided)}/10): " + " | ".join(parts)
