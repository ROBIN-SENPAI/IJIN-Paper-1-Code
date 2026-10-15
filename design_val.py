# Design selection on VALIDATION episodes only (seeds 101-108, validation evidence pool): each trust-score variant is
# calibrated on benign validation episodes under the joint 0.5% budget, then compared on validation attack episodes.
import json, os, sys, itertools, multiprocessing as mp
import numpy as np
import run_city as R
from apq import city as C

VARIANTS = {
    "V0_additive_twinrisk": dict(veto=False, twin_in_trust=True),
    "V1_veto_twinrisk": dict(veto=True, twin_in_trust=True),
    "V2_veto_notwinrisk": dict(veto=True, twin_in_trust=False),
    "V3_additive_notwinrisk": dict(veto=False, twin_in_trust=False),
}
BASE = dict(detector="global_ta", trust=True, twin=True, pqc="adaptive", behaviour=True)
OUT = r"E:\A-PQZTO_work\results\city\design_val.jsonl"
VAL_ATTACK_SEEDS = list(range(101, 109))


def register():
    for k, v in VARIANTS.items():
        C.POLICIES[k] = dict(BASE, **v)


def ep(task):
    register()
    t = dict(task); t["phase"] = "calib"            # validation evidence pool
    m = R.episode(t)
    return m


def run(tasks, nw):
    done = set()
    if os.path.exists(OUT):
        done = {json.loads(l)["key"] for l in open(OUT)}
    todo = [t for t in tasks if t["key"] not in done]
    with mp.Pool(nw, initializer=register) as pool, open(OUT, "a") as f:
        for r in pool.imap_unordered(ep, todo, chunksize=1):
            f.write(json.dumps(r) + "\n"); f.flush()


def rows():
    out = {}
    for l in open(OUT):
        r = json.loads(l); out.setdefault(r["key"], r)
    return list(out.values())


if __name__ == "__main__":
    register()
    nw = int(sys.argv[1]) if len(sys.argv) > 1 else 6
    # 1) calibrate (coarse then fine) on benign validation seeds
    coarse = R.COARSE
    tasks = [dict(policy=p, theta=float(th), seed=s, scen="benign", key=f"dv|cal|{p}|{th}|{s}")
             for p in VARIANTS for th in coarse for s in R.VAL_SEEDS]
    run(tasks, nw)
    tab = {}
    for r in rows():
        if r["key"].startswith("dv|cal|"):
            tab.setdefault(r["policy"], {}).setdefault(round(r["theta"], 2), []).append((r["fb_rate"], r["disruption_h"] / r["wsum"]))
    def feas(p):
        f = [th for th, v in tab[p].items() if np.mean([a for a, _ in v]) <= R.BUDGET and np.mean([b for _, b in v]) <= R.BUDGET]
        return max(f) if f else min(tab[p])
    fine = [dict(policy=p, theta=round(feas(p) + 0.01 * i, 2), seed=s, scen="benign", key=f"dv|cal|{p}|{round(feas(p) + 0.01 * i, 2)}|{s}")
            for p in VARIANTS for i in range(1, 5) for s in R.VAL_SEEDS]
    run(fine, nw)
    tab = {}
    for r in rows():
        if r["key"].startswith("dv|cal|"):
            tab.setdefault(r["policy"], {}).setdefault(round(r["theta"], 2), []).append((r["fb_rate"], r["disruption_h"] / r["wsum"]))
    theta = {p: feas(p) for p in VARIANTS}
    # the reported selection run read FL-only IDS's operating point from theta_v2.json (0.04, the same value as in
    # theta_v3.json); a fresh run of the released pipeline only has the current file
    p2 = os.path.join(R.RES, "theta_v2.json")
    th_main = json.load(open(p2 if os.path.exists(p2) else os.path.join(R.RES, f"theta_{R.VER}.json")))
    theta["fl_ids"] = th_main["fl_ids"]
    theta["none"] = 0.0
    # 2) compare on validation attack episodes
    ev = [dict(policy=p, theta=theta[p], seed=s, scen=sc, key=f"dv|ev|{p}|{theta[p]}|{s}|{sc}")
          for p in list(VARIANTS) + ["fl_ids", "none"] for s in VAL_ATTACK_SEEDS for sc in ["worm", "evasion", "injection", "ddos"]]
    for t in ev:
        if t["policy"] == "none":
            t["theta"] = 0.0
    run(ev, nw)
    res = {}
    rr = [r for r in rows() if r["key"].startswith("dv|ev|")]
    none = {(r["seed"], r["scen"]): r for r in rr if r["policy"] == "none"}
    for p in list(VARIANTS) + ["fl_ids"]:
        d = {}
        for sc in ["worm", "evasion", "injection", "ddos"]:
            v = []
            for r in rr:
                if r["policy"] == p and r["scen"] == sc:
                    n = none[(r["seed"], sc)]
                    v.append(1 - r["ever"] / max(n["ever"], 1) if sc == "worm" else r["attack_steps_eff"] / max(n["attack_steps_eff"], 1))
            d[sc] = float(np.mean(v)) if v else None
        d["theta"] = theta[p]
        res[p] = d
    json.dump(res, open(os.path.join(R.RES, "design_val_summary.json"), "w"), indent=1)
    print(json.dumps(res, indent=1))
