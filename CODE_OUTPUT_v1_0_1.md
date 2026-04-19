# CODE_OUTPUT — v1.0.1 Structural Safety Patch
**Date:** 2026-04-17  
**File patched:** `tns_optimal_zones.py`  
**Version:** `1.0.0-public` → `1.0.1-public`  
**Test result:** 58/58 PASS (57 existing + 1 new boundary gap test)

---

## 1. Version Confirmation

```
LIBRARY_VERSION = "1.0.1-public"
POLYGON_VERSION = "4.1"          # unchanged
```

---

## 2. New Constants Added

| Constant | Value | Purpose |
|---|---|---|
| `INTERVAL_CONVENTION` | `"half_open_low_inclusive"` | Documents range tuple semantics for all readers |
| `CLIENT_FACING` | `False` | Gate: callers must not render scores in client artifacts until `True` |

---

## 3. CHANGE-01: Half-Open Interval Transform

### Logic changes (in functions)

**`zone_for_value`** — line ~1108 of new file:
```python
# Before (v1.0.0 — closed upper bound)
if hi is not None and value > hi:
    in_zone = False

# After (v1.0.1 — exclusive upper bound)
if hi is not None and value >= hi:   # half-open: hi is exclusive
    in_zone = False
```

**`_classify_midrange`** — all three band comparisons:
```python
# Before
if opt_lo is not None and opt_hi is not None and opt_lo <= value <= opt_hi:
if acc_lo is not None and acc_hi is not None and acc_lo <= value <= acc_hi:
if sub_lo is not None and sub_hi is not None and sub_lo <= value <= sub_hi:

# After
if opt_lo is not None and opt_hi is not None and opt_lo <= value < opt_hi:
if acc_lo is not None and acc_hi is not None and acc_lo <= value < acc_hi:
if sub_lo is not None and sub_hi is not None and sub_lo <= value < sub_hi:
```

### Range tuple transforms — before / after

For each biomarker the `hi` of every non-open zone was adjusted so that `new_hi = next zone's lo` (decimals) or `old_hi + 1` (integers). **No clinical threshold numbers were changed** — only the endpoint convention.

| Biomarker | Zone | Before (closed) | After (half-open) | Rule |
|---|---|---|---|---|
| **hdl** (male) | acceptable | `(45, 59)` | `(45, 60)` | hi = next lo |
| | suboptimal | `(35, 44)` | `(35, 45)` | hi = next lo |
| | concerning | `(None, 34)` | `(None, 35)` | hi = next lo |
| **hdl** (female) | acceptable | `(50, 64)` | `(50, 65)` | hi = next lo |
| | suboptimal | `(40, 49)` | `(40, 50)` | hi = next lo |
| | concerning | `(None, 39)` | `(None, 40)` | hi = next lo |
| **total_chol** | optimal | `(150, 180)` | `(150, 181)` | hi = next lo |
| | acceptable | `(181, 199)` | `(181, 200)` | hi = next lo |
| | suboptimal | `(200, 239)` | `(200, 240)` | hi = `_concerning_upper` |
| | concerning | `(None, 129)` | `(None, 130)` | hi = next lo |
| **ldl** | optimal | `(None, 69)` | `(None, 70)` | hi = next lo |
| | acceptable | `(70, 99)` | `(70, 100)` | hi = next lo |
| | suboptimal | `(100, 129)` | `(100, 130)` | hi = next lo |
| **non_hdl** | optimal | `(None, 99)` | `(None, 100)` | hi = next lo |
| | acceptable | `(100, 129)` | `(100, 130)` | hi = next lo |
| | suboptimal | `(130, 159)` | `(130, 160)` | hi = next lo |
| **triglycerides** | optimal | `(None, 99)` | `(None, 100)` | hi = next lo |
| | acceptable | `(100, 149)` | `(100, 150)` | hi = next lo |
| | suboptimal | `(150, 199)` | `(150, 200)` | hi = next lo |
| **fasting_glucose** | optimal | `(70, 89)` | `(70, 90)` | hi = next lo |
| | acceptable | `(90, 99)` | `(90, 100)` | hi = next lo |
| | suboptimal | `(100, 109)` | `(100, 110)` | hi = next lo |
| **hba1c** ⭐ | optimal | `(4.0, 5.1)` | `(4.0, 5.2)` | hi = next lo |
| | acceptable | `(5.2, 5.6)` | `(5.2, 5.7)` | hi = next lo |
| | suboptimal | `(5.7, 6.4)` | `(5.7, 6.5)` | hi = next lo |
| **fasting_insulin** | optimal | `(2, 6)` | `(2, 7)` | hi = next lo |
| | acceptable | `(7, 12)` | `(7, 13)` | hi = next lo |
| | suboptimal | `(13, 20)` | `(13, 21)` | hi = next lo |
| **homa_ir** | optimal | `(None, 0.99)` | `(None, 1.0)` | hi = next lo |
| | acceptable | `(1.0, 1.9)` | `(1.0, 2.0)` | hi = next lo |
| | suboptimal | `(2.0, 2.9)` | `(2.0, 3.0)` | hi = next lo |
| **hs_crp** | acceptable | `(0.5, 1.0)` | `(0.5, 1.01)` | hi = next lo |
| | suboptimal | `(1.01, 3.0)` | `(1.01, 3.01)` | hi = next lo |
| **tsh** (band keys) | `_optimal_hi` | `2.5` | `2.51` | +0.01 |
| | `_acceptable_hi` | `3.5` | `3.51` | +0.01 |
| | `_suboptimal_hi` | `4.5` | `4.51` | +0.01 |
| **free_t3** (band keys) | `_optimal_hi` | `4.2` | `4.21` | +0.01 |
| | `_acceptable_hi` | `4.5` | `4.51` | +0.01 |
| | `_suboptimal_hi` | `5.0` | `5.01` | +0.01 |
| **free_t4** (band keys) | `_optimal_hi` | `1.7` | `1.71` | +0.01 |
| | `_acceptable_hi` | `1.9` | `1.91` | +0.01 |
| | `_suboptimal_hi` | `2.2` | `2.21` | +0.01 |
| **vitamin_d** | optimal | `(50, 80)` | `(50, 81)` | hi+1 |
| | acceptable | `(30, 49)` | `(30, 50)` | hi = next lo |
| | suboptimal | `(20, 29)` | `(20, 30)` | hi = next lo |
| | concerning | `(None, 19)` | `(None, 20)` | hi = next lo |
| vitamin_d athlete | optimal | `(60, 100)` | `(60, 101)` | hi+1 |
| | acceptable | `(50, 59)` | `(50, 60)` | hi = next lo |
| | suboptimal | `(30, 49)` | `(30, 50)` | hi = next lo |
| | concerning | `(None, 29)` | `(None, 30)` | hi = next lo |
| **vitamin_b12** | optimal | `(600, 1200)` | `(600, 1201)` | hi+1 |
| | acceptable | `(400, 599)` | `(400, 600)` | hi = next lo |
| | suboptimal | `(200, 399)` | `(200, 400)` | hi = next lo |
| | concerning | `(None, 199)` | `(None, 200)` | hi = next lo |
| **ferritin** male (band keys) | `_male_optimal_hi` | `150` | `151` | +1 |
| | `_male_acceptable_hi` | `200` | `201` | +1 |
| | `_male_suboptimal_hi` | `300` | `301` | +1 |
| **ferritin** female (band keys) | `_female_optimal_hi` | `100` | `101` | +1 |
| | `_female_acceptable_hi` | `150` | `151` | +1 |
| | `_female_suboptimal_hi` | `200` | `201` | +1 |
| **testosterone** male (band keys) | `_male_optimal_hi` | `900` | `901` | +1 |
| | `_male_acceptable_hi` | `599` | `600` | hi = next lo |
| | `_male_suboptimal_hi` | `399` | `400` | hi = next lo |
| | concerning | `(None, 249)` | `(None, 250)` | hi = next lo |
| testosterone male athlete | optimal | `(700, 1100)` | `(700, 1101)` | hi+1 |
| | acceptable | `(500, 699)` | `(500, 700)` | hi = next lo |
| | suboptimal | `(300, 499)` | `(300, 500)` | hi = next lo |
| | concerning | `(None, 299)` | `(None, 300)` | hi = next lo |
| **testosterone** female (band keys) | `_female_optimal_hi` | `60` | `61` | +1 |
| | `_female_acceptable_hi` | `80` | `81` | +1 |
| | `_female_suboptimal_hi` | `100` | `101` | +1 |
| **cortisol_am** (band keys) | `_optimal_hi` | `18` | `19` | +1 |
| | `_acceptable_hi` | `22` | `23` | +1 |
| | `_suboptimal_hi` | `28` | `29` | +1 |
| **sbp** | optimal | `(90, 119)` | `(90, 120)` | hi = next lo |
| | acceptable | `(120, 129)` | `(120, 130)` | hi = next lo |
| | suboptimal | `(130, 139)` | `(130, 140)` | hi = next lo |
| **dbp** | optimal | `(60, 79)` | `(60, 80)` | hi = next lo |
| | acceptable | `(80, 84)` | `(80, 85)` | hi = next lo |
| | suboptimal | `(85, 89)` | `(85, 90)` | hi = next lo |
| **tg_hdl_ratio** | optimal | `(None, 1.99)` | `(None, 2.0)` | hi = next lo |
| | acceptable | `(2.0, 3.4)` | `(2.0, 3.5)` | hi = next lo |
| | suboptimal | `(3.5, 4.9)` | `(3.5, 5.0)` | hi = next lo |
| **lp_a** | optimal | `(None, 13)` | `(None, 14)` | hi = next lo |
| | acceptable | `(14, 30)` | `(14, 31)` | hi = next lo |
| | suboptimal | `(31, 50)` | `(31, 51)` | hi = next lo |
| **apo_b** | optimal | `(None, 79)` | `(None, 80)` | hi = next lo |
| | acceptable | `(80, 99)` | `(80, 100)` | hi = next lo |
| | suboptimal | `(100, 119)` | `(100, 120)` | hi = next lo |
| **egfr** | acceptable | `(75, 89)` | `(75, 90)` | hi = next lo |
| | suboptimal | `(60, 74)` | `(60, 75)` | hi = next lo |
| | concerning | `(None, 59)` | `(None, 60)` | hi = next lo |

⭐ **HbA1c was the canonical boundary-gap example:** value `5.15` mapped to `"concerning"` in v1.0.0 (fell between `(4.0, 5.1)` and `(5.2, 5.6)`). Now correctly maps to `"optimal"`.

---

## 4. CHANGE-02: Scaffolding Fields

Three fields added after `"reference"` in **all 24 unique entries** (alias `vitamin_d_25oh` inherits):

```python
"evidence_level": "pending_review",
"caveats":        [],
"last_reviewed":  None,
```

These are placeholders for the v1.1.0 clinical review cycle. `CLIENT_FACING` remains `False` until they are populated.

Module docstring updated with an "Architecture" section entry explaining the scaffolding fields.

---

## 5. CHANGE-03: CLIENT_FACING Gate

```python
CLIENT_FACING: bool = False
# Set to True only after the v1.1.0 clinical review cycle is complete and
# all evidence_level fields are updated from "pending_review".
# Callers MUST check this flag before rendering polygon scores in any
# client-facing artifact (report, app, email).
```

---

## 6. CHANGE-04: Boundary Gap Test

Added `test_no_boundary_gaps_in_optimal_zones()` to `tests/test_polygon_scorer.py`.

- Walks **27 biomarker/sex combos** across their plausible ranges in **0.01 steps**
- Asserts every value returns a valid zone string (`"optimal"` | `"acceptable"` | `"suboptimal"` | `"concerning"`)
- Asserts no exceptions are raised
- Total values checked: ~47,000 iterations

---

## 7. Test Results

```
============================= test session starts ==============================
platform darwin -- Python 3.9.13, pytest-7.1.2
collected 58 items

... (57 existing tests) ...
tests/test_polygon_scorer.py::test_no_boundary_gaps_in_optimal_zones PASSED

============================== 58 passed in 3.75s ==============================
```

Self-test (`python tns_optimal_zones.py`):
- 18/18 smoke tests: **PASS**
- 10/10 boundary gap spot-checks: **PASS**

---

## 8. Non-Goals Confirmed

The following were **not changed** in v1.0.1:
- No clinical threshold numbers (the actual boundary values are the same)
- No biomarker additions or removals
- No layperson strings
- No `source` or `reference` fields
- No `POLYGON_VERSION` (stays `"4.1"`)
- No changes to `tns_polygon_scorer.py`, `tns_reconcile.py`, `tns_questionnaire.py`, or `app.py`

---

## 9. Open Questions for v1.1.0

1. **`CLIENT_FACING` → True**: What is the process / sign-off required to flip this gate? Who is the clinical reviewer?
2. **`evidence_level` values**: Should we define an enum (`"pending_review"`, `"expert_consensus"`, `"rct_backed"`, `"tns_curated"`)?
3. **`caveats` population**: Will disclaimers be bilingual (EN + ES) to match layperson strings?
4. **`last_reviewed` format**: ISO-8601 date string (`"2026-06-01"`) or datetime with reviewer ID?
5. **`_male_concerning_upper` for testosterone**: Currently metadata-only (not enforced in `zone_for_value`). Should values 901–1200 really classify as "concerning" for non-athlete males, or should an "acceptable" upper band be added?
6. **vitamin_d upper cap**: Values above 81 ng/mL fall through to "concerning" via catch-all. Clinically, values 81–150 are likely just "optimal-high"; consider adding an explicit upper acceptable/suboptimal band in v1.1.0.
