# Aggregation, statistics and figures for the federated experiments (E1 clean, E2 poisoning).
import json, os
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy.stats import wilcoxon

RES = r"E:\A-PQZTO_work\results"
FIG = r"E:\A-PQZTO_work\figures"
os.makedirs(FIG, exist_ok=True)
plt.rcParams.update({"font.family": "Times New Roman", "font.size": 8, "mathtext.fontset": "stix",
                     "axes.spines.top": False, "axes.spines.right": False, "axes.grid": True, "grid.color": "#e6e5e1",
                     "grid.linewidth": 0.6})
AGG_LAB = {"central": "Centralised", "fedavg": "FedAvg", "fedprox": "FedProx", "krum": "Krum", "mkrum": "Multi-Krum",
           "median": "Median", "trmean": "Trimmed mean", "ta": "A-PQZTO trust-aware"}
AGG_COL = {"central": "#000000", "fedavg": "#0072B2", "fedprox": "#56B4E9", "krum": "#CC79A7", "mkrum": "#E69F00",
           "median": "#009E73", "trmean": "#7f7f7f", "ta": "#D55E00"}
ORDER = ["fedavg", "fedprox", "krum", "mkrum", "median", "trmean", "ta"]
DS_LAB = {"ton": "TON_IoT", "cic": "CICIoT2023"}
ALPHA_LAB = {None: "IID", 1.0: "Dirichlet $\\alpha$=1.0", 0.1: "Dirichlet $\\alpha$=0.1"}


def load():
    seen = {}
    for l in open(os.path.join(RES, "fl", "fl_runs_v2.jsonl")):
        r = json.loads(l)
        seen.setdefault(r["key"], r)          # runs are deterministic per key; keep the first copy
    df = pd.DataFrame(list(seen.values()))
    df["alpha"] = df["alpha"].astype(object).where(df["alpha"].notna(), None)
    return df


def boot_ci(x, B=5000, seed=0):
    x = np.asarray(x, float)
    rng = np.random.default_rng(seed)
    m = rng.choice(x, (B, len(x)), replace=True).mean(1)
    return float(x.mean()), float(np.percentile(m, 2.5)), float(np.percentile(m, 97.5))


def cliffs(a, b):
    a, b = np.asarray(a), np.asarray(b)
    return float(((a[:, None] > b[None, :]).sum() - (a[:, None] < b[None, :]).sum()) / (len(a) * len(b)))


def bh(p):
    p = np.asarray(p, float); n = len(p); o = np.argsort(p)
    q = np.empty(n); prev = 1.0
    for r, i in reversed(list(enumerate(o, 1))):
        prev = min(prev, p[i] * n / r); q[i] = prev
    return q


def summarize(df):
    S = {"E1": {}, "E2": {}, "E2n": {}, "E3": {}, "tests": []}
    mets = ["macro_f1", "bin_f1", "auc", "fpr", "detect_rate", "bal_acc"]
    e1 = df[df.exp == "E1"]
    for ds in ("ton", "cic"):
        c = e1[(e1.ds == ds) & (e1["agg"] == "central")]
        S["E1"][f"{ds}|central|None"] = {m: boot_ci(c[m]) for m in mets}
        for a in (None, 1.0, 0.1):
            for g in ORDER:
                r = e1[(e1.ds == ds) & (e1["agg"] == g) & (e1.alpha.map(lambda v: v == a if a is not None else v is None))]
                if len(r):
                    S["E1"][f"{ds}|{g}|{a}"] = {m: boot_ci(r[m]) for m in mets}
                    S["E1"][f"{ds}|{g}|{a}"]["n"] = int(len(r))
    for exp in ("E2", "E2n", "E3"):
        e = df[df.exp == exp]
        for (ds, att, nm, g), r in e.groupby(["ds", "attack", "n_mal", "agg"]):
            S[exp][f"{ds}|{att}|{nm}|{g}"] = {m: boot_ci(r[m]) for m in mets}
            S[exp][f"{ds}|{att}|{nm}|{g}"]["diverged"] = int(r["diverged"].sum())
    # paired tests: trust-aware aggregation versus every other aggregator (same seed, same condition)
    tests = []

    def add(cond, sub, metric):
        ta = sub[sub["agg"] == "ta"].set_index("seed")[metric]
        for g in ORDER[:-1]:
            o = sub[sub["agg"] == g].set_index("seed")[metric]
            idx = ta.index.intersection(o.index)
            if len(idx) < 5:
                continue
            a, b = ta.loc[idx].values, o.loc[idx].values
            d = a - b
            p = 1.0 if np.allclose(d, 0) else float(wilcoxon(a, b, zero_method="zsplit").pvalue)
            tests.append(dict(cond=cond, metric=metric, vs=g, n=int(len(idx)), mean_diff=float(d.mean()),
                              wins=int((d > 0).sum()), p=p, cliff=cliffs(a, b)))
    for ds in ("ton", "cic"):
        for a in (None, 1.0, 0.1):
            sub = e1[(e1.ds == ds) & (e1.alpha.map(lambda v: v == a if a is not None else v is None))]
            add(f"E1|{ds}|{a}", sub, "macro_f1")
        for att in ("lf", "sf"):
            for nm in (1, 2, 3):
                sub = df[(df.exp == "E2") & (df.ds == ds) & (df.attack == att) & (df.n_mal == nm)]
                add(f"E2|{ds}|{att}|{nm}", sub, "detect_rate")
                add(f"E2|{ds}|{att}|{nm}", sub, "macro_f1")
            sub = df[(df.exp == "E2n") & (df.ds == ds) & (df.attack == att)]
            add(f"E2n|{ds}|{att}|2", sub, "detect_rate")
            add(f"E2n|{ds}|{att}|2", sub, "macro_f1")
    # E3: trust-aware rule (no Byzantine bound) versus rules told to expect one attacker while three attack
    for ds in ("ton", "cic"):
        for att in ("lf", "sf"):
            ta = df[(df.exp == "E2") & (df.ds == ds) & (df.attack == att) & (df.n_mal == 3) & (df["agg"] == "ta")]
            ta = ta.set_index("seed")
            for g in ("krum", "mkrum", "trmean"):
                o = df[(df.exp == "E3") & (df.ds == ds) & (df.attack == att) & (df["agg"] == g)].set_index("seed")
                idx = ta.index.intersection(o.index)
                if len(idx) < 5:
                    continue
                for metric in ("detect_rate", "macro_f1"):
                    a, b = ta.loc[idx, metric].values, o.loc[idx, metric].values
                    d = a - b
                    p = 1.0 if np.allclose(d, 0) else float(wilcoxon(a, b, zero_method="zsplit").pvalue)
                    tests.append(dict(cond=f"E3|{ds}|{att}|3", metric=metric, vs=g + "_f1", n=int(len(idx)),
                                      mean_diff=float(d.mean()), wins=int((d > 0).sum()), p=p, cliff=cliffs(a, b)))
    if tests:
        q = bh([t["p"] for t in tests])
        for t, qq in zip(tests, q):
            t["q_bh"] = float(qq)
    S["tests"] = tests
    return S


def fig_clean(S):
    fig, axs = plt.subplots(1, 2, figsize=(6.5, 2.75), sharey=False)
    for ax, ds in zip(axs, ("ton", "cic")):
        x = np.arange(3); w = 0.11
        for j, g in enumerate(ORDER):
            v = [S["E1"].get(f"{ds}|{g}|{a}", {}).get("macro_f1", (np.nan,) * 3) for a in (None, 1.0, 0.1)]
            m = np.array([t[0] for t in v]); lo = m - np.array([t[1] for t in v]); hi = np.array([t[2] for t in v]) - m
            ax.bar(x + (j - 3) * w, m, w * 0.9, color=AGG_COL[g], label=AGG_LAB[g], yerr=[lo, hi], capsize=1.2,
                   error_kw={"lw": 0.6}, zorder=3)
        c = S["E1"][f"{ds}|central|None"]["macro_f1"][0]
        ax.axhline(c, color="black", ls="--", lw=0.9, label="Centralised (pooled data)", zorder=4)
        ax.set_xticks(x); ax.set_xticklabels([ALPHA_LAB[a] for a in (None, 1.0, 0.1)])
        ax.set_title(f"({'ab'[('ton','cic').index(ds)]}) {DS_LAB[ds]}", fontsize=8.6)
        ax.set_ylabel("Macro-F1 (multi-class, test set)")
        lo = min(min(S["E1"][k]["macro_f1"][1] for k in S["E1"] if k.startswith(ds)) - 0.05, c - 0.1)
        ax.set_ylim(max(0, lo), 1.0)
    h, l = axs[0].get_legend_handles_labels()
    fig.legend(h, l, loc="lower center", ncol=4, fontsize=7.8, frameon=False, bbox_to_anchor=(0.5, -0.02),
               columnspacing=1.4, handlelength=1.8)
    fig.tight_layout(rect=(0, 0.13, 1, 1))
    save(fig, "fig6_fl_clean")


def fig_poison(S):
    fig, axs = plt.subplots(2, 2, figsize=(6.5, 4.8), sharex=True)
    for i, ds in enumerate(("ton", "cic")):
        for j, att in enumerate(("lf", "sf")):
            ax = axs[i, j]
            for g in ORDER:
                xs, ms, lo, hi = [0], [S["E1"][f"{ds}|{g}|1.0"]["detect_rate"][0]], [S["E1"][f"{ds}|{g}|1.0"]["detect_rate"][1]], [S["E1"][f"{ds}|{g}|1.0"]["detect_rate"][2]]
                for nm in (1, 2, 3):
                    k = f"{ds}|{att}|{nm}|{g}"
                    if k in S["E2"]:
                        t = S["E2"][k]["detect_rate"]; xs.append(nm); ms.append(t[0]); lo.append(t[1]); hi.append(t[2])
                ax.plot(xs, ms, marker="o", ms=3.5, lw=2.0 if g == "ta" else 1.1, color=AGG_COL[g], label=AGG_LAB[g],
                        zorder=5 if g == "ta" else 3)
                ax.fill_between(xs, lo, hi, color=AGG_COL[g], alpha=0.12, lw=0)
            ax.set_ylim(-0.03, 1.03)
            ax.set_xticks([0, 1, 2, 3]); ax.set_xticklabels(["0", "1 (8%)", "2 (17%)", "3 (25%)"])
            name = "targeted label flipping" if att == "lf" else "sign-flipped, scaled updates"
            ax.set_title(f"({'abcd'[2 * i + j]}) {DS_LAB[ds]}: {name}", fontsize=8.4)
            if j == 0:
                ax.set_ylabel("Attack detection rate")
            if i == 1:
                ax.set_xlabel("Malicious edge clients (of 12), Dirichlet $\\alpha$=1.0")
    h, l = axs[0, 0].get_legend_handles_labels()
    fig.legend(h, l, loc="lower center", ncol=4, fontsize=7.8, frameon=False, bbox_to_anchor=(0.5, 0.0),
               columnspacing=1.4, handlelength=1.8)
    fig.tight_layout(rect=(0, 0.075, 1, 1))
    save(fig, "fig7_fl_poisoning")


def save(fig, name):
    for ext, kw in ((".png", {}), (".tif", {"pil_kwargs": {"compression": "tiff_lzw"}})):
        fig.savefig(os.path.join(FIG, name + ext), dpi=400, bbox_inches="tight", facecolor="white", **kw)
    plt.close(fig)


if __name__ == "__main__":
    df = load()
    print(df.groupby(["exp", "ds"]).size())
    S = summarize(df)
    S["n_runs"] = int(len(df))
    json.dump(S, open(os.path.join(RES, "fl_summary.json"), "w"), indent=1, default=str)
    fig_clean(S)
    if len(S["E2"]):
        fig_poison(S)
    print("ok")
