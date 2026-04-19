"""
TNS Multidimensional Analysis System
Task 1: InBody 270S CSV Parser

Reads InBody 270S LookinBody Cloud CSV exports.
Handles UTF-8-BOM, lb→kg / kJ→kcal conversions, missing "-" values,
and the "Left leg" vs "Left Leg" capitalisation inconsistency in firmware.

Usage
-----
    from tns_inbody_parser import parse_inbody_csv, parse_inbody_csv_string

    # From file (downloaded from LookinBody Cloud):
    scans = parse_inbody_csv("InBody-20260415.csv")

    # From raw text (Colab cell paste):
    scans = parse_inbody_csv_string(csv_text)

    print(scans[0]["ib_weight_kg"])    # 99.38
    print(scans[0]["ib_bf_pct"])       # 29.8
    print(scans[0]["ib_bmr_kcal"])     # 1877
"""

from __future__ import annotations

import csv
import io
from datetime import datetime
from pathlib import Path
from typing import Union

# ── Unit conversion factors ──────────────────────────────────────────────────
LB_TO_KG: float = 1 / 2.20462
KJ_TO_KCAL: float = 1 / 4.184

# ── Column name mapping: InBody CSV header → pipeline variable name ──────────
# Variables not in this map are kept under raw_<header> for traceability.
INBODY_MAP: dict[str, str] = {
    "Weight(lb)":                  "ib_weight_kg",
    "Skeletal Muscle Mass(lb)":    "ib_smm_kg",
    "Body Fat Mass(lb)":           "ib_fat_mass_kg",
    "BMI(kg/m²)":                  "ib_bmi",
    "Percent Body Fat(%)":         "ib_bf_pct",
    "Basal Metabolic Rate(kJ)":    "ib_bmr_kcal",
    "InBody Score":                "ib_score",
    # Segmental lean — note firmware inconsistency: "Left leg" (lowercase)
    "Right Arm Lean Mass(lb)":     "ib_lean_arm_r_kg",
    "Left Arm Lean Mass(lb)":      "ib_lean_arm_l_kg",
    "Trunk Lean Mass(lb)":         "ib_lean_trunk_kg",
    "Right Leg Lean Mass(lb)":     "ib_lean_leg_r_kg",
    "Left leg Lean Mass(lb)":      "ib_lean_leg_l_kg",   # 270S firmware: lowercase
    "Left Leg Lean Mass(lb)":      "ib_lean_leg_l_kg",   # fallback: uppercase
    # Segmental fat
    "Right Arm Fat Mass(lb)":      "ib_fat_arm_r_kg",
    "Left Arm Fat Mass(lb)":       "ib_fat_arm_l_kg",
    "Trunk Fat Mass(lb)":          "ib_fat_trunk_kg",
    "Right Leg Fat Mass(lb)":      "ib_fat_leg_r_kg",
    "Left Leg Fat Mass(lb)":       "ib_fat_leg_l_kg",
    # Ratios / scores
    "Waist Hip Ratio":             "ib_whr",
    "Visceral Fat Level(Level)":   "ib_visceral_fat_level",
    # Body water (exported as lb on 270S despite the unit name)
    "Total Body Water(lb)":        "ib_tbw_kg",
    # Body composition breakdown
    "Protein(lb)":                 "ib_protein_kg",
    "Mineral(lb)":                 "ib_mineral_kg",
    # Functional indices
    "SMI(kg/m²)":                  "ib_smi",
    "Whole Body Phase Angle(°)":   "ib_phase_angle",
}

# Variables that need lb → kg conversion
_CONVERT_LB_TO_KG: frozenset[str] = frozenset({
    "ib_weight_kg",
    "ib_smm_kg",
    "ib_fat_mass_kg",
    "ib_lean_arm_r_kg", "ib_lean_arm_l_kg",
    "ib_lean_trunk_kg",
    "ib_lean_leg_r_kg", "ib_lean_leg_l_kg",
    "ib_fat_arm_r_kg", "ib_fat_arm_l_kg",
    "ib_fat_trunk_kg",
    "ib_fat_leg_r_kg", "ib_fat_leg_l_kg",
    "ib_tbw_kg",
    "ib_protein_kg",
    "ib_mineral_kg",
})

# Variables that need kJ → kcal conversion
_CONVERT_KJ_TO_KCAL: frozenset[str] = frozenset({"ib_bmr_kcal"})

# Variables that are 270S-unavailable (exported as "-"); kept as None
UNAVAILABLE_270S: tuple[str, ...] = (
    "Soft Lean Mass(lb)",
    "Right Arm ECW Ratio", "Left Arm ECW Ratio",
    "Trunk ECW Ratio", "Right Leg ECW Ratio", "Left Leg ECW Ratio",
    "Waist Circumference(cm)", "Visceral Fat Area(cm²)",
    "Intracellular Water(lb)", "Extracellular Water(lb)", "ECW Ratio",
    "Leg Muscle Level(Level)",
    "Bone Mineral Content(lb)", "Body Cell Mass(lb)",
)


# ── Internal helpers ─────────────────────────────────────────────────────────

def _parse_scan_date(raw: str) -> str | None:
    """
    Parse InBody timestamp (YYYYMMDDHHMMSS) → ISO date string (YYYY-MM-DD).
    Strips any trailing device suffix (e.g. '20260412153252' from '20260412153252_270S').
    Returns None if parsing fails.
    """
    raw = raw.strip().split("_")[0]
    if len(raw) >= 8:
        try:
            return datetime.strptime(raw[:8], "%Y%m%d").strftime("%Y-%m-%d")
        except ValueError:
            pass
    return None


def _to_float_or_none(val: str) -> float | None:
    """Convert to float; return None for '-', empty string, or non-numeric."""
    v = val.strip()
    if v in ("", "-", "N/A", "NA", "n/a", "—"):
        return None
    try:
        return float(v)
    except ValueError:
        return None


def _apply_conversions(record: dict) -> dict:
    """Apply lb→kg and kJ→kcal conversions to a partially-built record dict."""
    for key in _CONVERT_LB_TO_KG:
        if record.get(key) is not None:
            record[key] = round(record[key] * LB_TO_KG, 4)
    for key in _CONVERT_KJ_TO_KCAL:
        if record.get(key) is not None:
            record[key] = round(record[key] * KJ_TO_KCAL, 2)
    return record


def _parse_reader(reader: csv.DictReader) -> list[dict]:
    """
    Core parse loop shared by both the file-path and string variants.
    Expects a csv.DictReader whose fieldnames are already available.
    """
    if reader.fieldnames is None:
        return []

    # Strip whitespace from headers (BOM already removed by utf-8-sig)
    clean_fieldnames: list[str] = [f.strip() for f in reader.fieldnames]

    rows: list[dict] = []
    for raw_row in reader:
        # Normalise key whitespace for robustness
        row: dict[str, str] = {k.strip(): v for k, v in raw_row.items() if k}

        record: dict = {}

        # ── Scan timestamp (column 0) ──────────────────────────────────────
        first_col = clean_fieldnames[0] if clean_fieldnames else None
        record["scan_date"] = _parse_scan_date(row.get(first_col or "", ""))

        # ── Device model (column 1) ────────────────────────────────────────
        second_col = clean_fieldnames[1] if len(clean_fieldnames) > 1 else None
        if second_col:
            device_val = row.get(second_col, "").strip()
            record["scan_device"] = device_val or None
        else:
            record["scan_device"] = None

        # ── Map known columns → pipeline names ───────────────────────────
        already_set: set[str] = set()
        for original_header, pipeline_name in INBODY_MAP.items():
            if original_header in row:
                val = _to_float_or_none(row[original_header])
                # Only set if not already populated (handles upper/lower-case
                # duplicate entries — first non-None value wins)
                if pipeline_name not in already_set or record.get(pipeline_name) is None:
                    record[pipeline_name] = val
                    if val is not None:
                        already_set.add(pipeline_name)

        # ── Unit conversions ───────────────────────────────────────────────
        _apply_conversions(record)

        # ── Preserve unmapped columns with raw_ prefix ─────────────────────
        mapped_originals: set[str] = set(INBODY_MAP.keys())
        if first_col:
            mapped_originals.add(first_col)
        if second_col:
            mapped_originals.add(second_col)

        for col in clean_fieldnames:
            if col not in mapped_originals:
                record[f"raw_{col}"] = row.get(col)

        rows.append(record)

    return rows


# ── Public API ───────────────────────────────────────────────────────────────

def parse_inbody_csv(csv_path: Union[str, Path]) -> list[dict]:
    """
    Read an InBody 270S LookinBody Cloud CSV export from disk.

    Parameters
    ----------
    csv_path : str or Path
        Path to the exported CSV file.

    Returns
    -------
    list[dict]
        One dict per scan row containing:
        - scan_date   : ISO date string "YYYY-MM-DD" (None if unparseable)
        - scan_device : Device model string e.g. "270S"
        - ib_*        : Pipeline-named variables (all metric: kg, kcal)
        - raw_*       : Any columns not in the mapping, for auditability

        270S-unavailable variables (e.g. ECW ratios) are present but set to None.

    Raises
    ------
    FileNotFoundError
        If csv_path does not exist.
    """
    path = Path(csv_path)
    if not path.exists():
        raise FileNotFoundError(f"InBody CSV not found: {path}")

    with path.open(encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        return _parse_reader(reader)


def parse_inbody_csv_string(csv_text: str) -> list[dict]:
    """
    Same as parse_inbody_csv() but accepts a raw CSV string.

    Useful for the Colab paste workflow where Jesus or Stephanie copies the
    LookinBody Cloud export text directly into a notebook cell variable.

    Parameters
    ----------
    csv_text : str
        Full CSV text, with or without BOM.

    Returns
    -------
    list[dict]
        Same schema as parse_inbody_csv().
    """
    if csv_text.startswith("\ufeff"):
        csv_text = csv_text[1:]

    reader = csv.DictReader(io.StringIO(csv_text))
    return _parse_reader(reader)


def inbody_summary(scan: dict) -> str:
    """
    Return a one-line human-readable summary of a parsed scan dict.
    Useful for quick verification in Colab.
    """
    parts = [
        f"Date: {scan.get('scan_date', 'N/A')}",
        f"Weight: {scan.get('ib_weight_kg', 'N/A'):.1f} kg"
            if scan.get("ib_weight_kg") else "Weight: N/A",
        f"BF%: {scan.get('ib_bf_pct', 'N/A')}%",
        f"SMM: {scan.get('ib_smm_kg', 'N/A'):.1f} kg"
            if scan.get("ib_smm_kg") else "SMM: N/A",
        f"Score: {scan.get('ib_score', 'N/A')}",
        f"Phase∠: {scan.get('ib_phase_angle', 'N/A')}°",
    ]
    return " | ".join(parts)


# ── Smoke test ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import json
    import sys

    if len(sys.argv) >= 2:
        results = parse_inbody_csv(sys.argv[1])
    else:
        # Built-in demo: Jesus Garcia, April 12 2026
        DEMO = (
            "Date,Measurement device.,Weight(lb),Skeletal Muscle Mass(lb),"
            "Soft Lean Mass(lb),Body Fat Mass(lb),BMI(kg/m\u00b2),Percent Body Fat(%),"
            "Basal Metabolic Rate(kJ),InBody Score,Right Arm Lean Mass(lb),"
            "Left Arm Lean Mass(lb),Trunk Lean Mass(lb),Right Leg Lean Mass(lb),"
            "Left leg Lean Mass(lb),Right Arm Fat Mass(lb),Left Arm Fat Mass(lb),"
            "Trunk Fat Mass(lb),Right Leg Fat Mass(lb),Left Leg Fat Mass(lb),"
            "Right Arm ECW Ratio,Left Arm ECW Ratio,Trunk ECW Ratio,"
            "Right Leg ECW Ratio,Left Leg ECW Ratio,Waist Hip Ratio,"
            "Waist Circumference(cm),Visceral Fat Area(cm\u00b2),Visceral Fat Level(Level),"
            "Total Body Water(lb),Intracellular Water(lb),Extracellular Water(lb),"
            "ECW Ratio,Upper-Lower,Upper,Lower,Leg Muscle Level(Level),"
            "Leg Lean Mass(lb),Protein(lb),Mineral(lb),Bone Mineral Content(lb),"
            "Body Cell Mass(lb),SMI(kg/m\u00b2),Whole Body Phase Angle(\u00b0)\n"
            "20260412153252,270S,219.1,88.0,-,65.3,34.4,29.8,7853,78.0,"
            "9.11,9.19,68.1,22.00,21.72,4.4,4.4,35.9,8.6,8.6,-,-,-,-,-,"
            "0.95,-,-,12.0,112.9,-,-,-,1,0,0,-,-,30.6,10.45,-,-,9.7,6.9"
        )
        results = parse_inbody_csv_string(DEMO)

    for r in results:
        print(inbody_summary(r))
        print()
        print(json.dumps(
            {k: v for k, v in r.items() if not k.startswith("raw_")},
            indent=2, default=str
        ))
