# CODE_OUTPUT — v1.0.3 Clinician-Supervised Render Reframe
**Date:** 2026-04-18
**Files patched:** `tns_optimal_zones.py`, `tns_polygon_scorer.py`, `tns_visualize.py`, `tns_pca_pipeline.py`, `app.py`
**Files rewritten:** `tests/test_client_facing_gate.py`
**Version:** `1.0.2-public` → `1.0.3-public`
**Test result:** 93/94 PASS (15 new gate tests + 58 polygon scorer + 21 project_client; 1 pre-existing failure, same as v1.0.2)

---

## 1. Version Confirmation

```
LIBRARY_VERSION = "1.0.3-public"
POLYGON_VERSION = "4.1"          # unchanged
```

---

## 2. Purpose

v1.0.3 reframes the render gate from a binary "is this ready to ship to consumers" flag into a semantically accurate "is this report being reviewed with a licensed clinical lead" flag. The architecture is unchanged — the gate is still one boolean, still blocks rendering when False, still bypassed by `TNS_ALLOW_DEV_RENDER=1` in tests. What changed:

1. **Names** — every identifier that said "client_facing" or "ClientFacingBlocked" now says "clinician_supervised_render" or "ClinicalReviewPending".
2. **New constants** — `CLINICAL_LEAD_NAME` and `CLINICAL_LEAD_CREDENTIAL` must be set before the gate can be flipped True. Module-level and call-time assertions enforce this.
3. **Layperson strings** — all "talk to your coach / discuss with your doctor / seek guidance" suffixes stripped and replaced with direct clinical descriptions.
4. **Report disclaimer** — `get_report_disclaimer()` added; wired into the polygon score dict, all figure footers, and the Streamlit results caption.

---

## 3. CHANGE-01: Gate Rename — All Sites

### New constants in `tns_optimal_zones.py`

```python
CLINICIAN_SUPERVISED_RENDER: bool = False
# Set to True ONLY after the TNS clinical lead has reviewed and signed off on
# all thresholds in this library version.  This flag is flipped once per
# library version, not per individual report.

CLINICAL_LEAD_NAME: str = "PENDING_ASSIGNMENT"
# Full name of the TNS-licensed clinical lead who has reviewed this library
# version (e.g. "Dr. María López Hernández").

CLINICAL_LEAD_CREDENTIAL: str = "PENDING_ASSIGNMENT"
# Professional credential of the clinical lead
# (e.g. "Nutriólogo Clínico" or "Médico Cirujano").
```

### Startup assertion (fires at import time)

```python
if CLINICIAN_SUPERVISED_RENDER:
    if (CLINICAL_LEAD_NAME == "PENDING_ASSIGNMENT"
            or CLINICAL_LEAD_CREDENTIAL == "PENDING_ASSIGNMENT"):
        raise ClinicalReviewPendingError(
            "CLINICIAN_SUPERVISED_RENDER is True but CLINICAL_LEAD_NAME or "
            "CLINICAL_LEAD_CREDENTIAL is still 'PENDING_ASSIGNMENT'. "
            "Assign both constants before flipping the render gate."
        )
```

### Guard function

```python
class ClinicalReviewPendingError(RuntimeError):
    """Raised when a client-facing render is attempted before clinical sign-off."""

def assert_clinician_review_complete(context: str) -> None:
    import os
    if CLINICIAN_SUPERVISED_RENDER:
        if (CLINICAL_LEAD_NAME == "PENDING_ASSIGNMENT"
                or CLINICAL_LEAD_CREDENTIAL == "PENDING_ASSIGNMENT"):
            raise ClinicalReviewPendingError(
                f"CLINICIAN_SUPERVISED_RENDER is True but CLINICAL_LEAD_NAME or "
                f"CLINICAL_LEAD_CREDENTIAL is still 'PENDING_ASSIGNMENT'. "
                f"Set both constants before rendering client reports."
            )
        return
    if os.environ.get("TNS_ALLOW_DEV_RENDER") == "1":
        return
    raise ClinicalReviewPendingError(
        f"Clinical review not yet complete; rendering blocked at: {context}. "
        f"Flip CLINICIAN_SUPERVISED_RENDER = True only after the TNS clinical lead "
        f"has reviewed all thresholds and CLINICAL_LEAD_NAME / "
        f"CLINICAL_LEAD_CREDENTIAL have been set. "
        f"For local dev previews, set TNS_ALLOW_DEV_RENDER=1."
    )
```

### Rename summary table

| Old name | New name | File(s) |
|---|---|---|
| `CLIENT_FACING` | `CLINICIAN_SUPERVISED_RENDER` | `tns_optimal_zones.py` |
| `ClientFacingBlockedError` | `ClinicalReviewPendingError` | `tns_optimal_zones.py`, importers |
| `assert_client_facing_allowed()` | `assert_clinician_review_complete()` | all files |
| `assert_client_facing_allowed("tns_polygon_scorer.score_polygon")` | `assert_clinician_review_complete("tns_polygon_scorer.score_polygon")` | `tns_polygon_scorer.py` |
| `assert_client_facing_allowed("tns_visualize.plot_population_map")` | `assert_clinician_review_complete("tns_visualize.plot_population_map")` | `tns_visualize.py` |
| `assert_client_facing_allowed("tns_visualize.plot_loadings_bar")` | `assert_clinician_review_complete("tns_visualize.plot_loadings_bar")` | `tns_visualize.py` |
| `assert_client_facing_allowed("tns_visualize.plot_trajectory_timeline")` | `assert_clinician_review_complete("tns_visualize.plot_trajectory_timeline")` | `tns_visualize.py` |
| `assert_client_facing_allowed("tns_visualize.plot_radar_overlay")` | `assert_clinician_review_complete("tns_visualize.plot_radar_overlay")` | `tns_visualize.py` |
| `assert_client_facing_allowed("tns_visualize.generate_client_figures")` | `assert_clinician_review_complete("tns_visualize.generate_client_figures")` | `tns_visualize.py` |
| `assert_client_facing_allowed("tns_pca_pipeline.project_client")` | `assert_clinician_review_complete("tns_pca_pipeline.project_client")` | `tns_pca_pipeline.py` |
| `assert_client_facing_allowed("app.generate_health_map")` | `assert_clinician_review_complete("app.generate_health_map")` | `app.py` |

### Import diffs per file

**`tns_polygon_scorer.py`**
```python
# BEFORE
from tns_optimal_zones import (
    LIBRARY_VERSION, POLYGON_VERSION, score_biomarker,
    get_derived_biomarkers, assert_client_facing_allowed,
)
# AFTER
from tns_optimal_zones import (
    LIBRARY_VERSION, POLYGON_VERSION, score_biomarker,
    get_derived_biomarkers, assert_clinician_review_complete, get_report_disclaimer,
)
```

**`tns_visualize.py`**
```python
# BEFORE
from tns_optimal_zones import assert_client_facing_allowed, ClientFacingBlockedError  # noqa: F401
# AFTER
from tns_optimal_zones import (  # noqa: F401
    assert_clinician_review_complete,
    ClinicalReviewPendingError,
    get_report_disclaimer,
)
```

**`tns_pca_pipeline.py`**
```python
# BEFORE
from tns_optimal_zones import assert_client_facing_allowed, ClientFacingBlockedError  # noqa: F401
# AFTER
from tns_optimal_zones import assert_clinician_review_complete, ClinicalReviewPendingError  # noqa: F401
```

**`app.py`**
```python
# BEFORE
from tns_optimal_zones import assert_client_facing_allowed, ClientFacingBlockedError
try:
    assert_client_facing_allowed("app.generate_health_map")
except ClientFacingBlockedError as _cfe:
    st.error("⚠️ **Health Map generation is currently disabled.**  "
             "Clinical review of zone thresholds has not been completed.  "
             "Contact the TNS team to unlock this feature.")
    st.stop()
# AFTER
from tns_optimal_zones import (
    assert_clinician_review_complete,
    ClinicalReviewPendingError,
    get_report_disclaimer,
)
try:
    assert_clinician_review_complete("app.generate_health_map")
except ClinicalReviewPendingError as _cpe:
    st.error("⚠️ **Health Map generation is currently disabled.**  "
             "Clinical review of zone thresholds has not been completed, "
             "or the TNS clinical lead has not yet been assigned.  "
             "Contact the TNS team to unlock this feature.")
    st.stop()
```

---

## 4. CHANGE-02: Layperson Strings — Complete Before/After

All strings in the **concerning** zone (and two suboptimal overrides for `lp_a` and `egfr`) were updated to remove "talk to your coach / discuss with your coach / seek guidance / work with your coach" redirections. Replaced with direct clinical descriptions that the clinician present in the room can contextualize.

Strings flagged **[PM REVIEW]** below contain clinical interpretive language that the assigned clinical lead should verify before `CLINICIAN_SUPERVISED_RENDER` is flipped True.

---

### 1. HDL *(done in prior session)*

| | EN | ES |
|---|---|---|
| **BEFORE** | "Your HDL needs attention. Talk to your coach about next steps." | "Tu HDL necesita atención. Habla con tu coach sobre los próximos pasos." |
| **AFTER** | "Your HDL is significantly below optimal — a key cardiovascular risk factor." | "Tu HDL está significativamente por debajo del óptimo — un factor de riesgo cardiovascular clave." |

---

### 2. Total Cholesterol (concerning)

| | EN | ES |
|---|---|---|
| **BEFORE** | "Your total cholesterol is very high or very low. Seek guidance soon." | "Tu colesterol total es muy alto o muy bajo. Busca orientación pronto." |
| **AFTER** | "Your total cholesterol is outside the safe range — either very high (≥240) or very low (<130 mg/dL)." | "Tu colesterol total está fuera del rango seguro — muy alto (≥240) o muy bajo (<130 mg/dL)." |

---

### 3. LDL (concerning)

| | EN | ES |
|---|---|---|
| **BEFORE** | "Your LDL is high. Work with your coach on a reduction plan." | "Tu LDL es alto. Trabaja con tu coach en un plan de reducción." |
| **AFTER** | "Your LDL is high — a primary driver of cardiovascular risk. Reducing saturated fat and refined carbs is the key lever." | "Tu LDL es alto — impulsor principal del riesgo cardiovascular. Reducir grasas saturadas y carbohidratos refinados es la palanca clave." |

---

### 4. Non-HDL (concerning)

| | EN | ES |
|---|---|---|
| **BEFORE** | "Your non-HDL is high. Prioritize this with your coach." | "Tu colesterol no-HDL es alto. Prioriza esto con tu coach." |
| **AFTER** | "Your non-HDL is high — elevated atherogenic particle burden. Diet and activity are the primary levers." | "Tu colesterol no-HDL es alto — carga aterogénica elevada. La dieta y la actividad son las palancas principales." |

---

### 5. Triglycerides (concerning)

| | EN | ES |
|---|---|---|
| **BEFORE** | "Your triglycerides are high. Discuss a nutrition plan with your coach." | "Tus triglicéridos son altos. Habla con tu coach sobre un plan nutricional." |
| **AFTER** | "Your triglycerides are very high. Reducing refined carbs, added sugars, and alcohol are the primary levers." | "Tus triglicéridos son muy altos. Reducir carbohidratos refinados, azúcares añadidos y alcohol son las palancas principales." |

---

### 6. Fasting Glucose (concerning)

| | EN | ES |
|---|---|---|
| **BEFORE** | "Your fasting glucose is too high or too low. Prioritize this with your coach." | "Tu glucosa en ayunas está fuera de rango. Prioriza esto con tu coach." |
| **AFTER** | "Your fasting glucose is outside the safe range — elevated (≥110 mg/dL) or hypoglycemic (<60 mg/dL)." | "Tu glucosa en ayunas está fuera del rango seguro — elevada (≥110 mg/dL) o hipoglucémica (<60 mg/dL)." |

---

### 7. HbA1c (concerning)

| | EN | ES |
|---|---|---|
| **BEFORE** | "Your HbA1c is high. Work with your coach on a blood sugar plan." | "Tu HbA1c es alto. Trabaja con tu coach en un plan de azúcar en sangre." |
| **AFTER** | "Your HbA1c indicates poor long-term blood sugar control — in the diabetes threshold range." | "Tu HbA1c indica un control deficiente del azúcar a largo plazo — en el umbral de diabetes." |

---

### 8. Fasting Insulin (concerning)

| | EN | ES |
|---|---|---|
| **BEFORE** | "Your insulin is very high or very low. Discuss this with your coach." | "Tu insulina está muy alta o muy baja. Habla con tu coach." |
| **AFTER** | "Your insulin is hyperinsulinemic (>21 µIU/mL) or abnormally low (<2 µIU/mL)." | "Tu insulina es hiperinsulinémica (>21 µIU/mL) o anormalmente baja (<2 µIU/mL)." |

---

### 9. HOMA-IR (concerning)

| | EN | ES |
|---|---|---|
| **BEFORE** | "Your HOMA-IR indicates significant insulin resistance. Act with your coach." | "Tu HOMA-IR indica resistencia significativa a la insulina. Actúa con tu coach." |
| **AFTER** | "Your HOMA-IR indicates significant insulin resistance — a major metabolic risk factor requiring structured intervention." | "Tu HOMA-IR indica resistencia significativa a la insulina — un factor de riesgo metabólico importante que requiere intervención estructurada." |

---

### 10. hs-CRP (concerning)

| | EN | ES |
|---|---|---|
| **BEFORE** | "Your inflammation marker is high. Discuss recovery strategies with your coach." | "Tu marcador de inflamación es alto. Habla con tu coach sobre estrategias de recuperación." |
| **AFTER** | "Your inflammation marker is high — chronic low-grade inflammation warranting investigation of sleep, diet, and stress load." | "Tu marcador de inflamación es alto — inflamación crónica de bajo grado que requiere investigar sueño, dieta y carga de estrés." |

---

### 11. TSH (concerning) **[PM REVIEW]**

| | EN | ES |
|---|---|---|
| **BEFORE** | "Your thyroid is significantly outside range. Follow up with your coach." | "Tu tiroides está significativamente fuera de rango. Consulta con tu coach." |
| **AFTER** | "Your thyroid is significantly outside reference range — requires full thyroid panel review." | "Tu tiroides está significativamente fuera del rango de referencia — requiere revisión del panel tiroideo completo." |

> **Flag:** The phrase "requires full thyroid panel review" implies a clinical action. Clinical lead should confirm whether this phrasing is appropriate for in-session delivery given Mexican NOM guidelines.

---

### 12. Free T3 (concerning) **[PM REVIEW]**

| | EN | ES |
|---|---|---|
| **BEFORE** | "Your active thyroid hormone is significantly outside range. Discuss with your coach." | "Tu hormona tiroidea activa está significativamente fuera. Consulta con tu coach." |
| **AFTER** | "Your active thyroid hormone is significantly outside reference range — requires thyroid panel review." | "Tu hormona tiroidea activa está significativamente fuera del rango de referencia — requiere revisión del panel tiroideo." |

> **Flag:** Same as TSH — clinical lead to confirm.

---

### 13. Free T4 (concerning) **[PM REVIEW]**

| | EN | ES |
|---|---|---|
| **BEFORE** | "Your T4 is significantly outside range. Follow up with your coach." | "Tu T4 está significativamente fuera de rango. Consulta con tu coach." |
| **AFTER** | "Your T4 is significantly outside reference range — requires thyroid panel review." | "Tu T4 está significativamente fuera del rango de referencia — requiere revisión del panel tiroideo." |

> **Flag:** Same as TSH — clinical lead to confirm.

---

### 14. Vitamin D (concerning)

| | EN | ES |
|---|---|---|
| **BEFORE** | "Your vitamin D is very low. Discuss a supplement plan with your coach." | "Tu vitamina D es muy baja. Habla con tu coach sobre un plan de suplementación." |
| **AFTER** | "Your vitamin D is very low — deficiency impairs bone health, immunity, and mood. A supplementation protocol is indicated." | "Tu vitamina D es muy baja — la deficiencia deteriora la salud ósea, la inmunidad y el estado de ánimo. Está indicado un protocolo de suplementación." |

---

### 15. Vitamin B12 (concerning)

| | EN | ES |
|---|---|---|
| **BEFORE** | "Your B12 is very low. Deficiency affects energy and nerves. Act now." | "Tu B12 es muy bajo. La deficiencia afecta energía y nervios. Actúa ya." |
| **AFTER** | "Your B12 is very low — deficiency impairs nerve function and red blood cell production. Supplementation is indicated." | "Tu B12 es muy bajo — la deficiencia deteriora la función nerviosa y la producción de glóbulos rojos. La suplementación está indicada." |

> Note: This string didn't have coach-referral language in v1.0.2 but was updated to match the clinical description standard.

---

### 16. Ferritin (concerning) **[PM REVIEW]**

| | EN | ES |
|---|---|---|
| **BEFORE** | "Your iron stores are too low or too high. Discuss with your coach." | "Tus reservas de hierro son muy bajas o muy altas. Habla con tu coach." |
| **AFTER** | "Your iron stores are very low or very high — very low impairs oxygen transport; very high may warrant further workup." | "Tus reservas de hierro son muy bajas o muy altas — muy bajas deterioran el transporte de oxígeno; muy altas pueden requerir evaluación adicional." |

> **Flag:** "May warrant further workup" for high ferritin implies hemochromatosis screening. Clinical lead to confirm whether this is within scope.

---

### 17. Total Testosterone (concerning) **[PM REVIEW]**

| | EN | ES |
|---|---|---|
| **BEFORE** | "Your testosterone is significantly outside range. Work with your coach on next steps." | "Tu testosterona está significativamente fuera de rango. Trabaja con tu coach." |
| **AFTER** | "Your testosterone is either deficient or supraphysiologic — significantly outside the reference range." | "Tu testosterona es deficiente o suprafisiológica — significativamente fuera del rango de referencia." |

> **Flag:** "Supraphysiologic" is accurate but may alarm clients in performance contexts. Clinical lead to decide whether this term is appropriate for the session context.

---

### 18. Morning Cortisol (concerning) **[PM REVIEW]**

| | EN | ES |
|---|---|---|
| **BEFORE** | "Your morning cortisol is significantly off. Discuss recovery with your coach." | "Tu cortisol matutino está significativamente fuera. Habla con tu coach sobre recuperación." |
| **AFTER** | "Your morning cortisol is significantly outside range — very low may suggest adrenal insufficiency; very high may reflect chronic stress or HPA dysregulation." | "Tu cortisol matutino está significativamente fuera de rango — muy bajo puede indicar insuficiencia adrenal; muy alto puede reflejar estrés crónico o desregulación del eje HPA." |

> **Flag:** "Adrenal insufficiency" and "HPA dysregulation" are clinical terms. Clinical lead to confirm whether these terms are appropriate for in-session delivery.

---

### 19. Systolic Blood Pressure (concerning)

| | EN | ES |
|---|---|---|
| **BEFORE** | "Your systolic blood pressure is very high or very low. Prioritize this with your coach." | "Tu presión sistólica es muy alta o muy baja. Prioriza esto con tu coach." |
| **AFTER** | "Your systolic blood pressure is hypertensive (≥140 mmHg) or hypotensive (<85 mmHg)." | "Tu presión sistólica está en rango hipertensivo (≥140 mmHg) o hipotensivo (<85 mmHg)." |

---

### 20. Diastolic Blood Pressure (concerning)

| | EN | ES |
|---|---|---|
| **BEFORE** | "Your diastolic blood pressure is very high or very low. Talk to your coach." | "Tu presión diastólica es muy alta o muy baja. Habla con tu coach." |
| **AFTER** | "Your diastolic blood pressure is hypertensive (≥90 mmHg) or hypotensive (<55 mmHg)." | "Tu presión diastólica está en rango hipertensivo (≥90 mmHg) o hipotensivo (<55 mmHg)." |

---

### 21. TG/HDL Ratio (concerning)

| | EN | ES |
|---|---|---|
| **BEFORE** | "Your TG/HDL ratio is high — a key insulin resistance marker. Discuss with your coach." | "Tu relación TG/HDL es alta, marcador clave de resistencia a insulina. Habla con tu coach." |
| **AFTER** | "Your TG/HDL ratio is high — a key marker of insulin resistance and cardiovascular risk. Reducing refined carbs and increasing activity are the primary levers." | "Tu relación TG/HDL es alta — marcador clave de resistencia a la insulina y riesgo cardiovascular. Reducir carbohidratos refinados y aumentar la actividad son las palancas principales." |

---

### 22. Lp(a) — suboptimal (also updated)

| | EN | ES |
|---|---|---|
| **BEFORE** | "Your Lp(a) is moderately elevated. Discuss lifestyle strategies with your coach." | "Tu Lp(a) está moderadamente elevado. Habla con tu coach sobre estrategias." |
| **AFTER** | "Your Lp(a) is moderately elevated — largely genetic, but optimizing LDL and inflammatory load can help." | "Tu Lp(a) está moderadamente elevado — en gran parte genético, pero optimizar el LDL y la carga inflamatoria puede ayudar." |

### Lp(a) — concerning (also updated)

| | EN | ES |
|---|---|---|
| **BEFORE** | "Your Lp(a) is high — a genetic risk marker. Track it closely with your coach." | "Tu Lp(a) es alto, marcador de riesgo genético. Monitoréalo con tu coach." |
| **AFTER** | "Your Lp(a) is high — a genetically-driven cardiovascular risk marker. Lifestyle modifications have limited impact; focus on overall cardiovascular risk reduction." | "Tu Lp(a) es alto — marcador de riesgo cardiovascular de origen genético. Las modificaciones de estilo de vida tienen impacto limitado; enfócate en reducir el riesgo cardiovascular general." |

---

### 23. ApoB (concerning)

| | EN | ES |
|---|---|---|
| **BEFORE** | "Your ApoB is high. Work with your coach on a targeted reduction plan." | "Tu ApoB es alto. Trabaja con tu coach en un plan de reducción específico." |
| **AFTER** | "Your ApoB is high — a strong predictor of cardiovascular events. Reducing LDL particle concentration through diet and exercise is the primary target." | "Tu ApoB es alto — predictor fuerte de eventos cardiovasculares. Reducir la concentración de partículas LDL mediante dieta y ejercicio es el objetivo principal." |

---

### 24. eGFR — suboptimal (also updated)

| | EN | ES |
|---|---|---|
| **BEFORE** | "Your kidney filtration is slightly reduced. Discuss with your coach." | "Tu filtración renal está ligeramente reducida. Habla con tu coach." |
| **AFTER** | "Your kidney filtration is slightly reduced. Stay well hydrated, limit NSAIDs, and monitor blood pressure." | "Tu filtración renal está ligeramente reducida. Mantente bien hidratado, limita los AINEs y monitorea tu presión arterial." |

### eGFR — concerning **[PM REVIEW]**

| | EN | ES |
|---|---|---|
| **BEFORE** | "Your kidney filtration is significantly reduced. Seek guidance promptly." | "Tu filtración renal está significativamente reducida. Busca orientación pronto." |
| **AFTER** | "Your kidney filtration is significantly reduced — consistent with CKD Stage 3 or higher. Ongoing monitoring and dietary management are indicated." | "Tu filtración renal está significativamente reducida — compatible con ERC grado 3 o superior. El monitoreo continuo y el manejo dietético están indicados." |

> **Flag:** "CKD Stage 3" is a diagnostic category under KDIGO staging. Verify with clinical lead whether this classification is appropriate to present in-session.

---

## 5. CHANGE-03: Report Disclaimer Footer

### New helper in `tns_optimal_zones.py`

```python
def get_report_disclaimer() -> str:
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
```

### `tns_polygon_scorer.py` — `disclaimer` key added to `score_polygon()` return dict

```python
return {
    ...
    "missing_data_notes":  deduped_notes,
    "disclaimer":          get_report_disclaimer(),   # ← new
}
```

### `tns_visualize.py` — `_add_disclaimer_footer()` helper + calls before each savefig

```python
def _add_disclaimer_footer(fig: plt.Figure) -> None:
    """Stamp the clinical review disclaimer at the bottom of a figure."""
    text = get_report_disclaimer()
    fig.text(
        0.5, 0.005, text,
        ha="center", va="bottom",
        fontsize=6, color=GREY_MED,
        wrap=True,
        transform=fig.transFigure,
    )
```

Called immediately before `fig.savefig()` in:
- `plot_population_map()`
- `plot_loadings_bar()`
- `plot_trajectory_timeline()`
- `plot_radar_overlay()`

### `app.py` — `st.caption()` after JSON download button

```python
st.download_button("⬇️ Download JSON Report", ...)

# ── Clinical disclaimer footer ─────────────────────────────────────────────
st.caption(get_report_disclaimer())
```

---

## 6. CHANGE-04: Test File — `tests/test_client_facing_gate.py`

Full rewrite. 15 tests (vs. 11 in v1.0.2):

| Test | What it covers |
|---|---|
| `test_guard_passes_when_clinician_supervised_render_true` | Gate True + both lead constants assigned → no raise |
| `test_guard_raises_when_flag_false_and_no_env_var` | Gate False + no env var → ClinicalReviewPendingError with context string |
| `test_guard_bypassed_by_env_var` | TNS_ALLOW_DEV_RENDER="1" → no raise |
| `test_guard_not_bypassed_by_non_one_env_var[0…]` | 7 bad env values → all raise (parametrized) |
| `test_score_polygon_raises_when_clinical_review_pending` | End-to-end: score_polygon raises with "tns_polygon_scorer.score_polygon" in message |
| `test_guard_raises_when_clinical_lead_pending` | Gate True + both constants PENDING → raises with "PENDING_ASSIGNMENT" in message |
| `test_guard_raises_when_only_name_pending` | Gate True + only name PENDING → raises |
| `test_guard_raises_when_only_credential_pending` | Gate True + only credential PENDING → raises |
| `test_guard_passes_when_clinical_lead_assigned` | Gate True + both assigned → returns None |

---

## 7. Test Results

```
============================= test session starts ==============================
platform darwin -- Python 3.9.13, pytest-7.1.2
collected 94 items

tests/test_client_facing_gate.py::test_guard_passes_when_clinician_supervised_render_true PASSED
tests/test_client_facing_gate.py::test_guard_raises_when_flag_false_and_no_env_var PASSED
tests/test_client_facing_gate.py::test_guard_bypassed_by_env_var PASSED
tests/test_client_facing_gate.py::test_guard_not_bypassed_by_non_one_env_var[0] PASSED
tests/test_client_facing_gate.py::test_guard_not_bypassed_by_non_one_env_var[yes] PASSED
tests/test_client_facing_gate.py::test_guard_not_bypassed_by_non_one_env_var[true] PASSED
tests/test_client_facing_gate.py::test_guard_not_bypassed_by_non_one_env_var[True] PASSED
tests/test_client_facing_gate.py::test_guard_not_bypassed_by_non_one_env_var[1 ] PASSED
tests/test_client_facing_gate.py::test_guard_not_bypassed_by_non_one_env_var[ 1] PASSED
tests/test_client_facing_gate.py::test_guard_not_bypassed_by_non_one_env_var[] PASSED
tests/test_client_facing_gate.py::test_score_polygon_raises_when_clinical_review_pending PASSED
tests/test_client_facing_gate.py::test_guard_raises_when_clinical_lead_pending PASSED
tests/test_client_facing_gate.py::test_guard_raises_when_only_name_pending PASSED
tests/test_client_facing_gate.py::test_guard_raises_when_only_credential_pending PASSED
tests/test_client_facing_gate.py::test_guard_passes_when_clinical_lead_assigned PASSED
tests/test_polygon_scorer.py ... (58 tests) ... ALL PASSED
tests/test_project_client.py ... (21 tests) ... 20 PASSED, 1 FAILED (pre-existing)

============================== 93 passed, 1 failed in 15.13s ==============================
```

Smoke test (standalone):
```
CLINICIAN_SUPERVISED_RENDER = False
CLINICAL_LEAD_NAME = PENDING_ASSIGNMENT
CLINICAL_LEAD_CREDENTIAL = PENDING_ASSIGNMENT
LIBRARY_VERSION = 1.0.3-public

PASS: raised ClinicalReviewPendingError when gate closed
PASS: no raise with TNS_ALLOW_DEV_RENDER=1
Disclaimer (draft): [DRAFT — clinical lead not yet assigned] Scoring engine: TNS Optimal Zones Library v1.0.3-public.
LIBRARY_VERSION = 1.0.3-public
```

---

## 8. Pre-Existing Test Failure (Not a v1.0.3 Regression)

**Test:** `tests/test_project_client.py::TestJesusScanLabs::test_completeness_partial_data`

Identical to v1.0.2 §8. Not touched in this release. Flagged for v1.1.0.

---

## 9. PM Sign-Off Steps — How to Flip the Gate for v1.1.0

When the v1.1.0 clinical review cycle is complete:

1. **Assign the clinical lead** — in `tns_optimal_zones.py`, set:
   ```python
   CLINICAL_LEAD_NAME: str = "Dr. Nombre Completo Aquí"
   CLINICAL_LEAD_CREDENTIAL: str = "Médico Cirujano / Nutriólogo Clínico"
   ```

2. **Flip the gate** — in `tns_optimal_zones.py`, change:
   ```python
   CLINICIAN_SUPERVISED_RENDER: bool = False
   ```
   to:
   ```python
   CLINICIAN_SUPERVISED_RENDER: bool = True
   ```
   If the lead is not yet assigned, the module will raise `ClinicalReviewPendingError` at import time — the assignment on step 1 must happen first.

3. **Confirm all OPTIMAL_ZONES entries reviewed** — every `evidence_level` field should be updated from `"pending_review"`, `caveats` populated, and `last_reviewed` set to the ISO-8601 review date.

4. **PM review the flagged strings** — verify the 7 biomarkers flagged **[PM REVIEW]** in CHANGE-02 above (TSH, Free T3, Free T4, Ferritin, Testosterone, Cortisol, eGFR concerning). Approve or revise before flipping the gate.

5. **Bump the version** — change `LIBRARY_VERSION` from `"1.0.3-public"` to `"1.1.0-public"`. Update `source` on TNS-curated entries from `"public"` to `"tns_curated"`.

6. **Append CHANGELOG entry** in `tns_optimal_zones.py`.

7. **Run the full test suite** — `python -m pytest tests/ -v`. All gate tests should pass; conftest ensures existing tests remain unaffected.

8. **Remove `TNS_ALLOW_DEV_RENDER`** from any `.env` or dev config files — CI/production must NOT have this variable set.

---

## 10. Open Questions for v1.1.0

1. **Clinical lead identity** — who is the licensed clinical reviewer for the Mexico launch? `CLINICAL_LEAD_NAME` / `CLINICAL_LEAD_CREDENTIAL` must be set before gate flip.
2. **Flagged strings** (see §4) — the 7 `[PM REVIEW]` strings use clinical terms (adrenal insufficiency, HPA dysregulation, CKD Stage 3, thyroid panel, supraphysiologic). Clinical lead to approve or rewrite for in-session context.
3. **Bilingual sign-off** — will the clinical lead review both the EN and ES strings, or only one language?
4. **`evidence_level` enum** — define allowed values: `"pending_review"` | `"expert_consensus"` | `"rct_backed"` | `"tns_curated"`?
5. **`_compute_data_completeness` logic** — reconcile `full_data` flag semantics (coverage fraction vs. tier presence). Fix or update the failing test (v1.0.2 §8, unchanged here).
6. **Citation layer** — `get_report_disclaimer()` says "citations by biomarker" but citations are not yet surfaced in the report. Add a `biomarker_citations` key to the score output in v1.1.0?
7. **Vitamin D upper cap** — values above 81 ng/mL fall through to "concerning". Add explicit upper acceptable/suboptimal band.
8. **`_male_concerning_upper` for testosterone** — values 901–1200 are neither optimal nor concerning in the male general range. Confirm classification.

---

## 11. Non-Goals Confirmed

The following were **not changed** in v1.0.3:
- `CLINICIAN_SUPERVISED_RENDER` is still `False` — not flipped to `True`
- No clinical threshold numbers changed
- No `POLYGON_VERSION` (stays `"4.1"`)
- No changes to `tns_reconcile.py` or `tns_questionnaire.py`
- No changes to any `tests/fixtures/*.json`
- `score_category()` and internal helpers deliberately NOT guarded
- `conftest.py` session fixture unchanged (`TNS_ALLOW_DEV_RENDER=1` for test runs)
