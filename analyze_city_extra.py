# -*- coding: utf-8 -*-
"""Twin-model sensitivity and scalability of the city-scale orchestration: Fig. 10 and city_extra_summary.json.

Inputs (JSON lines written by run_city.py, one run per line; deduplicated by "key", first copy kept):
  results/city/twin_v3.jsonl  worm; A-PQZTO with twin graph error (twin_err: share of true contact links missing from
                              the twin, as many spurious same-domain links added) x propagation-prior error (beta_err:
                              twin prior 0.03*(1+beta_err)), seeds 21-40, plus no-response runs of the same seeds
  results/city/scal_v3.jsonl  worm; apqzto, apqzto_nodt, fl_ids at 1x-8x city size (1,500-12,000 devices), seeds 21-23,
                              one worker (clean timing)
Outputs:
  results/city_extra_summary.json   (sections written for whichever input exists; meta.*_complete flags partial data)
  figures/fig10_twin_scal.png/.tif  (only when both inputs exist)

Usage:
  python analyze_city_extra.py                       real inputs -> real outputs
  python analyze_city_extra.py --selftest [--keep] [--outdir DIR]
        synthetic, clearly FAKE rows -> temporary folder only (never the real summary or figure); checks the pipeline
"""
import argparse
import json
import os
import shutil
import sys
import tempfile
import time

import numpy as np
import pandas as pd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.ticker import FixedLocator, FuncFormatter, NullFormatter, NullLocator  # noqa: E402
from scipy.stats import linregress, t as t_dist  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from analyze_city import boot_ci, POL_LAB, POL_COL, T_STEPS  # noqa: E402

RES = r"E:\A-PQZTO_work\results"
FIG = r"E:\A-PQZTO_work\figures"
TWIN_IN = os.path.join(RES, "city", "twin_v3.jsonl")
SCAL_IN = os.path.join(RES, "city", "scal_v3.jsonl")
THETA_IN = os.path.join(RES, "city", "theta_v3.json")
OUT_JSON = os.path.join(RES, "city_extra_summary.json")
FIG_NAME = "fig10_twin_scal"

plt.rcParams.update({"font.family": "Times New Roman", "font.size": 8, "mathtext.fontset": "stix",
                     "axes.spines.top": False, "axes.spines.right": False, "axes.grid": True, "grid.color": "#e6e5e1",
                     "grid.linewidth": 0.6})

STEP_S = 10                                  # decision interval (s)
EP_H = T_STEPS * STEP_S / 3600.0             # episode length (h) = 1
INTERVAL_MS = 1000.0 * STEP_S                # 10,000 ms
TWIN_ERR = [0.0, 0.1, 0.3, 0.5]
BETA_ERR = [-0.5, 0.0, 1.0]
SEEDS = list(range(21, 41))
SCAL_POL = ["apqzto", "apqzto_nodt", "fl_ids"]
SCALES = [1.0, 2.0, 4.0, 8.0]
SCAL_SEEDS = [21, 22, 23]
NOMINAL = (0.1, 0.0)                         # twin setting of the main city runs (City defaults)
EXACT = (0.0, 0.0)
BETA_LAB = {-0.5: "propagation prior ×0.5", 0.0: "exact prior", 1.0: "×2"}
BETA_COL = {-0.5: "#009E73", 0.0: "#000000", 1.0: "#CC79A7"}
POL_MARK = {"apqzto": "o", "apqzto_nodt": "s", "fl_ids": "^"}


def tkey(te, be):
    return f"twin_err={te:.1f}|beta_err={be:.1f}"


def skey(p, n):
    return f"{p}|n_dev={int(n)}"


# ------------------------------------------------------------------------------------------------ loading
def load_jsonl(path):
    """Rows of a JSON-lines file, first copy per "key". A line still being written (truncated) is skipped."""
    if not os.path.exists(path):
        return pd.DataFrame(), 0
    seen, bad = {}, 0
    with open(path) as f:
        for line in f:
            if not line.strip():
                continue
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                bad += 1
                continue
            seen.setdefault(r["key"], r)
    return pd.DataFrame(list(seen.values())), bad


def _ci(x, name):
    x = np.asarray(x, float)
    x = x[~np.isnan(x)]
    if not len(x):
        return {f"{name}_mean": None, f"{name}_ci95_lo": None, f"{name}_ci95_hi": None}
    m, lo, hi = boot_ci(x)
    return {f"{name}_mean": m, f"{name}_ci95_lo": lo, f"{name}_ci95_hi": hi}


# ------------------------------------------------------------------------------------------------ twin sensitivity
def prep_twin(df, theta=None):
    """Per-run outcomes of A-PQZTO under twin error, paired by seed with the no-response run."""
    notes = []
    if not len(df):
        return pd.DataFrame(), pd.DataFrame(), notes
    if "scen" in df:
        df = df[df.scen == "worm"]
    none = df[df.policy == "none"].drop_duplicates("seed", keep="first")
    ap = df[df.policy == "apqzto"].copy()
    if not len(ap):
        return ap, none, notes
    ths = sorted(set(ap.theta.astype(float).round(4)))
    if len(ths) > 1:              # a re-calibration would change the key; keep one operating point only
        keep = round(theta, 4) if theta is not None and round(theta, 4) in ths else \
            float(ap.theta.astype(float).round(4).mode()[0])
        notes.append(f"apqzto runs with theta {ths} found; kept theta={keep}")
        ap = ap[ap.theta.astype(float).round(4) == keep].copy()
    ap["te"] = ap.twin_err.astype(float).round(2)
    ap["be"] = ap.beta_err.astype(float).round(2)
    ap = ap.drop_duplicates(["te", "be", "seed"], keep="first")
    ever_none = none.set_index("seed")["ever"].astype(float) if len(none) else pd.Series(dtype=float)
    ap["ever_none"] = ap.seed.map(ever_none)
    ap["ce"] = 1 - ap.ever / ap.ever_none.clip(lower=1)          # as analyze_city.derive; NaN if no reference run
    ap["iso_h"] = ap.isolations.astype(float) / EP_H
    ap["disr_frac"] = ap.disruption_h.astype(float) / ap.wsum.astype(float)
    ap["cont"] = ap.contained.fillna(False).astype(bool)
    fc = pd.to_numeric(ap.first_contain, errors="coerce")
    ap["ttc_min"] = np.where(ap.cont, fc * STEP_S / 60.0, np.nan)
    missing = sorted(set(ap.seed) - set(none.seed)) if len(none) else sorted(set(ap.seed))
    if missing:
        notes.append(f"no no-response run for seeds {missing}: CE undefined for those runs")
    return ap, none, notes


def summarize_twin(df, theta=None, n_bad=0):
    ap, none, notes = prep_twin(df, theta)
    if n_bad:
        notes.append(f"{n_bad} unreadable (partially written) line(s) skipped")
    out = {"theta": float(ap.theta.iloc[0]) if len(ap) else theta,
           "twin_err_values": TWIN_ERR, "beta_err_values": BETA_ERR,
           "beta_prior_base": 0.03, "nominal_cell": tkey(*NOMINAL), "exact_cell": tkey(*EXACT),
           "n_runs_apqzto": int(len(ap)), "n_runs_none": int(len(none)),
           "expected_runs_apqzto": len(TWIN_ERR) * len(BETA_ERR) * len(SEEDS), "expected_runs_none": len(SEEDS),
           "none_ever_mean": float(none.ever.mean()) if len(none) else None,
           "cells": {}, "notes": notes}
    out["complete"] = out["n_runs_apqzto"] >= out["expected_runs_apqzto"] and \
        out["n_runs_none"] >= out["expected_runs_none"]
    if not len(ap):
        return out
    ref = ap[(ap.te == EXACT[0]) & (ap.be == EXACT[1])].set_index("seed")["ce"]
    for te in TWIN_ERR:
        for be in BETA_ERR:
            g = ap[(ap.te == te) & (ap.be == be)]
            if not len(g):
                continue
            c = {"twin_err": te, "beta_err": be, "beta_hat": 0.03 * (1 + be), "n": int(len(g)),
                 "n_paired": int(g.ce.notna().sum())}
            c.update(_ci(g.ce, "ce"))
            gi = g.set_index("seed")["ce"]
            idx = gi.dropna().index.intersection(ref.dropna().index)
            c.update(_ci((ref.loc[idx] - gi.loc[idx]).values, "ce_loss_vs_exact"))   # >0: worse than exact twin
            c["n_paired_vs_exact"] = int(len(idx))
            c.update(_ci(g.iso_h, "iso_per_h"))
            c.update(_ci(g.disr_frac, "disr_frac"))
            c["fb_rate_mean"] = float(g.fb_rate.mean())
            c["contained_share"] = float(g.cont.mean())
            c["n_contained"] = int(g.cont.sum())
            c["ttc_min_median"] = float(g.ttc_min.median()) if g.ttc_min.notna().any() else None
            c["ever_mean"] = float(g.ever.mean())
            c["twin_missing_mean"] = float(g.twin_missing.mean()) if "twin_missing" in g else None
            c["twin_spurious_mean"] = float(g.twin_spurious.mean()) if "twin_spurious" in g else None
            out["cells"][tkey(te, be)] = c
    cs = {k: v for k, v in out["cells"].items() if v["ce_mean"] is not None}
    if cs:
        kmin = min(cs, key=lambda k: cs[k]["ce_mean"]); kmax = max(cs, key=lambda k: cs[k]["ce_mean"])
        out["ce_mean_min"], out["ce_mean_min_cell"] = cs[kmin]["ce_mean"], kmin
        out["ce_mean_max"], out["ce_mean_max_cell"] = cs[kmax]["ce_mean"], kmax
        cl = {k: v for k, v in cs.items() if v["ce_loss_vs_exact_mean"] is not None}
        if cl:
            kl = max(cl, key=lambda k: cl[k]["ce_loss_vs_exact_mean"])
            out["max_ce_loss_vs_exact"], out["max_ce_loss_vs_exact_cell"] = cl[kl]["ce_loss_vs_exact_mean"], kl
    out["contained_share_min"] = min(v["contained_share"] for v in out["cells"].values())
    out["iso_per_h_mean_max"] = max(v["iso_per_h_mean"] for v in out["cells"].values())
    out["disr_frac_mean_max"] = max(v["disr_frac_mean"] for v in out["cells"].values())
    return out


# ------------------------------------------------------------------------------------------------ scalability
def prep_scal(df):
    if not len(df):
        return df
    if "scen" in df:
        df = df[df.scen == "worm"]
    df = df[df.policy.isin(SCAL_POL)].copy()
    df["dec_ms"] = 1000.0 * df.decision_s.astype(float) / T_STEPS
    return df.drop_duplicates(["policy", "n_dev", "seed"], keep="first")


def loglog_fit(g):
    g = g[(g.dec_ms > 0) & (g.n_dev > 0)]
    if len(g) < 3 or g.n_dev.nunique() < 2:
        return None
    x, y = np.log10(g.n_dev.astype(float).values), np.log10(g.dec_ms.values)
    r = linregress(x, y)
    tq = float(t_dist.ppf(0.975, len(x) - 2))
    return {"slope": float(r.slope), "slope_ci95_lo": float(r.slope - tq * r.stderr),
            "slope_ci95_hi": float(r.slope + tq * r.stderr), "intercept_log10_ms": float(r.intercept),
            "r2": float(r.rvalue ** 2), "n_points": int(len(x)),
            "n_dev_at_interval_extrap": float(10 ** ((np.log10(INTERVAL_MS) - r.intercept) / r.slope))
            if r.slope > 0 else None}


def summarize_scal(df, n_bad=0):
    d = prep_scal(df)
    out = {"policies": SCAL_POL, "n_runs": int(len(d)),
           "expected_runs": len(SCAL_POL) * len(SCALES) * len(SCAL_SEEDS), "decision_interval_ms": INTERVAL_MS,
           "dec_ms_definition": "1000*decision_s/360 (policy computation per 10-s step, one worker)",
           "cells": {}, "fit": {}, "notes": []}
    out["complete"] = out["n_runs"] >= out["expected_runs"]
    if n_bad:
        out["notes"].append(f"{n_bad} unreadable (partially written) line(s) skipped")
    if not len(d):
        return out
    out["n_dev_values"] = sorted(int(v) for v in d.n_dev.unique())
    for (p, n), g in d.groupby(["policy", "n_dev"]):
        out["cells"][skey(p, n)] = {
            "policy": p, "n_dev": int(n), "scale": float(g.scale.iloc[0]) if "scale" in g else None,
            "n": int(len(g)),
            "dec_ms_mean": float(g.dec_ms.mean()), "dec_ms_min": float(g.dec_ms.min()),
            "dec_ms_max": float(g.dec_ms.max()),
            "dec_share_of_interval_mean": float(g.dec_ms.mean() / INTERVAL_MS),
            "wall_s_mean": float(g.wall_s.mean()), "wall_s_min": float(g.wall_s.min()),
            "wall_s_max": float(g.wall_s.max())}
    for p in SCAL_POL:
        g = d[d.policy == p]
        f = loglog_fit(g)
        if f is not None:
            m = g.groupby("n_dev").dec_ms.mean()
            f["n_dev_smallest"], f["n_dev_largest"] = int(m.index.min()), int(m.index.max())
            f["dec_ms_ratio_largest_vs_smallest"] = float(m.iloc[-1] / m.iloc[0])
        out["fit"][p] = f
    out["notes"].append("wall_s is the whole episode in the worker, including building the City (and loading "
                        "detector evidence) whenever it was not already cached in that process; use dec_ms for timing "
                        "claims")
    return out


# ------------------------------------------------------------------------------------------------ figure
def save_fig(fig, fig_dir, name):
    paths = []
    for ext, kw in ((".png", {}), (".tif", {"pil_kwargs": {"compression": "tiff_lzw"}})):
        p = os.path.join(fig_dir, name + ext)
        fig.savefig(p, dpi=400, bbox_inches="tight", facecolor="white", **kw)
        paths.append(p)
    plt.close(fig)
    return paths


def fig10(TW, SC, fig_dir, name=FIG_NAME):
    fig, axs = plt.subplots(1, 2, figsize=(7.0, 2.7))
    # (a) containment efficiency versus twin graph error, one line per propagation-prior error
    ax = axs[0]
    dodge = {-0.5: -0.9, 0.0: 0.0, 1.0: 0.9}           # percentage points, keeps the error bars apart
    for be in BETA_ERR:
        pts = [(100 * te, TW["cells"][tkey(te, be)]) for te in TWIN_ERR if tkey(te, be) in TW["cells"]]
        pts = [(x, c) for x, c in pts if c["ce_mean"] is not None]
        if not pts:
            continue
        x = np.array([p[0] for p in pts]) + dodge[be]
        m = np.array([p[1]["ce_mean"] for p in pts])
        lo = np.array([p[1]["ce_ci95_lo"] for p in pts]); hi = np.array([p[1]["ce_ci95_hi"] for p in pts])
        ax.errorbar(x, m, yerr=[m - lo, hi - m], color=BETA_COL[be], marker="o", ms=3.4,
                    lw=1.6 if be == 0.0 else 1.1, capsize=1.8, elinewidth=0.7, capthick=0.7, label=BETA_LAB[be],
                    zorder=5 if be == 0.0 else 3)
    ax.set_xticks([100 * te for te in TWIN_ERR])
    ax.set_xlim(-4, 54)
    ax.set_xlabel("Twin graph error (% of links missing, as many spurious)")
    ax.set_ylabel("Containment efficiency (mean, 95% CI)")
    ax.set_title("(a) Containment under twin-model error", fontsize=8.2)
    ax.legend(fontsize=6.6, frameon=False, loc="best")
    # (b) decision time per step versus number of devices (log-log), mean with min-max range over seeds
    ax = axs[1]
    lows = []
    for p in SCAL_POL:
        cs = sorted([c for c in SC["cells"].values() if c["policy"] == p], key=lambda c: c["n_dev"])
        if not cs:
            continue
        x = np.array([c["n_dev"] for c in cs], float)
        m = np.array([c["dec_ms_mean"] for c in cs])
        lo = np.array([c["dec_ms_min"] for c in cs]); hi = np.array([c["dec_ms_max"] for c in cs])
        lows.append(lo.min())
        ax.errorbar(x, m, yerr=[m - lo, hi - m], color=POL_COL[p], marker=POL_MARK[p], ms=3.8,
                    lw=1.8 if p == "apqzto" else 1.1, capsize=1.8, elinewidth=0.7, capthick=0.7, label=POL_LAB[p],
                    zorder=5 if p == "apqzto" else 3)
    ns = SC.get("n_dev_values") or [1500, 3000, 6000, 12000]
    ax.set_xscale("log"); ax.set_yscale("log")
    ax.set_xlim(ns[0] / 1.3, ns[-1] * 1.3)
    # y range chosen so that the 10-s line sits at a fixed height (LINE_AT of the axis), leaving a band for its label
    LINE_AT = 0.86
    bot = max(min(min(lows) / 2.5, INTERVAL_MS / 100), 1e-3) if lows else 0.1
    span = np.log10(INTERVAL_MS) - np.log10(bot)
    ax.set_ylim(bot, 10 ** (np.log10(INTERVAL_MS) + span * (1 - LINE_AT) / LINE_AT))
    ax.axhline(INTERVAL_MS, color="#444444", ls="--", lw=0.9, zorder=2)
    ax.text(ns[0] / 1.22, INTERVAL_MS * 1.18, "decision interval (10 s)", fontsize=6.8, color="#444444",
            ha="left", va="bottom")
    ax.xaxis.set_major_locator(FixedLocator(ns)); ax.xaxis.set_minor_locator(NullLocator())
    ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:,.0f}"))
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:,.0f}" if v >= 1 else f"{v:g}"))
    ax.yaxis.set_minor_formatter(NullFormatter())
    ax.set_xlabel("Number of devices")
    ax.set_ylabel("Decision time per step (ms)")
    ax.set_title("(b) Decision time versus city size", fontsize=8.2)
    # legend just below the 10-s line on the left, unless the data reach that region (then lower right)
    left = [c["dec_ms_max"] for c in SC["cells"].values() if c["n_dev"] <= ns[min(1, len(ns) - 1)]]
    frac = (np.log10(max(left)) - np.log10(bot)) / (span / LINE_AT) if left else 0.0
    if frac < 0.55:
        ax.legend(fontsize=6.6, frameon=False, loc="upper left", bbox_to_anchor=(0.0, LINE_AT - 0.02))
    else:
        ax.legend(fontsize=6.6, frameon=False, loc="lower right")
    fig.tight_layout()
    return save_fig(fig, fig_dir, name)


# ------------------------------------------------------------------------------------------------ pipeline
def _clean(o):
    """JSON-safe copy: numpy scalars to Python, NaN/inf to null."""
    if isinstance(o, dict):
        return {str(k): _clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_clean(v) for v in o]
    if isinstance(o, (np.bool_, bool)):
        return bool(o)
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (float, np.floating)):
        return None if not np.isfinite(o) else float(o)
    return o


def run(twin_path=TWIN_IN, scal_path=SCAL_IN, out_json=OUT_JSON, fig_dir=FIG, theta=None, selftest=False):
    tw_df, tw_bad = load_jsonl(twin_path)
    sc_df, sc_bad = load_jsonl(scal_path)
    if not len(tw_df) and not len(sc_df):
        print("no input yet:", twin_path, "and", scal_path, "are missing or empty; nothing written")
        return None
    S = {"meta": {"generated": time.strftime("%Y-%m-%d %H:%M:%S"), "selftest_fake_data": bool(selftest),
                  "twin_file": twin_path, "scal_file": scal_path,
                  "ce_definition": "1 - ever(apqzto)/max(ever(none),1), paired by seed",
                  "ci": "95% percentile bootstrap of the mean over seeds (B=5000, seed 0; analyze_fl.boot_ci)",
                  "episode_h": EP_H},
         "twin": summarize_twin(tw_df, theta, tw_bad) if len(tw_df) else None,
         "scal": summarize_scal(sc_df, sc_bad) if len(sc_df) else None}
    S["meta"]["twin_complete"] = bool(S["twin"] and S["twin"]["complete"])
    S["meta"]["scal_complete"] = bool(S["scal"] and S["scal"]["complete"])
    S["meta"]["figure"] = None
    if S["twin"] and S["twin"]["cells"] and S["scal"] and S["scal"]["cells"]:
        S["meta"]["figure"] = fig10(S["twin"], S["scal"], fig_dir)
    else:
        print("figure not drawn: needs both twin and scalability results")
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(_clean(S), f, indent=1, allow_nan=False, ensure_ascii=False)
    if S["twin"] is not None and not S["twin"]["complete"]:
        t = S["twin"]
        print(f"WARNING: twin results incomplete: {t['n_runs_apqzto']}/{t['expected_runs_apqzto']} A-PQZTO runs, "
              f"{t['n_runs_none']}/{t['expected_runs_none']} no-response runs")
    if S["scal"] is not None and not S["scal"]["complete"]:
        print(f"WARNING: scalability results incomplete: {S['scal']['n_runs']}/{S['scal']['expected_runs']} runs")
    print("wrote", out_json, *(S["meta"]["figure"] or []))
    return S


# ------------------------------------------------------------------------------------------------ self-test
def fake_rows(rng):
    """Synthetic rows with the fields of run_city.py output. FAKE: for testing this script only."""
    common = dict(FAKE_SELFTEST=True, scen="worm", wsum=673.55, n_dev=1500, twin_missing=470, twin_spurious=470)
    twin, scal = [], []
    for s in SEEDS:
        en = int(rng.integers(300, 900))
        twin.append({**common, "phase": "twin", "policy": "none", "theta": 0.0, "seed": s, "ever": en,
                     "isolations": 0, "disruption_h": 0.0, "fb_rate": 0.0, "decision_s": 0.0, "first_contain": None,
                     "contained": False, "wall_s": 3.0, "key": f"SELFTEST|twin_none|{s}"})
        for te in TWIN_ERR:
            for be in BETA_ERR:
                ce = float(np.clip(0.93 - 0.30 * te - 0.04 * abs(be) + rng.normal(0, 0.03), 0, 1))
                cont = bool(rng.random() < 0.95 - 0.8 * te)
                twin.append({**common, "phase": "twin", "policy": "apqzto", "theta": -0.19, "seed": s,
                             "twin_err": te, "beta_err": be, "ever": max(3, int(round(en * (1 - ce)))),
                             "isolations": int(rng.poisson(2 + 6 * te + 2 * max(be, 0))),
                             "disruption_h": float(rng.uniform(0.5, 2.5) * (1 + te)), "fb_rate": 0.001,
                             "decision_s": 8.0, "first_contain": int(rng.integers(20, 200)) if cont else None,
                             "contained": cont, "wall_s": 12.0,
                             "key": f"SELFTEST|twin|{te}|{be}|-0.19|{s}"})
    # exercise the cleaning rules: a duplicated key (must be ignored), a run at another theta (must be dropped),
    # a missing no-response run (last seed: CE undefined), a truncated last line (must be skipped)
    dup = dict(twin[1]); dup["ever"] = 99999
    other = dict(twin[1]); other["theta"] = 0.5; other["ever"] = 99999; other["key"] = "SELFTEST|twin|other_theta"
    twin = [r for r in twin if r["key"] != f"SELFTEST|twin_none|{SEEDS[-1]}"] + [dup, other]
    slope = {"apqzto": 1.10, "apqzto_nodt": 1.00, "fl_ids": 0.95}
    base = {"apqzto": 40.0, "apqzto_nodt": 8.0, "fl_ids": 3.0}
    for p in SCAL_POL:
        for sc in SCALES:
            for s in SCAL_SEEDS:
                ms = base[p] * sc ** slope[p] * float(np.exp(rng.normal(0, 0.05)))
                scal.append({**common, "phase": "scal", "policy": p, "theta": 0.0, "seed": s, "scale": sc,
                             "n_dev": int(1500 * sc), "decision_s": ms * T_STEPS / 1000.0,
                             "wall_s": ms * T_STEPS / 1000.0 + 15 * sc, "ever": 50, "isolations": 1,
                             "disruption_h": 1.0, "fb_rate": 0.001, "first_contain": 30, "contained": True,
                             "key": f"SELFTEST|scal|{p}|{sc}|{s}"})
    return twin, scal, slope


def _stamp(p):
    return os.path.getmtime(p) if os.path.exists(p) else None


def selftest(outdir=None, keep=False):
    tmp = outdir or tempfile.mkdtemp(prefix="apq_fig10_selftest_")
    os.makedirs(tmp, exist_ok=True)
    real = {os.path.normcase(os.path.abspath(p)) for p in
            (OUT_JSON, os.path.join(FIG, FIG_NAME + ".png"), os.path.join(FIG, FIG_NAME + ".tif"), TWIN_IN, SCAL_IN)}
    tw_p, sc_p = os.path.join(tmp, "FAKE_twin_v3.jsonl"), os.path.join(tmp, "FAKE_scal_v3.jsonl")
    out_json = os.path.join(tmp, "FAKE_city_extra_summary.json")
    for p in (tw_p, sc_p, out_json, os.path.join(tmp, FIG_NAME + ".png"), os.path.join(tmp, FIG_NAME + ".tif")):
        assert os.path.normcase(os.path.abspath(p)) not in real, "self-test must not touch real outputs"
    before = {p: _stamp(p) for p in real}
    twin, scal, slope = fake_rows(np.random.default_rng(12345))
    with open(tw_p, "w") as f:
        f.writelines(json.dumps(r) + "\n" for r in twin)
        f.write('{"key": "SELFTEST|truncated", "ever": 1')            # half-written line, no newline
    with open(sc_p, "w") as f:
        f.writelines(json.dumps(r) + "\n" for r in scal)
    print("self-test (FAKE data) ->", tmp)
    S = run(tw_p, sc_p, out_json, tmp, theta=-0.19, selftest=True)
    ok = True

    def check(cond, msg):
        nonlocal ok
        print(("  ok   " if cond else "  FAIL ") + msg)
        ok &= bool(cond)

    S2 = json.load(open(out_json, encoding="utf-8"), parse_constant=lambda c: (_ for _ in ()).throw(ValueError(c)))
    check(S2["meta"]["selftest_fake_data"] is True, "summary flagged as fake")
    T, C = S2["twin"], S2["scal"]
    check(len(T["cells"]) == 12, "12 twin cells")
    check(all(c["n"] == 20 and c["n_paired"] == 19 for c in T["cells"].values()),
          "20 runs per cell, 19 paired (the last seed has no reference run)")
    first = {}
    for r in twin:                                                 # first copy per key, as the loader does
        if r["policy"] == "apqzto" and r["theta"] == -0.19 and r["twin_err"] == 0.0 and r["beta_err"] == -0.5:
            first.setdefault(r["seed"], r)
    none = {r["seed"]: r["ever"] for r in twin if r["policy"] == "none"}
    exp = np.mean([1 - first[s]["ever"] / max(none[s], 1) for s in first if s in none])
    check(abs(T["cells"][tkey(0.0, -0.5)]["ce_mean"] - exp) < 1e-12, "dedup keeps the first copy; CE recomputed")
    check(any("kept theta=-0.19" in n for n in T["notes"]), "other-theta run dropped")
    check(any("unreadable" in n for n in T["notes"]), "truncated line skipped")
    check(abs(T["cells"][tkey(*EXACT)]["ce_loss_vs_exact_mean"]) < 1e-12, "loss vs exact twin is 0 for exact cell")
    check(all(c["ce_ci95_lo"] <= c["ce_mean"] <= c["ce_ci95_hi"] for c in T["cells"].values()), "CI brackets mean")
    check(T["complete"] is False and S2["meta"]["twin_complete"] is False, "incomplete twin flagged (19 none runs)")
    check(len(C["cells"]) == 12 and all(c["n"] == 3 for c in C["cells"].values()), "12 scalability cells x 3 seeds")
    check(C["complete"] is True, "scalability complete")
    for p in SCAL_POL:
        check(abs(C["fit"][p]["slope"] - slope[p]) < 0.1,
              f"log-log slope {p}: {C['fit'][p]['slope']:.3f} (true {slope[p]})")
    c1 = C["cells"][skey("apqzto", 1500)]
    check(c1["dec_ms_min"] <= c1["dec_ms_mean"] <= c1["dec_ms_max"], "min <= mean <= max")
    figs = S2["meta"]["figure"] or []
    check(len(figs) == 2 and all(os.path.dirname(os.path.abspath(p)) == os.path.abspath(tmp) for p in figs),
          "figure written to the temporary folder only")
    if len(figs) == 2:
        import matplotlib.image as mpimg
        from PIL import Image
        img = mpimg.imread(figs[0])
        check(img.shape[1] > 2400 and img.shape[0] > 900 and float(img[..., :3].std()) > 0.02,
              f"PNG renders ({img.shape[1]}x{img.shape[0]} px, not blank)")
        with Image.open(figs[1]) as im:
            dpi = float(im.info.get("dpi", (0, 0))[0])
            check(im.info.get("compression") == "tiff_lzw" and abs(dpi - 400) < 1,
                  f"TIFF LZW at {dpi:.0f} dpi ({im.size[0]}x{im.size[1]} px)")
    check(all(_stamp(p) == before[p] for p in real), "real inputs/outputs untouched (existence and mtime)")
    print("SELFTEST PASSED" if ok else "SELFTEST FAILED")
    if not keep and outdir is None:
        shutil.rmtree(tmp, ignore_errors=True)
    elif keep or outdir:
        print("kept:", tmp)
    return ok


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--selftest", action="store_true", help="run the pipeline on synthetic FAKE rows in a temp folder")
    ap.add_argument("--keep", action="store_true", help="keep the self-test folder")
    ap.add_argument("--outdir", help="self-test output folder (default: a new temporary folder)")
    a = ap.parse_args()
    if a.selftest:
        sys.exit(0 if selftest(a.outdir, a.keep) else 1)
    th = json.load(open(THETA_IN)).get("apqzto") if os.path.exists(THETA_IN) else None
    run(theta=th)
