# Analysis of the post-quantum (PQC) cost measurements written by pqc_bench.py (OpenSSL 3.5, FIPS 203 / FIPS 204).
#  * parses the raw `openssl speed` tables (KEM and signature, plus any other "*_raw" key or --extra-raw file),
#    takes the median over repetitions per algorithm and operation, converts to milliseconds;
#  * classical key exchange (X25519, P-256) comes from the legacy ECDH table (`openssl speed ecdhx25519 ecdhp256`,
#    header "op op/s"): one "op" = one ECDH shared-secret derivation (key generation is not timed); it is stored as
#    kem_ms[...]["derive"], and kex_per_handshake_ms states exactly which operations are summed per handshake;
#  * summarises the TLS 1.3 measurements (classical X25519 + ECDSA P-256 vs hybrid X25519MLKEM768 + ML-DSA-65):
#    handshake bytes from the s_client -msg trace, per-handshake time from s_time, certificate size;
#  * kappa_max per slice = L_d / t_hs(hybrid), hybrid-vs-classical overhead;
#  * writes results/pqc_summary.json and figures/fig9_pqc.{png,tif}.
#
#   python pqc_analyze.py                         real data (results/pqc/pqc_bench.json)
#   python pqc_analyze.py --extra-raw cls.txt     add e.g. `openssl speed ed25519 ecdsap256` output (Ed25519/ECDSA
#                                                 are NOT part of `openssl speed -signature-algorithms`)
#   python pqc_analyze.py --selftest [--outdir D] FAKE data, writes only to a temporary directory
import argparse, json, math, os, re, statistics, sys, tempfile
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import to_rgb
from matplotlib.patches import Patch

ROOT = r"E:\A-PQZTO_work"
BENCH = os.path.join(ROOT, "results", "pqc", "pqc_bench.json")
SUMMARY = os.path.join(ROOT, "results", "pqc_summary.json")
FIG = os.path.join(ROOT, "figures")
FIGNAME = "fig9_pqc"
L_D_MS = {"transport": 10.0, "energy": 50.0, "health": 100.0, "safety": 20.0}   # slice handshake latency budgets
COL = {"classical": "#0072B2", "pq": "#D55E00", "hybrid": "#CC79A7"}
CAT_LAB = {"classical": "Classical", "pq": "Post-quantum", "hybrid": "Hybrid"}
KEM_OPS = ("keygen", "encaps", "decaps")
SIG_OPS = ("keygen", "sign", "verify")
# label, category, [(table kind, regex full-matched on the normalised name = lower-case alphanumerics only)]
# X25519 / ECP-256: DHKEM rows of `openssl speed -kem-algorithms` if present, else the legacy ECDH table
# (" 253 bits ecdh (X25519)   0.0001s  12589.5" under the header "op  op/s"; one op = one shared-secret derivation)
KEM_SEL = [("X25519", "classical", [("kem", r"x25519"), ("kex_classic", r"(\d+bits)?ecdhx25519")]),
           ("ECP-256", "classical", [("kem", r"ecp256"),
                                     ("kex_classic", r"(\d+bits)?ecdh(nistp256|p256|prime256v1|secp256r1)")]),
           ("ML-KEM-512", "pq", [("kem", r"mlkem512")]),
           ("ML-KEM-768", "pq", [("kem", r"mlkem768")]),
           ("ML-KEM-1024", "pq", [("kem", r"mlkem1024")]),
           ("X25519MLKEM768", "hybrid", [("kem", r"x25519mlkem768")])]
SIG_SEL = [("Ed25519", "classical", [("sig_classic", r"(\d+bits)?eddsaed25519"), ("sig", r"ed25519")]),
           ("ECDSA P-256", "classical", [("sig_classic", r"(\d+bits)?ecdsa(nistp256|p256|prime256v1|secp256r1)"),
                                         ("sig", r"ecdsa(p256|nistp256)?")]),
           ("RSA-2048", "classical", [("sig", r"rsa2048"), ("rsa_classic", r"rsa2048(bits)?")]),
           ("ML-DSA-44", "pq", [("sig", r"mldsa44")]),
           ("ML-DSA-65", "pq", [("sig", r"mldsa65")]),
           ("ML-DSA-87", "pq", [("sig", r"mldsa87")])]
POST_HS = {"NewSessionTicket", "KeyUpdate"}       # post-handshake messages, excluded from "full handshake" bytes
# exact size deltas hybrid - classical expected from the specs (one key share each side, RFC 8446 framing):
# X25519MLKEM768 client share 1216 B vs X25519 32 B; server share 1120 B vs 32 B; ML-DSA-65 CertificateVerify
# = 4 (handshake header) + 2 (scheme) + 2 (length) + 3309 (signature) = 3317 B.
EXPECTED = {"ClientHello_delta": 1184, "ServerHello_delta": 1088, "CertificateVerify_hybrid": 3317}

plt.rcParams.update({"font.family": "Times New Roman", "font.size": 8, "mathtext.fontset": "stix",
                     "axes.spines.top": False, "axes.spines.right": False, "axes.grid": True, "grid.color": "#e6e5e1",
                     "grid.linewidth": 0.6, "hatch.linewidth": 0.5})


# ----------------------------------------------------------------------------------------------- openssl speed parsing
_NUM = re.compile(r"^(?:\d+(?:\.\d*)?|\.\d+|inf|nan)$", re.I)
_TIME = re.compile(r"^(?:\d+(?:\.\d*)?|\.\d+|inf|nan)s$", re.I)
_OPCANON = {"signs": "sign", "keygens": "keygen", "verifies": "verify", "encr.": "encrypt", "decr.": "decrypt"}


def norm(name):
    return re.sub(r"[^a-z0-9]", "", name.lower())


def _header(line):
    """Column header such as 'keygen  encaps  decaps keygens/s  encaps/s  decaps/s' -> (ops, table kind)."""
    toks = line.split()
    rate = [t for t in toks if t.endswith("/s")]
    ops = [_OPCANON.get(t, t) for t in toks if not t.endswith("/s")]
    if not rate or len(ops) != len(rate) or any(_NUM.match(t) or _TIME.match(t) or ":" in t for t in toks):
        return None
    if "encaps" in ops:
        kind = "kem"
    elif ops == ["keygen", "sign", "verify"]:
        kind = "sig"
    elif "encrypt" in ops:
        kind = "rsa_classic"                 # legacy RSA table: sign verify encrypt decrypt
    elif ops == ["sign", "verify"]:
        kind = "sig_classic"                 # legacy ECDSA / EdDSA / SM2 tables
    elif ops == ["op"]:
        kind = "kex_classic"                 # legacy ECDH / FFDH tables
    else:
        kind = "other"
    return ops, kind


def _row(line):
    """Data row: <name (any chars)> <t_1>s ... <t_n>s <r_1> ... <r_n>; returns (name, times_s, rates_per_s)."""
    toks = line.split()
    i, rates, times = len(toks), [], []
    while i > 0 and _NUM.match(toks[i - 1]):
        rates.insert(0, float(toks[i - 1])); i -= 1
    while i > 0 and _TIME.match(toks[i - 1]):
        times.insert(0, float(toks[i - 1][:-1])); i -= 1
    if i == 0 or not rates or len(times) != len(rates):
        return None
    return " ".join(toks[:i]), times, rates


def _to_ms(t, r):
    """Prefer the ops/s column (the legacy ECDSA/EdDSA tables print times with only 4 decimals)."""
    if r is not None and math.isfinite(r) and r > 0:
        return 1000.0 / r
    if t is not None and math.isfinite(t) and t > 0:
        return 1000.0 * t
    return None


def parse_speed_text(txt, default_kind=None):
    """All table rows of one `openssl speed` output (stdout+stderr; 'Doing ...' and version lines are ignored)."""
    out, ops, kind = [], None, None
    for line in txt.splitlines():
        h = _header(line)
        if h:
            ops, kind = h
            continue
        r = _row(line)
        if not r:
            continue
        name, times, rates = r
        o, k = ops, kind
        if o is None or len(o) != len(times):     # no header seen (fragment): infer from the source key
            if default_kind == "kem" and len(times) == 3:
                o, k = list(KEM_OPS), "kem"
            elif default_kind == "sig" and len(times) == 3:
                o, k = list(SIG_OPS), "sig"
            else:
                o, k = [f"op{j + 1}" for j in range(len(times))], "unknown"
        out.append({"kind": k, "name": name, "ms": {op: _to_ms(t, rr) for op, t, rr in zip(o, times, rates)}})
    return out


def collect_speed(bench, extra_texts=()):
    """Aggregate rows over repetitions: {(kind, name): {op: [ms per rep]}} plus repetition counts per source."""
    agg, reps = {}, {}
    sources = []
    for key, val in bench.items():
        if key.endswith("_raw"):
            texts = val if isinstance(val, list) else [val]
            dk = "kem" if key.startswith("kem") else "sig" if key.startswith("sig") else None
            reps[key] = len(texts)
            sources += [(key, dk, t) for t in texts if isinstance(t, str)]
    for j, t in enumerate(extra_texts):
        sources.append((f"extra[{j}]", None, t))
    reps["extra"] = len(extra_texts)
    for key, dk, txt in sources:
        for r in parse_speed_text(txt, dk):
            d = agg.setdefault((r["kind"], r["name"]), {})
            for op, v in r["ms"].items():
                if v is not None:
                    d.setdefault(op, []).append(v)
    return agg, reps


def select(agg, spec, ops, warn):
    """Median ms per op for the selected algorithms (+ min/max and n); None (and a warning) when absent."""
    med, rng, det = {}, {}, {}
    for label, cat, pats in spec:
        hit = None
        for kind, pat in pats:
            for (k, name), d in agg.items():
                if k == kind and re.fullmatch(pat, norm(name)) and d:
                    hit = (k, name, d); break
            if hit:
                break
        if not hit:
            med[label] = None
            warn.append(f"{label}: not found in the openssl speed output")
            continue
        k, name, d = hit
        if k == "kex_classic":
            # legacy ECDH table: its single "op" column is one shared-secret derivation (EVP_PKEY_derive); the
            # time column is rounded to 0.0001 s, so the value comes from op/s (see _to_ms). No keygen/encaps/decaps.
            d = {"derive": d.get("op", [])}
            row_ops = tuple(ops) + ("derive",)
        else:
            row_ops = tuple(ops)
        med[label] = {op: (float(statistics.median(d[op])) if d.get(op) else None) for op in row_ops}
        rng[label] = {op: ([min(d[op]), max(d[op])] if d.get(op) else None) for op in row_ops}
        det[label] = {"category": cat, "table": k, "openssl_name": name, "n": max(len(v) for v in d.values())}
        if k == "kex_classic":
            det[label]["op_meaning"] = "one ECDH shared-secret derivation; key generation not timed by openssl speed"
            miss = [] if d.get("derive") else ["derive"]
        else:
            # the legacy ECDSA / EdDSA / RSA tables have no keygen column: expected, not worth a warning
            miss = [op for op in ops if not d.get(op) and not (op == "keygen" and k in ("sig_classic", "rsa_classic"))]
        if miss:
            warn.append(f"{label}: no value for {', '.join(miss)} (table '{k}')")
    return med, rng, det


def kex_per_handshake(kem_ms):
    """Key-establishment CPU per handshake, both sides together, and exactly what was summed."""
    out = {}
    for lab, v in kem_ms.items():
        if not v:
            continue
        if all(v.get(o) is not None for o in KEM_OPS):
            out[lab] = {"ms": v["keygen"] + v["encaps"] + v["decaps"], "complete": True,
                        "summed": "keygen + encaps + decaps (client key generation, server encapsulation, "
                                  "client decapsulation)"}
        elif v.get("derive") is not None:
            out[lab] = {"ms": 2.0 * v["derive"], "complete": False,
                        "summed": "2 x ECDH derive (one shared-secret derivation per side). A classical ephemeral "
                                  "exchange needs one key generation plus one ECDH derivation per side; openssl speed "
                                  "does not time the key generations, so this value is a lower bound",
                        "ms_if_keygen_equals_derive": 4.0 * v["derive"]}
    return out


def all_medians(agg, kinds):
    return {f"{name} [{k}]" if k not in kinds[:1] else name: {op: float(statistics.median(v)) for op, v in d.items()}
            for (k, name), d in sorted(agg.items()) if k in kinds}


# ----------------------------------------------------------------------------------------------------------- TLS 1.3
def _median(x):
    x = [v for v in x if v is not None and math.isfinite(v)]
    return float(statistics.median(x)) if x else None


def tls_summary(t, warn, tag):
    hs = t.get("handshake") or {}
    msgs = []
    for m in hs.get("messages", []):
        if isinstance(m, dict):
            msgs.append((m.get("dir"), m.get("name"), int(m.get("len", m.get("bytes", 0)))))
        else:
            msgs.append((m[0], m[1], int(m[2])))
    out = {"group": t.get("group"), "cert_alg": t.get("cert")}
    if msgs:
        core = [m for m in msgs if m[1] not in POST_HS]
        out["client_bytes"] = sum(n for d, _, n in core if d == ">>>")
        out["server_bytes"] = sum(n for d, _, n in core if d == "<<<")
        out["client_bytes_incl_post_hs"] = sum(n for d, _, n in msgs if d == ">>>")
        out["server_bytes_incl_post_hs"] = sum(n for d, _, n in msgs if d == "<<<")
        out["messages"] = [{"dir": "C->S" if d == ">>>" else "S->C", "msg": nm, "bytes": n} for d, nm, n in msgs]
        out["hello_retry"] = sum(1 for d, nm, _ in msgs if d == ">>>" and nm == "ClientHello") > 1
        if out["hello_retry"]:
            warn.append(f"tls {tag}: two ClientHello messages (HelloRetryRequest) in the trace")
        cert = [n for d, nm, n in core if d == "<<<" and nm == "Certificate"]
        # TLS 1.3 Certificate = 4 hdr + 1 ctx len + 3 list len + 3 cert len + DER + 2 ext len (single cert, no ext)
        out["cert_der_bytes_from_msg"] = cert[0] - 13 if len(cert) == 1 else None
        if not any(nm == "Finished" for d, nm, _ in core if d == ">>>"):
            warn.append(f"tls {tag}: no client Finished in the message trace (handshake incomplete or trace format)")
    else:
        out["client_bytes"], out["server_bytes"] = hs.get("client_bytes"), hs.get("server_bytes")
        out["messages"] = []
        warn.append(f"tls {tag}: empty message trace; using the stored client/server byte sums (may include "
                    f"NewSessionTicket or be 0 if the -msg regex did not match)")
    cb, sb = out["client_bytes"], out["server_bytes"]
    out["total_bytes"] = cb + sb if cb is not None and sb is not None else None
    out["cert_pem_file_bytes"] = t.get("cert_bytes")
    st = [r for r in (t.get("s_time") or []) if r.get("conns")]
    hs_ms = [1000.0 * r["real_s"] / r["conns"] for r in st if r.get("real_s")]
    cpu_ms = [1000.0 / r["per_user_s"] for r in st if r.get("per_user_s")]
    wall_key = next((k for k in ("wall_s", "real_wall_s", "real_seconds") if st and k in st[0]), None)
    wall_ms = [1000.0 * r[wall_key] / r["conns"] for r in st if r.get(wall_key)] if wall_key else []
    out["s_time_reps"] = len(st)
    out["conns"] = [r["conns"] for r in st]
    out["hs_time_ms"] = _median(hs_ms)                  # 1000 * real_s / conns  (see NOTES: real_s is user CPU)
    out["hs_time_ms_range"] = [min(hs_ms), max(hs_ms)] if hs_ms else None
    out["client_cpu_ms"] = _median(cpu_ms)              # 1000 / per_user_s
    out["client_cpu_ms_range"] = [min(cpu_ms), max(cpu_ms)] if cpu_ms else None
    out["wall_ms"] = _median(wall_ms)
    out["wall_ms_range"] = [min(wall_ms), max(wall_ms)] if wall_ms else None
    if not st:
        warn.append(f"tls {tag}: no s_time repetitions parsed -> handshake time unavailable")
    return out


def _d(a, b):
    return a - b if a is not None and b is not None else None


def _r(a, b):
    return a / b if a is not None and b else None


# ------------------------------------------------------------------------------------------------------------ summary
def summarize(bench, extra_texts=(), source=""):
    warn = []
    agg, reps = collect_speed(bench, extra_texts)
    kem_ms, kem_rng, kem_det = select(agg, KEM_SEL, KEM_OPS, warn)
    sig_ms, sig_rng, sig_det = select(agg, SIG_SEL, SIG_OPS, warn)
    if sig_ms.get("Ed25519") is None or sig_ms.get("ECDSA P-256") is None:
        warn.append("`openssl speed -signature-algorithms` does not benchmark Ed25519/ECDSA (they live in the legacy "
                    "tables); run `openssl speed -seconds 2 ed25519 ecdsap256` and pass it with --extra-raw")
    tl = {(t.get("tag") or "").lower(): t for t in bench.get("tls", [])}
    lst = bench.get("tls", [])
    t_cls = tl.get("classical") or (lst[0] if len(lst) > 0 else {})
    t_hyb = tl.get("hybrid_pq") or tl.get("hybrid") or (lst[1] if len(lst) > 1 else {})
    cls, hyb = tls_summary(t_cls, warn, "classical"), tls_summary(t_hyb, warn, "hybrid")
    ob = {k: _d(hyb[k], cls[k]) for k in ("client_bytes", "server_bytes", "total_bytes")}
    ob["total_ratio"] = _r(hyb["total_bytes"], cls["total_bytes"])
    ot = {"hs_time_ms": _d(hyb["hs_time_ms"], cls["hs_time_ms"]),
          "client_cpu_ms": _d(hyb["client_cpu_ms"], cls["client_cpu_ms"]),
          "wall_ms": _d(hyb["wall_ms"], cls["wall_ms"]),
          "hs_time_ratio": _r(hyb["hs_time_ms"], cls["hs_time_ms"])}
    th, tc = hyb["hs_time_ms"], cls["hs_time_ms"]
    kap = {s: (L / th if th else None) for s, L in L_D_MS.items()}
    # sanity checks against exact spec-derived size deltas (only meaningful if the trace parsed)
    by = lambda T, nm, d: sum(m["bytes"] for m in T["messages"] if m["msg"] == nm and m["dir"] == d) or None
    san = {"ClientHello_delta": _d(by(hyb, "ClientHello", "C->S"), by(cls, "ClientHello", "C->S")),
           "ServerHello_delta": _d(by(hyb, "ServerHello", "S->C"), by(cls, "ServerHello", "S->C")),
           "CertificateVerify_hybrid": by(hyb, "CertificateVerify", "S->C")}
    sanity = {k: {"measured": v, "expected": EXPECTED[k], "ok": (v == EXPECTED[k]) if v is not None else None}
              for k, v in san.items()}
    if sanity["ClientHello_delta"]["measured"] == EXPECTED["ClientHello_delta"] - 8:
        sanity["ClientHello_delta"]["explanation"] = (
            "key_share grows by exactly 1184 B (1216-B X25519MLKEM768 share vs 32-B X25519 share), but the "
            "X25519MLKEM768-only ClientHello omits the 8-byte ec_point_formats extension, which OpenSSL sends only "
            "when an elliptic-curve group is offered; supported_groups has one entry in both. Checked by capturing "
            "the ClientHello of the same OpenSSL 3.5.6 s_client: 219 B (-groups x25519) and 1395 B "
            "(-groups X25519MLKEM768)")
    for k, v in sanity.items():
        if v["ok"] is False:
            warn.append(f"sanity {k}: measured {v['measured']} B, expected {v['expected']} B")
    info = bench.get("info", {}) or {}
    ver = (info.get("openssl") or "").strip().splitlines()
    S = {"source": source,
         "openssl_version": ver[0] if ver else None,
         "platform": info.get("platform"), "cpu": info.get("cpu"),
         "n_reps": {"kem": reps.get("kem_raw", 0), "sig": reps.get("sig_raw", 0),
                    "other_raw": {k: v for k, v in reps.items() if k not in ("kem_raw", "sig_raw") and v},
                    "s_time": {"classical": cls["s_time_reps"], "hybrid": hyb["s_time_reps"]}},
         "units": "milliseconds per operation (median over repetitions, from the ops/s column of openssl speed); "
                  "bytes = TLS handshake-message bytes incl. 4-byte handshake headers, excl. record-layer overhead "
                  "and post-handshake NewSessionTicket",
         "kem_ms": kem_ms, "sig_ms": sig_ms,
         "kem_ms_range": kem_rng, "sig_ms_range": sig_rng, "kem_detail": kem_det, "sig_detail": sig_det,
         "kex_per_handshake_ms": kex_per_handshake(kem_ms),
         "kem_ms_all": all_medians(agg, ("kem", "kex_classic")),
         "sig_ms_all": all_medians(agg, ("sig", "sig_classic", "rsa_classic")),
         "tls": {"classical": cls, "hybrid": hyb},
         "overhead": {"bytes": ob, "time_ms": ot},
         "L_d_ms": dict(L_D_MS),
         "kappa_max": kap,
         "kappa_max_floor": {s: (int(math.floor(v)) if v is not None else None) for s, v in kap.items()},
         "kappa_max_classical": {s: (L / tc if tc else None) for s, L in L_D_MS.items()},
         "sanity": sanity,
         "notes": ["hs_time_ms = 1000*real_s/conns and client_cpu_ms = 1000/per_user_s are the same quantity: the "
                   "first s_time line reports the client's USER CPU seconds, so both are client CPU per full "
                   "handshake (lower bound of handshake latency; server CPU, kernel time and network excluded)",
                   "s_time has no -groups option: its client offers the OpenSSL 3.5 default key shares "
                   "(X25519MLKEM768 + X25519) against both servers, so the client CPU of BOTH configurations includes "
                   "generating both key shares (checked: the default s_time ClientHello is 1526 B with key shares "
                   "X25519MLKEM768 (1216 B) and x25519 (32 B)); the handshake BYTES come from s_client with a single "
                   "-groups value and are not affected",
                   "s_time prints the elapsed (wall) time in whole seconds (9 s for every run), so wall_ms has a "
                   "resolution of about 1/9 of its value",
                   "X25519 and ECP-256 come from the legacy ECDH table of openssl speed (header 'op op/s'); one op "
                   "is one ECDH shared-secret derivation, converted as ms = 1000 / (op/s) because the printed time is "
                   "rounded to 0.0001 s; a classical ephemeral key exchange needs one key generation plus one "
                   "derivation per side, and the key generations are not timed (see kex_per_handshake_ms)",
                   "openssl speed divides by CPU user time unless -elapsed is given"],
         "warnings": warn}
    if bench.get("FAKE"):
        S["FAKE"] = True
        S["warnings"].insert(0, "FAKE SELF-TEST DATA - NOT A MEASUREMENT")
    return S


# ------------------------------------------------------------------------------------------------------------- figure
def _light(c, f):
    r, g, b = to_rgb(c)
    return (r + (1 - r) * f, g + (1 - g) * f, b + (1 - b) * f)


def _op_style(j, c):
    if j == 0:
        return dict(facecolor=c, edgecolor=c)
    if j == 1:
        return dict(facecolor=_light(c, 0.5), edgecolor=c)
    if j == 3:                                          # ECDH shared-secret derivation (legacy ECDH table)
        return dict(facecolor="white", edgecolor=c, hatch="xxxx")
    return dict(facecolor="white", edgecolor=c, hatch="//////")


def _fmt(v):
    return f"{v:.2f}" if v < 10 else f"{v:.1f}"


def panel_a(ax, S):
    rows, y, yt, yl, bold, vals = [], 0.0, [], [], [], []
    has_derive = False
    for grp, sel, ops, d, det in (("Key establishment", KEM_SEL, KEM_OPS, S["kem_ms"], S["kem_detail"]),
                                  ("Signatures", SIG_SEL, SIG_OPS, S["sig_ms"], S["sig_detail"])):
        items = [(lab, cat) for lab, cat, _ in sel if d.get(lab) and any(v is not None for v in d[lab].values())]
        if not items:
            continue
        if yt:
            ax.axhline(y - 0.5, color="#9a9a9a", lw=0.5, ls=(0, (3, 2)), zorder=1)
            y += 0.25
        yt.append(y); yl.append(grp); bold.append(True); y += 1
        for lab, cat in items:
            c = COL[cat]
            for j, op in enumerate(ops):
                v = d[lab].get(op)
                if v is None:
                    continue
                ax.barh(y + (j - 1) * 0.27, v, 0.25, lw=0.4, zorder=3, **_op_style(j, c))
                vals.append(v)
            v = d[lab].get("derive")
            if v is not None:                           # ECDH derivation: one bar in the middle slot
                ax.barh(y, v, 0.25, lw=0.4, zorder=3, **_op_style(3, c))
                vals.append(v)
                has_derive = True
            yt.append(y); yl.append(lab + (" (ECDH)" if v is not None else "")); bold.append(False); y += 1
    ax.set_yticks(yt)
    ax.set_yticklabels(yl)
    for tl, b in zip(ax.get_yticklabels(), bold):
        if b:
            tl.set_fontweight("bold"); tl.set_fontstyle("italic")
    ax.tick_params(axis="y", length=0)
    ax.set_ylim(y - 0.4, -0.6)                          # inverted: first row on top
    ax.set_xscale("log")
    if vals:
        ax.set_xlim(10 ** math.floor(math.log10(min(vals)) - 0.15), 10 ** math.ceil(math.log10(max(vals)) + 0.05))
    ax.grid(axis="y", visible=False)
    ax.set_axisbelow(True)
    ax.set_xlabel("Time per operation (ms, log scale)")
    ax.set_title("(a) Primitive cost (median of repetitions)", fontsize=8.5, loc="left")
    # legends are drawn below the panels by make_figure (inside the axes they would cover bars at 7.6 pt):
    # one row for the categories (shared with panels b and c), one row for the operations
    cat = {"classical": "Classical (b, c: X25519 + ECDSA P-256)", "pq": "Post-quantum",
           "hybrid": "Hybrid (b, c: X25519MLKEM768 + ML-DSA-65)"}
    hc = [Patch(facecolor=COL[k], edgecolor=COL[k], label=cat[k]) for k in ("classical", "pq", "hybrid")]
    op_lab = ["keygen", "encaps / sign", "decaps / verify"] + (["ECDH derive"] if has_derive else [])
    ho = [Patch(lw=0.4, label=lab, **_op_style(j, "#555555")) for j, lab in enumerate(op_lab)]
    return hc, ho


def panel_b(axb, axt, S):
    cls, hyb = S["tls"]["classical"], S["tls"]["hybrid"]
    var = (("classical", cls, COL["classical"], "Classical\n(X25519 + ECDSA P-256)"),
           ("hybrid", hyb, COL["hybrid"], "Hybrid PQ\n(X25519MLKEM768 + ML-DSA-65)"))
    grp = (("Client\u2192\nserver", "client_bytes"), ("Server\u2192\nclient", "server_bytes"), ("Total", "total_bytes"))
    x, w, top = np.arange(len(grp)), 0.38, 0.0
    for k, (_, t, c, lab) in enumerate(var):
        v = [(t[key] or 0) / 1000.0 for _, key in grp]
        bars = axb.bar(x + (k - 0.5) * w, v, w * 0.94, color=c, label=lab, zorder=3)
        for b, val in zip(bars, v):
            axb.text(b.get_x() + b.get_width() / 2, val, _fmt(val), ha="center", va="bottom", fontsize=7.6)
        top = max(top, max(v))
    axb.set_xticks(x); axb.set_xticklabels([g for g, _ in grp], fontsize=8)
    axb.set_ylim(0, top * 1.12 if top else 1)
    axb.set_ylabel("Handshake messages (kB)")
    axb.grid(axis="x", visible=False); axb.set_axisbelow(True)
    axb.set_title("(b) TLS 1.3 handshake size", fontsize=8.5, loc="left")
    tg = [("Client\nCPU", "client_cpu_ms", "client_cpu_ms_range")]
    if cls.get("wall_ms") is not None and hyb.get("wall_ms") is not None:
        tg.append(("Wall\nclock", "wall_ms", "wall_ms_range"))
    xt, top, wt = np.arange(len(tg)), 0.0, 0.4
    for k, (_, t, c, _) in enumerate(var):
        v = [t[key] or 0.0 for _, key, _ in tg]
        err = np.array([[v[i] - (t[rk] or [v[i]] * 2)[0], (t[rk] or [v[i]] * 2)[1] - v[i]]
                        for i, (_, _, rk) in enumerate(tg)]).T
        bars = axt.bar(xt + (k - 0.5) * wt, v, wt * 0.92, color=c, yerr=err, capsize=1.5,
                       error_kw={"lw": 0.6, "zorder": 4}, zorder=3)
        for b, val, e in zip(bars, v, err[1]):
            axt.text(b.get_x() + b.get_width() / 2, val + e + 0.08, _fmt(val), ha="center", va="bottom",
                     fontsize=7.6)
        top = max(top, max(np.array(v) + err[1]))
    axt.set_xticks(xt); axt.set_xticklabels([g for g, _, _ in tg], fontsize=8)
    axt.set_xlim(-0.55, len(tg) - 0.45)
    axt.set_ylim(0, top * 1.22 if top else 1)
    axt.set_ylabel("ms per full handshake")
    axt.set_title("(c) Time per handshake", fontsize=8.5, loc="left")
    axt.grid(axis="x", visible=False); axt.set_axisbelow(True)


def save(fig, figdir, name):
    os.makedirs(figdir, exist_ok=True)
    paths = []
    for ext, kw in ((".png", {}), (".tif", {"pil_kwargs": {"compression": "tiff_lzw"}})):
        p = os.path.join(figdir, name + ext)
        fig.savefig(p, dpi=400, bbox_inches="tight", facecolor="white", **kw)
        paths.append(p)
    plt.close(fig)
    return paths


def make_figure(S, figdir, name=FIGNAME):
    fig = plt.figure(figsize=(6.5, 3.7))
    gs = fig.add_gridspec(1, 3, width_ratios=[1.35, 1.12, 0.86], wspace=0.47, left=0.165, right=0.985, bottom=0.255,
                          top=0.92)
    hc, ho = panel_a(fig.add_subplot(gs[0]), S)
    panel_b(fig.add_subplot(gs[1]), fig.add_subplot(gs[2]), S)
    kw = dict(loc="lower center", frameon=False, fontsize=7.6, handlelength=1.3, handleheight=0.9, columnspacing=1.6)
    fig.legend(handles=hc, ncol=3, bbox_to_anchor=(0.5, 0.045), **kw)
    fig.legend(handles=ho, ncol=4, bbox_to_anchor=(0.5, -0.005), **kw)
    if S.get("FAKE"):
        fig.text(0.5, 0.5, "FAKE SELF-TEST DATA", fontsize=30, color="red", alpha=0.25, ha="center", va="center",
                 rotation=18, zorder=10)
    return save(fig, figdir, name)


# -------------------------------------------------------------------------------------------------------------- print
def _g(v, nd=4):
    return "-" if v is None else f"{v:.{nd}g}"


def print_table(S):
    print(f"OpenSSL: {S['openssl_version']} | reps: kem={S['n_reps']['kem']} sig={S['n_reps']['sig']} "
          f"s_time={S['n_reps']['s_time']}")
    for title, d, ops in (("KEM (ms)", S["kem_ms"], KEM_OPS + ("derive",)), ("Signature (ms)", S["sig_ms"], SIG_OPS)):
        print(f"\n{title:<16}" + "".join(f"{o:>11}" for o in ops))
        for lab, v in d.items():
            print(f"{lab:<16}" + "".join(f"{_g(v.get(o) if v else None):>11}" for o in ops))
    print("\nkey establishment per handshake (both sides): " + "; ".join(
        f"{k} {_g(v['ms'])} ms{'' if v['complete'] else ' (lower bound)'}"
        for k, v in S.get("kex_per_handshake_ms", {}).items()))
    c, h = S["tls"]["classical"], S["tls"]["hybrid"]
    print(f"\n{'TLS 1.3':<26}{'classical':>12}{'hybrid':>12}{'delta':>12}")
    for k in ("client_bytes", "server_bytes", "total_bytes", "cert_der_bytes_from_msg", "cert_pem_file_bytes",
              "hs_time_ms", "client_cpu_ms", "wall_ms"):
        a, b = c.get(k), h.get(k)
        print(f"{k:<26}{_g(a, 6):>12}{_g(b, 6):>12}{_g(_d(b, a), 6):>12}")
    print("\nkappa_max = L_d / t_hs(hybrid): " + ", ".join(
        f"{s} (L_d={S['L_d_ms'][s]:g} ms) {_g(v)}" for s, v in S["kappa_max"].items()))
    print("sanity: " + ", ".join(f"{k}={v['measured']} (exp {v['expected']})" for k, v in S["sanity"].items()))
    for w in S["warnings"]:
        print("WARNING:", w)


def run(bench_path, summary_path, figdir, extra=(), figname=FIGNAME):
    bench = json.load(open(bench_path, encoding="utf-8"))
    extra_texts = [open(p, encoding="utf-8", errors="replace").read() for p in extra]
    S = summarize(bench, extra_texts, source=os.path.abspath(bench_path))
    os.makedirs(os.path.dirname(os.path.abspath(summary_path)), exist_ok=True)
    json.dump(S, open(summary_path, "w", encoding="utf-8"), indent=1)
    figs = make_figure(S, figdir, figname)
    print_table(S)
    print(f"\nsummary -> {summary_path}\nfigure  -> {', '.join(figs)}")
    return S, figs


# ----------------------------------------------------------------------------------------------------------- selftest
SAMPLE_KEM_LINE = "                 ML-KEM-768 0.000160s 0.000086s 0.000147s    6258.9   11672.9    6814.3"


def _fake_bench():
    """FAKE pqc_bench.json-like dict. Only the ML-KEM-768 rates come from the sample line; all else is invented."""
    jit = [1.00, 0.97, 1.03, 0.95, 1.02]                 # odd count -> the median repetition is exactly the base
    kem = {"X25519": (32000.0, 14500.0, 29000.0), "ECP-256": (40000.0, 9000.0, 14000.0),
           "ML-KEM-512": (9500.0, 17500.0, 10500.0), "ML-KEM-768": (6258.9, 11672.9, 6814.3),
           "ML-KEM-1024": (4100.0, 7900.0, 4600.0), "X25519MLKEM768": (4900.0, 6200.0, 4700.0),
           "SecP256r1MLKEM768": (5200.0, 4800.0, 4300.0), "rsa2048": (8.0, 10000.0, 700.0)}
    sig = {"rsa2048": (7.0, 650.0, 14500.0), "ML-DSA-44": (3000.0, 1000.0, 3100.0),
           "ML-DSA-65": (1800.0, 640.0, 1900.0), "ML-DSA-87": (1150.0, 520.0, 1050.0),
           "SLH-DSA-SHA2-128s": (30.0, 1.2, 1400.0)}
    pre = ("version: 3.5.6\nbuilt on: FAKE\noptions: bn(64,64)\ncompiler: gcc -O3 -DOPENSSLBIN=\"\\\"/x\\\"\"\n"
           "CPUINFO: OPENSSL_ia32cap=0x0:0x0\n")

    def table(hdr, algs, js, verb):
        s, err = pre + " " * 31 + hdr + "\n", ""
        for a, rates in algs.items():
            r = [round(x * js, 1) for x in rates]
            s += "%27s %8.6fs %8.6fs %8.6fs %9.1f %9.1f %9.1f\n" % (a, *[1 / x for x in r], *r)
            err += "".join(f"Doing {a} {o} ops for 3s: {int(x * 3)} {a} {verb} {o} ops in 2.99s\n"
                           for o, x in zip(("keygen", "encaps", "decaps"), r))
        return s + err

    kem_raw = [table("keygen    encaps    decaps keygens/s  encaps/s  decaps/s", kem, j, "KEM") for j in jit]
    sig_raw = [table("keygen     signs    verify keygens/s    sign/s  verify/s", sig, j, "signature")
               for j in jit[:3]]
    kem_raw[2] += "                 FAKE-BROKEN infs infs infs       0.0       0.0       0.0\n"   # failed alg
    cls_raw = []
    for j in jit[:3]:
        s = (" " * 19 + "sign    verify    encrypt   decrypt   sign/s verify/s  encr./s  decr./s\n"
             "rsa  2048 bits %8.6fs %8.6fs %8.6fs %8.6fs %8.1f %8.1f %8.1f %8.1f\n" % (
                 1 / (690 * j), 1 / (13000 * j), 1 / (12000 * j), 1 / (600 * j), 690 * j, 13000 * j, 12000 * j, 600 * j))
        s += " " * 30 + "sign    verify    sign/s verify/s\n" + " 256 bits ecdsa (nistp256) %8.4fs %8.4fs %8.1f %8.1f\n" % (
            1 / (30000 * j), 1 / (11000 * j), 30000 * j, 11000 * j)
        s += " " * 30 + "sign    verify    sign/s verify/s\n" + " 253 bits EdDSA (Ed25519) %8.4fs %8.4fs %8.1f %8.1f\n" % (
            1 / (22000 * j), 1 / (8000 * j), 22000 * j, 8000 * j)
        cls_raw.append(s + "Doing 253 bits sign Ed25519 ops for 2s: 44000 253 bits Ed25519 sign ops in 2.00s\n")

    def hs(msgs):
        return {"client_bytes": sum(n for d, _, n in msgs if d == ">>>"),
                "server_bytes": sum(n for d, _, n in msgs if d == "<<<"), "messages": [list(m) for m in msgs]}
    m_cls = [(">>>", "ClientHello", 242), ("<<<", "ServerHello", 90), ("<<<", "EncryptedExtensions", 10),
             ("<<<", "Certificate", 453), ("<<<", "CertificateVerify", 79), ("<<<", "Finished", 52),
             (">>>", "Finished", 52), ("<<<", "NewSessionTicket", 186), ("<<<", "NewSessionTicket", 186)]
    m_hyb = [(">>>", "ClientHello", 242 + 1184), ("<<<", "ServerHello", 90 + 1088), ("<<<", "EncryptedExtensions", 10),
             ("<<<", "Certificate", 5531), ("<<<", "CertificateVerify", 3317), ("<<<", "Finished", 52),
             (">>>", "Finished", 52), ("<<<", "NewSessionTicket", 186), ("<<<", "NewSessionTicket", 186)]
    st = lambda rows: [{"conns": c, "real_s": r, "per_user_s": round(c / r, 2)} for c, r in rows]
    tls = [{"tag": "classical", "group": "x25519", "cert": "EC", "handshake": hs(m_cls),
            "s_time": st([(2210, 3.05), (2180, 3.11), (2250, 3.02)]), "cert_bytes": 652},
           {"tag": "hybrid_pq", "group": "X25519MLKEM768", "cert": "ML-DSA-65", "handshake": hs(m_hyb),
            "s_time": st([(1650, 3.20), (1610, 3.25), (1680, 3.18)]), "cert_bytes": 7612}]
    return {"FAKE": True,
            "info": {"openssl": "FAKE SELF-TEST DATA - NOT A MEASUREMENT (OpenSSL 3.5.6 output format)\n",
                     "platform": "FAKE", "cpu": "FAKE", "python": sys.version},
            "kem_raw": kem_raw, "sig_raw": sig_raw, "kem": [], "sig": [], "tls": tls}, cls_raw


def selftest(outdir=None):
    outdir = os.path.abspath(outdir or tempfile.mkdtemp(prefix="pqc_selftest_"))
    forbidden = {os.path.normcase(os.path.dirname(os.path.abspath(SUMMARY))), os.path.normcase(os.path.abspath(FIG))}
    assert os.path.normcase(outdir) not in forbidden, f"self-test must not write into {sorted(forbidden)}"
    os.makedirs(outdir, exist_ok=True)
    print(f"[selftest] FAKE data, output directory: {outdir}")
    # 1) parser unit checks on awkward lines
    r = parse_speed_text(SAMPLE_KEM_LINE, "kem")
    assert r and r[0]["name"] == "ML-KEM-768" and abs(r[0]["ms"]["encaps"] - 1000 / 11672.9) < 1e-12, r
    r = parse_speed_text(" " * 30 + "sign    verify    sign/s verify/s\n"
                         " 256 bits ecdsa (nistp256)   0.0000s   0.0001s  31234.5  11000.0\n")
    assert r[0]["kind"] == "sig_classic" and r[0]["name"] == "256 bits ecdsa (nistp256)", r
    assert abs(r[0]["ms"]["sign"] - 1000 / 31234.5) < 1e-12, r          # rate column used, not the 0.0000s time
    r = parse_speed_text("  SLH-DSA-SHA2-128s 0.031000s 0.800000s 0.000700s      32.3       1.2    1428.6\n", "sig")
    assert r[0]["name"] == "SLH-DSA-SHA2-128s" and r[0]["kind"] == "sig", r
    assert parse_speed_text("Doing ML-DSA-44 keygen ops for 1s: 1606 ML-DSA-44 signature keygen ops in 0.63s\n"
                            "version: 3.5.6\n") == []
    r = parse_speed_text("  BROKEN infs infs infs 0.0 0.0 0.0\n", "kem")
    assert r[0]["ms"] == {"keygen": None, "encaps": None, "decaps": None}, r
    # legacy ECDH table (openssl speed ecdhx25519 ecdhp256): rounded time column, value from op/s
    ecdh = (" " * 30 + "op      op/s\n 253 bits ecdh (X25519)   0.0001s  12589.5\n"
            + " " * 30 + "op      op/s\n 256 bits ecdh (nistp256)   0.0001s   9209.8\n")
    r = parse_speed_text(ecdh, "kem")
    assert [x["kind"] for x in r] == ["kex_classic"] * 2 and r[0]["name"] == "253 bits ecdh (X25519)", r
    assert abs(r[0]["ms"]["op"] - 1000 / 12589.5) < 1e-12 and abs(r[1]["ms"]["op"] - 1000 / 9209.8) < 1e-12, r
    agg = {("kex_classic", x["name"]): {"op": [x["ms"]["op"] * f for f in (0.98, 1.0, 1.03)]} for x in r}
    w = []
    med, _, det = select(agg, KEM_SEL[:2], KEM_OPS, w)
    assert not w and abs(med["X25519"]["derive"] - 1000 / 12589.5) < 1e-12, (w, med)
    assert abs(med["ECP-256"]["derive"] - 1000 / 9209.8) < 1e-12 and med["X25519"]["keygen"] is None
    assert det["X25519"]["table"] == "kex_classic"
    kx = kex_per_handshake(med)
    assert not kx["X25519"]["complete"] and abs(kx["X25519"]["ms"] - 2000 / 12589.5) < 1e-12
    print("[selftest] parser unit checks passed")
    # 2) full pipeline, with the classic Ed25519/ECDSA tables supplied as an extra raw source
    bench, cls_raw = _fake_bench()
    bp = os.path.join(outdir, "pqc_bench_FAKE.json")
    json.dump(bench, open(bp, "w"), indent=1)
    cp = os.path.join(outdir, "speed_classic_FAKE.txt")
    open(cp, "w").write("\n".join(cls_raw))
    S, figs = run(bp, os.path.join(outdir, "pqc_summary_FAKE.json"), outdir, extra=[cp], figname=FIGNAME + "_FAKE")
    assert S["FAKE"] and S["n_reps"]["kem"] == 5 and S["n_reps"]["sig"] == 3
    assert all(S["kem_ms"][k] for k, _, _ in KEM_SEL) and all(S["sig_ms"][k] for k, _, _ in SIG_SEL)
    assert abs(S["kem_ms"]["ML-KEM-768"]["encaps"] - 1000 / 11672.9) < 1e-9          # median repetition
    assert abs(S["kem_ms"]["ML-KEM-768"]["keygen"] - 1000 / 6258.9) < 1e-9
    assert S["sig_detail"]["RSA-2048"]["table"] == "sig" and abs(S["sig_ms"]["RSA-2048"]["keygen"] - 1000 / 7) < 1e-9
    assert S["sig_detail"]["Ed25519"]["table"] == "sig_classic" and S["sig_ms"]["Ed25519"]["keygen"] is None
    assert abs(S["sig_ms"]["Ed25519"]["sign"] - 1000 / 22000) < 1e-9
    assert abs(S["sig_ms"]["ECDSA P-256"]["verify"] - 1000 / 11000) < 1e-9
    assert "SLH-DSA-SHA2-128s" in S["sig_ms_all"] and "SecP256r1MLKEM768" in S["kem_ms_all"]
    c, h = S["tls"]["classical"], S["tls"]["hybrid"]
    assert c["client_bytes"] == 242 + 52 and c["server_bytes"] == 90 + 10 + 453 + 79 + 52     # NST excluded
    assert c["server_bytes_incl_post_hs"] == c["server_bytes"] + 2 * 186
    assert h["total_bytes"] - c["total_bytes"] == S["overhead"]["bytes"]["total_bytes"] == 1184 + 1088 + 5078 + 3238
    assert h["cert_der_bytes_from_msg"] == 5531 - 13
    assert all(v["ok"] for v in S["sanity"].values()), S["sanity"]
    med = statistics.median([1000 * 3.20 / 1650, 1000 * 3.25 / 1610, 1000 * 3.18 / 1680])
    assert abs(h["hs_time_ms"] - med) < 1e-12 and abs(h["client_cpu_ms"] - med) < 1e-3   # same quantity (rounding)
    assert abs(S["kappa_max"]["transport"] - 10 / med) < 1e-9 and abs(S["kappa_max"]["health"] - 100 / med) < 1e-9
    from PIL import Image
    for p in figs:
        assert os.path.getsize(p) > 10000, p
    im = Image.open(figs[1])
    assert im.info.get("compression") == "tiff_lzw" and round(im.info["dpi"][0]) == 400, im.info
    print("[selftest] full pipeline checks passed (with classic Ed25519/ECDSA tables)")
    # 3) the expected real situation: no Ed25519/ECDSA rows (not part of -signature-algorithms), must still work
    S2, _ = run(bp, os.path.join(outdir, "pqc_summary_FAKE_noclassic.json"), outdir, figname=FIGNAME + "_FAKE_noclassic")
    assert S2["sig_ms"]["Ed25519"] is None and S2["sig_ms"]["ECDSA P-256"] is None and S2["sig_ms"]["ML-DSA-65"]
    assert any("--extra-raw" in w for w in S2["warnings"])
    print("[selftest] missing Ed25519/ECDSA handled (warning issued, figure produced)")
    print(f"[selftest] ALL PASSED - outputs (FAKE) in {outdir}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--bench", default=BENCH, help="pqc_bench.json produced by pqc_bench.py")
    ap.add_argument("--extra-raw", action="append", default=[],
                    help="text file with extra `openssl speed` output (e.g. ed25519 ecdsap256); repeatable")
    ap.add_argument("--summary", default=SUMMARY)
    ap.add_argument("--figdir", default=FIG)
    ap.add_argument("--selftest", action="store_true", help="run on FAKE data in a temporary directory")
    ap.add_argument("--outdir", default=None, help="self-test output directory (default: new temp dir)")
    a = ap.parse_args()
    if a.selftest:
        selftest(a.outdir)
        sys.exit(0)
    if not os.path.exists(a.bench):
        sys.exit(f"{a.bench} not found - run pqc_bench.py first (or `python pqc_analyze.py --selftest`)")
    run(a.bench, a.summary, a.figdir, a.extra_raw)
