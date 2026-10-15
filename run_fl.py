# E1 (clean) and E2 (poisoning) federated experiments; resumable, parallel, one JSON line per run.
import json, os, sys, itertools, multiprocessing as mp
RES = r"E:\A-PQZTO_work\results\fl"
SEEDS = list(range(1, 11))
AGGS = ["fedavg", "fedprox", "krum", "mkrum", "median", "trmean", "ta"]

def tasks():
    T = []
    for ds in ("ton", "cic"):
        for s in SEEDS:
            T.append(dict(exp="E1", ds=ds, centralized=True, agg="central", alpha=None, seed=s))
        for alpha, agg, s in itertools.product([None, 1.0, 0.1], AGGS, SEEDS):
            T.append(dict(exp="E1", ds=ds, agg=agg, alpha=alpha, seed=s))
        for att, nm, agg, s in itertools.product(["lf", "sf"], [1, 2, 3], AGGS, SEEDS):
            T.append(dict(exp="E2", ds=ds, agg=agg, alpha=1.0, n_mal=nm, attack=att, seed=s))
        for att, agg, s in itertools.product(["lf", "sf"], AGGS, SEEDS):
            T.append(dict(exp="E2n", ds=ds, agg=agg, alpha=0.1, n_mal=2, attack=att, seed=s))
        # E3: Byzantine bound misspecified (three attackers, rules told to expect one)
        for att, agg, s in itertools.product(["lf", "sf"], ["krum", "mkrum", "trmean"], SEEDS):
            T.append(dict(exp="E3", ds=ds, agg=agg, alpha=1.0, n_mal=3, attack=att, f_assumed=1, seed=s))
    return T

def key(t):
    k = "|".join(f"{k}={t.get(k)}" for k in ("exp", "ds", "agg", "alpha", "n_mal", "attack", "seed"))
    return k + (f"|f={t['f_assumed']}" if "f_assumed" in t else "")

_D = {}
def work(t):
    # every seed uses its own stratified split of the deduplicated data (split variance enters the CIs)
    from apq.data import prepare
    from apq import fl
    k = (t["ds"], t["seed"])
    if k not in _D:
        _D.clear()
        _D[k] = prepare(t["ds"], seed=t["seed"])
    kw = {kk: v for kk, v in t.items() if kk not in ("exp", "ds")}
    if kw.get("centralized"):
        kw.pop("agg")
    r = fl.run(_D[k], **kw)
    r.update(exp=t["exp"], ds=t["ds"], key=key(t))
    return r

if __name__ == "__main__":
    os.makedirs(RES, exist_ok=True)
    out = os.path.join(RES, "fl_runs_v2.jsonl")
    done = set()
    if os.path.exists(out):
        for line in open(out):
            done.add(json.loads(line)["key"])
    # group tasks by (dataset, seed) so that each worker reuses its prepared split
    todo = sorted([t for t in tasks() if key(t) not in done], key=lambda t: (t["ds"], t["seed"]))
    print("total", len(tasks()), "todo", len(todo), flush=True)
    nw = int(sys.argv[1]) if len(sys.argv) > 1 else 6
    with mp.Pool(nw) as pool, open(out, "a") as f:
        for i, r in enumerate(pool.imap_unordered(work, todo, chunksize=8)):
            f.write(json.dumps(r) + "\n"); f.flush()
            if i % 25 == 0:
                print(i, r["key"], round(r["macro_f1"], 3), flush=True)
    print("done", flush=True)
