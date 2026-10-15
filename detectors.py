# Detector score tables for the city simulator: attack log-odds of each held-out TON_IoT test flow under
#   global_fedavg / global_ta   (12 edge clients; benign traffic at every edge, attack classes Dirichlet alpha = 0.1)
#   local                       (12 edge-local models trained on their own shard only)
import os, sys, numpy as np, torch
from apq.data import prepare
from apq import fl

OUT = r"E:\A-PQZTO_work\results\detectors_v2"
os.makedirs(OUT, exist_ok=True)
d = prepare("ton", seed=0)
for s in [int(x) for x in sys.argv[1:]] or [1, 2, 3, 4, 5]:
    path = os.path.join(OUT, f"ton_det_s{s}.npz")
    if os.path.exists(path):
        continue
    res, info = {}, {}
    for name, kw in [("global_fedavg", dict(agg="fedavg")), ("global_ta", dict(agg="ta"))]:
        r = fl.run(d, alpha=0.1, seed=s, return_model=True, benign_iid=True, **kw)
        L = fl.predict_logits(r["model"], r["flat"], d["X_te"])
        res[name] = fl.attack_logodds(L)
        info[name] = {k: r[k] for k in ("macro_f1", "bin_f1", "auc", "fpr", "detect_rate")}
        print(s, name, info[name], flush=True)
    r = fl.run(d, alpha=0.1, seed=s, local_only=True, benign_iid=True)
    model = fl.BMLP(d["X_tr"].shape[1], int(d["y_tr"].max() + 1), 12, h=(64, 32), seed=s)
    loc = []
    for k in range(12):
        L = fl.predict_logits(model, r["local_flat"][k], d["X_te"])
        loc.append(fl.attack_logodds(L))
        e = fl.evaluate(L, d["y_te"])
        info[f"local{k}"] = {kk: e[kk] for kk in ("macro_f1", "bin_f1", "auc", "fpr", "detect_rate")}
    res["local"] = np.stack(loc)
    print(s, "local mean detect", np.mean([info[f"local{k}"]["detect_rate"] for k in range(12)]), flush=True)
    np.savez_compressed(path, y_te=d["y_te"], classes=np.array(d["classes"], dtype=object), info=str(info), **res)
