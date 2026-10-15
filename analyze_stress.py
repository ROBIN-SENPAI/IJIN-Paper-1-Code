# Stress tests (fast worm, twin fidelity under the fast worm), PQ handshake-cost sensitivity and scalability.
# Inputs : results/city/stress_v3.jsonl, results/city/pqcost_v3.jsonl, results/city/main_v3.jsonl (no-response runs for
#          the impostor/evasion reference), results/city_extra_summary.json (scalability cells)
# Outputs: results/stress_summary.json, figures/fig10_stress.png/.tif
import json, os
import numpy as np
import pandas as pd
import matplotlib
import matplotlib.ticker
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy.stats import wilcoxon
from analyze_fl import boot_ci, cliffs, bh, save
from analyze_city import POL_LAB, POL_COL, T_STEPS

RES = r"E:\A-PQZTO_work\results"
CITY = os.path.join(RES, "city")
plt.rcParams.update({"font.family": "Times New Roman", "font.size": 8, "mathtext.fontset": "stix",
                     "axes.spines.top": False, "axes.spines.right": False, "axes.grid": True, "grid.color": "#e6e5e1",
                     "grid.linewidth": 0.6})
EXTRA_COL = {"apqzto_notrust": "#882255", "apqzto_noveto": "#44AA99"}
STRESS_POL = ["static_zta", "fl_ids", "dt_ids_nofl", "apqzto_notrust", "apqzto_noveto", "apqzto_nodt", "apqzto"]
BETA_PRIOR = 0.03
SLICE_BUDGET_MS = {"transport": 10.0, "safety": 20.0, "energy": 50.0, "health": 100.0}
PQ_MS = 2.0


def jl(path):
    rows = {}
    for l in open(path):
        r = json.loads(l)
        rows.setdefault(r["key"], r)
    return pd.DataFrame(list(rows.values()))


def paired(a, b, lower_better=True):
    idx = a.index.intersection(b.index)
    x, y = a.loc[idx].values.astype(float), b.loc[idx].values.astype(float)
    d = x - y
    p = 1.0 if np.allclose(d, 0) else float(wilcoxon(x, y, zero_method="zsplit").pvalue)
    return dict(n=int(len(idx)), mean_diff=float(d.mean()), p=p, cliff=cliffs(x, y),
                better=int(((d < 0) if lower_better else (d > 0)).sum()),
                worse=int(((d > 0) if lower_better else (d < 0)).sum()))


def cell(g, none_ever):
    e = {"n": int(len(g))}
    e["ever"] = boot_ci(g.ever.values)
    ce = [1 - r.ever / max(none_ever.get(r.seed, 1), 1) for r in g.itertuples()]
    e["ce"] = boot_ci(ce)
    e["contained"] = float(g.contained.astype(float).mean())
    ttc = [r.first_contain * 10 / 60 for r in g.itertuples() if r.contained]
    e["ttc_median"] = float(np.median(ttc)) if ttc else None
    e["iso_per_h"] = boot_ci(g.isolations.values)
    e["disr_frac"] = boot_ci((g.disruption_h / g.wsum).values)
    e["fb"] = boot_ci(g.fb_rate.values)
    return e


def stress_summary():
    df = jl(os.path.join(CITY, "stress_v3.jsonl"))
    out = {"n_runs": int(len(df))}
    st = df[df.phase == "stress"]
    none_ever = st[st.policy == "none"].set_index("seed").ever.to_dict()
    out["none_ever"] = boot_ci(list(none_ever.values()))
    out["policies"] = {p: cell(st[st.policy == p], none_ever) for p in STRESS_POL if (st.policy == p).any()}
    a = st[st.policy == "apqzto"].set_index("seed").ever
    T = []
    for p in STRESS_POL[:-1]:
        b = st[st.policy == p].set_index("seed").ever
        if len(b):
            T.append(dict(vs=p, metric="ever", **paired(a, b)))
    tw = df[df.phase == "stress_twin"].copy()
    tw["beta_hat"] = (BETA_PRIOR * (1 + tw.beta_err)).round(3)
    cells = {}
    for (te, bh_), g in tw.groupby(["twin_err", "beta_hat"]):
        cells[f"twin_err={te}|beta_hat={bh_}"] = dict(twin_err=float(te), beta_hat=float(bh_), **cell(g, none_ever))
    out["twin_cells"] = cells
    # paired contrasts inside the twin sweep
    def ser(te, bh_):
        g = tw[(tw.twin_err == te) & (tw.beta_hat == bh_)]
        return g.set_index("seed").ever
    TT = []
    for te in sorted(tw.twin_err.unique()):
        TT.append(dict(contrast=f"beta_hat 0.10 vs 0.03 at twin_err {te}", **paired(ser(te, 0.1), ser(te, 0.03))))
    for bh_ in sorted(tw.beta_hat.unique()):
        TT.append(dict(contrast=f"twin_err 0.5 vs 0.0 at beta_hat {bh_}", **paired(ser(0.5, bh_), ser(0.0, bh_))))
    TT.append(dict(contrast="apqzto(beta_hat 0.10, twin_err 0.1) vs fl_ids",
                   **paired(ser(0.1, 0.1), st[st.policy == "fl_ids"].set_index("seed").ever)))
    allT = T + TT
    q = bh([t["p"] for t in allT])
    for t, qq in zip(allT, q):
        t["q_bh"] = float(qq)
    out["tests_policies"], out["tests_twin"] = T, TT
    return out


def pqcost_summary():
    p = os.path.join(CITY, "pqcost_v3.jsonl")
    if not os.path.exists(p):
        return None
    df = jl(p)
    main = jl(os.path.join(CITY, "main_v3.jsonl"))
    nn = main[main.policy == "none"]
    ref_imp = nn[nn.scen == "impostor"].set_index("seed").impostor_access.to_dict()
    ref_imp_tr = nn[nn.scen == "impostor"].set_index("seed").impostor_access_transport.to_dict()
    ref_ev = nn[nn.scen == "evasion"].set_index("seed").attack_steps_eff.to_dict()
    out = {"n_runs": int(len(df)), "pq_ms": PQ_MS, "cells": {}}
    for (dfac, sc), g in df.groupby(["dev_factor", "scen"]):
        e = {"dev_factor": float(dfac), "hs_ms": PQ_MS * float(dfac), "scen": sc, "n": int(len(g))}
        if sc == "impostor":
            e["asr"] = boot_ci([r.impostor_access / max(ref_imp[r.seed], 1) for r in g.itertuples()])
            e["asr_transport"] = boot_ci([r.impostor_access_transport / max(ref_imp_tr[r.seed], 1)
                                          for r in g.itertuples()])
        if sc == "evasion":
            e["asr"] = boot_ci([r.attack_steps_eff / max(ref_ev[r.seed], 1) for r in g.itertuples()])
        e["fb"] = boot_ci(g.fb_rate.values)
        e["pq_reauth"] = boot_ci(g.n_pq_reauth.values)
        e["pq_deferred"] = boot_ci(g.pq_deferred.values)
        e["hndl_all"] = boot_ci(g.hndl_all.values)
        e["slices_fitting"] = [k for k, v in SLICE_BUDGET_MS.items() if PQ_MS * dfac <= v]
        out["cells"][f"{dfac}|{sc}"] = e
    return out


def fig(S, P, X):
    fig, ax = plt.subplots(2, 2, figsize=(6.5, 5.6))
    FS, FT = 7.8, 8.4                                  # annotation / legend size and panel-title size (pt)
    # (a) fast worm by policy
    a = ax[0, 0]
    pols = [p for p in STRESS_POL if p in S["policies"]]
    for i, p in enumerate(pols):
        m, lo, hi = S["policies"][p]["ever"]
        a.errorbar(i, m, yerr=[[m - lo], [hi - m]], fmt="o", ms=5, color=POL_COL.get(p, EXTRA_COL.get(p, "#555555")), capsize=2, lw=1.2)
        a.text(i, hi * 1.12, f"{m:.0f}", ha="center", va="bottom", fontsize=FS, color="#333333")
    a.set_yscale("log")
    a.set_ylim(10, 1300)
    a.set_yticks([10, 20, 50, 100, 200, 500, 1000])
    a.set_yticklabels(["10", "20", "50", "100", "200", "500", "1000"])
    a.minorticks_off()
    a.set_xticks(range(len(pols)))
    a.set_xticklabels([POL_LAB[p].replace("A-PQZTO w/o ", "w/o ").replace("zero-trust veto", "veto") for p in pols],
                      rotation=35, ha="right", rotation_mode="anchor", fontsize=8)
    a.set_ylabel("Devices ever infected (log scale)")
    a.set_title(f"(a) Fast worm, $\\beta$ = 0.10 (no response: {S['none_ever'][0]:.0f})", fontsize=FT)
    # (b) twin fidelity under the fast worm
    b = ax[0, 1]
    errs = sorted({c["twin_err"] for c in S["twin_cells"].values()})
    shades = ["#9ecae1", "#6baed6", "#3182bd", "#08519c"]
    for j, te in enumerate(errs):
        cs = sorted([c for c in S["twin_cells"].values() if c["twin_err"] == te], key=lambda c: c["beta_hat"])
        xs = [c["beta_hat"] for c in cs]
        ys = [c["ever"][0] for c in cs]
        b.plot(xs, ys, "-o", ms=4, lw=1.4, color=shades[j % 4], label=f"{100 * te:.0f}% of links wrong")
    fl = S["policies"].get("fl_ids")
    if fl:
        b.axhline(fl["ever"][0], ls="--", lw=1.0, color=POL_COL["fl_ids"])
        b.text(0.017, fl["ever"][0] + 0.8, "FL-only IDS", ha="left", va="bottom", fontsize=FS, color=POL_COL["fl_ids"])
    b.axvline(0.10, ls=":", lw=0.9, color="#555555")
    b.set_ylim(10, 60)
    b.text(0.097, 11.5, "true rate", ha="right", va="bottom", fontsize=FS, color="#555555")
    b.set_xticks(sorted({c["beta_hat"] for c in S["twin_cells"].values()}))
    b.set_xlabel("Twin's propagation-rate estimate $\\hat{\\beta}$")
    b.set_ylabel("Devices ever infected")
    b.set_title("(b) A-PQZTO, twin fidelity under the fast worm", fontsize=FT)
    b.legend(fontsize=FS, frameon=False, loc="center left", bbox_to_anchor=(0.0, 0.57), labelspacing=0.3,
             handlelength=1.8)
    # (c) PQ handshake cost (series are labelled directly; the slice budgets L_d are the dotted lines)
    c = ax[1, 0]
    if P:
        dfs = sorted({v["dev_factor"] for v in P["cells"].values()})
        hs = [PQ_MS * d for d in dfs]
        imp = [100 * P["cells"][f"{d}|impostor"]["asr"][0] for d in dfs]
        imp_lo = [100 * P["cells"][f"{d}|impostor"]["asr"][1] for d in dfs]
        imp_hi = [100 * P["cells"][f"{d}|impostor"]["asr"][2] for d in dfs]
        ev = [100 * P["cells"][f"{d}|evasion"]["asr"][0] for d in dfs]
        c.errorbar(hs, imp, yerr=[np.subtract(imp, imp_lo), np.subtract(imp_hi, imp)], fmt="o", ms=4.5, capsize=2,
                   lw=1.2, color=POL_COL["apqzto"], label="Impostor success")
        c.plot(hs, ev, "s", ms=4, color="#555555", label="Credential-misuse success")
        for k, v in SLICE_BUDGET_MS.items():
            c.axvline(v, ls=":", lw=0.8, color="#999999")
        c.set_xscale("log")
        c.set_xticks(hs)
        c.set_xticklabels([f"{h:g}" for h in hs])
        c.minorticks_off()
        top = max(max(imp_hi), max(ev)) * 1.3
        c.set_ylim(0, top)
        for k, v in SLICE_BUDGET_MS.items():
            c.text(v * 0.94, top * 0.47, k + " budget", rotation=90, va="center", ha="right", fontsize=FS,
                   color="#777777")
        c.text(hs[0] * 0.92, max(ev) + 0.055 * top, "Credential-misuse\nsuccess", ha="left", va="bottom",
               fontsize=FS, color="#555555", linespacing=1.1)
        c.text(hs[0] * 0.92, max(imp_hi[:2]) + 0.05 * top, "Impostor success", ha="left", va="bottom", fontsize=FS,
               color=POL_COL["apqzto"])
        c.set_xlabel("PQ handshake latency on the device (ms)")
        c.set_ylabel("Attack-success ratio (%)")
    c.set_title("(c) A-PQZTO, cost of PQ re-authentication", fontsize=FT)
    # (d) scalability
    d = ax[1, 1]
    for p in X["policies"]:
        cs = sorted([v for v in X["cells"].values() if v["policy"] == p], key=lambda v: v["n_dev"])
        d.plot([v["n_dev"] for v in cs], [v["dec_ms_mean"] for v in cs], "-o", ms=4, lw=1.4,
               color=POL_COL.get(p, "#555555"), label=POL_LAB[p])
    d.set_xscale("log"); d.set_yscale("log")
    d.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda y, _: f"{y:g}"))
    nd = sorted({v["n_dev"] for v in X["cells"].values()})
    d.set_xticks(nd); d.set_xticklabels([f"{n:,}" for n in nd])
    d.minorticks_off()
    d.set_xlabel("Devices in the city")
    d.set_ylabel("Decision time per 10-s step (ms)")
    d.set_title("(d) Scalability (one worker)", fontsize=FT)
    d.legend(fontsize=FS, frameon=False, loc="upper left", labelspacing=0.3)
    fig.tight_layout(h_pad=1.2)
    save(fig, "fig10_stress")


if __name__ == "__main__":
    S = stress_summary()
    P = pqcost_summary()
    X = json.load(open(os.path.join(RES, "city_extra_summary.json")))
    out = {"stress": S, "pqcost": P, "scal": X["scal"], "twin_nominal_note":
           "nominal worm: the twin approved no isolation in any cell, so graph and rate errors had no effect"}
    json.dump(out, open(os.path.join(RES, "stress_summary.json"), "w"), indent=1)
    fig(S, P, X["scal"])
    print("policies:", {p: round(v["ever"][0], 1) for p, v in S["policies"].items()}, "none", S["none_ever"][0])
    print("contained:", {p: v["contained"] for p, v in S["policies"].items()})
    print("iso/h:", {p: round(v["iso_per_h"][0], 2) for p, v in S["policies"].items()})
    for t in S["tests_policies"] + S["tests_twin"]:
        print(t.get("vs", t.get("contrast")), f"diff={t['mean_diff']:+.1f} better={t['better']}/{t['n']} "
              f"q={t['q_bh']:.3f} cliff={t['cliff']:+.2f}")
    for k, c in sorted(S["twin_cells"].items()):
        print(k, "ever", round(c["ever"][0], 1), "iso", round(c["iso_per_h"][0], 2), "cont", c["contained"],
              "disr%", round(100 * c["disr_frac"][0], 3))
    if P:
        for k, c in P["cells"].items():
            print(k, {m: (round(c[m][0], 4) if isinstance(c.get(m), list) and c[m] and not isinstance(c[m][0], str) else c.get(m))
                      for m in ("asr", "asr_transport", "fb", "pq_reauth", "pq_deferred", "slices_fitting")})
