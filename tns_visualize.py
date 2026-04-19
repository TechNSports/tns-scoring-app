"""
TNS Multidimensional Analysis System
Task 5: Visualization Module

Publication-quality matplotlib figures for the TNS health map system.

Brand / compliance rules (hardcoded):
  - Background  : #0a0a14 (dark canvas)
  - Card panels  : #111127
  - TNS Blue     : #0659FF
  - Waterspout   : #CDDEFF
  - Healthy dir  : #22c55e (green)
  - Attention    : #f59e0b (amber)  — NEVER use red in client-facing output
  - White text   : #FFFFFF
  - No equipment brand names (use "3D body scan" / "body composition scan")
  - No "apple/pear" shape language (use "waist-dominant" / "hip-dominant")
  - No BMI in client-facing tables

Functions
---------
  plot_population_map()        — Reference population scatter + client position
  plot_loadings_bar()          — PC1 loadings horizontal bar chart
  plot_trajectory_timeline()   — PC1 percentile over time (line chart)
  plot_radar_overlay()         — Wellness polygon: intake vs current
  generate_client_figures()    — Master function: all figures for a client

Usage
-----
    from tns_visualize import generate_client_figures

    figs = generate_client_figures(
        projection_result=result,          # from project_client()
        model=model,                       # loaded JSON model
        client_name="Jesus Garcia",
        save_dir="/content/drive/MyDrive/.../client_projections/garcia_jesus",
        previous_projections=[...],        # prior scan results list
    )
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional, Union
import math

from tns_optimal_zones import (  # noqa: F401
    assert_clinician_review_complete,
    ClinicalReviewPendingError,
    get_report_disclaimer,
)

import matplotlib
matplotlib.use("Agg")   # non-interactive backend — safe for Colab and scripts
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.patheffects as pe
from matplotlib.gridspec import GridSpec
import numpy as np

# ── Brand palette ─────────────────────────────────────────────────────────────
BG          = "#0a0a14"
CARD        = "#111127"
TNS_BLUE    = "#0659FF"
WATERSPOUT  = "#CDDEFF"
WHITE       = "#FFFFFF"
GREY_MED    = "#8888aa"
GREEN       = "#22c55e"
AMBER       = "#f59e0b"
POPULATION_DOT = "#2a2a4a"    # subtle dots for reference population
CLIENT_DOT     = TNS_BLUE
TRAJECTORY_LINE = WATERSPOUT

# Variable display names for labels (no equipment brands, no medical jargon overload)
DISPLAY_NAMES: dict[str, str] = {
    "bmi":               "Body Mass Index",
    "waist_cm":          "Waist circumference",
    "hip_cm":            "Hip circumference",
    "thigh_cm":          "Thigh circumference",
    "arm_cm":            "Arm circumference",
    "whr":               "Waist-to-hip ratio",
    "whtr":              "Waist-to-height ratio",
    "bf_pct":            "Body fat %",
    "fat_mass_kg":       "Fat mass",
    "lean_mass_kg":      "Lean mass",
    "ffmi":              "Fat-free mass index",
    "android_fat_pct":   "Central fat distribution",
    "gynoid_fat_pct":    "Hip fat distribution",
    "sbp":               "Systolic blood pressure",
    "dbp":               "Diastolic blood pressure",
    "total_chol":        "Total cholesterol",
    "hdl":               "HDL cholesterol",
    "ldl":               "LDL cholesterol",
    "triglycerides":     "Triglycerides",
    "glucose":           "Fasting glucose",
    "hba1c":             "HbA1c",
    "insulin":           "Fasting insulin",
    "hscrp":             "hs-CRP (inflammation)",
    "visceral_fat_level":"Visceral fat level",
    "smi":               "Skeletal muscle index",
    "phase_angle":       "Phase angle",
    "inbody_score":      "Body composition score",
    "shape_score":       "3D scan shape score",
    "pa_sed_min":        "Sedentary time",
    "pa_vig_min":        "Vigorous activity",
}

def _dname(v: str) -> str:
    return DISPLAY_NAMES.get(v, v.replace("_", " ").title())


def _set_dark_style(fig: plt.Figure, axes: list) -> None:
    """Apply TNS dark theme to a figure and list of axes."""
    fig.patch.set_facecolor(BG)
    for ax in axes:
        ax.set_facecolor(CARD)
        ax.tick_params(colors=GREY_MED, labelsize=9)
        for spine in ax.spines.values():
            spine.set_edgecolor(WATERSPOUT)
            spine.set_linewidth(0.5)
        ax.xaxis.label.set_color(WATERSPOUT)
        ax.yaxis.label.set_color(WATERSPOUT)
        ax.title.set_color(WHITE)


def _add_disclaimer_footer(fig: plt.Figure) -> None:
    """Stamp the clinical review disclaimer at the bottom of a figure.

    Uses ``get_report_disclaimer()`` from tns_optimal_zones so the text is
    always in sync with the library constants.  While CLINICAL_LEAD_NAME /
    CLINICAL_LEAD_CREDENTIAL are still "PENDING_ASSIGNMENT" the function
    prints a clearly-marked draft placeholder so figures are never silently
    footer-less during development.
    """
    text = get_report_disclaimer()
    fig.text(
        0.5, 0.005, text,
        ha="center", va="bottom",
        fontsize=6, color=GREY_MED,
        wrap=True,
        transform=fig.transFigure,
    )


# ─────────────────────────────────────────────────────────────────────────────
# 1. Population map
# ─────────────────────────────────────────────────────────────────────────────

def plot_population_map(
    projection_result: dict,
    model: dict,
    client_name: str = "You",
    previous_projections: Optional[list[dict]] = None,
    mode: str = "simple",
    figsize: tuple = (10, 7),
    save_path: Optional[Union[str, Path]] = None,
) -> plt.Figure:
    """
    Reference population scatter with the client's position and trajectory.

    Parameters
    ----------
    projection_result : dict
        Output of project_client().
    model : dict
        Loaded JSON model dict.
    client_name : str
        Display name (used on the figure, not a unique identifier).
    previous_projections : list[dict], optional
        Prior scan results for trajectory arrow(s).
    mode : str
        "simple"    — clean client-friendly view, no PC axis labels
        "technical" — full PC labels + variance % + loadings annotation
    figsize : tuple
    save_path : str or Path, optional
    """
    assert_clinician_review_complete("tns_visualize.plot_population_map")
    pop_scores = np.array(model["population"]["pc_scores_2d"])
    pc1_client = projection_result["pc1"]
    pc2_client = projection_result["pc2"]
    pct = projection_result["percentile_pc1"]
    ev = projection_result["explained_variance"]

    fig, ax = plt.subplots(figsize=figsize)
    _set_dark_style(fig, [ax])

    # ── Reference population scatter ─────────────────────────────────────────
    # Subsample if large (>2000 points) for render performance
    n_pop = len(pop_scores)
    if n_pop > 2000:
        idx = np.random.default_rng(42).choice(n_pop, 2000, replace=False)
        pop_plot = pop_scores[idx]
    else:
        pop_plot = pop_scores

    ax.scatter(
        pop_plot[:, 0], pop_plot[:, 1],
        c=POPULATION_DOT, s=8, alpha=0.35, linewidths=0, zorder=1,
        label="Reference population"
    )

    # ── Trajectory arrows (prior scans) ──────────────────────────────────────
    if previous_projections:
        all_pts = sorted(previous_projections, key=lambda p: p.get("date", ""))
        for i, prev in enumerate(all_pts):
            ax.scatter(
                prev["pc1"], prev["pc2"],
                c=WATERSPOUT, s=70, zorder=4, alpha=0.6, edgecolors="none"
            )
            ax.annotate(
                prev.get("label", f"Visit {i+1}"),
                (prev["pc1"], prev["pc2"]),
                textcoords="offset points", xytext=(6, 4),
                fontsize=7, color=WATERSPOUT
            )
        last = all_pts[-1]
        ax.annotate(
            "",
            xy=(pc1_client, pc2_client),
            xytext=(last["pc1"], last["pc2"]),
            arrowprops=dict(
                arrowstyle="-|>", color=GREEN, lw=1.8,
                connectionstyle="arc3,rad=0.1"
            ),
            zorder=5
        )

    # ── Client dot ───────────────────────────────────────────────────────────
    ax.scatter(
        pc1_client, pc2_client,
        c=TNS_BLUE, s=220, zorder=6, edgecolors=WHITE, linewidths=1.5,
        label=client_name
    )
    ax.annotate(
        f"{client_name}\n{pct:.0f}th percentile",
        (pc1_client, pc2_client),
        textcoords="offset points", xytext=(12, 8),
        fontsize=9, color=WHITE, fontweight="bold",
        path_effects=[pe.withStroke(linewidth=2, foreground=BG)]
    )

    # ── Directional labels ───────────────────────────────────────────────────
    x_min, x_max = ax.get_xlim()
    y_min, y_max = ax.get_ylim()
    if mode == "simple":
        ax.text(x_min + 0.05*(x_max-x_min), 0.02, "Higher health risk",
                transform=ax.get_xaxis_transform(), ha="left",
                fontsize=8, color=AMBER, alpha=0.8)
        ax.text(x_max - 0.05*(x_max-x_min), 0.02, "Better health markers",
                transform=ax.get_xaxis_transform(), ha="right",
                fontsize=8, color=GREEN, alpha=0.8)
        ax.set_xlabel("Health axis (relative position)", fontsize=9)
        ax.set_ylabel("Body shape axis", fontsize=9)
        ax.set_xticklabels([])
        ax.set_yticklabels([])
    else:
        pc1_var = ev.get("pc1", 0) or 0
        pc2_var = ev.get("pc2", 0) or 0
        ax.set_xlabel(f"PC1 ({pc1_var:.1%} variance)", fontsize=9, color=WATERSPOUT)
        ax.set_ylabel(f"PC2 ({pc2_var:.1%} variance)", fontsize=9, color=WATERSPOUT)

    lens_label = projection_result.get("lens_used", "").replace("_", " ").title()
    dc = projection_result.get("data_completeness", {})
    badge_text = f"● {dc.get('completeness_label', '')}" if dc else ""
    badge_color = GREEN if dc.get("full_data") else AMBER
    ax.set_title(f"Health Map — {lens_label} Lens", fontsize=13, color=WHITE, pad=12)
    if badge_text:
        ax.text(0.99, 1.02, badge_text,
                transform=ax.transAxes, ha="right", va="bottom",
                fontsize=8, color=badge_color, fontweight="bold")

    ax.axhline(0, color=WATERSPOUT, linewidth=0.3, alpha=0.3, zorder=0)
    ax.axvline(0, color=WATERSPOUT, linewidth=0.3, alpha=0.3, zorder=0)

    # ── Legend ───────────────────────────────────────────────────────────────
    legend_handles = [
        mpatches.Patch(color=POPULATION_DOT, label="Reference population"),
        mpatches.Patch(color=TNS_BLUE, label=client_name),
    ]
    ax.legend(handles=legend_handles, loc="upper left", fontsize=8,
              facecolor=CARD, edgecolor=WATERSPOUT, labelcolor=WHITE)

    plt.tight_layout(pad=1.5)
    if save_path:
        _add_disclaimer_footer(fig)
        fig.savefig(save_path, dpi=150, bbox_inches="tight", facecolor=BG)
    return fig


# ─────────────────────────────────────────────────────────────────────────────
# 2. PC1 loadings bar chart
# ─────────────────────────────────────────────────────────────────────────────

def plot_loadings_bar(
    projection_result: dict,
    n_vars: int = 10,
    figsize: tuple = (8, 6),
    save_path: Optional[Union[str, Path]] = None,
) -> plt.Figure:
    """
    Horizontal bar chart of PC1 loadings — shows what drives the health axis.

    Parameters
    ----------
    projection_result : dict
        Output of project_client() — must contain pc1_loadings.
    n_vars : int
        Number of top variables to show (by absolute loading).
    """
    assert_clinician_review_complete("tns_visualize.plot_loadings_bar")
    loadings = projection_result.get("pc1_loadings", {})
    if not loadings:
        raise ValueError("projection_result must contain 'pc1_loadings'.")

    ranked = sorted(loadings.items(), key=lambda x: abs(x[1]), reverse=True)[:n_vars]
    # Reverse so largest is at top
    ranked = list(reversed(ranked))
    labels = [_dname(v) for v, _ in ranked]
    values = [l for _, l in ranked]

    fig, ax = plt.subplots(figsize=figsize)
    _set_dark_style(fig, [ax])

    colors = [GREEN if v > 0 else AMBER for v in values]
    bars = ax.barh(range(len(values)), values, color=colors, height=0.65,
                   edgecolor="none", zorder=2)

    ax.set_yticks(range(len(labels)))
    ax.set_yticklabels(labels, fontsize=9, color=WHITE)
    ax.axvline(0, color=WATERSPOUT, linewidth=0.8, alpha=0.6)
    ax.set_xlabel("Loading on PC1 (health axis)", fontsize=9)
    ax.set_title("What drives your health axis position", fontsize=12, color=WHITE, pad=10)

    # Value labels
    for bar, val in zip(bars, values):
        xpos = val + (0.005 if val >= 0 else -0.005)
        ha = "left" if val >= 0 else "right"
        ax.text(xpos, bar.get_y() + bar.get_height()/2, f"{val:+.3f}",
                va="center", ha=ha, fontsize=7.5, color=WHITE)

    # Legend
    pos_patch = mpatches.Patch(color=GREEN, label="Associated with better markers")
    neg_patch = mpatches.Patch(color=AMBER, label="Associated with attention area")
    ax.legend(handles=[pos_patch, neg_patch], loc="lower right", fontsize=8,
              facecolor=CARD, edgecolor=WATERSPOUT, labelcolor=WHITE)

    plt.tight_layout(pad=1.5)
    if save_path:
        _add_disclaimer_footer(fig)
        fig.savefig(save_path, dpi=150, bbox_inches="tight", facecolor=BG)
    return fig


# ─────────────────────────────────────────────────────────────────────────────
# 3. Trajectory timeline (PC1 percentile over time)
# ─────────────────────────────────────────────────────────────────────────────

def plot_trajectory_timeline(
    current_projection: dict,
    previous_projections: list[dict],
    client_name: str = "You",
    figsize: tuple = (9, 5),
    save_path: Optional[Union[str, Path]] = None,
) -> plt.Figure:
    """
    Line chart of PC1 percentile over time — the most client-friendly output.

    Shows health trajectory from intake through all check-in points.
    Annotates improvement arrows and labels each visit.

    Parameters
    ----------
    current_projection : dict
        Latest project_client() result.
    previous_projections : list[dict]
        Prior results, each with keys: pc1, percentile_pc1, date, label.
    """
    assert_clinician_review_complete("tns_visualize.plot_trajectory_timeline")
    # Build sorted time series
    all_points = sorted(previous_projections, key=lambda p: p.get("date", ""))
    all_points.append({
        "pc1":           current_projection["pc1"],
        "percentile_pc1": current_projection["percentile_pc1"],
        "date":          current_projection.get("scan_date", "Now"),
        "label":         current_projection.get("scan_label", "Current"),
    })

    dates  = [p.get("label", p.get("date", f"Visit {i+1}")) for i, p in enumerate(all_points)]
    pcts   = [float(p.get("percentile_pc1", 50)) for p in all_points]
    x_vals = list(range(len(dates)))

    fig, ax = plt.subplots(figsize=figsize)
    _set_dark_style(fig, [ax])

    # Shaded reference bands
    ax.axhspan(0,  25, color=AMBER, alpha=0.07, zorder=0)
    ax.axhspan(25, 75, color=WATERSPOUT, alpha=0.05, zorder=0)
    ax.axhspan(75, 100, color=GREEN, alpha=0.07, zorder=0)
    # ax.get_yaxis_transform(): x in axes fraction [0,1], y in data coordinates.
    # This keeps x=0.01 (1 % from left edge) while letting y use the 0-100
    # percentile scale so the labels sit inside their respective shaded bands.
    _yt = ax.get_yaxis_transform()
    ax.text(0.01, 10,  "Focus area",    transform=_yt,
            fontsize=7, color=AMBER,     alpha=0.6, va="bottom")
    ax.text(0.01, 50,  "Typical range", transform=_yt,
            fontsize=7, color=WATERSPOUT, alpha=0.5, va="center")
    ax.text(0.01, 88,  "Optimal zone",  transform=_yt,
            fontsize=7, color=GREEN,     alpha=0.6, va="top")

    # Smooth line
    ax.plot(x_vals, pcts, color=WATERSPOUT, linewidth=2, zorder=3,
            marker="o", markersize=8, markerfacecolor=TNS_BLUE,
            markeredgecolor=WHITE, markeredgewidth=1.2)

    # Colour fill under line
    ax.fill_between(x_vals, pcts, 0, alpha=0.12, color=TNS_BLUE, zorder=2)

    # Annotate each point
    for i, (x, pct, label) in enumerate(zip(x_vals, pcts, dates)):
        offset_y = 4 if pct < 90 else -6
        ax.annotate(f"{pct:.0f}th",
                    (x, pct),
                    textcoords="offset points", xytext=(0, offset_y),
                    ha="center", fontsize=8.5, color=WHITE, fontweight="bold",
                    path_effects=[pe.withStroke(linewidth=2, foreground=BG)])

    # Improvement delta annotation between first and last
    if len(pcts) >= 2:
        delta = pcts[-1] - pcts[0]
        if abs(delta) >= 1:
            delta_color = GREEN if delta > 0 else AMBER
            sign = "+" if delta > 0 else ""
            ax.annotate(
                f"{sign}{delta:.0f} percentile points",
                xy=(x_vals[-1], pcts[-1]),
                xytext=(x_vals[-1] - 0.5, (pcts[-1] + pcts[0]) / 2),
                fontsize=9, color=delta_color, fontweight="bold",
                arrowprops=dict(arrowstyle="-|>", color=delta_color, lw=1.2),
                path_effects=[pe.withStroke(linewidth=2, foreground=BG)]
            )

    ax.set_xticks(x_vals)
    ax.set_xticklabels(dates, fontsize=9, color=WHITE)
    ax.set_ylim(0, 100)
    ax.set_ylabel("Health percentile (vs reference population)", fontsize=9)
    ax.set_title(f"{client_name} — Health Trajectory", fontsize=13, color=WHITE, pad=12)

    lens_label = current_projection.get("lens_used", "").replace("_", " ").title()
    ax.text(0.99, 0.01, f"Lens: {lens_label}", transform=ax.transAxes,
            ha="right", va="bottom", fontsize=7, color=GREY_MED)

    plt.tight_layout(pad=1.5)
    if save_path:
        _add_disclaimer_footer(fig)
        fig.savefig(save_path, dpi=150, bbox_inches="tight", facecolor=BG)
    return fig


# ─────────────────────────────────────────────────────────────────────────────
# 4. Radar overlay (wellness polygon)
# ─────────────────────────────────────────────────────────────────────────────

def plot_radar_overlay(
    current_values: dict,
    baseline_values: Optional[dict] = None,
    client_name: str = "You",
    figsize: tuple = (7, 7),
    save_path: Optional[Union[str, Path]] = None,
) -> plt.Figure:
    """
    Radar (spider) chart comparing current vs baseline across wellness domains.

    Parameters
    ----------
    current_values : dict
        Dict of {domain_label: 0-100 score}. Scores must be pre-normalised
        to 0–100 (100 = optimal). Use compute_radar_scores() helper.
    baseline_values : dict, optional
        Same schema as current_values. If None, only current is shown.
    """
    assert_clinician_review_complete("tns_visualize.plot_radar_overlay")
    categories = list(current_values.keys())
    n = len(categories)
    if n < 3:
        raise ValueError("Need at least 3 categories for a radar chart.")

    angles = np.linspace(0, 2 * np.pi, n, endpoint=False).tolist()
    angles += angles[:1]   # close the polygon

    def _vals(d: dict) -> list[float]:
        v = [d.get(c, 50) for c in categories]
        return v + v[:1]

    curr_vals = _vals(current_values)
    base_vals = _vals(baseline_values) if baseline_values else None

    fig, ax = plt.subplots(figsize=figsize, subplot_kw=dict(polar=True))
    fig.patch.set_facecolor(BG)
    ax.set_facecolor(CARD)
    ax.spines["polar"].set_edgecolor(WATERSPOUT)
    ax.spines["polar"].set_linewidth(0.5)

    # Gridlines
    ax.set_ylim(0, 100)
    ax.yaxis.set_tick_params(labelsize=6, labelcolor=GREY_MED)
    ax.set_yticks([25, 50, 75, 100])
    ax.set_yticklabels(["25", "50", "75", "100"], fontsize=6, color=GREY_MED)
    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(categories, size=9, color=WHITE)
    ax.tick_params(colors=GREY_MED)
    for g in ax.yaxis.get_gridlines():
        g.set_color(WATERSPOUT)
        g.set_alpha(0.2)

    # Baseline polygon
    if base_vals:
        ax.plot(angles, base_vals, color=AMBER, linewidth=1.5,
                linestyle="--", alpha=0.7, label="Intake")
        ax.fill(angles, base_vals, color=AMBER, alpha=0.08)

    # Current polygon
    ax.plot(angles, curr_vals, color=GREEN, linewidth=2, label="Current")
    ax.fill(angles, curr_vals, color=GREEN, alpha=0.15)

    ax.set_title(f"{client_name} — Wellness Profile", y=1.08,
                 fontsize=12, color=WHITE)

    legend = ax.legend(loc="upper right", bbox_to_anchor=(1.25, 1.1),
                       fontsize=8, facecolor=CARD, edgecolor=WATERSPOUT,
                       labelcolor=WHITE)

    if save_path:
        _add_disclaimer_footer(fig)
        fig.savefig(save_path, dpi=150, bbox_inches="tight", facecolor=BG)
    return fig


def compute_radar_scores(unified: dict, sex: str = "M") -> dict:
    """
    Convert unified scan variables to 0–100 radar scores (100 = optimal).
    Uses evidence-based thresholds; sex-adjusted where relevant.
    Does NOT include BMI in client-facing output (per TNS brand policy).

    Returns
    -------
    dict of {domain: score_0_to_100}
    """
    def _score(val, worse_bound, better_bound) -> float:
        """Linear interpolation: worse_bound→0, better_bound→100."""
        if val is None:
            return 50.0
        clamped = max(min(val, worse_bound), better_bound) \
            if worse_bound > better_bound else \
            max(min(val, better_bound), worse_bound)
        if worse_bound == better_bound:
            return 50.0
        raw = (val - worse_bound) / (better_bound - worse_bound) * 100
        return max(0.0, min(100.0, round(raw, 1)))

    # Thresholds (worse→better)
    scores: dict[str, float] = {}

    # Body composition score (BF%)
    if sex == "F":
        scores["Body Fat"] = _score(unified.get("bf_pct"), 45, 20)
    else:
        scores["Body Fat"] = _score(unified.get("bf_pct"), 35, 12)

    # Lean mass (SMM) relative to height
    if unified.get("lean_per_cm") is not None:
        scores["Lean Mass"] = _score(unified.get("lean_per_cm"), 0.20, 0.30)

    # Waist distribution
    scores["Waist Health"] = _score(unified.get("whr"), 1.00, 0.75)

    # Cardiovascular (if labs present)
    if unified.get("lab_hdl") is not None:
        hdl_score = _score(unified.get("lab_hdl"), 30, 70)
        tg_score  = _score(unified.get("lab_triglycerides"), 300, 100)
        scores["Cardiovascular"] = round((hdl_score + tg_score) / 2, 1)

    # Glycaemic (if labs present)
    if unified.get("lab_glucose") is not None:
        glu_score  = _score(unified.get("lab_glucose"), 200, 80)
        hba1c      = unified.get("lab_hba1c")
        hba1c_score = _score(hba1c, 9.0, 5.0) if hba1c else glu_score
        scores["Glycaemic"] = round((glu_score + hba1c_score) / 2, 1)

    # Inflammation (if labs present)
    if unified.get("lab_hscrp") is not None:
        scores["Inflammation"] = _score(unified.get("lab_hscrp"), 10.0, 0.5)

    # Blood pressure (if present)
    if unified.get("lab_sbp") is not None:
        sbp_score = _score(unified.get("lab_sbp"), 180, 110)
        scores["Blood Pressure"] = sbp_score

    # Phase angle (biomarker of cell health — from InBody)
    if unified.get("ib_phase_angle") is not None:
        scores["Cell Health"] = _score(unified.get("ib_phase_angle"), 3.0, 8.0)

    if not scores:
        # Fallback: waist + BF only
        scores = {
            "Body Fat": _score(unified.get("bf_pct"), 35, 12),
            "Waist Health": _score(unified.get("whr"), 1.00, 0.75),
        }

    return scores


# ─────────────────────────────────────────────────────────────────────────────
# 5. Master figure generator
# ─────────────────────────────────────────────────────────────────────────────

def generate_client_figures(
    projection_result: dict,
    model: dict,
    client_name: str,
    save_dir: Union[str, Path],
    previous_projections: Optional[list[dict]] = None,
    baseline_unified: Optional[dict] = None,
    current_unified: Optional[dict] = None,
    sex: str = "M",
    mode: str = "simple",
) -> dict[str, Path]:
    """
    Generate all TNS figures for a client visit and save to save_dir.

    Parameters
    ----------
    projection_result : dict
        Output of project_client() for the current visit.
    model : dict
        Loaded PCA model dict (matching projection_result["lens_used"]).
    client_name : str
        Display name for titles and annotations.
    save_dir : str or Path
        Folder where figures will be saved (created if needed).
    previous_projections : list[dict], optional
        Prior project_client() results for trajectory charts.
    baseline_unified : dict, optional
        Reconciled scan dict from intake (for radar comparison).
    current_unified : dict, optional
        Reconciled scan dict for current visit (for radar scores).
    sex : str
        "M" or "F" — affects radar score thresholds.
    mode : str
        "simple" (default, client-facing) or "technical" (clinician).

    Returns
    -------
    dict[str, Path]
        {figure_name: saved_path}
    """
    assert_clinician_review_complete("tns_visualize.generate_client_figures")
    save_dir = Path(save_dir)
    save_dir.mkdir(parents=True, exist_ok=True)

    saved: dict[str, Path] = {}
    client_slug = client_name.lower().replace(" ", "_")
    lens = projection_result.get("lens_used", "health")

    # Figure 1: Population map
    pop_path = save_dir / f"{client_slug}_health_map_{lens}.png"
    try:
        fig1 = plot_population_map(
            projection_result, model, client_name,
            previous_projections=previous_projections,
            mode=mode, save_path=pop_path
        )
        plt.close(fig1)
        saved["health_map"] = pop_path
        print(f"  [OK] Health map → {pop_path.name}")
    except Exception as e:
        print(f"  [ERR] Health map failed: {e}")

    # Figure 2: PC1 loadings bar
    load_path = save_dir / f"{client_slug}_loadings_{lens}.png"
    try:
        fig2 = plot_loadings_bar(projection_result, n_vars=10, save_path=load_path)
        plt.close(fig2)
        saved["loadings"] = load_path
        print(f"  [OK] Loadings bar → {load_path.name}")
    except Exception as e:
        print(f"  [ERR] Loadings bar failed: {e}")

    # Figure 3: Trajectory timeline (only if prior data exists)
    if previous_projections:
        tl_path = save_dir / f"{client_slug}_timeline_{lens}.png"
        try:
            fig3 = plot_trajectory_timeline(
                projection_result, previous_projections,
                client_name=client_name, save_path=tl_path
            )
            plt.close(fig3)
            saved["timeline"] = tl_path
            print(f"  [OK] Timeline → {tl_path.name}")
        except Exception as e:
            print(f"  [ERR] Timeline failed: {e}")

    # Figure 4: Radar overlay (only if unified scan data provided)
    if current_unified:
        radar_path = save_dir / f"{client_slug}_radar_{lens}.png"
        try:
            current_scores  = compute_radar_scores(current_unified, sex=sex)
            baseline_scores = compute_radar_scores(baseline_unified, sex=sex) \
                              if baseline_unified else None
            fig4 = plot_radar_overlay(
                current_scores, baseline_scores,
                client_name=client_name, save_path=radar_path
            )
            plt.close(fig4)
            saved["radar"] = radar_path
            print(f"  [OK] Radar → {radar_path.name}")
        except Exception as e:
            print(f"  [ERR] Radar failed: {e}")

    dc = projection_result.get("data_completeness", {})
    if not dc.get("full_data"):
        missing = []
        if not dc.get("labs"):      missing.append("labs")
        if not dc.get("lifestyle"): missing.append("lifestyle")
        if missing:
            print(f"\n  ⚠️  Partial Data — missing: {', '.join(missing)}")
            print(f"     Health/Longevity/Performance lenses used population medians for missing values.")
    # Max possible figures: map + loadings always; timeline only with prior data;
    # radar only with current_unified — compute dynamically rather than hardcoding.
    max_figs = 2 + (1 if previous_projections else 0) + (1 if current_unified else 0)
    print(f"\n  {len(saved)}/{max_figs} figures saved to {save_dir}")
    return saved


# ─────────────────────────────────────────────────────────────────────────────
# Smoke test
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import json

    print("tns_visualize.py — smoke test (no model needed)")

    # Minimal mock projection
    MOCK_PROJECTION = {
        "pc1": 0.82,
        "pc2": -0.31,
        "percentile_pc1": 68.5,
        "lens_used": "health",
        "lens_description": "Health Optimization",
        "scan_label": "8wk",
        "pc1_loadings": {
            "waist_cm": -0.38,
            "bf_pct": -0.35,
            "hdl": 0.29,
            "glucose": -0.26,
            "hscrp": -0.24,
            "hba1c": -0.22,
            "sbp": -0.20,
            "total_chol": -0.18,
            "whr": -0.17,
            "triglycerides": -0.16,
        },
        "explained_variance": {"pc1": 0.31, "pc2": 0.18},
        "cross_scanner_flags": [],
    }
    MOCK_PREV = [
        {"pc1": 0.12, "pc2": -0.5, "percentile_pc1": 48.0, "date": "2026-01-15", "label": "Intake"},
    ]

    # Radar test
    MOCK_UNIFIED = {
        "bf_pct": 29.8,
        "whr": 0.95,
        "lean_per_cm": 0.223,
        "ib_phase_angle": 6.9,
        "lab_hdl": None, "lab_glucose": None, "lab_hscrp": None,
        "lab_sbp": None, "lab_triglycerides": None,
    }

    import tempfile, os
    tmpdir = tempfile.mkdtemp()

    # Test loadings bar (no model required)
    fig = plot_loadings_bar(MOCK_PROJECTION, save_path=os.path.join(tmpdir, "test_loadings.png"))
    plt.close(fig)
    print(f"  Loadings bar: {os.path.join(tmpdir, 'test_loadings.png')}")

    # Test trajectory timeline
    fig = plot_trajectory_timeline(
        MOCK_PROJECTION, MOCK_PREV, client_name="Test Client",
        save_path=os.path.join(tmpdir, "test_timeline.png")
    )
    plt.close(fig)
    print(f"  Timeline:     {os.path.join(tmpdir, 'test_timeline.png')}")

    # Test radar
    scores = compute_radar_scores(MOCK_UNIFIED)
    fig = plot_radar_overlay(scores, save_path=os.path.join(tmpdir, "test_radar.png"))
    plt.close(fig)
    print(f"  Radar:        {os.path.join(tmpdir, 'test_radar.png')}")

    print(f"\nAll smoke test figures saved to: {tmpdir}")
