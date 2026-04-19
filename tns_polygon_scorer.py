"""
tns_polygon_scorer.py
=====================
TechNSports (TNS) Multidimensional Health Polygon Scoring Engine
-----------------------------------------------------------------
Pipeline: 4.1  (POLYGON_VERSION from tns_optimal_zones)

Architecture
~~~~~~~~~~~~
This module is the main entry point for computing a client's six-category
health polygon.  It orchestrates three data tiers per category:

  Tier A — Biomarker inputs (blood labs)  →  tns_optimal_zones.score_biomarker
  Tier B — Scan inputs (ShapeScale / InBody)  →  SCAN_SCORING (defined here)
  Tier C — Questionnaire  →  tns_questionnaire.score_category_questionnaire

Hard rules enforced throughout
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
  Rule 44 : ShapeScale wins over InBody for overlap fields
            (bf_pct, bmi, whr, whtr, weight_kg).
  Rule 45 : Missing data never crashes. Every category always scores.
  Rule 46 : Every input in the output includes layperson_en + layperson_es.
  Rule 47 : Every scan threshold has a source reference (see SCAN_SCORING).
  Rule 48 : Athlete clients get adjusted zones for select biomarkers
            (delegated to tns_optimal_zones.score_biomarker).

Forbidden language
~~~~~~~~~~~~~~~~~~
The words "diagnose," "treat," "cure," "disease," "patient," "prescribe"
MUST NOT appear in any user-facing string in this module.

Usage
-----
    from tns_polygon_scorer import score_polygon

    result = score_polygon(
        unified=reconciled_dict,          # from tns_reconcile.reconcile_scanners()
        questionnaire=parsed_q,           # from tns_questionnaire.parse_questionnaire()
        sex="male",
        athlete_status="recreational",
        client_id="client_001",
    )
    print(result["overall_score"])        # 0-100
    print(result["categories"]["body_composition"]["score"])
"""

from __future__ import annotations

import datetime
from typing import Optional

from tns_optimal_zones import (
    LIBRARY_VERSION,
    POLYGON_VERSION,
    score_biomarker,
    get_derived_biomarkers,
    assert_clinician_review_complete,
    get_report_disclaimer,
)
from tns_questionnaire import (
    score_category_questionnaire,
    check_par_q,
    CATEGORY_ITEMS,
)

# ---------------------------------------------------------------------------
# Zone → score map (mirrors tns_optimal_zones.ZONE_SCORES)
# ---------------------------------------------------------------------------

_ZONE_SCORES: dict[str, int] = {
    "optimal":    90,
    "acceptable": 70,
    "suboptimal": 45,
    "concerning": 15,
}


# ---------------------------------------------------------------------------
# SCAN_SCORING
# ---------------------------------------------------------------------------
# Each entry mirrors the OPTIMAL_ZONES structure so _score_scan_variable()
# can handle it uniformly.  direction is one of:
#   "lower_is_better" | "higher_is_better" | "midrange_is_optimal"
# sex_stratified = True means 'male' and 'female' sub-dicts exist.
# ---------------------------------------------------------------------------

SCAN_SCORING: dict[str, dict] = {

    # ------------------------------------------------------------------
    # bf_pct — Body Fat Percentage (sex-stratified, sequential ranges)
    # Zones are non-overlapping sequential bands (not nested).
    # Concerning: male <6 or ≥30; female <16 or ≥41.
    # Sources: ACSM Guidelines 11th ed; Gallagher 2000 IJCO; WHO 1995
    # ------------------------------------------------------------------
    "body_fat": {
        "unit": "%",
        "reference": (
            "ACSM Guidelines for Exercise Testing 11th ed; "
            "Gallagher 2000 Int J Obes; WHO 1995 body fat standards"
        ),
        "sex_stratified": True,
        # Use lower_is_better direction so _zone_from_scan_entry uses the flat
        # piecewise path; the concerning bounds (lower/upper) are checked first.
        "direction": "lower_is_better",
        "ranges": {
            "male": {
                "optimal":    (8, 19),
                "acceptable": (19, 25),
                "suboptimal": (25, 30),       # hi = concerning_upper
                "concerning": (None, None),   # <6 or ≥30; enforced by bounds below
            },
            "female": {
                "optimal":    (21, 31),
                "acceptable": (31, 36),
                "suboptimal": (36, 41),       # hi = concerning_upper
                "concerning": (None, None),   # <16 or ≥41; enforced by bounds below
            },
        },
        # Sex-specific concerning bounds — checked before flat piecewise
        "_male_concerning_lower":   6,
        "_male_concerning_upper":   30,
        "_female_concerning_lower": 16,
        "_female_concerning_upper": 41,
        "layperson_en": {
            "optimal":    "Your body fat is in the healthy optimal range. Great composition balance.",
            "acceptable": "Your body fat is acceptable. Small adjustments can move you to optimal.",
            "suboptimal": "Your body fat is above the ideal range. Consistent training and nutrition can lower it.",
            "concerning": "Your body fat needs attention — either too high or too low for optimal health.",
        },
        "layperson_es": {
            "optimal":    "Tu grasa corporal está en el rango óptimo saludable. Excelente equilibrio de composición.",
            "acceptable": "Tu grasa corporal es aceptable. Pequeños ajustes pueden llevarte al óptimo.",
            "suboptimal": "Tu grasa corporal está por encima del rango ideal. El entrenamiento y la nutrición consistentes pueden reducirla.",
            "concerning": "Tu grasa corporal necesita atención — es demasiado alta o baja para una salud óptima.",
        },
    },

    # ------------------------------------------------------------------
    # bmi — Body Mass Index (not sex-stratified, sequential ranges)
    # Zones are non-overlapping sequential bands.
    # Concerning: <18.5 or ≥30.
    # Source: WHO BMI classification 2000; NIH NHLBI guidelines
    # ------------------------------------------------------------------
    "bmi_func": {
        "unit": "kg/m²",
        "reference": (
            "WHO BMI Classification 2000; NIH NHLBI Obesity guidelines"
        ),
        "sex_stratified": False,
        "direction": "lower_is_better",   # flat piecewise path; bounds checked first
        "ranges": {
            "optimal":    (18.5, 23.0),
            "acceptable": (23.0, 25.0),
            "suboptimal": (25.0, 30.0),       # hi = concerning_upper
            "concerning": (None, None),       # <18.5 or ≥30; enforced by bounds below
        },
        "_concerning_lower": 18.5,
        "_concerning_upper": 30.0,
        "layperson_en": {
            "optimal":    "Your BMI is in the ideal range for overall health and longevity.",
            "acceptable": "Your BMI is slightly above ideal but still within a healthy zone.",
            "suboptimal": "Your BMI is in the overweight range. Body composition training can help.",
            "concerning": "Your BMI is outside the healthy range. A structured program can help.",
        },
        "layperson_es": {
            "optimal":    "Tu IMC está en el rango ideal para la salud y la longevidad.",
            "acceptable": "Tu IMC está un poco por encima del ideal pero aún en zona saludable.",
            "suboptimal": "Tu IMC está en rango de sobrepeso. El entrenamiento de composición corporal puede ayudar.",
            "concerning": "Tu IMC está fuera del rango saludable. Un programa estructurado puede ayudar.",
        },
    },

    # ------------------------------------------------------------------
    # whr — Waist-to-Hip Ratio (sex-stratified, lower is better)
    # Source: WHO 2008 waist circumference and WHR; IDF metabolic syndrome
    # ------------------------------------------------------------------
    "whr_func": {
        "unit": "ratio",
        "reference": (
            "WHO 2008 Waist Circumference and Waist-Hip Ratio report; "
            "IDF Metabolic Syndrome Definition 2006"
        ),
        "sex_stratified": True,
        "direction": "lower_is_better",
        "ranges": {
            "male": {
                "optimal":    (None, 0.85),
                "acceptable": (0.85, 0.91),
                "suboptimal": (0.91, 0.951),  # hi = concerning lo
                "concerning": (0.951, None),
            },
            "female": {
                "optimal":    (None, 0.75),
                "acceptable": (0.75, 0.81),
                "suboptimal": (0.81, 0.851),  # hi = concerning lo
                "concerning": (0.851, None),
            },
        },
        "layperson_en": {
            "optimal":    "Your waist-to-hip ratio is excellent — low abdominal fat distribution.",
            "acceptable": "Your waist-to-hip ratio is acceptable. Core-focused training can improve it.",
            "suboptimal": "Your waist-to-hip ratio is elevated. Reducing abdominal fat is the key target.",
            "concerning": "Your waist-to-hip ratio is high — a key metabolic risk signal. Prioritize this.",
        },
        "layperson_es": {
            "optimal":    "Tu relación cintura-cadera es excelente — baja distribución de grasa abdominal.",
            "acceptable": "Tu relación cintura-cadera es aceptable. El entrenamiento de core puede mejorarla.",
            "suboptimal": "Tu relación cintura-cadera está elevada. Reducir la grasa abdominal es el objetivo clave.",
            "concerning": "Tu relación cintura-cadera es alta — una señal clave de riesgo metabólico. Prioriza esto.",
        },
    },

    # ------------------------------------------------------------------
    # whtr — Waist-to-Height Ratio (not sex-stratified, lower is better)
    # Source: Ashwell & Hsieh 2005; Browning 2010 meta-analysis
    # ------------------------------------------------------------------
    "whtr_func": {
        "unit": "ratio",
        "reference": (
            "Ashwell & Hsieh 2005 Obes Rev; "
            "Browning 2010 Nutr Res Rev waist-height meta-analysis"
        ),
        "sex_stratified": False,
        "direction": "lower_is_better",
        "ranges": {
            "optimal":    (None, 0.40),
            "acceptable": (0.40, 0.48),
            "suboptimal": (0.48, 0.55),   # hi = concerning lo
            "concerning": (0.55, None),
        },
        "layperson_en": {
            "optimal":    "Your waist-to-height ratio is excellent — a strong cardiovascular health signal.",
            "acceptable": "Your waist-to-height ratio is acceptable. Small improvements in core fat can help.",
            "suboptimal": "Your waist-to-height ratio is elevated — a moderate cardiovascular risk indicator.",
            "concerning": "Your waist-to-height ratio is high. Reducing central fat is a top priority.",
        },
        "layperson_es": {
            "optimal":    "Tu relación cintura-talla es excelente — señal fuerte de salud cardiovascular.",
            "acceptable": "Tu relación cintura-talla es aceptable. Pequeñas mejoras en la grasa central pueden ayudar.",
            "suboptimal": "Tu relación cintura-talla está elevada — indicador moderado de riesgo cardiovascular.",
            "concerning": "Tu relación cintura-talla es alta. Reducir la grasa central es una prioridad máxima.",
        },
    },

    # ------------------------------------------------------------------
    # waist_cm — Waist Circumference in cm (sex-stratified, lower is better)
    # Source: IDF 2006; WHO 2008; Alberti 2009 harmonized MetS criteria
    # ------------------------------------------------------------------
    "waist_func": {
        "unit": "cm",
        "reference": (
            "IDF Metabolic Syndrome Definition 2006; WHO 2008 WHR report; "
            "Alberti 2009 harmonized MetS criteria JAHA"
        ),
        "sex_stratified": True,
        "direction": "lower_is_better",
        "ranges": {
            "male": {
                "optimal":    (None, 80),
                "acceptable": (80, 91),
                "suboptimal": (91, 102.1),    # hi = concerning lo
                "concerning": (102.1, None),
            },
            "female": {
                "optimal":    (None, 72),
                "acceptable": (72, 81),
                "suboptimal": (81, 88.1),     # hi = concerning lo
                "concerning": (88.1, None),
            },
        },
        "layperson_en": {
            "optimal":    "Your waist size is in the healthy range — low abdominal fat risk.",
            "acceptable": "Your waist is slightly above optimal. Core training and nutrition can help.",
            "suboptimal": "Your waist size is elevated. Reducing belly fat lowers metabolic risk.",
            "concerning": "Your waist size is high — a significant metabolic risk marker. Make this a priority.",
        },
        "layperson_es": {
            "optimal":    "Tu medida de cintura está en el rango saludable — bajo riesgo de grasa abdominal.",
            "acceptable": "Tu cintura está ligeramente por encima del óptimo. El entrenamiento de core y la nutrición pueden ayudar.",
            "suboptimal": "Tu medida de cintura está elevada. Reducir la grasa abdominal disminuye el riesgo metabólico.",
            "concerning": "Tu medida de cintura es alta — un marcador de riesgo metabólico significativo. Prioriza esto.",
        },
    },

    # ------------------------------------------------------------------
    # visceral_fat_level — InBody scale 1–20 (not sex-stratified, lower is better)
    # Source: InBody technical documentation; Shuster 2012 visceral fat review
    # ------------------------------------------------------------------
    "visc_fat_func": {
        "unit": "level",
        "reference": (
            "InBody visceral fat level technical documentation; "
            "Shuster 2012 Obes Rev visceral adiposity review"
        ),
        "sex_stratified": False,
        "direction": "lower_is_better",
        "ranges": {
            "optimal":    (1, 8),
            "acceptable": (8, 11),
            "suboptimal": (11, 14),   # hi = concerning lo
            "concerning": (14, None),
        },
        "layperson_en": {
            "optimal":    "Your visceral fat level is in the healthy range. Internal organs are well protected.",
            "acceptable": "Your visceral fat is slightly elevated. Aerobic training and diet can reduce it.",
            "suboptimal": "Your visceral fat is elevated — this type wraps around organs and raises health risks.",
            "concerning": "Your visceral fat is high. Reducing it is one of the most impactful health steps you can take.",
        },
        "layperson_es": {
            "optimal":    "Tu nivel de grasa visceral está en el rango saludable. Los órganos internos están bien protegidos.",
            "acceptable": "Tu grasa visceral está ligeramente elevada. El entrenamiento aeróbico y la dieta pueden reducirla.",
            "suboptimal": "Tu grasa visceral está elevada — este tipo rodea los órganos y aumenta los riesgos de salud.",
            "concerning": "Tu grasa visceral es alta. Reducirla es uno de los pasos de salud más impactantes que puedes tomar.",
        },
    },

    # ------------------------------------------------------------------
    # phase_angle — Phase Angle in degrees (not sex-stratified, higher is better)
    # Source: Barbosa-Silva 2005 Nutrition; Selberg & Selberg 2002 EJCN
    # ------------------------------------------------------------------
    "phase_angle_func": {
        "unit": "°",
        "reference": (
            "Barbosa-Silva 2005 Nutrition phase angle reference; "
            "Selberg & Selberg 2002 EJCN phase angle clinical significance"
        ),
        "sex_stratified": False,
        "direction": "higher_is_better",
        "ranges": {
            "optimal":    (7.0, None),
            "acceptable": (6.0, 7.0),
            "suboptimal": (5.0, 6.0),
            "concerning": (None, 5.0),
        },
        "layperson_en": {
            "optimal":    "Your phase angle is excellent — a strong signal of cellular health and resilience.",
            "acceptable": "Your phase angle is good. Consistent training and hydration support this marker.",
            "suboptimal": "Your phase angle is slightly low. Improved nutrition and hydration can raise it.",
            "concerning": "Your phase angle is low — it reflects reduced cellular integrity. Prioritize recovery.",
        },
        "layperson_es": {
            "optimal":    "Tu ángulo de fase es excelente — señal fuerte de salud celular y resiliencia.",
            "acceptable": "Tu ángulo de fase es bueno. El entrenamiento consistente y la hidratación apoyan este marcador.",
            "suboptimal": "Tu ángulo de fase es algo bajo. Una mejor nutrición e hidratación pueden elevarlo.",
            "concerning": "Tu ángulo de fase es bajo — refleja integridad celular reducida. Prioriza la recuperación.",
        },
    },

    # ------------------------------------------------------------------
    # ffmi — Fat-Free Mass Index (sex-stratified, higher is better)
    # Source: Kouri 1995 NEJM; Schutz 2002 FFMI reference ranges
    # ------------------------------------------------------------------
    "ffmi_func": {
        "unit": "kg/m²",
        "reference": (
            "Kouri 1995 NEJM FFMI natural limit; "
            "Schutz 2002 Am J Clin Nutr FFMI reference values"
        ),
        "sex_stratified": True,
        "direction": "higher_is_better",
        "ranges": {
            "male": {
                "optimal":    (20, 26),   # hi=26 intentional upper cap; >26 falls to concerning
                "acceptable": (18, 20),
                "suboptimal": (17, 18),
                "concerning": (None, 17),
            },
            "female": {
                "optimal":    (16, 22),   # hi=22 intentional upper cap
                "acceptable": (14, 16),
                "suboptimal": (13, 14),
                "concerning": (None, 13),
            },
        },
        "layperson_en": {
            "optimal":    "Your lean mass index is excellent — you carry healthy, functional muscle.",
            "acceptable": "Your lean mass index is adequate. Progressive training can push it higher.",
            "suboptimal": "Your lean mass index is below ideal. Resistance training and protein intake help.",
            "concerning": "Your lean mass index is low. Building muscle is a high-priority health goal.",
        },
        "layperson_es": {
            "optimal":    "Tu índice de masa magra es excelente — tienes músculo saludable y funcional.",
            "acceptable": "Tu índice de masa magra es adecuado. El entrenamiento progresivo puede elevarlo.",
            "suboptimal": "Tu índice de masa magra está por debajo del ideal. El entrenamiento de resistencia y la proteína ayudan.",
            "concerning": "Tu índice de masa magra es bajo. Construir músculo es un objetivo de salud prioritario.",
        },
    },

    # ------------------------------------------------------------------
    # smi — Skeletal Muscle Mass Index (sex-stratified, higher is better)
    # Source: Janssen 2002 JAGS; Cruz-Jentoft 2019 EWGSOP2 sarcopenia
    # ------------------------------------------------------------------
    "smi_func": {
        "unit": "kg/m²",
        "reference": (
            "Janssen 2002 JAGS SMI sarcopenia thresholds; "
            "Cruz-Jentoft 2019 Age Ageing EWGSOP2 sarcopenia consensus"
        ),
        "sex_stratified": True,
        "direction": "higher_is_better",
        "ranges": {
            "male": {
                "optimal":    (10.0, None),
                "acceptable": (8.5, 10.0),
                "suboptimal": (7.5, 8.5),
                "concerning": (None, 7.5),
            },
            "female": {
                "optimal":    (6.5, None),
                "acceptable": (5.5, 6.5),
                "suboptimal": (4.5, 5.5),
                "concerning": (None, 4.5),
            },
        },
        "layperson_en": {
            "optimal":    "Your skeletal muscle mass index is excellent — strong foundation for long-term health.",
            "acceptable": "Your muscle mass index is good. Targeted resistance training can improve it further.",
            "suboptimal": "Your muscle mass index is below optimal. Resistance work and protein are the key levers.",
            "concerning": "Your muscle mass index is low. Building muscle is critical for metabolism and mobility.",
        },
        "layperson_es": {
            "optimal":    "Tu índice de masa muscular esquelética es excelente — base sólida para la salud a largo plazo.",
            "acceptable": "Tu índice de masa muscular es bueno. El entrenamiento de resistencia específico puede mejorarlo.",
            "suboptimal": "Tu índice de masa muscular está por debajo del óptimo. La resistencia y la proteína son los factores clave.",
            "concerning": "Tu índice de masa muscular es bajo. Construir músculo es crítico para el metabolismo y la movilidad.",
        },
    },

    # ------------------------------------------------------------------
    # inbody_score — InBody proprietary score 0–100 (not sex-stratified,
    # higher is better)
    # Source: InBody technical documentation
    # ------------------------------------------------------------------
    "inbody_score_func": {
        "unit": "pts",
        "reference": (
            "InBody proprietary composite score technical documentation; "
            "InBody 770 user reference manual"
        ),
        "sex_stratified": False,
        "direction": "higher_is_better",
        "ranges": {
            "optimal":    (80, None),
            "acceptable": (70, 80),
            "suboptimal": (60, 70),
            "concerning": (None, 60),
        },
        "layperson_en": {
            "optimal":    "Your InBody score is excellent — overall body composition is in a strong zone.",
            "acceptable": "Your InBody score is good. Small improvements in body fat or muscle can push it higher.",
            "suboptimal": "Your InBody score is below optimal. A structured program can move this significantly.",
            "concerning": "Your InBody score needs improvement. Body composition work will have a big impact.",
        },
        "layperson_es": {
            "optimal":    "Tu puntaje InBody es excelente — la composición corporal general está en una zona fuerte.",
            "acceptable": "Tu puntaje InBody es bueno. Pequeñas mejoras en grasa o músculo pueden elevarlo.",
            "suboptimal": "Tu puntaje InBody está por debajo del óptimo. Un programa estructurado puede moverlo significativamente.",
            "concerning": "Tu puntaje InBody necesita mejora. El trabajo de composición corporal tendrá un gran impacto.",
        },
    },

    # ------------------------------------------------------------------
    # shape_score — ShapeScale proprietary score 0–100 (not sex-stratified,
    # higher is better)
    # Source: ShapeScale technical documentation
    # ------------------------------------------------------------------
    "shape_score_func": {
        "unit": "pts",
        "reference": (
            "ShapeScale proprietary composite shape score technical documentation"
        ),
        "sex_stratified": False,
        "direction": "higher_is_better",
        "ranges": {
            "optimal":    (85, None),
            "acceptable": (70, 85),
            "suboptimal": (55, 70),
            "concerning": (None, 55),
        },
        "layperson_en": {
            "optimal":    "Your ShapeScale score is excellent — shape and composition are in a strong zone.",
            "acceptable": "Your ShapeScale score is good. Continued training and nutrition will move it higher.",
            "suboptimal": "Your ShapeScale score has room to improve. A targeted plan can make a real difference.",
            "concerning": "Your ShapeScale score is low. Consistent effort on training and nutrition will improve it.",
        },
        "layperson_es": {
            "optimal":    "Tu puntaje ShapeScale es excelente — la forma y composición están en una zona fuerte.",
            "acceptable": "Tu puntaje ShapeScale es bueno. El entrenamiento y la nutrición continuos lo elevarán.",
            "suboptimal": "Tu puntaje ShapeScale tiene margen de mejora. Un plan específico puede marcar una diferencia real.",
            "concerning": "Tu puntaje ShapeScale es bajo. El esfuerzo consistente en entrenamiento y nutrición lo mejorará.",
        },
    },
}


# ---------------------------------------------------------------------------
# Lab key mapping — unified dict prefixed keys → canonical biomarker names
# ---------------------------------------------------------------------------

LAB_KEY_MAP: dict[str, str] = {
    "lab_total_chol":    "total_chol",
    "lab_hdl":           "hdl",
    "lab_ldl":           "ldl",
    "lab_triglycerides": "triglycerides",
    "lab_glucose":       "fasting_glucose",
    "lab_hba1c":         "hba1c",
    "lab_insulin":       "fasting_insulin",
    "lab_hscrp":         "hs_crp",
    "lab_sbp":           "sbp",
    "lab_dbp":           "dbp",
    # Extended panel
    "lab_tsh":           "tsh",
    "lab_free_t3":       "free_t3",
    "lab_free_t4":       "free_t4",
    "lab_testosterone":  "testosterone_total",
    "lab_cortisol_am":   "cortisol_am",
    "lab_vitamin_d":     "vitamin_d",
    "lab_vitamin_b12":   "vitamin_b12",
    "lab_ferritin":      "ferritin",
    "lab_lp_a":          "lp_a",
    "lab_apo_b":         "apo_b",
    # Phase B extension points — in LAB_KEY_MAP so values pass through
    # _extract_labs() into the labs dict; score_biomarker() returns None
    # for these (no OPTIMAL_ZONES entry yet) and they are gracefully added
    # to the missing list rather than crashing.  Threshold entries will be
    # added in a future LIBRARY_VERSION bump.
    "lab_dhea_s":        "dhea_s",
    "lab_estradiol":     "estradiol",
    "lab_egfr":          "egfr",
}


# ---------------------------------------------------------------------------
# Category definitions
# ---------------------------------------------------------------------------

# Each category specifies:
#   tier_a_biomarkers : list[str]   canonical biomarker names
#   tier_b_scan_keys  : list[tuple] (unified_key, scoring_name, unit, func_key_or_None)
#   tier_c_items      : list[str]   questionnaire item names (from CATEGORY_ITEMS)
#   base_weights      : dict        {"a": float, "b": float, "c": float}
#   max_score         : int
#   overall_weight    : float

CATEGORY_DEFS: dict[str, dict] = {
    "body_composition": {
        "tier_a_biomarkers": ["testosterone_total", "cortisol_am", "vitamin_d"],
        "tier_b_scan_keys": [
            ("bf_pct",               "bf_pct",             "%",      "body_fat"),
            ("bmi",                  "bmi",                "kg/m²",  "bmi_func"),
            ("whr",                  "whr",                "ratio",  "whr_func"),
            ("whtr",                 "whtr",               "ratio",  "whtr_func"),
            ("ib_visceral_fat_level","visceral_fat_level", "level",  "visc_fat_func"),
            ("ib_phase_angle",       "phase_angle",        "°",      "phase_angle_func"),
            ("ib_smm_kg",            "smm_kg",             "kg",     None),
            ("ffmi",                 "ffmi",               "kg/m²",  "ffmi_func"),
        ],
        "tier_c_items": [
            "q_activity_hours_per_week",
            "q_weight_trend_perception",
            "q_training_frequency_days_per_week",
        ],
        "base_weights": {"a": 0.25, "b": 0.55, "c": 0.20},
        "max_score": 99,
        "overall_weight": 0.20,
    },

    "heart_vascular": {
        "tier_a_biomarkers": [
            "total_chol", "hdl", "ldl", "non_hdl", "triglycerides",
            "tg_hdl_ratio", "hs_crp", "sbp", "dbp", "lp_a", "apo_b",
        ],
        "tier_b_scan_keys": [
            ("whr",      "whr",      "ratio", "whr_func"),
            ("bmi",      "bmi",      "kg/m²", "bmi_func"),
            ("ss_waist_cm", "waist_cm", "cm", "waist_func"),
        ],
        "tier_c_items": [
            "q_family_history_heart",
            "q_smoking",
            "q_alcohol_drinks_per_week",
            "q_cv_fitness_stairs_3_flights",
            "q_chest_pain_on_exertion",
        ],
        "base_weights": {"a": 0.55, "b": 0.15, "c": 0.30},
        "max_score": 99,
        "overall_weight": 0.20,
    },

    "metabolic_function": {
        "tier_a_biomarkers": [
            "fasting_glucose", "hba1c", "fasting_insulin", "homa_ir",
            "tg_hdl_ratio", "tsh", "free_t3", "free_t4",
        ],
        "tier_b_scan_keys": [
            ("ss_waist_cm",           "waist_cm",          "cm",    "waist_func"),
            ("ib_visceral_fat_level", "visceral_fat_level","level", "visc_fat_func"),
            ("bmi",                   "bmi",               "kg/m²", "bmi_func"),
        ],
        "tier_c_items": [
            "q_energy_consistency_days_per_week",
            "q_afternoon_crashes",
            "q_cold_sensitivity",
        ],
        "base_weights": {"a": 0.55, "b": 0.25, "c": 0.20},
        "max_score": 99,
        "overall_weight": 0.15,
    },

    "hormonal_balance": {
        "tier_a_biomarkers": [
            "testosterone_total", "cortisol_am", "tsh", "free_t3", "free_t4",
            "vitamin_d", "vitamin_b12", "ferritin",
            # optional — included if present
            "dhea_s", "estradiol",
        ],
        "tier_b_scan_keys": [
            ("ib_phase_angle", "phase_angle", "°", "phase_angle_func"),
        ],
        "tier_c_items": [
            "q_libido_past_4_weeks",
            "q_mood_swings_past_4_weeks",
            "q_thermoregulation",
            "q_morning_motivation",
            "q_menstrual_regularity",
        ],
        "base_weights": {"a": 0.50, "b": 0.10, "c": 0.40},
        "max_score": 99,
        "overall_weight": 0.15,
    },

    "stress_recovery": {
        "tier_a_biomarkers": ["cortisol_am", "hs_crp", "ferritin"],
        "tier_b_scan_keys": [
            ("ib_phase_angle", "phase_angle", "°", "phase_angle_func"),
        ],
        "tier_c_items": [
            "q_sleep_hours_per_night",
            "q_sleep_quality_rested_days",
            "q_stress_interference_past_4_weeks",
            "q_recovery_time_after_workout",
            "q_overwhelmed",
        ],
        "base_weights": {"a": 0.30, "b": 0.10, "c": 0.60},
        "max_score": 99,
        "overall_weight": 0.15,
    },

    "lifestyle_fitness": {
        "tier_a_biomarkers": [],
        "tier_b_scan_keys": [
            ("ib_smm_kg",     "smm_kg",       "kg",    None),
            ("ib_smi",        "smi",          "kg/m²", "smi_func"),
            ("ib_score",      "inbody_score", "pts",   "inbody_score_func"),
            ("ss_shape_score","shape_score",  "pts",   "shape_score_func"),
        ],
        "tier_c_items": [
            "q_training_frequency_days_per_week",
            "q_training_type",
            "q_training_intensity_1to10",
            "q_daily_steps",
            "q_nutrition_whole_food_meals",
            "q_hydration_liters_per_day",
            "q_protein_meals_with_palm_serving",
        ],
        "base_weights": {"a": 0.00, "b": 0.35, "c": 0.65},
        "max_score": 99,
        "overall_weight": 0.15,
    },
}


# ---------------------------------------------------------------------------
# Overall category weights
# ---------------------------------------------------------------------------

CATEGORY_WEIGHTS: dict[str, float] = {
    cat: defn["overall_weight"] for cat, defn in CATEGORY_DEFS.items()
}
# Verify they sum to 1.00 (sanity check at import time)
assert abs(sum(CATEGORY_WEIGHTS.values()) - 1.0) < 1e-9, (
    f"CATEGORY_WEIGHTS must sum to 1.0, got {sum(CATEGORY_WEIGHTS.values())}"
)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _expand_tier_weights(base_weights: dict, present_tiers: set) -> dict:
    """
    Redistribute weights of absent tiers proportionally to present tiers.

    Parameters
    ----------
    base_weights  : {"a": 0.55, "b": 0.15, "c": 0.30}
    present_tiers : {"a", "c"}   — "b" has no data

    Returns redistributed weights that sum to 1.0.
    """
    absent = {t for t in base_weights if t not in present_tiers}
    if not absent:
        return base_weights  # nothing to redistribute

    absent_weight = sum(base_weights[t] for t in absent)
    present_total = sum(base_weights[t] for t in present_tiers)

    if present_total == 0:
        equal_share = 1.0 / len(present_tiers) if present_tiers else 0.0
        return {t: (equal_share if t in present_tiers else 0.0) for t in base_weights}

    result = {}
    for t in base_weights:
        if t in present_tiers:
            result[t] = base_weights[t] + absent_weight * (base_weights[t] / present_total)
        else:
            result[t] = 0.0
    return result


def _extract_labs(unified: dict) -> dict:
    """
    Apply LAB_KEY_MAP to the unified dict and compute derived biomarkers.

    Returns a flat dict keyed by canonical biomarker name.
    """
    labs: dict = {}

    # Map prefixed keys
    for prefixed_key, canonical in LAB_KEY_MAP.items():
        val = unified.get(prefixed_key)
        if val is not None:
            labs[canonical] = val

    # Also accept canonical keys directly (no prefix) for flexibility
    for canonical in LAB_KEY_MAP.values():
        if canonical not in labs and unified.get(canonical) is not None:
            labs[canonical] = unified[canonical]

    # Compute derived biomarkers
    derived = get_derived_biomarkers(labs)
    for k, v in derived.items():
        if k not in labs:   # don't overwrite if already supplied directly
            labs[k] = v

    return labs


def _score_scan_variable(
    scoring_name: str,
    value: float,
    sex: str,
) -> Optional[dict]:
    """
    Score a single scan variable using SCAN_SCORING.

    Returns a result dict (zone, score, layperson_en, layperson_es)
    or None if the scoring_name is not in SCAN_SCORING.
    """
    entry = SCAN_SCORING.get(scoring_name)
    if entry is None:
        return None

    sex_key = sex if sex in ("male", "female") else "male"
    direction = entry.get("direction", "lower_is_better")

    # Resolve sex-stratified ranges
    ranges = entry["ranges"]
    if entry.get("sex_stratified"):
        flat_ranges = ranges.get(sex_key, ranges.get("male", {}))
    else:
        flat_ranges = ranges

    # --- Determine zone ---
    zone = _zone_from_scan_entry(entry, value, sex_key, flat_ranges, direction)

    score = _ZONE_SCORES.get(zone, 0)
    layperson_en = entry["layperson_en"].get(zone, "")
    layperson_es = entry["layperson_es"].get(zone, "")

    return {
        "zone":         zone,
        "score":        score,
        "layperson_en": layperson_en,
        "layperson_es": layperson_es,
        "reference":    entry.get("reference", ""),
    }


def _zone_from_scan_entry(
    entry: dict,
    value: float,
    sex_key: str,
    flat_ranges: dict,
    direction: str,
) -> str:
    """
    Classify a scan value into a zone, handling sex-specific concerning
    bounds, midrange entries, and standard monotone ranges.
    """
    # Check sex-specific special bounds stored in the entry dict
    # (used by body_fat and bmi_func)
    prefix = f"_{sex_key}_" if entry.get("sex_stratified") else "_"
    concerning_lower = entry.get(f"{prefix}concerning_lower") or entry.get("_concerning_lower")
    concerning_upper = entry.get(f"{prefix}concerning_upper") or entry.get("_concerning_upper")

    if concerning_lower is not None and value < concerning_lower:
        return "concerning"
    if concerning_upper is not None and value >= concerning_upper:
        return "concerning"

    # For midrange optimal: check if nested band keys exist
    if direction == "midrange_is_optimal":
        opt_lo_key  = f"{prefix}optimal_lo"
        opt_hi_key  = f"{prefix}optimal_hi"
        acc_lo_key  = f"{prefix}acceptable_lo"
        acc_hi_key  = f"{prefix}acceptable_hi"
        sub_lo_key  = f"{prefix}suboptimal_lo"
        sub_hi_key  = f"{prefix}suboptimal_hi"

        def _get(k: str):
            return entry.get(k)

        opt_lo  = _get(opt_lo_key)  if _get(opt_lo_key)  is not None else _get("_optimal_lo")
        opt_hi  = _get(opt_hi_key)  if _get(opt_hi_key)  is not None else _get("_optimal_hi")
        acc_lo  = _get(acc_lo_key)  if _get(acc_lo_key)  is not None else _get("_acceptable_lo")
        acc_hi  = _get(acc_hi_key)  if _get(acc_hi_key)  is not None else _get("_acceptable_hi")
        sub_lo  = _get(sub_lo_key)  if _get(sub_lo_key)  is not None else _get("_suboptimal_lo")
        sub_hi  = _get(sub_hi_key)  if _get(sub_hi_key)  is not None else _get("_suboptimal_hi")

        if opt_lo is not None and opt_hi is not None and opt_lo <= value < opt_hi:
            return "optimal"
        if acc_lo is not None and acc_hi is not None and acc_lo <= value < acc_hi:
            return "acceptable"
        if sub_lo is not None and sub_hi is not None and sub_lo <= value < sub_hi:
            return "suboptimal"

        # Fall through to flat ranges check below if band keys not resolved
        if opt_lo is None and opt_hi is None:
            pass  # no band keys; fall through to flat
        else:
            return "concerning"

    # Flat piecewise check (lower_is_better, higher_is_better, or plain midrange)
    zone_order = ["optimal", "acceptable", "suboptimal", "concerning"]
    for zone in zone_order:
        bounds = flat_ranges.get(zone)
        if bounds is None:
            continue
        lo, hi = bounds
        if lo is None and hi is None:
            continue  # open-ended catch-all; handled at end
        in_zone = True
        if lo is not None and value < lo:
            in_zone = False
        if hi is not None and value >= hi:   # half-open: hi is exclusive
            in_zone = False
        if in_zone:
            return zone

    return "concerning"


def _determine_scan_source(
    unified_key: str,
    unified: dict,
) -> str:
    """
    Determine the data source label for a scan variable.

    Rule 44 overlap fields: bf_pct, bmi, whr, whtr, weight_kg → use
    primary_weight_source if available.
    """
    overlap_fields = {"bf_pct", "bmi", "whr", "whtr", "weight_kg"}
    bare_key = unified_key.lstrip("_")

    if bare_key in overlap_fields or unified_key in overlap_fields:
        primary = unified.get("primary_weight_source", "shapescale")
        return primary if primary in ("shapescale", "inbody") else "shapescale"

    if unified_key.startswith("ss_"):
        return "shapescale"
    if unified_key.startswith("ib_"):
        return "inbody"

    # Computed fields (ffmi, bf_pct without prefix) — derive from primary
    primary = unified.get("primary_weight_source", "shapescale")
    return primary if primary in ("shapescale", "inbody") else "shapescale"


def _score_tier_a(
    category_name: str,
    labs: dict,
    sex: str,
    athlete_status: str,
    pregnant: bool,
) -> tuple[Optional[int], list[dict], list[str]]:
    """
    Score all available Tier A biomarkers for a category.

    Returns (tier_score, inputs_list, missing_list).
    tier_score is None if no biomarkers were scored.
    """
    defn = CATEGORY_DEFS[category_name]
    biomarker_names = defn["tier_a_biomarkers"]

    scored_inputs: list[dict] = []
    missing: list[str] = []

    if pregnant and category_name == "body_composition":
        # Body composition is excluded during pregnancy
        return None, [], ["body_composition Tier A excluded — pregnancy flag set."]

    for bm_name in biomarker_names:
        val = labs.get(bm_name)
        if val is None:
            missing.append(bm_name)
            continue

        result = score_biomarker(
            bm_name, val, sex=sex, athlete_status=athlete_status
        )
        if result is None:
            missing.append(bm_name)
            continue

        scored_inputs.append({
            "name":         bm_name,
            "value":        val,
            "unit":         result["unit"],
            "source":       "lab",
            "zone":         result["zone"],
            "input_score":  result["score"],
            "layperson_en": result["layperson_en"],
            "layperson_es": result["layperson_es"],
        })

    if not scored_inputs:
        return None, scored_inputs, missing

    avg = round(sum(i["input_score"] for i in scored_inputs) / len(scored_inputs))
    return avg, scored_inputs, missing


def _score_tier_b(
    category_name: str,
    unified: dict,
    sex: str,
    pregnant: bool,
) -> tuple[Optional[int], list[dict], list[str]]:
    """
    Score all available Tier B scan variables for a category.

    Returns (tier_score, inputs_list, missing_list).
    tier_score is None if no variables were scored.
    """
    defn = CATEGORY_DEFS[category_name]
    scan_keys = defn["tier_b_scan_keys"]

    scored_inputs: list[dict] = []
    missing: list[str] = []

    if pregnant and category_name == "body_composition":
        return None, [], ["body_composition Tier B excluded — pregnancy flag set."]

    for unified_key, scoring_name, unit, func_key in scan_keys:
        val = unified.get(unified_key)
        if val is None:
            missing.append(unified_key)
            continue

        # smm_kg has no scoring function — carry as informational input only
        if func_key is None:
            source = _determine_scan_source(unified_key, unified)
            scored_inputs.append({
                "name":         scoring_name,
                "value":        float(val),
                "unit":         unit,
                "source":       source,
                "zone":         "informational",
                "input_score":  None,
                "layperson_en": "Skeletal muscle mass — used for SMI calculation, not scored directly.",
                "layperson_es": "Masa muscular esquelética — usada para el cálculo del IMM, no se puntúa directamente.",
            })
            continue

        result = _score_scan_variable(func_key, float(val), sex)
        if result is None:
            missing.append(unified_key)
            continue

        source = _determine_scan_source(unified_key, unified)
        scored_inputs.append({
            "name":         scoring_name,
            "value":        float(val),
            "unit":         unit,
            "source":       source,
            "zone":         result["zone"],
            "input_score":  result["score"],
            "layperson_en": result["layperson_en"],
            "layperson_es": result["layperson_es"],
        })

    # Only inputs with a numeric score count toward the tier average
    scoreable = [i for i in scored_inputs if i["input_score"] is not None]
    if not scoreable:
        return None, scored_inputs, missing

    avg = round(sum(i["input_score"] for i in scoreable) / len(scoreable))
    return avg, scored_inputs, missing


def _score_tier_c(
    category_name: str,
    questionnaire: Optional[dict],
    sex: str,
) -> tuple[Optional[int], list[dict], list[str]]:
    """
    Score the Tier C questionnaire portion for a category.

    Returns (tier_score, inputs_list, missing_list).
    tier_score is None when questionnaire is None.
    """
    if questionnaire is None:
        return None, [], [f"No questionnaire provided for {category_name}."]

    result = score_category_questionnaire(category_name, questionnaire, sex=sex)

    if not result["items_scored"]:
        return None, [], result["items_missing"]

    inputs: list[dict] = []
    for item in result["items_scored"]:
        inputs.append({
            "name":         item["name"],
            "value":        item["value"],
            "unit":         "response",
            "source":       "questionnaire",
            "zone":         item["zone"],
            "input_score":  item["score"],
            "layperson_en": item["layperson_en"],
            "layperson_es": item["layperson_es"],
        })

    tier_score = round(result["tier_c_score"])
    return tier_score, inputs, result["items_missing"]


def _determine_category_confidence(
    tier_a_score: Optional[int],
    tier_b_score: Optional[int],
    tier_c_score: Optional[int],
) -> str:
    """
    high     : Tier A labs present AND Tier B scan present
    moderate : Tier B scan present, no Tier A labs
    baseline : only Tier C questionnaire
    """
    if tier_a_score is not None and tier_b_score is not None:
        return "high"
    if tier_b_score is not None:
        return "moderate"
    return "baseline"


def _missing_data_notes_for_category(
    category_name: str,
    missing_a: list[str],
    missing_b: list[str],
    questionnaire: Optional[dict],
) -> list[str]:
    """
    Generate plain-language missing-data notes for a category.
    """
    notes: list[str] = []

    # --- Tier A missing clusters ---
    thyroid_panel = {"tsh", "free_t3", "free_t4"}
    if category_name in ("hormonal_balance", "metabolic_function"):
        if thyroid_panel.issubset(set(missing_a)):
            notes.append(
                "No thyroid panel (TSH, T3, T4) — "
                f"{category_name.replace('_', ' ').title()} scored from scan and questionnaire only."
            )

    if "cortisol_am" in missing_a and category_name == "stress_recovery":
        notes.append(
            "No cortisol test — Stress & Recovery uses inflammation markers only."
        )

    if "cortisol_am" in missing_a and category_name == "hormonal_balance":
        notes.append(
            "No morning cortisol result — Hormonal Balance scored without HPA axis biomarker."
        )

    if missing_a and category_name == "heart_vascular":
        lipid_missing = [m for m in missing_a if m in (
            "total_chol", "hdl", "ldl", "triglycerides", "non_hdl"
        )]
        if lipid_missing:
            notes.append(
                "No lipid panel — Heart & Vascular scored from scan and questionnaire data only."
            )

    # --- Tier B missing ---
    if missing_b and all(k in missing_b for k in ("bf_pct", "bmi")):
        notes.append(
            f"No primary body scan data for {category_name.replace('_', ' ')} — "
            "Tier B scored from available scan fields only."
        )

    # --- No questionnaire ---
    if questionnaire is None:
        notes.append(
            f"No questionnaire responses for {category_name.replace('_', ' ')} — "
            "Tier C not included in this score."
        )

    return notes


# ---------------------------------------------------------------------------
# Public API: score_category
# ---------------------------------------------------------------------------

def score_category(
    category_name: str,
    unified: dict,
    questionnaire: Optional[dict],
    sex: str = "male",
    athlete_status: str = "recreational",
) -> dict:
    """
    Score one polygon category.  Returns the category result dict.

    Parameters
    ----------
    category_name  : one of the six category keys in CATEGORY_DEFS
    unified        : output from tns_reconcile.reconcile_scanners()
    questionnaire  : parsed questionnaire dict or None
    sex            : "male" | "female"
    athlete_status : "recreational" | "competitive_amateur" | "competitive_pro"
    """
    if category_name not in CATEGORY_DEFS:
        raise ValueError(
            f"Unknown category '{category_name}'. "
            f"Valid: {list(CATEGORY_DEFS.keys())}"
        )

    defn = CATEGORY_DEFS[category_name]
    pregnant = bool(unified.get("pregnant", False))

    # ── Extract labs ────────────────────────────────────────────────────────
    labs = _extract_labs(unified)

    # ── Score all three tiers ───────────────────────────────────────────────
    tier_a_score, inputs_a, missing_a = _score_tier_a(
        category_name, labs, sex, athlete_status, pregnant
    )
    tier_b_score, inputs_b, missing_b = _score_tier_b(
        category_name, unified, sex, pregnant
    )
    tier_c_score, inputs_c, missing_c = _score_tier_c(
        category_name, questionnaire, sex
    )

    # ── Determine which tiers have data ─────────────────────────────────────
    present_tiers: set[str] = set()
    if tier_a_score is not None:
        present_tiers.add("a")
    if tier_b_score is not None:
        present_tiers.add("b")
    if tier_c_score is not None:
        present_tiers.add("c")

    # If no tiers have data, fall back to baseline score of 50
    if not present_tiers:
        return {
            "score":             50,
            "max":               defn["max_score"],
            "tier_scores":       {"a": None, "b": None, "c": None},
            "tier_weights_used": {"a": 0.0, "b": 0.0, "c": 0.0},
            "inputs":            [],
            "rendering":         "dashed",
            "confidence":        "baseline",
        }

    # ── Expand weights for absent tiers ─────────────────────────────────────
    tier_weights = _expand_tier_weights(defn["base_weights"], present_tiers)

    # ── Compute weighted category score ─────────────────────────────────────
    weighted_sum = 0.0
    if tier_a_score is not None:
        weighted_sum += tier_a_score * tier_weights["a"]
    if tier_b_score is not None:
        weighted_sum += tier_b_score * tier_weights["b"]
    if tier_c_score is not None:
        weighted_sum += tier_c_score * tier_weights["c"]

    raw_score = round(weighted_sum)
    # Clamp to [0, max_score]
    category_score = max(0, min(raw_score, defn["max_score"]))

    # ── Build combined inputs list ───────────────────────────────────────────
    all_inputs = inputs_a + inputs_b + inputs_c

    # ── Confidence and rendering ─────────────────────────────────────────────
    confidence = _determine_category_confidence(
        tier_a_score, tier_b_score, tier_c_score
    )
    has_scan_or_lab = (tier_a_score is not None or tier_b_score is not None)
    rendering = "solid" if has_scan_or_lab else "dashed"

    return {
        "score":             category_score,
        "max":               defn["max_score"],
        "tier_scores":       {
            "a": tier_a_score,
            "b": tier_b_score,
            "c": tier_c_score,
        },
        "tier_weights_used": {
            k: round(v, 4) for k, v in tier_weights.items()
        },
        "inputs":            all_inputs,
        "rendering":         rendering,
        "confidence":        confidence,
        "_missing_a":        missing_a,
        "_missing_b":        missing_b,
        "_missing_c":        missing_c,
    }


# ---------------------------------------------------------------------------
# Public API: score_polygon
# ---------------------------------------------------------------------------

def score_polygon(
    unified: dict,
    questionnaire: Optional[dict] = None,
    sex: str = "male",
    athlete_status: str = "recreational",
    client_id: Optional[str] = None,
) -> dict:
    """
    Score all 6 categories and compute the overall health polygon score.

    Parameters
    ----------
    unified : dict
        Output from tns_reconcile.reconcile_scanners().
        Must contain scan data (ib_*, ss_*) and optionally lab_* keys.
    questionnaire : dict, optional
        Parsed questionnaire responses (from tns_questionnaire.parse_questionnaire()).
        If None, Tier C scores are absent for all categories.
    sex : str
        "male" or "female"
    athlete_status : str
        "recreational" | "competitive_amateur" | "competitive_pro"
    client_id : str, optional
        Identifier stored in the output for traceability.

    Returns
    -------
    dict matching the output schema defined in the module docstring.
    """
    assert_clinician_review_complete("tns_polygon_scorer.score_polygon")
    projection_date = datetime.date.today().isoformat()
    pregnant = bool(unified.get("pregnant", False))

    # ── PAR-Q check ──────────────────────────────────────────────────────────
    par_q_escalation = False
    if questionnaire is not None:
        par_q_escalation = check_par_q(questionnaire)

    # ── Score all six categories ─────────────────────────────────────────────
    categories: dict[str, dict] = {}
    all_missing_notes: list[str] = []
    cross_scanner_flags: list[str] = []

    for cat_name in CATEGORY_DEFS:
        cat_result = score_category(
            cat_name,
            unified,
            questionnaire,
            sex=sex,
            athlete_status=athlete_status,
        )

        # Extract and clean private missing keys before storing
        missing_a = cat_result.pop("_missing_a", [])
        missing_b = cat_result.pop("_missing_b", [])
        missing_c = cat_result.pop("_missing_c", [])

        categories[cat_name] = cat_result

        # Accumulate missing-data notes
        notes = _missing_data_notes_for_category(
            cat_name, missing_a, missing_b, questionnaire
        )
        all_missing_notes.extend(notes)

    # ── Pregnant flag: annotate body_composition inputs ──────────────────────
    if pregnant:
        bc = categories.get("body_composition", {})
        if "inputs" in bc:
            bc["inputs"].insert(0, {
                "name":         "pregnancy_flag",
                "value":        True,
                "unit":         "",
                "source":       "system",
                "zone":         "informational",
                "input_score":  None,
                "layperson_en": "Body composition scoring is paused — pregnancy flag is set.",
                "layperson_es": "La puntuación de composición corporal está en pausa — se detectó indicador de embarazo.",
            })
        all_missing_notes.append(
            "Pregnancy flag set — body composition Tier A and Tier B are excluded."
        )

    # ── Cross-scanner flags (Rule 44) ────────────────────────────────────────
    overlap_fields = ["bf_pct", "bmi", "whr", "whtr", "weight_kg"]
    has_ss = any(unified.get(f"ss_{f}") is not None or unified.get(f) is not None
                 for f in overlap_fields)
    has_ib = any(unified.get(f"ib_{f}") is not None for f in ["smm_kg", "phase_angle",
                 "visceral_fat_level", "smi", "score"])
    primary = unified.get("primary_weight_source")
    if has_ss and has_ib and primary:
        cross_scanner_flags.append(
            f"Rule 44 applied: '{primary}' used as primary source for "
            f"overlap fields {overlap_fields}."
        )
    if has_ss and has_ib and not primary:
        cross_scanner_flags.append(
            "Both ShapeScale and InBody data detected but "
            "'primary_weight_source' key not set in unified dict. "
            "Defaulting to 'shapescale' for overlap fields (Rule 44)."
        )

    # ── Overall score ────────────────────────────────────────────────────────
    weight_sum = sum(CATEGORY_WEIGHTS.values())
    overall_score = round(
        sum(
            categories[cat]["score"] * CATEGORY_WEIGHTS[cat]
            for cat in CATEGORY_DEFS
        ) / weight_sum
    )
    overall_score = max(0, min(overall_score, 100))

    # ── Overall confidence = minimum across all 6 categories ─────────────────
    confidence_rank = {"high": 3, "moderate": 2, "baseline": 1}
    confidence_str  = {3: "high", 2: "moderate", 1: "baseline"}
    min_rank = min(
        confidence_rank.get(categories[cat]["confidence"], 1)
        for cat in CATEGORY_DEFS
    )
    overall_confidence = confidence_str[min_rank]

    # ── Deduplicate missing notes ────────────────────────────────────────────
    seen: set[str] = set()
    deduped_notes: list[str] = []
    for note in all_missing_notes:
        if note not in seen:
            seen.add(note)
            deduped_notes.append(note)

    return {
        "client_id":           client_id,
        "projection_date":     projection_date,
        "library_version":     LIBRARY_VERSION,
        "polygon_version":     POLYGON_VERSION,
        "confidence":          overall_confidence,
        "overall_score":       overall_score,
        "categories":          categories,
        "cross_scanner_flags": cross_scanner_flags,
        "par_q_escalation":    par_q_escalation,
        "pregnant":            pregnant,
        "cluster":             None,   # Phase B
        "missing_data_notes":  deduped_notes,
        "disclaimer":          get_report_disclaimer(),
    }


# ---------------------------------------------------------------------------
# __main__ smoke test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import json

    print("=" * 70)
    print("TNS Polygon Scorer — Smoke Test")
    print(f"Library: {LIBRARY_VERSION}  |  Pipeline: {POLYGON_VERSION}")
    print("=" * 70)

    # ── Synthetic unified dict (mimics tns_reconcile output) ─────────────────
    synthetic_unified = {
        # Rule 44: ShapeScale is primary
        "primary_weight_source": "shapescale",

        # ShapeScale outputs
        "bf_pct":        22.5,      # male optimal edge
        "bmi":           23.8,      # acceptable
        "whr":           0.82,      # male acceptable
        "whtr":          0.46,      # acceptable
        "weight_kg":     82.0,
        "ss_waist_cm":   85.0,      # male acceptable
        "ss_shape_score": 78.0,     # acceptable

        # InBody outputs
        "ib_visceral_fat_level": 6,     # optimal
        "ib_phase_angle":        7.2,   # optimal
        "ib_smm_kg":            38.5,   # informational
        "ib_smi":                9.8,   # male acceptable
        "ib_score":              76.0,  # acceptable
        "ffmi":                  21.0,  # male optimal

        # Lab values (prefixed, as from tns_reconcile)
        "lab_hdl":           62,        # male optimal
        "lab_ldl":           85,        # acceptable
        "lab_total_chol":    168,       # optimal
        "lab_triglycerides": 95,        # optimal
        "lab_glucose":       82,        # optimal
        "lab_hba1c":         5.0,       # optimal
        "lab_insulin":       5.5,       # optimal
        "lab_hscrp":         0.4,       # optimal
        "lab_sbp":           112,       # optimal
        "lab_dbp":           72,        # optimal
        "lab_tsh":           1.8,       # optimal
        "lab_free_t3":       3.6,       # optimal
        "lab_free_t4":       1.3,       # optimal
        "lab_testosterone":  720,       # male optimal
        "lab_cortisol_am":   15.0,      # optimal
        "lab_vitamin_d":     58,        # optimal
        "lab_vitamin_b12":   750,       # optimal
        "lab_ferritin":      90,        # male optimal

        "pregnant": False,
    }

    # ── Synthetic questionnaire ───────────────────────────────────────────────
    synthetic_questionnaire = {
        "q_activity_hours_per_week":           "5-7 hours",
        "q_weight_trend_perception":           "stable",
        "q_training_frequency_days_per_week":  "4",
        "q_family_history_heart":              "no",
        "q_smoking":                           "never",
        "q_alcohol_drinks_per_week":           "0-3",
        "q_cv_fitness_stairs_3_flights":       "yes",
        "q_chest_pain_on_exertion":            "no",
        "q_energy_consistency_days_per_week":  "6-7",
        "q_afternoon_crashes":                 "never",
        "q_cold_sensitivity":                  "no",
        "q_libido_past_4_weeks":               "strong",
        "q_mood_swings_past_4_weeks":          "rarely",
        "q_thermoregulation":                  "no",
        "q_morning_motivation":                "within_15min",
        # q_menstrual_regularity intentionally absent (male client)
        "q_sleep_hours_per_night":             "7-7.9",
        "q_sleep_quality_rested_days":         "often",
        "q_stress_interference_past_4_weeks":  "few_times",
        "q_recovery_time_after_workout":       "1_2_days",
        "q_overwhelmed":                       "sometimes",
        "q_training_type":                     "mixed",
        "q_training_intensity_1to10":          7,
        "q_daily_steps":                       "7500-9999",
        "q_nutrition_whole_food_meals":        "most_75",
        "q_hydration_liters_per_day":          "2-3",
        "q_protein_meals_with_palm_serving":   "two_of_3",
    }

    # ── Test 1: Full data (all three tiers) ───────────────────────────────────
    print("\n--- Test 1: Full data (male, recreational) ---")
    result_full = score_polygon(
        unified=synthetic_unified,
        questionnaire=synthetic_questionnaire,
        sex="male",
        athlete_status="recreational",
        client_id="smoke_test_001",
    )
    print(f"Overall score   : {result_full['overall_score']}")
    print(f"Overall confidence: {result_full['confidence']}")
    print(f"PAR-Q escalation: {result_full['par_q_escalation']}")
    print(f"Pregnant flag   : {result_full['pregnant']}")
    print(f"Cross-scanner   : {result_full['cross_scanner_flags']}")
    print()
    all_scored = True
    for cat, cat_result in result_full["categories"].items():
        ts = cat_result["tier_scores"]
        conf = cat_result["confidence"]
        rend = cat_result["rendering"]
        n_inputs = len(cat_result["inputs"])
        scored_ok = cat_result["score"] is not None
        if not scored_ok:
            all_scored = False
        print(
            f"  {cat:25s}  score={cat_result['score']:>3}  "
            f"A={str(ts['a']):>4}  B={str(ts['b']):>4}  C={str(ts['c']):>4}  "
            f"conf={conf:10}  render={rend:6}  inputs={n_inputs}"
        )
    print(f"\nAll 6 categories scored: {all_scored}")

    # ── Test 2: No questionnaire (Tier C absent everywhere) ───────────────────
    print("\n--- Test 2: No questionnaire (Tier C absent) ---")
    result_no_q = score_polygon(
        unified=synthetic_unified,
        questionnaire=None,
        sex="male",
        athlete_status="recreational",
        client_id="smoke_test_002",
    )
    print(f"Overall score   : {result_no_q['overall_score']}")
    print(f"Overall confidence: {result_no_q['confidence']}")
    all_scored_no_q = True
    for cat, cat_result in result_no_q["categories"].items():
        ts = cat_result["tier_scores"]
        scored_ok = cat_result["score"] is not None
        if not scored_ok:
            all_scored_no_q = False
        print(
            f"  {cat:25s}  score={cat_result['score']:>3}  "
            f"A={str(ts['a']):>4}  B={str(ts['b']):>4}  C={str(ts['c']):>4}"
        )
    print(f"\nAll 6 categories scored (no questionnaire): {all_scored_no_q}")

    # ── Test 3: Labs only (no scan data) ─────────────────────────────────────
    print("\n--- Test 3: Labs only (no scan data) ---")
    labs_only_unified = {k: v for k, v in synthetic_unified.items()
                         if k.startswith("lab_") or k == "pregnant"}
    result_labs_only = score_polygon(
        unified=labs_only_unified,
        questionnaire=synthetic_questionnaire,
        sex="female",
        athlete_status="competitive_amateur",
        client_id="smoke_test_003",
    )
    print(f"Overall score   : {result_labs_only['overall_score']}")
    print(f"Overall confidence: {result_labs_only['confidence']}")
    for cat, cat_result in result_labs_only["categories"].items():
        ts = cat_result["tier_scores"]
        print(
            f"  {cat:25s}  score={cat_result['score']:>3}  "
            f"A={str(ts['a']):>4}  B={str(ts['b']):>4}  C={str(ts['c']):>4}  "
            f"render={cat_result['rendering']}"
        )

    # ── Test 4: Questionnaire only (no labs, no scan) ────────────────────────
    print("\n--- Test 4: Questionnaire only (baseline) ---")
    result_q_only = score_polygon(
        unified={"pregnant": False},
        questionnaire=synthetic_questionnaire,
        sex="male",
        athlete_status="recreational",
        client_id="smoke_test_004",
    )
    print(f"Overall score   : {result_q_only['overall_score']}")
    print(f"Overall confidence: {result_q_only['confidence']}")
    for cat, cat_result in result_q_only["categories"].items():
        ts = cat_result["tier_scores"]
        print(
            f"  {cat:25s}  score={cat_result['score']:>3}  "
            f"A={str(ts['a']):>4}  B={str(ts['b']):>4}  C={str(ts['c']):>4}  "
            f"render={cat_result['rendering']:6}  conf={cat_result['confidence']}"
        )

    # ── Test 5: PAR-Q trigger ────────────────────────────────────────────────
    print("\n--- Test 5: PAR-Q trigger (chest pain) ---")
    parq_q = dict(synthetic_questionnaire)
    parq_q["q_chest_pain_on_exertion"] = "yes"
    result_parq = score_polygon(
        unified=synthetic_unified,
        questionnaire=parq_q,
        sex="male",
        client_id="smoke_test_005",
    )
    print(f"PAR-Q escalation: {result_parq['par_q_escalation']}  (expected True)")

    # ── Test 6: Pregnant flag ────────────────────────────────────────────────
    print("\n--- Test 6: Pregnant flag ---")
    preg_unified = dict(synthetic_unified)
    preg_unified["pregnant"] = True
    result_preg = score_polygon(
        unified=preg_unified,
        questionnaire=synthetic_questionnaire,
        sex="female",
        client_id="smoke_test_006",
    )
    bc_inputs = result_preg["categories"]["body_composition"]["inputs"]
    preg_note_found = any(i.get("name") == "pregnancy_flag" for i in bc_inputs)
    print(f"Pregnant flag   : {result_preg['pregnant']}  (expected True)")
    print(f"Pregnancy input : {preg_note_found}  (expected True)")

    # ── Missing data notes ───────────────────────────────────────────────────
    print("\n--- Missing data notes (full run) ---")
    for note in result_full.get("missing_data_notes", []):
        print(f"  • {note}")

    print("\n" + "=" * 70)
    print("Smoke test complete.")
    print("=" * 70)
