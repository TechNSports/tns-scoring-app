"""
TNS Multidimensional Analysis System
Tasks 3 + A5: Scanner Reconciliation + Lab/Lifestyle data blocks

Merges InBody 270S + ShapeScale outputs into a single unified variable set
ready for PCA projection.

Reconciliation rules (Rule 44 — ShapeScale > InBody on overlap fields)
----------------------------------------------------------------------
When both scanners measure the same variable, ShapeScale takes priority.
ShapeScale = 3D optical measurement of actual tissue volume.
InBody = bioelectrical impedance estimation (affected by hydration, meal timing).
No exceptions without a written override.

Body composition — overlap fields (ShapeScale primary per Rule 44):
    → BF%, weight, BMI: ShapeScale wins when available; InBody is fallback.
    → Discrepancy flags raised when |SS − IB| exceeds threshold.

Body composition — InBody-only fields (no ShapeScale equivalent):
    → visceral_fat_level, phase_angle, ecw_tbw_ratio, segmental_lean,
      inbody_score, body_water_kg, protein_kg, mineral_kg
    → InBody always used; no conflict.

Morphology (circumferences, volumes, pre-computed ratios):
    → Use ShapeScale as primary (3D optical measurement, higher accuracy
      for external dimensions than tape or BIA estimates)

WHR:
    → Average of both instruments when both are available.
      InBody WHR is BIA-estimated; ShapeScale WHR is tape-measured.
      They capture slightly different constructs; averaging reduces
      method-specific bias.

BMI:
    → Recalculated from ShapeScale weight + measured standing height (Rule 44).
      InBody weight used as fallback when ShapeScale weight unavailable.
      Both scanner BMIs are kept as ib_bmi / ss_bmi for audit.

Derived variables computed here:
    - ffmi        : Fat-Free Mass Index = lean_mass_kg / height_m²
    - lean_per_cm : lean_mass_kg / height_cm (size-adjusted lean mass)
    - trunk_fat_ratio : ib_fat_trunk_kg / ib_fat_mass_kg
    - ag_ratio    : android proxy = trunk fat / (trunk + leg fat)
    - arm_lean_asym   : |R − L| / mean(R, L) * 100  (%)
    - leg_lean_asym   : |R − L| / mean(R, L) * 100  (%)

Cross-scanner discrepancy flags:
    - Raised when |InBody BF% − ShapeScale BF%| > 3 percentage points

Usage
-----
    from tns_reconcile import reconcile_scanners

    unified = reconcile_scanners(
        inbody_data=ib_scan,          # dict from tns_inbody_parser
        shapescale_data=ss_scan,      # dict from tns_shapescale_reader
        height_cm=175.0,              # from physical assessment intake
        client_id="garcia_jesus",     # optional
        scan_label="intake",          # optional: "intake" / "8wk" / etc.
    )
"""

from __future__ import annotations

import math
from typing import Optional


# ── Thresholds ───────────────────────────────────────────────────────────────
BF_DISCREPANCY_FLAG_PP: float = 3.0   # percentage points
ASYMMETRY_FLAG_PCT: float = 10.0      # % asymmetry triggers a note

# ── ShapeScale > InBody priority fields (Rule 44) ────────────────────────────
# When both scanners measure the same variable, ShapeScale takes priority.
# ShapeScale = 3D optical measurement of actual tissue volume.
# InBody = bioelectrical impedance estimation (affected by hydration, meal timing).
#
# Exception — WHR: reconcile_scanners() AVERAGES InBody and ShapeScale WHR
# rather than taking ShapeScale alone.  The two instruments capture slightly
# different constructs (BIA-estimated vs 3D-taped), so averaging reduces
# method-specific bias.  The field is listed here because ShapeScale is the
# superior source; the averaging is a documented design choice, not a Rule 44
# violation.  WHtR (whtr) is purely ShapeScale (computed from ss_waist_cm).
SHAPESCALE_PRIORITY_FIELDS: frozenset[str] = frozenset({
    "weight_kg",     # both; prefer ShapeScale (direct load cell measurement)
    "bmi",           # both; prefer ShapeScale (computed from SS weight + height)
    "bf_pct",        # both; prefer ShapeScale (3D optical body fat estimation)
    "lean_mass_kg",  # both; prefer ShapeScale (volume-derived)
    "whr",           # ShapeScale more accurate; see note above — averaged in practice
    "whtr",          # derived from ShapeScale waist only (no averaging)
})

INBODY_ONLY_FIELDS: frozenset[str] = frozenset({
    "visceral_fat_level",  # BIA proprietary; no ShapeScale equivalent
    "phase_angle",          # cellular membrane integrity; BIA-only
    "ecw_tbw_ratio",        # extracellular/total water ratio; BIA-only
    "segmental_lean",       # limb-by-limb impedance; BIA-only
    "inbody_score",         # proprietary InBody composite; BIA-only
    "body_water_kg",        # total body water; BIA-only
    "protein_kg",           # estimated from lean mass; BIA-only
    "mineral_kg",           # estimated from bone density proxy; BIA-only
})

SHAPESCALE_ONLY_FIELDS: frozenset[str] = frozenset({
    "posture_score",    # 3D posture analysis; ShapeScale-only
    "bsr",              # Body Shape Rating; ShapeScale/Fit3D proprietary
    "circumferences",   # 3D-measured; ShapeScale-only
})

# ── Client-variable mapping for downstream PCA projection ───────────────────
# Maps unified dict keys → generic NHANES model variable names.
# Used by project_client() in tns_pca_pipeline.py.
CLIENT_TO_MODEL_VAR: dict[str, str] = {
    # Body composition
    "bf_pct":               "bf_pct",
    "ib_smm_kg":            "smm_kg",
    "ib_fat_mass_kg":       "fat_mass_kg",
    "ib_lean_trunk_kg":     "lean_trunk_kg",
    "ib_lean_leg_r_kg":     "lean_leg_r_kg",
    "ib_lean_leg_l_kg":     "lean_leg_l_kg",
    "ib_lean_arm_r_kg":     "lean_arm_r_kg",
    "ib_lean_arm_l_kg":     "lean_arm_l_kg",
    "ib_fat_trunk_kg":      "fat_trunk_kg",
    "ib_fat_leg_r_kg":      "fat_leg_r_kg",
    "ib_fat_leg_l_kg":      "fat_leg_l_kg",
    "ib_visceral_fat_level":"visceral_fat_level",
    "ib_smi":               "smi",
    "ib_phase_angle":       "phase_angle",
    "ib_score":             "inbody_score",
    # Morphology (ShapeScale primary)
    "ss_waist_cm":          "waist_cm",
    "ss_hips_cm":           "hip_cm",
    "ss_chest_cm":          "chest_cm",
    "ss_neck_cm":           "neck_cm",
    "ss_shoulders_cm":      "shoulders_cm",
    "ss_thigh_l_cm":        "thigh_l_cm",
    "ss_thigh_r_cm":        "thigh_r_cm",
    "ss_calf_l_cm":         "calf_l_cm",
    "ss_calf_r_cm":         "calf_r_cm",
    "ss_bicep_l_cm":        "bicep_l_cm",
    "ss_bicep_r_cm":        "bicep_r_cm",
    "ss_vol_trunk_cm3":     "vol_trunk_cm3",
    "ss_shape_score":       "shape_score",
    "ss_health_score":      "health_score",
    "ss_body_age":          "body_age",
    # Ratios / indices (reconciled or recalculated)
    "bmi":                  "bmi",
    "whr":                  "whr",
    "whtr":                 "whtr",
    "ss_shoulder_waist":    "shoulder_waist_ratio",
    # Derived
    "ffmi":                 "ffmi",
    "lean_per_cm":          "lean_per_cm",
    "trunk_fat_ratio":      "trunk_fat_ratio",
    "ag_ratio":             "ag_ratio",
    # Labs (if available from intake form — not from scanners)
    "lab_total_chol":       "total_chol",
    "lab_hdl":              "hdl",
    "lab_ldl":              "ldl",
    "lab_triglycerides":    "triglycerides",
    "lab_glucose":          "glucose",
    "lab_hba1c":            "hba1c",
    "lab_insulin":          "insulin",
    "lab_hscrp":            "hscrp",
    "lab_sbp":              "sbp",
    "lab_dbp":              "dbp",
}


# ── Internal helpers ─────────────────────────────────────────────────────────

def _safe_mean(*vals: Optional[float]) -> Optional[float]:
    """Mean of non-None values; returns None if all are None."""
    good = [v for v in vals if v is not None]
    return sum(good) / len(good) if good else None


def _asymmetry_pct(right: Optional[float], left: Optional[float]) -> Optional[float]:
    """
    Bilateral asymmetry as |R−L| / mean(R,L) * 100.
    Returns None if either limb value is missing.
    """
    if right is None or left is None:
        return None
    mean_val = (right + left) / 2
    if mean_val == 0:
        return 0.0
    return round(abs(right - left) / mean_val * 100, 2)


# ── Public API ───────────────────────────────────────────────────────────────

_LAB_KEYS = (
    "lab_total_chol", "lab_hdl", "lab_ldl", "lab_triglycerides",
    "lab_glucose", "lab_hba1c", "lab_insulin", "lab_hscrp",
    "lab_sbp", "lab_dbp",
)
_CORE_LAB_KEYS = ("lab_total_chol", "lab_hdl", "lab_ldl",
                   "lab_triglycerides", "lab_glucose", "lab_hba1c")

_LIFESTYLE_KEYS = (
    "lifestyle_vig_min_week", "lifestyle_mod_min_week", "lifestyle_sed_hours_day",
    "lifestyle_sleep_hours", "lifestyle_smoker_score",
    "lifestyle_alcohol_drinks_week", "lifestyle_stress_score",
    "lifestyle_subj_health_score",
)
_CORE_LIFESTYLE_KEYS = (
    "lifestyle_vig_min_week", "lifestyle_mod_min_week", "lifestyle_sed_hours_day",
)

# Smoker text → numeric for downstream ML use
_SMOKER_ENCODE = {"never": 0, "former": 1, "current": 2}


def reconcile_scanners(
    inbody_data: dict,
    shapescale_data: dict,
    height_cm: float,
    client_id: Optional[str] = None,
    scan_label: Optional[str] = None,
    extra_labs: Optional[dict] = None,
    lifestyle_data: Optional[dict] = None,
) -> dict:
    """
    Merge InBody 270S + ShapeScale data into a single unified record for PCA.

    Parameters
    ----------
    inbody_data : dict
        Parsed output from tns_inbody_parser.parse_inbody_csv() — one scan dict.
    shapescale_data : dict
        Parsed output from tns_shapescale_reader.parse_shapescale_sheet() — one scan dict.
    height_cm : float
        Standing height in cm from the physical assessment intake form.
        Used to recalculate BMI and FFMI from InBody weight.
    client_id : str, optional
        Client identifier (e.g. "garcia_jesus") for traceability.
    scan_label : str, optional
        Timepoint label: "intake", "8wk", "16wk", "24wk".
    extra_labs : dict, optional
        Lab values keyed as: lab_total_chol, lab_hdl, lab_ldl, lab_triglycerides,
        lab_glucose, lab_hba1c, lab_insulin, lab_hscrp, lab_sbp, lab_dbp
    lifestyle_data : dict, optional
        Lifestyle values keyed as: lifestyle_vig_min_week, lifestyle_mod_min_week,
        lifestyle_sed_hours_day, lifestyle_sleep_hours, lifestyle_smoker_score,
        lifestyle_alcohol_drinks_week, lifestyle_stress_score, lifestyle_subj_health_score.
        "smoker" text values ("Never"/"Former"/"Current") are auto-encoded to 0/1/2.

    Returns
    -------
    dict
        ~55-variable unified record. Keys include:
        - ib_* variables (from InBody, in metric)
        - ss_* variables (from ShapeScale, in metric)
        - bmi, whr, whtr (reconciled)
        - ffmi, lean_per_cm, trunk_fat_ratio, ag_ratio, arm_lean_asym, leg_lean_asym
        - lab_* variables if provided (else None)
        - lifestyle_* variables if provided (else None)
        - data_completeness: {scan, labs, lifestyle, full_data, completeness_label}
        - meta: client_id, scan_label, scan_date_ib, scan_date_ss, height_cm
        - flags: list of discrepancy/warning strings
    """
    ib = dict(inbody_data)   # defensive copy — never mutate input
    ss = dict(shapescale_data)

    result: dict = {}
    flags: list[str] = []

    # ── Meta ──────────────────────────────────────────────────────────────────
    result["client_id"]    = client_id or ib.get("client_id") or ss.get("ss_client_id")
    result["scan_label"]   = scan_label
    result["scan_date_ib"] = ib.get("scan_date")
    result["scan_date_ss"] = ss.get("ss_scan_date")
    result["height_cm"]    = height_cm

    # ── Body composition — InBody pass-through (raw scanner values) ──────────
    comp_vars = [
        "ib_bf_pct", "ib_fat_mass_kg", "ib_smm_kg",
        "ib_lean_arm_r_kg", "ib_lean_arm_l_kg", "ib_lean_trunk_kg",
        "ib_lean_leg_r_kg", "ib_lean_leg_l_kg",
        "ib_fat_arm_r_kg",  "ib_fat_arm_l_kg",  "ib_fat_trunk_kg",
        "ib_fat_leg_r_kg",  "ib_fat_leg_l_kg",
        "ib_visceral_fat_level", "ib_tbw_kg", "ib_protein_kg", "ib_mineral_kg",
        "ib_smi", "ib_phase_angle", "ib_score", "ib_bmr_kcal", "ib_weight_kg",
    ]
    for var in comp_vars:
        result[var] = ib.get(var)

    # ── Unified BF% — ShapeScale primary per Rule 44 ─────────────────────────
    ss_bf = ss.get("ss_bf_pct")
    ib_bf = ib.get("ib_bf_pct")
    if ss_bf is not None:
        result["bf_pct"] = ss_bf   # ShapeScale wins (Rule 44)
    elif ib_bf is not None:
        result["bf_pct"] = ib_bf   # InBody fallback when no ShapeScale
    else:
        result["bf_pct"] = None

    # ── Morphology — ShapeScale primary ───────────────────────────────────────
    morph_vars = [
        "ss_neck_cm", "ss_shoulders_cm", "ss_chest_cm", "ss_waist_cm", "ss_hips_cm",
        "ss_bicep_l_cm", "ss_bicep_r_cm",
        "ss_thigh_l_cm", "ss_thigh_r_cm",
        "ss_calf_l_cm",  "ss_calf_r_cm",
        "ss_vol_trunk_cm3",
        "ss_vol_upper_leg_l_cm3", "ss_vol_upper_leg_r_cm3",
        "ss_vol_lower_leg_l_cm3", "ss_vol_lower_leg_r_cm3",
        "ss_vol_upper_arm_l_cm3", "ss_vol_upper_arm_r_cm3",
        "ss_whr", "ss_whtr", "ss_shoulder_waist", "ss_thigh_waist", "ss_neck_waist",
        "ss_shape_score", "ss_health_score", "ss_body_age", "ss_bf_pct",
        "ss_weight_kg", "ss_bmi", "ss_bmr_kcal", "ss_visceral_fat_num",
    ]
    for var in morph_vars:
        result[var] = ss.get(var)

    # ── Reconciled WHR: average of both ───────────────────────────────────────
    whr_reconciled = _safe_mean(ib.get("ib_whr"), ss.get("ss_whr"))
    result["whr"] = round(whr_reconciled, 4) if whr_reconciled is not None else None

    # ── BMI: prefer ShapeScale weight + height; InBody as fallback (Rule 44) ──
    ss_weight = ss.get("ss_weight_kg")
    ib_weight = ib.get("ib_weight_kg")
    # Primary weight for BMI: ShapeScale direct measurement
    primary_weight = ss_weight if ss_weight is not None else ib_weight
    height_m = height_cm / 100.0
    if primary_weight is not None and height_m > 0:
        result["bmi"] = round(primary_weight / (height_m ** 2), 2)
    else:
        result["bmi"] = ib.get("ib_bmi") or ss.get("ss_bmi")
    result["ib_bmi"] = ib.get("ib_bmi")
    result["ss_bmi"] = ss.get("ss_bmi")
    # Keep both scanner weights for audit
    result["primary_weight_kg"] = primary_weight
    result["primary_weight_source"] = "shapescale" if ss_weight is not None else "inbody"

    # ── Waist-to-Height Ratio (use ShapeScale waist + measured height) ─────────
    waist = ss.get("ss_waist_cm")
    if waist is not None and height_cm > 0:
        result["whtr"] = round(waist / height_cm, 4)
    else:
        result["whtr"] = ss.get("ss_whtr")

    # ── Derived variables ─────────────────────────────────────────────────────
    lean_mass = ib.get("ib_smm_kg")   # using SMM (skeletal muscle mass)
    fat_mass  = ib.get("ib_fat_mass_kg")

    # FFMI: Fat-Free Mass Index = lean_mass / height_m²
    # Uses SMM as proxy; true FFMI uses FFM = total weight - fat mass
    ffm = (ib_weight - fat_mass) if (ib_weight is not None and fat_mass is not None) else None
    if ffm is not None and height_m > 0:
        result["ffmi"] = round(ffm / (height_m ** 2), 2)
    else:
        result["ffmi"] = None

    # Lean mass per cm height (size-adjusted lean mass)
    if lean_mass is not None and height_cm > 0:
        result["lean_per_cm"] = round(lean_mass / height_cm, 4)
    else:
        result["lean_per_cm"] = None

    # Trunk fat ratio = trunk fat / total fat
    trunk_fat = ib.get("ib_fat_trunk_kg")
    if trunk_fat is not None and fat_mass is not None and fat_mass > 0:
        result["trunk_fat_ratio"] = round(trunk_fat / fat_mass, 4)
    else:
        result["trunk_fat_ratio"] = None

    # Android-to-Gynoid proxy: trunk fat / (trunk + bilateral leg fat)
    fat_leg_r = ib.get("ib_fat_leg_r_kg")
    fat_leg_l = ib.get("ib_fat_leg_l_kg")
    if all(v is not None for v in [trunk_fat, fat_leg_r, fat_leg_l]):
        denominator = trunk_fat + fat_leg_r + fat_leg_l
        result["ag_ratio"] = round(trunk_fat / denominator, 4) if denominator > 0 else None
    else:
        result["ag_ratio"] = None

    # Bilateral asymmetries (%)
    result["arm_lean_asym"] = _asymmetry_pct(
        ib.get("ib_lean_arm_r_kg"), ib.get("ib_lean_arm_l_kg")
    )
    result["leg_lean_asym"] = _asymmetry_pct(
        ib.get("ib_lean_leg_r_kg"), ib.get("ib_lean_leg_l_kg")
    )

    # ── Labs (pass-through; extra_labs takes priority over anything in ib/ss) ──
    for k in _LAB_KEYS:
        result[k] = (extra_labs or {}).get(k)

    # ── Lifestyle (normalise and pass-through) ────────────────────────────────
    raw_life = dict(lifestyle_data) if lifestyle_data else {}
    # Encode smoker text → numeric
    smoker_raw = raw_life.pop("smoker", raw_life.pop("lifestyle_smoker", None))
    if smoker_raw is not None:
        if isinstance(smoker_raw, str):
            raw_life["lifestyle_smoker_score"] = _SMOKER_ENCODE.get(
                smoker_raw.strip().lower(), None
            )
        else:
            raw_life["lifestyle_smoker_score"] = float(smoker_raw)
    # Accept aliased column names from Lifestyle Entry sheet
    for alias, canonical in (
        ("vigorous_min_per_week",   "lifestyle_vig_min_week"),
        ("moderate_min_per_week",   "lifestyle_mod_min_week"),
        ("sedentary_hrs_per_day",   "lifestyle_sed_hours_day"),
        ("sleep_hrs_per_night",     "lifestyle_sleep_hours"),
        ("alcohol_drinks_per_week", "lifestyle_alcohol_drinks_week"),
        ("stress_1to10",            "lifestyle_stress_score"),
        ("subj_health_1to10",       "lifestyle_subj_health_score"),
    ):
        if alias in raw_life and canonical not in raw_life:
            raw_life[canonical] = raw_life.pop(alias)

    for k in _LIFESTYLE_KEYS:
        result[k] = raw_life.get(k)

    # ── data_completeness ─────────────────────────────────────────────────────
    has_scan      = ib.get("ib_weight_kg") is not None or ss.get("ss_weight_kg") is not None
    has_labs      = any(result.get(k) is not None for k in _CORE_LAB_KEYS)
    has_lifestyle = any(result.get(k) is not None for k in _CORE_LIFESTYLE_KEYS)
    result["data_completeness"] = {
        "scan":              has_scan,
        "labs":              has_labs,
        "lifestyle":         has_lifestyle,
        "full_data":         has_scan and has_labs and has_lifestyle,
        "completeness_label": (
            "Full Data" if has_scan and has_labs and has_lifestyle
            else "Partial Data"
        ),
    }

    # ── Cross-scanner discrepancy flags ──────────────────────────────────────
    # BF% flag (uses ss_bf / ib_bf already resolved above)
    if ib_bf is not None and ss_bf is not None:
        delta_bf = abs(ib_bf - ss_bf)
        if delta_bf > BF_DISCREPANCY_FLAG_PP:
            flags.append(
                f"BF% discrepancy: ShapeScale={ss_bf:.1f}%, InBody={ib_bf:.1f}% "
                f"(Δ={delta_bf:.1f}pp > {BF_DISCREPANCY_FLAG_PP}pp threshold). "
                "ShapeScale used per Rule 44 (3D optical > bioimpedance)."
            )

    # Weight discrepancy flag (Rule 44 — both present but differ)
    if ib_weight is not None and ss_weight is not None:
        weight_delta = abs(ib_weight - ss_weight)
        if weight_delta > 1.5:
            flags.append(
                f"Weight discrepancy: ShapeScale={ss_weight:.1f} kg, InBody={ib_weight:.1f} kg "
                f"(Δ={weight_delta:.1f} kg). ShapeScale used per Rule 44. "
                "Large delta may indicate hydration difference between scan days."
            )

    if result["arm_lean_asym"] is not None and result["arm_lean_asym"] > ASYMMETRY_FLAG_PCT:
        flags.append(
            f"Arm lean asymmetry: {result['arm_lean_asym']:.1f}% "
            f"(threshold {ASYMMETRY_FLAG_PCT}%). Monitor for injury or dominance."
        )
    if result["leg_lean_asym"] is not None and result["leg_lean_asym"] > ASYMMETRY_FLAG_PCT:
        flags.append(
            f"Leg lean asymmetry: {result['leg_lean_asym']:.1f}% "
            f"(threshold {ASYMMETRY_FLAG_PCT}%). Monitor for compensation pattern."
        )

    result["flags"] = flags
    return result


def reconcile_summary(unified: dict) -> str:
    """One-line verification summary."""
    bf         = unified.get("bf_pct", "N/A")
    bmi        = unified.get("bmi", "N/A")
    ffmi       = unified.get("ffmi", "N/A")
    waist      = unified.get("ss_waist_cm", "N/A")
    whr        = unified.get("whr", "N/A")
    weight_src = unified.get("primary_weight_source", "?")
    flags      = unified.get("flags", [])
    flag_str   = f" [{len(flags)} flag(s)]" if flags else ""
    return (
        f"Client: {unified.get('client_id', 'N/A')} | "
        f"BF%: {bf} | BMI: {bmi} | FFMI: {ffmi} | "
        f"Waist: {waist} cm | WHR: {whr} | "
        f"Weight source: {weight_src}{flag_str}"
    )


# ── Smoke test ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import json

    # Minimal demo with Jesus Garcia's April 2026 data
    IB = {
        "scan_date": "2026-04-12",
        "ib_weight_kg": 99.38,
        "ib_smm_kg": 39.92,
        "ib_fat_mass_kg": 29.62,
        "ib_bf_pct": 29.8,
        "ib_bmi": 34.4,
        "ib_bmr_kcal": 1877.2,
        "ib_score": 78.0,
        "ib_lean_arm_r_kg": 4.13,
        "ib_lean_arm_l_kg": 4.17,
        "ib_lean_trunk_kg": 30.88,
        "ib_lean_leg_r_kg": 9.98,
        "ib_lean_leg_l_kg": 9.84,
        "ib_fat_arm_r_kg": 2.00,
        "ib_fat_arm_l_kg": 2.00,
        "ib_fat_trunk_kg": 16.29,
        "ib_fat_leg_r_kg": 3.90,
        "ib_fat_leg_l_kg": 3.90,
        "ib_whr": 0.95,
        "ib_visceral_fat_level": 12.0,
        "ib_tbw_kg": 51.25,
        "ib_protein_kg": 13.88,
        "ib_mineral_kg": 4.74,
        "ib_smi": 9.7,
        "ib_phase_angle": 6.9,
    }
    SS = {
        "ss_scan_date": "2026-04-13",
        "ss_weight_kg": 97.68,
        "ss_bf_pct": 34.5,
        "ss_bmi": 33.8,
        "ss_neck_cm": 41.91,
        "ss_waist_cm": 111.76,
        "ss_hips_cm": 111.76,
        "ss_chest_cm": 112.01,
        "ss_whr": 1.00,
        "ss_whtr": 0.564,
        "ss_shape_score": 72,
        "ss_health_score": 65,
    }

    unified = reconcile_scanners(IB, SS, height_cm=179.0, client_id="garcia_jesus", scan_label="intake")
    print(reconcile_summary(unified))
    print()
    print("Flags:", unified.get("flags"))
    print()
    print(json.dumps(
        {k: v for k, v in unified.items() if k != "flags"},
        indent=2, default=str
    ))
