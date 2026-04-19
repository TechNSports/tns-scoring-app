# CODE_OUTPUT — v1.0.2 CLIENT_FACING Enforcement
**Date:** 2026-04-17
**File patched:** `tns_optimal_zones.py` (primary), `tns_polygon_scorer.py`, `tns_visualize.py`, `tns_pca_pipeline.py`, `app.py`
**Files created:** `tests/conftest.py`, `tests/test_client_facing_gate.py`
**Version:** `1.0.1-public` → `1.0.2-public`
**Test result:** 89/90 PASS (58 existing + 11 new gate tests; 1 pre-existing failure, see §8)

---

## 1. Version Confirmation

```
LIBRARY_VERSION = "1.0.2-public"
POLYGON_VERSION = "4.1"          # unchanged
```

---

## 2. Purpose

`CLIENT_FACING: bool = False` was added in v1.0.1 as a gating constant, but
nothing enforced it — any caller could generate client-visible artifacts
regardless. v1.0.2 makes the gate **load-bearing**: every function that
produces a client-bound artifact now calls `assert_client_facing_allowed()`
at its entry point, which raises `ClientFacingBlockedError` unless the flag is
`True` or the dev-bypass env var is active.

---

## 3. CHANGE-01: Guard Helper in `tns_optimal_zones.py`

### Exception class

```python
class ClientFacingBlockedError(RuntimeError):
    """Raised when a client-facing render is attempted while CLIENT_FACING is False."""
```

### Guard function

```python
def assert_client_facing_allowed(context: str) -> None:
    import os
    if CLIENT_FACING:
        return
    if os.environ.get("TNS_ALLOW_DEV_RENDER") == "1":
        return
    raise ClientFacingBlockedError(
        f"CLIENT_FACING is False; rendering blocked at: {context}. "
        f"Flip CLIENT_FACING = True only after clinical sign-off is complete. "
        f"For local dev previews, set TNS_ALLOW_DEV_RENDER=1."
    )
```

**Placement:** Added after the `CLIENT_FACING` constant block, before the
`CHANGELOG` section.

**Bypass rules:**
| Condition | Result |
|---|---|
| `CLIENT_FACING is True` | Returns `None` (allowed) |
| `os.environ["TNS_ALLOW_DEV_RENDER"] == "1"` | Returns `None` (dev bypass) |
| Anything else | Raises `ClientFacingBlockedError` |

Only the exact string `"1"` activates the bypass. Values like `"yes"`, `"true"`,
`"0"`, or `" 1"` (leading space) are rejected.

---

## 4. CHANGE-02: Guard Call Sites

### Summary table

| Function | File | Guard call | Reason |
|---|---|---|---|
| `score_polygon()` | `tns_polygon_scorer.py` | `assert_client_facing_allowed("tns_polygon_scorer.score_polygon")` | Primary client score producer — all layperson strings + zone labels |
| `plot_population_map()` | `tns_visualize.py` | `assert_client_facing_allowed("tns_visualize.plot_population_map")` | PNG with client name + percentile |
| `plot_loadings_bar()` | `tns_visualize.py` | `assert_client_facing_allowed("tns_visualize.plot_loadings_bar")` | PNG chart |
| `plot_trajectory_timeline()` | `tns_visualize.py` | `assert_client_facing_allowed("tns_visualize.plot_trajectory_timeline")` | PNG with percentile history |
| `plot_radar_overlay()` | `tns_visualize.py` | `assert_client_facing_allowed("tns_visualize.plot_radar_overlay")` | PNG radar with wellness scores |
| `generate_client_figures()` | `tns_visualize.py` | `assert_client_facing_allowed("tns_visualize.generate_client_figures")` | Master PNG generator — saves to disk |
| `project_client()` | `tns_pca_pipeline.py` | `assert_client_facing_allowed("tns_pca_pipeline.project_client")` | Full projection dict including polygon, percentile, layperson strings |
| `if run_btn:` block | `app.py` | try/except + `st.error()` + `st.stop()` | Streamlit orchestration entry point |

### Functions explicitly NOT guarded

| Function | File | Reason |
|---|---|---|
| `score_category()` | `tns_polygon_scorer.py` | Internal building block called by `score_polygon`; test suite calls it standalone |
| `_score_tier_a/b/c()` | `tns_polygon_scorer.py` | Pure computation helpers |
| `compute_radar_scores()` | `tns_visualize.py` | Returns a plain dict; no rendering |
| `reconcile_scanners()` | `tns_reconcile.py` | Merges scanner dicts; no client output |
| `reconcile_summary()` | `tns_reconcile.py` | Returns diagnostic string for internal use |
| `build_all_models()`, `load_model()`, `load_all_models()` | `tns_pca_pipeline.py` | Model infrastructure |
| `validate_model()` | `tns_pca_pipeline.py` | Internal diagnostic |

### `tns_reconcile.py` finding

No export functions (XLSX, CSV, JSON to client destination) were found in
`tns_reconcile.py`. The spec asked to survey for these — confirmed absent.
No guard needed in this file.

### Import additions

`tns_polygon_scorer.py` — extended existing import:
```python
from tns_optimal_zones import (
    LIBRARY_VERSION,
    POLYGON_VERSION,
    score_biomarker,
    get_derived_biomarkers,
    assert_client_facing_allowed,   # ← added
    ClientFacingBlockedError,       # ← added
)
```

`tns_visualize.py` — new top-level import:
```python
from tns_optimal_zones import assert_client_facing_allowed, ClientFacingBlockedError  # noqa: F401
```

`tns_pca_pipeline.py` — new top-level import (after `from typing import ...`):
```python
from tns_optimal_zones import assert_client_facing_allowed, ClientFacingBlockedError  # noqa: F401
```

`app.py` — inline import at top of `if run_btn:` block:
```python
from tns_optimal_zones import assert_client_facing_allowed, ClientFacingBlockedError
```

### `app.py` guard pattern

The app catches the exception and shows a user-friendly Streamlit error rather
than letting the raw exception surface:

```python
if run_btn:
    from tns_optimal_zones import assert_client_facing_allowed, ClientFacingBlockedError
    try:
        assert_client_facing_allowed("app.generate_health_map")
    except ClientFacingBlockedError:
        st.error(
            "⚠️ **Health Map generation is currently disabled.**  "
            "Clinical review of zone thresholds has not been completed.  "
            "Contact the TNS team to unlock this feature."
        )
        st.stop()
    (parse_inbody_csv_string, ...) = _load_pipeline()
    ...
```

---

## 5. CHANGE-03: New Test File — `tests/test_client_facing_gate.py`

5 tests (11 items after parametrize expansion):

| Test | What it covers |
|---|---|
| `test_guard_passes_when_client_facing_true` | Monkeypatches `CLIENT_FACING = True`; asserts no raise |
| `test_guard_raises_when_flag_false_and_no_env_var` | Clears env var, asserts `ClientFacingBlockedError` with context string in message |
| `test_guard_bypassed_by_env_var` | Sets `TNS_ALLOW_DEV_RENDER="1"`, asserts no raise |
| `test_guard_not_bypassed_by_non_one_env_var` | Parametrized over `["0", "yes", "true", "True", "1 ", " 1", ""]`; each must raise |
| `test_score_polygon_raises_when_client_facing_blocked` | End-to-end: calls `score_polygon()` with fixture data after clearing env var; asserts `ClientFacingBlockedError` with call-site string |

---

## 6. CHANGE-04: New File — `tests/conftest.py`

Session-scoped autouse fixture that sets `TNS_ALLOW_DEV_RENDER=1` for the entire
pytest run, ensuring all 58 existing tests continue to pass without per-test
changes.

```python
@pytest.fixture(autouse=True, scope="session")
def _allow_dev_render_in_tests():
    os.environ["TNS_ALLOW_DEV_RENDER"] = "1"
    yield
    os.environ.pop("TNS_ALLOW_DEV_RENDER", None)
```

The session scope means the env var is set once at test startup and torn down
after the last test — no fixture overhead per test.

---

## 7. Test Results

```
============================= test session starts ==============================
platform darwin -- Python 3.9.13, pytest-7.1.2
collected 90 items

tests/test_client_facing_gate.py::test_guard_passes_when_client_facing_true PASSED
tests/test_client_facing_gate.py::test_guard_raises_when_flag_false_and_no_env_var PASSED
tests/test_client_facing_gate.py::test_guard_bypassed_by_env_var PASSED
tests/test_client_facing_gate.py::test_guard_not_bypassed_by_non_one_env_var[0] PASSED
tests/test_client_facing_gate.py::test_guard_not_bypassed_by_non_one_env_var[yes] PASSED
tests/test_client_facing_gate.py::test_guard_not_bypassed_by_non_one_env_var[true] PASSED
tests/test_client_facing_gate.py::test_guard_not_bypassed_by_non_one_env_var[True] PASSED
tests/test_client_facing_gate.py::test_guard_not_bypassed_by_non_one_env_var[1 ] PASSED
tests/test_client_facing_gate.py::test_guard_not_bypassed_by_non_one_env_var[ 1] PASSED
tests/test_client_facing_gate.py::test_guard_not_bypassed_by_non_one_env_var[] PASSED
tests/test_client_facing_gate.py::test_score_polygon_raises_when_client_facing_blocked PASSED
tests/test_polygon_scorer.py ... (58 tests) ... ALL PASSED
tests/test_project_client.py ... (21 tests) ... 20 PASSED, 1 FAILED (pre-existing)

============================== 89 passed, 1 failed in 7.80s ==============================
```

Smoke test (standalone):
```
python3 -c "..."
CLIENT_FACING = False
PASS: raised ClientFacingBlockedError
PASS: no raise with env var set
LIBRARY_VERSION = '1.0.2-public'
PASS: version is 1.0.2-public
```

---

## 8. Pre-Existing Test Failure (Not a v1.0.2 Regression)

**Test:** `tests/test_project_client.py::TestJesusScanLabs::test_completeness_partial_data`

**Assertion:** `dc["full_data"] is False` — test expects `full_data=False` because lifestyle data is absent.

**Root cause:** `_compute_data_completeness()` computes `full_data` from the PCA
variable-coverage fraction (`n_vars_provided / n_vars_total >= FULL_DATA_THRESHOLD`),
not from the boolean presence of all three tiers (scan + labs + lifestyle). The
`jesus_scan_labs.json` fixture provides enough scan + lab variables to push the
coverage fraction above threshold, so `full_data=True` even though `has_lifestyle=False`.

**Why it is not a v1.0.2 regression:** This function and its logic were not
touched in v1.0.2. The guard added to `project_client()` fires before
`_compute_data_completeness()` is called, and the conftest fixture bypasses
the guard for all tests. The test's pass/fail behavior is identical before and
after this patch.

**Resolution:** Out of scope for v1.0.2. Flagged for v1.1.0: either update
`_compute_data_completeness` to require all three tiers for `full_data=True`,
or update the test to match the current implementation's intent.

---

## 9. How to Flip the Gate (PM Sign-Off Steps)

When the v1.1.0 clinical review cycle is complete and all `evidence_level`
fields have been updated from `"pending_review"`, the PM/lead developer should
follow these exact steps to unlock client-facing output:

1. **Get clinical sign-off** — confirm every biomarker entry in `OPTIMAL_ZONES`
   has been reviewed; `evidence_level` updated (e.g., `"expert_consensus"`),
   `caveats` populated with any applicable disclaimer strings, and
   `last_reviewed` set to the ISO-8601 review date (e.g., `"2026-06-01"`).

2. **Flip the flag** — in `tns_optimal_zones.py`, change:
   ```python
   CLIENT_FACING: bool = False   # line ~92
   ```
   to:
   ```python
   CLIENT_FACING: bool = True
   ```

3. **Bump the version** — change `LIBRARY_VERSION` from `"1.0.2-public"` to
   `"1.1.0-public"` (or `"1.1.0-hybrid"` if some biomarkers are TNS-curated).
   Update the `source` field on any TNS-curated entries from `"public"` to
   `"tns_curated"`.

4. **Append a CHANGELOG entry** inside `tns_optimal_zones.py` — follow the
   existing `# v1.0.x-public` comment format.

5. **Run the full test suite** — `python -m pytest tests/ -v`. The conftest
   `_allow_dev_render_in_tests` fixture keeps existing tests passing, but
   the gate tests should also confirm everything is clean.

6. **Remove or scope `TNS_ALLOW_DEV_RENDER`** from any `.env` or dev config
   files — CI/production must NOT have this variable set.

---

## 11. Non-Goals Confirmed

The following were **not changed** in v1.0.2:
- `CLIENT_FACING` is still `False` — not flipped to `True`
- No clinical threshold numbers
- No layperson strings
- No biomarker additions or removals
- No `source` or `reference` fields
- No `POLYGON_VERSION` (stays `"4.1"`)
- No changes to `tns_reconcile.py` or `tns_questionnaire.py`
- No changes to any `tests/fixtures/*.json`
- `score_category()` deliberately NOT guarded (internal building block)

---

## 12. Open Questions for v1.1.0

*(Carried over from v1.0.2 scope, plus new items)*

1. **`CLIENT_FACING` → True**: Who is the clinical reviewer, and what is the
   sign-off process? What checklist gates the flip?
2. **`evidence_level` values**: Should we define an enum (`"pending_review"`,
   `"expert_consensus"`, `"rct_backed"`, `"tns_curated"`)?
3. **`caveats` population**: Will disclaimers be bilingual (EN + ES)?
4. **`last_reviewed` format**: ISO-8601 date string or datetime with reviewer ID?
5. **`_male_concerning_upper` for testosterone**: Currently metadata-only. Should
   values 901–1200 classify as "concerning" for non-athlete males?
6. **vitamin_d upper cap**: Values above 81 ng/mL fall through to "concerning".
   Add explicit upper acceptable/suboptimal band in v1.1.0.
7. **`_compute_data_completeness` logic**: Reconcile `full_data` flag semantics
   (coverage fraction vs. tier presence). Fix or update the failing test.
