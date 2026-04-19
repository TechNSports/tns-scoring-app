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


# ── Pipeline module loader (cached — imports happen once per session) ─────────
@st.cache_resource(show_spinner=False)
def _load_pipeline():
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
# SIDEBAR — client info + model path
# ════════════════════════════════════════════════════════════════════════════════
with st.sidebar:
    st.markdown("## 🔬 TNS Health Map")
    st.markdown("*TechNSports · Mérida, Yucatán*")
    st.divider()

    st.markdown("### Client")
    client_name = st.text_input("Name", value="Jesus Garcia")
    client_id   = st.text_input("ID (snake_case)", value="garcia_jesus")
    col_s, col_h = st.columns(2)
    with col_s:
        sex = st.selectbox("Sex", ["M", "F"])
    with col_h:
        height_cm = st.number_input("Height cm", 100.0, 250.0, 179.0, 0.5)

    scan_label = st.selectbox("Visit", ["intake", "8wk", "16wk", "24wk"])
    lens       = st.selectbox("Lens", ["auto", "health", "body_comp",
                                        "performance", "weight_mgmt", "longevity"])
    st.divider()

    st.markdown("### Models")
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
# DATA ENTRY TABS
# ════════════════════════════════════════════════════════════════════════════════
tab_ib, tab_ss, tab_labs, tab_life = st.tabs(
    ["🔬 InBody Scan", "📐 ShapeScale Scan", "🩸 Lab Values", "🏃 Lifestyle"]
)

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
        ss_weight_lb    = st.number_input("Weight (lb)",       0.0, 600.0, 215.3, 0.1)
        ss_bf_pct       = st.number_input("Body fat %",        0.0,  70.0,  34.5, 0.1)
        ss_bmi          = st.number_input("BMI",               0.0,  80.0,  33.8, 0.1)
        ss_shape_score  = st.number_input("Shape score",       0,    100,   72,   1)
        ss_health_score = st.number_input("Health score",      0,    100,   65,   1)
        ss_body_age     = st.number_input("Body age",          0,    120,   46,   1)
        ss_visc_rating  = st.selectbox("Visceral fat rating",
                                        ["Very Poor", "Poor", "Fair", "Good", "Excellent"],
                                        index=1)
    with c2:
        st.markdown("**Circumferences (in)**")
        ss_neck      = st.number_input("Neck",        0.0, 60.0, 16.5, 0.1)
        ss_shoulders = st.number_input("Shoulders",   0.0, 90.0, 51.2, 0.1)
        ss_chest     = st.number_input("Chest",       0.0, 80.0, 44.1, 0.1)
        ss_waist     = st.number_input("Waist",       0.0, 80.0, 44.0, 0.1)
        ss_hips      = st.number_input("Hips",        0.0, 80.0, 44.0, 0.1)
    with c3:
        st.markdown("**Limbs (in)**")
        ss_bicep_l  = st.number_input("Bicep L",   0.0, 30.0, 14.8, 0.1)
        ss_bicep_r  = st.number_input("Bicep R",   0.0, 30.0, 15.0, 0.1)
        ss_thigh_l  = st.number_input("Thigh L",   0.0, 50.0, 25.1, 0.1)
        ss_thigh_r  = st.number_input("Thigh R",   0.0, 50.0, 25.3, 0.1)
        ss_calf_l   = st.number_input("Calf L",    0.0, 30.0, 15.9, 0.1)
        ss_calf_r   = st.number_input("Calf R",    0.0, 30.0, 16.1, 0.1)

# ── Labs ──────────────────────────────────────────────────────────────────────
with tab_labs:
    st.markdown("From printed lab report. Leave at **0** for any value not available — it will be imputed from population medians.")
    st.caption("Units: mg/dL for lipids and glucose · % for HbA1c · µIU/mL for insulin · mg/L for hs-CRP · mmHg for BP")

    # ── Preset buttons ────────────────────────────────────────────────────────
    st.markdown("**Quick fill (testing):**")
    pb1, pb2, pb3, _ = st.columns([1, 1, 1, 3])
    with pb1:
        if st.button("🟢 Healthy",   key="preset_lab_h", use_container_width=True):
            st.session_state["_pending_preset"] = "healthy";   st.rerun()
    with pb2:
        if st.button("🟡 Average",   key="preset_lab_a", use_container_width=True):
            st.session_state["_pending_preset"] = "average";   st.rerun()
    with pb3:
        if st.button("🔴 Unhealthy", key="preset_lab_u", use_container_width=True):
            st.session_state["_pending_preset"] = "unhealthy"; st.rerun()
    st.divider()

    lc1, lc2 = st.columns(2)
    with lc1:
        lab_total_chol    = st.number_input("Total Cholesterol (mg/dL)", 0.0, 1000.0, step=1.0,  key="lab_total_chol")
        lab_hdl           = st.number_input("HDL (mg/dL)",               0.0,  500.0, step=1.0,  key="lab_hdl")
        lab_ldl           = st.number_input("LDL (mg/dL)",               0.0,  800.0, step=1.0,  key="lab_ldl")
        lab_triglycerides = st.number_input("Triglycerides (mg/dL)",     0.0, 3000.0, step=1.0,  key="lab_triglycerides")
        lab_glucose       = st.number_input("Glucose fasting (mg/dL)",   0.0,  800.0, step=1.0,  key="lab_glucose")
    with lc2:
        lab_hba1c   = st.number_input("HbA1c (%)",          0.0, 25.0,  step=0.1, key="lab_hba1c")
        lab_insulin = st.number_input("Insulin (µIU/mL)",   0.0, 500.0, step=0.1, key="lab_insulin")
        lab_hscrp   = st.number_input("hs-CRP (mg/L)",      0.0, 200.0, step=0.1, key="lab_hscrp")
        lab_sbp     = st.number_input("Systolic BP (mmHg)", 0.0, 300.0, step=1.0, key="lab_sbp")
        lab_dbp     = st.number_input("Diastolic BP (mmHg)",0.0, 200.0, step=1.0, key="lab_dbp")

# ── Lifestyle ─────────────────────────────────────────────────────────────────
with tab_life:
    st.markdown("From intake form. Leave at **0** for any value not available.")

    # ── Preset buttons ────────────────────────────────────────────────────────
    st.markdown("**Quick fill (testing):**")
    lb1, lb2, lb3, _ = st.columns([1, 1, 1, 3])
    with lb1:
        if st.button("🟢 Healthy",   key="preset_life_h", use_container_width=True):
            st.session_state["_pending_preset"] = "healthy";   st.rerun()
    with lb2:
        if st.button("🟡 Average",   key="preset_life_a", use_container_width=True):
            st.session_state["_pending_preset"] = "average";   st.rerun()
    with lb3:
        if st.button("🔴 Unhealthy", key="preset_life_u", use_container_width=True):
            st.session_state["_pending_preset"] = "unhealthy"; st.rerun()
    st.divider()

    ll1, ll2 = st.columns(2)
    with ll1:
        life_vig    = st.number_input("Vigorous activity (min/week)", 0, 2000, step=10,  key="life_vig")
        life_mod    = st.number_input("Moderate activity (min/week)", 0, 2000, step=10,  key="life_mod")
        life_sed    = st.number_input("Sedentary hours/day",          0.0, 24.0, step=0.5, key="life_sed")
        life_sleep  = st.number_input("Sleep hours/night",            0.0, 24.0, step=0.5, key="life_sleep")
    with ll2:
        life_smoker  = st.selectbox("Smoker status",
                                     ["(not provided)", "Never", "Former", "Current"],
                                     key="life_smoker")
        life_alcohol = st.number_input("Alcohol drinks/week", 0, 100, step=1, key="life_alcohol")
        life_stress  = st.slider("Stress (1–10, 0 = not provided)", 0, 10, key="life_stress")
        life_health  = st.slider("Subjective health (1–10, 0 = not provided)", 0, 10, key="life_health")


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


# ════════════════════════════════════════════════════════════════════════════════
# PIPELINE EXECUTION + RESULTS
# ════════════════════════════════════════════════════════════════════════════════
if run_btn:
    from tns_optimal_zones import (
        assert_clinician_review_complete,
        ClinicalReviewPendingError,
        get_report_disclaimer,
    )
    try:
        assert_clinician_review_complete("app.generate_health_map")
    except ClinicalReviewPendingError as _cpe:
        st.error(
            "⚠️ **Health Map generation is currently disabled.**  "
            "Clinical review of zone thresholds has not been completed, "
            "or the TNS clinical lead has not yet been assigned.  "
            "Contact the TNS team to unlock this feature."
        )
        st.stop()
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
        "lab_total_chol":    _nz(lab_total_chol),
        "lab_hdl":           _nz(lab_hdl),
        "lab_ldl":           _nz(lab_ldl),
        "lab_triglycerides": _nz(lab_triglycerides),
        "lab_glucose":       _nz(lab_glucose),
        "lab_hba1c":         _nz(lab_hba1c),
        "lab_insulin":       _nz(lab_insulin),
        "lab_hscrp":         _nz(lab_hscrp),
        "lab_sbp":           _nz(lab_sbp),
        "lab_dbp":           _nz(lab_dbp),
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
