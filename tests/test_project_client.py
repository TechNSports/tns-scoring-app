"""
TNS PCA Pipeline — Integration tests for project_client()

Covers three completeness scenarios using fixtures built from
Jesus Garcia's April 2026 intake scans (real InBody + ShapeScale data)
with synthetic representative labs:

  jesus_full.json       — scan + labs + lifestyle  → Full Data
  jesus_scan_only.json  — scan only                → Partial Data
  jesus_scan_labs.json  — scan + labs, no lifestyle → Partial Data

Each test uses stub PCA models so no NHANES files are required at test time.
The stub models produce finite, deterministic PC scores and allow assertions
on data_completeness, lens selection, and return-dict structure.

Run with:
    cd 02_MEXICO/PCA_Pipeline
    pytest tests/test_project_client.py -v
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path
from typing import Any

import pytest

# ── Import path setup ────────────────────────────────────────────────────────
# Tests live in tests/ one level below the pipeline modules
PIPELINE_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(PIPELINE_DIR))

from tns_pca_pipeline import project_client  # noqa: E402

# ── Fixture paths ────────────────────────────────────────────────────────────
FIXTURES_DIR = Path(__file__).parent / "fixtures"

FIXTURE_FULL      = FIXTURES_DIR / "jesus_full.json"
FIXTURE_SCAN_ONLY = FIXTURES_DIR / "jesus_scan_only.json"
FIXTURE_SCAN_LABS = FIXTURES_DIR / "jesus_scan_labs.json"

# ── Required return keys (contract) ─────────────────────────────────────────
REQUIRED_KEYS = {
    "pc1", "pc2", "percentile_pc1", "lens_used", "lens_description",
    "n_vars_provided", "n_vars_total", "n_vars_imputed", "imputed_vars",
    "top_drivers", "pc1_loadings", "explained_variance",
    "trajectory", "cross_scanner_flags", "data_completeness",
}

# ── Lens variable definitions (mirrors LENS_DEFS in tns_pca_pipeline.py) ────
_LENS_VARS: dict[str, list[str]] = {
    "health": [
        "bmi", "waist_cm", "hip_cm", "arm_cm",
        "total_chol", "hdl", "ldl", "triglycerides",
        "glucose", "hba1c", "insulin", "hscrp", "sbp", "dbp",
        "whr", "whtr",
    ],
    "body_comp": [
        "lean_mass_kg", "fat_mass_kg", "fat_trunk_kg",
        "android_fat_pct", "gynoid_fat_pct",
        "waist_cm", "hip_cm", "thigh_cm", "calf_cm", "arm_cm",
        "whr", "whtr", "ffmi",
    ],
    "performance": [
        "bmi", "waist_cm", "hip_cm", "arm_cm", "thigh_cm",
        "glucose", "hba1c", "sbp", "dbp",
        "pa_vig_min_week", "pa_mod_min_week", "pa_sed_hours_day",
    ],
    "weight_mgmt": [
        "bmi", "waist_cm", "whr",
        "glucose", "insulin", "triglycerides", "hba1c",
        "sbp", "total_chol", "hdl",
    ],
    "longevity": [
        "bmi", "waist_cm", "arm_cm",
        "glucose", "hba1c", "triglycerides", "hdl",
        "sbp", "dbp", "hscrp",
    ],
}

_LENS_DESCRIPTIONS: dict[str, str] = {
    "health":     "Health Optimization — body measures + lipids + metabolic + inflammation + BP",
    "body_comp":  "Body Composition — DXA body comp + circumferences",
    "performance":"Performance — body measures + metabolic + physical activity",
    "weight_mgmt":"Weight Management — body comp + metabolic markers",
    "longevity":  "Longevity — body measures + metabolic + inflammation",
}


def _stub_model(lens_name: str) -> dict[str, Any]:
    """
    Build a minimal but structurally valid PCA model for testing.

    Uses:
      - scaler mean=0, std=1 (identity scaling)
      - imputer median=0 (missing vars impute to 0)
      - PCA PC1: equal positive loading on all vars → PC1 = mean(scaled_vals)
      - PCA PC2: alternating +/- loadings → PC2 ≈ contrast between odd/even vars
      - Population: 100 synthetic participants with PC1 scores ~ N(0, 1)

    This is sufficient for arithmetic correctness checks and completeness-flag
    assertions. The exact PC1 value is not asserted (it depends on fixture values).
    """
    variables = _LENS_VARS[lens_name]
    n_vars = len(variables)
    n_comp = min(2, n_vars)

    # Equal-weight first component
    w = 1.0 / math.sqrt(n_vars)
    components: list[list[float]] = [[w] * n_vars]
    if n_comp > 1:
        # Alternating-sign second component (orthogonal by construction)
        alt = [(1.0 if i % 2 == 0 else -1.0) / math.sqrt(n_vars) for i in range(n_vars)]
        components.append(alt)

    # Synthetic population: 100 participants, PC1 ~ uniform(-2, 2)
    pop_size = 100
    pc1_sorted = [round(-2.0 + 4.0 * i / (pop_size - 1), 4) for i in range(pop_size)]
    pc1_loadings = {v: round(w, 6) for v in variables}
    pop_scores_2d = [[round(s, 4), 0.0] for s in pc1_sorted]

    return {
        "lens":        lens_name,
        "description": _LENS_DESCRIPTIONS[lens_name],
        "n_components": n_comp,
        "variables":   variables,
        "dropped_variables": [],
        "scaler": {
            "mean": [0.0] * n_vars,
            "std":  [1.0] * n_vars,
        },
        "imputer": {
            "strategy": "median",
            "medians":  [0.0] * n_vars,
        },
        "pca": {
            "components":              components,
            "explained_variance_ratio": [0.35] + ([0.20] if n_comp > 1 else []),
            "cumulative_variance":      [0.35] + ([0.55] if n_comp > 1 else []),
        },
        "population": {
            "n_participants": pop_size,
            "pc_scores_2d":  pop_scores_2d,
            "pc1_distribution": {
                "p5": -1.6, "p10": -1.2, "p25": -0.8, "p50": 0.0,
                "p75": 0.8, "p90": 1.2, "p95": 1.6,
                "mean": 0.0, "std": 1.0,
            },
            "pc1_sorted":   pc1_sorted,
            "pc1_loadings": pc1_loadings,
        },
        "missing_pct_by_var": {v: 0.0 for v in variables},
        "fit_info": {
            "nhanes_cycle": "2017",
            "age_range": [20, 65],
            "n_included": pop_size,
            "fit_date": "2026-04-16",
        },
    }


def _stub_models() -> dict[str, Any]:
    """Return stub models for all five lenses."""
    return {name: _stub_model(name) for name in _LENS_VARS}


# ── Helpers ──────────────────────────────────────────────────────────────────

def _load_fixture(path: Path) -> dict:
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    # Strip the _fixture_meta key — project_client doesn't know about it
    data.pop("_fixture_meta", None)
    return data


def _assert_valid_result(result: dict, fixture_name: str) -> None:
    """Common structural assertions for any project_client() return value."""
    assert isinstance(result, dict), f"[{fixture_name}] result must be a dict"

    missing = REQUIRED_KEYS - result.keys()
    assert not missing, f"[{fixture_name}] missing keys: {missing}"

    assert isinstance(result["pc1"], float), f"[{fixture_name}] pc1 must be float"
    assert isinstance(result["pc2"], float), f"[{fixture_name}] pc2 must be float"
    assert math.isfinite(result["pc1"]), f"[{fixture_name}] pc1 must be finite"
    assert math.isfinite(result["pc2"]), f"[{fixture_name}] pc2 must be finite"

    pct = result["percentile_pc1"]
    assert 0.0 <= pct <= 100.0, f"[{fixture_name}] percentile_pc1={pct} must be 0–100"

    assert result["lens_used"] in _LENS_VARS, (
        f"[{fixture_name}] lens_used='{result['lens_used']}' not a known lens"
    )

    dc = result["data_completeness"]
    assert isinstance(dc, dict), f"[{fixture_name}] data_completeness must be dict"
    for flag in ("scan", "labs", "lifestyle", "full_data"):
        assert flag in dc, f"[{fixture_name}] data_completeness missing '{flag}'"
        assert isinstance(dc[flag], bool), (
            f"[{fixture_name}] data_completeness['{flag}'] must be bool"
        )
    assert dc["completeness_label"] in ("Full Data", "Partial Data"), (
        f"[{fixture_name}] unexpected completeness_label='{dc['completeness_label']}'"
    )

    assert isinstance(result["top_drivers"], list), (
        f"[{fixture_name}] top_drivers must be list"
    )
    assert isinstance(result["n_vars_provided"], int), (
        f"[{fixture_name}] n_vars_provided must be int"
    )
    assert result["n_vars_provided"] >= 0

    assert isinstance(result["imputed_vars"], list)
    assert result["n_vars_imputed"] == len(result["imputed_vars"]), (
        f"[{fixture_name}] n_vars_imputed / imputed_vars length mismatch"
    )


# ── Tests: jesus_full ────────────────────────────────────────────────────────

class TestJesusFull:
    """Fixture: scan + labs + lifestyle.  Expected: Full Data, health lens."""

    def setup_method(self):
        self.data = _load_fixture(FIXTURE_FULL)
        self.models = _stub_models()

    def test_returns_valid_result(self):
        result = project_client(self.data, models=self.models)
        _assert_valid_result(result, "jesus_full")

    def test_completeness_full_data(self):
        result = project_client(self.data, models=self.models)
        dc = result["data_completeness"]
        assert dc["scan"]      is True,  "scan flag must be True for full fixture"
        assert dc["labs"]      is True,  "labs flag must be True (all core labs provided)"
        assert dc["lifestyle"] is True,  "lifestyle flag must be True (PA vars provided)"
        assert dc["full_data"] is True,  "full_data must be True when all three present"
        assert dc["completeness_label"] == "Full Data"

    def test_auto_selects_health_lens(self):
        result = project_client(self.data, models=self.models, lens="auto")
        assert result["lens_used"] == "health", (
            "health lens should be selected when lab values are present"
        )

    def test_all_five_lenses_project_without_error(self):
        for lens_name in _LENS_VARS:
            result = project_client(self.data, models=self.models, lens=lens_name)
            _assert_valid_result(result, f"jesus_full/{lens_name}")

    def test_no_trajectory_without_prior(self):
        result = project_client(self.data, models=self.models)
        assert result["trajectory"] is None

    def test_trajectory_with_prior_projection(self):
        prior = [{"pc1": -0.5, "pc2": 0.1, "date": "2026-01-15",
                  "label": "pre-intake", "percentile_pc1": 35.0,
                  "lens_used": "health"}]
        result = project_client(self.data, models=self.models,
                                 previous_projections=prior)
        traj = result["trajectory"]
        assert traj is not None
        assert "delta_pc1" in traj
        assert "direction" in traj
        assert traj["direction"] in ("improved", "declined", "stable")

    def test_lab_data_kwarg_overrides_fixture_labs(self):
        """lab_data kwarg should override any existing lab_* in client_data."""
        override_labs = {"lab_total_chol": 165.0, "lab_glucose": 85.0}
        result = project_client(self.data, models=self.models,
                                 lab_data=override_labs, lens="health")
        _assert_valid_result(result, "jesus_full/lab_override")

    def test_cross_scanner_flags_propagated(self):
        result = project_client(self.data, models=self.models)
        flags = result["cross_scanner_flags"]
        assert isinstance(flags, list)
        # Jesus's intake has a 4.7pp BF% discrepancy — flag must be present
        assert len(flags) >= 1, "Expected at least one cross-scanner flag (BF% delta)"


# ── Tests: jesus_scan_only ───────────────────────────────────────────────────

class TestJesusScanOnly:
    """Fixture: scan only — labs and lifestyle absent.  Regression test."""

    def setup_method(self):
        self.data = _load_fixture(FIXTURE_SCAN_ONLY)
        self.models = _stub_models()

    def test_returns_valid_result(self):
        result = project_client(self.data, models=self.models)
        _assert_valid_result(result, "jesus_scan_only")

    def test_completeness_partial_data(self):
        result = project_client(self.data, models=self.models)
        dc = result["data_completeness"]
        assert dc["scan"]      is True,  "scan must be True (InBody weight is present)"
        assert dc["labs"]      is False, "labs must be False (all lab_* are null)"
        assert dc["lifestyle"] is False, "lifestyle must be False (all lifestyle_* are null)"
        assert dc["full_data"] is False, "full_data must be False when labs/lifestyle missing"
        assert dc["completeness_label"] == "Partial Data"

    def test_does_not_select_health_lens_auto(self):
        """health lens requires lab vars; scan-only data should not trigger it."""
        result = project_client(self.data, models=self.models, lens="auto")
        assert result["lens_used"] != "health", (
            "health lens must not be selected when no lab values are present"
        )

    def test_all_five_lenses_project_without_error(self):
        for lens_name in _LENS_VARS:
            result = project_client(self.data, models=self.models, lens=lens_name)
            _assert_valid_result(result, f"jesus_scan_only/{lens_name}")

    def test_missing_lab_vars_are_imputed(self):
        """With scan-only data, all lab model variables should be in imputed_vars."""
        result = project_client(self.data, models=self.models, lens="health")
        lab_model_vars = {"total_chol", "hdl", "ldl", "triglycerides",
                         "glucose", "hba1c", "insulin", "hscrp"}
        imputed = set(result["imputed_vars"])
        for lv in lab_model_vars:
            assert lv in imputed, f"lab var '{lv}' should be imputed when labs are absent"


# ── Tests: jesus_scan_labs ───────────────────────────────────────────────────

class TestJesusScanLabs:
    """Fixture: scan + labs, no lifestyle.  Partial Data; health lens active."""

    def setup_method(self):
        self.data = _load_fixture(FIXTURE_SCAN_LABS)
        self.models = _stub_models()

    def test_returns_valid_result(self):
        result = project_client(self.data, models=self.models)
        _assert_valid_result(result, "jesus_scan_labs")

    def test_completeness_partial_data(self):
        result = project_client(self.data, models=self.models)
        dc = result["data_completeness"]
        assert dc["scan"]      is True,  "scan must be True"
        assert dc["labs"]      is True,  "labs must be True (core lab values provided)"
        assert dc["lifestyle"] is False, "lifestyle must be False (no lifestyle entry)"
        assert dc["full_data"] is False, "full_data must be False (missing lifestyle)"
        assert dc["completeness_label"] == "Partial Data"

    def test_auto_selects_health_lens(self):
        """Labs present → health lens preferred regardless of lifestyle absence."""
        result = project_client(self.data, models=self.models, lens="auto")
        assert result["lens_used"] == "health", (
            "health lens should be selected when labs are present, even without lifestyle"
        )

    def test_all_five_lenses_project_without_error(self):
        for lens_name in _LENS_VARS:
            result = project_client(self.data, models=self.models, lens=lens_name)
            _assert_valid_result(result, f"jesus_scan_labs/{lens_name}")

    def test_lifestyle_vars_imputed_in_performance_lens(self):
        """PA vars should be imputed when lifestyle_* is absent."""
        result = project_client(self.data, models=self.models, lens="performance")
        pa_vars = {"pa_vig_min_week", "pa_mod_min_week", "pa_sed_hours_day"}
        imputed = set(result["imputed_vars"])
        for pv in pa_vars:
            assert pv in imputed, f"PA var '{pv}' should be imputed without lifestyle data"

    def test_lifestyle_kwarg_fills_pa_vars(self):
        """Passing lifestyle_data kwarg should reduce imputed PA vars."""
        lifestyle = {
            "lifestyle_vig_min_week":  90.0,
            "lifestyle_mod_min_week":  120.0,
            "lifestyle_sed_hours_day": 7.5,
        }
        result = project_client(self.data, models=self.models,
                                 lifestyle_data=lifestyle, lens="performance")
        imputed = set(result["imputed_vars"])
        for pv in ["pa_vig_min_week", "pa_mod_min_week", "pa_sed_hours_day"]:
            assert pv not in imputed, (
                f"PA var '{pv}' should NOT be imputed when lifestyle_data is provided"
            )


# ── Sanity: fixture files exist ───────────────────────────────────────────────

def test_fixture_files_exist():
    for path, name in [
        (FIXTURE_FULL,      "jesus_full.json"),
        (FIXTURE_SCAN_ONLY, "jesus_scan_only.json"),
        (FIXTURE_SCAN_LABS, "jesus_scan_labs.json"),
    ]:
        assert path.exists(), f"Fixture file missing: {name}"


def test_fixture_data_completeness_flags_match_content():
    """
    Validate that the completeness flags embedded in each fixture JSON match
    what the actual data contains (i.e., the fixture was constructed correctly).
    """
    checks = [
        (FIXTURE_FULL,      True,  True,  True),
        (FIXTURE_SCAN_ONLY, False, False, False),
        (FIXTURE_SCAN_LABS, True,  False, False),
    ]
    core_lab_keys   = ["lab_total_chol", "lab_hdl", "lab_ldl", "lab_triglycerides",
                       "lab_glucose", "lab_hba1c"]
    core_life_keys  = ["lifestyle_vig_min_week", "lifestyle_mod_min_week",
                       "lifestyle_sed_hours_day"]

    for path, expect_labs, expect_life, expect_full in checks:
        data = _load_fixture(path)
        has_labs = any(data.get(k) is not None for k in core_lab_keys)
        has_life = any(data.get(k) is not None for k in core_life_keys)
        has_scan = data.get("ib_weight_kg") is not None

        assert has_scan, f"{path.name}: ib_weight_kg must be non-null"
        assert has_labs  == expect_labs,  f"{path.name}: labs presence mismatch"
        assert has_life  == expect_life,  f"{path.name}: lifestyle presence mismatch"

        dc = data["data_completeness"]
        assert dc["scan"]      == True,         f"{path.name}: dc.scan should be True"
        assert dc["labs"]      == expect_labs,  f"{path.name}: dc.labs mismatch"
        assert dc["lifestyle"] == expect_life,  f"{path.name}: dc.lifestyle mismatch"
        assert dc["full_data"] == expect_full,  f"{path.name}: dc.full_data mismatch"
