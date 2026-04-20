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
    st.title("TechNSports Scoring Tool")
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
    before any widgets are instantiated."""
    persona = DEMO_PERSONAS[persona_key]
    for field_key, value in persona["values"].items():
        st.session_state[field_key] = value
    st.session_state["_demo_persona_loaded"] = persona["name"]


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
    st.markdown("## 🔬 TNS Health Map")
    st.markdown("*TechNSports · Mérida, Yucatán*")
    st.divider()

    # ── 1. Client Info (expanded=True) ────────────────────────────────────────
    with st.expander("Client Info", expanded=True):
        client_name = st.text_input("Name", value="Jesus Garcia", key="client_name")
        client_id   = st.text_input("ID (snake_case)", value="garcia_jesus", key="client_id")
        col_s, col_h = st.columns(2)
        with col_s:
            sex = st.selectbox("Sex", ["M", "F"], key="sex")
        with col_h:
            height_cm = st.number_input("Height cm", 100.0, 250.0, 179.0, 0.5, key="height_cm")
        scan_label = st.selectbox("Visit", ["intake", "8wk", "16wk", "24wk"])
        lens       = st.selectbox("Lens", ["auto", "health", "body_comp",
                                            "performance", "weight_mgmt", "longevity"])

    st.divider()

    # ── 2. Models ─────────────────────────────────────────────────────────────
    with st.expander("Models", expanded=False):
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
    with st.expander("🧪 Demo Personas (QA only — remove before launch)", expanded=False):
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
    st.markdown("**Option A — Upload** the CSV from LookinBody Cloud, or **Option B — Paste** the text below.")

    upload_ib = st.file_uploader("Upload InBody CSV", type=["csv"])

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
    st.markdown("Enter values from the ShapeScale app or PDF. Circumferences in **inches**, weight in **pounds**.")

    c1, c2, c3 = st.columns(3)
    with c1:
        ss_date         = st.date_input("Scan date", datetime.date(2026, 4, 13))
        ss_weight_lb    = st.number_input("Weight (lb)",       0.0, 600.0, 215.3, 0.1, key="ss_weight_lb")
        ss_bf_pct       = st.number_input("Body fat %",        0.0,  70.0,  34.5, 0.1, key="ss_bf_pct")
        ss_bmi          = st.number_input("BMI",               0.0,  80.0,  33.8, 0.1, key="ss_bmi")
        ss_shape_score  = st.number_input("Shape score",       0,    100,   72,   1,   key="ss_shape_score")
        ss_health_score = st.number_input("Health score",      0,    100,   65,   1,   key="ss_health_score")
        ss_body_age     = st.number_input("Body age",          0,    120,   46,   1,   key="ss_body_age")
        ss_visc_rating  = st.selectbox("Visceral fat rating",
                                        ["Very Poor", "Poor", "Fair", "Good", "Excellent"],
                                        index=1, key="ss_visc_rating")
    with c2:
        st.markdown("**Circumferences (in)**")
        ss_neck      = st.number_input("Neck",        0.0, 60.0, 16.5, 0.1, key="ss_neck")
        ss_shoulders = st.number_input("Shoulders",   0.0, 90.0, 51.2, 0.1, key="ss_shoulders")
        ss_chest     = st.number_input("Chest",       0.0, 80.0, 44.1, 0.1, key="ss_chest")
        ss_waist     = st.number_input("Waist",       0.0, 80.0, 44.0, 0.1, key="ss_waist")
        ss_hips      = st.number_input("Hips",        0.0, 80.0, 44.0, 0.1, key="ss_hips")
    with c3:
        st.markdown("**Limbs (in)**")
        ss_bicep_l  = st.number_input("Bicep L",   0.0, 30.0, 14.8, 0.1, key="ss_bicep_l")
        ss_bicep_r  = st.number_input("Bicep R",   0.0, 30.0, 15.0, 0.1, key="ss_bicep_r")
        ss_thigh_l  = st.number_input("Thigh L",   0.0, 50.0, 25.1, 0.1, key="ss_thigh_l")
        ss_thigh_r  = st.number_input("Thigh R",   0.0, 50.0, 25.3, 0.1, key="ss_thigh_r")
        ss_calf_l   = st.number_input("Calf L",    0.0, 30.0, 15.9, 0.1, key="ss_calf_l")
        ss_calf_r   = st.number_input("Calf R",    0.0, 30.0, 16.1, 0.1, key="ss_calf_r")

# ── Questionnaire ─────────────────────────────────────────────────────────────
with tab_q:
    st.markdown(
        "Complete the questionnaire below to enable **Tier C** scoring across all six health categories.  \n"
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

st.caption("Labs and Lifestyle values are entered in the sidebar expanders (Lipids, Metabolic, etc.).")


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


# ════════════════════════════════════════════════════════════════════════════════
# PIPELINE EXECUTION + RESULTS
# ════════════════════════════════════════════════════════════════════════════════
if run_btn:
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

    if raw_text.strip():
        try:
            ib_scans = parse_inbody_csv_string(raw_text)
        except Exception as exc:
            errors.append(f"InBody parse error: {exc}")
    else:
        errors.append("InBody data missing — paste CSV text or upload a file in the InBody tab.")

    # ── Build ShapeScale row ──────────────────────────────────────────────────
    ss_row = {
        "client_id":           client_id,
        "scan_date":           ss_date.strftime("%Y-%m-%d"),
        "weight_lb":           str(ss_weight_lb),
        "body_fat_pct":        str(ss_bf_pct),
        "bmi":                 str(ss_bmi),
        "neck_in":             str(ss_neck),
        "shoulders_in":        str(ss_shoulders),
        "chest_in":            str(ss_chest),
        "waist_in":            str(ss_waist),
        "hips_in":             str(ss_hips),
        "bicep_l_in":          str(ss_bicep_l),
        "bicep_r_in":          str(ss_bicep_r),
        "thigh_l_in":          str(ss_thigh_l),
        "thigh_r_in":          str(ss_thigh_r),
        "calf_l_in":           str(ss_calf_l),
        "calf_r_in":           str(ss_calf_r),
        "shape_score":         str(ss_shape_score),
        "health_score":        str(ss_health_score),
        "body_age":            str(ss_body_age),
        "visceral_fat_rating": ss_visc_rating,
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
                previous_projections = None,
                current_unified      = unified,
                baseline_unified     = None,
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
        f"Coverage: **{result['n_vars_provided']}/{result['n_vars_total']} vars** &nbsp;·&nbsp; "
        f"Scan: {'✓' if dc.get('scan') else '✗'} &nbsp; "
        f"Labs: {'✓' if dc.get('labs') else '✗'} &nbsp; "
        f"Lifestyle: {'✓' if dc.get('lifestyle') else '✗'}"
    )

    # ── Key metrics ───────────────────────────────────────────────────────────
    m1, m2, m3, m4, m5, m6 = st.columns(6)
    m1.metric("Overall Score",   f"{result.get('overall_score', '—')}/100",
              help="Wellness Polygon overall score (0=all concerning, 100=all optimal). "
                   "Scored against research-based optimal zones, not population percentiles.")
    m2.metric("Body Fat",        f"{unified.get('bf_pct', '—')}%",
              help="Percent body fat from reconciled scan data.")
    m3.metric("FFMI",            f"{unified.get('ffmi', '—')}",
              help="Fat-Free Mass Index (kg/m²). Reflects lean mass relative to height.")
    m4.metric("Waist",           f"{unified.get('ss_waist_cm', '—')} cm",
              help="Waist circumference from ShapeScale (cm). Key cardiometabolic risk marker.")
    m5.metric("BMI",             f"{unified.get('bmi', '—')}",
              help="Body Mass Index (kg/m²). Contextual — interpret alongside body composition.")
    m6.metric("Visceral Fat",    f"L{unified.get('ib_visceral_fat_level') or '—'}",
              help="Visceral fat level from InBody. Level 10+ indicates elevated risk.")

    m7, m8, m9, m10, _, _ = st.columns(6)
    m7.metric("WHR",             f"{unified.get('whr', '—')}")
    m8.metric("Phase Angle",     f"{unified.get('ib_phase_angle', '—')}°")
    m9.metric("SMM",             f"{unified.get('ib_smm_kg', '—')} kg")
    m10.metric("InBody Score",   f"{unified.get('ib_score', '—')}")

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

        cat_cols = st.columns(6)
        for col, (cat_key, cat_data) in zip(cat_cols, categories.items()):
            label = CATEGORY_LABELS.get(cat_key, cat_key)
            score = cat_data.get("score", "—")
            rendering = cat_data.get("rendering", "solid")
            conf = cat_data.get("confidence", "")
            render_icon = "📊" if rendering == "solid" else "📈"
            col.metric(
                label=f"{render_icon} {label.split(' ', 1)[1]}",
                value=f"{score}/99",
                delta=conf if conf != "high" else None,
                help=f"Rendering: {rendering}. Confidence: {conf}."
            )

    # ── Missing data notes ────────────────────────────────────────────────────
    notes = result.get("missing_data_notes", [])
    if notes:
        with st.expander(f"ℹ️ {len(notes)} data gap note(s)"):
            for note in notes:
                st.caption(f"• {note}")

    # ── Imputed variables note ────────────────────────────────────────────────
    if result.get("imputed_vars"):
        with st.expander(f"ℹ️ {result['n_vars_imputed']} variable(s) imputed from population medians"):
            st.caption(", ".join(result["imputed_vars"]))

    # ── Figures ───────────────────────────────────────────────────────────────
    if saved_figs:
        fig_order = sorted(
            saved_figs.items(),
            key=lambda kv: (0 if "map" in kv[0] else 1 if "radar" in kv[0] else 2)
        )
        for fig_key, fig_path in fig_order:
            if not fig_path.exists():
                continue
            label = fig_key.replace("_", " ").title()
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
    with st.expander("📈 Top PC1 drivers"):
        loadings = result.get("pc1_loadings", {})
        for var in result.get("top_drivers", []):
            val = loadings.get(var, 0)
            arrow = "▲" if val > 0 else "▼"
            st.markdown(f"&nbsp;&nbsp;{arrow} `{var}` &nbsp; {val:+.4f}")

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
    st.download_button(
        "⬇️ Download JSON Report",
        json.dumps(report, indent=2, default=str),
        file_name=f"{client_id}_{scan_label}_report.json",
        mime="application/json",
    )

    # ── Clinical disclaimer footer ─────────────────────────────────────────────
    st.caption(get_report_disclaimer())
