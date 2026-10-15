# Prepare the deduplicated data once and one stratified split per seed (0 = audit/reference split).
from apq.data import prepare
import sys
for ds in ("ton", "edge", "cic"):
    for s in ([0] if ds == "edge" else range(0, 11)):
        d = prepare(ds, seed=s)
        print(ds, s, d["X_tr"].shape, flush=True)
