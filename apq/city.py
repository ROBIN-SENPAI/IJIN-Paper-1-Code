# -*- coding: utf-8 -*-
"""City-scale zero-trust orchestration simulator (1,500 IoT devices, 12 edge nodes, four 6G slices), version 2.

The ground-truth network is a contact graph on which compromises spread and attacks are executed. Every device emits
flow evidence whose threat score is drawn from REAL detector outputs on held-out TON_IoT flows of the matching class
(global federated model or the edge's own local model). The behavioural profile is a modelled traffic statistic (not
drawn from data); an ablation removes it. A policy observes only this evidence, authentication state and (optionally)
the digital twin, and decides per device: allow, restrict, PQ re-authenticate, quarantine or block; the twin can also
isolate an edge cluster after validating the action by Monte Carlo roll-outs on its own, imperfect copy of the graph.

Randomness is split into three independent streams so that runs of different policies with the same seed share the
environment (initial compromises, activity, emissions, spread draws, flow classes): common random numbers.
"""
import time

import numpy as np
import scipy.sparse as sp

DOMAINS = ["transport", "energy", "health", "safety"]
N_DEV = {"transport": 450, "energy": 375, "health": 300, "safety": 375}
SENS = {"transport": 0.6, "energy": 0.8, "health": 1.0, "safety": 0.9}
SENSITIVE = {"energy", "health", "safety"}            # long-lived confidentiality -> PQ key establishment
EDGES_PER_DOMAIN = 3
# per-slice latency budget (ms) that a security handshake may add to a session; PQ re-authentication is only
# scheduled when the handshake latency (measured, times a device slowdown factor) fits the budget
SLICE_BUDGET_MS = {"transport": 10.0, "energy": 50.0, "health": 100.0, "safety": 20.0}
STEP_S = 10                                            # one decision interval = 10 s
T_STEPS = 360                                          # one-hour episode
T0 = 60                                                # attack onset
BETA_PRIOR = 0.03                                      # twin's prior per-contact propagation probability
RESTRICT = 0.3                                         # rate limiting keeps 30% of a device's activity

SCEN = {
    "worm": dict(classes=["scanning", "backdoor", "ransomware"], act=0.5, mu=1.5, beta=0.03, n0=3, spread=True),
    # stress test: a worm that spreads about three times faster than the twin's prior assumes
    "worm_fast": dict(classes=["scanning", "backdoor", "ransomware"], act=0.5, mu=1.5, beta=0.10, n0=3, spread=True),
    "ddos": dict(classes=["ddos", "dos"], act=0.8, mu=3.0, n0=30, spread=False),
    "evasion": dict(classes=["password", "injection", "xss", "backdoor"], act=0.15, mu=0.8, n0=8, spread=False,
                    domains=["health", "energy"]),
    "injection": dict(classes=["injection"], act=0.4, mu=1.0, n0=15, spread=False, domains=["energy"]),
    "impostor": dict(classes=["mitm", "password"], act=0.3, mu=0.5, n0=12, spread=False, impostor=True),
    "benign": dict(classes=[], act=0.0, mu=0.0, n0=0, spread=False),
}

# detector: 'global_fedavg' | 'global_ta' | 'local'; trust: Eq. (1) (else rule: score above threshold in `consec`
# consecutive observations); twin: propagation risk and validated isolation; pqc: 'none' | 'fixed' | 'adaptive';
# behaviour: the policy uses the behavioural profile (trust policies only)
POLICIES = {
    "none":           dict(respond=False),
    "static_zta":     dict(detector="local", trust=False, twin=False, pqc="none", consec=3),
    "fl_ids":         dict(detector="global_fedavg", trust=False, twin=False, pqc="none", consec=2),
    "zta_fixedpqc":   dict(detector="local", trust=False, twin=False, pqc="fixed", consec=3),
    "dt_ids_nofl":    dict(detector="local", trust=False, twin=True, pqc="none", consec=2),
    # A-PQZTO as selected on validation episodes: zero-trust veto, twin used to validate cluster isolation
    "apqzto":         dict(detector="global_ta", trust=True, twin=True, pqc="adaptive", behaviour=True, veto=True,
                           twin_in_trust=False),
    "apqzto_nopqc":   dict(detector="global_ta", trust=True, twin=True, pqc="none", behaviour=True, veto=True,
                           twin_in_trust=False),
    "apqzto_nodt":    dict(detector="global_ta", trust=True, twin=False, pqc="adaptive", behaviour=True, veto=True,
                           twin_in_trust=False),
    "apqzto_nofl":    dict(detector="local", trust=True, twin=True, pqc="adaptive", behaviour=True, veto=True,
                           twin_in_trust=False),
    "apqzto_notrust": dict(detector="global_ta", trust=False, twin=True, pqc="adaptive", consec=2),
    "apqzto_nobeh":   dict(detector="global_ta", trust=True, twin=True, pqc="adaptive", behaviour=False, veto=True,
                           twin_in_trust=False),
    # design alternatives evaluated as ablations
    "apqzto_noveto":  dict(detector="global_ta", trust=True, twin=True, pqc="adaptive", behaviour=True, veto=False,
                           twin_in_trust=False),
    "apqzto_twinrisk": dict(detector="global_ta", trust=True, twin=True, pqc="adaptive", behaviour=True, veto=False,
                            twin_in_trust=True),
}


# ------------------------------------------------------------------------------------------------ city
class City:
    def __init__(self, seed, twin_err=0.1, beta_err=0.0, scale=1.0):
        rng = np.random.default_rng(10_000 + seed)
        self.dom, self.edge = [], []
        e = 0
        for d in DOMAINS:
            n = int(round(N_DEV[d] * scale))
            self.dom += [d] * n
            self.edge += list(e + rng.permutation(np.arange(n) % EDGES_PER_DOMAIN))
            e += EDGES_PER_DOMAIN
        self.dom = np.array(self.dom)
        self.edge = np.array(self.edge)
        self.N = len(self.dom)
        self.n_edges = e
        self.sens = np.array([SENS[d] for d in self.dom])
        crit = 0.2 + 0.8 * rng.beta(2, 3, self.N)
        crit[rng.random(self.N) < 0.1] = 1.0
        self.crit = crit
        self.w = self.sens * self.crit
        self.wsum = float(self.w.sum())
        self.budget = np.array([SLICE_BUDGET_MS[d] for d in self.dom])
        rows, cols = [], []
        for k in range(self.n_edges):                      # small world inside each edge cluster
            ii = np.flatnonzero(self.edge == k)
            n, kk = len(ii), 6
            for a in range(n):
                for j in range(1, kk // 2 + 1):
                    b = (a + j) % n
                    if rng.random() < 0.1:
                        b = rng.integers(n)
                    if b != a:
                        rows.append(ii[a]); cols.append(ii[b])
        for d in DOMAINS:                                  # gateway links between clusters of a domain
            ii = np.flatnonzero(self.dom == d)
            for _ in range(int(0.02 * len(ii))):
                a, b = rng.choice(ii, 2, replace=False)
                if self.edge[a] != self.edge[b]:
                    rows.append(a); cols.append(b)
        for k in range(self.n_edges):                      # shared services across domains
            ii = np.flatnonzero(self.edge == k)
            jj = np.flatnonzero(self.dom != self.dom[ii[0]])
            for _ in range(3):
                rows.append(rng.choice(ii)); cols.append(rng.choice(jj))
        A = sp.coo_matrix((np.ones(len(rows)), (rows, cols)), shape=(self.N, self.N)).tocsr()
        A = ((A + A.T) > 0).astype(np.float64)
        A.setdiag(0); A.eliminate_zeros()
        self.A = A.tocsr()
        r, c = self.A.nonzero()
        same = self.edge[r] == self.edge[c]
        self.A_in = sp.csr_matrix((np.ones(same.sum()), (r[same], c[same])), shape=A.shape)
        self.A_out = sp.csr_matrix((np.ones((~same).sum()), (r[~same], c[~same])), shape=A.shape)
        # twin copy: a share twin_err of the true links is missing and the same number of spurious links (between
        # devices of the same domain, where unknown service dependencies are plausible) is added
        r, c = sp.triu(self.A).nonzero()
        keep = rng.random(len(r)) >= twin_err
        n_fake = int((~keep).sum())
        dom_idx = self.edge // EDGES_PER_DOMAIN
        fr, fc = [], []
        existing = set(zip(r.tolist(), c.tolist()))
        while len(fr) < n_fake:
            a = int(rng.integers(self.N))
            same_dom = np.flatnonzero(dom_idx == dom_idx[a])
            b = int(rng.choice(same_dom))
            if a != b and (min(a, b), max(a, b)) not in existing:
                fr.append(a); fc.append(b)
        rr = np.concatenate([r[keep], np.array(fr, dtype=int)]); cc = np.concatenate([c[keep], np.array(fc, dtype=int)])
        T = sp.coo_matrix((np.ones(len(rr)), (rr, cc)), shape=A.shape).tocsr()
        T = ((T + T.T) > 0).astype(np.float64)
        T.setdiag(0); T.eliminate_zeros()
        self.Ahat = T.tocsr()
        self.n_missing, self.n_spurious = int((~keep).sum()), len(fr)
        self.beta_hat = BETA_PRIOR * (1 + beta_err)


# ------------------------------------------------------------------------------------------------ evidence
class Evidence:
    """Pools of real detector scores (attack log-odds) on held-out TON_IoT flows, per detector and class.

    Every detector is calibrated on benign commissioning traffic, separately for every edge node: its score is mapped
    to a tail score z = clip((F_ref(s) - q0) / (1 - q0), 0, 1), where F_ref is the empirical CDF (mid-rank for ties)
    over benign reference flows. Held-out flows at even positions are the reference; odd positions are split into a
    validation pool (used to calibrate the operating points) and a disjoint test pool (used in the reported runs)."""

    def __init__(self, scores, y_te, classes, q0=0.95, part="test"):
        self.cidx = {c: i for i, c in enumerate(classes)}
        n = len(y_te)
        pos = np.arange(n)
        ref = pos % 2 == 0
        ben_ref = ref & (y_te == 0)
        odd_half = (pos // 2) % 2
        pool_mask = (~ref) & (odd_half == (0 if part == "val" else 1))

        def tail(raw):
            r = np.sort(raw[ben_ref])
            F = 0.5 * (np.searchsorted(r, raw, side="left") + np.searchsorted(r, raw, side="right")) / len(r)
            return np.clip((F - q0) / (1 - q0), 0, 1)

        self.pools = {}
        for name, s in scores.items():
            if name == "local":
                self.pools["local"] = [{c: tail(s[k])[pool_mask & (y_te == i)] for c, i in self.cidx.items()}
                                       for k in range(len(s))]
            else:
                z = tail(s)
                self.pools[name] = {c: z[pool_mask & (y_te == i)] for c, i in self.cidx.items()}

    def draw(self, rng, det, cls, edge):
        out = np.empty(len(cls))
        for c in np.unique(cls):
            msk = cls == c
            if det == "local":
                for k in np.unique(edge[msk]):
                    mm = msk & (edge == k)
                    pool = self.pools["local"][k][c]
                    out[mm] = pool[rng.integers(0, len(pool), mm.sum())]
            else:
                pool = self.pools[det][c]
                out[msk] = pool[rng.integers(0, len(pool), msk.sum())]
        return out


# ------------------------------------------------------------------------------------------------ episode
def run_episode(city, ev, scen, policy, seed, theta=0.0, pq_ms=2.0, dev_factor=1.0, horizon=12, mc=8, record=False):
    env = np.random.default_rng(seed)                 # environment: shared by all policies (common random numbers)
    obs = np.random.default_rng(seed + 1_000_003)     # observation noise and detector draws
    rtw = np.random.default_rng(seed + 2_000_003)     # twin roll-outs
    S = SCEN[scen]
    P = POLICIES[policy]
    N = city.N
    respond = P.get("respond", True)
    use_beh = P.get("behaviour", False)
    classes = S["classes"]
    # ---- attack set
    comp = np.zeros(N, bool)
    impostor = np.zeros(N, bool)
    comp_at = np.array([], int)
    if S["n0"]:
        pool = np.arange(N)
        if "domains" in S:
            pool = np.flatnonzero(np.isin(city.dom, S["domains"]))
        if S.get("spread"):
            pool = np.flatnonzero(city.edge == env.integers(city.n_edges))
        if scen == "ddos":
            pool = np.flatnonzero(np.isin(city.edge, env.choice(city.n_edges, 2, replace=False)))
        chosen = env.choice(pool, S["n0"], replace=False)
        if S.get("impostor"):
            impostor[chosen] = True
        else:
            comp_at = chosen
    rekey_phase = env.integers(0, 180, N)
    ever = np.zeros(N, bool)
    # ---- policy state
    quar = np.zeros(N, bool); q_until = np.zeros(N, int)
    blk = np.zeros(N, bool); b_until = np.zeros(N, int)
    restr = np.zeros(N, bool)
    iso = np.zeros(city.n_edges, bool); iso_until = np.zeros(city.n_edges, int)
    last_eval = np.full(city.n_edges, -99)
    ema_p = np.zeros(N); ema_u = np.zeros(N); rep = np.ones(N)
    consec = np.zeros(N, int)
    pqc_mode = P.get("pqc", "none")
    sens_dev = np.isin(city.dom, list(SENSITIVE))
    auth = np.where(pqc_mode == "fixed", 1.0, np.where(sens_dev & (pqc_mode == "adaptive"), 1.0, 0.85))
    pq_identity = auth >= 1.0
    det = P.get("detector", "global_ta")
    beta = S.get("beta", 0.0)
    m = dict(benign_steps=0, fb_steps=0, disruption=0.0, attack_steps_eff=0, impostor_access=0,
             impostor_access_transport=0, decision_s=0.0, isolations=0, first_contain=None, pq_deferred=0,
             n_sessions=0, n_classical=0, n_sens_sessions=0, n_sens_classical=0, n_pq_hs=0, n_pq_reauth=0)
    tau_allow, tau_restrict, tau_quar, tau_block = 0.75 + theta, 0.55 + theta, 0.40 + theta, 0.20 + theta
    thr_shift = 0.10 * (city.sens - 0.8)              # stricter thresholds in more sensitive slices
    dthr = 0.5 - theta                                # detector threshold for rule-based policies
    fits = pq_ms * dev_factor <= city.budget
    trace = []
    for t in range(T_STEPS):
        if t == T0 and len(comp_at):
            comp[comp_at] = True
        removed = quar | blk
        imp_now = impostor & (t >= T0)
        # environment draws (fixed sizes, independent of the policy)
        u_act, u_spread, u_emit = env.random(N), env.random(N), env.random(N)
        cls_idx = env.integers(max(len(classes), 1), size=N)
        # ---- sessions: onboarding, re-keying every 30 min, impostor connection at the attack onset
        new_sess = (t == 0) | ((t % 180) == rekey_phase) | (imp_now & (t == T0))
        idx = np.flatnonzero(new_sess & ~removed)
        if len(idx):
            sens = sens_dev[idx]
            pq = np.ones(len(idx), bool) if pqc_mode == "fixed" else (sens if pqc_mode == "adaptive" else
                                                                       np.zeros(len(idx), bool))
            m["n_sessions"] += len(idx); m["n_classical"] += int((~pq).sum())
            m["n_sens_sessions"] += int(sens.sum()); m["n_sens_classical"] += int((sens & ~pq).sum())
            m["n_pq_hs"] += int(pq.sum())
            if t == T0:
                ii = idx[imp_now[idx]]               # the forged classical credential replaces the device's session
                auth[ii] = 0.85
                pq_identity[ii] = False
            if pqc_mode in ("fixed", "adaptive"):
                auth[idx[pq & imp_now[idx]]] = 0.0   # stated assumption: a forged credential fails ML-DSA verification
                pq_identity[idx[pq & ~imp_now[idx]]] = True
        # ---- attack activity (rate limiting keeps RESTRICT of the activity) and spread
        act_scale = np.where(restr, RESTRICT, 1.0)
        active_att = comp & ~removed & (u_act < S["act"] * act_scale)
        active_imp = imp_now & ~removed & (auth > 0) & (u_act < S["act"] * act_scale)
        if S["n0"] and t >= T0:
            m["attack_steps_eff"] += int(active_att.sum())
            m["impostor_access"] += int(active_imp.sum())
            m["impostor_access_transport"] += int((active_imp & ~sens_dev).sum())
        if S.get("spread") and t >= T0:
            inf_src = active_att * beta
            out_ok = ~iso[city.edge]
            lam = city.A_in @ np.log1p(-np.clip(inf_src, 0, 0.99))
            lam_out = city.A_out @ np.log1p(-np.clip(inf_src * out_ok, 0, 0.99))
            p_inf = 1 - np.exp(lam + lam_out * out_ok)
            comp |= (~comp) & (~removed) & (~imp_now) & (u_spread < p_inf)
        ever |= comp
        # ---- evidence
        emit_att = active_att | active_imp
        emit = emit_att | ((~removed) & (~emit_att) & (u_emit < 0.5))
        if respond:
            cls = np.full(N, "normal", dtype=object)
            if classes:
                cls[emit_att] = np.array(classes, dtype=object)[cls_idx[emit_att]]
            ie = np.flatnonzero(emit)
            sc = ev.draw(obs, det, cls[ie], city.edge[ie])
            ema_p[ie] = 0.5 * ema_p[ie] + 0.5 * sc
            z = obs.normal(0, 1, N) + np.where(emit_att, S["mu"], 0.0)
            act_dev = ~removed
            if use_beh:
                u = 1 / (1 + np.exp(-1.5 * (z - 1.5)))
                ema_u[act_dev] = 0.7 * ema_u[act_dev] + 0.3 * u[act_dev]
                rep[act_dev] = 0.98 * rep[act_dev] + 0.02 * (1 - np.maximum(ema_u[act_dev], ema_p[act_dev]))
            else:
                rep[act_dev] = 0.98 * rep[act_dev] + 0.02 * (1 - ema_p[act_dev])
        # ---- policy
        if respond:
            t1 = time.perf_counter()
            if P["trust"]:
                R = np.zeros(N)
                if P["twin"]:
                    sus_vec = (~removed).astype(float) * (1 - np.clip(ema_p, 0, 1) * ~removed)
                    n1 = city.Ahat @ sus_vec
                    n2 = city.Ahat @ n1
                    bh = city.beta_hat * horizon
                    R = np.clip((bh * n1 + 0.5 * bh ** 2 * n2) / 5.0, 0, 1) * city.crit * city.sens * (ema_p > 0.3)
                b = 1 - ema_u if use_beh else np.ones(N)
                if not P.get("twin_in_trust", True):
                    R = np.zeros(N)
                T = np.clip(0.35 * b + 0.25 * rep + 0.40 * auth - 0.60 * ema_p - 0.40 * R, 0, 1)
                if P.get("veto", False):
                    # zero-trust veto: credentials and reputation cannot outweigh threat evidence
                    T = np.minimum(T, 1 - np.maximum(ema_p, R))
                restr = (T < tau_restrict + thr_shift) & ~removed
                low = (T < tau_allow + thr_shift) & ~pq_identity & ~removed
                q_new = (T < tau_quar + thr_shift) & ~removed
                b_new = (T < tau_block + thr_shift) & ~removed
                susp = restr.copy()
            else:
                hit = (ema_p > dthr) & ~removed
                # consecutive observations: only steps in which the device emitted a flow update the counter
                consec = np.where(emit & hit, consec + 1, np.where(emit & ~hit, 0, consec))
                q_new = (consec >= P.get("consec", 2)) & ~removed
                b_new = np.zeros(N, bool)
                restr = np.zeros(N, bool)
                low = hit & ~pq_identity
                susp = hit
            # adaptive PQ re-authentication of suspicious entities, if the handshake fits the slice budget
            if pqc_mode == "adaptive":
                need = low & fits
                m["pq_deferred"] += int((low & ~fits).sum())
                if need.any():
                    m["n_pq_reauth"] += int(need.sum()); m["n_pq_hs"] += int(need.sum())
                    pq_identity[need] = True
                    auth[need & ~imp_now] = 1.0
                    auth[need & imp_now] = 0.0
            b_new |= (auth == 0) & ~blk                # failed PQ verification is a hard block
            if P["twin"] and t % 3 == 0:
                cand = [k for k in np.unique(city.edge[susp & ~q_new]) if not iso[k] and last_eval[k] <= t - 6]
                if cand:
                    last_eval[cand] = t
                    belief = np.clip(ema_p, 0, 1) * (1 - rep) * susp
                    for k, d_ in zip(cand, _twin_validate(city, cand, belief, removed | q_new, horizon, mc, rtw)):
                        if d_:
                            iso[k] = True; iso_until[k] = t + 30; m["isolations"] += 1
            elif P["trust"] and not P["twin"] and t % 3 == 0:
                # without the twin: static rule, isolate a cluster once three devices are suspected in it
                flagged = np.bincount(city.edge[susp & ~q_new], minlength=city.n_edges)
                for k in np.flatnonzero((flagged >= 3) & ~iso):
                    iso[k] = True; iso_until[k] = t + 30; m["isolations"] += 1
            quar[q_new] = True; q_until[q_new] = t + 30
            blk[b_new] = True; b_until[b_new] = t + 60
            m["decision_s"] += time.perf_counter() - t1
            # operator review (identical for all policies): benign devices are released, compromised ones are cleaned
            rel = quar & (q_until <= t) & ~comp & ~imp_now
            quar[rel] = False; ema_p[rel] = 0; ema_u[rel] = 0
            relb = blk & (b_until <= t) & ~comp & ~imp_now
            blk[relb] = False; ema_p[relb] = 0; ema_u[relb] = 0
            iso[iso_until <= t] = False
        # ---- service accounting for benign devices
        benign = ~comp & ~imp_now
        m["benign_steps"] += int(benign.sum())
        fb = benign & (quar | blk)
        m["fb_steps"] += int(fb.sum())
        w = city.w
        # weight of the strongest restriction a benign device suffers: blocked/quarantined 1, isolated cluster 0.5,
        # rate-limited 0.2
        wt = np.where(fb, 1.0, np.where(benign & iso[city.edge], 0.5, np.where(benign & restr, 0.2, 0.0)))
        m["disruption"] += float((w * wt).sum())
        if S.get("spread") and t > T0 and m["first_contain"] is None and comp.any():
            if not (comp & ~(quar | blk)).any():
                m["first_contain"] = t - T0
        if record:
            trace.append((int(comp.sum()), int((quar | blk).sum()), int(iso.sum())))
    m.update(ever=int(ever.sum()), fb_rate=m["fb_steps"] / max(m["benign_steps"], 1),
             hndl_sensitive=m["n_sens_classical"] / max(m["n_sens_sessions"], 1),
             hndl_all=m["n_classical"] / max(m["n_sessions"], 1),
             disruption_h=m["disruption"] * STEP_S / 3600.0, wsum=city.wsum,
             contained=m["first_contain"] is not None)
    if record:
        m["trace"] = trace
    return m


def _twin_validate(city, cands, belief, removed, H, M, rng, g_min=1.0):
    """Monte Carlo validation of isolating each candidate cluster k on the twin graph with the twin's own
    propagation estimate. Initial infections are sampled only inside k from the belief of its suspected devices; both
    actions (quarantine only, isolate k) use common random numbers, so their difference isolates the effect of the
    isolation. Isolate if the expected number of infections escaping k drops by at least g_min."""
    belief = np.clip(belief, 0, 1) * ~removed
    keep = (~removed).astype(float)
    Ah = city.Ahat                                   # symmetric
    bh = city.beta_hat
    out = []
    for k in cands:
        inside = city.edge == k
        if belief[inside].sum() < 0.5:               # fewer than half a compromised device expected
            out.append(False)
            continue
        X0 = (rng.random((M, city.N)) < belief * inside).astype(float)
        U = rng.random((H, M, city.N))
        res = []
        for isolate in (False, True):
            X = X0.copy()
            for h in range(H):
                src = X * bh
                if isolate:
                    lin = np.log1p(-np.clip(src * inside, 0, 0.99))
                    lout = np.log1p(-np.clip(src * ~inside, 0, 0.99))
                    lam = np.where(inside, (Ah @ lin.T).T, (Ah @ lout.T).T)
                else:
                    lam = (Ah @ np.log1p(-np.clip(src, 0, 0.99)).T).T
                X = np.maximum(X, (U[h] < 1 - np.exp(lam)) * keep)
            res.append((X * ~inside).sum(1).mean())
        out.append((res[0] - res[1]) >= g_min)
    return out
