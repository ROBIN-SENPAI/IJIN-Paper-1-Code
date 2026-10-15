# Aggregation, paired statistics and figures for the city-scale experiments.
import json, os
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy.stats import wilcoxon
from analyze_fl import boot_ci, cliffs, bh, save

RES = r"E:\A-PQZTO_work\results"
plt.rcParams.update({"font.family": "Times New Roman", "font.size": 8, "mathtext.fontset": "stix",
                     "axes.spines.top": False, "axes.spines.right": False, "axes.grid": True, "grid.color": "#e6e5e1",
                     "grid.linewidth": 0.6})
STEP_H = 10 / 3600.0
T_STEPS, T0 = 360, 60
POL_LAB = {"none": "No response", "static_zta": "Static ZTA", "fl_ids": "FL-only IDS", "zta_fixedpqc": "ZTA + fixed PQC",
           "dt_ids_nofl": "DT-assisted IDS w/o FL", "apqzto": "A-PQZTO", "apqzto_nopqc": "A-PQZTO w/o PQC",
           "apqzto_nodt": "A-PQZTO w/o twin", "apqzto_nofl": "A-PQZTO w/o FL", "apqzto_notrust": "A-PQZTO w/o adaptive trust",
           "apqzto_nobeh": "A-PQZTO w/o behavioural profile", "apqzto_noveto": "A-PQZTO w/o zero-trust veto",
           "apqzto_twinrisk": "Original design (additive, twin risk in trust)"}
POL_COL = {"none": "#7f7f7f", "static_zta": "#CC79A7", "fl_ids": "#0072B2", "zta_fixedpqc": "#E69F00",
           "dt_ids_nofl": "#009E73", "apqzto": "#D55E00", "apqzto_nodt": "#56B4E9", "apqzto_nofl": "#000000"}
BASE = ["static_zta", "zta_fixedpqc", "fl_ids", "dt_ids_nofl", "apqzto"]
ABL = ["apqzto", "apqzto_nopqc", "apqzto_nodt", "apqzto_nofl", "apqzto_notrust", "apqzto_nobeh", "apqzto_noveto",
       "apqzto_twinrisk"]
SCEN = ["worm", "ddos", "evasion", "injection", "impostor", "benign"]


def load(name):
    p = os.path.join(RES, "city", name)
    if not os.path.exists(p):
        return pd.DataFrame()
    seen = {}
    for l in open(p):
        r = json.loads(l)
        seen.setdefault(r["key"], r)
    return pd.DataFrame(list(seen.values()))


def derive(df):
    """Per-run outcome measures, paired with the no-response run of the same seed and scenario."""
    none = df[df.policy == "none"].set_index(["scen", "seed"])
    out = []
    for _, r in df.iterrows():
        k = (r.scen, r.seed)
        n = none.loc[k] if k in none.index else None
        d = {"policy": r.policy, "scen": r.scen, "seed": r.seed, "fb": r.fb_rate,
             "disr_h": r.disruption_h, "disr_frac": r.disruption_h / r.wsum, "pq_hs": r.n_pq_hs,
             "pq_reauth": r.n_pq_reauth, "hndl": r.hndl_sensitive, "hndl_all": r.hndl_all,
             "dec_ms": 1000 * r.decision_s / T_STEPS, "iso": r.isolations, "ever": r.ever}
        if n is not None:
            if r.scen == "worm":
                d["ce"] = 1 - r.ever / max(n.ever, 1)
                d["contained"] = float(bool(r.contained))
                d["ttc_min"] = (r.first_contain * 10 / 60) if r.contained else np.nan
            if r.scen in ("ddos", "evasion", "injection"):
                d["asr"] = r.attack_steps_eff / max(n.attack_steps_eff, 1)
            if r.scen == "impostor":
                d["asr"] = r.impostor_access / max(n.impostor_access, 1)
                d["asr_transport"] = r.impostor_access_transport / max(n.impostor_access_transport, 1)
        out.append(d)
    return pd.DataFrame(out)


def summarize(X):
    S = {}
    for (p, s), g in X.groupby(["policy", "scen"]):
        e = {}
        for mcol in ("fb", "disr_h", "disr_frac", "pq_hs", "pq_reauth", "hndl", "hndl_all", "dec_ms", "iso", "ever",
                     "ce", "asr", "asr_transport", "contained", "ttc_min"):
            if mcol in g and g[mcol].notna().any():
                e[mcol] = boot_ci(g[mcol].dropna().values)
        if "ttc_min" in g and g["ttc_min"].notna().any():
            e["ttc_median"] = float(g["ttc_min"].median())
        S[f"{p}|{s}"] = e
    return S


def tests(X):
    T = []
    for s in SCEN[:-1]:
        metric = "ce" if s == "worm" else "asr"
        sub = X[X.scen == s]
        a = sub[sub.policy == "apqzto"].set_index("seed")[metric]
        for p in BASE[:-1] + ABL[1:]:
            if p == "apqzto":
                continue
            b = sub[sub.policy == p].set_index("seed")[metric]
            idx = a.index.intersection(b.index)
            if len(idx) < 5:
                continue
            x, y = a.loc[idx].values, b.loc[idx].values
            dlt = x - y
            pv = 1.0 if np.allclose(dlt, 0) else float(wilcoxon(x, y, zero_method="zsplit").pvalue)
            T.append(dict(scen=s, metric=metric, vs=p, n=int(len(idx)), mean_diff=float(dlt.mean()), p=pv,
                          cliff=cliffs(x, y), better=int(((dlt > 0) if metric == "ce" else (dlt < 0)).sum())))
    if T:
        q = bh([t["p"] for t in T])
        for t, qq in zip(T, q):
            t["q_bh"] = float(qq)
    return T


def fig_city(S, tr):
    fig, axs = plt.subplots(1, 2, figsize=(6.5, 3.2), gridspec_kw={"width_ratios": [1.1, 1]})
    ax = axs[0]
    if len(tr):
        for p in ["none", "static_zta", "fl_ids", "dt_ids_nofl", "apqzto_nodt", "apqzto"]:
            g = tr[tr.policy == p]
            if not len(g):
                continue
            arr = np.array([[x[0] for x in t] for t in g["trace"]])
            t_min = (np.arange(arr.shape[1]) - T0) * 10 / 60
            mu = arr.mean(0)
            ax.plot(t_min, mu, color=POL_COL[p], lw=2.0 if p == "apqzto" else 1.1, label=POL_LAB[p])
            ax.fill_between(t_min, np.percentile(arr, 10, 0), np.percentile(arr, 90, 0), color=POL_COL[p], alpha=0.10,
                            lw=0)
        ax.set_yscale("symlog", linthresh=10)
        ax.set_xlim(-2, (T_STEPS - T0) * 10 / 60)
        ax.set_xlabel("Minutes after worm onset")
        ax.set_ylabel("Compromised devices (mean, 10–90% band)")
        ax.set_title("(a) Worm outbreak in a 1,500-device city", fontsize=8.4)
    ax = axs[1]
    scen = ["ddos", "evasion", "injection", "impostor"]
    lab = {"ddos": "Flooding", "evasion": "Credential\nmisuse", "injection": "Data\ninjection", "impostor": "Impostor"}
    pols = ["static_zta", "fl_ids", "dt_ids_nofl", "apqzto_nodt", "apqzto"]
    w = 0.16
    for j, p in enumerate(pols):
        v = [S.get(f"{p}|{s}", {}).get("asr", (np.nan,) * 3) for s in scen]
        m = np.array([t[0] for t in v]); lo = m - np.array([t[1] for t in v]); hi = np.array([t[2] for t in v]) - m
        ax.bar(np.arange(len(scen)) + (j - 2) * w, m, w * 0.9, color=POL_COL[p], yerr=[lo, hi], capsize=1.2,
               error_kw={"lw": 0.6}, label=POL_LAB[p], zorder=3)
    ax.set_xticks(np.arange(len(scen))); ax.set_xticklabels([lab[s] for s in scen])
    ax.set_ylabel("Attack-success ratio vs. no response")
    ax.set_title("(b) Non-spreading attacks (lower is better)", fontsize=8.4)
    # one legend for both panels, below the axes (panel (b) uses the same colours without "No response")
    h, l = axs[0].get_legend_handles_labels()
    fig.legend(h, l, loc="lower center", ncol=3, fontsize=7.8, frameon=False, bbox_to_anchor=(0.5, 0.0),
               columnspacing=1.6, handlelength=2.0)
    fig.tight_layout(rect=(0, 0.12, 1, 1))
    save(fig, "fig8_city")


if __name__ == "__main__":
    df = load("main_v3.jsonl")
    X = derive(df)
    S = summarize(X)
    T = tests(X)
    th = json.load(open(os.path.join(RES, "city", "theta_v3.json")))
    tr = load("trace_v3.jsonl")
    json.dump({"summary": S, "tests": T, "theta": th, "n_runs": int(len(df))},
              open(os.path.join(RES, "city_summary.json"), "w"), indent=1, default=float)
    fig_city(S, tr)
    print("ok", len(df))
