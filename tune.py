# Hyper-parameter selection on the VALIDATION split (seeds 100-102), never on the test split.
import itertools, json, time, numpy as np
from apq.data import prepare
from apq import fl
d = prepare("ton")
rows = []
for lr, alpha in itertools.product([0.05, 0.1], [1.0, 0.1]):
    m = [fl.run(d, agg="fedavg", alpha=alpha, lr=lr, seed=s, split="va")["macro_f1"] for s in (100, 101, 102)]
    rows.append(("fedavg", lr, alpha, None, float(np.mean(m)))); print(rows[-1], flush=True)
for cut, alpha, att in itertools.product([0.0, 0.25, 0.5], [1.0, 0.1], [None, "sf"]):
    m = [fl.run(d, agg="ta", alpha=alpha, ta_cut=cut, seed=s, split="va", n_mal=2 if att else 0, attack=att)["macro_f1"]
         for s in (100, 101, 102)]
    rows.append(("ta", cut, alpha, att, float(np.mean(m)))); print(rows[-1], flush=True)
json.dump(rows, open(r"E:\A-PQZTO_work\results_tune.json", "w"), indent=1)
