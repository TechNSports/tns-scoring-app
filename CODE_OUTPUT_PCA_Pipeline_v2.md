# CODE OUTPUT — PCA Pipeline v2 Sprint
### Phase A v2: Optimal Zone Scoring + Polygon v4.1 Alignment

**Sprint dates:** 2026-04-16 → 2026-04-17  
**Author:** Claude (Anthropic) + Jesus Garcia  
**Status:** ✅ Complete — 57/57 tests pass, Streamlit live on :8502

---

## Executive Summary

This sprint replaced population-percentile scoring with **research-based optimal zone scoring** (Wellness Polygon v4.1). PCA is now a visualization layer only — coordinates for the population cloud plot, not the primary score. All 6 polygon categories score independently with 3-tier evidence weighting. Full backward compatibility maintained: all legacy `project_client()` keys still present at the top level.

**Scoring philosophy change:**

| Before (v1) | After (v2) |
|---|---|
| Score = percentile vs US NHANES population | Score = proximity to peer-reviewed optimal thresholds |
| PC1 = primary score axis | PC1 = visualization coordinate only |
| Single number (percentile) | 6 categories × 3 tiers = polygon |
| No data confidence signal | high / moderate / baseline confidence levels |
| PCA crashes on missing data | Every category always scores (Rule 45) |

---

## Files Created / Modified

### NEW — `tns_optimal_zones.py` (TASK 8 v2)
**Purpose:** Biomarker zone library. The single source of truth for all optimal-zone thresholds.

| Constant | Value |
|---|---|
| `LIBRARY_VERSION` | `"1.0.0-public"` |
| `POLYGON_VERSION` | `"4.1"` |
| `ZONE_SCORES` | `{"optimal": 90, "acceptable": 70, "suboptimal": 45, "concerning": 15}` |
| `OPTIMAL_ZONES` entries | 25 biomarkers |

**Zone thresholds (selected):**

| Biomarker | Optimal | Acceptable | Suboptimal | Concerning | Source |
|---|---|---|---|---|---|
| HDL (M) | ≥60 | 45–59 | 35–44 | ≤34 | AHA/ACC 2018 |
| HDL (F) | ≥65 | 50–64 | 40–49 | ≤39 | AHA/ACC 2018 |
| LDL | ≤69 | 70–99 | 100–129 | ≥130 | AHA/ACC 2018 |
| Total Chol | 150–180 | 181–199 | 200–239 | <130 or ≥240 | AHA/ACC 2018 |
| Fasting Glucose | 70–89 | 90–99 | 100–109 | <60 or ≥110 | ADA 2024 |
| HbA1c | 4.0–5.1% | 5.2–5.6% | 5.7–6.4% | ≥6.5% | ADA 2024 |
| Fasting Insulin | 2–6 µIU/mL | 7–12 | 13–20 | <2 or >20 | Kraft 2008 |
| HOMA-IR | <1.0 | 1.0–1.9 | 2.0–2.9 | ≥3.0 | Matthews 1985 |
| hsCRP | <0.5 mg/L | 0.5–1.0 | 1.01–3.0 | >3.0 | Ridker 2003 |
| Vitamin D | 50–80 ng/mL | 30–49 | 20–29 | <20 | Holick 2011 |
| Testosterone (M) | 600–900 ng/dL | 400–599 | 250–399 | <250 | Endocrine Soc. 2018 |
| Cortisol AM | 12–18 µg/dL | 8–22 | 5–28 | <5 or >28 | Endocrine Soc. 2016 |
| TSH | 1.0–2.5 mIU/L | 0.5–3.5 | 0.3–4.5 | <0.3 or >4.5 | ATA 2012 |

**Athlete overrides (Rule 48):**
- `vitamin_d`: competitive → optimal band lifts to 60–100 ng/mL
- `testosterone_total` (male): competitive → optimal band lifts to 700–1100 ng/dL (non-competitive optimal = 600–900)

**Key functions:**
- `zone_for_value(entry, value, sex)` → zone string
- `score_biomarker(name, value, sex, athlete_status)` → `{"zone": ..., "score": ..., "layperson_en": ..., "layperson_es": ..., "reference": ...}`
- `get_derived_biomarkers(lab_dict)` → computes `homa_ir`, `tg_hdl_ratio`, `non_hdl` if source values present
- `list_available(lab_dict)` → list of scoreable biomarkers given input dict

**Self-tests:** 18/18 pass

---

### NEW — `tns_questionnaire.py` (TASK 10)
**Purpose:** Tier C (questionnaire) scoring for all 6 polygon categories.

**27 items across 6 categories:**

| Category | Items (count) | PAR-Q trigger? |
|---|---|---|
| body_composition | 5 | No |
| heart_vascular | 5 | `q_chest_pain_on_exertion="yes"` → PAR-Q |
| metabolic_function | 4 | No |
| hormonal_balance | 5 | No |
| stress_recovery | 4 | No |
| lifestyle_fitness | 4 | No |

**Key scoring rules:**
- `q_training_intensity_1to10`: 7–8 = optimal (90), 5–6 = acceptable (70), 9–10 = acceptable (70, very high is not optimal), <5 = suboptimal (45)
- `q_menstrual_regularity`: returns `None` for `sex="male"` (skipped without error, Rule 45)
- `q_chest_pain_on_exertion="yes"` → `check_par_q()` returns `True` → medical clearance required

**Key functions:**
- `parse_questionnaire(raw)` → validated dict with defaults
- `score_questionnaire_item(item_name, value, sex)` → `{"zone": ..., "score": ..., "layperson_en": ..., "layperson_es": ...}`
- `score_category_questionnaire(category, questionnaire, sex)` → mean score across category items
- `check_par_q(questionnaire)` → bool

**Self-tests:** 13/13 pass

---

### MODIFIED — `tns_reconcile.py` (TASK 11)
**Purpose:** Enforce ShapeScale > InBody priority for overlap fields (Rule 44).

**New constants:**
```python
SHAPESCALE_PRIORITY_FIELDS = frozenset({
    "weight_kg", "bmi", "bf_pct", "lean_mass_kg", "whr", "whtr"
})
INBODY_ONLY_FIELDS = frozenset({
    "visceral_fat_level", "phase_angle", "ecw_tbw_ratio",
    "segmental_lean", "inbody_score", "body_water_kg", "protein_kg", "mineral_kg"
})
SHAPESCALE_ONLY_FIELDS = frozenset({"posture_score", "bsr", "circumferences"})
```

**Rule 44 changes to `reconcile_scans()`:**
- `bf_pct` → ShapeScale primary (was InBody)
- BMI → computed from ShapeScale weight if available
- `primary_weight_kg` and `primary_weight_source` added to output
- Weight discrepancy flag fires when |SS − IB| > 1.5 kg

**Impact on Jesus Garcia April 2026 data:**
| Field | Before | After |
|---|---|---|
| `bf_pct` | 29.8% (InBody) | 34.5% (ShapeScale) |
| `bmi` | 34.4 | 30.49 |
| `primary_weight_source` | — | `"shapescale"` |
| Flags | 1 | 2 (added Rule 44 + weight discrepancy) |

---

### NEW — `tns_polygon_scorer.py` (TASK 9 v2)
**Purpose:** 6-category polygon scoring engine. Primary scoring layer (PCA demoted to coordinates).

**1,591 lines. Architecture:**

```
score_polygon(unified, questionnaire, sex, athlete_status, client_id)
    └─ score_category(cat_name, unified, questionnaire, sex, athlete_status)  [× 6]
           ├─ Tier A: score_biomarker()  [tns_optimal_zones]
           ├─ Tier B: SCAN_SCORING funcs [body_fat, bmi, whr, whtr, waist, ...]
           └─ Tier C: score_category_questionnaire()  [tns_questionnaire]
```

**Category weights and Tier base weights:**

| Category | Overall wt | Tier A | Tier B | Tier C | Tier A biomarkers (count) |
|---|---|---|---|---|---|
| body_composition | 20% | 25% | 55% | 20% | 3 (testosterone, cortisol_am, vitamin_d) |
| heart_vascular | 20% | 55% | 15% | 30% | 11 (lipids, CRP, BP, lp_a, apo_b) |
| metabolic_function | 15% | 55% | 25% | 20% | 8 (glucose, hba1c, insulin, homa_ir, TG/HDL, thyroid) |
| hormonal_balance | 15% | 50% | 10% | 40% | 8 (testosterone, cortisol, thyroid, vitamin_d/B12, ferritin) |
| stress_recovery | 15% | 30% | 10% | 60% | 3 (cortisol_am, hs_crp, ferritin) |
| lifestyle_fitness | 15% | 0% | 35% | 65% | 0 (no blood biomarkers for lifestyle) |

> Module-level `assert` verifies weights sum to 1.00 at import.

**Tier Expansion Rule:** When a tier has zero inputs, its weight redistributes proportionally to present tiers. Weights always sum to 1.0 within each category.

**Confidence logic:**
- `high` → Tier A labs present (≥1 biomarker) AND Tier B scan present
- `moderate` → Tier B scan present, no Tier A labs
- `baseline` → Tier C questionnaire only
- Overall = minimum confidence across all 6 categories
- `lifestyle_fitness` has no Tier A → max confidence is `moderate`; this is correct behavior, not a bug

**SCAN_SCORING dict (10 entries):**
- `body_fat` — sex-stratified: M optimal 8–18%, F optimal 21–30%
- `bmi_func` — optimal 18.5–22.9
- `whr_func` — sex-stratified: M optimal <0.85, F optimal <0.75
- `whtr_func` — optimal <0.40
- `waist_func` — sex-stratified: M optimal <80 cm, F optimal <72 cm
- `visc_fat_func` — optimal 1–7 InBody units
- `phase_angle_func` — optimal ≥7.0°
- `ffmi_func` — sex-stratified: M optimal 20–26, F optimal 16–22
- `smi_func` — sex-stratified: M optimal ≥10.0, F optimal ≥6.5 kg/m²
- `inbody_score_func` — optimal ≥80
- `shape_score_func` — optimal ≥85

**LAB_KEY_MAP (23 entries):** Maps unified dict `lab_*` prefixed keys → canonical biomarker names for `tns_optimal_zones.score_biomarker()`.

**`score_polygon()` return schema:**
```json
{
  "overall_score": 52,
  "confidence": "moderate",
  "par_q_escalation": false,
  "missing_data_notes": ["No Tier A labs provided for body_composition ..."],
  "library_version": "1.0.0-public",
  "polygon_version": "4.1",
  "categories": {
    "body_composition": {
      "score": 45,
      "rendering": "solid",
      "confidence": "moderate",
      "tiers": { "A": null, "B": {...}, "C": {...} },
      "inputs": [ { "name": "body_fat", "value": 34.5, "zone": "suboptimal", "score": 45, ... } ],
      "pca": null
    },
    "heart_vascular": { ... },
    ...
  }
}
```

**Rendering field:** `"solid"` when Tier A or Tier B present; `"dashed"` (questionnaire only, baseline).

**Smoke test:** 6 scenarios all pass (full data, no questionnaire, labs only, questionnaire only, PAR-Q trigger, pregnant flag).

---

### MODIFIED — `tns_pca_pipeline.py` (TASK 12)
**Purpose:** Wire polygon scorer into `project_client()`. PCA demoted to visualization layer.

**`project_client()` — v2 return schema:**

```python
# New primary keys (polygon scoring)
"overall_score"       # int 0–100
"confidence"          # "high" | "moderate" | "baseline"
"categories"          # 6-category polygon result dict
"par_q_escalation"    # bool
"missing_data_notes"  # list[str]
"library_version"     # "1.0.0-public"
"polygon_version"     # "4.1"
"pca_visualization"   # nested: pc1, pc2, percentile_pc1, lens_used, loadings, ...

# Legacy keys preserved (backward compat — existing notebooks/app don't break)
"pc1", "pc2", "percentile_pc1", "lens_used", "n_vars_provided",
"top_drivers", "pc1_loadings", "explained_variance",
"trajectory", "data_completeness"
```

**Lazy import pattern:** `tns_polygon_scorer` imported inside `project_client()` to prevent circular imports and allow graceful fallback to legacy v1 schema if scorer not installed.

---

### MODIFIED — `app.py` (TASK 12)
**Purpose:** Display polygon scores in Results section. Two separate fixes applied:

**Fix 1 — StreamlitAPIException (pending-preset pattern):**
Preset buttons (`_apply_preset()`) were modifying `st.session_state` keys that matched already-rendered widgets, causing:
```
StreamlitAPIException: st.session_state.lab_total_chol cannot be modified
after the widget with key lab_total_chol is instantiated
```
Solution: Buttons now set `st.session_state["_pending_preset"] = profile` + rerun. A resolver block at the very top of the render cycle (before any widgets) applies values on the next pass:
```python
if "_pending_preset" in st.session_state:
    _apply_preset(st.session_state.pop("_pending_preset"))
```

**Fix 2 — v2 Results section:**

| New element | Behavior |
|---|---|
| Overall Score metric | Replaces Percentile as first headline metric; 0–100 range; help text |
| Confidence badge | `🟢 High / 🟡 Moderate / ⚪ Questionnaire only` appended to `## Results` header |
| PAR-Q escalation warning | `st.error(...)` banner; only renders when `par_q_escalation=True` |
| Wellness Polygon Scores grid | `st.columns(6)`, one tile per category; `📊` solid / `📈` dashed icon; score/99; confidence delta |
| Missing data notes | `st.expander` listing each note; only renders when list non-empty |
| JSON report download | Adds `overall_score`, `confidence`, `polygon_version`, `library_version`, `category_scores`, `par_q_escalation`, `missing_data_notes` |

All existing elements preserved: scan body metrics, population map, radar, trajectory, Top PC1 drivers expander, figure download buttons, Full/Partial Data badge.

---

### NEW — Tests (TASK 9 v2)

**`tests/test_polygon_scorer.py`** — 57 tests, 57 pass (0.08s)

| Class | Count | Focus |
|---|---|---|
| Module sanity | 5 | category weights sum, 6 categories defined, version constants |
| `TestFixtureQuestionnaireOnly` | 9 | All dashed rendering, baseline confidence, no Tier A/B inputs |
| `TestFixtureScanAndQuestionnaire` | 8 | Body comp solid, no Tier A labs, Rule 44 source check |
| `TestFixturePartialLabs` | 8 | heart_vascular Tier A present, derived TG/HDL ratio, LDL zone |
| `TestFixtureFullData` | 15 | All solid, overall score 30–65, zone assertions, cross-scanner flags |
| `TestEdgeCases` | 6 | Empty questionnaire, empty unified, PAR-Q trigger, sex-stratified HDL, all 4 fixtures score |
| **Total** | **57** | **57/57 pass** |

**`tests/fixtures/`** — 4 new fixtures:

| File | Contents |
|---|---|
| `fixture_questionnaire_only.json` | No scan, no labs — only questionnaire responses |
| `fixture_scan_and_questionnaire.json` | Jesus Garcia Apr 2026 ShapeScale + InBody scan data; no labs |
| `fixture_partial_labs.json` | Scan + lipid panel only (total_chol=198, hdl=45, ldl=122, trig=155) |
| `fixture_full_data.json` | Full scan + complete synthetic lab panel + questionnaire |

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                      project_client()                       │
│                   tns_pca_pipeline.py                       │
│                                                             │
│  ┌──────────────┐     ┌─────────────────────────────────┐  │
│  │  PCA Engine  │     │     score_polygon()              │  │
│  │  (unchanged) │     │   tns_polygon_scorer.py          │  │
│  │              │     │                                  │  │
│  │ → pc1, pc2   │     │  6× score_category()             │  │
│  │ → percentile │     │    ├─ Tier A: score_biomarker()  │  │
│  │ → lens_used  │     │    │   tns_optimal_zones.py      │  │
│  └──────┬───────┘     │    ├─ Tier B: SCAN_SCORING funcs │  │
│         │             │    └─ Tier C: score_category_q() │  │
│         │             │        tns_questionnaire.py      │  │
│         │             └────────────────┬────────────────┘  │
│         │                              │                   │
│         └──────────────────────────────┘                   │
│                              │                             │
│         pca_visualization ←──┘──→ overall_score            │
│         (coordinates only)         categories, confidence  │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
                ┌─────────────────────────┐
                │        app.py           │
                │   Streamlit :8502       │
                │                         │
                │  Overall Score /100     │
                │  🟢 High confidence     │
                │  ████████████████       │
                │  6-category grid        │
                │  Population cloud       │
                │  Radar + Trajectory     │
                └─────────────────────────┘
```

---

## Key Rules Implemented

| Rule | Description | Where |
|---|---|---|
| Rule 44 | ShapeScale 3D optical wins over InBody BIA for: weight, BMI, BF%, lean mass, WHR, WHtR | `tns_reconcile.py` |
| Rule 45 | Missing data never crashes; every category always scores (defaults to 50 if zero tiers) | `tns_polygon_scorer.py` |
| Rule 46 | Every `inputs` entry has `layperson_en` + `layperson_es` (≤25 words, 8th-grade) | `tns_optimal_zones.py`, `tns_questionnaire.py`, `tns_polygon_scorer.py` |
| Rule 47 | Every threshold has a `reference` field (AHA, ADA, Endocrine Soc., WHO, etc.) | `tns_optimal_zones.py`, `tns_polygon_scorer.py` |
| Rule 48 | Athlete overrides for vitamin_d and testosterone thresholds | `tns_optimal_zones.py` |

---

## Derived Biomarkers

Three biomarkers are computed automatically in `get_derived_biomarkers()` if source values are present:

| Derived | Formula | Source fields required |
|---|---|---|
| `homa_ir` | `(fasting_glucose × fasting_insulin) / 405` | `lab_glucose` + `lab_fasting_insulin` |
| `tg_hdl_ratio` | `triglycerides / hdl` | `lab_trig` + `lab_hdl` |
| `non_hdl` | `total_cholesterol − hdl` | `lab_total_chol` + `lab_hdl` |

---

## Versioning

| Constant | Value | Where |
|---|---|---|
| `LIBRARY_VERSION` | `"1.0.0-public"` | `tns_optimal_zones.py` (immutable stamp) |
| `POLYGON_VERSION` | `"4.1"` | `tns_optimal_zones.py` |

Historical projections carry these stamps so results can never be silently re-scored across scoring-engine upgrades.

---

## Phase B Deferred Items

The following are explicitly deferred to Phase B:

1. **`plot_polygon_radar()`** — 6-category hexagonal polygon chart (the actual product visualization). Infrastructure placeholder (`pca: null` key in each category result) is in place.

2. **Per-category PCA clouds** — 6 category-specific NHANES models, one per polygon category. Requires running `build_all_models()` with 6 new lens definitions. Deferred pending category-specific model data.

3. **Color-coded cloud backgrounds** — green=optimal, yellow=acceptable, orange=suboptimal, red=concerning zones on the population scatter plot.

4. **`TNS_Scan_Data_Master.xlsx` — Questionnaire Entry sheet** — Tab for entering questionnaire responses directly from Excel (for non-Streamlit workflows).

5. **`TNS_PCA_Production.ipynb` — questionnaire + polygon cells** — Notebook cells for questionnaire input and polygon scoring display.

---

## Running the Test Suite

```bash
cd "02_MEXICO/PCA_Pipeline"

# All polygon scorer tests
python -m pytest tests/test_polygon_scorer.py -v

# Module self-tests
python tns_optimal_zones.py   # 18/18
python tns_questionnaire.py   # 13/13
python tns_polygon_scorer.py  # 6 smoke scenarios

# Start Streamlit
streamlit run app.py --server.port 8502
```

---

## Status Docs (NHANES_RAW/models/)

| File | Task | Summary |
|---|---|---|
| `TASK_8_v2_STATUS.md` | Optimal zones library | 25 biomarkers, zone bands, athlete overrides |
| `TASK_9_v2_STATUS.md` | Polygon scorer | 6-category engine, tier expansion, confidence logic |
| `TASK_10_STATUS.md` | Questionnaire integration | 27 items, PAR-Q, 6-category Tier C |
| `TASK_11_STATUS.md` | ShapeScale priority | Rule 44 enforcement, reconcile.py update |
| `TASK_12_STATUS.md` | Visualization + pipeline | pca_pipeline v2 schema, app.py v2 Results |
