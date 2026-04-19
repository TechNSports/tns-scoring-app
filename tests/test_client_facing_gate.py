"""
tests/test_client_facing_gate.py
---------------------------------
Unit + integration tests for the v1.0.3 CLINICIAN_SUPERVISED_RENDER gate.

Tests
-----
1. assert_clinician_review_complete passes when CLINICIAN_SUPERVISED_RENDER=True
   AND both CLINICAL_LEAD_NAME and CLINICAL_LEAD_CREDENTIAL are assigned.
2. assert_clinician_review_complete raises ClinicalReviewPendingError when
   CLINICIAN_SUPERVISED_RENDER=False and TNS_ALLOW_DEV_RENDER is absent.
3. TNS_ALLOW_DEV_RENDER="1" bypasses the guard when the gate is False.
4. TNS_ALLOW_DEV_RENDER with a value other than "1" does NOT bypass the guard.
5. Integration: score_polygon() raises ClinicalReviewPendingError by default
   (i.e., when CLINICIAN_SUPERVISED_RENDER=False and env var absent).
6. Guard raises ClinicalReviewPendingError when gate is True but
   CLINICAL_LEAD_NAME or CLINICAL_LEAD_CREDENTIAL is "PENDING_ASSIGNMENT".
7. Guard passes when gate is True and both clinical lead constants are assigned.

Note on conftest
~~~~~~~~~~~~~~~~
tests/conftest.py sets TNS_ALLOW_DEV_RENDER=1 for the whole session so the
rest of the suite passes.  Tests here that need the raw raise behaviour use
monkeypatch.delenv to temporarily clear the bypass for the duration of that
individual test.
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
import tns_optimal_zones
from tns_optimal_zones import (
    assert_clinician_review_complete,
    ClinicalReviewPendingError,
)
from tns_polygon_scorer import score_polygon
from tns_questionnaire import parse_questionnaire


# ── Helpers ───────────────────────────────────────────────────────────────────

def _load_fixture(name: str) -> dict:
    with open(FIXTURES_DIR / name, encoding="utf-8") as fh:
        return json.load(fh)


# =============================================================================
# Test 1 — gate True + lead assigned → no raise
# =============================================================================

def test_guard_passes_when_clinician_supervised_render_true(monkeypatch):
    """assert_clinician_review_complete() must return None when the gate is True
    AND both clinical lead constants are assigned (not PENDING_ASSIGNMENT).
    """
    monkeypatch.setattr(tns_optimal_zones, "CLINICIAN_SUPERVISED_RENDER", True)
    monkeypatch.setattr(tns_optimal_zones, "CLINICAL_LEAD_NAME", "Dr. Test Lead")
    monkeypatch.setattr(tns_optimal_zones, "CLINICAL_LEAD_CREDENTIAL", "MD")

    result = assert_clinician_review_complete(
        "test.test_guard_passes_when_clinician_supervised_render_true"
    )
    assert result is None


# =============================================================================
# Test 2 — gate False + no env var → raises
# =============================================================================

def test_guard_raises_when_flag_false_and_no_env_var(monkeypatch):
    """Guard must raise ClinicalReviewPendingError when gate is False
    and TNS_ALLOW_DEV_RENDER is not set.
    """
    monkeypatch.setattr(tns_optimal_zones, "CLINICIAN_SUPERVISED_RENDER", False)
    monkeypatch.delenv("TNS_ALLOW_DEV_RENDER", raising=False)

    with pytest.raises(ClinicalReviewPendingError) as exc_info:
        assert_clinician_review_complete("test.raises_context")

    # Exception message must contain the context string
    assert "test.raises_context" in str(exc_info.value)
    # And must hint how to unblock
    assert "TNS_ALLOW_DEV_RENDER" in str(exc_info.value)


# =============================================================================
# Test 3 — TNS_ALLOW_DEV_RENDER="1" bypasses guard
# =============================================================================

def test_guard_bypassed_by_env_var(monkeypatch):
    """TNS_ALLOW_DEV_RENDER='1' must allow rendering even when gate is False."""
    monkeypatch.setattr(tns_optimal_zones, "CLINICIAN_SUPERVISED_RENDER", False)
    monkeypatch.setenv("TNS_ALLOW_DEV_RENDER", "1")

    result = assert_clinician_review_complete("test.env_var_bypass")
    assert result is None


# =============================================================================
# Test 4 — non-"1" values of env var do NOT bypass guard
# =============================================================================

@pytest.mark.parametrize("bad_value", ["0", "yes", "true", "True", "1 ", " 1", ""])
def test_guard_not_bypassed_by_non_one_env_var(monkeypatch, bad_value):
    """Only the exact string '1' is a valid bypass; anything else must still raise."""
    monkeypatch.setattr(tns_optimal_zones, "CLINICIAN_SUPERVISED_RENDER", False)
    monkeypatch.setenv("TNS_ALLOW_DEV_RENDER", bad_value)

    with pytest.raises(ClinicalReviewPendingError):
        assert_clinician_review_complete("test.bad_env_value")


# =============================================================================
# Test 5 — integration: score_polygon raises ClinicalReviewPendingError by default
# =============================================================================

def test_score_polygon_raises_when_clinical_review_pending(monkeypatch):
    """score_polygon() must raise ClinicalReviewPendingError when the gate is closed.

    This verifies that the guard is actually wired into the production call path,
    not just that the standalone helper function raises.
    """
    monkeypatch.setattr(tns_optimal_zones, "CLINICIAN_SUPERVISED_RENDER", False)
    monkeypatch.delenv("TNS_ALLOW_DEV_RENDER", raising=False)

    fixture = _load_fixture("fixture_full_data.json")
    unified = fixture["unified"]
    ctx     = fixture["context"]
    q_raw   = fixture["questionnaire"]
    questionnaire = parse_questionnaire(q_raw)

    with pytest.raises(ClinicalReviewPendingError) as exc_info:
        score_polygon(
            unified=unified,
            questionnaire=questionnaire,
            sex=ctx["sex"],
            athlete_status=ctx.get("athlete_status", "recreational"),
            client_id=ctx.get("client_id"),
        )

    # Error message must reference the exact call site
    assert "tns_polygon_scorer.score_polygon" in str(exc_info.value)


# =============================================================================
# Test 6 — gate True + PENDING_ASSIGNMENT → raises
# =============================================================================

def test_guard_raises_when_clinical_lead_pending(monkeypatch):
    """Guard must raise ClinicalReviewPendingError when gate is True but
    CLINICAL_LEAD_NAME or CLINICAL_LEAD_CREDENTIAL is still "PENDING_ASSIGNMENT".
    """
    monkeypatch.setattr(tns_optimal_zones, "CLINICIAN_SUPERVISED_RENDER", True)
    monkeypatch.setattr(tns_optimal_zones, "CLINICAL_LEAD_NAME", "PENDING_ASSIGNMENT")
    monkeypatch.setattr(tns_optimal_zones, "CLINICAL_LEAD_CREDENTIAL", "PENDING_ASSIGNMENT")
    monkeypatch.delenv("TNS_ALLOW_DEV_RENDER", raising=False)

    with pytest.raises(ClinicalReviewPendingError) as exc_info:
        assert_clinician_review_complete("test.pending_lead")

    assert "PENDING_ASSIGNMENT" in str(exc_info.value)


def test_guard_raises_when_only_name_pending(monkeypatch):
    """Guard must raise when gate is True and only CLINICAL_LEAD_NAME is PENDING."""
    monkeypatch.setattr(tns_optimal_zones, "CLINICIAN_SUPERVISED_RENDER", True)
    monkeypatch.setattr(tns_optimal_zones, "CLINICAL_LEAD_NAME", "PENDING_ASSIGNMENT")
    monkeypatch.setattr(tns_optimal_zones, "CLINICAL_LEAD_CREDENTIAL", "MD")
    monkeypatch.delenv("TNS_ALLOW_DEV_RENDER", raising=False)

    with pytest.raises(ClinicalReviewPendingError):
        assert_clinician_review_complete("test.only_name_pending")


def test_guard_raises_when_only_credential_pending(monkeypatch):
    """Guard must raise when gate is True and only CLINICAL_LEAD_CREDENTIAL is PENDING."""
    monkeypatch.setattr(tns_optimal_zones, "CLINICIAN_SUPERVISED_RENDER", True)
    monkeypatch.setattr(tns_optimal_zones, "CLINICAL_LEAD_NAME", "Dr. Test Lead")
    monkeypatch.setattr(tns_optimal_zones, "CLINICAL_LEAD_CREDENTIAL", "PENDING_ASSIGNMENT")
    monkeypatch.delenv("TNS_ALLOW_DEV_RENDER", raising=False)

    with pytest.raises(ClinicalReviewPendingError):
        assert_clinician_review_complete("test.only_credential_pending")


# =============================================================================
# Test 7 — gate True + both constants assigned → passes
# =============================================================================

def test_guard_passes_when_clinical_lead_assigned(monkeypatch):
    """Guard must pass when gate is True and both lead constants are non-PENDING."""
    monkeypatch.setattr(tns_optimal_zones, "CLINICIAN_SUPERVISED_RENDER", True)
    monkeypatch.setattr(tns_optimal_zones, "CLINICAL_LEAD_NAME", "Dra. Ana García")
    monkeypatch.setattr(tns_optimal_zones, "CLINICAL_LEAD_CREDENTIAL", "Nutrióloga Clínica")
    monkeypatch.delenv("TNS_ALLOW_DEV_RENDER", raising=False)

    result = assert_clinician_review_complete("test.lead_assigned")
    assert result is None
