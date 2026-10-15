# -*- coding: utf-8 -*-
"""Federated threat-intelligence experiments with all clients trained in one batched tensor program.

K edge clients hold Dirichlet-partitioned shards. Each round every client runs tau local SGD steps from the global
model; the server aggregates the client updates with FedAvg, FedProx (proximal local objective), Krum, Multi-Krum,
coordinate-wise median, coordinate-wise trimmed mean, or the trust-aware aggregation (TA) of A-PQZTO. Malicious
clients can flip attack labels to benign (targeted label flipping) or send sign-flipped, scaled updates.
"""
import time

import numpy as np
import torch
import torch.nn.functional as F
from sklearn.metrics import f1_score, roc_auc_score, balanced_accuracy_score

torch.set_num_threads(1)

AGGS = ["fedavg", "fedprox", "krum", "mkrum", "median", "trmean", "ta"]


# -------------------------------------------------------------------------------------------- partitions
def partition(y, K, alpha, rng, min_size=40, benign_iid=False):
    """alpha=None -> IID equal split; otherwise Dirichlet(alpha) over clients for every class. With benign_iid the
    benign class (label 0) is split evenly and only the attack classes follow the Dirichlet skew."""
    n = len(y)
    if alpha is None:
        perm = rng.permutation(n)
        return [np.sort(p) for p in np.array_split(perm, K)]
    for _ in range(200):
        parts = [[] for _ in range(K)]
        for c in np.unique(y):
            ii = rng.permutation(np.flatnonzero(y == c))
            p = np.ones(K) / K if (benign_iid and c == 0) else rng.dirichlet(alpha * np.ones(K))
            cut = (np.cumsum(p) * len(ii)).astype(int)[:-1]
            for k, chunk in enumerate(np.split(ii, cut)):
                parts[k].extend(chunk.tolist())
        if min(len(p) for p in parts) >= min_size:
            return [np.sort(np.array(p)) for p in parts]
    raise RuntimeError("partition failed")


# -------------------------------------------------------------------------------------------- batched MLP
class BMLP:
    """K independent MLPs (d -> h1 -> h2 -> C) stored as stacked tensors; flat view for aggregation."""

    def __init__(self, d, C, K, h=(128, 64), seed=0):
        g = torch.Generator().manual_seed(seed)
        dims = [d, *h, C]
        self.shapes = []
        for a, b in zip(dims[:-1], dims[1:]):
            self.shapes += [(a, b), (b,)]
        self.sizes = [int(np.prod(s)) for s in self.shapes]
        self.P = sum(self.sizes)
        w = []
        for s in self.shapes:
            if len(s) == 2:
                bound = (6 / (s[0] + s[1])) ** 0.5
                w.append((torch.rand(s, generator=g) * 2 - 1) * bound)
            else:
                w.append(torch.zeros(s))
        self.global_flat = torch.cat([x.reshape(-1) for x in w])
        self.K = K

    def unflat(self, flat):
        """flat [K, P] -> list of [K, *shape] tensors (views)."""
        out, o = [], 0
        for s, n in zip(self.shapes, self.sizes):
            out.append(flat[:, o:o + n].reshape(flat.shape[0], *s))
            o += n
        return out

    @staticmethod
    def forward(params, X):
        """params list for K models, X [K, B, d] -> logits [K, B, C]."""
        h = X
        L = len(params) // 2
        for i in range(L):
            W, b = params[2 * i], params[2 * i + 1]
            h = torch.baddbmm(b.unsqueeze(1), h, W)
            if i < L - 1:
                h = F.relu(h)
        return h


def predict_logits(model, flat, X, bs=8192):
    out = []
    with torch.no_grad():
        prm = model.unflat(flat.unsqueeze(0))
        for i in range(0, len(X), bs):
            xb = torch.from_numpy(X[i:i + bs]).unsqueeze(0)
            out.append(BMLP.forward(prm, xb)[0].double().numpy())
    return np.concatenate(out)


def predict_proba(model, flat, X, bs=8192):
    L = predict_logits(model, flat, X, bs)
    L = L - L.max(1, keepdims=True)
    P = np.exp(L)
    return P / P.sum(1, keepdims=True)


def attack_logodds(L):
    """log P(attack) - log P(benign) from logits, without saturation."""
    from scipy.special import logsumexp
    return logsumexp(L[:, 1:], axis=1) - L[:, 0]


# -------------------------------------------------------------------------------------------- aggregation
def true_median(U):
    """Coordinate-wise median; for an even number of clients the mean of the two middle values."""
    K = U.shape[0]
    S = U.sort(0).values
    return S[K // 2] if K % 2 else 0.5 * (S[K // 2 - 1] + S[K // 2])


def aggregate(name, U, n, f, state):
    """U [K, P] client updates; n [K] sample counts; f assumed number of Byzantine clients."""
    K = U.shape[0]
    w = torch.as_tensor(n, dtype=torch.float32)
    if name in ("fedavg", "fedprox"):
        return (w[:, None] * U).sum(0) / w.sum()
    if name == "median":
        return true_median(U)
    if name == "trmean":
        # M5: trim the same number of clients per side as Krum assumes to be Byzantine
        b = f
        S = U.sort(0).values
        return S[b:K - b].mean(0)
    if name in ("krum", "mkrum"):
        D = torch.cdist(U, U) ** 2
        m = max(1, K - f - 2)
        sc = D.sort(1).values[:, 1:m + 1].sum(1)
        order = sc.argsort()
        if name == "krum":
            return U[order[0]]
        sel = order[:K - f]
        return U[sel].mean(0)
    if name == "ta":
        # trust-aware aggregation: consistency with the coordinate-wise median, norm clipping, and an exponentially
        # smoothed reliability that remembers past behaviour of each edge client
        ref = true_median(U)
        norms = U.norm(dim=1) + 1e-12
        med_norm = norms.median()
        Uc = U * torch.clamp(1.5 * med_norm / norms, max=1.0)[:, None]
        cos = (Uc @ ref) / (Uc.norm(dim=1) * (ref.norm() + 1e-12) + 1e-12)
        cons = torch.clamp(cos, min=0.0)
        r = state.get("rel")
        r = cons if r is None else 0.7 * r + 0.3 * cons
        state["rel"] = r
        edge_trust = state.get("edge_trust", torch.ones(K))
        omega = w * r * edge_trust
        omega = torch.where(r >= state.get("cut", 0.5) * r.max(), omega, torch.zeros_like(omega))
        if omega.sum() <= 0:
            return ref
        return (omega[:, None] * Uc).sum(0) / omega.sum()
    raise ValueError(name)


# -------------------------------------------------------------------------------------------- training run
def run(d, agg="fedavg", K=12, alpha=1.0, rounds=40, tau=20, B=128, lr=0.05, mu=0.01, n_mal=0, attack=None,
        scale=4.0, seed=0, f_assumed=3, return_model=False, local_only=False, centralized=False, hidden=(64, 32),
        split="te", ta_cut=0.0, benign_iid=False):
    rng = np.random.default_rng(seed)
    torch.manual_seed(seed)
    Xtr, ytr = d["X_tr"], d["y_tr"]
    C = int(max(d["y_tr"].max(), d["y_te"].max()) + 1)
    if centralized:
        parts, Kc = [np.arange(len(ytr))], 1
    else:
        parts, Kc = partition(ytr, K, alpha, rng, benign_iid=benign_iid), K
    mal = set(rng.choice(Kc, n_mal, replace=False).tolist()) if n_mal else set()
    ylocal = [ytr[p].copy() for p in parts]
    if attack == "lf":
        for k in mal:
            ylocal[k][ylocal[k] != 0] = 0
    Xt = torch.from_numpy(Xtr)
    # one gather per step: concatenated client index table, per-client offsets and lengths
    allidx = torch.from_numpy(np.concatenate(parts))
    ycat = torch.from_numpy(np.concatenate(ylocal))
    lens = torch.tensor([len(p) for p in parts], dtype=torch.float64)
    offs = torch.cumsum(torch.cat([torch.zeros(1, dtype=torch.float64), lens[:-1]]), 0)
    tg = torch.Generator().manual_seed(int(seed) + 7)
    model = BMLP(Xtr.shape[1], C, Kc, h=hidden, seed=seed)
    g = model.global_flat.clone()
    nk = np.array([len(p) for p in parts], dtype=float)
    state = {"cut": ta_cut}
    Bc = B * K if centralized else B
    t0 = time.time()
    local = g.unsqueeze(0).repeat(Kc, 1)
    for r in range(rounds):
        if not local_only:
            local = g.unsqueeze(0).repeat(Kc, 1)
        local.requires_grad_(True)
        mom = torch.zeros_like(local)
        start = local.detach().clone()
        for s in range(tau):
            u = torch.rand((Kc, Bc), generator=tg, dtype=torch.float64)
            pos = (offs[:, None] + torch.floor(u * lens[:, None])).long()
            xb = Xt[allidx[pos]]
            yb = ycat[pos]
            prm = model.unflat(local)
            out = BMLP.forward(prm, xb)
            loss = F.cross_entropy(out.reshape(-1, C), yb.reshape(-1), reduction="sum") / Bc
            if agg == "fedprox" and not centralized:
                loss = loss + 0.5 * mu * ((local - start) ** 2).sum()
            gr, = torch.autograd.grad(loss, local)
            with torch.no_grad():
                gr = gr + 1e-4 * local
                mom = 0.9 * mom + gr
                local = (local - lr * mom).detach().requires_grad_(True)
        with torch.no_grad():
            local = local.detach()
            if local_only or centralized:
                g = local[0] if centralized else g
                continue
            U = local - g.unsqueeze(0)
            if attack == "sf":
                for k in mal:
                    U[k] = -scale * U[k]
            g = g + aggregate(agg, U, nk, f_assumed, state)
    train_s = time.time() - t0
    out = {"agg": "central" if centralized else ("local" if local_only else agg), "alpha": alpha, "seed": seed,
           "n_mal": n_mal, "attack": attack, "train_s": train_s, "mal": sorted(mal)}
    if local_only:
        out["local_flat"] = local
        return out
    L = predict_logits(model, g, d["X_" + split])
    out["diverged"] = bool(not np.isfinite(L).all())
    if out["diverged"]:
        L = np.zeros_like(L)
    out.update(evaluate(L, d["y_" + split], diverged=out["diverged"]))
    if return_model:
        out["flat"] = g
        out["model"] = model
        out["parts"] = parts
    return out


def evaluate(L, y, diverged=False):
    """L: logits. A diverged model is scored as predicting the benign class everywhere (detection 0); its FPR is
    reported as missing so that it does not lower the mean FPR."""
    P = L
    pred = L.argmax(1)
    s = attack_logodds(L)
    yb = (y != 0).astype(int)
    pb = (pred != 0).astype(int)
    neg = yb == 0
    res = {"macro_f1": float(f1_score(y, pred, average="macro", labels=np.unique(y), zero_division=0)),
           "bin_f1": float(f1_score(yb, pb, zero_division=0)),
           "auc": float(roc_auc_score(yb, s)) if 0 < yb.sum() < len(yb) else float("nan"),
           "fpr": float(pb[neg].mean()) if (neg.any() and not diverged) else float("nan"),
           "detect_rate": float(pb[yb == 1].mean()),
           "bal_acc": float(balanced_accuracy_score(y, pred)),
           "acc": float((pred == y).mean())}
    res["per_class_recall"] = [float((pred[y == c] == c).mean()) if (y == c).any() else float("nan")
                               for c in range(P.shape[1])]
    return res
