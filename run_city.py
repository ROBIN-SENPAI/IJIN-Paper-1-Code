# City-scale orchestration experiments, version 2.
#   calib : per-policy operating point theta, chosen on VALIDATION episodes (benign, seeds 101-104, validation evidence
#           pool) as the largest theta that keeps BOTH the false-blocking rate and the criticality-weighted service
#           disruption (quarantine, blocking, isolation, rate limiting) at or below 0.5%; coarse grid (0.05) then a
#           0.01 refinement
#   main  : 6 scenarios x all policies x 20 test seeds (test evidence pool)
#   trace : worm trajectories; twin : twin graph / propagation-rate error; scal : decision time versus city size
import json, os, sys, time, itertools, multiprocessing as mp
import numpy as np

VER = "v3"
RES = r"E:\A-PQZTO_work\results\city"
DET = r"E:\A-PQZTO_work\results\detectors_v2"
BUDGET = 0.005
COARSE = [round(x, 2) for x in np.arange(-0.45, 0.3001, 0.05)]
VAL_SEEDS = [101, 102, 103, 104]
TEST_SEEDS = list(range(21, 41))     # fresh seeds: no design decision used them
SCENARIOS = ["benign", "worm", "ddos", "evasion", "injection", "impostor"]

_EV, _CITY = {}, {}


def evidence(det_seed, part):
    from apq import city as C
    k = (det_seed, part)
    if k not in _EV:
        z = np.load(os.path.join(DET, f"ton_det_s{det_seed}.npz"), allow_pickle=True)
        scores = {k2: z[k2] for k2 in z.files if k2.startswith("global") or k2 == "local"}
        _EV[k] = C.Evidence(scores, z["y_te"], list(z["classes"]), part=part)
    return _EV[k]


def city(seed, twin_err=0.1, beta_err=0.0, scale=1.0):
    from apq import city as C
    k = (seed, twin_err, beta_err, scale)
    if k not in _CITY:
        if len(_CITY) > 8:
            _CITY.clear()
        _CITY[k] = C.City(seed, twin_err=twin_err, beta_err=beta_err, scale=scale)
    return _CITY[k]


def det_seed(s):
    return (s - 1) % 5 + 1


def episode(task):
    from apq import city as C
    t0 = time.time()
    c = city(task["seed"], task.get("twin_err", 0.1), task.get("beta_err", 0.0), task.get("scale", 1.0))
    part = "val" if task["phase"] == "calib" else "test"
    m = C.run_episode(c, evidence(det_seed(task["seed"]), part), task["scen"], task["policy"], seed=task["seed"] * 7919,
                      theta=task.get("theta", 0.0), record=task.get("record", False), pq_ms=task.get("pq_ms", 2.0),
                      dev_factor=task.get("dev_factor", 1.0))
    m.update(task)
    m["wall_s"] = time.time() - t0
    m["n_dev"] = c.N
    m["twin_missing"], m["twin_spurious"] = c.n_missing, c.n_spurious
    return m


def run_pool(tasks, out, nw):
    done = set()
    if os.path.exists(out):
        for line in open(out):
            done.add(json.loads(line)["key"])
    todo = [t for t in tasks if t["key"] not in done]
    print(out, "todo", len(todo), flush=True)
    if not todo:
        return
    with mp.Pool(nw) as pool, open(out, "a") as f:
        for i, r in enumerate(pool.imap_unordered(episode, todo, chunksize=1)):
            f.write(json.dumps(r) + "\n"); f.flush()
            if i % 50 == 0:
                print(i, r["key"], flush=True)


def key(*parts):
    return VER + "|" + "|".join(str(p) for p in parts)


def calib_tasks(policies, thetas):
    return [dict(phase="calib", policy=p, theta=float(th), seed=s, scen="benign", key=key("calib", p, th, s))
            for p in policies for th in thetas[p] for s in VAL_SEEDS]


def load(path):
    rows = {}
    for l in open(path):
        r = json.loads(l)
        rows.setdefault(r["key"], r)
    return list(rows.values())


def feasible_table(rows):
    """policy -> theta -> (fb, disruption fraction, feasible)."""
    out = {}
    for r in rows:
        out.setdefault(r["policy"], {}).setdefault(round(r["theta"], 2), []).append(
            (r["fb_rate"], r["disruption_h"] / r["wsum"]))
    tab = {}
    for p, d in out.items():
        tab[p] = {}
        for th, v in d.items():
            fb, dz = float(np.mean([a for a, _ in v])), float(np.mean([b for _, b in v]))
            tab[p][th] = (fb, dz, fb <= BUDGET and dz <= BUDGET)
    return tab


if __name__ == "__main__":
    os.makedirs(RES, exist_ok=True)
    phase = sys.argv[1]
    nw = int(sys.argv[2]) if len(sys.argv) > 2 else 6
    from apq.city import POLICIES
    pols = [p for p in POLICIES if p != "none"]
    cpath = os.path.join(RES, f"calib_{VER}.jsonl")
    if phase == "calib":
        run_pool(calib_tasks(pols, {p: COARSE for p in pols}), cpath, nw)
        tab = feasible_table(load(cpath))
        fine = {}
        for p in pols:
            feas = [th for th, v in tab[p].items() if v[2] and th in COARSE]
            base = max(feas) if feas else min(COARSE)
            fine[p] = [round(base + 0.01 * i, 2) for i in range(1, 5)]
        run_pool(calib_tasks(pols, fine), cpath, nw)
        tab = feasible_table(load(cpath))
        theta, report = {}, {}
        for p in pols:
            feas = [th for th, v in tab[p].items() if v[2]]
            theta[p] = max(feas) if feas else min(tab[p])
            report[p] = {"theta": theta[p], "fb": tab[p][theta[p]][0], "disruption_frac": tab[p][theta[p]][1],
                         "feasible": bool(feas)}
        json.dump(theta, open(os.path.join(RES, f"theta_{VER}.json"), "w"), indent=1)
        json.dump({p: {str(k): v for k, v in sorted(tab[p].items())} for p in tab},
                  open(os.path.join(RES, f"calib_table_{VER}.json"), "w"), indent=1)
        print(json.dumps(report, indent=1))
    else:
        th = json.load(open(os.path.join(RES, f"theta_{VER}.json")))
        if phase == "main":
            T = [dict(phase="main", policy=p, theta=th.get(p, 0.0), seed=s, scen=sc,
                      key=key("main", p, th.get(p, 0.0), s, sc)) for p, s, sc in
                 itertools.product(POLICIES, TEST_SEEDS, SCENARIOS)]
            run_pool(T, os.path.join(RES, f"main_{VER}.jsonl"), nw)
        elif phase == "trace":
            T = [dict(phase="trace", policy=p, theta=th.get(p, 0.0), seed=s, scen="worm", record=True,
                      key=key("trace", p, th.get(p, 0.0), s)) for p, s in itertools.product(
                          ["none", "static_zta", "fl_ids", "dt_ids_nofl", "apqzto", "apqzto_nodt", "apqzto_nofl",
                           "apqzto_twinrisk"], range(21, 31))]
            run_pool(T, os.path.join(RES, f"trace_{VER}.jsonl"), nw)
        elif phase == "twin":
            T = [dict(phase="twin", policy="apqzto", theta=th["apqzto"], seed=s, scen="worm", twin_err=te,
                      beta_err=be, key=key("twin", te, be, th["apqzto"], s))
                 for te, be, s in itertools.product([0.0, 0.1, 0.3, 0.5], [-0.5, 0.0, 1.0], TEST_SEEDS)]
            T += [dict(phase="twin", policy="none", theta=0.0, seed=s, scen="worm", key=key("twin_none", s))
                  for s in TEST_SEEDS]
            run_pool(T, os.path.join(RES, f"twin_{VER}.jsonl"), nw)
        elif phase == "stress":
            # worm_fast: beta = 0.10 against the twin's prior of 0.03. Same calibrated thetas, fresh test seeds.
            T = [dict(phase="stress", policy=p, theta=th.get(p, 0.0), seed=s, scen="worm_fast",
                      key=key("stress", p, th.get(p, 0.0), s)) for p, s in itertools.product(
                          ["none", "static_zta", "fl_ids", "dt_ids_nofl", "apqzto", "apqzto_nodt", "apqzto_notrust",
                           "apqzto_noveto"], TEST_SEEDS)]
            T += [dict(phase="stress_twin", policy="apqzto", theta=th["apqzto"], seed=s, scen="worm_fast", twin_err=te,
                       beta_err=be, key=key("stress_twin", te, be, th["apqzto"], s))
                  for te, be, s in itertools.product([0.0, 0.1, 0.3, 0.5], [-0.5, 0.0, 1.0, 7.0 / 3.0], TEST_SEEDS)]
            run_pool(T, os.path.join(RES, f"stress_{VER}.jsonl"), nw)
        elif phase == "pqcost":
            # sensitivity of adaptive PQ re-authentication to the handshake cost on slower devices: pq_ms = 2 ms (close
            # to the measured hybrid handshake) times a device slowdown factor; re-authentication is deferred when the
            # result exceeds the slice latency budget
            T = [dict(phase="pqcost", policy="apqzto", theta=th["apqzto"], seed=s, scen=sc, dev_factor=df,
                      key=key("pqcost", df, sc, s)) for df, sc, s in itertools.product(
                          [1.0, 3.0, 10.0, 30.0, 60.0], ["impostor", "evasion", "benign"], TEST_SEEDS)]
            run_pool(T, os.path.join(RES, f"pqcost_{VER}.jsonl"), nw)
        elif phase == "scal":
            T = [dict(phase="scal", policy=p, theta=th.get(p, 0.0), seed=s, scen="worm", scale=sc,
                      key=key("scal", p, sc, s)) for p, sc, s in itertools.product(
                          ["apqzto", "apqzto_nodt", "fl_ids"], [1.0, 2.0, 4.0, 8.0], [21, 22, 23])]
            run_pool(T, os.path.join(RES, f"scal_{VER}.jsonl"), 1)   # one worker: clean timing
