# -*- coding: utf-8 -*-
"""Section 6 (Discussion), Section 7 (Conclusions), the abstract, the highlights and the cover-letter claims.

Every result number is read at build time from the result summaries (fl_summary.json, city_summary.json,
stress_summary.json, pqc_summary.json, city_extra_summary.json); design constants come from apq.city. Each qualitative
statement (which policy is ahead, which difference is significant, what the twin did) is guarded by an assertion, so
that a re-run with different outcomes fails loudly instead of producing a wrong sentence."""
import json
import math
import os
import re

from narr_disc import LIMITATIONS

RES = r"E:\A-PQZTO_work\results"
SIG = 0.05                      # Benjamini-Hochberg adjusted p threshold used throughout Section 5
HL_CHARS = 85                   # Elsevier highlight limit, spaces included
ABS_WORDS = 250
NUM_WORD = {2: "two", 3: "three", 4: "four", 5: "five", 6: "six"}
BANNED = ("notably", "crucially", "importantly", "it is worth noting", "delve", "underscore", "pivotal", "landscape",
          "seamless", "paves the way", "pave the way", "in today's world", "not only", "robust", "\u2014")
# names that contain two or more capitals but are not abbreviations needing a definition in the abstract
ABS_NAMES = {"Post-Quantum", "Zero-Trust", "Multi-Krum", "TON_IoT", "CICIoT2023", "Edge-IIoTset"}


# ------------------------------------------------------------------------------------------------ helpers
def _load(S, key, fname):
    v = S.get(key)
    if v is None:
        p = os.path.join(RES, fname)
        v = json.load(open(p)) if os.path.exists(p) else None
    return v


def _v(x):
    """mean of a [mean, lo, hi] triple, or the value itself"""
    return x[0] if isinstance(x, (list, tuple)) else x


def _test(T, **kw):
    for t in T:
        if all(t.get(k) == v for k, v in kw.items()):
            return t
    raise KeyError(kw)


def _p(x, nd=1):
    """a share in [0, 1] as a percentage string without the sign"""
    return f"{100 * x:.{nd}f}"


def _words(text):
    return len(text.split())


def _style(text, where):
    low = text.lower()
    bad = [b for b in BANNED if b in low]
    assert not bad, f"{where}: banned wording {bad}"
    assert "*" not in text, f"{where}: stray markup asterisk"
    assert "({eq:" not in text, f"{where}: equation labels already carry brackets"


def _pqc(P):
    """Hybrid and classical TLS 1.3 handshake figures, or None if the PQC summary is missing or incomplete (another
    script may be rewriting the classical KEM rows; only the TLS rows are used here)."""
    try:
        tl = P["tls"]
        hy, cl = tl["hybrid"], tl["classical"]
        msg = {m["msg"]: m["bytes"] for m in hy["messages"] if m["dir"] == "S->C"}
        ver = re.search(r"OpenSSL (\d+\.\d+)", P.get("openssl_version", ""))
        return dict(hy_ms=float(hy["hs_time_ms"]), cl_ms=float(cl["hs_time_ms"]),
                    hy_kb=hy["total_bytes"] / 1000, cl_kb=cl["total_bytes"] / 1000,
                    sig_share=(msg["Certificate"] + msg["CertificateVerify"]) / hy["total_bytes"],
                    ver=ver.group(1) if ver else None)
    except (KeyError, TypeError, ValueError):
        return None


# ------------------------------------------------------------------------------------------------ facts
def _facts(S):
    """All numbers and guarded qualitative facts used below."""
    from apq import city as CITY                              # design constants (no simulation is run)
    F, C = S["fl"], S["city"]
    Z = _load(S, "stress", "stress_summary.json")
    X = _load(S, "city_extra", "city_extra_summary.json")
    P = _load(S, "pqc", "pqc_summary.json")
    f = {}
    # ---------------------------------------------------------------- federated detection
    E1, E2, E3, T = F["E1"], F["E2"], F["E3"], F["tests"]
    f["n_fl_runs"] = S.get("n_fl_runs", F.get("n_runs"))
    clean = [(ds, a, _test(T, cond=f"E1|{ds}|{a}", metric="macro_f1", vs="fedavg"))
             for ds in ("ton", "cic") for a in ("None", "1.0", "0.1")]
    # mean_diff = trust-aware minus FedAvg; at most one setting may differ significantly, and only downwards
    f["clean_sig"] = [(ds, a, t) for ds, a, t in clean if t["q_bh"] <= SIG]
    assert len(f["clean_sig"]) <= 1 and all(t["mean_diff"] < 0 for _, _, t in f["clean_sig"])
    f["clean_n"] = len(clean)
    f["clean_max"] = max(abs(t["mean_diff"]) for _, _, t in clean)
    assert f["clean_max"] < 0.01, "trust-aware rule no longer within 0.01 macro-F1 of FedAvg on clean data"
    f["q_clean"] = min(t["q_bh"] for _, _, t in clean if t["q_bh"] > SIG)
    sf = lambda E, ds, n, g: E[f"{ds}|sf|{n}|{g}"]["detect_rate"][0]
    f["ta_min"] = min(sf(E2, ds, n, "ta") for ds in ("ton", "cic") for n in (1, 2, 3))
    assert f["ta_min"] > 0.9
    assert max(sf(E2, ds, n, g) for ds in ("ton", "cic") for n in (2, 3) for g in ("fedavg", "fedprox")) < 0.35
    gap = [E2[f"{ds}|{att}|2|mkrum"]["macro_f1"][0] - E2[f"{ds}|{att}|2|ta"]["macro_f1"][0]
           for ds in ("ton", "cic") for att in ("lf", "sf")]
    assert min(gap) > 0, "Multi-Krum (correct bound) is no longer ahead of the trust-aware rule"
    assert max(gap) < 0.02
    f["mk_gap"] = max(gap)
    f["mk3_ton"], f["tm3_ton"] = sf(E3, "ton", 3, "mkrum"), sf(E3, "ton", 3, "trmean")
    f["mk3_cic"], f["tm3_cic"] = sf(E3, "cic", 3, "mkrum"), sf(E3, "cic", 3, "trmean")
    f["ta3_ton"], f["ta3_cic"] = sf(E2, "ton", 3, "ta"), sf(E2, "cic", 3, "ta")
    assert f["mk3_ton"] == 0 and f["tm3_ton"] == 0 and f["tm3_cic"] == 0, "'detected none' no longer true"
    assert 0 < f["mk3_cic"] < 0.5 and f["ta3_ton"] > 0.99 and f["ta3_cic"] > 0.9
    q3 = [_test(T, cond=f"E3|{ds}|sf|3", metric="macro_f1", vs=f"{g}_f1")["q_bh"]
          for ds in ("ton", "cic") for g in ("mkrum", "trmean")]
    assert max(q3) <= SIG
    f["bad3_max"] = max(f["mk3_ton"], f["tm3_ton"], f["mk3_cic"], f["tm3_cic"])
    D = S.get("data") or {}
    f["edge_maj"] = D.get("edge", {}).get("leakage_audit", {}).get("majority_baseline")
    # ---------------------------------------------------------------- city, main comparison
    s, CT, TH = C["summary"], C["tests"], C["theta"]
    g = lambda p, sc, k: _v(s[f"{p}|{sc}"][k])
    ct = lambda sc, vs: _test(CT, scen=sc, vs=vs)
    f["n_dev"] = sum(CITY.N_DEV.values())
    f["n_edge"] = len(CITY.DOMAINS) * CITY.EDGES_PER_DOMAIN
    f["n_slices"] = len(CITY.DOMAINS)
    f["n_seeds"] = ct("worm", "fl_ids")["n"]
    f["ce_a"], f["ce_f"] = g("apqzto", "worm", "ce"), g("fl_ids", "worm", "ce")
    f["q_ce"] = ct("worm", "fl_ids")["q_bh"]
    assert f["q_ce"] > SIG, "worm containment of A-PQZTO and FL-only IDS now differs significantly"
    f["ev_a"], f["ev_f"] = g("apqzto", "evasion", "asr"), g("fl_ids", "evasion", "asr")
    assert ct("evasion", "fl_ids")["q_bh"] > SIG
    f["ttc_a"], f["ttc_f"] = s["apqzto|worm"]["ttc_median"], s["fl_ids|worm"]["ttc_median"]
    assert f["ttc_a"] > f["ttc_f"]
    for sc in ("ddos", "injection"):
        t = ct(sc, "fl_ids")
        assert t["q_bh"] <= SIG and 0 < t["mean_diff"] < 0.005, f"{sc}: A-PQZTO vs FL-only IDS changed"
    f["dd"], f["di"] = ct("ddos", "fl_ids")["mean_diff"], ct("injection", "fl_ids")["mean_diff"]
    f["fb_a"], f["fb_f"] = g("apqzto", "benign", "fb"), g("fl_ids", "benign", "fb")
    f["fb_s"], f["fb_nt"] = g("static_zta", "benign", "fb"), g("apqzto_notrust", "benign", "fb")
    assert f["fb_a"] < f["fb_f"] / 2 and f["fb_a"] < f["fb_s"] and f["fb_nt"] > f["fb_a"]
    f["dz_a"], f["dz_f"] = g("apqzto", "benign", "disr_frac"), g("fl_ids", "benign", "disr_frac")
    assert f["dz_a"] < f["dz_f"]
    f["imp_a"], f["imp_f"] = g("apqzto", "impostor", "asr"), g("fl_ids", "impostor", "asr")
    f["imp_s"], f["imp_nopqc"] = g("static_zta", "impostor", "asr"), g("apqzto_nopqc", "impostor", "asr")
    for vs in ("fl_ids", "static_zta", "apqzto_nopqc"):
        t = ct("impostor", vs)
        assert t["q_bh"] <= SIG and t["mean_diff"] < 0
    scen = ("benign", "worm", "ddos", "evasion", "injection", "impostor")
    assert all(g("apqzto", sc, "hndl") == 0 for sc in scen), "a sensitive session used classical keys"
    red = [1 - g("apqzto", sc, "pq_hs") / g("zta_fixedpqc", sc, "pq_hs") for sc in scen]
    assert max(red) - min(red) < 0.02
    f["red"] = sum(red) / len(red)
    f["cls"] = sum(g("apqzto", sc, "hndl_all") for sc in scen) / len(scen)
    n_transport = CITY.N_DEV["transport"] / f["n_dev"]
    assert abs(f["cls"] - n_transport) < 0.01 and set(CITY.DOMAINS) - CITY.SENSITIVE == {"transport"}
    # risk-triggered re-authentication: a verified identity is kept for the episode, so at most one per
    # transportation device; 'almost every' requires at least 95% of them in the benign hour
    f["n_tr"] = CITY.N_DEV["transport"]
    f["reauth"] = g("apqzto", "benign", "pq_reauth")
    assert 0.95 * f["n_tr"] <= f["reauth"] <= f["n_tr"], "re-authentication coverage changed: revise 6.2"
    # false blocking at the calibrated operating points on the VALIDATION episodes (calibration grid of Section 4.4)
    cal = json.load(open(os.path.join(RES, "city", "calib_table_v3.json")))
    vfb = lambda p: next(x[0] for k, x in cal[p].items() if abs(float(k) - TH[p]) < 1e-9)
    f["vfb_a"], f["vfb_f"] = vfb("apqzto"), vfb("fl_ids")
    assert abs(f["vfb_f"] - f["vfb_a"]) < 0.5 * (f["fb_f"] - f["fb_a"]) and f["vfb_a"] > f["fb_a"], \
        "false-blocking gap is no longer mainly a validation-to-test shift: revise 6.1"
    f["vfb_nt"] = vfb("apqzto_notrust")
    v3 = (f["vfb_a"], f["vfb_f"], f["vfb_nt"])
    assert max(v3) - min(v3) < 0.5 * (f["fb_f"] - f["fb_a"]), "'the three were close on validation': revise 6.2"
    # twin isolations in the nominal test scenarios: none in the worm, a few during flooding only
    iso = {sc: g("apqzto", sc, "iso") for sc in scen}
    assert iso["worm"] == 0 and iso["ddos"] > 0 and all(iso[sc] == 0 for sc in scen if sc != "ddos")
    assert iso["ddos"] * f["n_seeds"] <= 5, "'very few isolations' no longer true (Section 6.3)"
    # ---------------------------------------------------------------- city, ablations
    f["ce_nofl"] = g("apqzto_nofl", "worm", "ce")
    assert ct("worm", "apqzto_nofl")["q_bh"] <= SIG and f["ce_nofl"] < f["ce_a"]
    f["ev_nodt"] = g("apqzto_nodt", "evasion", "asr")
    assert ct("evasion", "apqzto_nodt")["q_bh"] <= SIG and f["ev_nodt"] > f["ev_a"]
    f["th_a"], f["th_nodt"] = TH["apqzto"], TH["apqzto_nodt"]
    assert f["th_nodt"] < f["th_a"], "static isolation rule no longer forces a less sensitive operating point"
    assert g("apqzto_nodt", "benign", "iso") > 0 and g("apqzto", "benign", "iso") == 0
    f["ever_a"], f["ever_tr"] = g("apqzto", "worm", "ever"), g("apqzto_twinrisk", "worm", "ever")
    f["cont_tr"], f["ev_tr"] = g("apqzto_twinrisk", "worm", "contained"), g("apqzto_twinrisk", "evasion", "asr")
    assert ct("worm", "apqzto_twinrisk")["q_bh"] <= SIG and ct("evasion", "apqzto_twinrisk")["q_bh"] <= SIG
    assert f["ever_tr"] > 2 * f["ever_a"] and f["cont_tr"] < 1 and g("apqzto", "worm", "contained") == 1
    assert all(t["q_bh"] > SIG for t in CT if t["vs"] == "apqzto_nobeh"), "behavioural term now matters"
    # ---------------------------------------------------------------- stress tests
    st, pq, sc_cells = Z["stress"], Z["pqcost"], Z["scal"]["cells"]
    Pz = st["policies"]
    TZ = {t["vs"]: t for t in st["tests_policies"]}
    f["fast_ratio"] = CITY.SCEN["worm_fast"]["beta"] / CITY.BETA_PRIOR
    f["e_a"], f["e_f"], f["e_nt"] = (_v(Pz[p]["ever"]) for p in ("apqzto", "fl_ids", "apqzto_notrust"))
    f["e_s"], f["e_dt"] = _v(Pz["static_zta"]["ever"]), _v(Pz["dt_ids_nofl"]["ever"])
    t = TZ["fl_ids"]
    assert t["q_bh"] > SIG and t["better"] <= t["n"] // 2 and f["e_a"] > f["e_f"]
    assert TZ["apqzto_notrust"]["q_bh"] > SIG and abs(f["e_nt"] - f["e_f"]) < 3
    assert all(Pz[p]["contained"] == 1.0 for p in ("apqzto", "fl_ids", "apqzto_notrust"))
    f["fast_better"], f["fast_n"], f["fast_q"] = t["better"], t["n"], t["q_bh"]
    tw = st["tests_twin"]
    assert all(x["q_bh"] > SIG for x in tw if "fl_ids" not in x["contrast"]), "twin fidelity effect now significant"
    assert X["twin"]["iso_per_h_mean_max"] == 0.0, "the twin approved an isolation in the nominal worm"
    cells = st["twin_cells"]
    evs = [_v(c["ever"]) for c in cells.values()]
    assert (max(evs) - min(evs)) / max(evs) < 0.2                      # "only slightly"
    C2 = pq["cells"]
    dfs = sorted({v["dev_factor"] for v in C2.values()})
    imp = {d: C2[f"{d}|impostor"] for d in dfs}
    fit = [d for d in dfs if "transport" in imp[d]["slices_fitting"]]
    nofit = [d for d in dfs if "transport" not in imp[d]["slices_fitting"]]
    f["a0"], f["a1"] = _v(imp[fit[0]]["asr"]), _v(imp[nofit[0]]["asr"])
    f["t0"], f["t1"] = _v(imp[fit[0]]["asr_transport"]), _v(imp[nofit[0]]["asr_transport"])
    assert all(abs(_v(imp[d]["asr"]) - f["a0"]) < 1e-9 for d in fit)
    assert all(abs(_v(imp[d]["asr"]) - f["a1"]) < 1e-9 for d in nofit)
    assert f["a0"] < f["a1"] < f["imp_f"]
    ev_asr = [_v(C2[f"{d}|evasion"]["asr"]) for d in dfs]
    fbs = [_v(C2[f"{d}|benign"]["fb"]) for d in dfs]
    assert max(ev_asr) - min(ev_asr) < 1e-9 and max(fbs) - min(fbs) < 1e-9
    f["pq_ms"] = pq["pq_ms"]
    f["L_tr"] = CITY.SLICE_BUDGET_MS["transport"]
    assert fit[-1] * f["pq_ms"] <= f["L_tr"] < nofit[0] * f["pq_ms"]
    dm = lambda p, n: sc_cells[f"{p}|n_dev={n}"]["dec_ms_mean"]
    ns = sorted({v["n_dev"] for v in sc_cells.values()})
    f["n0"], f["n1"] = ns[0], ns[-1]
    f["d0"], f["d1"] = dm("apqzto", ns[0]), dm("apqzto", ns[-1])
    f["d1_nodt"] = dm("apqzto_nodt", ns[-1])
    assert f["d1"] / f["d0"] > 4 * ns[-1] / ns[0] and f["d1_nodt"] < 1.0       # super-linear; < 1 ms without twin
    f["d1_share"] = f["d1"] / Z["scal"]["decision_interval_ms"]
    assert f["d1_share"] < 0.01
    # ---------------------------------------------------------------- PQC microbenchmarks
    f["pqc"] = _pqc(P)
    if f["pqc"]:
        q = f["pqc"]
        assert q["hy_ms"] / q["cl_ms"] < 1.5, "hybrid handshake no longer cheap in CPU time"
        assert q["hy_kb"] / q["cl_kb"] > 5 and q["sig_share"] > 0.5
        assert abs(q["hy_ms"] - f["pq_ms"]) / f["pq_ms"] < 0.25, "measured handshake far from simulator assumption"
    return f


# ------------------------------------------------------------------------------------------------ text
def build(S):
    f = _facts(S)
    q = f["pqc"]
    fast = NUM_WORD.get(round(f["fast_ratio"]), f"{f['fast_ratio']:.0f}")
    lim = f"{math.ceil(100 * f['clean_max']) / 100:.2f}"            # largest clean-data gap, rounded up
    out = {}
    DS = {"ton": "TON_IoT", "cic": "CICIoT2023"}
    AL = {"None": "IID clients", "1.0": "$\\alpha$ = 1.0", "0.1": "$\\alpha$ = 0.1"}
    if f["clean_sig"]:
        ds, a, t = f["clean_sig"][0]
        clean_txt = (f"stayed within {lim} of FedAvg in macro-F1, a gap that was significant only on {DS[ds]} with "
                     f"{AL[a]} (adjusted p = {t['q_bh']:.2f})")
    else:
        clean_txt = f"did not differ significantly from FedAvg (adjusted p ≥ {f['q_clean']:.2f})"

    # ================================================================ 6.1
    d61 = [
        f"The federated results support a narrow claim. On clean data the trust-aware rule {clean_txt}. Under "
        f"model poisoning with $\\alpha$ = 1.0 it detected at least {_p(f['ta_min'])}% of attacks, whereas FedAvg "
        "and FedProx collapsed once two or more clients were malicious. Multi-Krum with the correct Byzantine bound "
        "was slightly stronger. The trust-aware rule earns its place when that bound, which Krum-type rules and "
        "the trimmed mean need [@blanchard2017krum; @yin2018median], is wrong: with three poisoning clients and a "
        "bound of one, Multi-Krum and the trimmed mean detected none of the TON_IoT attacks, while the trust-aware "
        f"rule detected {_p(f['ta3_ton'])}% ({_p(f['ta3_cic'])}% on CICIoT2023). Since an operator rarely knows "
        "how many edge nodes are compromised, a rule without this parameter is the safer default, as long as "
        "honest clients remain the majority that its median reference assumes.",

        "In the city, the informative comparison is with FL-only IDS, which uses a federated detector without the "
        "rest of the loop. At equal calibrated budgets the two contained the nominal "
        f"worm equally well (containment efficiency {f['ce_a']:.4f} against {f['ce_f']:.4f}, adjusted p = "
        f"{f['q_ce']:.2f}) and allowed similar credential-misuse success. A-PQZTO blocked benign devices less often "
        f"on the test seeds ({_p(f['fb_a'], 2)}% of device-steps against {_p(f['fb_f'], 2)}%) but not on the "
        f"validation episodes ({_p(f['vfb_a'], 2)}% and {_p(f['vfb_f'], 2)}%), so this gap is mostly a shift between "
        "validation and test, not a designed property. The clearest gain was against impostors "
        f"({_p(f['imp_a'])}% success against {_p(f['imp_f'])}%, and {_p(f['imp_s'])}% for Static ZTA), and it rests "
        "on the impostor assumption of Section 3.2.",

        "The ablations (Section 5.5) help to explain these outcomes. Removing post-quantum authentication "
        f"raised impostor success to {_p(f['imp_nopqc'])}%, and local detectors lowered containment efficiency to "
        f"{f['ce_nofl']:.4f}. A static isolation rule in place of the twin isolated clusters in benign episodes, used "
        "up disruption budget and forced a less sensitive operating point, so credential-misuse success rose to "
        f"{_p(f['ev_nodt'])}%. The original design, with the twin's propagation risk inside the trust score, left "
        f"{f['ever_tr']:.0f} devices infected on average instead of {f['ever_a']:.0f} and contained only "
        f"{_p(f['cont_tr'], 0)}% of worm episodes. This agrees with the validation-only comparison (Section 4.4) on "
        "which the final design, with the twin outside the score and the zero-trust veto, was chosen.",
    ]

    # ================================================================ 6.2
    pq_txt = (
        "Post-quantum protection is cheap in processor time and expensive in bytes: the hybrid handshake took "
        f"{q['hy_ms']:.1f} ms of client CPU time against {q['cl_ms']:.1f} ms for the classical one, but "
        f"{q['hy_kb']:.1f} kB instead of {q['cl_kb']:.1f} kB, mostly for the ML-DSA certificate and signature. On "
        "low-rate radio links, where post-quantum schemes are seldom tested [@almutairi2025], the bytes will set the "
        "cost. "
    ) if q else (
        "Post-quantum protection has a processor cost and a message-size cost, both measured in Section 5.6. ")
    d62 = [
        "The trust score of Eq. {eq:trust} accumulates evidence over several observations, so A-PQZTO reacts later "
        "than FL-only IDS, which acts after two consecutive detector hits. Its median time to contain the nominal "
        f"worm was {f['ttc_a']:.2f} min against {f['ttc_f']:.2f} min, and flooding and data injection were "
        f"{_p(f['dd'])} and {_p(f['di'])} percentage points more successful. A worm {fast} times faster than the "
        f"twin assumes made the cost larger: {f['e_a']:.0f} infected devices on average against {f['e_f']:.0f} for "
        f"FL-only IDS and {f['e_nt']:.0f} for A-PQZTO w/o adaptive trust, with A-PQZTO ahead of FL-only IDS in "
        f"only {f['fast_better']} of {f['fast_n']} seeds (adjusted p = {f['fast_q']:.2f}). The intended return, "
        "fewer wrongly blocked devices, appeared on the test seeds but not on the validation episodes, so the cost of "
        "the smoothing is better established than its benefit.",

        pq_txt + "The risk trigger was also less selective than intended: "
        f"{f['reauth']:.0f} re-authentications per hour for {f['n_tr']} transportation devices mean that almost "
        "every one of them fell below $\\tau_{allow,d}$ within the hour. The "
        f"{_p(f['red'], 0)}% saving against ZTA + fixed PQC therefore comes from keeping transportation sessions "
        f"classical ({_p(f['cls'], 0)}% of all sessions), not from singling out suspicious devices. On devices too "
        f"slow to fit the {f['L_tr']:.0f} ms transportation budget, impostor success rose from {_p(f['a0'])}% to "
        f"{_p(f['a1'])}% ({_p(f['t1'])}% within the transportation slice).",

        "The twin is also the most expensive component to compute: with one worker, decision time per 10-s step grew from "
        f"{f['d0']:.1f} ms at {f['n0']:,} devices to {f['d1']:.0f} ms at {f['n1']:,}, against under 1 ms without "
        "it, because the roll-outs multiply dense matrices.",
    ]

    # ================================================================ 6.4
    d64 = [
        "Policies should be compared at a fixed budget of false blocking and service "
        "disruption, since otherwise the most aggressive policy looks best [@arp2022dosdonts], and their operating "
        "points should be re-checked on fresh data. Where the number of compromised edge nodes cannot be bounded, an "
        "aggregation rule without a Byzantine bound is the safer choice, and a twin belongs in front of costly "
        "actions rather than inside the trust score.",
        "Next steps are handshake measurements on microcontroller-class devices and radio links, a separate "
        "re-authentication threshold that targets suspicious devices, attackers that adapt to the aggregation rule "
        "or the trust score, sparse twin roll-outs, evidence from more datasets and calibration budgets, and a pilot "
        "on an operator testbed.",
    ]
    out["discussion"] = [("6.1 What the evaluation supports", d61),
                         ("6.2 Trade-offs an operator should expect", d62),
                         ("6.3 Limitations", list(LIMITATIONS)),
                         ("6.4 Implications and future work", d64)]

    # ================================================================ conclusions
    pq_c = (f"A measured hybrid handshake cost {q['hy_ms']:.1f} ms of client CPU time but {q['hy_kb']:.1f} kB on "
            "the wire, so bandwidth rather than computation is its main cost on IoT links. ") if q else ""
    edge_c = (" Predicting 'attack' for every remaining Edge-IIoTset flow already reaches "
              f"{_p(f['edge_maj'])}% accuracy, so its machine-learning subset cannot support binary detector "
              "benchmarking once identifiers and the placeholder artefact are removed.") if f["edge_maj"] else (
        " The leakage audit showed that the Edge-IIoTset machine-learning subset cannot support binary detector "
        "benchmarking once identifiers and the placeholder artefact are removed.")
    out["conclusions"] = [
        "This paper presented A-PQZTO, a zero-trust orchestration loop for smart-city IoT in which trust is computed "
        "only from evidence about the device, while post-quantum cost and slice latency decide when stronger "
        "authentication is used. Under its session policy every sensitive-slice session used post-quantum keys, and "
        f"modelled impostor success fell to {_p(f['imp_a'])}%. The risk trigger, however, re-authenticated almost "
        "every transportation device within the hour, so the "
        f"{_p(f['red'], 0)}% saving in handshakes came from keeping transportation sessions classical. " + pq_c +
        f"In {f['n_fl_runs']:,} federated training runs, the trust-aware aggregation rule stayed within {lim} of "
        "FedAvg in macro-F1 on clean data. Under model poisoning by three clients it still detected "
        f"{_p(f['ta3_ton'])}% of the TON_IoT and {_p(f['ta3_cic'])}% of the CICIoT2023 attacks, whereas Multi-Krum "
        "and the trimmed mean, told to expect one attacker, failed; with a correct bound, Multi-Krum remained "
        "slightly better." + edge_c,

        "In the city-scale evaluation, with all policies calibrated on validation episodes to the same false-blocking "
        "and disruption budget, A-PQZTO contained the worm as well as federated detection alone. It blocked benign "
        f"devices less often on the test seeds ({_p(f['fb_a'], 2)}% against {_p(f['fb_f'], 2)}% of the time), though "
        f"not on the validation episodes, and it reacted more slowly, which a worm {fast} times faster than expected "
        f"made visible ({f['e_a']:.0f} against {f['e_f']:.0f} infected devices). The digital twin's measurable "
        "contribution was limited to declining cluster isolations that a static rule would have made, and the "
        "behavioural profile made no measurable difference. Measurements on IoT hardware and a field trial are "
        "needed to show whether these trade-offs hold outside simulation.",
    ]

    # ================================================================ abstract
    pq_a = (" A hybrid post-quantum handshake in Transport Layer Security 1.3 took "
            f"{q['hy_ms']:.1f} ms of client processor time and {q['hy_kb']:.1f} kB on the wire.") if q else ""
    abstract = (
        "Smart-city Internet of Things (IoT) networks need per-device security decisions that weigh service "
        "disruption and resist future quantum attacks. We present the Adaptive Post-Quantum "
        "Zero-Trust Orchestrator (A-PQZTO), which scores device trust from behavioural, authentication and "
        "federated-detection evidence, triggers post-quantum re-authentication only when the handshake fits the "
        "slice latency budget, and lets a digital twin approve cluster isolation. In "
        f"{f['n_fl_runs']:,} federated training runs on TON_IoT and CICIoT2023, the trust-aware aggregation rule "
        f"stayed within {lim} of federated averaging in macro-averaged F1 on clean data. A correctly bounded "
        "Multi-Krum was slightly better, but with three of 12 clients poisoning the model and a bound of one, "
        "Multi-Krum and the trimmed mean detected no TON_IoT attacks; the bound-free rule detected "
        f"{_p(f['ta3_ton'])}%. Edge-IIoTset failed a leakage audit. In a simulated {f['n_dev']:,}-device city driven "
        "by measured detector outputs, with every policy calibrated on validation episodes to one false-blocking and "
        "disruption budget, A-PQZTO matched federated detection alone on worm containment over "
        f"{f['n_seeds']} test seeds, blocked benign devices less often ({_p(f['fb_a'], 2)}% against "
        f"{_p(f['fb_f'], 2)}% of device-steps, a gap absent on validation episodes) and reduced impostor success "
        f"from {_p(f['imp_f'])}% to {_p(f['imp_a'])}%, assuming impostors cannot pass post-quantum verification. "
        "All sensitive-slice sessions used post-quantum keys; keeping transportation sessions classical saved "
        f"{_p(f['red'], 0)}% of handshakes. The price was slower reaction: a worm {fast} times faster than the twin "
        f"assumes infected {f['e_a']:.0f} devices against {f['e_f']:.0f}. The digital twin had little measurable "
        "effect." + pq_a)
    out["abstract"] = abstract

    # ================================================================ highlights
    hl = [
        f"Bound-free aggregation kept {_p(f['ta3_ton'])}% detection where wrongly bounded Multi-Krum failed",
        "At equal calibrated budgets, A-PQZTO matched federated detection on worm containment",
        f"Post-quantum re-authentication cut modelled impostor success from {_p(f['imp_f'])}% to "
        f"{_p(f['imp_a'])}%",
        f"All sensitive sessions post-quantum; classical transport saved {_p(f['red'], 0)}% of handshakes",
        f"Trust smoothing slows reaction: a fast worm infected {f['e_a']:.0f} devices instead of {f['e_f']:.0f}",
    ]
    out["highlights"] = hl

    # ================================================================ cover letter
    out["cover_claims"] = [
        "A trust-aware aggregation rule for federated intrusion detection that needs no bound on the number of "
        f"malicious clients: it stayed within {lim} of FedAvg in macro-F1 on clean TON_IoT and CICIoT2023 data and "
        f"still detected {_p(f['ta3_ton'])}% and {_p(f['ta3_cic'])}% of attacks when three of 12 clients poisoned "
        "the model, a setting in which Multi-Krum and the trimmed mean, configured for one attacker, detected at "
        f"most {_p(f['bad3_max'], 0)}% (with a correct bound, Multi-Krum was slightly better).",
        f"A city-scale evaluation ({f['n_dev']:,} devices driven by real detector outputs, every policy calibrated "
        f"on validation episodes to one false-blocking and disruption budget, {f['n_seeds']} fresh test seeds) in "
        "which A-PQZTO matched federated detection alone on worm containment and cut modelled impostor success from "
        f"{_p(f['imp_f'])}% to {_p(f['imp_a'])}%; ablations and stress tests show that it reacts more slowly to a "
        "fast worm and that its digital twin acts mainly as a gate against harmful cluster isolations.",
        ((f"Measured hybrid post-quantum TLS 1.3 handshakes (X25519MLKEM768 with ML-DSA-65"
          + (f", OpenSSL {q['ver']}" if q['ver'] else "") + f") cost {q['hy_ms']:.1f} ms of client CPU time and "
          f"{q['hy_kb']:.1f} kB on the wire; in the city") if q else "In the city") +
        ", every sensitive-slice session used post-quantum key exchange, and keeping transportation sessions "
        f"classical saved {_p(f['red'], 0)}% of post-quantum handshakes compared with protecting every session.",
    ]

    _check(out)
    return out


# ------------------------------------------------------------------------------------------------ checks
def _check(out):
    disc = [p for _, ps in out["discussion"] for p in ps]
    for i, p in enumerate(disc + out["conclusions"] + [out["abstract"]] + out["highlights"] + out["cover_claims"]):
        _style(p, f"block {i}")
    n_disc, n_conc, n_abs = sum(map(_words, disc)), sum(map(_words, out["conclusions"])), _words(out["abstract"])
    assert 850 <= n_disc <= 1250, f"discussion has {n_disc} words"
    assert 180 <= n_conc <= 320 and 2 <= len(out["conclusions"]) <= 3, f"conclusions have {n_conc} words"
    # abstract: length, no citations, every token with two or more capitals is defined or a dataset/method name
    a = out["abstract"]
    assert n_abs <= ABS_WORDS, f"abstract has {n_abs} words"
    assert "[@" not in a and "{" not in a and "$" not in a
    for tok in set(re.findall(r"[A-Za-z0-9_\-]+", a)):
        if sum(ch.isupper() for ch in tok) >= 2 and tok not in ABS_NAMES:
            assert f"({tok})" in a, f"abstract: undefined abbreviation {tok}"
    # highlights: 3-5 items, at most 85 characters, every number also in the abstract
    hl = out["highlights"]
    assert 3 <= len(hl) <= 5 and len(set(hl)) == len(hl)
    body = a.replace(",", "")
    for h in hl:
        assert len(h) <= HL_CHARS, f"highlight too long ({len(h)}): {h}"
        for num in re.findall(r"\d[\d,]*(?:\.\d+)?", h):
            assert num.replace(",", "") in body, f"highlight number {num} not in the abstract: {h}"
    assert 2 <= len(out["cover_claims"]) <= 3
    for c in out["cover_claims"]:
        assert not any(w in c.lower() for w in ("competing", "conflict", "funding", "ethic")), c


def stats(out):
    """Word and character counts for reports."""
    disc = {h: sum(map(_words, ps)) for h, ps in out["discussion"]}
    return dict(discussion=disc, discussion_total=sum(disc.values()),
                conclusions=sum(map(_words, out["conclusions"])), abstract=_words(out["abstract"]),
                highlight_chars=[len(h) for h in out["highlights"]])
