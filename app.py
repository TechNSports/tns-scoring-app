"""
TNS Health Map — Streamlit Web App
Internal tool for health map generation and client PCA projection.

Run locally:
    cd "02_MEXICO/PCA_Pipeline"
    streamlit run app.py

Requires models built via the Colab notebook (Step 1 — Build Models).
"""

import datetime
import json
import random
import sys
import tempfile
from pathlib import Path

import os

import streamlit as st

# ── Page config (must be the first Streamlit call) ────────────────────────────
st.set_page_config(
    page_title="TNS Health Map",
    page_icon="🔬",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Password gate ─────────────────────────────────────────────────────────────
# Password is set via Streamlit Cloud Secrets as `app_password`.
# When running locally without a secrets file the gate falls open automatically.

def _check_password():
    """Gates the app behind a password set via Streamlit Cloud secrets.
    When running locally without secrets, falls open (no password required)."""
    try:
        expected = st.secrets["app_password"]
    except Exception:
        return True  # local dev, no secrets file = open access
    if st.session_state.get("_authed"):
        return True
    st.title("TNS Health Map")
    st.caption("Body composition intelligence — TechNSports · Mérida, Yucatán")
    pw = st.text_input("App password", type="password")
    if pw and pw == expected:
        st.session_state["_authed"] = True
        st.rerun()
    elif pw:
        st.error("Wrong password")
    return False

if not _check_password():
    st.stop()

# ── Path setup ────────────────────────────────────────────────────────────────
# Use os.path.abspath so the path is correct even when launched via nohup
# (where __file__ may be relative to the launch directory).
APP_DIR = Path(os.path.abspath(__file__)).parent
sys.path.insert(0, str(APP_DIR))

DEFAULT_MODEL_DIR = str(APP_DIR / "models")

# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
  [data-testid="stSidebar"] { background: #0f172a; }
  [data-testid="stSidebar"] * { color: #e2e8f0 !important; }
  [data-testid="stSidebar"] .stTextInput input,
  [data-testid="stSidebar"] .stNumberInput input,
  [data-testid="stSidebar"] .stSelectbox select {
    background: #1e293b; color: #f1f5f9;
  }
  .badge-full    { color: #10b981; font-weight: 700; font-size: 1rem; }
  .badge-partial { color: #f59e0b; font-weight: 700; font-size: 1rem; }
  .tns-header    { color: #0f172a; font-size: 2rem; font-weight: 800; margin-bottom: 0; }
  .tns-sub       { color: #64748b; font-size: 0.9rem; margin-top: 0; }
</style>
""", unsafe_allow_html=True)


# ── Preset value generator ────────────────────────────────────────────────────
def _apply_preset(profile: str) -> None:
    """
    Populate lab + lifestyle session_state keys with random values that match
    the requested clinical profile: 'healthy', 'average', or 'unhealthy'.
    """
    r = random

    if profile == "healthy":
        labs = dict(
            lab_total_chol    = round(r.uniform(150, 185), 1),
            lab_hdl           = round(r.uniform(55,  75),  1),
            lab_ldl           = round(r.uniform(65,  100), 1),
            lab_triglycerides = round(r.uniform(65,  120), 1),
            lab_glucose       = round(r.uniform(72,  88),  1),
            lab_hba1c         = round(r.uniform(4.8, 5.2), 1),
            lab_insulin       = round(r.uniform(3.0, 7.5), 1),
            lab_hscrp         = round(r.uniform(0.1, 0.7), 2),
            lab_sbp           = float(r.randint(105, 118)),
            lab_dbp           = float(r.randint(62,  74)),
        )
        life = dict(
            life_vig    = r.randint(150, 250),
            life_mod    = r.randint(180, 300),
            life_sed    = round(r.uniform(4.5, 6.5),  1),
            life_sleep  = round(r.uniform(7.5, 9.0),  1),
            life_smoker = "Never",
            life_alcohol= r.randint(0, 2),
            life_stress = r.randint(1, 3),
            life_health = r.randint(8, 10),
        )
    elif profile == "average":
        labs = dict(
            lab_total_chol    = round(r.uniform(195, 230), 1),
            lab_hdl           = round(r.uniform(40,  52),  1),
            lab_ldl           = round(r.uniform(120, 148), 1),
            lab_triglycerides = round(r.uniform(130, 175), 1),
            lab_glucose       = round(r.uniform(88,  102), 1),
            lab_hba1c         = round(r.uniform(5.3, 5.7), 1),
            lab_insulin       = round(r.uniform(8.0, 15.0),1),
            lab_hscrp         = round(r.uniform(0.8, 2.8), 2),
            lab_sbp           = float(r.randint(118, 130)),
            lab_dbp           = float(r.randint(74,  84)),
        )
        life = dict(
            life_vig    = r.randint(45,  120),
            life_mod    = r.randint(90,  180),
            life_sed    = round(r.uniform(7.5, 10.0), 1),
            life_sleep  = round(r.uniform(6.0, 7.5),  1),
            life_smoker = "Never",
            life_alcohol= r.randint(2, 7),
            life_stress = r.randint(4, 6),
            life_health = r.randint(5, 7),
        )
    else:  # unhealthy
        labs = dict(
            lab_total_chol    = round(r.uniform(255, 295), 1),
            lab_hdl           = round(r.uniform(25,  38),  1),
            lab_ldl           = round(r.uniform(170, 210), 1),
            lab_triglycerides = round(r.uniform(275, 430), 1),
            lab_glucose       = round(r.uniform(108, 140), 1),
            lab_hba1c         = round(r.uniform(5.9, 7.8), 1),
            lab_insulin       = round(r.uniform(18,  38),  1),
            lab_hscrp         = round(r.uniform(4.0, 9.5), 2),
            lab_sbp           = float(r.randint(140, 165)),
            lab_dbp           = float(r.randint(88,  100)),
        )
        life = dict(
            life_vig    = r.randint(0,  20),
            life_mod    = r.randint(0,  40),
            life_sed    = round(r.uniform(10.5, 14.0), 1),
            life_sleep  = round(r.uniform(4.0,  6.0),  1),
            life_smoker = r.choice(["Former", "Current"]),
            life_alcohol= r.randint(10, 20),
            life_stress = r.randint(7, 10),
            life_health = r.randint(2, 4),
        )

    st.session_state.update(labs)
    st.session_state.update(life)


# ── Pending-preset resolver (must run BEFORE any keyed widgets are created) ───
# Buttons only queue the profile name; this block applies values on the next
# render cycle, before widgets are instantiated, so Streamlit doesn't complain.
if "_pending_preset" in st.session_state:
    _apply_preset(st.session_state.pop("_pending_preset"))


# ── ShapeScale unit-preference change → auto-convert display values ───────────
# When the user flips Imperial ↔ Metric the stored ss_* values are converted
# in-place so number_input widgets show correct numbers without manual re-entry.
# Keys that hold weight/lean-mass values (lb ↔ kg):
_SS_WT_KEYS   = ["ss_weight_lb", "ss_lean_mass"]
# Keys that hold circumference values (in ↔ cm):
_SS_CIRC_KEYS = ["ss_neck", "ss_shoulders", "ss_chest", "ss_waist", "ss_hips",
                 "ss_bicep_l", "ss_bicep_r", "ss_thigh_l", "ss_thigh_r",
                 "ss_calf_l", "ss_calf_r"]
_UNIT_METRIC  = "Metric (kg / cm)"
_curr_unit    = st.session_state.get("unit_pref",       "Imperial (lb / in)")
_prev_unit    = st.session_state.get("_prev_unit_pref", "Imperial (lb / in)")
if _curr_unit != _prev_unit:
    if _curr_unit == _UNIT_METRIC:          # lb / in → kg / cm
        for _k in _SS_WT_KEYS:
            if st.session_state.get(_k):
                st.session_state[_k] = round(float(st.session_state[_k]) * 0.453592, 1)
        for _k in _SS_CIRC_KEYS:
            if st.session_state.get(_k):
                st.session_state[_k] = round(float(st.session_state[_k]) * 2.54, 1)
    else:                                   # kg / cm → lb / in
        for _k in _SS_WT_KEYS:
            if st.session_state.get(_k):
                st.session_state[_k] = round(float(st.session_state[_k]) / 0.453592, 1)
        for _k in _SS_CIRC_KEYS:
            if st.session_state.get(_k):
                st.session_state[_k] = round(float(st.session_state[_k]) / 2.54, 1)
    st.session_state["_prev_unit_pref"] = _curr_unit


# ============================================================
# DEMO PERSONAS PANEL — REMOVE BEFORE PRODUCTION LAUNCH
# Added 2026-04-18 for QA and sales demos.
# To remove: delete this block + the DEMO_PERSONAS dict + _load_demo_persona() helper.
# ============================================================

# ── InBody CSV header shared by all demo personas ────────────────────────────
_IB_HDR = (
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
    "Body Cell Mass(lb),SMI(kg/m\u00b2),Whole Body Phase Angle(\u00b0)"
)

DEMO_PERSONAS: dict = {
    # ── 1. Elite endurance athlete ─────────────────────────────────────────────
    "sofia": {
        "name": "Sofia Martínez", "age": 28, "sex": "F",
        "profile_summary": "Elite endurance athlete — full panel, all optimal. BF 18%, HDL 75, hs-CRP 0.3.",
        "values": {
            "sex": "F", "height_cm": 163.0,
            "client_name": "Sofia Martínez", "client_id": "martinez_sofia",
            "ib_csv": _IB_HDR + "\n20260418000001,270S,127.0,62.0,-,22.9,21.7,18.0,5600,88.0,6.0,6.0,46.0,12.5,12.5,1.0,1.0,12.0,4.5,4.4,-,-,-,-,-,0.72,-,-,3.0,67.7,-,-,-,1,0,0,-,-,17.0,5.2,-,-,10.6,7.8",
            "ss_weight_lb": 127.0, "ss_bf_pct": 18.0, "ss_bmi": 21.7,
            "ss_shape_score": 88, "ss_health_score": 90, "ss_body_age": 22,
            "ss_visc_rating": "Excellent",
            "ss_lean_mass": 104.1, "ss_whr": 0.75, "ss_whtr": 0.41, "ss_bmr_cal": 0,
            "ss_neck": 13.0, "ss_shoulders": 40.0, "ss_chest": 33.0, "ss_waist": 26.5, "ss_hips": 35.5,
            "ss_bicep_l": 11.0, "ss_bicep_r": 11.2, "ss_thigh_l": 20.0, "ss_thigh_r": 20.0,
            "ss_calf_l": 13.5, "ss_calf_r": 13.5,
            "lab_total_chol": 160.0, "lab_hdl": 75.0, "lab_ldl": 80.0, "lab_triglycerides": 55.0,
            "lab_glucose": 75.0, "lab_hba1c": 5.0, "lab_insulin": 4.5, "lab_hscrp": 0.3,
            "lab_sbp": 105.0, "lab_dbp": 65.0,
            "lab_ferritin": 60.0, "lab_b12": 450.0, "lab_vitamin_d": 45.0,
            "lab_tsh": 1.8, "lab_free_t3": 3.2, "lab_free_t4": 1.2,
            "lab_cortisol_am": 18.0, "lab_testosterone": 55.0,
            "lab_lpa": 12.0, "lab_apob": 65.0, "lab_homa_ir": 0.9,
            "lab_egfr": 105.0, "lab_resting_hr": 48.0,
            "life_vig": 240, "life_mod": 150, "life_sed": 5.5, "life_sleep": 8.5,
            "life_smoker": "Never", "life_alcohol": 1, "life_stress": 3, "life_health": 9,
            # Tier C — questionnaire
            "q_activity_hours_per_week": "8+ hours",
            "q_weight_trend_perception": "stable",
            "q_training_frequency_days_per_week": "5+",
            "q_family_history_heart": "no",
            "q_smoking": "never",
            "q_alcohol_drinks_per_week": "0-3",
            "q_cv_fitness_stairs_3_flights": "yes",
            "q_chest_pain_on_exertion": "no",
            "q_energy_consistency_days_per_week": "6-7",
            "q_afternoon_crashes": "never",
            "q_cold_sensitivity": "no",
            "q_libido_past_4_weeks": "strong",
            "q_mood_swings_past_4_weeks": "rarely",
            "q_thermoregulation": "no",
            "q_morning_motivation": "within_15min",
            "q_menstrual_regularity": "regular",
            "q_sleep_hours_per_night": "8+",
            "q_sleep_quality_rested_days": "almost_always",
            "q_stress_interference_past_4_weeks": "rarely",
            "q_recovery_time_after_workout": "1_2_days",
            "q_overwhelmed": "never",
            "q_training_type": "mixed",
            "q_training_intensity_1to10": 7,
            "q_daily_steps": "10000+",
            "q_nutrition_whole_food_meals": "most_75",
            "q_hydration_liters_per_day": "3+",
            "q_protein_meals_with_palm_serving": "all_3",
        },
    },
    # ── 2. Active weekend warrior ──────────────────────────────────────────────
    "carlos": {
        "name": "Carlos Reyes", "age": 35, "sex": "M",
        "profile_summary": "Active weekend warrior — full panel, mostly optimal. LDL 135 (acceptable), BF 16%.",
        "values": {
            "sex": "M", "height_cm": 178.0,
            "client_name": "Carlos Reyes", "client_id": "reyes_carlos",
            "ib_csv": _IB_HDR + "\n20260418000002,270S,183.0,90.0,-,29.3,26.2,16.0,7400,80.0,8.5,8.5,65.0,20.0,20.0,1.5,1.5,16.0,5.2,5.1,-,-,-,-,-,0.85,-,-,5.0,99.0,-,-,-,1,0,0,-,-,25.0,7.5,-,-,12.9,7.5",
            "ss_weight_lb": 183.0, "ss_bf_pct": 16.0, "ss_bmi": 26.2,
            "ss_shape_score": 79, "ss_health_score": 82, "ss_body_age": 33,
            "ss_visc_rating": "Good",
            "ss_lean_mass": 153.7, "ss_whr": 0.86, "ss_whtr": 0.49, "ss_bmr_cal": 0,
            "ss_neck": 15.5, "ss_shoulders": 48.5, "ss_chest": 42.0, "ss_waist": 34.0, "ss_hips": 39.5,
            "ss_bicep_l": 14.0, "ss_bicep_r": 14.2, "ss_thigh_l": 22.5, "ss_thigh_r": 22.5,
            "ss_calf_l": 15.0, "ss_calf_r": 15.0,
            "lab_total_chol": 205.0, "lab_hdl": 52.0, "lab_ldl": 135.0, "lab_triglycerides": 110.0,
            "lab_glucose": 88.0, "lab_hba1c": 5.4, "lab_insulin": 8.0, "lab_hscrp": 1.0,
            "lab_sbp": 118.0, "lab_dbp": 72.0,
            "lab_ferritin": 120.0, "lab_b12": 380.0, "lab_vitamin_d": 38.0,
            "lab_tsh": 2.1, "lab_free_t3": 3.0, "lab_free_t4": 1.1,
            "lab_cortisol_am": 16.0, "lab_testosterone": 620.0,
            "lab_lpa": 18.0, "lab_apob": 88.0, "lab_homa_ir": 1.8,
            "lab_egfr": 98.0, "lab_resting_hr": 62.0,
            "life_vig": 90, "life_mod": 180, "life_sed": 8.0, "life_sleep": 7.0,
            "life_smoker": "Never", "life_alcohol": 4, "life_stress": 5, "life_health": 7,
            # Tier C — questionnaire
            "q_activity_hours_per_week": "3-4 hours",
            "q_weight_trend_perception": "stable",
            "q_training_frequency_days_per_week": "3",
            "q_family_history_heart": "unknown",
            "q_smoking": "never",
            "q_alcohol_drinks_per_week": "4-7",
            "q_cv_fitness_stairs_3_flights": "yes",
            "q_chest_pain_on_exertion": "no",
            "q_energy_consistency_days_per_week": "4-5",
            "q_afternoon_crashes": "sometimes",
            "q_cold_sensitivity": "no",
            "q_libido_past_4_weeks": "moderate_lower",
            "q_mood_swings_past_4_weeks": "few_times",
            "q_thermoregulation": "no",
            "q_morning_motivation": "30_to_60min",
            "q_sleep_hours_per_night": "7-7.9",
            "q_sleep_quality_rested_days": "often",
            "q_stress_interference_past_4_weeks": "few_times",
            "q_recovery_time_after_workout": "1_2_days",
            "q_overwhelmed": "sometimes",
            "q_training_type": "mixed",
            "q_training_intensity_1to10": 7,
            "q_daily_steps": "7500-9999",
            "q_nutrition_whole_food_meals": "half",
            "q_hydration_liters_per_day": "2-3",
            "q_protein_meals_with_palm_serving": "two_of_3",
        },
        # ── Pre-stored visit history (3 visits) ─────────────────────────────
        "visits": [
            {
                "scan_label": "2026-01-15",
                "scan_date":  "2026-01-15",
                "result": {
                    "scan_date": "2026-01-15", "scan_label": "2026-01-15",
                    "overall_score": 72, "confidence": "high",
                    "lens_used": "body_comp",
                    "n_vars_provided": 28, "n_vars_total": 35,
                    "pc1": -0.8, "pc2": 0.3, "percentile_pc1": 55,
                    "categories": {
                        "body_composition":   {"score": 75, "rendering": "solid", "confidence": "high"},
                        "heart_vascular":     {"score": 68, "rendering": "solid", "confidence": "high"},
                        "metabolic_function": {"score": 74, "rendering": "solid", "confidence": "high"},
                        "hormonal_balance":   {"score": 72, "rendering": "solid", "confidence": "moderate"},
                        "stress_recovery":    {"score": 70, "rendering": "solid", "confidence": "moderate"},
                        "lifestyle_fitness":  {"score": 73, "rendering": "solid", "confidence": "high"},
                    },
                    "par_q_escalation": False, "missing_data_notes": [], "flags": [],
                    "top_drivers": [], "pc1_loadings": {}, "imputed_vars": [], "n_vars_imputed": 0,
                    "data_completeness": {"scan": True, "labs": True, "lifestyle": True, "full_data": True},
                },
                "unified": {"bf_pct": 16.8, "bmi": 26.5, "ffmi": 23.1, "ib_phase_angle": 7.3},
            },
            {
                "scan_label": "2026-02-26",
                "scan_date":  "2026-02-26",
                "result": {
                    "scan_date": "2026-02-26", "scan_label": "2026-02-26",
                    "overall_score": 76, "confidence": "high",
                    "lens_used": "body_comp",
                    "n_vars_provided": 28, "n_vars_total": 35,
                    "pc1": -0.6, "pc2": 0.2, "percentile_pc1": 58,
                    "categories": {
                        "body_composition":   {"score": 78, "rendering": "solid", "confidence": "high"},
                        "heart_vascular":     {"score": 72, "rendering": "solid", "confidence": "high"},
                        "metabolic_function": {"score": 77, "rendering": "solid", "confidence": "high"},
                        "hormonal_balance":   {"score": 74, "rendering": "solid", "confidence": "moderate"},
                        "stress_recovery":    {"score": 73, "rendering": "solid", "confidence": "moderate"},
                        "lifestyle_fitness":  {"score": 78, "rendering": "solid", "confidence": "high"},
                    },
                    "par_q_escalation": False, "missing_data_notes": [], "flags": [],
                    "top_drivers": [], "pc1_loadings": {}, "imputed_vars": [], "n_vars_imputed": 0,
                    "data_completeness": {"scan": True, "labs": True, "lifestyle": True, "full_data": True},
                },
                "unified": {"bf_pct": 15.9, "bmi": 26.1, "ffmi": 23.4, "ib_phase_angle": 7.5},
            },
        ],
    },
    # ── 3. Sedentary overweight — metabolic syndrome ───────────────────────────
    "maria": {
        "name": "María López", "age": 45, "sex": "F",
        "profile_summary": "Sedentary overweight — full panel. Metabolic syndrome: HbA1c 6.1, TG 220, HDL 38, visceral fat L13.",
        "values": {
            "sex": "F", "height_cm": 163.0,
            "client_name": "María López", "client_id": "lopez_maria",
            "ib_csv": _IB_HDR + "\n20260418000003,270S,190.0,72.0,-,64.6,32.5,34.0,7000,62.0,7.5,7.5,53.0,15.5,15.5,3.5,3.5,36.0,11.0,10.6,-,-,-,-,-,0.90,-,-,13.0,82.0,-,-,-,1,0,0,-,-,20.0,7.8,-,-,12.3,5.8",
            "ss_weight_lb": 190.0, "ss_bf_pct": 34.0, "ss_bmi": 32.5,
            "ss_shape_score": 52, "ss_health_score": 48, "ss_body_age": 58,
            "ss_visc_rating": "Poor",
            "ss_lean_mass": 125.4, "ss_whr": 0.90, "ss_whtr": 0.65, "ss_bmr_cal": 0,
            "ss_neck": 15.5, "ss_shoulders": 46.0, "ss_chest": 43.5, "ss_waist": 42.0, "ss_hips": 46.5,
            "ss_bicep_l": 14.5, "ss_bicep_r": 14.5, "ss_thigh_l": 27.5, "ss_thigh_r": 27.5,
            "ss_calf_l": 17.0, "ss_calf_r": 17.0,
            "lab_total_chol": 225.0, "lab_hdl": 38.0, "lab_ldl": 145.0, "lab_triglycerides": 220.0,
            "lab_glucose": 118.0, "lab_hba1c": 6.1, "lab_insulin": 22.0, "lab_hscrp": 4.2,
            "lab_sbp": 135.0, "lab_dbp": 85.0,
            "lab_ferritin": 85.0, "lab_b12": 320.0, "lab_vitamin_d": 22.0,
            "lab_tsh": 2.8, "lab_free_t3": 2.8, "lab_free_t4": 1.0,
            "lab_cortisol_am": 20.0, "lab_testosterone": 32.0,
            "lab_lpa": 28.0, "lab_apob": 112.0, "lab_homa_ir": 6.4,
            "lab_egfr": 82.0, "lab_resting_hr": 82.0,
            "life_vig": 0, "life_mod": 30, "life_sed": 12.0, "life_sleep": 6.0,
            "life_smoker": "Never", "life_alcohol": 3, "life_stress": 7, "life_health": 4,
            # Tier C — questionnaire
            "q_activity_hours_per_week": "1-2 hours",
            "q_weight_trend_perception": "gaining_unwanted",
            "q_training_frequency_days_per_week": "1",
            "q_family_history_heart": "yes",
            "q_smoking": "never",
            "q_alcohol_drinks_per_week": "0-3",
            "q_cv_fitness_stairs_3_flights": "with_difficulty",
            "q_chest_pain_on_exertion": "no",
            "q_energy_consistency_days_per_week": "2-3",
            "q_afternoon_crashes": "often",
            "q_cold_sensitivity": "sometimes",
            "q_libido_past_4_weeks": "low_reduced",
            "q_mood_swings_past_4_weeks": "several_per_week",
            "q_thermoregulation": "occasionally",
            "q_morning_motivation": "over_hour",
            "q_menstrual_regularity": "irregular",
            "q_sleep_hours_per_night": "6-6.9",
            "q_sleep_quality_rested_days": "sometimes",
            "q_stress_interference_past_4_weeks": "several_per_week",
            "q_recovery_time_after_workout": "3_plus_days",
            "q_overwhelmed": "often",
            "q_training_type": "cardio",
            "q_training_intensity_1to10": 4,
            "q_daily_steps": "3000-4999",
            "q_nutrition_whole_food_meals": "half",
            "q_hydration_liters_per_day": "1-2",
            "q_protein_meals_with_palm_serving": "one_of_3",
        },
        # ── Pre-stored visit history (2 visits — improvement in progress) ────
        "visits": [
            {
                "scan_label": "2025-12-10",
                "scan_date":  "2025-12-10",
                "result": {
                    "scan_date": "2025-12-10", "scan_label": "2025-12-10",
                    "overall_score": 58, "confidence": "high",
                    "lens_used": "body_comp",
                    "n_vars_provided": 30, "n_vars_total": 35,
                    "pc1": 1.4, "pc2": -0.4, "percentile_pc1": 22,
                    "categories": {
                        "body_composition":   {"score": 52, "rendering": "solid", "confidence": "high"},
                        "heart_vascular":     {"score": 55, "rendering": "solid", "confidence": "high"},
                        "metabolic_function": {"score": 48, "rendering": "solid", "confidence": "high"},
                        "hormonal_balance":   {"score": 60, "rendering": "solid", "confidence": "moderate"},
                        "stress_recovery":    {"score": 55, "rendering": "solid", "confidence": "moderate"},
                        "lifestyle_fitness":  {"score": 66, "rendering": "solid", "confidence": "high"},
                    },
                    "par_q_escalation": False, "missing_data_notes": [], "flags": [],
                    "top_drivers": [], "pc1_loadings": {}, "imputed_vars": [], "n_vars_imputed": 0,
                    "data_completeness": {"scan": True, "labs": True, "lifestyle": True, "full_data": True},
                },
                "unified": {"bf_pct": 35.5, "bmi": 33.2, "ffmi": 16.8, "ib_phase_angle": 5.6},
            },
            {
                "scan_label": "2026-02-20",
                "scan_date":  "2026-02-20",
                "result": {
                    "scan_date": "2026-02-20", "scan_label": "2026-02-20",
                    "overall_score": 62, "confidence": "high",
                    "lens_used": "body_comp",
                    "n_vars_provided": 30, "n_vars_total": 35,
                    "pc1": 1.1, "pc2": -0.3, "percentile_pc1": 26,
                    "categories": {
                        "body_composition":   {"score": 57, "rendering": "solid", "confidence": "high"},
                        "heart_vascular":     {"score": 59, "rendering": "solid", "confidence": "high"},
                        "metabolic_function": {"score": 52, "rendering": "solid", "confidence": "high"},
                        "hormonal_balance":   {"score": 63, "rendering": "solid", "confidence": "moderate"},
                        "stress_recovery":    {"score": 59, "rendering": "solid", "confidence": "moderate"},
                        "lifestyle_fitness":  {"score": 70, "rendering": "solid", "confidence": "high"},
                    },
                    "par_q_escalation": False, "missing_data_notes": [], "flags": [],
                    "top_drivers": [], "pc1_loadings": {}, "imputed_vars": [], "n_vars_imputed": 0,
                    "data_completeness": {"scan": True, "labs": True, "lifestyle": True, "full_data": True},
                },
                "unified": {"bf_pct": 33.8, "bmi": 32.1, "ffmi": 17.2, "ib_phase_angle": 5.9},
            },
        ],
    },
    # ── 4. Stressed executive — partial panel (lipids + glucose only) ──────────
    "roberto": {
        "name": "Roberto Gómez", "age": 52, "sex": "M",
        "profile_summary": "Stressed executive — PARTIAL: lipids + glucose only. LDL 165, TG 180, HbA1c 5.8. Insulin/CRP/BP unset.",
        "values": {
            "sex": "M", "height_cm": 176.0,
            "client_name": "Roberto Gómez", "client_id": "gomez_roberto",
            "ib_csv": _IB_HDR + "\n20260418000004,270S,195.0,84.0,-,46.8,28.6,24.0,7800,72.0,8.0,8.0,62.5,18.0,18.0,2.5,2.5,26.0,8.0,7.8,-,-,-,-,-,0.92,-,-,9.0,93.0,-,-,-,1,0,0,-,-,24.0,7.9,-,-,12.3,6.8",
            "ss_weight_lb": 195.0, "ss_bf_pct": 24.0, "ss_bmi": 28.6,
            "ss_shape_score": 65, "ss_health_score": 62, "ss_body_age": 60,
            "ss_visc_rating": "Fair",
            "ss_lean_mass": 148.2, "ss_whr": 0.93, "ss_whtr": 0.56, "ss_bmr_cal": 0,
            "ss_neck": 16.5, "ss_shoulders": 50.0, "ss_chest": 44.5, "ss_waist": 39.0, "ss_hips": 42.0,
            "ss_bicep_l": 13.5, "ss_bicep_r": 13.5, "ss_thigh_l": 22.0, "ss_thigh_r": 22.0,
            "ss_calf_l": 15.0, "ss_calf_r": 15.0,
            "lab_total_chol": 245.0, "lab_hdl": 42.0, "lab_ldl": 165.0, "lab_triglycerides": 180.0,
            "lab_glucose": 108.0, "lab_hba1c": 5.8, "lab_insulin": 0.0, "lab_hscrp": 0.0,
            "lab_sbp": 0.0, "lab_dbp": 0.0,
            "lab_ferritin": 0.0, "lab_b12": 0.0, "lab_vitamin_d": 0.0,
            "lab_tsh": 0.0, "lab_free_t3": 0.0, "lab_free_t4": 0.0,
            "lab_cortisol_am": 28.0, "lab_testosterone": 0.0,
            "lab_lpa": 0.0, "lab_apob": 0.0, "lab_homa_ir": 0.0,
            "lab_egfr": 0.0, "lab_resting_hr": 0.0,
            "life_vig": 20, "life_mod": 60, "life_sed": 10.5, "life_sleep": 6.5,
            "life_smoker": "Never", "life_alcohol": 8, "life_stress": 8, "life_health": 5,
            # Tier C — questionnaire
            "q_activity_hours_per_week": "1-2 hours",
            "q_weight_trend_perception": "gaining_unwanted",
            "q_training_frequency_days_per_week": "2",
            "q_family_history_heart": "yes",
            "q_smoking": "never",
            "q_alcohol_drinks_per_week": "8-14",
            "q_cv_fitness_stairs_3_flights": "with_difficulty",
            "q_chest_pain_on_exertion": "no",
            "q_energy_consistency_days_per_week": "2-3",
            "q_afternoon_crashes": "often",
            "q_cold_sensitivity": "no",
            "q_libido_past_4_weeks": "low_reduced",
            "q_mood_swings_past_4_weeks": "few_times",
            "q_thermoregulation": "no",
            "q_morning_motivation": "30_to_60min",
            "q_sleep_hours_per_night": "6-6.9",
            "q_sleep_quality_rested_days": "sometimes",
            "q_stress_interference_past_4_weeks": "most_days",
            "q_recovery_time_after_workout": "3_plus_days",
            "q_overwhelmed": "often",
            "q_training_type": "none",
            "q_training_intensity_1to10": 3,
            "q_daily_steps": "5000-7499",
            "q_nutrition_whole_food_meals": "less_half",
            "q_hydration_liters_per_day": "1-2",
            "q_protein_meals_with_palm_serving": "one_of_3",
        },
    },
    # ── 5. Postpartum — partial (ferritin/B12/vitD not in form) ───────────────
    "luz": {
        "name": "Luz Hernández", "age": 38, "sex": "F",
        "profile_summary": "Postpartum — PARTIAL: ferritin 18, B12 210, vit D 18 (deficient; not in form). TSH/thyroid unset. Everything else acceptable.",
        "values": {
            "sex": "F", "height_cm": 165.0,
            "client_name": "Luz Hernández", "client_id": "hernandez_luz",
            "ib_csv": _IB_HDR + "\n20260418000005,270S,145.0,62.0,-,39.2,24.2,27.0,5900,74.0,6.3,6.3,46.5,13.2,13.2,2.2,2.2,21.5,7.0,6.8,-,-,-,-,-,0.80,-,-,6.0,75.5,-,-,-,1,0,0,-,-,17.5,5.9,-,-,10.6,6.8",
            "ss_weight_lb": 145.0, "ss_bf_pct": 27.0, "ss_bmi": 24.2,
            "ss_shape_score": 71, "ss_health_score": 68, "ss_body_age": 38,
            "ss_visc_rating": "Good",
            "ss_lean_mass": 105.9, "ss_whr": 0.79, "ss_whtr": 0.49, "ss_bmr_cal": 0,
            "ss_neck": 13.5, "ss_shoulders": 42.0, "ss_chest": 36.5, "ss_waist": 32.0, "ss_hips": 40.5,
            "ss_bicep_l": 11.5, "ss_bicep_r": 11.5, "ss_thigh_l": 23.5, "ss_thigh_r": 23.5,
            "ss_calf_l": 14.5, "ss_calf_r": 14.5,
            "lab_total_chol": 185.0, "lab_hdl": 55.0, "lab_ldl": 110.0, "lab_triglycerides": 100.0,
            "lab_glucose": 82.0, "lab_hba1c": 5.2, "lab_insulin": 7.0, "lab_hscrp": 1.2,
            "lab_sbp": 112.0, "lab_dbp": 70.0,
            "lab_ferritin": 18.0, "lab_b12": 210.0, "lab_vitamin_d": 18.0,
            "lab_tsh": 0.0, "lab_free_t3": 0.0, "lab_free_t4": 0.0,
            "lab_cortisol_am": 0.0, "lab_testosterone": 0.0,
            "lab_lpa": 0.0, "lab_apob": 0.0, "lab_homa_ir": 0.0,
            "lab_egfr": 0.0, "lab_resting_hr": 72.0,
            "life_vig": 60, "life_mod": 120, "life_sed": 7.5, "life_sleep": 6.5,
            "life_smoker": "Never", "life_alcohol": 1, "life_stress": 6, "life_health": 6,
            # Tier C — questionnaire
            "q_activity_hours_per_week": "3-4 hours",
            "q_weight_trend_perception": "stable",
            "q_training_frequency_days_per_week": "3",
            "q_family_history_heart": "no",
            "q_smoking": "never",
            "q_alcohol_drinks_per_week": "0-3",
            "q_cv_fitness_stairs_3_flights": "yes",
            "q_chest_pain_on_exertion": "no",
            "q_energy_consistency_days_per_week": "4-5",
            "q_afternoon_crashes": "often",
            "q_cold_sensitivity": "yes",
            "q_libido_past_4_weeks": "low_reduced",
            "q_mood_swings_past_4_weeks": "few_times",
            "q_thermoregulation": "occasionally",
            "q_morning_motivation": "30_to_60min",
            "q_menstrual_regularity": "irregular",
            "q_sleep_hours_per_night": "6-6.9",
            "q_sleep_quality_rested_days": "sometimes",
            "q_stress_interference_past_4_weeks": "few_times",
            "q_recovery_time_after_workout": "1_2_days",
            "q_overwhelmed": "sometimes",
            "q_training_type": "mixed",
            "q_training_intensity_1to10": 6,
            "q_daily_steps": "7500-9999",
            "q_nutrition_whole_food_meals": "most_75",
            "q_hydration_liters_per_day": "2-3",
            "q_protein_meals_with_palm_serving": "two_of_3",
        },
    },
    # ── 6. College athlete — partial (no advanced lipids / hormones) ───────────
    "diego": {
        "name": "Diego Torres", "age": 22, "sex": "M",
        "profile_summary": "College athlete — PARTIAL: basic metabolic + body comp. BF 10%, InBody 91. Lp(a)/ApoB/hormones unset.",
        "values": {
            "sex": "M", "height_cm": 180.0,
            "client_name": "Diego Torres", "client_id": "torres_diego",
            "ib_csv": _IB_HDR + "\n20260418000006,270S,170.0,97.0,-,17.0,23.8,10.0,7200,91.0,9.8,9.8,72.0,22.0,22.0,0.8,0.8,8.5,3.5,3.4,-,-,-,-,-,0.82,-,-,2.0,97.5,-,-,-,1,0,0,-,-,27.5,6.9,-,-,13.6,8.5",
            "ss_weight_lb": 170.0, "ss_bf_pct": 10.0, "ss_bmi": 23.8,
            "ss_shape_score": 91, "ss_health_score": 93, "ss_body_age": 19,
            "ss_visc_rating": "Excellent",
            "ss_lean_mass": 153.0, "ss_whr": 0.82, "ss_whtr": 0.43, "ss_bmr_cal": 0,
            "ss_neck": 15.0, "ss_shoulders": 48.0, "ss_chest": 41.5, "ss_waist": 30.5, "ss_hips": 37.0,
            "ss_bicep_l": 14.5, "ss_bicep_r": 14.8, "ss_thigh_l": 24.5, "ss_thigh_r": 24.5,
            "ss_calf_l": 15.5, "ss_calf_r": 15.5,
            "lab_total_chol": 175.0, "lab_hdl": 60.0, "lab_ldl": 100.0, "lab_triglycerides": 70.0,
            "lab_glucose": 82.0, "lab_hba1c": 5.0, "lab_insulin": 5.0, "lab_hscrp": 0.4,
            "lab_sbp": 108.0, "lab_dbp": 65.0,
            "lab_ferritin": 95.0, "lab_b12": 420.0, "lab_vitamin_d": 42.0,
            "lab_tsh": 1.6, "lab_free_t3": 3.4, "lab_free_t4": 1.3,
            "lab_cortisol_am": 0.0, "lab_testosterone": 780.0,
            "lab_lpa": 0.0, "lab_apob": 0.0, "lab_homa_ir": 0.9,
            "lab_egfr": 115.0, "lab_resting_hr": 44.0,
            "life_vig": 300, "life_mod": 200, "life_sed": 5.0, "life_sleep": 8.0,
            "life_smoker": "Never", "life_alcohol": 3, "life_stress": 4, "life_health": 9,
            # Tier C — questionnaire
            "q_activity_hours_per_week": "8+ hours",
            "q_weight_trend_perception": "stable",
            "q_training_frequency_days_per_week": "5+",
            "q_family_history_heart": "no",
            "q_smoking": "never",
            "q_alcohol_drinks_per_week": "0-3",
            "q_cv_fitness_stairs_3_flights": "yes",
            "q_chest_pain_on_exertion": "no",
            "q_energy_consistency_days_per_week": "6-7",
            "q_afternoon_crashes": "never",
            "q_cold_sensitivity": "no",
            "q_libido_past_4_weeks": "strong",
            "q_mood_swings_past_4_weeks": "rarely",
            "q_thermoregulation": "no",
            "q_morning_motivation": "within_15min",
            "q_sleep_hours_per_night": "8+",
            "q_sleep_quality_rested_days": "almost_always",
            "q_stress_interference_past_4_weeks": "rarely",
            "q_recovery_time_after_workout": "1_2_days",
            "q_overwhelmed": "sometimes",
            "q_training_type": "mixed",
            "q_training_intensity_1to10": 8,
            "q_daily_steps": "10000+",
            "q_nutrition_whole_food_meals": "half",
            "q_hydration_liters_per_day": "2-3",
            "q_protein_meals_with_palm_serving": "two_of_3",
        },
    },
    # ── 7. Post-menopausal active — familial high cholesterol ─────────────────
    "elena": {
        "name": "Elena Ruiz", "age": 60, "sex": "F",
        "profile_summary": "Post-menopausal active — full panel. Familial hypercholesterolemia: LDL 180, TC 270. But metabolic profile clean.",
        "values": {
            "sex": "F", "height_cm": 162.0,
            "client_name": "Elena Ruiz", "client_id": "ruiz_elena",
            "ib_csv": _IB_HDR + "\n20260418000007,270S,155.0,70.0,-,43.4,26.8,28.0,6000,76.0,6.5,6.5,52.0,14.0,14.0,2.0,2.0,24.0,7.5,7.4,-,-,-,-,-,0.80,-,-,7.0,80.0,-,-,-,1,0,0,-,-,19.5,6.3,-,-,12.1,6.5",
            "ss_weight_lb": 155.0, "ss_bf_pct": 28.0, "ss_bmi": 26.8,
            "ss_shape_score": 75, "ss_health_score": 72, "ss_body_age": 58,
            "ss_visc_rating": "Good",
            "ss_lean_mass": 111.6, "ss_whr": 0.83, "ss_whtr": 0.53, "ss_bmr_cal": 0,
            "ss_neck": 13.5, "ss_shoulders": 43.0, "ss_chest": 38.5, "ss_waist": 34.0, "ss_hips": 41.0,
            "ss_bicep_l": 12.0, "ss_bicep_r": 12.0, "ss_thigh_l": 23.0, "ss_thigh_r": 23.0,
            "ss_calf_l": 14.0, "ss_calf_r": 14.0,
            "lab_total_chol": 270.0, "lab_hdl": 65.0, "lab_ldl": 180.0, "lab_triglycerides": 90.0,
            "lab_glucose": 88.0, "lab_hba1c": 5.3, "lab_insulin": 6.5, "lab_hscrp": 0.8,
            "lab_sbp": 122.0, "lab_dbp": 74.0,
            "lab_ferritin": 55.0, "lab_b12": 310.0, "lab_vitamin_d": 35.0,
            "lab_tsh": 3.2, "lab_free_t3": 2.8, "lab_free_t4": 1.0,
            "lab_cortisol_am": 14.0, "lab_testosterone": 22.0,
            "lab_lpa": 55.0, "lab_apob": 118.0, "lab_homa_ir": 1.4,
            "lab_egfr": 72.0, "lab_resting_hr": 68.0,
            "life_vig": 80, "life_mod": 150, "life_sed": 7.0, "life_sleep": 7.5,
            "life_smoker": "Never", "life_alcohol": 2, "life_stress": 4, "life_health": 7,
            # Tier C — questionnaire
            "q_activity_hours_per_week": "3-4 hours",
            "q_weight_trend_perception": "stable",
            "q_training_frequency_days_per_week": "4",
            "q_family_history_heart": "yes",
            "q_smoking": "never",
            "q_alcohol_drinks_per_week": "0-3",
            "q_cv_fitness_stairs_3_flights": "yes",
            "q_chest_pain_on_exertion": "no",
            "q_energy_consistency_days_per_week": "6-7",
            "q_afternoon_crashes": "sometimes",
            "q_cold_sensitivity": "sometimes",
            "q_libido_past_4_weeks": "moderate_lower",
            "q_mood_swings_past_4_weeks": "few_times",
            "q_thermoregulation": "frequently",
            "q_morning_motivation": "within_15min",
            "q_menstrual_regularity": "NA_menopausal",
            "q_sleep_hours_per_night": "7-7.9",
            "q_sleep_quality_rested_days": "often",
            "q_stress_interference_past_4_weeks": "rarely",
            "q_recovery_time_after_workout": "1_2_days",
            "q_overwhelmed": "sometimes",
            "q_training_type": "mixed",
            "q_training_intensity_1to10": 6,
            "q_daily_steps": "7500-9999",
            "q_nutrition_whole_food_meals": "most_75",
            "q_hydration_liters_per_day": "2-3",
            "q_protein_meals_with_palm_serving": "two_of_3",
        },
    },
    # ── 8. Hidden CV risk — normal LDL but high Lp(a) / ApoB / CRP ────────────
    "javier": {
        "name": "Javier Morales", "age": 48, "sex": "M",
        "profile_summary": "Hidden CV risk — full panel. Normal LDL 125 but hs-CRP 3.5. Lp(a) 110 / ApoB 125 not in form.",
        "values": {
            "sex": "M", "height_cm": 175.0,
            "client_name": "Javier Morales", "client_id": "morales_javier",
            "ib_csv": _IB_HDR + "\n20260418000008,270S,185.0,87.0,-,40.7,27.4,22.0,7500,75.0,8.3,8.3,65.0,19.0,19.0,2.0,2.0,22.5,7.1,7.0,-,-,-,-,-,0.88,-,-,8.0,95.0,-,-,-,1,0,0,-,-,23.5,7.6,-,-,12.9,6.8",
            "ss_weight_lb": 185.0, "ss_bf_pct": 22.0, "ss_bmi": 27.4,
            "ss_shape_score": 73, "ss_health_score": 70, "ss_body_age": 52,
            "ss_visc_rating": "Fair",
            "ss_lean_mass": 144.3, "ss_whr": 0.91, "ss_whtr": 0.54, "ss_bmr_cal": 0,
            "ss_neck": 16.0, "ss_shoulders": 49.5, "ss_chest": 44.0, "ss_waist": 37.5, "ss_hips": 41.0,
            "ss_bicep_l": 13.8, "ss_bicep_r": 14.0, "ss_thigh_l": 23.0, "ss_thigh_r": 23.0,
            "ss_calf_l": 15.5, "ss_calf_r": 15.5,
            "lab_total_chol": 210.0, "lab_hdl": 48.0, "lab_ldl": 125.0, "lab_triglycerides": 120.0,
            "lab_glucose": 95.0, "lab_hba1c": 5.5, "lab_insulin": 10.0, "lab_hscrp": 3.5,
            "lab_sbp": 125.0, "lab_dbp": 80.0,
            "lab_ferritin": 180.0, "lab_b12": 290.0, "lab_vitamin_d": 28.0,
            "lab_tsh": 2.4, "lab_free_t3": 2.9, "lab_free_t4": 1.1,
            "lab_cortisol_am": 18.0, "lab_testosterone": 480.0,
            "lab_lpa": 110.0, "lab_apob": 125.0, "lab_homa_ir": 2.2,
            "lab_egfr": 88.0, "lab_resting_hr": 72.0,
            "life_vig": 60, "life_mod": 120, "life_sed": 9.0, "life_sleep": 7.0,
            "life_smoker": "Never", "life_alcohol": 5, "life_stress": 6, "life_health": 6,
            # Tier C — questionnaire
            "q_activity_hours_per_week": "3-4 hours",
            "q_weight_trend_perception": "stable",
            "q_training_frequency_days_per_week": "3",
            "q_family_history_heart": "yes",
            "q_smoking": "never",
            "q_alcohol_drinks_per_week": "4-7",
            "q_cv_fitness_stairs_3_flights": "yes",
            "q_chest_pain_on_exertion": "no",
            "q_energy_consistency_days_per_week": "4-5",
            "q_afternoon_crashes": "sometimes",
            "q_cold_sensitivity": "no",
            "q_libido_past_4_weeks": "moderate_lower",
            "q_mood_swings_past_4_weeks": "few_times",
            "q_thermoregulation": "no",
            "q_morning_motivation": "30_to_60min",
            "q_sleep_hours_per_night": "7-7.9",
            "q_sleep_quality_rested_days": "often",
            "q_stress_interference_past_4_weeks": "few_times",
            "q_recovery_time_after_workout": "1_2_days",
            "q_overwhelmed": "sometimes",
            "q_training_type": "cardio",
            "q_training_intensity_1to10": 6,
            "q_daily_steps": "7500-9999",
            "q_nutrition_whole_food_meals": "half",
            "q_hydration_liters_per_day": "2-3",
            "q_protein_meals_with_palm_serving": "one_of_3",
        },
    },
    # ── 9. Endurance overtraining ──────────────────────────────────────────────
    "patricia": {
        "name": "Patricia Vega", "age": 40, "sex": "F",
        "profile_summary": "Endurance overtraining — full panel. Classic OTS: vig 380/wk, cortisol suppressed, ferritin 14 (not in form). HDL 72, TG 50.",
        "values": {
            "sex": "F", "height_cm": 165.0,
            "client_name": "Patricia Vega", "client_id": "vega_patricia",
            "ib_csv": _IB_HDR + "\n20260418000009,270S,132.0,65.0,-,25.1,22.0,19.0,5700,83.0,6.4,6.4,48.0,13.6,13.6,1.2,1.2,14.0,4.7,4.7,-,-,-,-,-,0.73,-,-,4.0,72.0,-,-,-,1,0,0,-,-,18.5,5.4,-,-,10.8,7.2",
            "ss_weight_lb": 132.0, "ss_bf_pct": 19.0, "ss_bmi": 22.0,
            "ss_shape_score": 84, "ss_health_score": 80, "ss_body_age": 38,
            "ss_visc_rating": "Excellent",
            "ss_lean_mass": 106.9, "ss_whr": 0.75, "ss_whtr": 0.42, "ss_bmr_cal": 0,
            "ss_neck": 13.0, "ss_shoulders": 41.0, "ss_chest": 34.0, "ss_waist": 27.5, "ss_hips": 36.5,
            "ss_bicep_l": 11.5, "ss_bicep_r": 11.5, "ss_thigh_l": 21.5, "ss_thigh_r": 21.5,
            "ss_calf_l": 14.0, "ss_calf_r": 14.0,
            "lab_total_chol": 165.0, "lab_hdl": 72.0, "lab_ldl": 88.0, "lab_triglycerides": 50.0,
            "lab_glucose": 72.0, "lab_hba1c": 4.9, "lab_insulin": 3.5, "lab_hscrp": 0.7,
            "lab_sbp": 100.0, "lab_dbp": 60.0,
            "lab_ferritin": 14.0, "lab_b12": 380.0, "lab_vitamin_d": 32.0,
            "lab_tsh": 1.4, "lab_free_t3": 2.1, "lab_free_t4": 0.8,
            "lab_cortisol_am": 8.0, "lab_testosterone": 28.0,
            "lab_lpa": 8.0, "lab_apob": 58.0, "lab_homa_ir": 0.7,
            "lab_egfr": 102.0, "lab_resting_hr": 42.0,
            "life_vig": 380, "life_mod": 120, "life_sed": 6.5, "life_sleep": 7.0,
            "life_smoker": "Never", "life_alcohol": 0, "life_stress": 7, "life_health": 6,
            # Tier C — questionnaire (overtraining syndrome pattern)
            "q_activity_hours_per_week": "8+ hours",
            "q_weight_trend_perception": "stable",
            "q_training_frequency_days_per_week": "5+",
            "q_family_history_heart": "no",
            "q_smoking": "never",
            "q_alcohol_drinks_per_week": "0-3",
            "q_cv_fitness_stairs_3_flights": "yes",
            "q_chest_pain_on_exertion": "no",
            "q_energy_consistency_days_per_week": "2-3",
            "q_afternoon_crashes": "often",
            "q_cold_sensitivity": "yes",
            "q_libido_past_4_weeks": "low_reduced",
            "q_mood_swings_past_4_weeks": "several_per_week",
            "q_thermoregulation": "occasionally",
            "q_morning_motivation": "over_hour",
            "q_menstrual_regularity": "irregular",
            "q_sleep_hours_per_night": "7-7.9",
            "q_sleep_quality_rested_days": "sometimes",
            "q_stress_interference_past_4_weeks": "few_times",
            "q_recovery_time_after_workout": "3_plus_days",
            "q_overwhelmed": "sometimes",
            "q_training_type": "cardio",
            "q_training_intensity_1to10": 9,
            "q_daily_steps": "10000+",
            "q_nutrition_whole_food_meals": "most_75",
            "q_hydration_liters_per_day": "2-3",
            "q_protein_meals_with_palm_serving": "two_of_3",
        },
    },
    # ── 10. Pre-diabetic sedentary ─────────────────────────────────────────────
    "miguel": {
        "name": "Miguel Sandoval", "age": 55, "sex": "M",
        "profile_summary": "Pre-diabetic sedentary — full panel. HbA1c 5.9, SBP 142, TG 195, HDL 36, visceral fat L14.",
        "values": {
            "sex": "M", "height_cm": 173.0,
            "client_name": "Miguel Sandoval", "client_id": "sandoval_miguel",
            "ib_csv": _IB_HDR + "\n20260418000010,270S,218.0,85.0,-,69.8,33.1,32.0,7800,63.0,8.5,8.5,63.0,17.5,17.5,3.8,3.8,38.5,12.0,11.7,-,-,-,-,-,0.98,-,-,14.0,95.0,-,-,-,1,0,0,-,-,23.5,8.9,-,-,12.9,5.9",
            "ss_weight_lb": 218.0, "ss_bf_pct": 32.0, "ss_bmi": 33.1,
            "ss_shape_score": 48, "ss_health_score": 45, "ss_body_age": 65,
            "ss_visc_rating": "Very Poor",
            "ss_lean_mass": 148.2, "ss_whr": 0.97, "ss_whtr": 0.65, "ss_bmr_cal": 0,
            "ss_neck": 17.5, "ss_shoulders": 52.0, "ss_chest": 47.5, "ss_waist": 44.5, "ss_hips": 46.0,
            "ss_bicep_l": 15.0, "ss_bicep_r": 15.0, "ss_thigh_l": 26.0, "ss_thigh_r": 26.0,
            "ss_calf_l": 17.5, "ss_calf_r": 17.5,
            "lab_total_chol": 230.0, "lab_hdl": 36.0, "lab_ldl": 155.0, "lab_triglycerides": 195.0,
            "lab_glucose": 115.0, "lab_hba1c": 5.9, "lab_insulin": 20.0, "lab_hscrp": 3.2,
            "lab_sbp": 142.0, "lab_dbp": 90.0,
            "lab_ferritin": 210.0, "lab_b12": 255.0, "lab_vitamin_d": 20.0,
            "lab_tsh": 2.6, "lab_free_t3": 2.7, "lab_free_t4": 1.0,
            "lab_cortisol_am": 22.0, "lab_testosterone": 320.0,
            "lab_lpa": 32.0, "lab_apob": 128.0, "lab_homa_ir": 5.6,
            "lab_egfr": 68.0, "lab_resting_hr": 78.0,
            "life_vig": 0, "life_mod": 40, "life_sed": 13.0, "life_sleep": 6.0,
            "life_smoker": "Former", "life_alcohol": 5, "life_stress": 7, "life_health": 4,
            # Tier C — questionnaire (pre-diabetic sedentary pattern)
            "q_activity_hours_per_week": "0 hours",
            "q_weight_trend_perception": "gaining_unwanted",
            "q_training_frequency_days_per_week": "0",
            "q_family_history_heart": "yes",
            "q_smoking": "former_5plus",
            "q_alcohol_drinks_per_week": "4-7",
            "q_cv_fitness_stairs_3_flights": "no",
            "q_chest_pain_on_exertion": "no",
            "q_energy_consistency_days_per_week": "0-1",
            "q_afternoon_crashes": "daily",
            "q_cold_sensitivity": "no",
            "q_libido_past_4_weeks": "very_low",
            "q_mood_swings_past_4_weeks": "few_times",
            "q_thermoregulation": "no",
            "q_morning_motivation": "over_hour",
            "q_sleep_hours_per_night": "6-6.9",
            "q_sleep_quality_rested_days": "rarely",
            "q_stress_interference_past_4_weeks": "several_per_week",
            "q_recovery_time_after_workout": "rarely_recovered",
            "q_overwhelmed": "often",
            "q_training_type": "none",
            "q_training_intensity_1to10": 2,
            "q_daily_steps": "<3000",
            "q_nutrition_whole_food_meals": "less_half",
            "q_hydration_liters_per_day": "<1",
            "q_protein_meals_with_palm_serving": "rarely",
        },
    },
    # ── 11. Vegan active — partial (micronutrient gaps not in form) ────────────
    "andrea": {
        "name": "Andrea Cruz", "age": 32, "sex": "F",
        "profile_summary": "Vegan active — PARTIAL: B12 180, ferritin 22, vit D 20 (deficient; not in form). Hormones unset. Otherwise optimal.",
        "values": {
            "sex": "F", "height_cm": 168.0,
            "client_name": "Andrea Cruz", "client_id": "cruz_andrea",
            "ib_csv": _IB_HDR + "\n20260418000011,270S,138.0,64.0,-,30.4,22.2,22.0,5800,81.0,6.2,6.2,48.5,13.4,13.4,1.6,1.6,16.5,5.6,5.1,-,-,-,-,-,0.75,-,-,4.0,73.5,-,-,-,1,0,0,-,-,18.0,5.6,-,-,10.3,7.0",
            "ss_weight_lb": 138.0, "ss_bf_pct": 22.0, "ss_bmi": 22.2,
            "ss_shape_score": 81, "ss_health_score": 78, "ss_body_age": 30,
            "ss_visc_rating": "Excellent",
            "ss_lean_mass": 107.6, "ss_whr": 0.76, "ss_whtr": 0.44, "ss_bmr_cal": 0,
            "ss_neck": 13.0, "ss_shoulders": 41.5, "ss_chest": 34.5, "ss_waist": 29.0, "ss_hips": 38.0,
            "ss_bicep_l": 11.0, "ss_bicep_r": 11.0, "ss_thigh_l": 22.0, "ss_thigh_r": 22.0,
            "ss_calf_l": 14.0, "ss_calf_r": 14.0,
            "lab_total_chol": 170.0, "lab_hdl": 62.0, "lab_ldl": 95.0, "lab_triglycerides": 75.0,
            "lab_glucose": 80.0, "lab_hba1c": 5.1, "lab_insulin": 5.5, "lab_hscrp": 0.6,
            "lab_sbp": 110.0, "lab_dbp": 68.0,
            "lab_ferritin": 22.0, "lab_b12": 180.0, "lab_vitamin_d": 20.0,
            "lab_tsh": 0.0, "lab_free_t3": 0.0, "lab_free_t4": 0.0,
            "lab_cortisol_am": 0.0, "lab_testosterone": 0.0,
            "lab_lpa": 0.0, "lab_apob": 0.0, "lab_homa_ir": 1.1,
            "lab_egfr": 98.0, "lab_resting_hr": 58.0,
            "life_vig": 160, "life_mod": 200, "life_sed": 6.0, "life_sleep": 8.0,
            "life_smoker": "Never", "life_alcohol": 0, "life_stress": 4, "life_health": 8,
            # Tier C — questionnaire (vegan active, micronutrient gap pattern)
            "q_activity_hours_per_week": "5-7 hours",
            "q_weight_trend_perception": "stable",
            "q_training_frequency_days_per_week": "4",
            "q_family_history_heart": "no",
            "q_smoking": "never",
            "q_alcohol_drinks_per_week": "0-3",
            "q_cv_fitness_stairs_3_flights": "yes",
            "q_chest_pain_on_exertion": "no",
            "q_energy_consistency_days_per_week": "4-5",
            "q_afternoon_crashes": "sometimes",
            "q_cold_sensitivity": "yes",
            "q_libido_past_4_weeks": "moderate_lower",
            "q_mood_swings_past_4_weeks": "few_times",
            "q_thermoregulation": "occasionally",
            "q_morning_motivation": "30_to_60min",
            "q_menstrual_regularity": "regular",
            "q_sleep_hours_per_night": "8+",
            "q_sleep_quality_rested_days": "often",
            "q_stress_interference_past_4_weeks": "rarely",
            "q_recovery_time_after_workout": "1_2_days",
            "q_overwhelmed": "sometimes",
            "q_training_type": "mixed",
            "q_training_intensity_1to10": 7,
            "q_daily_steps": "7500-9999",
            "q_nutrition_whole_food_meals": "all",
            "q_hydration_liters_per_day": "2-3",
            "q_protein_meals_with_palm_serving": "one_of_3",
        },
    },
    # ── 12. Well-managed CVD — on statin ──────────────────────────────────────
    "fernando": {
        "name": "Fernando Aguilar", "age": 65, "sex": "M",
        "profile_summary": "Well-managed CVD, on statin — full panel. LDL 85 (controlled), but eGFR 75 (not in form). SBP 128.",
        "values": {
            "sex": "M", "height_cm": 170.0,
            "client_name": "Fernando Aguilar", "client_id": "aguilar_fernando",
            "ib_csv": _IB_HDR + "\n20260418000012,270S,180.0,80.0,-,46.8,28.2,26.0,7000,71.0,7.8,7.8,60.0,17.0,17.0,2.5,2.5,26.0,8.0,7.8,-,-,-,-,-,0.89,-,-,8.0,90.5,-,-,-,1,0,0,-,-,22.5,7.4,-,-,12.6,6.2",
            "ss_weight_lb": 180.0, "ss_bf_pct": 26.0, "ss_bmi": 28.2,
            "ss_shape_score": 68, "ss_health_score": 70, "ss_body_age": 68,
            "ss_visc_rating": "Fair",
            "ss_lean_mass": 133.2, "ss_whr": 0.92, "ss_whtr": 0.58, "ss_bmr_cal": 0,
            "ss_neck": 15.5, "ss_shoulders": 48.0, "ss_chest": 43.5, "ss_waist": 38.5, "ss_hips": 42.0,
            "ss_bicep_l": 13.0, "ss_bicep_r": 13.0, "ss_thigh_l": 21.5, "ss_thigh_r": 21.5,
            "ss_calf_l": 14.5, "ss_calf_r": 14.5,
            "lab_total_chol": 165.0, "lab_hdl": 50.0, "lab_ldl": 85.0, "lab_triglycerides": 115.0,
            "lab_glucose": 96.0, "lab_hba1c": 5.6, "lab_insulin": 9.0, "lab_hscrp": 1.5,
            "lab_sbp": 128.0, "lab_dbp": 78.0,
            "lab_ferritin": 145.0, "lab_b12": 280.0, "lab_vitamin_d": 32.0,
            "lab_tsh": 2.8, "lab_free_t3": 2.6, "lab_free_t4": 1.0,
            "lab_cortisol_am": 14.0, "lab_testosterone": 340.0,
            "lab_lpa": 42.0, "lab_apob": 70.0, "lab_homa_ir": 2.0,
            "lab_egfr": 75.0, "lab_resting_hr": 65.0,
            "life_vig": 40, "life_mod": 120, "life_sed": 8.5, "life_sleep": 7.5,
            "life_smoker": "Former", "life_alcohol": 3, "life_stress": 5, "life_health": 6,
            # Tier C — questionnaire (well-managed CVD pattern)
            "q_activity_hours_per_week": "3-4 hours",
            "q_weight_trend_perception": "stable",
            "q_training_frequency_days_per_week": "3",
            "q_family_history_heart": "yes",
            "q_smoking": "former_5plus",
            "q_alcohol_drinks_per_week": "0-3",
            "q_cv_fitness_stairs_3_flights": "with_difficulty",
            "q_chest_pain_on_exertion": "no",
            "q_energy_consistency_days_per_week": "4-5",
            "q_afternoon_crashes": "sometimes",
            "q_cold_sensitivity": "no",
            "q_libido_past_4_weeks": "low_reduced",
            "q_mood_swings_past_4_weeks": "rarely",
            "q_thermoregulation": "no",
            "q_morning_motivation": "30_to_60min",
            "q_sleep_hours_per_night": "7-7.9",
            "q_sleep_quality_rested_days": "often",
            "q_stress_interference_past_4_weeks": "rarely",
            "q_recovery_time_after_workout": "1_2_days",
            "q_overwhelmed": "sometimes",
            "q_training_type": "mixed",
            "q_training_intensity_1to10": 5,
            "q_daily_steps": "5000-7499",
            "q_nutrition_whole_food_meals": "most_75",
            "q_hydration_liters_per_day": "2-3",
            "q_protein_meals_with_palm_serving": "two_of_3",
        },
    },
}


def _load_demo_persona(persona_key: str) -> None:
    """Apply demo persona values to session_state.
    Called from the pending resolver at the top of the script,
    before any widgets are instantiated.
    ss_* weight and circumference values stored in DEMO_PERSONAS are in imperial
    (lb / in); they are automatically converted to metric when the unit toggle
    is set to 'Metric (kg / cm)'.
    If the persona has a 'visits' list, it is loaded into visit_history so that
    trajectory charts and progress sections appear immediately."""
    persona = DEMO_PERSONAS[persona_key]
    in_metric = (st.session_state.get("unit_pref", "Imperial (lb / in)")
                 == "Metric (kg / cm)")
    _wt_keys = {"ss_weight_lb", "ss_lean_mass"}
    _ci_keys = {"ss_neck", "ss_shoulders", "ss_chest", "ss_waist", "ss_hips",
                "ss_bicep_l", "ss_bicep_r", "ss_thigh_l", "ss_thigh_r",
                "ss_calf_l", "ss_calf_r"}
    for field_key, value in persona["values"].items():
        if in_metric and isinstance(value, (int, float)):
            if field_key in _wt_keys:
                value = round(value * 0.453592, 1)
            elif field_key in _ci_keys:
                value = round(value * 2.54, 1)
        st.session_state[field_key] = value
    st.session_state["_demo_persona_loaded"] = persona["name"]
    # Keep _prev_unit_pref in sync so the auto-convert block does not
    # double-convert values that were just loaded by this function.
    st.session_state["_prev_unit_pref"] = st.session_state.get(
        "unit_pref", "Imperial (lb / in)")
    # Pre-load multi-visit history when persona has "visits" data
    if "visits" in persona:
        cid = persona["values"].get("client_id", persona_key)
        cname = persona["name"]
        existing = [h for h in st.session_state.get("visit_history", [])
                    if h["client_id"] != cid]
        for _v in persona["visits"]:
            existing.append({
                "client_id":    cid,
                "client_name":  cname,
                "scan_label":   _v["scan_label"],
                "generated_at": _v["scan_date"] + "T09:00:00",
                "result":       _v["result"],
                "unified":      _v.get("unified", {}),
            })
        st.session_state["visit_history"] = existing


if "_pending_demo" in st.session_state:
    _load_demo_persona(st.session_state.pop("_pending_demo"))

# ── end DEMO PERSONAS PANEL ──────────────────────────────────────────────────


# ── Pipeline module loader ────────────────────────────────────────────────────
# Not cached — always reimports so Streamlit Cloud hot-reloads pick up fresh
# module code (avoids stale sys.modules entries with old gate calls).
def _load_pipeline():
    import importlib, sys
    for mod in ["tns_inbody_parser", "tns_shapescale_reader", "tns_reconcile",
                "tns_pca_pipeline", "tns_visualize", "tns_optimal_zones",
                "tns_polygon_scorer"]:
        if mod in sys.modules:
            importlib.reload(sys.modules[mod])
    from tns_inbody_parser     import parse_inbody_csv_string
    from tns_shapescale_reader import parse_shapescale_sheet
    from tns_reconcile         import reconcile_scanners
    from tns_pca_pipeline      import project_client
    from tns_visualize         import generate_client_figures
    return (parse_inbody_csv_string, parse_shapescale_sheet,
            reconcile_scanners, project_client, generate_client_figures)


@st.cache_resource(show_spinner="Loading reference population models…")
def _load_models(model_dir: str):
    from tns_pca_pipeline import load_all_models
    return load_all_models(model_dir)


# ════════════════════════════════════════════════════════════════════════════════
# SIDEBAR — collapsible expanders
# ════════════════════════════════════════════════════════════════════════════════
with st.sidebar:
    st.markdown("## 🏋️ TNS Health Map")
    st.markdown("*TechNSports · Mérida, Yucatán*")
    st.divider()

    # ── 1. Client Info (expanded=True) ────────────────────────────────────────
    with st.expander("Client Info", expanded=True):
        # NOTE (FIX 21): A red square "..." icon sometimes appears on this field in
        # Chrome. Confirmed to be a browser extension artifact (grammar/spell-check
        # tools like Grammarly). Not a code bug — no fix required in app code.
        client_name = st.text_input("Name", value="Jesus Garcia", key="client_name")
        client_id   = st.text_input(
            "Client ID",
            value="garcia_jesus",
            key="client_id",
            help="Used for file naming. Use lowercase with underscores (e.g. garcia_jesus).",
        )
        col_s, col_h = st.columns(2)
        with col_s:
            sex = st.selectbox("Sex", ["M", "F"], key="sex")
        with col_h:
            height_cm = st.number_input("Height cm", 100.0, 250.0, 179.0, 0.5, key="height_cm")
        unit_pref = st.radio(
            "Units (ShapeScale)",
            ["Imperial (lb / in)", "Metric (kg / cm)"],
            horizontal=True,
            key="unit_pref",
            help="Switches display units for ShapeScale weight and circumference inputs. "
                 "Converts existing values automatically. Labs and InBody are unaffected.",
        )
        # ── Visit: free-form date + optional text label ───────────────
        _vc1, _vc2 = st.columns([1, 1])
        with _vc1:
            visit_date_input = st.date_input(
                "Visit date",
                value=datetime.date.today(),
                key="visit_date_input",
            )
        with _vc2:
            scan_label_raw = st.text_input(
                "Label (optional)",
                placeholder="Intake, 8wk, 3mo…",
                key="scan_label_input",
            )
        scan_label = scan_label_raw.strip() if scan_label_raw.strip() else visit_date_input.strftime("%Y-%m-%d")
        lens       = st.selectbox(
            "Lens",
            ["auto", "health", "body_comp", "performance", "weight_mgmt", "longevity"],
            help="Scoring perspective. 'auto' picks the best lens based on available data. "
                 "Options: health (general wellness), body_comp (body composition focus), "
                 "performance (athletic), weight_mgmt (weight loss/gain), longevity (aging markers).",
        )

    # ── Clear form button ─────────────────────────────────────────────────────
    _FORM_KEYS = [
        "client_name", "client_id", "sex", "height_cm",
        "ss_weight_lb", "ss_lean_mass", "ss_bmr_cal", "ss_bf_pct", "ss_bmi",
        "ss_shape_score", "ss_health_score", "ss_body_age", "ss_visc_rating",
        "ss_neck", "ss_shoulders", "ss_chest", "ss_waist", "ss_hips",
        "ss_bicep_l", "ss_bicep_r", "ss_thigh_l", "ss_thigh_r",
        "ss_calf_l", "ss_calf_r", "ss_whr", "ss_whtr",
        "lab_total_chol", "lab_hdl", "lab_ldl", "lab_triglycerides",
        "lab_lpa", "lab_apob", "lab_glucose", "lab_hba1c",
        "lab_insulin", "lab_homa_ir", "lab_hscrp",
        "lab_sbp", "lab_dbp", "lab_resting_hr",
        "lab_tsh", "lab_free_t3", "lab_free_t4",
        "lab_cortisol_am", "lab_testosterone",
        "lab_ferritin", "lab_b12", "lab_vitamin_d", "lab_egfr",
        "life_vig", "life_mod", "life_sed", "life_sleep",
        "life_smoker", "life_alcohol", "life_stress", "life_health",
        "ib_csv", "ib_pdf_scans", "_ib_pdf_name",
        "_demo_persona_loaded",
        "scan_label_input", "visit_date_input",
        "q_activity_hours_per_week", "q_weight_trend_perception",
        "q_training_frequency_days_per_week", "q_family_history_heart",
        "q_smoking", "q_alcohol_drinks_per_week",
        "q_cv_fitness_stairs_3_flights", "q_chest_pain_on_exertion",
        "q_energy_consistency_days_per_week", "q_afternoon_crashes",
        "q_cold_sensitivity", "q_libido_past_4_weeks",
        "q_mood_swings_past_4_weeks", "q_thermoregulation",
        "q_morning_motivation", "q_menstrual_regularity",
        "q_sleep_hours_per_night", "q_sleep_quality_rested_days",
        "q_stress_interference_past_4_weeks", "q_recovery_time_after_workout",
        "q_overwhelmed", "q_training_type", "q_training_intensity_1to10",
        "q_daily_steps", "q_nutrition_whole_food_meals",
        "q_hydration_liters_per_day", "q_protein_meals_with_palm_serving",
    ]
    if st.button("🗑️ Clear form", key="clear_form_btn", use_container_width=True,
                 help="Reset all client fields, scan data, and lab values."):
        for _ck in _FORM_KEYS:
            st.session_state.pop(_ck, None)
        st.rerun()

    st.divider()

    # ── 2. Models ─────────────────────────────────────────────────────────────
    with st.expander("⚙️ Engine Settings", expanded=False):
        model_dir = st.text_input("Model directory", value=DEFAULT_MODEL_DIR)
        models = None
        if Path(model_dir).exists():
            try:
                models = _load_models(model_dir)
                if models:
                    st.success(f"✅ {len(models)} lens model(s) loaded")
                    for lname in models:
                        st.caption(f"  • {lname}")
                else:
                    st.warning("No models found. Run Step 1 in the Colab notebook first.")
            except Exception as exc:
                st.error(f"Load error: {exc}")
        else:
            st.warning("Model directory not found.\nRun Colab Step 1 to build models.")

    st.divider()

    # ── 3. Lipids ─────────────────────────────────────────────────────────────
    with st.expander("Lipids", expanded=False):
        lab_total_chol    = st.number_input("Total Cholesterol (mg/dL)", 0.0, 1000.0, step=1.0,
                                             help="Optimal: 150–181 mg/dL", key="lab_total_chol")
        lab_hdl           = st.number_input("HDL (mg/dL)", 0.0, 500.0, step=1.0,
                                             help="Optimal (M): ≥60 | Optimal (F): ≥65 mg/dL", key="lab_hdl")
        lab_ldl           = st.number_input("LDL (mg/dL)", 0.0, 800.0, step=1.0,
                                             help="Optimal: <70 mg/dL", key="lab_ldl")
        lab_triglycerides = st.number_input("Triglycerides (mg/dL)", 0.0, 3000.0, step=1.0,
                                             help="Optimal: <100 mg/dL", key="lab_triglycerides")
        lab_lpa           = st.number_input("Lp(a) (mg/dL)", 0.0, 500.0, step=1.0,
                                             help="Optimal: <14 mg/dL", key="lab_lpa")
        lab_apob          = st.number_input("ApoB (mg/dL)", 0.0, 300.0, step=1.0,
                                             help="Optimal: <80 mg/dL", key="lab_apob")

    st.divider()

    # ── 4. Metabolic ──────────────────────────────────────────────────────────
    with st.expander("Metabolic", expanded=False):
        lab_glucose   = st.number_input("Glucose fasting (mg/dL)", 0.0, 800.0, step=1.0,
                                         help="Optimal: 70–90 mg/dL", key="lab_glucose")
        lab_hba1c     = st.number_input("HbA1c (%)", 0.0, 25.0, step=0.1,
                                         help="Optimal: 4.0–5.2%", key="lab_hba1c")
        lab_insulin   = st.number_input("Insulin fasting (µIU/mL)", 0.0, 500.0, step=0.1,
                                         help="Optimal: 2–7 µIU/mL", key="lab_insulin")
        lab_homa_ir   = st.number_input("HOMA-IR", 0.0, 50.0, step=0.1,
                                         help="Optimal: <1.0 (computed or direct entry)", key="lab_homa_ir")

    st.divider()

    # ── 5. Inflammation ───────────────────────────────────────────────────────
    with st.expander("Inflammation", expanded=False):
        lab_hscrp = st.number_input("hs-CRP (mg/L)", 0.0, 200.0, step=0.1,
                                     help="Optimal: <0.5 mg/L", key="lab_hscrp")

    st.divider()

    # ── 6. Blood Pressure & Heart Rate ────────────────────────────────────────
    with st.expander("Blood Pressure & Heart Rate", expanded=False):
        lab_sbp        = st.number_input("Systolic BP (mmHg)", 0.0, 300.0, step=1.0,
                                          help="Optimal: 90–120 mmHg", key="lab_sbp")
        lab_dbp        = st.number_input("Diastolic BP (mmHg)", 0.0, 200.0, step=1.0,
                                          help="Optimal: 60–80 mmHg", key="lab_dbp")
        lab_resting_hr = st.number_input("Resting HR (bpm)", 0.0, 250.0, step=1.0,
                                          help="Optimal: 40–60 bpm (well-trained)", key="lab_resting_hr")

    st.divider()

    # ── 7. Thyroid ────────────────────────────────────────────────────────────
    with st.expander("Thyroid", expanded=False):
        lab_tsh    = st.number_input("TSH (mIU/L)", 0.0, 20.0, step=0.01,
                                      help="Optimal: 1.0–2.51 mIU/L", key="lab_tsh")
        lab_free_t3 = st.number_input("Free T3 (pg/mL)", 0.0, 15.0, step=0.1,
                                       help="Optimal: 3.0–4.21 pg/mL", key="lab_free_t3")
        lab_free_t4 = st.number_input("Free T4 (ng/dL)", 0.0, 10.0, step=0.01,
                                       help="Optimal: 1.1–1.71 ng/dL", key="lab_free_t4")

    st.divider()

    # ── 8. Hormones ───────────────────────────────────────────────────────────
    with st.expander("Hormones", expanded=False):
        lab_cortisol_am  = st.number_input("AM Cortisol (µg/dL)", 0.0, 100.0, step=0.1,
                                            help="Optimal: 12–19 µg/dL", key="lab_cortisol_am")
        lab_testosterone = st.number_input("Testosterone total (ng/dL)", 0.0, 2000.0, step=1.0,
                                            help="Optimal (M): 600–901 | Optimal (F): 25–61 ng/dL",
                                            key="lab_testosterone")

    st.divider()

    # ── 9. Iron & Vitamins ────────────────────────────────────────────────────
    with st.expander("Iron & Vitamins", expanded=False):
        lab_ferritin  = st.number_input("Ferritin (ng/mL)", 0.0, 2000.0, step=1.0,
                                         help="Optimal (M): 50–151 | Optimal (F): 30–101 ng/mL",
                                         key="lab_ferritin")
        lab_b12       = st.number_input("Vitamin B12 (pg/mL)", 0.0, 5000.0, step=1.0,
                                         help="Optimal: 600–1201 pg/mL", key="lab_b12")
        lab_vitamin_d = st.number_input("Vitamin D 25-OH (ng/mL)", 0.0, 200.0, step=1.0,
                                         help="Optimal: 50–81 ng/mL", key="lab_vitamin_d")

    st.divider()

    # ── 10. Kidney ────────────────────────────────────────────────────────────
    with st.expander("Kidney", expanded=False):
        lab_egfr = st.number_input("eGFR (mL/min/1.73m²)", 0.0, 200.0, step=1.0,
                                    help="Optimal: ≥90 mL/min/1.73m²", key="lab_egfr")

    st.divider()

    # ── 11. Lifestyle ─────────────────────────────────────────────────────────
    with st.expander("Lifestyle", expanded=False):
        life_vig    = st.number_input("Vigorous activity (min/week)", 0, 2000, step=10,  key="life_vig")
        life_mod    = st.number_input("Moderate activity (min/week)", 0, 2000, step=10,  key="life_mod")
        life_sed    = st.number_input("Sedentary hours/day",          0.0, 24.0, step=0.5, key="life_sed")
        life_sleep  = st.number_input("Sleep hours/night",            0.0, 24.0, step=0.5, key="life_sleep")
        life_smoker  = st.selectbox("Smoker status",
                                     ["(not provided)", "Never", "Former", "Current"],
                                     key="life_smoker")
        life_alcohol = st.number_input("Alcohol drinks/week", 0, 100, step=1, key="life_alcohol")
        life_stress  = st.slider("Stress (1–10, 0 = not provided)", 0, 10, key="life_stress")
        life_health  = st.slider("Subjective health (1–10, 0 = not provided)", 0, 10, key="life_health")

    st.divider()

    # ── 12. Demo Personas (QA) ────────────────────────────────────────────────
    # ============================================================
    # DEMO PERSONAS PANEL — REMOVE BEFORE PRODUCTION LAUNCH
    # Added 2026-04-18 for QA and sales demos.
    # To remove: delete this block + the DEMO_PERSONAS dict + _load_demo_persona() helper.
    # ============================================================
    with st.expander("🧪 Demo Personas", expanded=False):
        st.caption("One-click fill for QA and sales demos. Partial panels leave realistic gaps.")
        pcols = st.columns(2)
        for i, (pkey, persona) in enumerate(DEMO_PERSONAS.items()):
            with pcols[i % 2]:
                if st.button(
                    f"{persona['name']} ({persona['age']}{persona['sex']})",
                    help=persona["profile_summary"],
                    key=f"demo_btn_{pkey}",
                    use_container_width=True,
                ):
                    st.session_state["_pending_demo"] = pkey
                    st.rerun()
    # ── end DEMO PERSONAS PANEL ──────────────────────────────────────────────

    st.divider()

    # ── 13. Visit History ─────────────────────────────────────────────────────
    with st.expander("📈 Visit History", expanded=False):
        _h_all    = st.session_state.get("visit_history", [])
        _h_client = [h for h in _h_all if h["client_id"] == client_id]
        _h_other  = [h for h in _h_all if h["client_id"] != client_id]
        if _h_client:
            st.caption(f"**{len(_h_client)} visit(s)** for {client_name}:")
            for _hv in sorted(_h_client, key=lambda x: x["result"].get("scan_date", x.get("generated_at", "")[:10])):
                _sc = _hv["result"].get("overall_score", "—")
                _dt = _hv["generated_at"][:10]
                st.caption(f"• **{_hv['scan_label'].upper()}** &nbsp;·&nbsp; "
                           f"{_sc}/100 &nbsp;·&nbsp; {_dt}")
        elif _h_other:
            st.info(f"History stored for: **{_h_other[-1]['client_name']}** — "
                    "change client ID or clear below.")
        else:
            st.caption("No visits stored. Generate a Health Map to start tracking.")
        if _h_all:
            if st.button("🗑️ Clear all history", key="clear_history_btn"):
                st.session_state.pop("visit_history", None)
                st.rerun()


# ════════════════════════════════════════════════════════════════════════════════
# MAIN HEADER
# ════════════════════════════════════════════════════════════════════════════════
st.markdown('<p class="tns-header">Health Map</p>', unsafe_allow_html=True)
st.markdown(
    f'<p class="tns-sub">{client_name} &nbsp;·&nbsp; '
    f'{scan_label.upper()} &nbsp;·&nbsp; {height_cm} cm &nbsp;·&nbsp; {sex}</p>',
    unsafe_allow_html=True,
)
st.divider()


# ════════════════════════════════════════════════════════════════════════════════
# DATA ENTRY TABS — Scan data only (labs & lifestyle in sidebar expanders)
# ════════════════════════════════════════════════════════════════════════════════
tab_ib, tab_ss, tab_q = st.tabs(["🔬 InBody Scan", "📐 ShapeScale Scan", "📋 Questionnaire"])

# ── InBody ────────────────────────────────────────────────────────────────────
with tab_ib:
    st.markdown(
        "**Option A — Upload** a file &nbsp;·&nbsp; "
        "**Option B — Paste** CSV text below."
    )

    _col_csv, _col_pdf = st.columns(2)
    with _col_csv:
        upload_ib = st.file_uploader(
            "📄 InBody CSV (LookinBody export)",
            type=["csv"],
        )
    with _col_pdf:
        _upload_ib_pdf = st.file_uploader(
            "📋 InBody PDF (HealthReport — LookinBody)",
            type=["pdf"],
            key="ib_pdf_uploader",
            help="Upload an 'Overall Results Analysis' PDF exported from LookinBody Cloud.",
        )

    # ── PDF parsing (cached by filename to avoid re-OCR on every rerun) ──────
    if _upload_ib_pdf is not None:
        if _upload_ib_pdf.name != st.session_state.get("_ib_pdf_name", ""):
            with st.spinner(f"Parsing {_upload_ib_pdf.name} … (may take 30–90 s)"):
                import tempfile as _tempfile
                from pathlib import Path as _Path
                _tmp_path = None
                try:
                    from tns_inbody_pdf_parser import parse_inbody_pdf as _parse_pdf
                    with _tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as _tmp:
                        _tmp.write(_upload_ib_pdf.getbuffer())
                        _tmp_path = _tmp.name
                    _pdf_scans = _parse_pdf(_tmp_path)
                    st.session_state["ib_pdf_scans"] = _pdf_scans
                    st.session_state["_ib_pdf_name"] = _upload_ib_pdf.name
                except Exception as _pdf_exc:
                    st.error(f"⚠️ PDF parse error: {_pdf_exc}")
                    st.session_state["ib_pdf_scans"] = []
                    st.session_state["_ib_pdf_name"] = _upload_ib_pdf.name
                finally:
                    if _tmp_path:
                        _Path(_tmp_path).unlink(missing_ok=True)

        _pdf_scans_cached = st.session_state.get("ib_pdf_scans", [])
        if _pdf_scans_cached:
            from tns_inbody_pdf_parser import inbody_pdf_summary as _ib_summary
            for _s in _pdf_scans_cached:
                _ib_fields = [k for k, v in _s.items() if k.startswith("ib_") and v is not None]
                if len(_ib_fields) >= 5:
                    st.success(f"✅ {_ib_summary(_s)}")
                else:
                    st.warning(
                        f"⚠️ PDF parsed but only {len(_ib_fields)} field(s) extracted "
                        f"(History format has limited data). "
                        f"**CSV or comparison HealthReport PDF recommended.** "
                        f"Extracted: {', '.join(_ib_fields) or 'none'}"
                    )
        else:
            st.warning("No scans could be extracted from this PDF.")

    # ── Active InBody source indicator ────────────────────────────────────────
    _has_pdf_active   = _upload_ib_pdf is not None and bool(st.session_state.get("ib_pdf_scans"))
    _has_csv_active   = bool(st.session_state.get("ib_csv", "").strip())
    if _has_pdf_active:
        _pdf_fields = [k for k, v in st.session_state["ib_pdf_scans"][0].items()
                       if k.startswith("ib_") and v is not None]
        if len(_pdf_fields) >= 5:
            st.info(f"📋 **Active source: PDF** ({st.session_state.get('_ib_pdf_name', 'uploaded PDF')}) — overrides CSV text below.")
        else:
            st.error(
                f"⚠️ **PDF has sparse data ({len(_pdf_fields)} InBody fields)** — "
                "remove the PDF from the uploader to fall back to CSV text."
            )
    elif _has_csv_active:
        st.info("📄 **Active source: CSV text** — PDF uploader is empty.")
    else:
        st.caption("No InBody data loaded yet.")

    if st.button("Load Jesus Garcia example data (Apr 12 2026)"):
        st.session_state["ib_csv"] = (
            "Date,Measurement device.,Weight(lb),Skeletal Muscle Mass(lb),Soft Lean Mass(lb),"
            "Body Fat Mass(lb),BMI(kg/m²),Percent Body Fat(%),Basal Metabolic Rate(kJ),"
            "InBody Score,Right Arm Lean Mass(lb),Left Arm Lean Mass(lb),Trunk Lean Mass(lb),"
            "Right Leg Lean Mass(lb),Left leg Lean Mass(lb),Right Arm Fat Mass(lb),"
            "Left Arm Fat Mass(lb),Trunk Fat Mass(lb),Right Leg Fat Mass(lb),Left Leg Fat Mass(lb),"
            "Right Arm ECW Ratio,Left Arm ECW Ratio,Trunk ECW Ratio,Right Leg ECW Ratio,"
            "Left Leg ECW Ratio,Waist Hip Ratio,Waist Circumference(cm),Visceral Fat Area(cm²),"
            "Visceral Fat Level(Level),Total Body Water(lb),Intracellular Water(lb),"
            "Extracellular Water(lb),ECW Ratio,Upper-Lower,Upper,Lower,Leg Muscle Level(Level),"
            "Leg Lean Mass(lb),Protein(lb),Mineral(lb),Bone Mineral Content(lb),Body Cell Mass(lb),"
            "SMI(kg/m²),Whole Body Phase Angle(°)\n"
            "20260412153252,270S,219.1,88.0,-,65.3,34.4,29.8,7853,78.0,9.11,9.19,68.1,22.00,21.72,"
            "4.4,4.4,35.9,8.6,8.6,-,-,-,-,-,0.95,-,-,12.0,112.9,-,-,-,1,0,0,-,-,30.6,10.45,-,-,9.7,6.9"
        )
        st.rerun()

    ib_csv_text = st.text_area(
        "Paste InBody CSV text",
        height=130,
        placeholder="Date,Measurement device.,Weight(lb),…",
        key="ib_csv",
    )

# ── ShapeScale ────────────────────────────────────────────────────────────────
with tab_ss:
    _ss_metric = (unit_pref == "Metric (kg / cm)")
    _su        = "kg / cm" if _ss_metric else "lb / in"
    st.markdown(
        f"Enter values from the ShapeScale app or PDF. &nbsp; **Units: {_su}** "
        f"— toggle via *Units (ShapeScale)* in the sidebar Client Info."
    )

    # ── Defaults from Jesus Garcia's actual ShapeScale scan (Apr 13 2026) ────
    _DEF_WT   = round(215.3 * 0.453592, 1) if _ss_metric else 215.3   # 97.7 kg
    _DEF_LM   = round(140.9 * 0.453592, 1) if _ss_metric else 140.9   # 63.9 kg
    _DEF_NECK = round(17.2  * 2.54,     1) if _ss_metric else 17.2    # 43.7 cm
    _DEF_SHO  = round(46.1  * 2.54,     1) if _ss_metric else 46.1    # 117.1 cm
    _DEF_CHE  = round(49.2  * 2.54,     1) if _ss_metric else 49.2    # 125.0 cm
    _DEF_WST  = round(44.1  * 2.54,     1) if _ss_metric else 44.1    # 112.0 cm
    _DEF_HIP  = round(44.1  * 2.54,     1) if _ss_metric else 44.1    # 112.0 cm
    _DEF_BIL  = round(15.7  * 2.54,     1) if _ss_metric else 15.7    # 39.9 cm
    _DEF_BIR  = round(15.4  * 2.54,     1) if _ss_metric else 15.4    # 39.1 cm
    _DEF_THL  = round(25.4  * 2.54,     1) if _ss_metric else 25.4    # 64.5 cm
    _DEF_THR  = round(25.2  * 2.54,     1) if _ss_metric else 25.2    # 64.0 cm
    _DEF_CAL  = round(16.8  * 2.54,     1) if _ss_metric else 16.8    # 42.7 cm
    _DEF_CAR  = round(16.7  * 2.54,     1) if _ss_metric else 16.7    # 42.4 cm

    c1, c2, c3 = st.columns(3)

    with c1:
        st.markdown("**Summary**")
        ss_date         = st.date_input("Scan date", datetime.date(2026, 4, 13))
        ss_weight_lb    = st.number_input(
            "Weight (kg)" if _ss_metric else "Weight (lb)",
            0.0, 300.0 if _ss_metric else 600.0, _DEF_WT, 0.1,
            key="ss_weight_lb",
        )
        ss_lean_mass    = st.number_input(
            "Lean mass (kg)" if _ss_metric else "Lean mass (lb)",
            0.0, 250.0 if _ss_metric else 500.0, _DEF_LM, 0.1,
            key="ss_lean_mass",
            help="Total lean (fat-free) mass from ShapeScale report. 0 = not provided.",
        )
        ss_bmr_cal      = st.number_input(
            "BMR (kcal/day)", 0, 5000, 1685, 1,
            key="ss_bmr_cal",
            help="Basal Metabolic Rate in kcal/day from ShapeScale report. 0 = not provided.",
        )
        ss_bf_pct       = st.number_input("Body fat %",   0.0,  70.0,  34.5, 0.1, key="ss_bf_pct")
        ss_bmi          = st.number_input("BMI",           0.0,  80.0,  33.8, 0.1, key="ss_bmi")
        ss_shape_score  = st.number_input("Shape score",   0,    100,   30,   1,   key="ss_shape_score")
        ss_health_score = st.number_input("Health score",  0,    100,   38,   1,   key="ss_health_score")
        ss_body_age     = st.number_input("Body age",      0,    120,   48,   1,   key="ss_body_age")
        ss_visc_rating  = st.selectbox(
            "Visceral fat rating",
            ["Very Poor", "Poor", "Fair", "Good", "Excellent"],
            index=0, key="ss_visc_rating",
        )

    with c2:
        _cu  = "cm" if _ss_metric else "in"
        _wmax = 200.0 if _ss_metric else 80.0
        _cmax = 250.0 if _ss_metric else 100.0
        st.markdown(f"**Circumferences ({_cu})**")
        ss_neck      = st.number_input("Neck",      0.0, _wmax, _DEF_NECK, 0.1, key="ss_neck")
        ss_shoulders = st.number_input("Shoulders", 0.0, _cmax, _DEF_SHO,  0.1, key="ss_shoulders")
        ss_chest     = st.number_input("Chest",     0.0, _cmax, _DEF_CHE,  0.1, key="ss_chest")
        ss_waist     = st.number_input("Waist",     0.0, _wmax, _DEF_WST,  0.1, key="ss_waist")
        ss_hips      = st.number_input("Hips",      0.0, _wmax, _DEF_HIP,  0.1, key="ss_hips")
        st.markdown("**Ratios** *(unit-free — 0 = not provided)*")
        ss_whr  = st.number_input(
            "WHR (waist ÷ hips)", 0.0, 2.0, 1.00, 0.01, key="ss_whr",
            help="Waist-to-hip ratio from ShapeScale. 0 = not provided.",
        )
        ss_whtr = st.number_input(
            "WHtR (waist ÷ height)", 0.0, 2.0, 0.63, 0.01, key="ss_whtr",
            help="Waist-to-height ratio from ShapeScale. 0 = not provided.",
        )

    with c3:
        _lmax = 80.0  if _ss_metric else 30.0
        _tmax = 130.0 if _ss_metric else 50.0
        st.markdown(f"**Limbs ({_cu})**")
        ss_bicep_l  = st.number_input("Bicep L",  0.0, _lmax, _DEF_BIL, 0.1, key="ss_bicep_l")
        ss_bicep_r  = st.number_input("Bicep R",  0.0, _lmax, _DEF_BIR, 0.1, key="ss_bicep_r")
        ss_thigh_l  = st.number_input("Thigh L",  0.0, _tmax, _DEF_THL, 0.1, key="ss_thigh_l")
        ss_thigh_r  = st.number_input("Thigh R",  0.0, _tmax, _DEF_THR, 0.1, key="ss_thigh_r")
        ss_calf_l   = st.number_input("Calf L",   0.0, _lmax, _DEF_CAL, 0.1, key="ss_calf_l")
        ss_calf_r   = st.number_input("Calf R",   0.0, _lmax, _DEF_CAR, 0.1, key="ss_calf_r")

# ── Questionnaire ─────────────────────────────────────────────────────────────
with tab_q:
    st.markdown(
        "Complete the questionnaire below to unlock **full scoring** across all six health categories.  \n"
        "Leave any unanswered items as *(not provided)* — partial responses are handled gracefully."
    )

    # ── Body Composition ──────────────────────────────────────────────────────
    with st.expander("🏋️ Body Composition", expanded=True):
        qbc1, qbc2 = st.columns(2)
        with qbc1:
            q_activity_hours_per_week = st.selectbox(
                "Weekly active hours",
                ["(not provided)", "0 hours", "1-2 hours", "3-4 hours", "5-7 hours", "8+ hours"],
                help="Total hours per week spent in physical activity (training + sport + active recreation).",
                key="q_activity_hours_per_week",
            )
            q_weight_trend_perception = st.selectbox(
                "Recent weight trend (self-reported)",
                ["(not provided)", "losing_happy", "stable", "gaining_unwanted"],
                format_func=lambda x: {
                    "(not provided)": "(not provided)",
                    "losing_happy":     "Losing — intentionally",
                    "stable":           "Stable",
                    "gaining_unwanted": "Gaining — not intended",
                }.get(x, x),
                key="q_weight_trend_perception",
            )
        with qbc2:
            q_training_frequency_days_per_week = st.selectbox(
                "Training days per week",
                ["(not provided)", "0", "1", "2", "3", "4", "5+"],
                help="Days per week with a structured workout session.",
                key="q_training_frequency_days_per_week",
            )

    # ── Heart & Vascular ──────────────────────────────────────────────────────
    with st.expander("❤️ Heart & Vascular", expanded=False):
        qhv1, qhv2 = st.columns(2)
        with qhv1:
            q_family_history_heart = st.selectbox(
                "Family history of heart problems",
                ["(not provided)", "no", "unknown", "yes"],
                format_func=lambda x: {
                    "(not provided)": "(not provided)", "no": "No",
                    "unknown": "Unknown", "yes": "Yes",
                }.get(x, x),
                key="q_family_history_heart",
            )
            q_smoking = st.selectbox(
                "Smoking status",
                ["(not provided)", "never", "former_5plus", "former_recent", "current"],
                format_func=lambda x: {
                    "(not provided)":  "(not provided)",
                    "never":           "Never smoked",
                    "former_5plus":    "Former — quit 5+ years ago",
                    "former_recent":   "Former — quit < 5 years ago",
                    "current":         "Current smoker",
                }.get(x, x),
                key="q_smoking",
            )
            q_alcohol_drinks_per_week = st.selectbox(
                "Alcoholic drinks per week",
                ["(not provided)", "0-3", "4-7", "8-14", "15+"],
                key="q_alcohol_drinks_per_week",
            )
        with qhv2:
            q_cv_fitness_stairs_3_flights = st.selectbox(
                "Can climb 3 flights of stairs without stopping?",
                ["(not provided)", "yes", "with_difficulty", "no"],
                format_func=lambda x: {
                    "(not provided)":   "(not provided)",
                    "yes":              "Yes — easily",
                    "with_difficulty":  "Yes — with difficulty",
                    "no":               "No",
                }.get(x, x),
                key="q_cv_fitness_stairs_3_flights",
            )
            q_chest_pain_on_exertion = st.selectbox(
                "Chest pain or pressure during physical activity? ⚠️",
                ["(not provided)", "no", "yes"],
                format_func=lambda x: {
                    "(not provided)": "(not provided)",
                    "no":  "No",
                    "yes": "Yes — triggers PAR-Q medical review",
                }.get(x, x),
                help="A 'yes' response triggers a PAR-Q escalation flag requiring medical clearance before exercise.",
                key="q_chest_pain_on_exertion",
            )

    # ── Metabolic Function ────────────────────────────────────────────────────
    with st.expander("⚡ Metabolic Function", expanded=False):
        qmf1, qmf2 = st.columns(2)
        with qmf1:
            q_energy_consistency_days_per_week = st.selectbox(
                "Days per week with consistent energy",
                ["(not provided)", "6-7", "4-5", "2-3", "0-1"],
                key="q_energy_consistency_days_per_week",
            )
            q_afternoon_crashes = st.selectbox(
                "Afternoon energy crashes",
                ["(not provided)", "never", "sometimes", "often", "daily"],
                key="q_afternoon_crashes",
            )
        with qmf2:
            q_cold_sensitivity = st.selectbox(
                "Unusual sensitivity to cold",
                ["(not provided)", "no", "sometimes", "yes"],
                format_func=lambda x: {
                    "(not provided)": "(not provided)",
                    "no":        "No",
                    "sometimes": "Sometimes",
                    "yes":       "Yes — frequently",
                }.get(x, x),
                help="Persistently cold hands/feet or feeling cold when others don't.",
                key="q_cold_sensitivity",
            )

    # ── Hormonal Balance ──────────────────────────────────────────────────────
    with st.expander("🔬 Hormonal Balance", expanded=False):
        qhb1, qhb2 = st.columns(2)
        with qhb1:
            q_libido_past_4_weeks = st.selectbox(
                "Libido / sex drive (past 4 weeks)",
                ["(not provided)", "strong", "moderate_lower", "low_reduced", "very_low"],
                format_func=lambda x: {
                    "(not provided)":   "(not provided)",
                    "strong":           "Strong",
                    "moderate_lower":   "Moderate / lower than usual",
                    "low_reduced":      "Low / significantly reduced",
                    "very_low":         "Very low / absent",
                }.get(x, x),
                key="q_libido_past_4_weeks",
            )
            q_mood_swings_past_4_weeks = st.selectbox(
                "Mood swings (past 4 weeks)",
                ["(not provided)", "rarely", "few_times", "several_per_week", "most_days"],
                format_func=lambda x: {
                    "(not provided)":    "(not provided)",
                    "rarely":            "Rarely",
                    "few_times":         "A few times",
                    "several_per_week":  "Several times per week",
                    "most_days":         "Most days",
                }.get(x, x),
                key="q_mood_swings_past_4_weeks",
            )
            q_thermoregulation = st.selectbox(
                "Unexplained hot flashes or night sweats",
                ["(not provided)", "no", "occasionally", "frequently"],
                key="q_thermoregulation",
            )
        with qhb2:
            q_morning_motivation = st.selectbox(
                "Time to feel alert and motivated in the morning",
                ["(not provided)", "within_15min", "30_to_60min", "over_hour", "rarely"],
                format_func=lambda x: {
                    "(not provided)": "(not provided)",
                    "within_15min": "< 15 minutes",
                    "30_to_60min":  "30–60 minutes",
                    "over_hour":    "Over 1 hour",
                    "rarely":       "Rarely feel motivated",
                }.get(x, x),
                key="q_morning_motivation",
            )
            q_menstrual_regularity = st.selectbox(
                "Menstrual cycle regularity (women only — skip if male)",
                ["(not provided)", "regular", "NA_contraception", "NA_menopausal", "irregular"],
                format_func=lambda x: {
                    "(not provided)":    "(not provided)",
                    "regular":           "Regular (28 ± 7 days)",
                    "NA_contraception":  "N/A — on hormonal contraception",
                    "NA_menopausal":     "N/A — menopausal / post-menopausal",
                    "irregular":         "Irregular",
                }.get(x, x),
                help="Automatically skipped in scoring for male clients.",
                key="q_menstrual_regularity",
            )

    # ── Stress & Recovery ─────────────────────────────────────────────────────
    with st.expander("🌙 Stress & Recovery", expanded=False):
        qsr1, qsr2 = st.columns(2)
        with qsr1:
            q_sleep_hours_per_night = st.selectbox(
                "Sleep hours per night",
                ["(not provided)", "8+", "7-7.9", "6-6.9", "5-5.9", "<5"],
                key="q_sleep_hours_per_night",
            )
            q_sleep_quality_rested_days = st.selectbox(
                "Days per week waking up feeling rested",
                ["(not provided)", "almost_always", "often", "sometimes", "rarely"],
                key="q_sleep_quality_rested_days",
            )
            q_stress_interference_past_4_weeks = st.selectbox(
                "Stress interfering with daily life (past 4 weeks)",
                ["(not provided)", "rarely", "few_times", "several_per_week", "most_days"],
                key="q_stress_interference_past_4_weeks",
            )
        with qsr2:
            q_recovery_time_after_workout = st.selectbox(
                "Recovery time after a hard workout",
                ["(not provided)", "same_day", "1_2_days", "3_plus_days", "rarely_recovered"],
                format_func=lambda x: {
                    "(not provided)":    "(not provided)",
                    "same_day":          "Same day",
                    "1_2_days":          "1–2 days",
                    "3_plus_days":       "3+ days",
                    "rarely_recovered":  "Never fully recovered",
                }.get(x, x),
                key="q_recovery_time_after_workout",
            )
            q_overwhelmed = st.selectbox(
                "Feeling overwhelmed or unable to cope",
                ["(not provided)", "never", "sometimes", "often", "always"],
                key="q_overwhelmed",
            )

    # ── Lifestyle & Fitness ───────────────────────────────────────────────────
    with st.expander("🏃 Lifestyle & Fitness", expanded=False):
        qlf1, qlf2 = st.columns(2)
        with qlf1:
            q_training_type = st.selectbox(
                "Primary training type",
                ["(not provided)", "mixed", "resistance", "cardio", "none"],
                format_func=lambda x: {
                    "(not provided)": "(not provided)",
                    "mixed":      "Mixed — resistance + cardio",
                    "resistance": "Resistance / strength only",
                    "cardio":     "Cardio / endurance only",
                    "none":       "None",
                }.get(x, x),
                key="q_training_type",
            )
            q_training_intensity_1to10 = st.slider(
                "Typical training intensity (0 = not provided, 7–8 = optimal zone)",
                0, 10, 0,
                help="Rate your typical session effort: 0 = not provided, 1 = very easy, 10 = maximum.",
                key="q_training_intensity_1to10",
            )
            q_daily_steps = st.selectbox(
                "Average daily steps",
                ["(not provided)", "10000+", "7500-9999", "5000-7499", "3000-4999", "<3000"],
                key="q_daily_steps",
            )
        with qlf2:
            q_nutrition_whole_food_meals = st.selectbox(
                "Proportion of meals based on whole foods",
                ["(not provided)", "all", "most_75", "half", "less_half", "few_none"],
                format_func=lambda x: {
                    "(not provided)": "(not provided)",
                    "all":       "All meals",
                    "most_75":   "Most (≥ 75%)",
                    "half":      "About half",
                    "less_half": "Less than half",
                    "few_none":  "Few or none",
                }.get(x, x),
                key="q_nutrition_whole_food_meals",
            )
            q_hydration_liters_per_day = st.selectbox(
                "Daily water intake",
                ["(not provided)", "3+", "2-3", "1-2", "<1"],
                format_func=lambda x: {
                    "(not provided)": "(not provided)",
                    "3+":  "3+ liters",
                    "2-3": "2–3 liters",
                    "1-2": "1–2 liters",
                    "<1":  "Less than 1 liter",
                }.get(x, x),
                key="q_hydration_liters_per_day",
            )
            q_protein_meals_with_palm_serving = st.selectbox(
                "Meals per day with a palm-sized protein serving",
                ["(not provided)", "all_3", "two_of_3", "one_of_3", "rarely"],
                format_func=lambda x: {
                    "(not provided)": "(not provided)",
                    "all_3":    "All 3 meals",
                    "two_of_3": "2 of 3 meals",
                    "one_of_3": "1 of 3 meals",
                    "rarely":   "Rarely",
                }.get(x, x),
                key="q_protein_meals_with_palm_serving",
            )

st.info("💡 **Tip:** Labs and Lifestyle values are entered in the **sidebar expanders** below Client Info (scroll down in the sidebar to find Lipids, Metabolic, etc.).")


# ════════════════════════════════════════════════════════════════════════════════
# RUN BUTTON
# ════════════════════════════════════════════════════════════════════════════════
st.divider()
run_disabled = models is None
if run_disabled:
    st.info("📋 Models not loaded. Point the **Model directory** in the sidebar to your built models folder.")

run_btn = st.button(
    "🗺️  Generate Health Map",
    type="primary",
    use_container_width=False,
    disabled=run_disabled,
)

# ── Demo persona banner ────────────────────────────────────────────────────────
if loaded := st.session_state.get("_demo_persona_loaded"):
    st.warning(
        f"⚠️ Demo persona loaded: **{loaded}** — clear the form before scoring a real client."
    )

# ── Visit history banner ───────────────────────────────────────────────────────
_prior_visits = sorted(
    [h for h in st.session_state.get("visit_history", []) if h["client_id"] == client_id],
    key=lambda x: x["result"].get("scan_date", x.get("generated_at", "")[:10]),
)
if _prior_visits:
    _vl = " → ".join(h["scan_label"].upper() for h in _prior_visits)
    st.info(
        f"📈 **{len(_prior_visits)} visit(s) stored for {client_name}:** {_vl}  \n"
        f"Generating **{scan_label.upper()}** will add a trajectory chart and "
        f"{'radar overlay comparison' if any(h['scan_label'] == 'intake' for h in _prior_visits) and scan_label != 'intake' else 'progress tracking'}."
    )


# ════════════════════════════════════════════════════════════════════════════════
# PIPELINE EXECUTION + RESULTS
# ════════════════════════════════════════════════════════════════════════════════
if run_btn:
    st.toast("🔄 Generating Health Map...", icon="🗺️")
    from tns_optimal_zones import get_report_disclaimer
    (parse_inbody_csv_string, parse_shapescale_sheet,
     reconcile_scanners, project_client,
     generate_client_figures) = _load_pipeline()

    errors: list[str] = []

    # ── Parse InBody ──────────────────────────────────────────────────────────
    ib_scans = []
    raw_text = ""
    if upload_ib is not None:
        raw_text = upload_ib.read().decode("utf-8-sig")
    elif st.session_state.get("ib_csv", "").strip():
        raw_text = st.session_state["ib_csv"]

    # PDF takes priority: if a PDF is currently in the uploader AND was successfully
    # parsed, use those scans directly.  We also check _upload_ib_pdf is not None so
    # that removing the file from the uploader automatically falls back to CSV — the
    # session-state cache alone is not sufficient because it persists across reruns
    # even after the file widget is cleared.
    if _upload_ib_pdf is not None and st.session_state.get("ib_pdf_scans"):
        ib_scans = st.session_state["ib_pdf_scans"]
    elif raw_text.strip():
        try:
            ib_scans = parse_inbody_csv_string(raw_text)
        except Exception as exc:
            errors.append(f"InBody parse error: {exc}")
    else:
        errors.append("InBody data missing — paste CSV or PDF in the InBody tab.")

    # ── Build ShapeScale row ──────────────────────────────────────────────────
    # tns_shapescale_reader expects weight in lb and circumferences in inches;
    # convert metric display values back to imperial before passing.
    _ss_in_metric = (st.session_state.get("unit_pref", "Imperial (lb / in)")
                     == "Metric (kg / cm)")
    def _ss_to_lb(v):
        """kg → lb when in metric mode, identity otherwise."""
        return round(float(v) / 0.453592, 4) if _ss_in_metric else float(v)
    def _ss_to_in(v):
        """cm → in when in metric mode, identity otherwise."""
        return round(float(v) / 2.54, 4) if _ss_in_metric else float(v)

    ss_row = {
        "client_id":           client_id,
        "scan_date":           ss_date.strftime("%Y-%m-%d"),
        "weight_lb":           str(_ss_to_lb(ss_weight_lb)),
        "lean_mass_lb":        str(_ss_to_lb(ss_lean_mass)) if ss_lean_mass else "",
        "bmr_cal":             str(int(ss_bmr_cal)) if ss_bmr_cal else "",
        "body_fat_pct":        str(ss_bf_pct),
        "bmi":                 str(ss_bmi),
        "neck_in":             str(_ss_to_in(ss_neck)),
        "shoulders_in":        str(_ss_to_in(ss_shoulders)),
        "chest_in":            str(_ss_to_in(ss_chest)),
        "waist_in":            str(_ss_to_in(ss_waist)),
        "hips_in":             str(_ss_to_in(ss_hips)),
        "bicep_l_in":          str(_ss_to_in(ss_bicep_l)),
        "bicep_r_in":          str(_ss_to_in(ss_bicep_r)),
        "thigh_l_in":          str(_ss_to_in(ss_thigh_l)),
        "thigh_r_in":          str(_ss_to_in(ss_thigh_r)),
        "calf_l_in":           str(_ss_to_in(ss_calf_l)),
        "calf_r_in":           str(_ss_to_in(ss_calf_r)),
        "shape_score":         str(ss_shape_score),
        "health_score":        str(ss_health_score),
        "body_age":            str(ss_body_age),
        "visceral_fat_rating": ss_visc_rating,
        "whr":                 str(ss_whr)  if ss_whr  else "",
        "whtr":                str(ss_whtr) if ss_whtr else "",
    }
    ss_scans = []
    try:
        ss_scans = parse_shapescale_sheet([ss_row])
    except Exception as exc:
        errors.append(f"ShapeScale parse error: {exc}")

    # ── Build lab dict (treat 0 as not provided) ──────────────────────────────
    def _nz(v):
        return float(v) if v and float(v) != 0.0 else None

    lab_data = {
        # Lipids
        "lab_total_chol":    _nz(lab_total_chol),
        "lab_hdl":           _nz(lab_hdl),
        "lab_ldl":           _nz(lab_ldl),
        "lab_triglycerides": _nz(lab_triglycerides),
        "lab_lpa":           _nz(lab_lpa),
        "lab_apob":          _nz(lab_apob),
        # Metabolic
        "lab_glucose":       _nz(lab_glucose),
        "lab_hba1c":         _nz(lab_hba1c),
        "lab_insulin":       _nz(lab_insulin),
        "lab_homa_ir":       _nz(lab_homa_ir),
        # Inflammation
        "lab_hscrp":         _nz(lab_hscrp),
        # BP & HR
        "lab_sbp":           _nz(lab_sbp),
        "lab_dbp":           _nz(lab_dbp),
        "lab_resting_hr":    _nz(lab_resting_hr),
        # Thyroid
        "lab_tsh":           _nz(lab_tsh),
        "lab_free_t3":       _nz(lab_free_t3),
        "lab_free_t4":       _nz(lab_free_t4),
        # Hormones
        "lab_cortisol_am":   _nz(lab_cortisol_am),
        "lab_testosterone":  _nz(lab_testosterone),
        # Iron & Vitamins
        "lab_ferritin":      _nz(lab_ferritin),
        "lab_b12":           _nz(lab_b12),
        "lab_vitamin_d":     _nz(lab_vitamin_d),
        # Kidney
        "lab_egfr":          _nz(lab_egfr),
    }

    # ── Build lifestyle dict (treat 0 as not provided) ────────────────────────
    smoker_encode = {"Never": 0, "Former": 1, "Current": 2}
    lifestyle_data = {
        "lifestyle_vig_min_week":        life_vig   or None,
        "lifestyle_mod_min_week":        life_mod   or None,
        "lifestyle_sed_hours_day":       life_sed   or None,
        "lifestyle_sleep_hours":         life_sleep or None,
        "lifestyle_smoker_score":        smoker_encode.get(life_smoker),
        "lifestyle_alcohol_drinks_week": life_alcohol or None,
        "lifestyle_stress_score":        life_stress or None,
        "lifestyle_subj_health_score":   life_health or None,
    }

    # ── Stop on errors ────────────────────────────────────────────────────────
    if errors:
        for e in errors:
            st.error(e)
        st.stop()

    # ── Reconcile ─────────────────────────────────────────────────────────────
    ib_scan = sorted(ib_scans, key=lambda s: s.get("scan_date", ""))[-1]
    ss_scan = sorted(ss_scans, key=lambda s: s.get("ss_scan_date", ""))[-1]

    with st.spinner("Reconciling scans…"):
        try:
            unified = reconcile_scanners(
                inbody_data     = ib_scan,
                shapescale_data = ss_scan,
                height_cm       = height_cm,
                client_id       = client_id,
                scan_label      = scan_label,
                extra_labs      = lab_data,
                lifestyle_data  = lifestyle_data,
            )
        except Exception as exc:
            st.error(f"Reconcile error: {exc}")
            st.stop()

    # Inject sex so sex-stratified scoring (HDL, body fat, ferritin, etc.) works
    # correctly for female clients.  reconcile_scanners does not receive sex, so
    # we add it here before project_client reads client_data.get("sex").
    unified["sex"] = "male" if sex == "M" else "female"

    # ── Inject questionnaire into unified for Tier C scoring ──────────────────
    # project_client reads client_data.get("questionnaire") and passes it to
    # score_polygon via parse_questionnaire().  "(not provided)" sentinels and
    # slider value 0 are filtered out before injection.
    _Q_NP = "(not provided)"
    _questionnaire_raw: dict = {}
    for _qk, _qv in [
        ("q_activity_hours_per_week",          q_activity_hours_per_week),
        ("q_weight_trend_perception",          q_weight_trend_perception),
        ("q_training_frequency_days_per_week", q_training_frequency_days_per_week),
        ("q_family_history_heart",             q_family_history_heart),
        ("q_smoking",                          q_smoking),
        ("q_alcohol_drinks_per_week",          q_alcohol_drinks_per_week),
        ("q_cv_fitness_stairs_3_flights",      q_cv_fitness_stairs_3_flights),
        ("q_chest_pain_on_exertion",           q_chest_pain_on_exertion),
        ("q_energy_consistency_days_per_week", q_energy_consistency_days_per_week),
        ("q_afternoon_crashes",                q_afternoon_crashes),
        ("q_cold_sensitivity",                 q_cold_sensitivity),
        ("q_libido_past_4_weeks",              q_libido_past_4_weeks),
        ("q_mood_swings_past_4_weeks",         q_mood_swings_past_4_weeks),
        ("q_thermoregulation",                 q_thermoregulation),
        ("q_morning_motivation",               q_morning_motivation),
        ("q_menstrual_regularity",             q_menstrual_regularity),
        ("q_sleep_hours_per_night",            q_sleep_hours_per_night),
        ("q_sleep_quality_rested_days",        q_sleep_quality_rested_days),
        ("q_stress_interference_past_4_weeks", q_stress_interference_past_4_weeks),
        ("q_recovery_time_after_workout",      q_recovery_time_after_workout),
        ("q_overwhelmed",                      q_overwhelmed),
        ("q_training_type",                    q_training_type),
        ("q_daily_steps",                      q_daily_steps),
        ("q_nutrition_whole_food_meals",       q_nutrition_whole_food_meals),
        ("q_hydration_liters_per_day",         q_hydration_liters_per_day),
        ("q_protein_meals_with_palm_serving",  q_protein_meals_with_palm_serving),
    ]:
        if _qv != _Q_NP:
            _questionnaire_raw[_qk] = _qv
    # Slider: 0 means "not provided"; any positive integer is a valid response
    if q_training_intensity_1to10 != 0:
        _questionnaire_raw["q_training_intensity_1to10"] = q_training_intensity_1to10
    if _questionnaire_raw:
        unified["questionnaire"] = _questionnaire_raw

    # ── Load visit history for longitudinal comparison ────────────────────────
    # previous_projections feeds the trajectory timeline chart;
    # baseline_unified feeds the radar overlay comparison vs. intake.
    _visit_hist_all    = st.session_state.get("visit_history", [])
    _visit_hist_client = [h for h in _visit_hist_all if h["client_id"] == client_id]
    # All stored visits for this client EXCEPT the one being generated now.
    _prev_projections = [
        {
            "pc1":            h["result"].get("pc1"),
            "pc2":            h["result"].get("pc2"),
            "percentile_pc1": h["result"].get("percentile_pc1"),
            "date":           h["result"].get("scan_date", h.get("generated_at", "")[:10]),
            "label":          h["scan_label"].upper(),
            "overall_score":  h["result"].get("overall_score"),
        }
        for h in sorted(_visit_hist_client,
                        key=lambda x: x["result"].get("scan_date", x.get("generated_at", "")[:10]))
        if h["scan_label"] != scan_label
    ]

    # Baseline = earliest stored visit (for radar overlay comparison)
    _sorted_hist = sorted(
        _visit_hist_client,
        key=lambda x: x["result"].get("scan_date", x.get("generated_at", "")[:10]),
    )
    _baseline_unified = (
        _sorted_hist[0].get("unified")
        if _sorted_hist and _sorted_hist[0]["scan_label"] != scan_label
        else None
    )

    # ── Project ───────────────────────────────────────────────────────────────
    with st.spinner("Projecting onto Health Map…"):
        try:
            result = project_client(
                client_data    = unified,
                models         = models,
                lens           = lens,
                lab_data       = lab_data,
                lifestyle_data = lifestyle_data,
            )
        except Exception as exc:
            st.error(f"Projection error: {exc}")
            st.stop()

    # ── Stamp scan metadata onto result (project_client doesn't include these) ──
    # Needed so trajectory charts and history display use the actual scan date
    # rather than the time the Health Map was generated.
    result["scan_date"]  = visit_date_input.strftime("%Y-%m-%d")
    result["scan_label"] = scan_label

    # ── Save result to visit history ──────────────────────────────────────────
    # Replace any previous entry for this client + visit label so re-running
    # the same visit always shows the latest result.
    _updated_hist = [
        h for h in st.session_state.get("visit_history", [])
        if not (h["client_id"] == client_id and h["scan_label"] == scan_label)
    ]
    _updated_hist.append({
        "client_id":    client_id,
        "client_name":  client_name,
        "scan_label":   scan_label,
        "generated_at": datetime.datetime.now().isoformat(),
        "result":       result,
        "unified":      unified,
    })
    st.session_state["visit_history"] = _updated_hist

    # ── Generate figures ──────────────────────────────────────────────────────
    saved_figs: dict = {}
    fig_dir = Path(tempfile.mkdtemp())
    with st.spinner("Generating figures…"):
        try:
            saved_figs = generate_client_figures(
                projection_result    = result,
                model                = models[result["lens_used"]],
                client_name          = client_name,
                save_dir             = fig_dir,
                previous_projections = _prev_projections if _prev_projections else None,
                current_unified      = unified,
                baseline_unified     = _baseline_unified,
                sex                  = sex,
                mode                 = "simple",
            )
        except Exception as exc:
            st.warning(f"Figure generation issue: {exc}")

    # ══════════════════════════════════════════════════════════════════════════
    # RESULTS
    # ══════════════════════════════════════════════════════════════════════════
    st.divider()
    dc = result.get("data_completeness", {})

    badge_html = (
        '<span class="badge-full">● Full Data</span>' if dc.get("full_data")
        else '<span class="badge-partial">● Partial Data</span>'
    )
    confidence_badge = {
        "high":     "🟢 High confidence",
        "moderate": "🟡 Moderate confidence",
        "baseline": "⚪ Questionnaire only",
    }.get(result.get("confidence", ""), "")
    confidence_md = f" &nbsp;·&nbsp; {confidence_badge}" if confidence_badge else ""
    st.markdown(
        f"## Results &nbsp; {badge_html}{confidence_md}",
        unsafe_allow_html=True,
    )
    st.caption(
        f"Lens: **{result['lens_used']}** &nbsp;·&nbsp; "
        f"Data: **{result['n_vars_provided']} of {result['n_vars_total']} markers** &nbsp;·&nbsp; "
        f"Scan: {'✓' if dc.get('scan') else '✗'} &nbsp; "
        f"Labs: {'✓' if dc.get('labs') else '✗'} &nbsp; "
        f"Lifestyle: {'✓' if dc.get('lifestyle') else '✗'}"
    )

    # ── Key metrics ───────────────────────────────────────────────────────────
    m1, m2, m3, m4, m5, m6 = st.columns(6)
    m1.metric("Overall Score",   f"{result.get('overall_score', '—')}/100",
              help="Your overall wellness score from 0 to 100. Based on research-backed optimal zones, "
                   "not just how you compare to others.")

    _bf = unified.get('bf_pct')
    m2.metric("Body Fat",        f"{_bf:.1f}%" if _bf is not None else "—%",
              help="Your body fat percentage from scan data. Lower isn't always better — "
                   "healthy range depends on age and sex.")

    _ffmi = unified.get('ffmi')
    m3.metric("FFMI",            f"{_ffmi:.1f}" if _ffmi is not None else "—",
              help="How much muscle you carry for your height. Men: 18–20 is average, 22+ is very muscular. "
                   "Women: 15–17 is average, 19+ is very muscular.")

    _waist = unified.get('ss_waist_cm')
    m4.metric("Waist",           f"{_waist:.1f} cm" if _waist is not None else "— cm",
              help="Waist circumference. A key indicator of belly fat and heart disease risk. "
                   "Men: below 94 cm is healthy. Women: below 80 cm is healthy.")

    _bmi = unified.get('bmi')
    m5.metric("BMI",             f"{_bmi:.1f}" if _bmi is not None else "—",
              help="Body Mass Index. Useful as a general flag, but doesn't distinguish muscle from fat. "
                   "Interpret alongside your body fat % and FFMI.")

    _vfl = unified.get('ib_visceral_fat_level')
    m6.metric("Visceral Fat",    f"L{int(_vfl)}" if _vfl is not None else "—",
              help="Visceral fat level from InBody (the deep belly fat around your organs). "
                   "Level 1–9 is normal. Level 10+ means elevated risk.")

    m7, m8, m9, m10, _, _ = st.columns(6)

    _whr = unified.get('whr')
    m7.metric("WHR",             f"{_whr:.2f}" if _whr is not None else "—",
              help="Waist-to-hip ratio. Healthy: below 0.90 for men, below 0.85 for women. "
                   "Higher values indicate more fat stored around the waist.")

    _pa = unified.get('ib_phase_angle')
    m8.metric("Phase Angle",     f"{_pa:.1f}°" if _pa is not None else "—°",
              help="Cell health indicator from InBody. Higher = healthier cells. "
                   "Typical range: 4–7°. Athletes often score 6–8°.")

    _smm = unified.get('ib_smm_kg')
    m9.metric("SMM",             f"{_smm:.1f} kg" if _smm is not None else "— kg",
              help="Skeletal Muscle Mass — the muscle attached to your bones. "
                   "More SMM means a stronger, more metabolically active body.")

    _ibs = unified.get('ib_score')
    m10.metric("InBody Score",   f"{int(_ibs)}" if _ibs is not None else "—",
               help="Overall body composition score from InBody (0–100). "
                    "Factors in your muscle-to-fat balance and hydration. Higher is better.")

    # ── Cross-scanner flags ───────────────────────────────────────────────────
    for flag in unified.get("flags", []):
        st.warning(flag)

    # ── PAR-Q escalation warning ──────────────────────────────────────────────
    if result.get("par_q_escalation"):
        st.error("⚠️ PAR-Q Escalation: Client reported chest pain on exertion. "
                 "Medical clearance required before exercise programming.")

    # ── Polygon category scores ───────────────────────────────────────────────
    categories = result.get("categories", {})
    if categories:
        st.markdown("### Wellness Polygon Scores")

        CATEGORY_LABELS = {
            "body_composition":   "🏋️ Body Composition",
            "heart_vascular":     "❤️ Heart & Vascular",
            "metabolic_function": "⚡ Metabolic Function",
            "hormonal_balance":   "🔬 Hormonal Balance",
            "stress_recovery":    "🌙 Stress & Recovery",
            "lifestyle_fitness":  "🏃 Lifestyle & Fitness",
        }

        # Human-readable names for model/NHANES variable names.
        # Used in Key Health Drivers and imputed-variables display.
        _DRIVER_LABELS: dict = {
            # Body measures
            "bmi":              "BMI",
            "weight_kg":        "Weight",
            "bf_pct":           "Body Fat %",
            "fat_mass_kg":      "Fat Mass",
            "lean_mass_kg":     "Lean Muscle Mass",
            "ffmi":             "Muscle Mass Index (FFMI)",
            "waist_cm":         "Waist Size",
            "hip_cm":           "Hip Size",
            "thigh_cm":         "Thigh Size",
            "calf_cm":          "Calf Size",
            "arm_cm":           "Arm Size",
            "whr":              "Waist-to-Hip Ratio",
            "whtr":             "Waist-to-Height Ratio",
            "android_fat_pct":  "Belly Fat %",
            "gynoid_fat_pct":   "Hip/Thigh Fat %",
            # Lipids
            "total_chol":       "Total Cholesterol",
            "hdl":              "HDL (good cholesterol)",
            "ldl":              "LDL (bad cholesterol)",
            "triglycerides":    "Triglycerides",
            # Metabolic
            "glucose":          "Blood Sugar (fasting)",
            "hba1c":            "HbA1c (3-month blood sugar avg)",
            "insulin":          "Insulin (fasting)",
            "hscrp":            "Inflammation (hs-CRP)",
            # Blood pressure
            "sbp":              "Systolic Blood Pressure",
            "dbp":              "Diastolic Blood Pressure",
            # Physical activity
            "pa_vig_min_week":  "Vigorous Activity (min/week)",
            "pa_mod_min_week":  "Moderate Activity (min/week)",
            "pa_sed_hours_day": "Sedentary Time (hours/day)",
        }

        cat_cols = st.columns(6)
        for col, (cat_key, cat_data) in zip(cat_cols, categories.items()):
            label = CATEGORY_LABELS.get(cat_key, cat_key)
            score = cat_data.get("score", "—")
            rendering = cat_data.get("rendering", "solid")
            conf = cat_data.get("confidence", "")
            render_icon = "📊" if rendering == "solid" else "📈"
            # Show confidence as a caption below, NOT as delta (delta adds misleading ↑/↓ arrows)
            col.metric(
                label=f"{render_icon} {label.split(' ', 1)[1]}",
                value=f"{score}/100",
                help=f"Data confidence: {conf}. "
                     f"{'Based on your scan + lab data.' if rendering == 'solid' else 'Estimated from available data.'}",
            )
            if conf and conf != "high":
                col.caption(f"🔸 {conf} confidence")

    # ── Missing data notes ────────────────────────────────────────────────────
    notes = result.get("missing_data_notes", [])
    if notes:
        with st.expander(f"ℹ️ {len(notes)} missing data note(s)"):
            for note in notes:
                st.caption(f"• {note}")

    # ── Imputed variables note ────────────────────────────────────────────────
    if result.get("imputed_vars"):
        with st.expander(f"ℹ️ {result['n_vars_imputed']} missing value(s) filled with national averages"):
            _readable_imputed = [_DRIVER_LABELS.get(v, v.replace("_", " ").title())
                                 for v in result["imputed_vars"]]
            st.caption(", ".join(_readable_imputed))

    # ── Progress summary (shown when ≥ 2 visits exist for this client) ──────────
    _all_vis = sorted(
        [h for h in st.session_state.get("visit_history", []) if h["client_id"] == client_id],
        key=lambda x: x["result"].get("scan_date", x.get("generated_at", "")[:10]),
    )
    if len(_all_vis) >= 2:
        st.markdown("### 📈 Progress Across Visits")
        _intake_sc = _all_vis[0]["result"].get("overall_score", 0) or 0
        _prog_cols = st.columns(len(_all_vis))
        for _pc, _hv in zip(_prog_cols, _all_vis):
            _sc  = _hv["result"].get("overall_score", 0) or 0
            _is_curr = _hv["scan_label"] == scan_label
            _delta = f"{_sc - _intake_sc:+.0f} vs intake" if _hv != _all_vis[0] else None
            _pc.metric(
                label   = ("▶ " if _is_curr else "") + _hv["scan_label"].upper(),
                value   = f"{_sc}/100",
                delta   = _delta,
            )
        # Per-category delta table
        _cat_rows: dict[str, list] = {}
        for _hv in _all_vis:
            for _ck, _cd in _hv["result"].get("categories", {}).items():
                _cat_rows.setdefault(_ck, []).append(_cd.get("score", "—"))
        if _cat_rows:
            _CAT_LABELS = {
                "body_composition":   "🏋️ Body Comp",
                "heart_vascular":     "❤️ Heart/Vasc",
                "metabolic_function": "⚡ Metabolic",
                "hormonal_balance":   "🔬 Hormonal",
                "stress_recovery":    "🌙 Stress/Rec",
                "lifestyle_fitness":  "🏃 Lifestyle",
            }
            _tbl_header = "| Category | " + " | ".join(
                v["scan_label"].upper() for v in _all_vis) + " |"
            _tbl_sep = "|---|" + "---|" * len(_all_vis)
            _tbl_rows = []
            for _ck, _scores in _cat_rows.items():
                _row = f"| {_CAT_LABELS.get(_ck, _ck)} | " + " | ".join(
                    f"**{s}**" if i == len(_scores) - 1 else str(s)
                    for i, s in enumerate(_scores)) + " |"
                _tbl_rows.append(_row)
            with st.expander("📋 Category scores by visit", expanded=False):
                st.markdown("\n".join([_tbl_header, _tbl_sep] + _tbl_rows))

    # ── Figures ───────────────────────────────────────────────────────────────
    if saved_figs:
        fig_order = sorted(
            saved_figs.items(),
            key=lambda kv: (0 if "map" in kv[0] else 1 if "radar" in kv[0] else 2)
        )
        for fig_key, fig_path in fig_order:
            if not fig_path.exists():
                continue
            # Map internal figure names to client-friendly labels
            _FIG_LABELS = {
                "loadings": "Variable Importance",
            }
            label = _FIG_LABELS.get(fig_key.split("_")[0], fig_key.replace("_", " ").title())
            expanded = "map" in fig_key or "radar" in fig_key
            with st.expander(f"📊 {label}", expanded=expanded):
                st.image(str(fig_path), use_container_width=True)
                with open(fig_path, "rb") as fh:
                    st.download_button(
                        f"⬇️ Download {fig_path.name}",
                        fh.read(),
                        file_name=fig_path.name,
                        mime="image/png",
                        key=f"dl_{fig_key}",
                    )

    # ── Top drivers ───────────────────────────────────────────────────────────
    with st.expander("📈 Key Health Drivers"):
        top_drivers = result.get("top_drivers", [])
        loadings = result.get("pc1_loadings", {})
        if top_drivers:
            st.caption("The factors with the biggest impact on your overall Health Map position:")
            for var in top_drivers:
                val = loadings.get(var, 0)
                direction = "higher is better" if val > 0 else "lower is better"
                readable = _DRIVER_LABELS.get(var, var.replace("_", " ").title())
                arrow = "🟢" if val > 0 else "🔴"
                st.markdown(f"&nbsp;&nbsp;{arrow} **{readable}** — {direction}")
        else:
            st.caption("No driver data available.")

    # ── JSON report download ──────────────────────────────────────────────────
    st.divider()
    report = {
        "client_id":    client_id,
        "client_name":  client_name,
        "scan_label":   scan_label,
        "generated_at": datetime.datetime.now().isoformat(),
        "projection":   result,
        "key_metrics": {k: unified.get(k) for k in [
            "bf_pct", "bmi", "ffmi", "whr", "whtr",
            "ss_waist_cm", "ib_visceral_fat_level",
            "ib_phase_angle", "ib_score", "ib_smm_kg",
        ]},
        "flags": unified.get("flags", []),
        "overall_score": result.get("overall_score"),
        "confidence": result.get("confidence"),
        "polygon_version": result.get("polygon_version"),
        "library_version": result.get("library_version"),
        "category_scores": {
            name: {
                "score":      cat["score"],
                "rendering":  cat["rendering"],
                "confidence": cat["confidence"],
            }
            for name, cat in result.get("categories", {}).items()
        },
        "par_q_escalation":   result.get("par_q_escalation", False),
        "missing_data_notes": result.get("missing_data_notes", []),
    }
    # ── Client-facing downloads ───────────────────────────────────────────────
    st.caption("📄 **Report Downloads**")
    _dl_col, _save_col = st.columns(2)
    with _dl_col:
        # Placeholder for future PDF report
        st.button(
            "📄 Download PDF Report",
            disabled=True,
            help="PDF report generation coming soon.",
            key="dl_pdf_placeholder",
        )
    with _save_col:
        if st.button("☁️ Save to Project Hub", key="save_drive_btn",
                     help="Save this report (JSON + figures) to TechNSports Project Hub on Google Drive."):
            import shutil as _shutil
            _drive_base = (
                "/Users/jesusgarcia/Library/CloudStorage/"
                "GoogleDrive-jesus.garcia@technsports.mx/"
                "Shared drives/TechNSports Project Hub/"
                "02_MEXICO/PCA_Pipeline/Reports"
            )
            _report_date = visit_date_input.strftime("%Y-%m-%d")
            _report_dir  = Path(_drive_base) / client_id / _report_date
            _report_dir.mkdir(parents=True, exist_ok=True)
            # Save JSON
            _json_path = _report_dir / f"{client_id}_{scan_label}_report.json"
            _json_path.write_text(json.dumps(report, indent=2, default=str))
            # Copy figures
            _figs_saved = []
            for _fk, _fp in saved_figs.items():
                if _fp.exists():
                    _dest = _report_dir / _fp.name
                    _shutil.copy2(_fp, _dest)
                    _figs_saved.append(_fp.name)
            st.success(
                f"✅ Saved to Project Hub: `{_report_dir.relative_to(Path(_drive_base).parent.parent.parent.parent.parent)}`  \n"
                f"JSON + {len(_figs_saved)} figure(s): {', '.join(_figs_saved) or 'none'}"
            )

    # ── Admin / Developer tools ───────────────────────────────────────────────
    with st.expander("🔧 Admin Tools", expanded=False):
        st.download_button(
            "⬇️ Download JSON Report",
            json.dumps(report, indent=2, default=str),
            file_name=f"{client_id}_{scan_label}_report.json",
            mime="application/json",
        )

    # ── Clinical disclaimer footer ─────────────────────────────────────────────
    st.caption(get_report_disclaimer())
