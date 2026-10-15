# -*- coding: utf-8 -*-
"""Dataset loading, leakage-safe preprocessing and stratified splits for the three IoT intrusion datasets.

Each dataset is processed on its own (the schemas are not merged). Steps: drop identifiers and free-text fields,
normalise placeholder spellings ("0" vs "0.0" vs "-"), remove exact duplicates and label-conflicting duplicates,
stratified 70/15/15 split, one-hot categorical encoding and log/standard scaling fitted on the training split only.
A single-feature leakage audit reports how well any one column separates attack from benign traffic.
"""
import hashlib
import json
import os

import numpy as np
import pandas as pd

DATA = os.environ.get("APQ_DATA", r"E:\A-PQZTO_data")
CACHE = os.environ.get("APQ_CACHE", r"E:\A-PQZTO_work\cache")

# ------------------------------------------------------------------------------------------- dataset specs
TON_DROP = ["src_ip", "dst_ip", "src_port", "dns_query", "ssl_subject", "ssl_issuer", "http_uri", "http_user_agent"]
TON_CAT = ["proto", "service", "conn_state", "dns_AA", "dns_RD", "dns_RA", "dns_rejected", "ssl_version", "ssl_cipher",
           "ssl_resumed", "ssl_established", "http_trans_depth", "http_method", "http_version", "http_orig_mime_types",
           "http_resp_mime_types", "weird_name", "weird_addl", "weird_notice"]

# Ferrag et al. recommend dropping these; packet-instance fields (checksums, raw sequence/ack numbers) are dropped too
EDGE_DROP = ["frame.time", "ip.src_host", "ip.dst_host", "arp.src.proto_ipv4", "arp.dst.proto_ipv4", "http.file_data",
             "http.request.full_uri", "icmp.transmit_timestamp", "http.request.uri.query", "tcp.options", "tcp.payload",
             "tcp.srcport", "tcp.dstport", "udp.port", "mqtt.msg", "tcp.checksum", "icmp.checksum", "tcp.ack_raw",
             "tcp.seq", "tcp.ack"]

# CICIoT2023: 34 classes grouped into the 8 families used by the dataset authors
CIC_FAMILY = {"BENIGN": "Benign", "MIRAI": "Mirai", "DDOS": "DDoS", "DOS": "DoS", "RECON": "Recon",
              "VULNERABILITYSCAN": "Recon", "DNS_SPOOFING": "Spoofing", "MITM-ARPSPOOFING": "Spoofing",
              "BROWSERHIJACKING": "Web", "BACKDOOR_MALWARE": "Web", "XSS": "Web", "UPLOADING_ATTACK": "Web",
              "SQLINJECTION": "Web", "COMMANDINJECTION": "Web", "DICTIONARYBRUTEFORCE": "BruteForce"}


def _cic_family(lbl):
    u = str(lbl).upper()
    if u in CIC_FAMILY:
        return CIC_FAMILY[u]
    for k, v in CIC_FAMILY.items():
        if u.startswith(k):
            return v
    return "Other"


def _norm_placeholders(s):
    """Unify spellings of the same value: '0', '0.0', '0.00' -> '0'; '-', '' and NaN -> 'NA'."""
    s = s.astype(str).str.strip()
    num = pd.to_numeric(s, errors="coerce")
    out = s.where(num.isna(), num.map(lambda v: ("%g" % v) if pd.notna(v) else "NA"))
    return out.replace({"-": "NA", "": "NA", "nan": "NA", "None": "NA"})


def load_raw(name):
    if name == "ton":
        df = pd.read_csv(os.path.join(DATA, "train_test_network.csv"), low_memory=False)
        y = df["type"].astype(str).str.lower()
        df = df.drop(columns=TON_DROP + ["label", "type"])
        cat = TON_CAT
    elif name == "edge":
        df = pd.read_csv(os.path.join(DATA, "ML-EdgeIIoT-dataset.csv"), low_memory=False)
        y = df["Attack_type"].astype(str)
        df = df.drop(columns=EDGE_DROP + ["Attack_label", "Attack_type"])
        cat = [c for c in df.columns if df[c].dtype == object]
    elif name == "cic":
        parts = [pd.read_csv(os.path.join(DATA, f), low_memory=False)
                 for f in ("CICIoT2023_Merged01.csv", "CICIoT2023_Merged02.csv")]
        df = pd.concat(parts, ignore_index=True)
        y = df["Label"].map(_cic_family)
        df = df.drop(columns=["Label"])
        cat = []
    else:
        raise ValueError(name)
    for c in cat:
        df[c] = _norm_placeholders(df[c])
    num = [c for c in df.columns if c not in cat]
    for c in num:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df[num] = df[num].replace([np.inf, -np.inf], np.nan).fillna(0.0)
    return df, y.reset_index(drop=True), cat, num


def deduplicate(df, y):
    """Drop exact duplicates; drop feature vectors that occur with more than one label."""
    key = pd.util.hash_pandas_object(df, index=False)
    tab = pd.DataFrame({"k": key.values, "y": y.values})
    n_lab = tab.groupby("k")["y"].nunique()
    conflict = tab["k"].map(n_lab) > 1
    keep = (~tab.duplicated(["k", "y"])) & (~conflict)
    return df[keep.values].reset_index(drop=True), y[keep.values].reset_index(drop=True), int(conflict.sum())


def cap_classes(df, y, cap, seed=0):
    rng = np.random.default_rng(seed)
    idx = []
    for c in sorted(y.unique()):
        ii = np.flatnonzero((y == c).values)
        idx.append(rng.choice(ii, min(cap, len(ii)), replace=False))
    idx = np.sort(np.concatenate(idx))
    return df.iloc[idx].reset_index(drop=True), y.iloc[idx].reset_index(drop=True)


def stratified_split(y, seed=0, frac=(0.70, 0.15, 0.15)):
    rng = np.random.default_rng(seed)
    tr, va, te = [], [], []
    for c in sorted(y.unique()):
        ii = rng.permutation(np.flatnonzero((y == c).values))
        a, b = int(round(frac[0] * len(ii))), int(round((frac[0] + frac[1]) * len(ii)))
        tr.append(ii[:a]); va.append(ii[a:b]); te.append(ii[b:])
    return [np.sort(np.concatenate(z)) for z in (tr, va, te)]


def leakage_audit(df, ybin, cat, max_levels=200):
    """Best single-feature binary accuracy (majority label per value, or best threshold for numeric columns)."""
    res = {}
    yb = np.asarray(ybin)
    base = max(yb.mean(), 1 - yb.mean())
    for c in df.columns:
        x = df[c]
        if c in cat or x.nunique() <= max_levels:
            g = pd.DataFrame({"x": x.astype(str).values, "y": yb}).groupby("x")["y"].agg(["sum", "count"])
            acc = np.maximum(g["sum"], g["count"] - g["sum"]).sum() / len(yb)
        else:
            v = x.values.astype(float)
            o = np.argsort(v, kind="mergesort")
            ys = yb[o]
            cpos = np.cumsum(ys)
            n = len(ys)
            left_pos = cpos[:-1]
            k = np.arange(1, n)
            # predict attack on the right side or on the left side, whichever is better
            acc1 = ((k - left_pos) + (cpos[-1] - left_pos)) / n
            acc2 = (left_pos + (n - k) - (cpos[-1] - left_pos)) / n
            valid = v[o][1:] != v[o][:-1]
            acc = max(acc1[valid].max(initial=0), acc2[valid].max(initial=0), base)
        res[c] = float(acc)
    top = sorted(res.items(), key=lambda kv: -kv[1])[:5]
    return {"majority_baseline": float(base), "top_single_feature": top, "max": top[0][1] if top else base}


def prepare(name, seed=0, cic_cap=40000):
    """Returns dict with X_tr, y_tr, X_va, y_va, X_te, y_te (float32 / int64), class names, benign index and a
    provenance record. Cached on disk."""
    os.makedirs(CACHE, exist_ok=True)
    cp = os.path.join(CACHE, f"{name}_v2_s{seed}.npz")
    if os.path.exists(cp):
        z = np.load(cp, allow_pickle=True)
        d = {k: z[k] for k in z.files}
        d["classes"] = list(d["classes"])
        d["info"] = json.loads(str(d["info"]))
        return d
    import pickle
    dp = os.path.join(CACHE, f"{name}_v2_dedup.pkl")
    if os.path.exists(dp):
        df, y, cat, num, n_raw, n_conf = pickle.load(open(dp, "rb"))
    else:
        df, y, cat, num = load_raw(name)
        n_raw = len(df)
        df, y, n_conf = deduplicate(df, y)
        pickle.dump((df, y, cat, num, n_raw, n_conf), open(dp, "wb"), protocol=4)
    n_dedup = len(df)
    if name == "cic":
        df, y = cap_classes(df, y, cic_cap, seed=seed)
    classes = sorted(y.unique(), key=lambda c: (c.lower() not in ("normal", "benign"), c))
    cidx = {c: i for i, c in enumerate(classes)}
    yi = y.map(cidx).values.astype(np.int64)
    audit = leakage_audit(df, (yi != 0).astype(int), cat) if seed == 0 else None
    tr, va, te = stratified_split(y, seed=seed)
    # encoding fitted on training rows only
    cats = {}
    for c in cat:
        lv = df[c].iloc[tr].value_counts()
        cats[c] = list(lv.index[:30])
    num_cols = [c for c in num if df[c].iloc[tr].std() > 0]

    def encode(ix):
        part = df.iloc[ix]
        mats = [np.sign(part[num_cols].values) * np.log1p(np.abs(part[num_cols].values))]
        for c in cat:
            m = np.zeros((len(part), len(cats[c])), dtype=np.float32)
            pos = {v: j for j, v in enumerate(cats[c])}
            jj = part[c].map(pos)
            ok = jj.notna().values
            m[np.flatnonzero(ok), jj[ok].astype(int).values] = 1.0
            mats.append(m)
        return np.concatenate(mats, axis=1).astype(np.float32)

    Xtr, Xva, Xte = encode(tr), encode(va), encode(te)
    mu, sd = Xtr.mean(0), Xtr.std(0) + 1e-6
    Xtr, Xva, Xte = [((x - mu) / sd).astype(np.float32) for x in (Xtr, Xva, Xte)]
    keep = Xtr.std(0) > 1e-4
    Xtr, Xva, Xte = Xtr[:, keep], Xva[:, keep], Xte[:, keep]
    info = {"dataset": name, "rows_raw": n_raw, "rows_after_dedup": n_dedup, "label_conflicts_removed": n_conf,
            "rows_used": int(len(df)), "n_features": int(Xtr.shape[1]), "classes": classes,
            "class_counts": {c: int((yi == i).sum()) for i, c in enumerate(classes)},
            "split": [int(len(tr)), int(len(va)), int(len(te))], "leakage_audit": audit,
            "categorical": cat, "numeric": num_cols}
    d = dict(X_tr=Xtr, y_tr=yi[tr], X_va=Xva, y_va=yi[va], X_te=Xte, y_te=yi[te],
             classes=np.array(classes, dtype=object), info=json.dumps(info))
    np.savez_compressed(cp, **d)
    d["classes"] = classes
    d["info"] = info
    return d


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


if __name__ == "__main__":
    import sys
    for nm in sys.argv[1:] or ["ton", "edge", "cic"]:
        d = prepare(nm)
        print(json.dumps({k: v for k, v in d["info"].items() if k not in ("categorical", "numeric")}, indent=1))
