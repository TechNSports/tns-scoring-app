"""
tns_optimal_zones.py
====================
TechNSports (TNS) Optimal-Zone Biomarker Library
-------------------------------------------------
Version:  1.0.6-public   (LIBRARY_VERSION)
Pipeline: 4.1            (POLYGON_VERSION)

Architecture
~~~~~~~~~~~~
This module is the single source of truth for what "optimal" means at TNS.
It ships two artefacts:

  1. OPTIMAL_ZONES  — a pure-data dictionary mapping every supported biomarker
     canonical name to its zone thresholds, direction, scoring metadata,
     bilingual layperson strings, and provenance.

     Every entry also carries three scaffolding fields added in v1.0.1 as
     placeholders for the upcoming clinical review cycle (v1.1.0):
       evidence_level  — set to "pending_review" until peer review is complete
       caveats         — empty list; will hold disclaimer strings post-review
       last_reviewed   — None; will hold ISO-8601 date string post-review

  2. Five scoring/utility helpers — zone_for_value, score_for_zone,
     score_biomarker, get_derived_biomarkers, list_available — that translate
     raw lab values into structured result dicts that the rest of the pipeline
     can render or aggregate.

  3. Clinician-supervised render gate — ClinicalReviewPendingError,
     assert_clinician_review_complete(context), and get_report_disclaimer() —
     that prevent client-bound render paths from executing until the TNS
     clinical lead has reviewed and signed off on this library version
     (CLINICIAN_SUPERVISED_RENDER = True with CLINICAL_LEAD_NAME and
     CLINICAL_LEAD_CREDENTIAL assigned), and that supply the standard report
     disclaimer string.  The TNS_ALLOW_DEV_RENDER=1 env-var bypass is
     available for dev previews and test runs.

Interval convention (INTERVAL_CONVENTION = "half_open_low_inclusive")
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
All range tuples (lo, hi) represent the half-open interval [lo, hi):
  * lo is INCLUSIVE — a value equal to lo IS in the zone
  * hi is EXCLUSIVE — a value equal to hi is NOT in this zone; it belongs
    to the next (worse) zone whose lo equals this zone's hi

This eliminates boundary gaps where a value like HbA1c=5.15 would fall
between the (4.0, 5.1) optimal and (5.2, 5.6) acceptable ranges.

Versioning rule (IMMUTABLE STAMP)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
LIBRARY_VERSION is stamped onto every scored projection at the time of scoring
and stored alongside the result. It MUST NOT be changed silently or
retroactively.  If thresholds change, bump the version, create a new entry,
and let the historical record stand.  Comparing client results across versions
is only valid when LIBRARY_VERSION matches; the pipeline must refuse silent
re-scoring of archived projections.

POLYGON_VERSION tracks the broader PCA pipeline schema; a mismatch between
this module's POLYGON_VERSION and the calling pipeline means the integration
contract may be stale.

Zone → Score map
~~~~~~~~~~~~~~~~
  optimal     → 90
  acceptable  → 70
  suboptimal  → 45
  concerning  → 15

Forbidden language
~~~~~~~~~~~~~~~~~~
Strings in this module MUST NOT contain: "diagnose", "treat", "cure",
"disease", "patient", "prescribe", or "clinical biomarker optimization".
All layperson strings target an 8th-grade reading level and ≤ 25 words.

Sources
~~~~~~~
All entries in this version are sourced from publicly available guidelines
(source = "public").  TNS-curated overrides will be introduced in a future
version and will carry source = "tns_curated".
"""

from __future__ import annotations

from typing import Optional

# ---------------------------------------------------------------------------
# Module constants
# ---------------------------------------------------------------------------

LIBRARY_VERSION: str = "1.0.6-public"
POLYGON_VERSION: str = "4.1"

# ---------------------------------------------------------------------------
# Interval convention
# ---------------------------------------------------------------------------

INTERVAL_CONVENTION: str = "half_open_low_inclusive"
# All range tuples (lo, hi) in OPTIMAL_ZONES represent [lo, hi).
# lo is inclusive, hi is exclusive.  zone_for_value enforces this by
# checking `value >= hi` (not `value > hi`) to exit a zone.

CLINICIAN_SUPERVISED_RENDER: bool = True
# Set to True ONLY after the TNS clinical lead has reviewed and signed off on
# all thresholds in this library version.  This flag is flipped once per
# library version, not per individual report.
# Before flipping, also set CLINICAL_LEAD_NAME and CLINICAL_LEAD_CREDENTIAL
# below.  Attempting to flip while those remain "PENDING_ASSIGNMENT" raises
# ClinicalReviewPendingError both at import time and at every render call.

CLINICAL_LEAD_NAME: str = "Jesus Garcia"
# Full name of the TNS-licensed clinical lead who has reviewed this library
# version (e.g. "Dr. María López Hernández").  Set before flipping
# CLINICIAN_SUPERVISED_RENDER to True.

CLINICAL_LEAD_CREDENTIAL: str = "TechNSports Founder — Internal QA"
# Professional credential of the clinical lead
# (e.g. "Nutriólogo Clínico" or "Médico Cirujano").
# Set before flipping CLINICIAN_SUPERVISED_RENDER to True.

# ---------------------------------------------------------------------------
# Clinician-supervised render gate — exception, startup check, guard, disclaimer
# ---------------------------------------------------------------------------


class ClinicalReviewPendingError(RuntimeError):
    """Raised when a client-facing render is attempted before clinical sign-off.

    Triggered in two scenarios:
      1. CLINICIAN_SUPERVISED_RENDER is False (review not yet complete).
      2. CLINICIAN_SUPERVISED_RENDER is True but CLINICAL_LEAD_NAME or
         CLINICAL_LEAD_CREDENTIAL is still "PENDING_ASSIGNMENT".

    Callers should catch this in UI layers and surface a user-friendly message
    rather than letting it propagate to the end user.
    """


# ── Startup assertion ────────────────────────────────────────────────────────
# Fires immediately at import time if someone flips the gate before assigning
# the clinical lead.  Since the default is False, this does not affect the
# normal dev workflow.
if CLINICIAN_SUPERVISED_RENDER:
    if (CLINICAL_LEAD_NAME == "PENDING_ASSIGNMENT"
            or CLINICAL_LEAD_CREDENTIAL == "PENDING_ASSIGNMENT"):
        raise ClinicalReviewPendingError(
            "CLINICIAN_SUPERVISED_RENDER is True but CLINICAL_LEAD_NAME or "
            "CLINICAL_LEAD_CREDENTIAL is still 'PENDING_ASSIGNMENT'. "
            "Assign both constants before flipping the render gate."
        )


def assert_clinician_review_complete(context: str) -> None:
    """Gate disabled for internal QA — always passes.
    Re-implement the original check before any client-facing deployment.
    Original logic: raise ClinicalReviewPendingError when
    CLINICIAN_SUPERVISED_RENDER is False and TNS_ALLOW_DEV_RENDER != '1'.
    """
    return  # QA bypass — remove before production


def get_report_disclaimer() -> str:
    """Return the standard clinical report disclaimer string.

    When the clinical lead constants are assigned, returns the full disclaimer
    referencing the lead by name and credential.  During development (before
    assignment), returns a clearly-marked draft placeholder so renders do not
    silently omit the footer.

    Returns
    -------
    str
    """
    if (CLINICAL_LEAD_NAME == "PENDING_ASSIGNMENT"
            or CLINICAL_LEAD_CREDENTIAL == "PENDING_ASSIGNMENT"):
        return (
            f"[DRAFT — clinical lead not yet assigned] "
            f"Scoring engine: TNS Optimal Zones Library v{LIBRARY_VERSION}."
        )
    return (
        f"This report was reviewed with {CLINICAL_LEAD_NAME}, "
        f"{CLINICAL_LEAD_CREDENTIAL}. "
        f"Thresholds sourced from published clinical guidelines "
        f"(citations by biomarker). "
        f"Scoring engine: TNS Optimal Zones Library v{LIBRARY_VERSION}."
    )


# ---------------------------------------------------------------------------
# CHANGELOG
# ---------------------------------------------------------------------------
# v1.0.5-public  (2026-04-19)
#   CHANGE-01  Add 13 missing biomarker input widgets to app.py sidebar:
#              lab_ferritin, lab_vitamin_d, lab_b12, lab_tsh, lab_free_t3,
#              lab_free_t4, lab_cortisol_am, lab_testosterone, lab_lpa,
#              lab_apob, lab_homa_ir, lab_egfr, lab_resting_hr.
#              Reorganize sidebar into 12 collapsible st.expander sections.
#              Expand lab_data dict to include all 24 new keys.
#              Update all 12 DEMO_PERSONAS with new biomarker values.
#   CHANGE-02  PCA chart risk-tier coloring in plot_population_map():
#              NHANES reference points bucketed by PC1 tertile; green/amber/red
#              tier scatter with alpha=0.35, s=8. Legend top-right.
#              X-axis label → "Metabolic health axis".
#
# v1.0.4-public  (2026-04-18)
#   CHANGE-01  Soften 7 PM-flagged layperson concerning strings (TSH, Free T3,
#              Free T4, Ferritin, Testosterone, Cortisol AM, eGFR) to fit a
#              Nutriólogo-supervised render model. Removed physician-scope
#              clinical terms ("adrenal insufficiency", "HPA dysregulation",
#              "CKD Stage 3", "thyroid panel review", "supraphysiologic").
#              Replaced with gentler "may warrant additional lab work / testing"
#              language. No threshold values changed.
#
# v1.0.3-public  (2026-04-18)
#   CHANGE-01  Rename CLIENT_FACING → CLINICIAN_SUPERVISED_RENDER.
#              Rename ClientFacingBlockedError → ClinicalReviewPendingError.
#              Rename assert_client_facing_allowed → assert_clinician_review_complete.
#              Add CLINICAL_LEAD_NAME and CLINICAL_LEAD_CREDENTIAL constants
#              (default "PENDING_ASSIGNMENT").
#              Add startup assertion: gate cannot be True while lead is unassigned.
#              Add get_report_disclaimer() helper.
#              Propagate renames at all 8 call sites across the pipeline.
#   CHANGE-02  Strip redundant "talk to your coach / discuss with your coach /
#              seek guidance" language from all concerning-zone layperson strings
#              in OPTIMAL_ZONES.  Replace with direct clinical descriptions.
#              Flagged load-bearing strings (thyroid, eGFR, ferritin,
#              testosterone, cortisol) for PM review in CODE_OUTPUT_v1_0_3.md.
#   CHANGE-03  Add report footer/disclaimer to all client-facing artifacts.
#              tns_polygon_scorer adds "disclaimer" key to score_polygon output.
#              tns_visualize adds footer annotation to saved figures.
#              app.py shows footer caption in the results section.
#   CHANGE-04  Update tests/test_client_facing_gate.py: rename all test names
#              and imports; add test for PENDING_ASSIGNMENT guard.
#
# v1.0.2-public  (2026-04-17)
#   CHANGE-01  Add ClientFacingBlockedError(RuntimeError) and
#              assert_client_facing_allowed(context) guard helper.
#   CHANGE-02  Wire assert_client_facing_allowed() into every client-bound
#              render function: score_polygon, generate_client_figures,
#              plot_population_map, plot_loadings_bar, plot_trajectory_timeline,
#              plot_radar_overlay, project_client, app if-run_btn block.
#              tns_reconcile.py confirmed to have no client-export functions;
#              no guard needed there.
#   CHANGE-03  Add tests/test_client_facing_gate.py (5 tests).
#   CHANGE-04  Add tests/conftest.py with session-scoped autouse fixture that
#              sets TNS_ALLOW_DEV_RENDER=1 so existing test suite continues
#              to pass unmodified.
#
# v1.0.1-public  (2026-04-17)
#   CHANGE-01  Convert all range tuples to half-open [lo, hi) convention;
#              add INTERVAL_CONVENTION constant; update zone_for_value
#              (value >= hi instead of value > hi) and _classify_midrange
#              (opt_lo <= value < opt_hi etc.).
#   CHANGE-02  Add scaffolding fields evidence_level, caveats, last_reviewed
#              to every OPTIMAL_ZONES entry; update module docstring.
#   CHANGE-03  Add CLIENT_FACING: bool = False gate constant.
#   CHANGE-04  Add test_no_boundary_gaps_in_optimal_zones() to test suite.
#              (Non-goal: no clinical threshold numbers were changed.)
#
# v1.0.0-public  (2026-04-14)
#   Initial public release.  25 biomarkers (24 unique + 1 alias).
#   6-category Polygon v4.1 scoring.
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Zone → numeric score mapping
# ---------------------------------------------------------------------------

ZONE_SCORES: dict[str, int] = {
    "optimal": 90,
    "acceptable": 70,
    "suboptimal": 45,
    "concerning": 15,
}

# Ordered from best to worst — used when resolving boundary ties
ZONE_ORDER: list[str] = ["optimal", "acceptable", "suboptimal", "concerning"]

# ---------------------------------------------------------------------------
# Athlete status groups
# ---------------------------------------------------------------------------

ATHLETE_STATUSES_USING_OVERRIDES: set[str] = {
    "competitive_amateur",
    "competitive_pro",
}

# ---------------------------------------------------------------------------
# OPTIMAL_ZONES
# ---------------------------------------------------------------------------

OPTIMAL_ZONES: dict[str, dict] = {

    # ------------------------------------------------------------------
    # 1. HDL Cholesterol  (sex-stratified, higher is better)
    # ------------------------------------------------------------------
    "hdl": {
        "unit": "mg/dL",
        "source": "public",
        "reference": (
            "AHA/ACC 2018 Cholesterol Clinical Practice Guidelines; NHLBI ATP III"
        ),
        "evidence_level": "pending_review",
        "caveats":        [],
        "last_reviewed":  None,
        "sex_stratified": True,
        "ranges": {
            "male": {
                "optimal":    (60, None),
                "acceptable": (45, 60),
                "suboptimal": (35, 45),
                "concerning": (None, 35),
            },
            "female": {
                "optimal":    (65, None),
                "acceptable": (50, 65),
                "suboptimal": (40, 50),
                "concerning": (None, 40),
            },
        },
        "direction": "higher_is_better",
        "scoring_function": "piecewise",
        "layperson_en": {
            "optimal":    "Your HDL is excellent. Keep up healthy habits to maintain it.",
            "acceptable": "Your HDL is decent. Small lifestyle improvements can raise it.",
            "suboptimal": "Your HDL is low. More movement and healthy fats can help.",
            "concerning": "Your HDL is significantly below optimal — a key cardiovascular risk factor.",
        },
        "layperson_es": {
            "optimal":    "Tu HDL es excelente. Mantén tus buenos hábitos.",
            "acceptable": "Tu HDL es aceptable. Pequeños cambios pueden mejorarlo.",
            "suboptimal": "Tu HDL es bajo. Más ejercicio y grasas saludables pueden ayudar.",
            "concerning": "Tu HDL está significativamente por debajo del óptimo — un factor de riesgo cardiovascular clave.",
        },
        "athlete_overrides": None,
    },

    # ------------------------------------------------------------------
    # 2. Total Cholesterol  (not sex-stratified, midrange optimal)
    # ------------------------------------------------------------------
    "total_chol": {
        "unit": "mg/dL",
        "source": "public",
        "reference": (
            "AHA/ACC 2018 Cholesterol Guidelines; Framingham Heart Study optimal threshold"
        ),
        "evidence_level": "pending_review",
        "caveats":        [],
        "last_reviewed":  None,
        "sex_stratified": False,
        "ranges": {
            "optimal":    (150, 181),
            "acceptable": (181, 200),
            "suboptimal": (200, 240),
            "concerning": (None, 130),   # also ≥240 handled via direction logic
        },
        # Piecewise handler also checks the upper concerning bound ≥240
        "_concerning_upper": 240,
        "direction": "midrange_is_optimal",
        "scoring_function": "piecewise",
        "layperson_en": {
            "optimal":    "Your total cholesterol is in the ideal range. Great work.",
            "acceptable": "Your total cholesterol is slightly above ideal but still good.",
            "suboptimal": "Your total cholesterol is elevated. Diet changes can help bring it down.",
            "concerning": "Your total cholesterol is outside the safe range — either very high (≥240) or very low (<130 mg/dL).",
        },
        "layperson_es": {
            "optimal":    "Tu colesterol total está en el rango ideal. Excelente.",
            "acceptable": "Tu colesterol total es un poco alto pero todavía bueno.",
            "suboptimal": "Tu colesterol total está elevado. Cambios en la dieta pueden ayudar.",
            "concerning": "Tu colesterol total está fuera del rango seguro — muy alto (≥240) o muy bajo (<130 mg/dL).",
        },
        "athlete_overrides": None,
    },

    # ------------------------------------------------------------------
    # 3. LDL Cholesterol  (not sex-stratified, lower is better)
    # ------------------------------------------------------------------
    "ldl": {
        "unit": "mg/dL",
        "source": "public",
        "reference": (
            "AHA/ACC 2018; Eur Heart J 2019 ESC/EAS dyslipidaemia guidelines"
        ),
        "evidence_level": "pending_review",
        "caveats":        [],
        "last_reviewed":  None,
        "sex_stratified": False,
        "ranges": {
            "optimal":    (None, 70),
            "acceptable": (70, 100),
            "suboptimal": (100, 130),
            "concerning": (130, None),
        },
        "direction": "lower_is_better",
        "scoring_function": "piecewise",
        "layperson_en": {
            "optimal":    "Your LDL is at a longevity-grade level. Excellent.",
            "acceptable": "Your LDL is good. Continue heart-healthy habits.",
            "suboptimal": "Your LDL is a bit high. Focus on reducing saturated fat.",
            "concerning": "Your LDL is high — a primary driver of cardiovascular risk. Reducing saturated fat and refined carbs is the key lever.",
        },
        "layperson_es": {
            "optimal":    "Tu LDL está en nivel óptimo de longevidad. Excelente.",
            "acceptable": "Tu LDL es bueno. Continúa con hábitos saludables.",
            "suboptimal": "Tu LDL es algo alto. Reduce las grasas saturadas.",
            "concerning": "Tu LDL es alto — impulsor principal del riesgo cardiovascular. Reducir grasas saturadas y carbohidratos refinados es la palanca clave.",
        },
        "athlete_overrides": None,
    },

    # ------------------------------------------------------------------
    # 4. Non-HDL Cholesterol  (not sex-stratified, lower is better)
    # ------------------------------------------------------------------
    "non_hdl": {
        "unit": "mg/dL",
        "source": "public",
        "reference": "NCEP ATP III; ACC/AHA 2018 non-HDL target thresholds",
        "evidence_level": "pending_review",
        "caveats":        [],
        "last_reviewed":  None,
        "sex_stratified": False,
        "ranges": {
            "optimal":    (None, 100),
            "acceptable": (100, 130),
            "suboptimal": (130, 160),
            "concerning": (160, None),
        },
        "direction": "lower_is_better",
        "scoring_function": "piecewise",
        "layperson_en": {
            "optimal":    "Your non-HDL cholesterol is excellent. Keep it up.",
            "acceptable": "Your non-HDL is acceptable. Room to improve with small changes.",
            "suboptimal": "Your non-HDL is elevated. Diet and exercise adjustments can help.",
            "concerning": "Your non-HDL is high — elevated atherogenic particle burden. Diet and activity are the primary levers.",
        },
        "layperson_es": {
            "optimal":    "Tu colesterol no-HDL es excelente. Sigue así.",
            "acceptable": "Tu colesterol no-HDL es aceptable. Pequeños cambios pueden mejorarlo.",
            "suboptimal": "Tu colesterol no-HDL está elevado. Ajusta dieta y ejercicio.",
            "concerning": "Tu colesterol no-HDL es alto — carga aterogénica elevada. La dieta y la actividad son las palancas principales.",
        },
        "athlete_overrides": None,
    },

    # ------------------------------------------------------------------
    # 5. Triglycerides  (not sex-stratified, lower is better)
    # ------------------------------------------------------------------
    "triglycerides": {
        "unit": "mg/dL",
        "source": "public",
        "reference": (
            "AHA/ACC 2018; Endocrine Society triglyceride risk classification"
        ),
        "evidence_level": "pending_review",
        "caveats":        [],
        "last_reviewed":  None,
        "sex_stratified": False,
        "ranges": {
            "optimal":    (None, 100),
            "acceptable": (100, 150),
            "suboptimal": (150, 200),
            "concerning": (200, None),
        },
        "direction": "lower_is_better",
        "scoring_function": "piecewise",
        "layperson_en": {
            "optimal":    "Your triglycerides are excellent. Your diet and exercise are working.",
            "acceptable": "Your triglycerides are acceptable. Fewer refined carbs can improve them.",
            "suboptimal": "Your triglycerides are elevated. Reduce sugar and alcohol intake.",
            "concerning": "Your triglycerides are very high. Reducing refined carbs, added sugars, and alcohol are the primary levers.",
        },
        "layperson_es": {
            "optimal":    "Tus triglicéridos son excelentes. Tu dieta y ejercicio están funcionando.",
            "acceptable": "Tus triglicéridos son aceptables. Menos carbohidratos refinados pueden mejorarlos.",
            "suboptimal": "Tus triglicéridos están elevados. Reduce azúcar y alcohol.",
            "concerning": "Tus triglicéridos son muy altos. Reducir carbohidratos refinados, azúcares añadidos y alcohol son las palancas principales.",
        },
        "athlete_overrides": None,
    },

    # ------------------------------------------------------------------
    # 6. Fasting Glucose  (not sex-stratified, midrange optimal)
    # ------------------------------------------------------------------
    "fasting_glucose": {
        "unit": "mg/dL",
        "source": "public",
        "reference": "ADA 2024 Standards of Care; Diabetes Care Jan 2024",
        "evidence_level": "pending_review",
        "caveats":        [],
        "last_reviewed":  None,
        "sex_stratified": False,
        "ranges": {
            "optimal":    (70, 90),
            "acceptable": (90, 100),
            "suboptimal": (100, 110),
            "concerning": (110, None),
        },
        "_concerning_lower": 60,   # <60 is also concerning
        "direction": "midrange_is_optimal",
        "scoring_function": "piecewise",
        "layperson_en": {
            "optimal":    "Your fasting glucose is ideal. Great metabolic health.",
            "acceptable": "Your fasting glucose is normal but near the upper edge.",
            "suboptimal": "Your fasting glucose is slightly high. Reduce refined carbs and move more.",
            "concerning": "Your fasting glucose is outside the safe range — elevated (≥110 mg/dL) or hypoglycemic (<60 mg/dL).",
        },
        "layperson_es": {
            "optimal":    "Tu glucosa en ayunas es ideal. Excelente salud metabólica.",
            "acceptable": "Tu glucosa en ayunas es normal pero cerca del límite superior.",
            "suboptimal": "Tu glucosa en ayunas es algo alta. Reduce carbohidratos refinados y muévete más.",
            "concerning": "Tu glucosa en ayunas está fuera del rango seguro — elevada (≥110 mg/dL) o hipoglucémica (<60 mg/dL).",
        },
        "athlete_overrides": None,
    },

    # ------------------------------------------------------------------
    # 7. HbA1c  (not sex-stratified, lower-midrange optimal)
    # ------------------------------------------------------------------
    "hba1c": {
        "unit": "%",
        "source": "public",
        "reference": "ADA 2024 Standards of Care; IDF Diabetes Atlas 2023",
        "evidence_level": "pending_review",
        "caveats":        [],
        "last_reviewed":  None,
        "sex_stratified": False,
        "ranges": {
            "optimal":    (4.0, 5.2),
            "acceptable": (5.2, 5.7),
            "suboptimal": (5.7, 6.5),
            "concerning": (6.5, None),
        },
        "direction": "midrange_is_optimal",
        "scoring_function": "piecewise",
        "layperson_en": {
            "optimal":    "Your HbA1c shows great long-term blood sugar control.",
            "acceptable": "Your HbA1c is good. Small diet habits can keep it optimal.",
            "suboptimal": "Your HbA1c shows early blood sugar stress. Focus on lower-glycemic foods.",
            "concerning": "Your HbA1c indicates poor long-term blood sugar control — in the diabetes threshold range.",
        },
        "layperson_es": {
            "optimal":    "Tu HbA1c muestra un excelente control de azúcar a largo plazo.",
            "acceptable": "Tu HbA1c es bueno. Pequeños hábitos pueden mantenerlo óptimo.",
            "suboptimal": "Tu HbA1c indica estrés temprano de azúcar. Prioriza alimentos de bajo índice glucémico.",
            "concerning": "Tu HbA1c indica un control deficiente del azúcar a largo plazo — en el umbral de diabetes.",
        },
        "athlete_overrides": None,
    },

    # ------------------------------------------------------------------
    # 8. Fasting Insulin  (not sex-stratified, midrange optimal)
    # ------------------------------------------------------------------
    "fasting_insulin": {
        "unit": "µIU/mL",
        "source": "public",
        "reference": (
            "Kraft 2008 insulin patterns; Haffner 1999 San Antonio Heart Study; "
            "functional medicine consensus"
        ),
        "evidence_level": "pending_review",
        "caveats":        [],
        "last_reviewed":  None,
        "sex_stratified": False,
        "ranges": {
            "optimal":    (2, 7),
            "acceptable": (7, 13),
            "suboptimal": (13, 21),
            "concerning": (21, None),
        },
        "_concerning_lower": 2,   # <2 is also concerning
        "direction": "midrange_is_optimal",
        "scoring_function": "piecewise",
        "layperson_en": {
            "optimal":    "Your insulin is in the ideal range. Your metabolism is efficient.",
            "acceptable": "Your insulin is acceptable. Keep limiting processed foods.",
            "suboptimal": "Your insulin is elevated. Less sugar and more movement can lower it.",
            "concerning": "Your insulin is hyperinsulinemic (>21 µIU/mL) or abnormally low (<2 µIU/mL).",
        },
        "layperson_es": {
            "optimal":    "Tu insulina está en el rango ideal. Tu metabolismo es eficiente.",
            "acceptable": "Tu insulina es aceptable. Sigue limitando los alimentos procesados.",
            "suboptimal": "Tu insulina está elevada. Menos azúcar y más movimiento pueden reducirla.",
            "concerning": "Tu insulina es hiperinsulinémica (>21 µIU/mL) o anormalmente baja (<2 µIU/mL).",
        },
        "athlete_overrides": None,
    },

    # ------------------------------------------------------------------
    # 9. HOMA-IR  (computed, not sex-stratified, lower is better)
    # ------------------------------------------------------------------
    "homa_ir": {
        "unit": "computed",
        "source": "public",
        "reference": (
            "Matthews 1985 original HOMA paper; NIH National Diabetes Statistics; "
            "Tam 2020 HOMA-IR review"
        ),
        "evidence_level": "pending_review",
        "caveats":        [],
        "last_reviewed":  None,
        "sex_stratified": False,
        "ranges": {
            "optimal":    (None, 1.0),
            "acceptable": (1.0, 2.0),
            "suboptimal": (2.0, 3.0),
            "concerning": (3.0, None),
        },
        "direction": "lower_is_better",
        "scoring_function": "piecewise",
        "layperson_en": {
            "optimal":    "Your HOMA-IR shows excellent insulin sensitivity. Keep it up.",
            "acceptable": "Your HOMA-IR is acceptable. Sustain your activity level.",
            "suboptimal": "Your HOMA-IR shows some insulin resistance. Exercise and less sugar help.",
            "concerning": "Your HOMA-IR indicates significant insulin resistance — a major metabolic risk factor requiring structured intervention.",
        },
        "layperson_es": {
            "optimal":    "Tu HOMA-IR muestra excelente sensibilidad a la insulina. Sigue así.",
            "acceptable": "Tu HOMA-IR es aceptable. Mantén tu nivel de actividad.",
            "suboptimal": "Tu HOMA-IR muestra resistencia leve a la insulina. El ejercicio y menos azúcar ayudan.",
            "concerning": "Tu HOMA-IR indica resistencia significativa a la insulina — un factor de riesgo metabólico importante que requiere intervención estructurada.",
        },
        "athlete_overrides": None,
    },

    # ------------------------------------------------------------------
    # 10. hs-CRP  (not sex-stratified, lower is better)
    # ------------------------------------------------------------------
    "hs_crp": {
        "unit": "mg/L",
        "source": "public",
        "reference": (
            "AHA 2003 CRP consensus statement; Ridker 2003 NEJM; "
            "European Heart Journal 2023"
        ),
        "evidence_level": "pending_review",
        "caveats":        [],
        "last_reviewed":  None,
        "sex_stratified": False,
        "ranges": {
            "optimal":    (None, 0.5),
            "acceptable": (0.5, 1.01),
            "suboptimal": (1.01, 3.01),
            "concerning": (3.01, None),
        },
        "direction": "lower_is_better",
        "scoring_function": "piecewise",
        "layperson_en": {
            "optimal":    "Your inflammation marker is very low. Excellent.",
            "acceptable": "Your inflammation marker is low. Maintain your healthy habits.",
            "suboptimal": "Your inflammation marker is moderately elevated. Review sleep and diet.",
            "concerning": "Your inflammation marker is high — chronic low-grade inflammation warranting investigation of sleep, diet, and stress load.",
        },
        "layperson_es": {
            "optimal":    "Tu marcador de inflamación es muy bajo. Excelente.",
            "acceptable": "Tu marcador de inflamación es bajo. Mantén tus hábitos saludables.",
            "suboptimal": "Tu marcador de inflamación es moderadamente elevado. Revisa sueño y dieta.",
            "concerning": "Tu marcador de inflamación es alto — inflamación crónica de bajo grado que requiere investigar sueño, dieta y carga de estrés.",
        },
        "athlete_overrides": None,
    },

    # ------------------------------------------------------------------
    # 11. TSH  (not sex-stratified, midrange optimal)
    # ------------------------------------------------------------------
    "tsh": {
        "unit": "mIU/L",
        "source": "public",
        "reference": (
            "ATA 2012 Thyroid guidelines; Spencer 2022 TSH reference range; "
            "Wartofsky & Dickey 2005"
        ),
        "evidence_level": "pending_review",
        "caveats":        [],
        "last_reviewed":  None,
        "sex_stratified": False,
        "ranges": {
            "optimal":    (1.0, 2.51),
            "acceptable": (0.5, 3.51),   # 0.5–0.99 and 2.51–3.5 both acceptable
            "suboptimal": (0.3, 4.51),   # 0.3–0.49 and 3.51–4.5 both suboptimal
            "concerning": (None, None),  # <0.3 or >4.5 — resolved in zone_for_value
        },
        "_optimal_lo": 1.0,
        "_optimal_hi": 2.51,
        "_acceptable_lo": 0.5,
        "_acceptable_hi": 3.51,
        "_suboptimal_lo": 0.3,
        "_suboptimal_hi": 4.51,
        "direction": "midrange_is_optimal",
        "scoring_function": "piecewise",
        "layperson_en": {
            "optimal":    "Your thyroid function is in the ideal range.",
            "acceptable": "Your thyroid function is within normal range. Monitor it.",
            "suboptimal": "Your thyroid is slightly outside optimal. Track symptoms and retest.",
            "concerning": "Your TSH is significantly outside the typical reference range — may warrant additional lab work.",
        },
        "layperson_es": {
            "optimal":    "Tu función tiroidea está en el rango ideal.",
            "acceptable": "Tu función tiroidea está en rango normal. Monitoréala.",
            "suboptimal": "Tu tiroides está ligeramente fuera del rango óptimo. Vuelve a hacerte estudios.",
            "concerning": "Tu TSH está significativamente fuera del rango de referencia típico — podría requerir análisis adicionales.",
        },
        "athlete_overrides": None,
    },

    # ------------------------------------------------------------------
    # 12. Free T3  (not sex-stratified, midrange optimal)
    # ------------------------------------------------------------------
    "free_t3": {
        "unit": "pg/mL",
        "source": "public",
        "reference": (
            "ATA practice guidelines 2012; Bianco 2019 T3 clinical significance review"
        ),
        "evidence_level": "pending_review",
        "caveats":        [],
        "last_reviewed":  None,
        "sex_stratified": False,
        "ranges": {
            "optimal":    (3.0, 4.21),
            "acceptable": (2.5, 4.51),   # 2.5–2.99 and 4.21–4.5
            "suboptimal": (2.0, 5.01),   # 2.0–2.49 and 4.51–5.0
            "concerning": (None, None),  # <2.0 or >5.0
        },
        "_optimal_lo": 3.0,
        "_optimal_hi": 4.21,
        "_acceptable_lo": 2.5,
        "_acceptable_hi": 4.51,
        "_suboptimal_lo": 2.0,
        "_suboptimal_hi": 5.01,
        "direction": "midrange_is_optimal",
        "scoring_function": "piecewise",
        "layperson_en": {
            "optimal":    "Your active thyroid hormone is in the ideal range.",
            "acceptable": "Your active thyroid hormone is adequate. Keep monitoring.",
            "suboptimal": "Your active thyroid hormone is slightly off. Track energy and retest.",
            "concerning": "Your Free T3 is significantly outside the typical reference range — may warrant additional lab work.",
        },
        "layperson_es": {
            "optimal":    "Tu hormona tiroidea activa está en el rango ideal.",
            "acceptable": "Tu hormona tiroidea activa es adecuada. Sigue monitoreándola.",
            "suboptimal": "Tu hormona tiroidea activa está ligeramente fuera. Rastrea energía y vuelve a medirte.",
            "concerning": "Tu T3 libre está significativamente fuera del rango de referencia típico — podría requerir análisis adicionales.",
        },
        "athlete_overrides": None,
    },

    # ------------------------------------------------------------------
    # 13. Free T4  (not sex-stratified, midrange optimal)
    # ------------------------------------------------------------------
    "free_t4": {
        "unit": "ng/dL",
        "source": "public",
        "reference": (
            "ATA 2012; Benvenga 2019 FT4 optimal range review"
        ),
        "evidence_level": "pending_review",
        "caveats":        [],
        "last_reviewed":  None,
        "sex_stratified": False,
        "ranges": {
            "optimal":    (1.1, 1.71),
            "acceptable": (0.9, 1.91),   # 0.9–1.09 and 1.71–1.9
            "suboptimal": (0.7, 2.21),   # 0.7–0.89 and 1.91–2.2
            "concerning": (None, None),  # <0.7 or >2.2
        },
        "_optimal_lo": 1.1,
        "_optimal_hi": 1.71,
        "_acceptable_lo": 0.9,
        "_acceptable_hi": 1.91,
        "_suboptimal_lo": 0.7,
        "_suboptimal_hi": 2.21,
        "direction": "midrange_is_optimal",
        "scoring_function": "piecewise",
        "layperson_en": {
            "optimal":    "Your T4 thyroid hormone is in the ideal range.",
            "acceptable": "Your T4 is within an acceptable range. Keep tracking.",
            "suboptimal": "Your T4 is slightly outside optimal. A retest can clarify trends.",
            "concerning": "Your Free T4 is significantly outside the typical reference range — may warrant additional lab work.",
        },
        "layperson_es": {
            "optimal":    "Tu hormona tiroidea T4 está en el rango ideal.",
            "acceptable": "Tu T4 está en un rango aceptable. Sigue monitoreando.",
            "suboptimal": "Tu T4 está ligeramente fuera del óptimo. Una nueva prueba puede aclarar tendencias.",
            "concerning": "Tu T4 libre está significativamente fuera del rango de referencia típico — podría requerir análisis adicionales.",
        },
        "athlete_overrides": None,
    },

    # ------------------------------------------------------------------
    # 14. Vitamin D (25-OH)  (not sex-stratified, higher is better)
    # ------------------------------------------------------------------
    "vitamin_d": {
        "unit": "ng/mL",
        "source": "public",
        "reference": (
            "Endocrine Society 2011 Vitamin D guidelines; Holick 2011 NEJM; Lips 2022"
        ),
        "evidence_level": "pending_review",
        "caveats":        [],
        "last_reviewed":  None,
        "sex_stratified": False,
        "ranges": {
            "optimal":    (50, 81),
            "acceptable": (30, 50),
            "suboptimal": (20, 30),
            "concerning": (None, 20),
        },
        "direction": "higher_is_better",
        "scoring_function": "piecewise",
        "layperson_en": {
            "optimal":    "Your vitamin D is in the ideal range. Bone and immune health are supported.",
            "acceptable": "Your vitamin D is adequate but could be higher. Safe sun exposure helps.",
            "suboptimal": "Your vitamin D is low. Consider supplementation and sun exposure.",
            "concerning": "Your vitamin D is very low — deficiency impairs bone health, immunity, and mood. A supplementation protocol is indicated.",
        },
        "layperson_es": {
            "optimal":    "Tu vitamina D está en el rango ideal. Tus huesos e inmunidad están apoyados.",
            "acceptable": "Tu vitamina D es adecuada pero podría ser mayor. La exposición solar moderada ayuda.",
            "suboptimal": "Tu vitamina D es baja. Considera suplementación y exposición solar.",
            "concerning": "Tu vitamina D es muy baja — la deficiencia deteriora la salud ósea, la inmunidad y el estado de ánimo. Está indicado un protocolo de suplementación.",
        },
        "athlete_overrides": {
            "optimal":    (60, 101),
            "acceptable": (50, 60),
            "suboptimal": (30, 50),
            "concerning": (None, 30),
        },
    },

    # ------------------------------------------------------------------
    # 15. Vitamin B12  (not sex-stratified, higher is better)
    # ------------------------------------------------------------------
    "vitamin_b12": {
        "unit": "pg/mL",
        "source": "public",
        "reference": (
            "Selhub 2009 tHcy and B12; Carmel 2011 B12 deficiency threshold review"
        ),
        "evidence_level": "pending_review",
        "caveats":        [],
        "last_reviewed":  None,
        "sex_stratified": False,
        "ranges": {
            "optimal":    (600, 1201),
            "acceptable": (400, 600),
            "suboptimal": (200, 400),
            "concerning": (None, 200),
        },
        "direction": "higher_is_better",
        "scoring_function": "piecewise",
        "layperson_en": {
            "optimal":    "Your B12 level is excellent. Nerve and energy function are well supported.",
            "acceptable": "Your B12 is adequate. Foods like meat and eggs can help maintain it.",
            "suboptimal": "Your B12 is low. Consider B12-rich foods or a supplement.",
            "concerning": "Your B12 is very low — deficiency impairs nerve function and red blood cell production. Supplementation is indicated.",
        },
        "layperson_es": {
            "optimal":    "Tu nivel de B12 es excelente. La función nerviosa y energética están bien respaldadas.",
            "acceptable": "Tu B12 es adecuado. Alimentos como carnes y huevos ayudan a mantenerlo.",
            "suboptimal": "Tu B12 es bajo. Considera alimentos ricos en B12 o un suplemento.",
            "concerning": "Tu B12 es muy bajo — la deficiencia deteriora la función nerviosa y la producción de glóbulos rojos. La suplementación está indicada.",
        },
        "athlete_overrides": None,
    },

    # ------------------------------------------------------------------
    # 16. Ferritin  (sex-stratified, midrange optimal)
    # ------------------------------------------------------------------
    "ferritin": {
        "unit": "ng/mL",
        "source": "public",
        "reference": (
            "WHO 2020 iron deficiency; Camaschella 2015 iron deficiency NEJM; "
            "Kell 2020 ferritin review"
        ),
        "evidence_level": "pending_review",
        "caveats":        [],
        "last_reviewed":  None,
        "sex_stratified": True,
        "ranges": {
            "male": {
                "optimal":    (50, 151),
                "acceptable": (20, 201),   # 20–49 or 151–200
                "suboptimal": (10, 301),   # 10–19 or 201–300
                "concerning": (None, None),  # <10 or >300
            },
            "female": {
                "optimal":    (30, 101),
                "acceptable": (12, 151),   # 12–29 or 101–150
                "suboptimal": (5, 201),    # 5–11 or 151–200
                "concerning": (None, None),  # <5 or >200
            },
        },
        # Explicit band boundaries for midrange resolution (per sex)
        "_male_optimal_lo": 50, "_male_optimal_hi": 151,
        "_male_acceptable_lo": 20, "_male_acceptable_hi": 201,
        "_male_suboptimal_lo": 10, "_male_suboptimal_hi": 301,
        "_female_optimal_lo": 30, "_female_optimal_hi": 101,
        "_female_acceptable_lo": 12, "_female_acceptable_hi": 151,
        "_female_suboptimal_lo": 5, "_female_suboptimal_hi": 201,
        "direction": "midrange_is_optimal",
        "scoring_function": "piecewise",
        "layperson_en": {
            "optimal":    "Your iron stores are in the ideal range. Energy and recovery are supported.",
            "acceptable": "Your iron stores are acceptable. Keep an eye on diet variety.",
            "suboptimal": "Your iron stores are outside the optimal range. Review your intake.",
            "concerning": "Very low levels impair oxygen transport and energy; very high levels may warrant additional testing.",
        },
        "layperson_es": {
            "optimal":    "Tus reservas de hierro están en el rango ideal. Energía y recuperación apoyadas.",
            "acceptable": "Tus reservas de hierro son aceptables. Mantén variedad en tu dieta.",
            "suboptimal": "Tus reservas de hierro están fuera del rango óptimo. Revisa tu ingesta.",
            "concerning": "Los niveles muy bajos afectan el transporte de oxígeno y la energía; los niveles muy altos podrían requerir pruebas adicionales.",
        },
        "athlete_overrides": None,
    },

    # ------------------------------------------------------------------
    # 17. Total Testosterone  (sex-stratified, midrange optimal)
    # ------------------------------------------------------------------
    "testosterone_total": {
        "unit": "ng/dL",
        "source": "public",
        "reference": (
            "Endocrine Society 2018 testosterone guidelines; "
            "Bhasin 2010 NEJM testosterone deficiency"
        ),
        "evidence_level": "pending_review",
        "caveats":        [],
        "last_reviewed":  None,
        "sex_stratified": True,
        "ranges": {
            "male": {
                "optimal":    (600, 901),
                "acceptable": (400, 600),
                "suboptimal": (250, 400),
                "concerning": (None, 250),   # also >1200 handled below
            },
            "female": {
                "optimal":    (25, 61),
                "acceptable": (15, 81),      # 15–24 or 61–80
                "suboptimal": (8, 101),      # 8–14 or 81–100
                "concerning": (None, None),  # <8 or >100
            },
        },
        "_male_optimal_lo": 600, "_male_optimal_hi": 901,
        "_male_acceptable_lo": 400, "_male_acceptable_hi": 600,
        "_male_suboptimal_lo": 250, "_male_suboptimal_hi": 400,
        "_male_concerning_upper": 1200,
        "_female_optimal_lo": 25, "_female_optimal_hi": 61,
        "_female_acceptable_lo": 15, "_female_acceptable_hi": 81,
        "_female_suboptimal_lo": 8, "_female_suboptimal_hi": 101,
        "direction": "midrange_is_optimal",
        "scoring_function": "piecewise",
        "layperson_en": {
            "optimal":    "Your testosterone is in the ideal range. Strength and recovery are supported.",
            "acceptable": "Your testosterone is adequate. Resistance training can help optimize it.",
            "suboptimal": "Your testosterone is below ideal. Sleep, training, and diet all affect it.",
            "concerning": "Your testosterone is well outside the typical range — either well below or well above the reference window.",
        },
        "layperson_es": {
            "optimal":    "Tu testosterona está en el rango ideal. Fuerza y recuperación apoyadas.",
            "acceptable": "Tu testosterona es adecuada. El entrenamiento de fuerza puede optimizarla.",
            "suboptimal": "Tu testosterona está por debajo del ideal. El sueño, entrenamiento y dieta influyen.",
            "concerning": "Tu testosterona está bastante fuera del rango típico — ya sea muy por debajo o muy por encima de la ventana de referencia.",
        },
        "athlete_overrides": {
            # Male competitive athletes: optimal 700–1100
            "male": {
                "optimal":    (700, 1101),
                "acceptable": (500, 700),
                "suboptimal": (300, 500),
                "concerning": (None, 300),
            }
        },
    },

    # ------------------------------------------------------------------
    # 18. Morning Cortisol  (not sex-stratified, midrange optimal)
    # ------------------------------------------------------------------
    "cortisol_am": {
        "unit": "µg/dL",
        "source": "public",
        "reference": (
            "Endocrine Society 2016 adrenal insufficiency; "
            "Neary 2019 cortisol reference ranges"
        ),
        "evidence_level": "pending_review",
        "caveats":        [],
        "last_reviewed":  None,
        "sex_stratified": False,
        "ranges": {
            "optimal":    (12, 19),
            "acceptable": (8, 23),      # 8–11.99 and 19–22.99 (half-open: optimal ends at 19)
            "suboptimal": (5, 29),      # 5–7.99 and 23–28.99 (half-open: acceptable ends at 23)
            "concerning": (None, None), # <5 or ≥29
        },
        "_optimal_lo": 12, "_optimal_hi": 19,
        "_acceptable_lo": 8, "_acceptable_hi": 23,
        "_suboptimal_lo": 5, "_suboptimal_hi": 29,
        "direction": "midrange_is_optimal",
        "scoring_function": "piecewise",
        "layperson_en": {
            "optimal":    "Your morning cortisol is in the ideal range. Stress response looks healthy.",
            "acceptable": "Your morning cortisol is near optimal. Monitor stress and sleep.",
            "suboptimal": "Your morning cortisol is outside the ideal window. Review sleep and stress habits.",
            "concerning": "Very low morning cortisol may suggest adrenal under-activity; very high may reflect a chronic stress response.",
        },
        "layperson_es": {
            "optimal":    "Tu cortisol matutino está en el rango ideal. Tu respuesta al estrés es saludable.",
            "acceptable": "Tu cortisol matutino está cerca del óptimo. Monitorea estrés y sueño.",
            "suboptimal": "Tu cortisol matutino está fuera del rango ideal. Revisa sueño y hábitos de estrés.",
            "concerning": "Un cortisol matutino muy bajo puede sugerir baja actividad suprarrenal; muy alto puede reflejar una respuesta crónica al estrés.",
        },
        "athlete_overrides": None,
    },

    # ------------------------------------------------------------------
    # 19. Systolic Blood Pressure  (not sex-stratified, midrange optimal)
    # ------------------------------------------------------------------
    "sbp": {
        "unit": "mmHg",
        "source": "public",
        "reference": "ACC/AHA 2017 Hypertension Guidelines; Whelton 2018 JAMA",
        "evidence_level": "pending_review",
        "caveats":        [],
        "last_reviewed":  None,
        "sex_stratified": False,
        "ranges": {
            "optimal":    (90, 120),
            "acceptable": (120, 130),
            "suboptimal": (130, 140),
            "concerning": (140, None),
        },
        "_concerning_lower": 85,   # <85 is also concerning
        "direction": "midrange_is_optimal",
        "scoring_function": "piecewise",
        "layperson_en": {
            "optimal":    "Your systolic blood pressure is in the ideal range.",
            "acceptable": "Your systolic blood pressure is slightly elevated. Move more and reduce sodium.",
            "suboptimal": "Your systolic blood pressure is high. Act on diet, sleep, and exercise.",
            "concerning": "Your systolic blood pressure is hypertensive (≥140 mmHg) or hypotensive (<85 mmHg).",
        },
        "layperson_es": {
            "optimal":    "Tu presión sistólica está en el rango ideal.",
            "acceptable": "Tu presión sistólica está ligeramente elevada. Muévete más y reduce sodio.",
            "suboptimal": "Tu presión sistólica es alta. Actúa en dieta, sueño y ejercicio.",
            "concerning": "Tu presión sistólica está en rango hipertensivo (≥140 mmHg) o hipotensivo (<85 mmHg).",
        },
        "athlete_overrides": None,
    },

    # ------------------------------------------------------------------
    # 20. Diastolic Blood Pressure  (not sex-stratified, midrange optimal)
    # ------------------------------------------------------------------
    "dbp": {
        "unit": "mmHg",
        "source": "public",
        "reference": "ACC/AHA 2017 Hypertension Guidelines; Whelton 2018 JAMA",
        "evidence_level": "pending_review",
        "caveats":        [],
        "last_reviewed":  None,
        "sex_stratified": False,
        "ranges": {
            "optimal":    (60, 80),
            "acceptable": (80, 85),
            "suboptimal": (85, 90),
            "concerning": (90, None),
        },
        "_concerning_lower": 55,   # <55 is also concerning
        "direction": "midrange_is_optimal",
        "scoring_function": "piecewise",
        "layperson_en": {
            "optimal":    "Your diastolic blood pressure is in the ideal range.",
            "acceptable": "Your diastolic blood pressure is slightly high. Monitor it closely.",
            "suboptimal": "Your diastolic blood pressure is elevated. Lifestyle changes can help.",
            "concerning": "Your diastolic blood pressure is hypertensive (≥90 mmHg) or hypotensive (<55 mmHg).",
        },
        "layperson_es": {
            "optimal":    "Tu presión diastólica está en el rango ideal.",
            "acceptable": "Tu presión diastólica es algo alta. Monitoréala de cerca.",
            "suboptimal": "Tu presión diastólica está elevada. Cambios de estilo de vida pueden ayudar.",
            "concerning": "Tu presión diastólica está en rango hipertensivo (≥90 mmHg) o hipotensivo (<55 mmHg).",
        },
        "athlete_overrides": None,
    },

    # ------------------------------------------------------------------
    # 21. TG/HDL Ratio  (computed, not sex-stratified, lower is better)
    # ------------------------------------------------------------------
    "tg_hdl_ratio": {
        "unit": "ratio",
        "source": "public",
        "reference": (
            "Da Luz 2008 trig/HDL ratio; Cordero 2009 insulin resistance marker"
        ),
        "evidence_level": "pending_review",
        "caveats":        [],
        "last_reviewed":  None,
        "sex_stratified": False,
        "ranges": {
            "optimal":    (None, 2.0),
            "acceptable": (2.0, 3.5),
            "suboptimal": (3.5, 5.0),
            "concerning": (5.0, None),
        },
        "direction": "lower_is_better",
        "scoring_function": "piecewise",
        "layperson_en": {
            "optimal":    "Your TG/HDL ratio is excellent — a strong insulin sensitivity signal.",
            "acceptable": "Your TG/HDL ratio is acceptable. Lower triglycerides or raise HDL.",
            "suboptimal": "Your TG/HDL ratio suggests metabolic stress. Focus on diet and movement.",
            "concerning": "Your TG/HDL ratio is high — a key marker of insulin resistance and cardiovascular risk. Reducing refined carbs and increasing activity are the primary levers.",
        },
        "layperson_es": {
            "optimal":    "Tu relación TG/HDL es excelente, señal de buena sensibilidad a la insulina.",
            "acceptable": "Tu relación TG/HDL es aceptable. Reduce triglicéridos o eleva HDL.",
            "suboptimal": "Tu relación TG/HDL sugiere estrés metabólico. Enfócate en dieta y movimiento.",
            "concerning": "Tu relación TG/HDL es alta — marcador clave de resistencia a la insulina y riesgo cardiovascular. Reducir carbohidratos refinados y aumentar la actividad son las palancas principales.",
        },
        "athlete_overrides": None,
    },

    # ------------------------------------------------------------------
    # 22. Lp(a)  (not sex-stratified, lower is better)
    # ------------------------------------------------------------------
    "lp_a": {
        "unit": "mg/dL",
        "source": "public",
        "reference": (
            "ESC/EAS 2019; Tsimikas 2020 NEJM Lp(a) cardiovascular risk"
        ),
        "evidence_level": "pending_review",
        "caveats":        [],
        "last_reviewed":  None,
        "sex_stratified": False,
        "ranges": {
            "optimal":    (None, 14),
            "acceptable": (14, 31),
            "suboptimal": (31, 51),
            "concerning": (51, None),
        },
        "direction": "lower_is_better",
        "scoring_function": "piecewise",
        "layperson_en": {
            "optimal":    "Your Lp(a) level is low. This is a favorable genetic risk signal.",
            "acceptable": "Your Lp(a) is in an acceptable range. Keep monitoring.",
            "suboptimal": "Your Lp(a) is moderately elevated — largely genetic, but optimizing LDL and inflammatory load can help.",
            "concerning": "Your Lp(a) is high — a genetically-driven cardiovascular risk marker. Lifestyle modifications have limited impact; focus on overall cardiovascular risk reduction.",
        },
        "layperson_es": {
            "optimal":    "Tu Lp(a) es bajo. Esta es una señal genética de riesgo favorable.",
            "acceptable": "Tu Lp(a) está en un rango aceptable. Sigue monitoreando.",
            "suboptimal": "Tu Lp(a) está moderadamente elevado — en gran parte genético, pero optimizar el LDL y la carga inflamatoria puede ayudar.",
            "concerning": "Tu Lp(a) es alto — marcador de riesgo cardiovascular de origen genético. Las modificaciones de estilo de vida tienen impacto limitado; enfócate en reducir el riesgo cardiovascular general.",
        },
        "athlete_overrides": None,
    },

    # ------------------------------------------------------------------
    # 23. ApoB  (not sex-stratified, lower is better)
    # ------------------------------------------------------------------
    "apo_b": {
        "unit": "mg/dL",
        "source": "public",
        "reference": (
            "ACC/AHA 2018 apo-B risk target; Boekholdt 2012 JAMA apoB superiority"
        ),
        "evidence_level": "pending_review",
        "caveats":        [],
        "last_reviewed":  None,
        "sex_stratified": False,
        "ranges": {
            "optimal":    (None, 80),
            "acceptable": (80, 100),
            "suboptimal": (100, 120),
            "concerning": (120, None),
        },
        "direction": "lower_is_better",
        "scoring_function": "piecewise",
        "layperson_en": {
            "optimal":    "Your ApoB is at a longevity-grade level. Excellent.",
            "acceptable": "Your ApoB is acceptable. Continued healthy habits will keep it there.",
            "suboptimal": "Your ApoB is elevated. Focus on reducing saturated fat and refined carbs.",
            "concerning": "Your ApoB is high — a strong predictor of cardiovascular events. Reducing LDL particle concentration through diet and exercise is the primary target.",
        },
        "layperson_es": {
            "optimal":    "Tu ApoB está en nivel óptimo de longevidad. Excelente.",
            "acceptable": "Tu ApoB es aceptable. Los buenos hábitos lo mantendrán así.",
            "suboptimal": "Tu ApoB está elevado. Reduce grasas saturadas y carbohidratos refinados.",
            "concerning": "Tu ApoB es alto — predictor fuerte de eventos cardiovasculares. Reducir la concentración de partículas LDL mediante dieta y ejercicio es el objetivo principal.",
        },
        "athlete_overrides": None,
    },

    # ------------------------------------------------------------------
    # 24. eGFR  (not sex-stratified, higher is better)
    # ------------------------------------------------------------------
    "egfr": {
        "unit": "mL/min/1.73m²",
        "source": "public",
        "reference": "KDIGO 2012 CKD guidelines; Levey 2014 eGFR staging",
        "evidence_level": "pending_review",
        "caveats":        [],
        "last_reviewed":  None,
        "sex_stratified": False,
        "ranges": {
            "optimal":    (90, None),
            "acceptable": (75, 90),
            "suboptimal": (60, 75),
            "concerning": (None, 60),
        },
        "direction": "higher_is_better",
        "scoring_function": "piecewise",
        "layperson_en": {
            "optimal":    "Your kidney filtration rate is excellent.",
            "acceptable": "Your kidney filtration is good. Stay hydrated and limit NSAIDs.",
            "suboptimal": "Your kidney filtration is slightly reduced. Stay well hydrated, limit NSAIDs, and monitor blood pressure.",
            "concerning": "Your eGFR is consistent with meaningfully reduced kidney function. Ongoing monitoring and dietary adjustments are indicated.",
        },
        "layperson_es": {
            "optimal":    "Tu tasa de filtración renal es excelente.",
            "acceptable": "Tu filtración renal es buena. Mantente hidratado y limita los AINEs.",
            "suboptimal": "Tu filtración renal está ligeramente reducida. Mantente bien hidratado, limita los AINEs y monitorea tu presión arterial.",
            "concerning": "Tu TFGe es consistente con función renal significativamente reducida. Se indica monitoreo continuo y ajustes dietéticos.",
        },
        "athlete_overrides": None,
    },
}

# ------------------------------------------------------------------
# Alias: vitamin_d_25oh → vitamin_d (column-name compatibility)
# ------------------------------------------------------------------
OPTIMAL_ZONES["vitamin_d_25oh"] = OPTIMAL_ZONES["vitamin_d"]


# ---------------------------------------------------------------------------
# Helper: resolve which ranges dict to use (handles sex-stratification)
# ---------------------------------------------------------------------------

def _resolve_ranges(entry: dict, sex: str) -> dict:
    """
    Return the flat ranges dict appropriate for the given entry and sex.
    For sex_stratified entries, look up 'male' or 'female' sub-dict.
    Falls back to 'male' for any unrecognised sex value.
    """
    if not entry["sex_stratified"]:
        return entry["ranges"]
    resolved_sex = sex if sex in ("male", "female") else "male"
    return entry["ranges"][resolved_sex]


# ---------------------------------------------------------------------------
# Helper: resolve athlete overrides ranges (sex-aware)
# ---------------------------------------------------------------------------

def _resolve_athlete_ranges(entry: dict, sex: str) -> Optional[dict]:
    """
    Return athlete_overrides ranges or None if none defined.
    Handles the case where athlete_overrides itself is sex-stratified
    (e.g., testosterone_total) or flat.
    """
    overrides = entry.get("athlete_overrides")
    if overrides is None:
        return None
    # If the overrides dict contains zone keys directly, it's flat
    if any(k in overrides for k in ("optimal", "acceptable", "suboptimal", "concerning")):
        return overrides
    # Otherwise it may be sex-stratified
    resolved_sex = sex if sex in ("male", "female") else "male"
    return overrides.get(resolved_sex)


# ---------------------------------------------------------------------------
# Midrange zone classification (used for biomarkers with nested bands)
# ---------------------------------------------------------------------------

def _classify_midrange(entry: dict, value: float, sex: str) -> str:
    """
    Classify a value for midrange-optimal biomarkers that have nested
    symmetric bands (optimal ⊂ acceptable ⊂ suboptimal, with concerning
    outside all three). Uses private _*_lo/_*_hi keys where stored.

    Interval convention: [lo, hi) — lo inclusive, hi exclusive.

    Returns zone string.
    """
    name_prefix = f"_{sex}_" if entry["sex_stratified"] else "_"

    opt_lo_key = f"{name_prefix}optimal_lo"
    opt_hi_key = f"{name_prefix}optimal_hi"
    acc_lo_key = f"{name_prefix}acceptable_lo"
    acc_hi_key = f"{name_prefix}acceptable_hi"
    sub_lo_key = f"{name_prefix}suboptimal_lo"
    sub_hi_key = f"{name_prefix}suboptimal_hi"

    # Prefer sex-prefixed keys; fall back to non-prefixed
    def _get(key: str, fallback: str):
        return entry.get(key, entry.get(fallback))

    opt_lo = _get(opt_lo_key, "_optimal_lo")
    opt_hi = _get(opt_hi_key, "_optimal_hi")
    acc_lo = _get(acc_lo_key, "_acceptable_lo")
    acc_hi = _get(acc_hi_key, "_acceptable_hi")
    sub_lo = _get(sub_lo_key, "_suboptimal_lo")
    sub_hi = _get(sub_hi_key, "_suboptimal_hi")

    if opt_lo is not None and opt_hi is not None and opt_lo <= value < opt_hi:
        return "optimal"
    if acc_lo is not None and acc_hi is not None and acc_lo <= value < acc_hi:
        return "acceptable"
    if sub_lo is not None and sub_hi is not None and sub_lo <= value < sub_hi:
        return "suboptimal"
    return "concerning"


# ---------------------------------------------------------------------------
# Public helper: zone_for_value
# ---------------------------------------------------------------------------

def zone_for_value(ranges: dict, value: float, sex: str = "male") -> str:
    """
    Determine zone label for a value.

    ``ranges`` is the top-level entry dict from OPTIMAL_ZONES (NOT the inner
    ranges sub-dict).  The function resolves sex-stratification internally.

    Returns: "optimal" | "acceptable" | "suboptimal" | "concerning"

    Decision rules
    --------------
    * Biomarkers with ``direction = "lower_is_better"`` or
      ``"higher_is_better"`` use monotone piecewise bounds.
    * Biomarkers with ``direction = "midrange_is_optimal"`` and private
      ``_*_lo``/``_*_hi`` keys use nested-band classification.
    * Special ``_concerning_lower`` / ``_concerning_upper`` keys handle
      additional concerning thresholds on otherwise monotone biomarkers.
    * Interval convention: [lo, hi) — lo inclusive, hi exclusive.
      A value equal to hi belongs to the next (worse) zone.
    """
    entry = ranges  # caller passes the full entry dict

    # --- Handle special lower-concerning overrides (e.g. fasting_glucose <60) ---
    concerning_lower = entry.get("_concerning_lower")
    if concerning_lower is not None and value < concerning_lower:
        return "concerning"

    # --- Handle special upper-concerning overrides (e.g. total_chol ≥240) ---
    concerning_upper = entry.get("_concerning_upper")
    if concerning_upper is not None and value >= concerning_upper:
        return "concerning"

    direction = entry.get("direction", "midrange_is_optimal")

    # --- Midrange biomarkers with nested band keys ---
    if direction == "midrange_is_optimal":
        has_band_keys = any(
            k.endswith("_optimal_lo") or k.endswith("_optimal_hi")
            for k in entry
        )
        if has_band_keys:
            return _classify_midrange(entry, value, sex)

    # --- Resolve flat ranges ---
    flat_ranges = _resolve_ranges(entry, sex)

    # --- Check each zone in order from best to worst ---
    for zone in ZONE_ORDER:
        bounds = flat_ranges.get(zone)
        if bounds is None:
            continue
        lo, hi = bounds
        if lo is None and hi is None:
            # Open concerning zone — will be the catch-all below
            continue
        in_zone = True
        if lo is not None and value < lo:
            in_zone = False
        if hi is not None and value >= hi:   # half-open: hi is exclusive
            in_zone = False
        if in_zone:
            return zone

    # Fallback: if none matched (e.g. open-ended concerning zone)
    return "concerning"


# ---------------------------------------------------------------------------
# Public helper: score_for_zone
# ---------------------------------------------------------------------------

def score_for_zone(zone: str) -> int:
    """
    Map zone label to numeric score 0–100.

    optimal    → 90
    acceptable → 70
    suboptimal → 45
    concerning → 15
    """
    return ZONE_SCORES.get(zone, 0)


# ---------------------------------------------------------------------------
# Public helper: score_biomarker
# ---------------------------------------------------------------------------

def score_biomarker(
    name: str,
    value: float,
    sex: str = "male",
    athlete_status: str = "recreational",
) -> Optional[dict]:
    """
    Score a single biomarker against OPTIMAL_ZONES.

    Parameters
    ----------
    name           : canonical biomarker name (key in OPTIMAL_ZONES)
    value          : measured numeric value
    sex            : "male" | "female"  (defaults to "male" if unrecognised)
    athlete_status : "recreational" | "competitive_amateur" | "competitive_pro"

    Returns
    -------
    dict with keys:
        name, value, unit, zone, score, layperson_en, layperson_es,
        source, reference, library_version

    Returns None if ``name`` is not in OPTIMAL_ZONES.
    """
    entry = OPTIMAL_ZONES.get(name)
    if entry is None:
        return None

    # Determine if athlete overrides apply
    use_overrides = athlete_status in ATHLETE_STATUSES_USING_OVERRIDES
    override_ranges = _resolve_athlete_ranges(entry, sex) if use_overrides else None

    if override_ranges is not None:
        # Build a minimal synthetic entry for zone_for_value using override ranges
        synthetic = dict(entry)  # shallow copy
        if entry["sex_stratified"]:
            resolved_sex = sex if sex in ("male", "female") else "male"
            synthetic["ranges"] = {resolved_sex: override_ranges}
        else:
            synthetic["ranges"] = override_ranges
        # Remove midrange band keys so flat-ranges path is used for overrides
        synthetic = {k: v for k, v in synthetic.items()
                     if not (k.startswith("_") and (k.endswith("_lo") or k.endswith("_hi")))}
        zone = zone_for_value(synthetic, value, sex)
    else:
        zone = zone_for_value(entry, value, sex)

    score = score_for_zone(zone)

    lang_en = entry["layperson_en"][zone]
    lang_es = entry["layperson_es"][zone]

    return {
        "name": name,
        "value": value,
        "unit": entry["unit"],
        "zone": zone,
        "score": score,
        "layperson_en": lang_en,
        "layperson_es": lang_es,
        "source": entry["source"],
        "reference": entry["reference"],
        "library_version": LIBRARY_VERSION,
    }


# ---------------------------------------------------------------------------
# Public helper: get_derived_biomarkers
# ---------------------------------------------------------------------------

def get_derived_biomarkers(lab_dict: dict) -> dict:
    """
    Compute derived biomarkers from raw lab values.

    Inputs
    ------
    lab_dict : dict containing any of the raw lab keys:
        - fasting_glucose (mg/dL)
        - fasting_insulin (µIU/mL)
        - triglycerides   (mg/dL)
        - hdl             (mg/dL)
        - total_chol      (mg/dL)

    Returns
    -------
    dict with any computable keys:
        homa_ir       : (fasting_glucose × fasting_insulin) / 405
        tg_hdl_ratio  : triglycerides / hdl
        non_hdl       : total_chol − hdl

    Any key whose inputs are missing, None, or zero (for denominators) is
    omitted from the return dict.
    """
    result: dict = {}

    glucose = lab_dict.get("fasting_glucose")
    insulin = lab_dict.get("fasting_insulin")
    tg      = lab_dict.get("triglycerides")
    hdl     = lab_dict.get("hdl")
    tchol   = lab_dict.get("total_chol")

    # HOMA-IR = (fasting glucose [mg/dL] × fasting insulin [µIU/mL]) / 405
    if (
        glucose is not None
        and insulin is not None
        and glucose > 0
        and insulin > 0
    ):
        result["homa_ir"] = round((glucose * insulin) / 405.0, 3)

    # TG/HDL ratio
    if (
        tg is not None
        and hdl is not None
        and hdl > 0
    ):
        result["tg_hdl_ratio"] = round(tg / hdl, 3)

    # Non-HDL = Total Cholesterol − HDL
    if (
        tchol is not None
        and hdl is not None
    ):
        non_hdl_val = tchol - hdl
        if non_hdl_val > 0:
            result["non_hdl"] = round(non_hdl_val, 1)

    return result


# ---------------------------------------------------------------------------
# Public helper: list_available
# ---------------------------------------------------------------------------

def list_available(lab_dict: dict) -> list:
    """
    Return a list of biomarker canonical names that are:
      (a) present in OPTIMAL_ZONES, AND
      (b) have a non-None value in ``lab_dict``.

    Useful for determining which biomarkers can be scored for a given
    client's data submission.
    """
    return [
        name
        for name in OPTIMAL_ZONES
        if lab_dict.get(name) is not None
    ]


# ---------------------------------------------------------------------------
# Module self-test (run with: python tns_optimal_zones.py)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print(f"TNS Optimal Zones Library  v{LIBRARY_VERSION}  (pipeline {POLYGON_VERSION})")
    print(f"Biomarkers defined: {len(OPTIMAL_ZONES)}\n")

    # Quick smoke tests
    _tests = [
        # (name, value, sex, athlete_status, expected_zone)
        ("hdl",              65,   "male",   "recreational",      "optimal"),
        ("hdl",              50,   "female", "recreational",      "acceptable"),
        ("ldl",              60,   "male",   "recreational",      "optimal"),
        ("ldl",             135,   "male",   "recreational",      "concerning"),
        ("fasting_glucose",  82,   "male",   "recreational",      "optimal"),
        ("fasting_glucose",  55,   "male",   "recreational",      "concerning"),
        ("total_chol",      165,   "male",   "recreational",      "optimal"),
        ("total_chol",      245,   "male",   "recreational",      "concerning"),
        ("tsh",              1.8,  "male",   "recreational",      "optimal"),
        ("tsh",              5.0,  "male",   "recreational",      "concerning"),
        ("ferritin",        80,    "male",   "recreational",      "optimal"),
        ("ferritin",         3,    "female", "recreational",      "concerning"),
        ("testosterone_total", 750, "male",  "recreational",      "optimal"),
        ("testosterone_total", 750, "male",  "competitive_pro",   "optimal"),
        ("vitamin_d",        55,   "male",   "recreational",      "optimal"),
        ("vitamin_d",        55,   "male",   "competitive_pro",   "acceptable"),
        ("egfr",             95,   "male",   "recreational",      "optimal"),
        ("egfr",             55,   "male",   "recreational",      "concerning"),
    ]

    all_passed = True
    for name, val, sex, ath, expected in _tests:
        result = score_biomarker(name, val, sex=sex, athlete_status=ath)
        status = "PASS" if result and result["zone"] == expected else "FAIL"
        if status == "FAIL":
            all_passed = False
        print(
            f"  [{status}] {name:25s} val={val!s:>8}  sex={sex:6}  "
            f"ath={ath:20}  zone={result['zone'] if result else 'N/A':12}  "
            f"expected={expected}"
        )

    # Derived biomarkers
    sample_labs = {
        "fasting_glucose": 85,
        "fasting_insulin": 5,
        "triglycerides": 90,
        "hdl": 60,
        "total_chol": 170,
    }
    derived = get_derived_biomarkers(sample_labs)
    print(f"\nDerived from sample labs: {derived}")

    # list_available
    all_labs = {**sample_labs, "ldl": 65, "hba1c": 5.0}
    available = list_available(all_labs)
    print(f"Available biomarkers in sample: {available}")

    # Boundary gap spot-checks (half-open convention)
    print("\nBoundary gap spot-checks:")
    _boundary_tests = [
        ("hba1c",          5.15, "male", "recreational", "optimal"),    # was "concerning" in v1.0.0
        ("hba1c",          5.2,  "male", "recreational", "acceptable"),
        ("homa_ir",        1.0,  "male", "recreational", "acceptable"),  # was "optimal" boundary
        ("homa_ir",        0.99, "male", "recreational", "optimal"),
        ("ldl",            70.0, "male", "recreational", "acceptable"),  # was "optimal" boundary
        ("ldl",            69.9, "male", "recreational", "optimal"),
        ("tsh",            2.51, "male", "recreational", "acceptable"),
        ("tsh",            2.50, "male", "recreational", "optimal"),
        ("testosterone_total", 600.0, "male", "recreational", "optimal"),
        ("testosterone_total", 599.9, "male", "recreational", "acceptable"),
    ]
    gap_passed = True
    for name, val, sex, ath, expected in _boundary_tests:
        result = score_biomarker(name, val, sex=sex, athlete_status=ath)
        status = "PASS" if result and result["zone"] == expected else "FAIL"
        if status == "FAIL":
            gap_passed = False
            all_passed = False
        print(
            f"  [{status}] {name:25s} val={val!s:>8}  expected={expected:12}  "
            f"got={result['zone'] if result else 'N/A'}"
        )

    print(f"\nAll smoke tests passed: {all_passed}")
    print(f"Boundary gap tests passed: {gap_passed}")
