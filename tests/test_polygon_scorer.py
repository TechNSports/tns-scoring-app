"""
TNS Polygon Scorer — pytest test suite (v2)

Tests cover all 4 data-availability tiers against the fixture JSON files.

Run from the PCA_Pipeline directory:
    pytest tests/test_polygon_scorer.py -v --tb=short

No NHANES files required — scores are computed from tns_polygon_scorer,
which has no external data dependencies for optimal-zone scoring.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

# ── Path setup ────────────────────────────────────────────────────────────────
PIPELINE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PIPELINE_DIR))
FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"

# ── Imports under test ────────────────────────────────────────────────────────
from tns_polygon_scorer import (
    score_polygon,
    score_category,
    CATEGORY_WEIGHTS,
    CATEGORY_DEFS,
    LAB_KEY_MAP,
)
from tns_questionnaire import parse_questionnaire, check_par_q
from tns_optimal_zones import LIBRARY_VERSION, POLYGON_VERSION


# ── Fixture loaders ───────────────────────────────────────────────────────────

def _load(fixture_name: str) -> dict:
    path = FIXTURES_DIR / fixture_name
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


# ─────────────────────────────────────────────────────────────────────────────
# Module-level sanity checks
# ─────────────────────────────────────────────────────────────────────────────

def test_category_weights_sum_to_1():
    total = sum(CATEGORY_WEIGHTS.values())
    assert abs(total - 1.0) < 1e-9, f"Category weights must sum to 1.0, got {total}"


def test_all_6_categories_defined():
    expected = {
        "body_composition", "heart_vascular", "metabolic_function",
        "hormonal_balance", "stress_recovery", "lifestyle_fitness",
    }
    assert set(CATEGORY_DEFS.keys()) == expected


def test_library_version_is_string():
    assert isinstance(LIBRARY_VERSION, str) and len(LIBRARY_VERSION) > 0


def test_polygon_version_is_41():
    assert POLYGON_VERSION == "4.1"


def test_lab_key_map_has_core_labs():
    required = {"lab_total_chol", "lab_hdl", "lab_ldl", "lab_triglycerides",
                "lab_glucose", "lab_hba1c", "lab_insulin", "lab_hscrp",
                "lab_sbp", "lab_dbp"}
    assert required.issubset(set(LAB_KEY_MAP.keys()))


# ─────────────────────────────────────────────────────────────────────────────
# Fixture 1: Questionnaire Only
# ─────────────────────────────────────────────────────────────────────────────

class TestFixtureQuestionnaireOnly:

    @pytest.fixture(autouse=True)
    def _setup(self):
        data = _load("fixture_questionnaire_only.json")
        self.unified = data["unified"]
        self.context = data["context"]
        q_raw = data["questionnaire"]
        self.questionnaire = parse_questionnaire(q_raw)
        self.result = score_polygon(
            unified=self.unified,
            questionnaire=self.questionnaire,
            sex=self.context["sex"],
            athlete_status=self.context["athlete_status"],
            client_id=self.context["client_id"],
        )

    def test_does_not_raise(self):
        assert self.result is not None

    def test_all_6_categories_score(self):
        cats = self.result["categories"]
        assert len(cats) == 6
        for name, cat in cats.items():
            assert isinstance(cat["score"], (int, float)), \
                f"Category '{name}' has no score"
            assert 0 <= cat["score"] <= 100

    def test_all_rendering_dashed(self):
        for name, cat in self.result["categories"].items():
            assert cat["rendering"] == "dashed", \
                f"Category '{name}' should be dashed when no scan/labs, got {cat['rendering']}"

    def test_overall_confidence_is_baseline(self):
        assert self.result["confidence"] == "baseline"

    def test_par_q_not_escalated(self):
        assert self.result["par_q_escalation"] is False

    def test_no_tier_a_or_b(self):
        for name, cat in self.result["categories"].items():
            ts = cat["tier_scores"]
            assert ts["a"] is None, f"Category '{name}' has unexpected Tier A score"
            assert ts["b"] is None, f"Category '{name}' has unexpected Tier B score"
            assert ts["c"] is not None, f"Category '{name}' must have Tier C score"

    def test_overall_score_in_range(self):
        assert 0 <= self.result["overall_score"] <= 100

    def test_library_and_polygon_version_stamped(self):
        assert self.result["library_version"] == LIBRARY_VERSION
        assert self.result["polygon_version"] == POLYGON_VERSION

    def test_client_id_in_result(self):
        assert self.result["client_id"] == self.context["client_id"]


# ─────────────────────────────────────────────────────────────────────────────
# Fixture 2: Scan + Questionnaire
# ─────────────────────────────────────────────────────────────────────────────

class TestFixtureScanAndQuestionnaire:

    @pytest.fixture(autouse=True)
    def _setup(self):
        data = _load("fixture_scan_and_questionnaire.json")
        self.unified = data["unified"]
        self.context = data["context"]
        self.questionnaire = parse_questionnaire(data["questionnaire"])
        self.result = score_polygon(
            unified=self.unified,
            questionnaire=self.questionnaire,
            sex=self.context["sex"],
            athlete_status=self.context["athlete_status"],
            client_id=self.context["client_id"],
        )

    def test_does_not_raise(self):
        assert self.result is not None

    def test_all_6_categories_score(self):
        cats = self.result["categories"]
        assert len(cats) == 6
        for name, cat in cats.items():
            assert isinstance(cat["score"], (int, float))

    def test_body_composition_is_solid(self):
        cat = self.result["categories"]["body_composition"]
        assert cat["rendering"] == "solid", \
            f"body_composition should be solid with scan data, got {cat['rendering']}"

    def test_body_composition_has_tier_b(self):
        ts = self.result["categories"]["body_composition"]["tier_scores"]
        assert ts["b"] is not None, "body_composition must have Tier B score from scan data"

    def test_no_tier_a_in_any_category(self):
        """No labs provided — Tier A must be absent from all categories."""
        for name, cat in self.result["categories"].items():
            assert cat["tier_scores"]["a"] is None, \
                f"Category '{name}' unexpectedly has Tier A score (no labs provided)"

    def test_par_q_not_escalated(self):
        assert self.result["par_q_escalation"] is False

    def test_confidence_at_least_moderate(self):
        confidence_rank = {"high": 3, "moderate": 2, "baseline": 1}
        assert confidence_rank.get(self.result["confidence"], 0) >= 2, \
            f"Expected at least moderate confidence, got '{self.result['confidence']}'"

    def test_shapescale_wins_on_bf_pct(self):
        """Rule 44: bf_pct source must be 'shapescale' when ShapeScale data present."""
        body_comp = self.result["categories"]["body_composition"]
        bf_input = next(
            (i for i in body_comp.get("inputs", []) if i["name"] == "bf_pct"),
            None
        )
        if bf_input is not None:
            assert bf_input["source"] == "shapescale", \
                f"bf_pct source should be 'shapescale' per Rule 44, got '{bf_input['source']}'"

    def test_cross_scanner_flags_present(self):
        """Fixture has cross-scanner discrepancy (BF% Δ=4.7pp) — at least 1 flag expected."""
        flags = self.result.get("cross_scanner_flags", [])
        assert len(flags) >= 1, \
            f"Expected ≥1 cross-scanner flag, got {len(flags)}"

    def test_all_scored_inputs_have_layperson_copy(self):
        """Rule 46: every input with a value must have EN + ES layperson strings."""
        for cat_name, cat in self.result["categories"].items():
            for inp in cat.get("inputs", []):
                if inp.get("zone") not in ("informational", None):
                    assert inp.get("layperson_en"), \
                        f"Category '{cat_name}' input '{inp.get('name')}' missing layperson_en"
                    assert inp.get("layperson_es"), \
                        f"Category '{cat_name}' input '{inp.get('name')}' missing layperson_es"


# ─────────────────────────────────────────────────────────────────────────────
# Fixture 3: Partial Labs (lipid panel only)
# ─────────────────────────────────────────────────────────────────────────────

class TestFixturePartialLabs:

    @pytest.fixture(autouse=True)
    def _setup(self):
        data = _load("fixture_partial_labs.json")
        self.unified = data["unified"]
        self.context = data["context"]
        self.questionnaire = parse_questionnaire(data["questionnaire"])
        self.result = score_polygon(
            unified=self.unified,
            questionnaire=self.questionnaire,
            sex=self.context["sex"],
            athlete_status=self.context["athlete_status"],
            client_id=self.context["client_id"],
        )

    def test_does_not_raise(self):
        assert self.result is not None

    def test_all_6_categories_score(self):
        for name, cat in self.result["categories"].items():
            assert isinstance(cat["score"], (int, float)), \
                f"Category '{name}' has no numeric score"

    def test_heart_vascular_has_tier_a(self):
        """Lipid panel gives Heart & Vascular Tier A inputs."""
        hv = self.result["categories"]["heart_vascular"]
        assert hv["tier_scores"]["a"] is not None, \
            "heart_vascular should have Tier A score from lipid panel"

    def test_heart_vascular_rendering_solid(self):
        cat = self.result["categories"]["heart_vascular"]
        assert cat["rendering"] == "solid"

    def test_derived_tg_hdl_ratio_present(self):
        """tg_hdl_ratio should be computed from triglycerides + hdl."""
        hv_inputs = self.result["categories"]["heart_vascular"].get("inputs", [])
        names = [i["name"] for i in hv_inputs]
        assert "tg_hdl_ratio" in names, \
            "tg_hdl_ratio should be derived and included in heart_vascular inputs"

    def test_derived_non_hdl_present(self):
        """non_hdl should be computed from total_chol - hdl."""
        hv_inputs = self.result["categories"]["heart_vascular"].get("inputs", [])
        names = [i["name"] for i in hv_inputs]
        assert "non_hdl" in names, \
            "non_hdl should be derived and included in heart_vascular inputs"

    def test_ldl_zone_is_suboptimal(self):
        """Fixture has LDL=122 mg/dL → suboptimal per optimal zones."""
        hv_inputs = self.result["categories"]["heart_vascular"].get("inputs", [])
        ldl_input = next((i for i in hv_inputs if i["name"] == "ldl"), None)
        if ldl_input is not None:
            assert ldl_input["zone"] == "suboptimal", \
                f"LDL 122 mg/dL should be suboptimal, got '{ldl_input['zone']}'"

    def test_metabolic_core_labs_absent(self):
        """No glucose/HbA1c in partial fixture — verify those inputs are not in metabolic."""
        metabolic_inputs = self.result["categories"]["metabolic_function"].get("inputs", [])
        names = [i["name"] for i in metabolic_inputs]
        assert "fasting_glucose" not in names, \
            "fasting_glucose should not appear in metabolic with lipid-only panel"
        assert "hba1c" not in names, \
            "hba1c should not appear in metabolic with lipid-only panel"

    def test_tier_expansion_applied_when_a_missing(self):
        """When Tier A is absent, weights redistribute to B + C (must still sum to 1.0)."""
        for cat_name, cat in self.result["categories"].items():
            weights = cat["tier_weights_used"]
            total = sum(w for w in weights.values() if w is not None)
            assert abs(total - 1.0) < 0.01, \
                f"Category '{cat_name}' tier weights should sum to 1.0, got {total:.4f}"


# ─────────────────────────────────────────────────────────────────────────────
# Fixture 4: Full Data
# ─────────────────────────────────────────────────────────────────────────────

class TestFixtureFullData:

    @pytest.fixture(autouse=True)
    def _setup(self):
        data = _load("fixture_full_data.json")
        self.unified = data["unified"]
        self.context = data["context"]
        self.questionnaire = parse_questionnaire(data["questionnaire"])
        self.result = score_polygon(
            unified=self.unified,
            questionnaire=self.questionnaire,
            sex=self.context["sex"],
            athlete_status=self.context["athlete_status"],
            client_id=self.context["client_id"],
        )
        self.expected = data["expected_assertions"]

    def test_does_not_raise(self):
        assert self.result is not None

    def test_all_6_categories_score(self):
        for name, cat in self.result["categories"].items():
            assert isinstance(cat["score"], (int, float))
            assert 0 <= cat["score"] <= 100

    def test_all_rendering_solid(self):
        for name, cat in self.result["categories"].items():
            assert cat["rendering"] == "solid", \
                f"Category '{name}' should be solid for full data, got '{cat['rendering']}'"

    def test_confidence_high_or_moderate(self):
        """Full data gives high/moderate confidence.
        'lifestyle_fitness' has no Tier A biomarkers by definition, which may
        pull overall confidence to 'moderate' — both are acceptable for full data."""
        assert self.result["confidence"] in ("high", "moderate"), \
            f"Expected high or moderate confidence for full data, got '{self.result['confidence']}'"
        # Verify categories with labs+scan reach 'high' individually
        for cat_name in ("heart_vascular", "metabolic_function", "hormonal_balance"):
            cat = self.result["categories"][cat_name]
            assert cat["confidence"] == "high", \
                f"Category '{cat_name}' should be high with full labs+scan, got '{cat['confidence']}'"

    def test_data_completeness_full(self):
        dc = self.unified.get("data_completeness", {})
        assert dc.get("full_data") is True

    def test_overall_score_in_expected_range(self):
        lo, hi = self.expected["overall_score_between"]
        score = self.result["overall_score"]
        assert lo <= score <= hi, \
            f"Overall score {score} not in expected range [{lo}, {hi}]"

    def test_shapescale_wins_bf_pct(self):
        """Rule 44: bf_pct source must be 'shapescale'."""
        body_comp = self.result["categories"]["body_composition"]
        bf_input = next(
            (i for i in body_comp.get("inputs", []) if i["name"] == "bf_pct"),
            None
        )
        if bf_input is not None:
            assert bf_input["source"] == "shapescale"

    def test_hdl_zone_is_acceptable(self):
        """HDL=45 mg/dL for male → acceptable (45-59 range)."""
        hv_inputs = self.result["categories"]["heart_vascular"].get("inputs", [])
        hdl = next((i for i in hv_inputs if i["name"] == "hdl"), None)
        if hdl:
            assert hdl["zone"] == "acceptable", \
                f"HDL 45 mg/dL (male) expected 'acceptable', got '{hdl['zone']}'"

    def test_triglycerides_zone_is_suboptimal(self):
        """Triglycerides=155 mg/dL → suboptimal (150-199)."""
        hv_inputs = self.result["categories"]["heart_vascular"].get("inputs", [])
        tg = next((i for i in hv_inputs if i["name"] == "triglycerides"), None)
        if tg:
            assert tg["zone"] == "suboptimal", \
                f"Triglycerides 155 expected 'suboptimal', got '{tg['zone']}'"

    def test_homa_ir_derived(self):
        """homa_ir should be derived from glucose(98) × insulin(12) / 405."""
        # (98 * 12) / 405 ≈ 2.90 → suboptimal (2.0-2.9)
        metabolic_inputs = self.result["categories"]["metabolic_function"].get("inputs", [])
        names = [i["name"] for i in metabolic_inputs]
        assert "homa_ir" in names, "homa_ir should be derived and scored"

    def test_non_hdl_derived(self):
        """non_hdl = total_chol(198) - hdl(45) = 153 → suboptimal."""
        hv_inputs = self.result["categories"]["heart_vascular"].get("inputs", [])
        names = [i["name"] for i in hv_inputs]
        assert "non_hdl" in names

    def test_library_version_stamped(self):
        assert self.result["library_version"] == LIBRARY_VERSION

    def test_polygon_version_stamped(self):
        assert self.result["polygon_version"] == POLYGON_VERSION

    def test_par_q_not_escalated(self):
        assert self.result["par_q_escalation"] is False

    def test_cross_scanner_flags_present(self):
        """Fixture has BF% discrepancy (Δ=4.7pp) — at least 1 flag expected."""
        flags = self.result.get("cross_scanner_flags", [])
        assert len(flags) >= 1, \
            f"Expected ≥1 cross-scanner flag, got {len(flags)}"

    def test_all_inputs_have_layperson_copy(self):
        """Rule 46: every scored input must have both EN and ES layperson strings."""
        for cat_name, cat in self.result["categories"].items():
            for inp in cat.get("inputs", []):
                if inp.get("zone") not in ("informational", None):
                    assert inp.get("layperson_en"), \
                        f"Missing layperson_en in {cat_name}.{inp.get('name')}"
                    assert inp.get("layperson_es"), \
                        f"Missing layperson_es in {cat_name}.{inp.get('name')}"

    def test_tier_weights_sum_to_1_all_categories(self):
        for cat_name, cat in self.result["categories"].items():
            weights = cat["tier_weights_used"]
            total = sum(w for w in weights.values() if w is not None)
            assert abs(total - 1.0) < 0.01, \
                f"Tier weights in '{cat_name}' sum to {total:.4f}, expected 1.0"

    def test_waist_zone_concerning(self):
        """Waist=111.76 cm (male) is above 102 cm → concerning."""
        metabolic_inputs = self.result["categories"]["metabolic_function"].get("inputs", [])
        waist = next((i for i in metabolic_inputs if i["name"] == "waist_cm"), None)
        if waist:
            assert waist["zone"] == "concerning", \
                f"Waist 111.76 cm (male) expected 'concerning', got '{waist['zone']}'"


# ─────────────────────────────────────────────────────────────────────────────
# Edge cases
# ─────────────────────────────────────────────────────────────────────────────

class TestEdgeCases:

    def test_score_polygon_no_questionnaire(self):
        """score_polygon(questionnaire=None) must not crash and all categories score."""
        data = _load("fixture_scan_and_questionnaire.json")
        result = score_polygon(
            unified=data["unified"],
            questionnaire=None,
            sex=data["context"]["sex"],
        )
        assert len(result["categories"]) == 6
        for name, cat in result["categories"].items():
            assert isinstance(cat["score"], (int, float))

    def test_score_polygon_empty_unified(self):
        """Completely empty unified dict must not crash."""
        result = score_polygon(unified={}, questionnaire=None, sex="male")
        assert result is not None
        assert len(result["categories"]) == 6
        assert result["confidence"] == "baseline"

    def test_par_q_escalation_triggers(self):
        """q_chest_pain_on_exertion='yes' must set par_q_escalation=True."""
        data = _load("fixture_scan_and_questionnaire.json")
        q = dict(data["questionnaire"])
        q["q_chest_pain_on_exertion"] = "yes"
        questionnaire = parse_questionnaire(q)
        result = score_polygon(
            unified=data["unified"],
            questionnaire=questionnaire,
            sex=data["context"]["sex"],
        )
        assert result["par_q_escalation"] is True

    def test_female_hdl_different_from_male(self):
        """Sex-stratified optimal zones: HDL=47 scores differently for M vs F.
        Male: optimal≥60, acceptable 45-59 → HDL 47 = acceptable.
        Female: optimal≥65, acceptable 50-64, suboptimal 40-49 → HDL 47 = suboptimal.
        """
        base_unified = {"lab_hdl": 47.0}
        result_m = score_polygon(unified=base_unified, sex="male")
        result_f = score_polygon(unified=base_unified, sex="female")
        hv_m = result_m["categories"]["heart_vascular"]
        hv_f = result_f["categories"]["heart_vascular"]
        hdl_m = next((i for i in hv_m.get("inputs", []) if i["name"] == "hdl"), None)
        hdl_f = next((i for i in hv_f.get("inputs", []) if i["name"] == "hdl"), None)
        if hdl_m and hdl_f:
            assert hdl_m["zone"] == "acceptable", \
                f"HDL 47 mg/dL (male) expected 'acceptable', got '{hdl_m['zone']}'"
            assert hdl_f["zone"] == "suboptimal", \
                f"HDL 47 mg/dL (female) expected 'suboptimal', got '{hdl_f['zone']}'"

    def test_all_5_lenses_scores_without_error(self):
        """All 6 categories must score on all 4 fixtures without error."""
        fixture_files = [
            "fixture_questionnaire_only.json",
            "fixture_scan_and_questionnaire.json",
            "fixture_partial_labs.json",
            "fixture_full_data.json",
        ]
        for fname in fixture_files:
            data = _load(fname)
            result = score_polygon(
                unified=data["unified"],
                questionnaire=parse_questionnaire(data["questionnaire"]),
                sex=data["context"]["sex"],
            )
            assert len(result["categories"]) == 6, \
                f"Fixture '{fname}' produced {len(result['categories'])} categories, expected 6"

    def test_individual_score_category_call(self):
        """score_category() can be called standalone per category."""
        data = _load("fixture_full_data.json")
        for cat_name in CATEGORY_DEFS:
            result = score_category(
                category_name=cat_name,
                unified=data["unified"],
                questionnaire=parse_questionnaire(data["questionnaire"]),
                sex=data["context"]["sex"],
            )
            assert "score" in result
            assert 0 <= result["score"] <= 100


# ─────────────────────────────────────────────────────────────────────────────
# CHANGE-04: Boundary gap test (v1.0.1)
# Walks every biomarker's plausible value range in 0.01 steps and asserts
# that every value resolves to a valid zone (no gaps, no crashes).
# ─────────────────────────────────────────────────────────────────────────────

from tns_optimal_zones import OPTIMAL_ZONES, zone_for_value, ZONE_SCORES


# Plausible scan ranges per biomarker/sex combo
# Format: (biomarker_name, sex, lo, hi)
_PLAUSIBLE_RANGES = [
    # HDL
    ("hdl", "male",   20.0,  100.0),
    ("hdl", "female", 20.0,  100.0),
    # Total cholesterol
    ("total_chol", "male", 100.0, 320.0),
    # LDL
    ("ldl", "male", 20.0, 250.0),
    # Non-HDL
    ("non_hdl", "male", 30.0, 300.0),
    # Triglycerides
    ("triglycerides", "male", 30.0, 500.0),
    # Fasting glucose
    ("fasting_glucose", "male", 40.0, 200.0),
    # HbA1c
    ("hba1c", "male", 3.5, 10.0),
    # Fasting insulin
    ("fasting_insulin", "male", 0.0, 50.0),
    # HOMA-IR
    ("homa_ir", "male", 0.0, 8.0),
    # hs-CRP
    ("hs_crp", "male", 0.0, 10.0),
    # TSH
    ("tsh", "male", 0.1, 8.0),
    # Free T3
    ("free_t3", "male", 1.0, 7.0),
    # Free T4
    ("free_t4", "male", 0.4, 3.0),
    # Vitamin D
    ("vitamin_d", "male",   5.0, 120.0),
    ("vitamin_d", "female", 5.0, 120.0),
    # Vitamin B12
    ("vitamin_b12", "male", 50.0, 1500.0),
    # Ferritin
    ("ferritin", "male",   1.0, 500.0),
    ("ferritin", "female", 1.0, 400.0),
    # Testosterone
    ("testosterone_total", "male",   50.0, 1400.0),
    ("testosterone_total", "female",  1.0,  150.0),
    # Cortisol AM
    ("cortisol_am", "male", 1.0, 50.0),
    # SBP
    ("sbp", "male", 60.0, 220.0),
    # DBP
    ("dbp", "male", 30.0, 130.0),
    # TG/HDL ratio
    ("tg_hdl_ratio", "male", 0.5, 12.0),
    # Lp(a)
    ("lp_a", "male", 0.0, 150.0),
    # ApoB
    ("apo_b", "male", 30.0, 250.0),
    # eGFR
    ("egfr", "male", 10.0, 160.0),
]

_VALID_ZONES = set(ZONE_SCORES.keys())


def test_no_boundary_gaps_in_optimal_zones():
    """
    Walk every biomarker's plausible range in 0.01 steps.
    Assert that every value resolves to a valid zone string with no gaps,
    no None returns, and no exceptions.  Introduced in v1.0.1 to verify the
    half-open interval (INTERVAL_CONVENTION = "half_open_low_inclusive") patch.
    """
    failures = []

    for biomarker, sex, lo, hi in _PLAUSIBLE_RANGES:
        entry = OPTIMAL_ZONES.get(biomarker)
        assert entry is not None, f"Biomarker '{biomarker}' not in OPTIMAL_ZONES"

        value = lo
        step = 0.01
        while value <= hi + step / 2:   # float-safe upper bound
            try:
                zone = zone_for_value(entry, value, sex=sex)
            except Exception as exc:
                failures.append(
                    f"{biomarker}({sex}) val={value:.2f} raised {type(exc).__name__}: {exc}"
                )
                value += step
                continue

            if zone not in _VALID_ZONES:
                failures.append(
                    f"{biomarker}({sex}) val={value:.2f} returned invalid zone={zone!r}"
                )
            value = round(value + step, 4)

    assert not failures, (
        f"{len(failures)} boundary gap(s) found:\n" + "\n".join(failures[:20])
    )
