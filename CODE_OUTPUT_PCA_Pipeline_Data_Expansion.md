# CODE OUTPUT — PCA Pipeline Data Expansion (Phase A)

**Sprint:** Phase A — Scan + Biomarkers + Lifestyle Integration  
**Completed:** 2026-04-16  
**Author:** Jesus Garcia / Claude Code  
**Builds on:** Sprint 1 (Tasks 1–7) which produced the scan-only PCA pipeline

---

## Summary

Phase A extends the TNS Multidimensional Analysis pipeline from scan-only to a full trimodal intake: scanner data + blood biomarkers + lifestyle/physical activity. Nine deliverables were completed across two sessions.

---

## Deliverables

### A1 — Lab Entry sheet added to TNS_Scan_Data_Master.xlsx

**File:** `02_MEXICO/TNS_Scan_Data_Master.xlsx`

New "Lab Entry" sheet with 14 columns:
- `client_id`, `date`, `lab_source` (dropdown)
- 10 lab values in NHANES-standard units: `lab_total_chol`, `lab_hdl`, `lab_ldl`, `lab_triglycerides`, `lab_glucose`, `lab_hba1c`, `lab_insulin`, `lab_hscrp`, `lab_sbp`, `lab_dbp`
- `notes`

Data validation applied: decimal range constraints on all numeric columns, dropdown for `lab_source` (External Lab / In-Office / Self-Report).

---

### A2 — Lifestyle Entry sheet added to TNS_Scan_Data_Master.xlsx

**File:** `02_MEXICO/TNS_Scan_Data_Master.xlsx`

New "Lifestyle Entry" sheet with 11 columns:
- `client_id`, `date`
- 8 lifestyle variables: `vigorous_min_per_week`, `moderate_min_per_week`, `sedentary_hrs_per_day`, `sleep_hrs_per_night`, `smoker` (dropdown: Never/Former/Current), `alcohol_drinks_per_week`, `stress_1to10`, `subj_health_1to10`
- `notes`

---

### A3 — Unified sheet auto-merge formulas

**File:** `02_MEXICO/TNS_Scan_Data_Master.xlsx`

The "Unified (auto-merged)" sheet was extended with 19 new columns (10 lab + 9 lifestyle). Each column uses a SUMPRODUCT-based IFERROR/INDEX/MATCH formula that auto-pulls from the corresponding entry sheet when `client_id` matches AND entry date is within ±3 days of the InBody scan date.

Example formula for `lab_total_chol`:
```excel
=IFERROR(INDEX('Lab Entry'!$D:$D,
  MATCH(1,(ABS('Lab Entry'!$B:$B-B2)<=3)*('Lab Entry'!$A:$A=A2),0)),"")
```

---

### A4 — tns_reconcile.py extended with lab + lifestyle blocks

**File:** `02_MEXICO/PCA_Pipeline/tns_reconcile.py`

Changes:
- Added constants: `_LAB_KEYS`, `_CORE_LAB_KEYS`, `_LIFESTYLE_KEYS`, `_CORE_LIFESTYLE_KEYS`, `_SMOKER_ENCODE`
- Added `lifestyle_data: Optional[dict] = None` parameter to `reconcile_scanners()`
- Lab block: passes all 10 `lab_*` keys from `extra_labs` into unified dict
- Lifestyle block: normalises 7 column-name aliases, encodes "Never"/"Former"/"Current" → 0/1/2
- Added `data_completeness` dict to return value: `{scan, labs, lifestyle, full_data, completeness_label}`

`data_completeness` logic:
- `scan`: `ib_weight_kg` or `ss_weight_kg` is not None
- `labs`: any of the 6 core lab keys is not None
- `lifestyle`: any of the 3 core PA keys is not None
- `full_data`: all three present

---

### A5 — tns_pca_pipeline.py extended

**File:** `02_MEXICO/PCA_Pipeline/tns_pca_pipeline.py`

Changes:
1. **PAQ variable fix:** Replaced incorrect `PAD675`/`PAD680` entries with the correct 7-column PAQ spec (`PAQ650`–`PAD680`). Added composite derivation in `_build_nhanes_df()`:
   ```python
   merged["pa_vig_min_week"] = np.where(vig_active, paq_vig_days * paq_vig_min, 0.0)
   merged["pa_mod_min_week"] = np.where(mod_active, paq_mod_days * paq_mod_min, 0.0)
   merged["pa_sed_hours_day"] = merged["paq_sed_min"] / 60.0
   ```

2. **LENS_DEFS["performance"]** updated to use composite PA vars: `pa_vig_min_week`, `pa_mod_min_week`, `pa_sed_hours_day`

3. **CLIENT_TO_MODEL** extended with lifestyle key mappings:
   - `lifestyle_vig_min_week` → `pa_vig_min_week`
   - `lifestyle_mod_min_week` → `pa_mod_min_week`
   - `lifestyle_sed_hours_day` → `pa_sed_hours_day`
   - Plus column-name aliases from Lifestyle Entry sheet

4. **`_compute_data_completeness()` helper added** — used at projection time

5. **`project_client()` extended:**
   ```python
   def project_client(
       client_data, model_dir=None, models=None, lens="auto",
       previous_projections=None,
       lab_data: Optional[dict] = None,      # NEW
       lifestyle_data: Optional[dict] = None, # NEW
   ) -> dict:
   ```
   Both kwargs are merged into `client_data` before projection. Return dict gains `"data_completeness"` key.

---

### A6 — tns_visualize.py extended

**File:** `02_MEXICO/PCA_Pipeline/tns_visualize.py`

Changes to `plot_population_map()`:
- Reads `projection_result["data_completeness"]`
- Renders a badge in the upper-right of every health-map figure:
  - `● Full Data` (green `#10b981`) when `full_data == True`
  - `● Partial Data` (amber `#f59e0b`) when `full_data == False`

Changes to `generate_client_figures()`:
- If `labs` or `lifestyle` is False in `data_completeness`, adds a footer note to the figure set explaining which data types are missing

---

### A7 — TNS_PCA_Production.ipynb extended

**File:** `02_MEXICO/PCA_Pipeline/TNS_PCA_Production.ipynb`

New cells added:

| Cell ID | Purpose |
|---|---|
| After `cell-inbody-option-b` | Step 3b header markdown |
| `e37e5e7c` | LAB_DATA dict with optional XLSX auto-read from Lab Entry sheet |
| `9dffcac4` | Step 3c header markdown |
| `733400dc` | LIFESTYLE_DATA dict with optional XLSX auto-read from Lifestyle Entry sheet |

Updated cells:
- `cell-reconcile`: passes `extra_labs=LAB_DATA`, `lifestyle_data=LIFESTYLE_DATA`; prints `data_completeness` badge
- `cell-project`: passes `lab_data`/`lifestyle_data` kwargs; prints `🟢 Full Data` / `🟡 Partial Data` badge and coverage %

---

### A8 — tns_lab_reader.py (new module)

**File:** `02_MEXICO/PCA_Pipeline/tns_lab_reader.py`

Standalone parser for lab data from three sources:
1. Lab Entry sheet rows (already in NHANES units)
2. Arbitrary-unit dicts (auto-converted)
3. Future: PDF parser output

**Public functions:**
- `parse_lab_row(row, validate=True)` — handles all column aliases from the Excel sheet
- `convert_lab_units(raw, validate=True)` — handles mmol/L (×38.67 or ×18.02), pmol/L (÷6.945), nmol/L (÷9.524), IFCC mmol/mol ((x/10.929)+2.15)
- `lab_summary(lab_dict)` — one-line string for Colab verification output

**Constants exported:** `LAB_BOUNDS`, `ALL_LAB_KEYS`

---

### A8 (continued) — Test fixtures + pytest

**Files:**
- `02_MEXICO/PCA_Pipeline/tests/fixtures/jesus_full.json`
- `02_MEXICO/PCA_Pipeline/tests/fixtures/jesus_scan_only.json`
- `02_MEXICO/PCA_Pipeline/tests/fixtures/jesus_scan_labs.json`
- `02_MEXICO/PCA_Pipeline/tests/test_project_client.py`

All fixtures represent the output of `tns_reconcile.reconcile_scanners()` using Jesus Garcia's real April 2026 intake scans plus synthetic labs/lifestyle.

| Fixture | Scan | Labs | Lifestyle | full_data | Expected lens (auto) |
|---|---|---|---|---|---|
| `jesus_full.json` | ✓ | ✓ | ✓ | `true` | `health` |
| `jesus_scan_only.json` | ✓ | ✗ | ✗ | `false` | non-health (body_comp) |
| `jesus_scan_labs.json` | ✓ | ✓ | ✗ | `false` | `health` |

The pytest file uses stub PCA models (no NHANES files required) and covers:
- 16 tests across 3 classes + 2 module-level sanity checks
- Structure assertions (required keys, finite floats, percentile 0–100)
- `data_completeness` flag correctness
- Lens auto-selection logic
- All 5 lenses project without error on all 3 fixtures
- `lab_data` and `lifestyle_data` kwarg overrides
- Imputed variable tracking

---

## File inventory (Phase A)

| File | Status |
|---|---|
| `02_MEXICO/TNS_Scan_Data_Master.xlsx` | Modified — Lab Entry + Lifestyle Entry sheets added, Unified extended |
| `02_MEXICO/PCA_Pipeline/tns_reconcile.py` | Modified — lab/lifestyle blocks + data_completeness |
| `02_MEXICO/PCA_Pipeline/tns_pca_pipeline.py` | Modified — PAQ fix, lifestyle mapping, project_client() kwargs, completeness |
| `02_MEXICO/PCA_Pipeline/tns_visualize.py` | Modified — Full/Partial Data badge on all health maps |
| `02_MEXICO/PCA_Pipeline/TNS_PCA_Production.ipynb` | Modified — Step 3b/3c lab+lifestyle cells, updated reconcile/project cells |
| `02_MEXICO/PCA_Pipeline/tns_lab_reader.py` | NEW — lab parsing + unit conversion utilities |
| `02_MEXICO/PCA_Pipeline/_add_lab_lifestyle_sheets.py` | NEW — one-time XLSX modification utility |
| `02_MEXICO/PCA_Pipeline/tests/fixtures/jesus_full.json` | NEW — full-data fixture |
| `02_MEXICO/PCA_Pipeline/tests/fixtures/jesus_scan_only.json` | NEW — scan-only regression fixture |
| `02_MEXICO/PCA_Pipeline/tests/fixtures/jesus_scan_labs.json` | NEW — scan+labs partial fixture |
| `02_MEXICO/PCA_Pipeline/tests/test_project_client.py` | NEW — 16 pytest tests |
| `02_MEXICO/NHANES_RAW/models/TASK_8_STATUS.md` | NEW — status doc |
| `02_MEXICO/NHANES_RAW/models/TASK_9_STATUS.md` | NEW — status doc |

---

## Key design decisions

### Lab variable naming stability (Phase B readiness)
All lab variables use the `lab_*` prefix throughout every layer (Excel, reconcile, pipeline, notebook). This naming is stable — the same Python modules can be imported by Cloud Functions in Phase B without renaming any keys.

### NHANES unit convention
All values stored and projected in NHANES-standard units (mg/dL for lipids/glucose, % for HbA1c, µIU/mL for insulin, mg/L for hs-CRP, mmHg for BP). Unit conversion happens at the edge (tns_lab_reader.py) and never inside the PCA pipeline.

### data_completeness computed in two places
- `tns_reconcile.reconcile_scanners()` — reflects what was collected at intake (source of truth for the unified record)
- `tns_pca_pipeline.project_client()` — recomputes based on what was actually matched to the model (may differ slightly from reconcile's version)
Both are returned and available for display/logging.

### No red in completeness badges
Follows TNS brand rule: amber (`#f59e0b`) for "Partial Data" attention state; green (`#10b981`) for "Full Data". No red is used in client-facing outputs.

---

## Phase B preview (not implemented)

Phase B will migrate the projection pipeline to Firestore + Cloud Functions:
- `unified` dict → Firestore document under `clients/{clientId}/scans/{scanId}`
- `project_client()` → Cloud Function `projectClient` (Python 3.11 runtime)
- Lab/lifestyle data → sub-collections or flat fields on the scan document
- No renaming required: all `lab_*`, `lifestyle_*`, `data_completeness` keys are already stable

Phase B is architecturally ready but explicitly deferred pending hardware installation and portal design finalization.
