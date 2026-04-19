"""
TNS Multidimensional Analysis System
Tasks 4 + 6: NHANES Reference Population Builder + Client Projection API

Builds five PCA models from NHANES 2017-2018 and 2015-2016 data:
  L1  Health Optimization  — body measures + lipids + metabolic + inflammation + BP
  L2  Body Composition     — DXA body comp + circumferences (2015-2016 DXA cycle)
  L3  Performance          — body measures + metabolic + physical activity
  L4  Weight Management    — body comp + metabolic markers
  L5  Longevity            — body measures + metabolic + inflammation + sarcopenia

Each model is serialised as a JSON file containing:
  - PCA loadings (sklearn PCA components array)
  - StandardScaler mean + std
  - Population PC1/PC2 scores (for plotting reference cloud)
  - Population percentile distribution (PC1)
  - Variable list, explained variance ratios, fit metadata

Usage
-----
    # Fit all models (run once in Colab — takes ~2 min):
    from tns_pca_pipeline import build_all_models
    build_all_models(nhanes_dir="/content/drive/MyDrive/.../NHANES_RAW",
                     out_dir="/content/drive/MyDrive/.../NHANES_RAW/models")

    # Project a client (daily use):
    from tns_pca_pipeline import project_client
    result = project_client(
        client_data=unified_dict,      # from tns_reconcile.reconcile_scanners()
        model_dir="/content/drive/MyDrive/.../NHANES_RAW/models",
        lens="auto",
        previous_projections=[
            {"pc1": -0.8, "pc2": 0.2, "date": "2026-01-15", "label": "intake"},
        ],
    )
    print(result["percentile_pc1"])     # 62.4
    print(result["top_drivers"])        # ["waist_cm", "bf_pct", "visceral_fat_level"]
"""

from __future__ import annotations

import json
import math
import os
import warnings
from pathlib import Path
from typing import Optional, Union

from tns_optimal_zones import assert_clinician_review_complete, ClinicalReviewPendingError  # noqa: F401

import numpy as np
import pandas as pd
from scipy import stats as scipy_stats
from sklearn.decomposition import PCA
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler

warnings.filterwarnings("ignore", category=pd.errors.DtypeWarning)

# ── NHANES file paths (relative to nhanes_dir) ──────────────────────────────
NHANES_2017_FILES: dict[str, str] = {
    "DEMO": "2017-2018/DEMO_J.XPT",
    "BMX":  "2017-2018/BMX_J.XPT",
    "BPX":  "2017-2018/BPX_J.XPT",
    "TCHOL":"2017-2018/TCHOL_J.XPT",
    "HDL":  "2017-2018/HDL_J.XPT",
    "TRIGLY":"2017-2018/TRIGLY_J.XPT",
    "GLU":  "2017-2018/GLU_J.XPT",
    "GHB":  "2017-2018/GHB_J.XPT",
    "INS":  "2017-2018/INS_J.XPT",
    "HSCRP":"2017-2018/HSCRP_J.XPT",
    "PAQ":  "2017-2018/PAQ_J.XPT",
}
NHANES_2015_FILES: dict[str, str] = {
    "DEMO": "2015-2016/DEMO_I.XPT",
    "BMX":  "2015-2016/BMX_I.XPT",
    "DXX":  "2015-2016/DXX_I.XPT",
    "DXXAG":"2015-2016/DXXAG_I.XPT",
}

# ── Variable extraction specs ────────────────────────────────────────────────
# format: (file_key, nhanes_column, generic_name, optional_transform)
# transform: None = pass-through; "g_to_kg" = divide by 1000
VARS_2017: list[tuple] = [
    # SEQN is loaded automatically as merge key — not listed here to avoid duplication
    ("DEMO",  "RIDAGEYR","age",            None),
    ("DEMO",  "RIAGENDR","sex",            None),   # 1=Male 2=Female
    ("DEMO",  "WTMEC2YR","sample_weight",  None),
    # Body measures
    ("BMX",   "BMXWT",   "weight_kg",      None),
    ("BMX",   "BMXHT",   "height_cm",      None),
    ("BMX",   "BMXBMI",  "bmi",            None),
    ("BMX",   "BMXWAIST","waist_cm",        None),
    ("BMX",   "BMXHIP",  "hip_cm",          None),
    # BMXTHICR / BMXCALF not collected in 2017-2018 cycle — omitted
    ("BMX",   "BMXARMC", "arm_cm",          None),
    # Blood pressure
    ("BPX",   "BPXSY1",  "sbp",            None),
    ("BPX",   "BPXDI1",  "dbp",            None),
    # Lipids / metabolic
    ("TCHOL", "LBXTC",   "total_chol",     None),
    ("HDL",   "LBDHDD",  "hdl",            None),
    ("TRIGLY","LBXTR",   "triglycerides",  None),
    ("TRIGLY","LBDLDL",  "ldl",            None),
    ("GLU",   "LBXGLU",  "glucose",        None),
    ("GHB",   "LBXGH",   "hba1c",          None),
    ("INS",   "LBXIN",   "insulin",        None),
    ("HSCRP", "LBXHSCRP","hscrp",          None),
    # Physical activity
    # Physical activity — raw columns; derived composite vars built in _build_nhanes_df
    ("PAQ",   "PAQ650",  "paq_vig_flag",   None),   # 1=yes vigorous rec activity
    ("PAQ",   "PAQ655",  "paq_vig_days",   None),   # days/wk vigorous rec
    ("PAQ",   "PAD660",  "paq_vig_min",    None),   # min/day vigorous rec  (PAD prefix in 2017-2018)
    ("PAQ",   "PAQ665",  "paq_mod_flag",   None),   # 1=yes moderate rec activity
    ("PAQ",   "PAQ670",  "paq_mod_days",   None),   # days/wk moderate rec
    ("PAQ",   "PAD675",  "paq_mod_min",    None),   # min/day moderate rec  (PAD prefix in 2017-2018)
    ("PAQ",   "PAD680",  "paq_sed_min",    None),   # min/day sedentary
]

VARS_2015: list[tuple] = [
    # SEQN is loaded automatically as merge key — not listed here to avoid duplication
    ("DEMO",  "RIDAGEYR","age",             None),
    ("DEMO",  "RIAGENDR","sex",             None),
    ("BMX",   "BMXWT",   "weight_kg",       None),
    ("BMX",   "BMXHT",   "height_cm",       None),
    ("BMX",   "BMXBMI",  "bmi",             None),
    ("BMX",   "BMXWAIST","waist_cm",         None),
    ("BMX",   "BMXHIP",  "hip_cm",           None),
    ("BMX",   "BMXTHICR","thigh_cm",         None),
    ("BMX",   "BMXCALF", "calf_cm",          None),
    ("BMX",   "BMXARMC", "arm_cm",           None),
    # DXA whole body
    ("DXX",   "DXDTOPF", "bf_pct",          None),   # total body fat %
    ("DXX",   "DXDTOFM", "fat_mass_kg",     "g_to_kg"),
    ("DXX",   "DXDTOLBM","lean_mass_kg",    "g_to_kg"),
    # DXA android/gynoid
    ("DXXAG", "DXDAGF",  "android_fat_pct", None),
    ("DXXAG", "DXDGYNF", "gynoid_fat_pct",  None),
]

# ── Lens definitions ─────────────────────────────────────────────────────────
# Each lens specifies which NHANES cycle to use and which generic variable names.
# Variables with ≥ 40% missingness after merge are auto-dropped at fit time.
LENS_DEFS: dict[str, dict] = {
    "health": {
        "cycle": "2017",
        "vars": [
            "bmi", "waist_cm", "hip_cm", "thigh_cm", "arm_cm",
            "whr", "whtr",
            "sbp", "dbp",
            "total_chol", "hdl", "ldl", "triglycerides",
            "glucose", "hba1c", "insulin", "hscrp",
        ],
        "n_components": 5,
        "description": "Health Optimization — body measures + lipids + metabolic + inflammation + BP",
    },
    "body_comp": {
        "cycle": "2015",
        "vars": [
            "bmi", "weight_kg", "bf_pct", "fat_mass_kg", "lean_mass_kg",
            "android_fat_pct", "gynoid_fat_pct",
            "waist_cm", "hip_cm", "thigh_cm", "calf_cm", "arm_cm",
            "whr", "whtr", "ffmi",
        ],
        "n_components": 5,
        "description": "Body Composition — DXA body comp + circumferences",
    },
    "performance": {
        "cycle": "2017",
        "vars": [
            "bmi", "waist_cm", "hip_cm", "arm_cm", "thigh_cm",
            "glucose", "hba1c",
            "sbp", "dbp",
            "pa_vig_min_week", "pa_mod_min_week", "pa_sed_hours_day",
        ],
        "n_components": 5,
        "description": "Performance — body measures + metabolic + physical activity",
    },
    "weight_mgmt": {
        "cycle": "2017",
        "vars": [
            "bmi", "waist_cm", "whr",
            "glucose", "insulin", "triglycerides", "hba1c",
            "sbp", "total_chol", "hdl",
        ],
        "n_components": 5,
        "description": "Weight Management — body comp + metabolic markers",
    },
    "longevity": {
        "cycle": "2017",
        "vars": [
            "bmi", "waist_cm", "arm_cm",
            "glucose", "hba1c", "triglycerides", "hdl",
            "sbp", "dbp", "hscrp",
        ],
        "n_components": 5,
        "description": "Longevity — body measures + metabolic + inflammation",
    },
}

# ── Client-to-model variable mapping ─────────────────────────────────────────
# Keys: unified dict keys from tns_reconcile.reconcile_scanners()
# Values: generic NHANES model variable names
CLIENT_TO_MODEL: dict[str, str] = {
    "bmi":                  "bmi",
    "ib_bmi":               "bmi",
    "ss_bmi":               "bmi",
    "ib_weight_kg":         "weight_kg",
    "ss_weight_kg":         "weight_kg",
    "height_cm":            "height_cm",
    "bf_pct":               "bf_pct",
    "ib_bf_pct":            "bf_pct",
    "ib_fat_mass_kg":       "fat_mass_kg",
    "ib_smm_kg":            "lean_mass_kg",     # SMM ≈ lean mass for projection
    "ffmi":                 "ffmi",
    "ss_waist_cm":          "waist_cm",
    "ss_hips_cm":           "hip_cm",
    "ss_thigh_r_cm":        "thigh_cm",
    "ss_thigh_l_cm":        "thigh_cm",         # averaged below
    "ss_calf_r_cm":         "calf_cm",
    "ss_bicep_r_cm":        "arm_cm",
    "whr":                  "whr",
    "whtr":                 "whtr",
    "ag_ratio":             "android_fat_pct",  # approximation
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
    # Lifestyle (physical activity — maps to NHANES PAQ composites)
    "lifestyle_vig_min_week":  "pa_vig_min_week",
    "lifestyle_mod_min_week":  "pa_mod_min_week",
    "lifestyle_sed_hours_day": "pa_sed_hours_day",
    # Aliases used when pasting directly from Lifestyle Entry sheet columns
    "vigorous_min_per_week":   "pa_vig_min_week",
    "moderate_min_per_week":   "pa_mod_min_week",
    "sedentary_hrs_per_day":   "pa_sed_hours_day",
}

# Variables that indicate lab availability (for auto lens selection)
LAB_VARS = {"total_chol", "hdl", "ldl", "triglycerides", "glucose", "hba1c", "insulin", "hscrp"}

# Variables that indicate lifestyle/PA availability
LIFESTYLE_CORE_VARS = {"pa_vig_min_week", "pa_mod_min_week", "pa_sed_hours_day"}

LENS_PRIORITY = ["health", "longevity", "weight_mgmt", "performance", "body_comp"]

# Required variables per lens for full-data classification
# (a lens is "full" when ≥ this fraction of its vars are provided, not imputed)
FULL_DATA_THRESHOLD = 0.70


# ── NHANES loading helpers ───────────────────────────────────────────────────

def _load_xpt(path: Path, cols: list[str]) -> pd.DataFrame:
    """
    Load an XPT file, returning only requested columns that actually exist.
    Prints a warning for any requested columns not found (to help debug NHANES
    variable name changes across cycles).
    """
    df = pd.read_sas(str(path), format="xport", encoding="latin-1")
    df.columns = [c.upper() for c in df.columns]
    missing = [c for c in cols if c not in df.columns]
    if missing:
        print(f"  [WARN] {path.name}: expected columns not found — {missing}")
        print(f"         Available: {sorted(df.columns.tolist())}")
    present = [c for c in cols if c in df.columns]
    return df[present].copy()


def _build_nhanes_df(nhanes_dir: Path, cycle: str) -> pd.DataFrame:
    """
    Load and merge all files for a given cycle.
    Returns a wide DataFrame with generic variable names.
    Filtered to adults 20–65 with valid height/weight.
    """
    if cycle == "2017":
        file_map = NHANES_2017_FILES
        var_specs = VARS_2017
    else:
        file_map = NHANES_2015_FILES
        var_specs = VARS_2015

    # Group specs by file key
    file_to_cols: dict[str, list[tuple]] = {}
    for spec in var_specs:
        fkey = spec[0]
        if fkey not in file_to_cols:
            file_to_cols[fkey] = []
        file_to_cols[fkey].append(spec)

    # Load each file
    frames: list[pd.DataFrame] = []
    for fkey, specs in file_to_cols.items():
        if fkey not in file_map:
            print(f"  [SKIP] No file mapping for {fkey}")
            continue
        fpath = nhanes_dir / file_map[fkey]
        if not fpath.exists():
            print(f"  [SKIP] File not found: {fpath}")
            continue
        nhanes_cols = list(dict.fromkeys(["SEQN"] + [s[1] for s in specs]))  # dedup
        df_raw = _load_xpt(fpath, nhanes_cols)
        # Rename to generic names
        rename = {s[1]: s[2] for s in specs if s[1] in df_raw.columns}
        df_raw = df_raw.rename(columns=rename)
        # Apply transforms
        for spec in specs:
            generic = spec[2]
            transform = spec[3] if len(spec) > 3 else None
            if transform == "g_to_kg" and generic in df_raw.columns:
                df_raw[generic] = df_raw[generic] / 1000.0
        frames.append(df_raw)

    if not frames:
        raise RuntimeError(f"No NHANES files loaded for cycle {cycle}. Check nhanes_dir.")

    # Merge on SEQN (left join from DEMO outward).
    # DEMO renames SEQN → "seqn" via VARS spec; normalise it back to uppercase
    # so all frames share the same join key name.
    merged = frames[0]
    if "seqn" in merged.columns:
        merged = merged.rename(columns={"seqn": "SEQN"})
    for df in frames[1:]:
        if "SEQN" in df.columns:
            merged = merged.merge(df, on="SEQN", how="left", suffixes=("", "_dup"))
            # Drop duplicate columns from suffixes
            dup_cols = [c for c in merged.columns if c.endswith("_dup")]
            merged = merged.drop(columns=dup_cols)

    # ── Age filter: adults 20–65 ──
    if "age" in merged.columns:
        merged = merged[(merged["age"] >= 20) & (merged["age"] <= 65)]

    # ── Derive PA composite variables from raw PAQ columns ────────────────
    # PAQ flags: 1=Yes, 2=No. Multiply days × min only when flag==1.
    if "paq_vig_days" in merged.columns and "paq_vig_min" in merged.columns:
        vig_active = (merged.get("paq_vig_flag", pd.Series(2, index=merged.index)) == 1)
        merged["pa_vig_min_week"] = np.where(
            vig_active,
            merged["paq_vig_days"].fillna(0) * merged["paq_vig_min"].fillna(0),
            0.0
        )
    if "paq_mod_days" in merged.columns and "paq_mod_min" in merged.columns:
        mod_active = (merged.get("paq_mod_flag", pd.Series(2, index=merged.index)) == 1)
        merged["pa_mod_min_week"] = np.where(
            mod_active,
            merged["paq_mod_days"].fillna(0) * merged["paq_mod_min"].fillna(0),
            0.0
        )
    if "paq_sed_min" in merged.columns:
        merged["pa_sed_hours_day"] = merged["paq_sed_min"] / 60.0

    # Drop raw PAQ staging columns
    raw_paq_cols = [c for c in merged.columns if c.startswith("paq_")]
    merged = merged.drop(columns=raw_paq_cols, errors="ignore")

    # ── Require valid height and weight ──
    for req in ["height_cm", "weight_kg", "bmi"]:
        if req in merged.columns:
            merged = merged[merged[req].notna() & (merged[req] > 0)]
            break

    # ── Derive WHR and WHtR if possible ──
    if "waist_cm" in merged.columns and "hip_cm" in merged.columns:
        merged["whr"] = (merged["waist_cm"] / merged["hip_cm"]).round(4)
    if "waist_cm" in merged.columns and "height_cm" in merged.columns:
        merged["whtr"] = (merged["waist_cm"] / merged["height_cm"]).round(4)

    # ── Derive FFMI for 2015 cycle (has DXA lean mass + height) ──
    if "lean_mass_kg" in merged.columns and "height_cm" in merged.columns:
        ht_m = merged["height_cm"] / 100
        merged["ffmi"] = (merged["lean_mass_kg"] / (ht_m ** 2)).round(2)

    # ── Remove extreme outliers (|z| > 5 per numeric column) ──
    num_cols = merged.select_dtypes(include=[np.number]).columns.difference(
        ["SEQN", "age", "sex", "sample_weight"]   # SEQN was uppercased during load
    )
    z_scores = merged[num_cols].apply(lambda x: np.abs((x - x.mean()) / x.std()))
    outlier_mask = (z_scores > 5).any(axis=1)
    n_removed = outlier_mask.sum()
    if n_removed > 0:
        print(f"  [INFO] Removed {n_removed} extreme outliers (|z|>5) from {cycle} data")
    merged = merged[~outlier_mask]

    print(f"  [INFO] Cycle {cycle}: {len(merged)} adults 20-65 after filters")
    return merged


def _fit_lens(
    df: pd.DataFrame,
    lens_name: str,
    lens_def: dict,
    n_components: int = 5,
    max_missing_pct: float = 0.40,
) -> dict:
    """
    Fit StandardScaler + PCA for one lens.
    Returns a serialisable model dict.
    """
    desired_vars = lens_def["vars"]

    # Keep only variables that exist AND have <max_missing_pct missingness
    available_vars: list[str] = []
    dropped_vars: list[str] = []
    missing_pcts: dict[str, float] = {}
    for v in desired_vars:
        if v not in df.columns:
            dropped_vars.append(v)
            continue
        miss_pct = df[v].isna().mean()
        missing_pcts[v] = round(float(miss_pct), 4)
        if miss_pct > max_missing_pct:
            dropped_vars.append(v)
            print(f"    [DROP] {v}: {miss_pct:.1%} missing > {max_missing_pct:.0%} threshold")
        else:
            available_vars.append(v)

    if len(available_vars) < 3:
        raise RuntimeError(
            f"Lens '{lens_name}' has only {len(available_vars)} usable variables. "
            "Cannot fit PCA. Check NHANES variable names."
        )
    if dropped_vars:
        print(f"    [WARN] Dropped from '{lens_name}': {dropped_vars}")
    print(f"    [OK]   '{lens_name}' fitting on {len(available_vars)} vars: {available_vars}")

    X_raw = df[available_vars].values.astype(float)

    # Median imputation (population reference — median appropriate for skewed distributions)
    imputer = SimpleImputer(strategy="median")
    X_imp = imputer.fit_transform(X_raw)
    imputer_medians = imputer.statistics_.tolist()

    # StandardScaler
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X_imp)

    # PCA — fit on full scaled data
    n_comp = min(n_components, len(available_vars), X_scaled.shape[0] - 1)
    pca = PCA(n_components=n_comp, random_state=42)
    pca.fit(X_scaled)

    # Population PC scores (all participants, first 2 components)
    pop_scores_2d: list[list[float]] = pca.transform(X_scaled)[:, :2].tolist()

    # PC1 percentile distribution
    pc1_vals = np.array([s[0] for s in pop_scores_2d])
    pct_breaks = [5, 10, 25, 50, 75, 90, 95]
    pc1_percentiles: dict[str, float] = {
        f"p{p}": round(float(np.percentile(pc1_vals, p)), 4)
        for p in pct_breaks
    }
    pc1_percentiles.update({
        "mean": round(float(pc1_vals.mean()), 4),
        "std":  round(float(pc1_vals.std()), 4),
    })

    # PC1 loadings (first component)
    pc1_loadings: dict[str, float] = {
        v: round(float(pca.components_[0, i]), 6)
        for i, v in enumerate(available_vars)
    }

    # For percentile scoring of a new point on PC1
    # We use the empirical CDF stored as the sorted population scores
    pc1_sorted = sorted(pc1_vals.tolist())

    return {
        "lens": lens_name,
        "description": lens_def["description"],
        "n_components": n_comp,
        "variables": available_vars,
        "dropped_variables": dropped_vars,
        "scaler": {
            "mean":  [round(float(v), 6) for v in scaler.mean_],
            "std":   [round(float(v), 6) for v in scaler.scale_],
        },
        "imputer": {
            "strategy": "median",
            "medians":  [round(float(v), 6) for v in imputer_medians],
        },
        "pca": {
            "components":              [[round(float(x), 8) for x in row]
                                        for row in pca.components_],
            "explained_variance_ratio": [round(float(v), 6)
                                         for v in pca.explained_variance_ratio_],
            "cumulative_variance":      [
                round(float(np.sum(pca.explained_variance_ratio_[:i+1])), 6)
                for i in range(n_comp)
            ],
        },
        "population": {
            "n_participants":  int(X_scaled.shape[0]),
            "pc_scores_2d":    pop_scores_2d,           # list of [pc1, pc2]
            "pc1_distribution": pc1_percentiles,
            "pc1_sorted":      [round(float(v), 6) for v in pc1_sorted],
            "pc1_loadings":    pc1_loadings,
        },
        "missing_pct_by_var": {k: missing_pcts.get(k, 0.0) for k in available_vars},
        "fit_info": {
            "nhanes_cycle": lens_def["cycle"],
            "age_range":    [20, 65],
            "n_included":   int(X_scaled.shape[0]),
            "fit_date":     pd.Timestamp.now().strftime("%Y-%m-%d"),
        },
    }


# ── Public: build all models ─────────────────────────────────────────────────

def build_all_models(
    nhanes_dir: Union[str, Path],
    out_dir: Union[str, Path],
    lenses: Optional[list[str]] = None,
) -> dict[str, Path]:
    """
    Fit all five PCA lens models and save as JSON.

    Parameters
    ----------
    nhanes_dir : str or Path
        Path to the NHANES_RAW/ folder containing 2017-2018/ and 2015-2016/ subdirs.
    out_dir : str or Path
        Output folder for JSON model files (will be created if needed).
    lenses : list[str], optional
        Subset of lenses to build. Defaults to all five.

    Returns
    -------
    dict[str, Path]
        Mapping of lens_name → output JSON path.
    """
    nhanes_dir = Path(nhanes_dir)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    if lenses is None:
        lenses = list(LENS_DEFS.keys())

    # Load each NHANES cycle once
    print("=" * 60)
    print("TNS PCA Pipeline — Building Reference Population Models")
    print("=" * 60)
    dfs: dict[str, pd.DataFrame] = {}
    for lens_name in lenses:
        cycle = LENS_DEFS[lens_name]["cycle"]
        if cycle not in dfs:
            print(f"\n[Loading NHANES {cycle}]")
            dfs[cycle] = _build_nhanes_df(nhanes_dir, cycle)

    saved: dict[str, Path] = {}
    for lens_name in lenses:
        cycle = LENS_DEFS[lens_name]["cycle"]
        lens_def = LENS_DEFS[lens_name]
        print(f"\n[Fitting lens: {lens_name.upper()}]")
        try:
            model = _fit_lens(dfs[cycle], lens_name, lens_def, n_components=5)
            out_path = out_dir / f"pca_model_{lens_name}.json"
            with open(out_path, "w", encoding="utf-8") as fh:
                json.dump(model, fh, indent=2)
            saved[lens_name] = out_path
            ev = model["pca"]["explained_variance_ratio"]
            print(f"    Saved → {out_path.name}  "
                  f"(PC1 {ev[0]:.1%}, PC2 {ev[1]:.1%})")
        except Exception as exc:
            print(f"    [ERROR] Could not fit lens '{lens_name}': {exc}")

    print(f"\n[Done] {len(saved)}/{len(lenses)} models saved to {out_dir}")
    return saved


# ── Public: load a model ─────────────────────────────────────────────────────

def load_model(model_path: Union[str, Path]) -> dict:
    """Load a previously saved JSON model."""
    path = Path(model_path)
    if not path.exists():
        raise FileNotFoundError(f"Model not found: {path}")
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def load_all_models(model_dir: Union[str, Path]) -> dict[str, dict]:
    """Load all pca_model_*.json files from a directory. Returns {lens_name: model}."""
    model_dir = Path(model_dir)
    models: dict[str, dict] = {}
    for lens in LENS_DEFS:
        path = model_dir / f"pca_model_{lens}.json"
        if path.exists():
            models[lens] = load_model(path)
    return models


# ── Public: project a client ─────────────────────────────────────────────────

def _compute_data_completeness(
    client_data: dict,
    n_vars_provided: int,
    n_vars_total: int,
) -> dict:
    """
    Return a completeness summary dict.
    'full' = provided fraction ≥ FULL_DATA_THRESHOLD and no lab vars missing.
    """
    has_scan     = any(client_data.get(k) is not None for k in ("ib_weight_kg", "ss_weight_kg"))
    has_labs     = any(client_data.get(f"lab_{k}") is not None for k in
                       ("total_chol", "hdl", "ldl", "triglycerides", "glucose", "hba1c"))
    has_lifestyle = any(client_data.get(k) is not None for k in
                        ("lifestyle_vig_min_week", "lifestyle_mod_min_week",
                         "lifestyle_sed_hours_day",
                         "vigorous_min_per_week", "moderate_min_per_week"))
    provided_fraction = n_vars_provided / max(n_vars_total, 1)
    is_full = provided_fraction >= FULL_DATA_THRESHOLD

    return {
        "scan":                has_scan,
        "labs":                has_labs,
        "lifestyle":           has_lifestyle,
        "full_data":           is_full,
        "provided_pct":        round(provided_fraction * 100, 1),
        "completeness_label":  "Full Data" if is_full else "Partial Data",
    }


def _map_client_to_model_vars(client_data: dict) -> dict:
    """
    Translate reconcile_scanners() output keys to generic model variable names.
    Handles bilateral average (e.g., thigh_l / thigh_r → thigh_cm).
    Returns a flat dict of {generic_name: float_or_None}.
    """
    mapped: dict[str, Optional[float]] = {}
    for client_key, model_key in CLIENT_TO_MODEL.items():
        val = client_data.get(client_key)
        if val is not None:
            if model_key in mapped and mapped[model_key] is not None:
                # Average bilateral values (thigh_l + thigh_r → thigh_cm)
                mapped[model_key] = round((mapped[model_key] + float(val)) / 2, 4)
            else:
                mapped[model_key] = float(val)
    return mapped


def _percentile_from_population(pc1_score: float, pc1_sorted: list[float]) -> float:
    """
    Empirical percentile of a new PC1 score against the reference population.
    Returns 0–100.
    """
    arr = np.array(pc1_sorted)
    n_below = int(np.searchsorted(arr, pc1_score, side="right"))
    return round(n_below / len(arr) * 100, 1)


def _select_lens_auto(model_vars: dict, models: dict[str, dict]) -> str:
    """
    Auto-select the richest available lens given the client's variable coverage.
    Logic: prefer lenses with more available model variables;
    upgrade to 'health' if any lab vars are present.
    """
    lab_present = any(model_vars.get(v) is not None for v in LAB_VARS)

    if lab_present and "health" in models:
        return "health"

    best_lens = None
    best_count = -1
    for lens_name in LENS_PRIORITY:
        if lens_name not in models:
            continue
        lens_vars = models[lens_name]["variables"]
        coverage = sum(1 for v in lens_vars if model_vars.get(v) is not None)
        if coverage > best_count:
            best_count = coverage
            best_lens = lens_name

    return best_lens or LENS_PRIORITY[-1]


def project_client(
    client_data: dict,
    model_dir: Union[str, Path, None] = None,
    models: Optional[dict[str, dict]] = None,
    lens: str = "auto",
    previous_projections: Optional[list[dict]] = None,
    lab_data: Optional[dict] = None,
    lifestyle_data: Optional[dict] = None,
) -> dict:
    """
    Project a client onto the PCA reference population.

    Parameters
    ----------
    client_data : dict
        Output from tns_reconcile.reconcile_scanners(). Input is never mutated.
        May already contain lab_* and/or lifestyle_* fields; lab_data and
        lifestyle_data kwargs will override any existing values if provided.
    model_dir : str or Path, optional
        Directory containing pca_model_*.json files.
        Not needed if `models` is supplied directly.
    models : dict[str, dict], optional
        Pre-loaded models dict from load_all_models(). Avoids re-loading from disk.
    lens : str
        Lens name: "health" | "body_comp" | "performance" | "weight_mgmt" | "longevity"
        or "auto" (default) to pick the richest available lens.
    previous_projections : list[dict], optional
        Prior scan results for trajectory calculation. Each entry:
        {"pc1": float, "pc2": float, "date": "YYYY-MM-DD", "label": str}
    lab_data : dict, optional
        Lab values keyed as lab_total_chol, lab_hdl, lab_ldl, lab_triglycerides,
        lab_glucose, lab_hba1c, lab_insulin, lab_hscrp, lab_sbp, lab_dbp.
        Merged into client_data before projection. Overrides any same-key values.
    lifestyle_data : dict, optional
        Lifestyle values keyed as lifestyle_vig_min_week, lifestyle_mod_min_week,
        lifestyle_sed_hours_day, lifestyle_sleep_hours, lifestyle_smoker_score,
        lifestyle_alcohol_drinks_week, lifestyle_stress_score,
        lifestyle_subj_health_score.
        Merged into client_data before projection. Overrides any same-key values.

    Returns
    -------
    dict with keys:
        pc1, pc2               : float  — position in PC space
        percentile_pc1         : float  — 0-100 vs reference population
        lens_used              : str
        n_vars_provided        : int    — client vars matched to model
        n_vars_imputed         : int    — vars not provided, filled with median
        imputed_vars           : list[str]
        top_drivers            : list[str]  — top 5 variables by PC1 loading
        pc1_loadings           : dict[str, float]  — all variable loadings on PC1
        explained_variance     : dict   — PC1, PC2 explained variance ratios
        trajectory             : dict | None  — delta from most recent prior scan
        cross_scanner_flags    : list[str]  — from reconcile step
        data_completeness      : dict   — scan/labs/lifestyle booleans + full_data flag
    """
    assert_clinician_review_complete("tns_pca_pipeline.project_client")
    client_data = dict(client_data)  # defensive copy — never mutate caller's dict

    # Merge lab and lifestyle overrides
    if lab_data:
        for k, v in lab_data.items():
            if v is not None:
                client_data[k] = v
    if lifestyle_data:
        for k, v in lifestyle_data.items():
            if v is not None:
                client_data[k] = v

    # Load models
    if models is None:
        if model_dir is None:
            raise ValueError("Either model_dir or models must be provided.")
        models = load_all_models(model_dir)

    if not models:
        raise RuntimeError("No models available. Run build_all_models() first.")

    # Translate client keys → model variable names
    model_vars = _map_client_to_model_vars(client_data)

    # Select lens
    if lens == "auto":
        lens_used = _select_lens_auto(model_vars, models)
    else:
        if lens not in models:
            available = list(models.keys())
            raise ValueError(f"Lens '{lens}' not found. Available: {available}")
        lens_used = lens

    model = models[lens_used]
    variables: list[str] = model["variables"]
    scaler_mean = np.array(model["scaler"]["mean"])
    scaler_std  = np.array(model["scaler"]["std"])
    pca_components = np.array(model["pca"]["components"])   # (n_comp, n_vars)
    imputer_medians = np.array(model["imputer"]["medians"])

    # ── Assemble client feature vector ───────────────────────────────────────
    x_raw = np.array([model_vars.get(v) for v in variables], dtype=object)

    n_provided = sum(1 for v in x_raw if v is not None)
    imputed_vars = [variables[i] for i, v in enumerate(x_raw) if v is None]
    n_imputed = len(imputed_vars)

    # Fill missing values with population medians
    x_filled = np.array([
        float(v) if v is not None else float(imputer_medians[i])
        for i, v in enumerate(x_raw)
    ], dtype=float)

    # ── Scale and project ─────────────────────────────────────────────────────
    x_scaled = (x_filled - scaler_mean) / scaler_std
    pc_scores = pca_components @ x_scaled          # shape: (n_comp,)

    pc1 = float(pc_scores[0])
    pc2 = float(pc_scores[1]) if len(pc_scores) > 1 else 0.0

    # ── Percentile ────────────────────────────────────────────────────────────
    pc1_sorted = model["population"]["pc1_sorted"]
    pct_pc1 = _percentile_from_population(pc1, pc1_sorted)

    # ── Top drivers (PC1 loadings ranked by absolute magnitude) ──────────────
    pc1_loadings = model["population"]["pc1_loadings"]
    top_drivers = sorted(pc1_loadings, key=lambda k: abs(pc1_loadings[k]), reverse=True)[:5]

    # ── Trajectory ────────────────────────────────────────────────────────────
    trajectory: Optional[dict] = None
    if previous_projections:
        # Use the most recent prior projection that matches this lens
        prior_lens_projections = [
            p for p in previous_projections
            if p.get("lens_used", lens_used) == lens_used
        ]
        if not prior_lens_projections:
            prior_lens_projections = previous_projections  # fallback

        most_recent = sorted(prior_lens_projections, key=lambda p: p.get("date", ""))[-1]
        delta_pc1 = pc1 - float(most_recent.get("pc1", pc1))
        delta_pc2 = pc2 - float(most_recent.get("pc2", pc2))
        delta_pct = pct_pc1 - float(most_recent.get("percentile_pc1", pct_pc1))

        trajectory = {
            "delta_pc1":         round(delta_pc1, 4),
            "delta_pc2":         round(delta_pc2, 4),
            "delta_percentile":  round(delta_pct, 1),
            "direction":         "improved" if delta_pct > 1 else
                                 "declined" if delta_pct < -1 else "stable",
            "prior_date":        most_recent.get("date"),
            "prior_label":       most_recent.get("label"),
            "prior_pc1":         most_recent.get("pc1"),
            "prior_percentile":  most_recent.get("percentile_pc1"),
        }

    ev = model["pca"]["explained_variance_ratio"]
    completeness = _compute_data_completeness(client_data, n_provided, len(variables))

    # ── PCA visualization dict (coordinates for population cloud plots) ───────
    pca_visualization = {
        "pc1":                round(pc1, 4),
        "pc2":                round(pc2, 4),
        "percentile_pc1":     pct_pc1,
        "lens_used":          lens_used,
        "lens_description":   model["description"],
        "n_vars_provided":    n_provided,
        "n_vars_total":       len(variables),
        "n_vars_imputed":     n_imputed,
        "imputed_vars":       imputed_vars,
        "top_drivers":        top_drivers,
        "pc1_loadings":       pc1_loadings,
        "explained_variance": {
            "pc1": ev[0] if ev else None,
            "pc2": ev[1] if len(ev) > 1 else None,
        },
        "trajectory":         trajectory,
    }

    # ── Polygon v2 scoring (optimal-zone based, primary score) ───────────────
    # Lazy import so the module is optional during NHANES model builds.
    polygon_result: Optional[dict] = None
    try:
        from tns_polygon_scorer import score_polygon
        from tns_questionnaire import parse_questionnaire as _parse_q
        q_raw = client_data.get("questionnaire")
        questionnaire = _parse_q(q_raw) if isinstance(q_raw, dict) else None
        sex            = str(client_data.get("sex", "male")).lower()
        athlete_status = str(client_data.get("athlete_status", "recreational")).lower()
        polygon_result = score_polygon(
            unified        = client_data,
            questionnaire  = questionnaire,
            sex            = sex,
            athlete_status = athlete_status,
            client_id      = client_data.get("client_id"),
        )
        # Embed PCA visualization coordinates into the polygon result
        polygon_result["pca_visualization"] = pca_visualization
    except ImportError:
        # tns_polygon_scorer not yet available — return legacy format only
        pass

    # ── Build output dict ─────────────────────────────────────────────────────
    if polygon_result is not None:
        # v2 schema: polygon result is primary; legacy PCA keys retained at top
        # level for backward compat with existing Streamlit app and notebooks.
        return {
            **polygon_result,              # overall_score, categories, confidence, …
            # Legacy flat keys (used by app.py and notebooks until they migrate)
            "pc1":                pca_visualization["pc1"],
            "pc2":                pca_visualization["pc2"],
            "percentile_pc1":     pct_pc1,
            "lens_used":          lens_used,
            "lens_description":   model["description"],
            "n_vars_provided":    n_provided,
            "n_vars_total":       len(variables),
            "n_vars_imputed":     n_imputed,
            "imputed_vars":       imputed_vars,
            "top_drivers":        top_drivers,
            "pc1_loadings":       pc1_loadings,
            "explained_variance": pca_visualization["explained_variance"],
            "trajectory":         trajectory,
            # cross_scanner_flags comes from polygon_result (already set there)
            "data_completeness":  completeness,
        }
    else:
        # Fallback: legacy v1 schema when polygon scorer unavailable
        return {
            **pca_visualization,
            "cross_scanner_flags": client_data.get("flags", []),
            "data_completeness":   completeness,
        }


# ── Validation plots (quick diagnostic) ─────────────────────────────────────

def validate_model(model: dict) -> None:
    """
    Print a quick text-based validation report for a fitted model.
    Does not require matplotlib.
    """
    print(f"\n{'='*50}")
    print(f"Model: {model['lens'].upper()} — {model['description']}")
    print(f"{'='*50}")
    print(f"N participants : {model['fit_info']['n_included']}")
    print(f"Variables ({len(model['variables'])}): {model['variables']}")
    if model.get("dropped_variables"):
        print(f"Dropped        : {model['dropped_variables']}")
    print(f"\nExplained variance:")
    for i, (ev, cum) in enumerate(zip(
        model["pca"]["explained_variance_ratio"],
        model["pca"]["cumulative_variance"]
    )):
        print(f"  PC{i+1}: {ev:.1%}  (cumulative {cum:.1%})")
    print(f"\nPC1 distribution (reference population):")
    dist = model["population"]["pc1_distribution"]
    for k in ["p5", "p25", "mean", "p75", "p95"]:
        print(f"  {k:5s}: {dist.get(k, 'N/A'):.3f}")
    print(f"\nTop PC1 loadings:")
    loadings = model["population"]["pc1_loadings"]
    ranked = sorted(loadings.items(), key=lambda x: abs(x[1]), reverse=True)
    for var, loading in ranked[:8]:
        bar_len = int(abs(loading) * 30)
        direction = "+" if loading > 0 else "-"
        bar = direction * bar_len
        print(f"  {var:25s} {loading:+.4f}  {bar}")


# ── CLI entry point ──────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    args = sys.argv[1:]
    if not args or args[0] in ("-h", "--help"):
        print("Usage:")
        print("  python tns_pca_pipeline.py build <nhanes_dir> <model_dir>")
        print("  python tns_pca_pipeline.py validate <model_dir> [lens]")
        sys.exit(0)

    cmd = args[0]

    if cmd == "build":
        nhanes_dir = args[1] if len(args) > 1 else "."
        model_dir  = args[2] if len(args) > 2 else "./models"
        build_all_models(nhanes_dir, model_dir)

    elif cmd == "validate":
        model_dir_arg = args[1] if len(args) > 1 else "./models"
        lens_filter   = args[2] if len(args) > 2 else None
        loaded = load_all_models(model_dir_arg)
        if not loaded:
            print(f"No models found in {model_dir_arg}")
            sys.exit(1)
        for lens_name, m in loaded.items():
            if lens_filter is None or lens_filter == lens_name:
                validate_model(m)
