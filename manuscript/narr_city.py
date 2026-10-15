# -*- coding: utf-8 -*-
"""Sections 5.4 (city-scale orchestration) and 5.5 (ablation). Every number is read at build time from
city_summary.json (S["city"]), from the validation calibration grid and the worm traces written by the same pipeline
run, or from the simulator's own constants. Every qualitative statement (which policy is ahead, which differences are
significant, what the twin did) is guarded by an assertion on the same data, so that a re-run with different outcomes
fails loudly instead of printing a wrong sentence."""
import json
import math
import os

from sections_exp import POL_LAB as L
from sections_results import FIG, pm

_HERE = os.path.dirname(os.path.abspath(__file__))
RES = os.path.normpath(os.path.join(_HERE, "..", "..", "results"))
CALIB_FILE = os.path.join(RES, "city", "calib_table_v3.json")   # validation grid behind S["city"]["theta"]
TRACE_FILE = os.path.join(RES, "city", "trace_v3.jsonl")        # worm traces plotted in Fig. 8(a)
ALPHA = 0.05            # significance level for the adjusted p-values
BUDGET = 0.005          # calibration budget of Section 4.4; used in assertions only, never printed

BASE = ["none", "static_zta", "zta_fixedpqc", "fl_ids", "dt_ids_nofl", "apqzto"]
ABL = ["apqzto", "apqzto_nopqc", "apqzto_nodt", "apqzto_nofl", "apqzto_notrust", "apqzto_nobeh", "apqzto_noveto",
       "apqzto_twinrisk"]
SINGLE = ABL[1:-1]                               # single-component removals (the last variant changes two things)
METRIC = {"worm": "ce", "ddos": "asr", "evasion": "asr", "injection": "asr", "impostor": "asr"}
WORDS = ["no", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten"]


# ------------------------------------------------------------------------------------------------ helpers
def _v(C, p, s, k):
    x = C["summary"][f"{p}|{s}"][k]
    return x[0] if isinstance(x, (list, tuple)) else x


def _ci(C, p, s, k):
    return C["summary"][f"{p}|{s}"][k]


def _t(C, scen, vs):
    for t in C["tests"]:
        if t["scen"] == scen and t["vs"] == vs:
            assert t["metric"] == METRIC[scen]
            return t
    raise KeyError((scen, vs))


def _q(q):
    if q < 0.001:
        return "$q$ < 0.001"
    return f"$q$ = {q:.3f}" if q < 0.1 else f"$q$ = {q:.2f}"


def _q_le(q):
    """Upper bound, rounded up so that the printed inequality is true."""
    if q < 0.001:
        return "$q$ < 0.001"
    d = 3 if q < 0.1 else 2
    return f"$q$ ≤ {math.ceil(round(q * 10 ** d, 9)) / 10 ** d:.{d}f}"


def _q_ge(q):
    """Lower bound, rounded down so that the printed inequality is true."""
    d = 3 if q < 0.1 else 2
    return f"$q$ ≥ {math.floor(round(q * 10 ** d, 9)) / 10 ** d:.{d}f}"


def _pc(x, nd=1):
    return f"{100 * x:.{nd}f}%"


def _sg(x, nd=2):
    return f"{x:.{nd}f}".replace("-", "−")


def _pmp(t, nd=2):
    return pm([100 * x for x in t], nd=nd)


def _w(n):
    return WORDS[n] if 0 <= n < len(WORDS) else f"{n:,}"


def _city_consts():
    from apq.city import N_DEV, SENSITIVE
    n = sum(N_DEV.values())
    n_classical = sum(v for d, v in N_DEV.items() if d not in SENSITIVE)    # transportation slice
    return n, n_classical


def _calib(S):
    if S.get("city_calib") is not None:
        return S["city_calib"]
    with open(CALIB_FILE) as f:
        return json.load(f)


def _cal_at(cal, p, theta):
    for k, x in cal[p].items():
        if abs(float(k) - theta) < 1e-9:
            return x
    raise KeyError((p, theta))


def _trace_seeds():
    seeds = {}
    with open(TRACE_FILE) as f:
        for line in f:
            r = json.loads(line)
            if r["scen"] == "worm":
                seeds.setdefault(r["policy"], set()).add(r["seed"])
    return seeds


def _mark(C, scen, p):
    if p in ("none", "apqzto"):
        return ""
    return "†" if _t(C, scen, p)["q_bh"] <= ALPHA else ""


# ------------------------------------------------------------------------------------------------ 5.4
def _table_sec(m, C, n):
    rows = []
    for p in BASE:
        lab = f"**{L[p]}**" if p == "apqzto" else L[p]
        if p == "none":
            ev = _ci(C, p, "worm", "ever")
            rows.append([lab, "–", f"{ev[0]:,.0f} ± {(ev[2] - ev[1]) / 2:,.0f}", "–"]
                        + [f"{100 * _v(C, p, s, 'asr'):.0f}" for s in ("ddos", "evasion", "injection", "impostor")])
            continue
        r = [lab, pm(_ci(C, p, "worm", "ce"), nd=4) + _mark(C, "worm", p), pm(_ci(C, p, "worm", "ever"), nd=1),
             f"{_v(C, p, 'worm', 'ttc_median'):.2f}"]
        for s in ("ddos", "evasion", "injection", "impostor"):
            r.append(_pmp(_ci(C, p, s, "asr")) + _mark(C, s, p))
        rows.append(r)
    hdr = [["Policy", "Worm", "", "", "Attack-success ratio (%)", "", "", ""],
           ["", "CE", "Devices compromised", "Median TTC (min)", "Flooding", "Credential misuse", "Data injection",
            "Impostor"]]
    m.table(hdr, rows, f"Security outcomes of the city-scale policies on the test episodes (mean ± half-width of the "
            f"95% bootstrap confidence interval over {n} seeds).", col_widths=[1.5, 0.95, 0.85, 0.6, 0.8, 0.85, 0.8, 0.8],
            label="citysec", header_rows=2, align=["left"] + ["center"] * 7,
            notes=f"CE: containment efficiency, Eq. {{eq:ce}}; devices compromised: devices ever compromised in the "
                  f"one-hour episode; TTC: time from the worm's onset until every compromised device was quarantined "
                  f"or blocked (median over episodes); attack-success ratio: Eq. {{eq:asr}}. Every policy except no "
                  f"response contained the worm in all {n} episodes. †: differs from A-PQZTO with $q$ ≤ {ALPHA:.2f} "
                  f"(paired Wilcoxon signed-rank test over seeds, Benjamini–Hochberg adjustment over all "
                  f"{len(C['tests'])} comparisons with A-PQZTO); tests were run for CE and the attack-success ratios.")


def _table_cost(m, C, n, n_dev):
    rows = []
    for p in BASE:
        lab = f"**{L[p]}**" if p == "apqzto" else L[p]
        g = lambda k: _ci(C, p, "benign", k)
        dec = "–" if p == "none" else pm(g("dec_ms"), nd=2)
        rows.append([lab, _pmp(g("fb")), _pmp(g("disr_frac")), f"{100 * g('hndl')[0]:.1f}",
                     f"{100 * g('hndl_all')[0]:.1f}", f"{g('pq_hs')[0]:,.0f}", f"{g('pq_reauth')[0]:,.0f}", dec])
    hdr = ["Policy", "False blocking (%)", "Disruption (%)", "$E_{HNDL}$, sensitive slices (%)",
           "$E_{HNDL}$, all slices (%)", "PQ handshakes per hour", "of which re-authentications",
           "Decision time per step (ms)"]
    m.table(hdr, rows, f"Cost of the city-scale policies in the benign test episodes (mean ± half-width of the 95% "
            f"bootstrap confidence interval over {n} seeds where shown, otherwise mean).",
            col_widths=[1.4, 0.85, 0.85, 0.8, 0.75, 0.85, 0.95, 0.8], label="citycost",
            align=["left"] + ["center"] * 7,
            notes="False blocking: share of benign device-steps spent quarantined or blocked. Disruption: "
                  "criticality-weighted service disruption as a share of the weighted capacity (Section 4.4). "
                  "$E_{HNDL}$ (Eq. {eq:hndl}): share of sessions established without post-quantum key exchange. "
                  f"Decision time: policy computation for all {n_dev:,} devices in one step, Python implementation, "
                  "measured while several runs shared the host.")


def block_main(m, S):
    C = S["city"]
    v = lambda p, s, k: _v(C, p, s, k)
    t = lambda s, p: _t(C, s, p)
    N, N_CL = _city_consts()
    n = t("worm", "fl_ids")["n"]
    assert all(x["n"] == n for x in C["tests"]), "unequal numbers of paired seeds"
    m.heading("5.4 City-scale orchestration", 2)
    m.label_next("tab", "citysec")
    m.label_next("fig", "city")

    # ---------------------------------------------------------------- worm
    ce = {p: v(p, "worm", "ce") for p in BASE}
    ev = {p: v(p, "worm", "ever") for p in BASE}
    ttc = {p: v(p, "worm", "ttc_median") for p in BASE[1:]}
    assert v("none", "worm", "contained") == 0.0
    assert all(v(p, "worm", "contained") == 1.0 for p in BASE[1:]), "a policy missed containment: revise text"
    w_fl, w_dt, w_st = t("worm", "fl_ids"), t("worm", "dt_ids_nofl"), t("worm", "static_zta")
    assert w_fl["q_bh"] > ALPHA and w_fl["mean_diff"] < 0, "A-PQZTO vs FL-only IDS on the worm changed: revise text"
    assert ttc["fl_ids"] < ttc["apqzto"], "FL-only IDS no longer contains the worm sooner: revise text"
    assert w_dt["q_bh"] <= ALPHA and w_dt["mean_diff"] > 0, "A-PQZTO vs DT-assisted IDS changed: revise text"
    assert w_st["mean_diff"] > 0 and w_st["p"] <= ALPHA < w_st["q_bh"], "A-PQZTO vs Static ZTA changed: revise text"
    m.para(f"Table {{tab:citysec}} and Fig. {{fig:city}} compare the policies, each at its validation-calibrated "
           f"operating point, on {n} test seeds per scenario that were used neither for calibration nor for selecting "
           "the design (Section 4.4). Here $q$ is the Benjamini–Hochberg-adjusted p-value of the paired Wilcoxon "
           "test over seeds ('adjusted p' in the other sections). Without a "
           "response, the worm reached a mean of "
           f"{ev['none']:,.0f} of the {N:,} devices; every other policy contained it in all {n} episodes "
           f"(Fig. {{fig:city}}a). A-PQZTO reached a containment efficiency of {ce['apqzto']:.4f} "
           f"({ev['apqzto']:.1f} devices compromised on average), against {ce['fl_ids']:.4f} ({ev['fl_ids']:.1f} "
           f"devices) for {L['fl_ids']}. The difference was not significant ({_q(w_fl['q_bh'])}), and "
           f"{L['fl_ids']} quarantined or blocked every compromised device sooner (median {ttc['fl_ids']:.2f} "
           f"against {ttc['apqzto']:.2f} min after onset). A-PQZTO contained the worm significantly better than "
           f"{L['dt_ids_nofl']} ({ev['dt_ids_nofl']:.1f} devices, {_q(w_dt['q_bh'])}); its advantage over "
           f"{L['static_zta']} ({ev['static_zta']:.1f} devices) did not survive the correction for multiple "
           f"comparisons ({_q(w_st['q_bh'])}).")

    # ---------------------------------------------------------------- non-spreading attacks
    a = {s: {p: v(p, s, "asr") for p in BASE} for s in ("ddos", "evasion", "injection", "impostor")}
    e_fl, i_fl, d_fl = t("evasion", "fl_ids"), t("injection", "fl_ids"), t("ddos", "fl_ids")
    assert e_fl["q_bh"] > ALPHA, "credential misuse: A-PQZTO vs FL-only IDS became significant: revise text"
    for x in (i_fl, d_fl):     # FL-only IDS ahead, significantly, by less than half a percentage point
        assert x["q_bh"] <= ALPHA and 0 < x["mean_diff"] < 0.005, "FL-only IDS no longer slightly better: revise text"
    m.para(f"Among the non-spreading attacks (Fig. {{fig:city}}b), under credential misuse the compromised devices "
           f"kept {_pc(a['evasion']['apqzto'])} of their unhindered "
           f"attack activity under A-PQZTO and {_pc(a['evasion']['fl_ids'])} under {L['fl_ids']} "
           f"({_q(e_fl['q_bh'])}). {L['fl_ids']} was slightly but significantly better against data injection "
           f"({_pc(a['injection']['fl_ids'])} against {_pc(a['injection']['apqzto'])}, {_q(i_fl['q_bh'])}) and "
           f"flooding ({_pc(a['ddos']['fl_ids'])} against {_pc(a['ddos']['apqzto'])}, {_q(d_fl['q_bh'])}), by "
           f"{100 * i_fl['mean_diff']:.1f} and {100 * d_fl['mean_diff']:.1f} percentage points.")

    # ---------------------------------------------------------------- impostor
    imp = {p: t("impostor", p) for p in ("fl_ids", "static_zta")}
    assert all(x["better"] == x["n"] for x in imp.values()), "A-PQZTO no longer lower in every seed: revise text"
    assert a["impostor"]["zta_fixedpqc"] == 0.0 and a["impostor"]["apqzto"] > 0
    # residual access concentrated on the classical (transportation) slice
    assert v("apqzto", "impostor", "asr_transport") > a["impostor"]["apqzto"]
    m.para("The impostor results rest on the assumption of Section 3.2 that a forged classical credential fails "
           "ML-DSA verification, because the impostor does not hold the device's post-quantum key. Under this "
           f"assumption, impostors kept {_pc(a['impostor']['apqzto'])} of their unhindered access under A-PQZTO, "
           f"against {_pc(a['impostor']['fl_ids'])} under {L['fl_ids']} and {_pc(a['impostor']['static_zta'])} "
           f"under {L['static_zta']}, and A-PQZTO was lower in all {n} seeds; {L['zta_fixedpqc']} gave them no "
           "access at all. Under A-PQZTO, the residual access occurred in the transportation slice, whose sessions "
           "start with classical keys; there an impostor is stopped only after its trust falls below "
           "$\\tau_{allow,d}$ and the re-authentication that this triggers fails.")

    # ---------------------------------------------------------------- figure and security table
    tr = _trace_seeds()
    n_tr = len(tr["apqzto"])
    assert all(tr[p] == tr["apqzto"] for p in ("none", "static_zta", "fl_ids", "dt_ids_nofl", "apqzto_nodt"))
    # caption: ZTA + fixed PQC equals Static ZTA except for impostors
    assert all(a[s]["zta_fixedpqc"] == a[s]["static_zta"] for s in ("ddos", "evasion", "injection"))
    m.figure(os.path.join(FIG, "fig8_city.png"),
             "City-scale results on the test episodes. (a) Devices compromised so far after the onset of the worm "
             f"(mean and 10–90% band over {_w(n_tr)} test seeds; symmetric logarithmic axis, linear below 10). (b) "
             "Attack-success ratio relative to no response for flooding, credential misuse, data injection and "
             f"impostors (mean and 95% bootstrap confidence interval over {n} test seeds; lower is better), with the "
             f"colours of (a). {L['zta_fixedpqc']} is not shown: its values equal those of {L['static_zta']}, except "
             "for impostors, where they are zero.", width_in=6.3, label="city")
    _table_sec(m, C, n)

    # ---------------------------------------------------------------- cost
    m.label_next("tab", "citycost")
    fb = {p: _ci(C, p, "benign", "fb") for p in BASE}
    di = {p: v(p, "benign", "disr_frac") for p in BASE}
    assert fb["apqzto"][0] < 0.5 * fb["fl_ids"][0] and fb["apqzto"][2] < fb["fl_ids"][1], "'less than half': revise"
    assert fb["apqzto"][0] < fb["static_zta"][0] and di["apqzto"] < min(di["fl_ids"], di["static_zta"])
    th = C["theta"]
    cal = _calib(S)
    vfb = {p: _cal_at(cal, p, th[p])[0] for p in ("apqzto", "fl_ids")}
    gap_val, gap_test = vfb["fl_ids"] - vfb["apqzto"], fb["fl_ids"][0] - fb["apqzto"][0]
    assert abs(gap_val) < 0.5 * gap_test and vfb["apqzto"] > fb["apqzto"][0], "validation/test shift claim: revise"
    m.para(f"In the benign test episodes (Table {{tab:citycost}}), A-PQZTO quarantined or blocked benign devices "
           f"in {_pc(fb['apqzto'][0], 2)} of their device-steps, against "
           f"{_pc(fb['fl_ids'][0], 2)} for {L['fl_ids']} and {_pc(fb['static_zta'][0], 2)} for {L['static_zta']}, "
           f"and its criticality-weighted disruption was {_pc(di['apqzto'], 2)}, against {_pc(di['fl_ids'], 2)} and "
           f"{_pc(di['static_zta'], 2)}. On the test seeds it thus matched {L['fl_ids']} on the worm and on credential misuse with "
           "less than half of its false blocking. Most of this gap arose between validation and test, however: at "
           "the calibrated operating points, the two policies had similar false blocking on the validation episodes "
           f"({_pc(vfb['apqzto'], 2)} and {_pc(vfb['fl_ids'], 2)}).")

    # ---------------------------------------------------------------- PQC and decision time
    hs = {p: v(p, "benign", "hndl") for p in BASE}
    ha = {p: v(p, "benign", "hndl_all") for p in BASE}
    classical = ("none", "static_zta", "fl_ids", "dt_ids_nofl")
    assert hs["apqzto"] == 0.0 and hs["zta_fixedpqc"] == 0.0 and ha["zta_fixedpqc"] == 0.0
    assert all(hs[p] == 1.0 and ha[p] == 1.0 for p in classical)
    assert abs(ha["apqzto"] - N_CL / N) < 0.01, "classical sessions are no longer those of the transportation slice"
    pq, rq, pqf = v("apqzto", "benign", "pq_hs"), v("apqzto", "benign", "pq_reauth"), v("zta_fixedpqc", "benign", "pq_hs")
    assert 0 < pq < pqf
    # a device keeps its verified identity for the rest of the episode, so at most one re-authentication per
    # transportation device; 'almost all' requires at least 95% of them
    assert 0.95 * N_CL <= rq <= N_CL, "re-authentication coverage changed: revise text"
    dm = {p: v(p, "benign", "dec_ms") for p in BASE}
    assert dm["apqzto"] > dm["fl_ids"]
    m.para(f"No sensitive-slice session of A-PQZTO or of {L['zta_fixedpqc']} relied on classical key exchange "
           f"alone, whereas every session of the classical policies did. Across all slices, {_pc(ha['apqzto'])} of "
           "A-PQZTO's sessions, those of the transportation slice, remained classical, so its migration is partial "
           "by design. These shares count sessions by their key exchange (Eq. {eq:hndl}) and do not measure any "
           f"decryption. A-PQZTO performed {pq:,.0f} post-quantum handshakes per hour, {rq:,.0f} of them "
           f"risk-triggered re-authentications, {100 * (1 - pq / pqf):.0f}% fewer than {L['zta_fixedpqc']} "
           f"({pqf:,.0f}). As a verified identity is kept for the rest of the episode, almost every one of the "
           f"{N_CL:,} transportation devices thus fell below $\\tau_{{allow,d}}$ at least once in the hour. A "
           f"decision step for all {N:,} devices took {dm['apqzto']:.2f} ms, against {dm['fl_ids']:.2f} ms for "
           f"{L['fl_ids']} (indicative times, as several runs shared the host; see Section 5.7).")
    _table_cost(m, C, n, N)


# ------------------------------------------------------------------------------------------------ 5.5
def _table_ablation(m, C, n):
    th = C["theta"]
    rows = []
    for p in ABL:
        lab = f"**{L[p]}**" if p == "apqzto" else L[p]
        r = [lab, _sg(th[p]), f"{_v(C, p, 'worm', 'ce'):.4f}" + _mark(C, "worm", p),
             f"{_v(C, p, 'worm', 'ever'):.1f}"]
        for s in ("ddos", "evasion", "injection", "impostor"):
            r.append(f"{100 * _v(C, p, s, 'asr'):.2f}" + _mark(C, s, p))
        r += [f"{100 * _v(C, p, 'benign', 'fb'):.2f}", f"{100 * _v(C, p, 'benign', 'hndl'):.0f}"]
        rows.append(r)
    cont = {p: _v(C, p, "worm", "contained") for p in ABL}
    short = [p for p in ABL if cont[p] < 1.0]
    assert short == ["apqzto_twinrisk"], "containment pattern of the variants changed: revise table note"
    n_c = round(cont[short[0]] * n)
    hdr = [["Variant", "$\\theta$", "Worm", "", "Attack-success ratio (%)", "", "", "", "Benign", "$E_{HNDL}$"],
           ["", "", "CE", "Devices compromised", "Flooding", "Credential misuse", "Data injection", "Impostor",
            "False blocking (%)", "Sensitive slices (%)"]]
    m.table(hdr, rows, f"Ablation of A-PQZTO: each variant removes or changes one component and is recalibrated to "
            f"the same budget (mean over {n} test seeds).",
            col_widths=[1.55, 0.45, 0.6, 0.85, 0.62, 0.7, 0.6, 0.64, 0.6, 0.65], label="ablation", header_rows=2,
            align=["left"] + ["center"] * 9,
            notes="$\\theta$: threshold offset calibrated on the validation episodes (Section 4.4); offsets are "
                  "comparable only between variants that use the same score. †: differs from A-PQZTO with $q$ ≤ "
                  f"{ALPHA:.2f} (paired Wilcoxon signed-rank test over seeds, Benjamini–Hochberg adjustment over all "
                  f"{len(C['tests'])} comparisons with A-PQZTO); tests were run for CE and the attack-success ratios. "
                  f"The original design contained the worm in {n_c} of {n} episodes, every other variant in all of "
                  "them.")


def block_ablation(m, S):
    C = S["city"]
    v = lambda p, s, k: _v(C, p, s, k)
    t = lambda s, p: _t(C, s, p)
    th = C["theta"]
    cal = _calib(S)
    n = t("worm", "fl_ids")["n"]
    m.heading("5.5 Ablation: what each component contributes", 2)
    m.label_next("tab", "ablation")
    A = "apqzto"

    # ---------------------------------------------------------------- without PQC
    p = "apqzto_nopqc"
    assert t("worm", p)["q_bh"] > ALPHA
    x = t("impostor", p)
    assert x["q_bh"] <= ALPHA and x["mean_diff"] < 0
    assert v(p, "benign", "hndl") == 1.0
    xe, xi = t("evasion", p), t("injection", p)
    assert all(y["q_bh"] <= ALPHA and -0.02 < y["mean_diff"] < 0 for y in (xe, xi)), "'slightly worse': revise text"
    assert th[p] < th[A]
    m.para("In Table {tab:ablation}, each variant removes or changes one component and is recalibrated to the same "
           "budget, so a component can matter directly or through the operating point it allows. "
           f"Without PQC, worm containment did not change ({_q(t('worm', p)['q_bh'])}), but impostor success rose "
           f"from {_pc(v(A, 'impostor', 'asr'))} to {_pc(v(p, 'impostor', 'asr'))} and every sensitive session "
           f"kept classical keys. Credential misuse ({_pc(v(p, 'evasion', 'asr'))}) and data injection "
           f"({_pc(v(p, 'injection', 'asr'))}) also became slightly more successful "
           f"({_q_le(max(xe['q_bh'], xi['q_bh']))}), probably because sensitive devices then keep the classical "
           f"value of $A_{{i}}$, which lowered the calibrated offset ({_sg(th[p])} instead of {_sg(th[A])}).")
    _table_ablation(m, C, n)

    # ---------------------------------------------------------------- without twin
    p = "apqzto_nodt"
    xw = t("worm", p)
    assert xw["q_bh"] > ALPHA, "worm containment without the twin changed: revise text"
    assert v(p, "benign", "iso") > 0 and v(A, "benign", "iso") == 0
    grid = sorted((float(k), x) for k, x in cal[p].items())
    assert abs(max(k for k, x in grid if x[2]) - th[p]) < 1e-9, "calibration grid does not match theta"
    above = [(k, x) for k, x in grid if k > th[p] + 1e-9]
    assert above and all(x[1] > BUDGET and not x[2] for _, x in above), "disruption no longer binding: revise text"
    k1, x1 = above[0]
    assert x1[0] < BUDGET                     # false blocking alone would have allowed this offset
    assert _cal_at(cal, A, th[A])[2] and th[p] < th[A]
    xe, xi = t("evasion", p), t("injection", p)
    assert all(y["q_bh"] <= ALPHA and y["mean_diff"] < 0 for y in (xe, xi)), "no-twin detection loss changed: revise"
    scen_all = ("benign", "worm", "ddos", "evasion", "injection", "impostor")
    iso = {s: v(A, s, "iso") for s in scen_all}
    assert iso["ddos"] > 0 and all(iso[s] == 0 for s in scen_all if s != "ddos"), "twin isolations changed: revise"
    n_iso = round(iso["ddos"] * n)             # one-hour episodes: mean isolations per hour x episodes
    assert abs(iso["ddos"] * n - n_iso) < 1e-6 and v(A, "worm", "contained") == 1.0
    m.para(f"In {L[p]}, a static rule isolates a cluster once three of its devices are suspected. Worm containment "
           f"was unchanged ({_q(xw['q_bh'])}), but the rule also isolated clusters in "
           f"benign episodes ({v(p, 'benign', 'iso'):.2f} per hour). On the validation episodes, its disruption "
           f"exceeded the budget at every offset above {_sg(th[p])} ({_pc(x1[1], 2)} at $\\theta$ = {_sg(k1)}, with "
           f"false blocking at {_pc(x1[0], 2)}), so the variant ran at a less sensitive operating point than A-PQZTO. "
           f"Credential misuse then kept {_pc(v(p, 'evasion', 'asr'))} of its activity instead of "
           f"{_pc(v(A, 'evasion', 'asr'))} ({_q(xe['q_bh'])}), and data injection {_pc(v(p, 'injection', 'asr'))} instead "
           f"of {_pc(v(A, 'injection', 'asr'))} ({_q(xi['q_bh'])}). The twin thus contributed by declining isolations "
           f"that would not pay off; in all nominal test episodes it approved only {_w(n_iso)}, all during flooding "
           "and none during the worm. Section 5.7 tests a faster worm to see when the twin does isolate clusters.")

    # ---------------------------------------------------------------- without FL
    p = "apqzto_nofl"
    xw, xe = t("worm", p), t("evasion", p)
    assert xw["q_bh"] <= ALPHA and xw["mean_diff"] > 0 and xe["q_bh"] <= ALPHA and xe["mean_diff"] < 0
    assert min(SINGLE, key=lambda q: v(q, "worm", "ce")) == p, "no longer the largest single-removal loss: revise"
    m.para("Replacing the federated detector with each edge node's own local detector weakened worm containment "
           f"more than any other single removal: containment efficiency fell to {v(p, 'worm', 'ce'):.4f} "
           f"({_q(xw['q_bh'])}), {v(p, 'worm', 'ever'):.1f} devices were compromised on average, and credential "
           f"misuse rose to {_pc(v(p, 'evasion', 'asr'))} ({_q(xe['q_bh'])}).")

    # ---------------------------------------------------------------- without adaptive trust
    p = "apqzto_notrust"
    xw, xd, xi, xm = t("worm", p), t("ddos", p), t("injection", p), t("impostor", p)
    assert xw["q_bh"] > ALPHA
    assert all(y["q_bh"] <= ALPHA and y["mean_diff"] > 0 for y in (xd, xi)), "rule-based variant no longer better"
    fbp, fba = _ci(C, p, "benign", "fb"), _ci(C, A, "benign", "fb")
    assert fbp[1] > fba[2], "rule-based variant no longer blocks more benign devices: revise text"
    assert xm["q_bh"] <= ALPHA and xm["mean_diff"] < 0
    m.para(f"{L[p]}, which acts after two consecutive suspicious observations, contained the worm equally well "
           f"({_q(xw['q_bh'])}) and was significantly better against flooding ({_pc(v(p, 'ddos', 'asr'), 2)} "
           f"against {_pc(v(A, 'ddos', 'asr'), 2)}, {_q(xd['q_bh'])}) and data injection "
           f"({_pc(v(p, 'injection', 'asr'))} against {_pc(v(A, 'injection', 'asr'))}, {_q(xi['q_bh'])}), but it "
           f"blocked more benign devices ({_pc(fbp[0], 2)} against {_pc(fba[0], 2)}) and let impostors keep more "
           f"access ({_pc(v(p, 'impostor', 'asr'), 2)} against {_pc(v(A, 'impostor', 'asr'), 2)}, "
           f"{_q(xm['q_bh'])}).")

    # ---------------------------------------------------------------- without behavioural profile
    p = "apqzto_nobeh"
    assert th[p] == th[A]
    for s in ("evasion", "injection"):
        y = t(s, p)
        assert y["p"] == 1.0 and y["mean_diff"] == 0.0 and y["better"] == 0, "no longer identical in every seed"
    qs = [t(s, p)["q_bh"] for s in METRIC]
    assert min(qs) > ALPHA, "behavioural ablation now shows a significant difference: revise text"
    m.para("Removing the behavioural profile, the only modelled evidence input, changed nothing measurable: the "
           "calibrated offset was the same, credential misuse and data injection gave identical outcomes in every seed, "
           f"and no difference was significant ({_q_ge(min(qs))}). The profile shifts when a device attacks, which "
           "is also when its detector evidence rises, so in this simulator it duplicated that evidence.")

    # ---------------------------------------------------------------- without veto
    p = "apqzto_noveto"
    xd, xi, xe = t("ddos", p), t("injection", p), t("evasion", p)
    assert v(p, "benign", "fb") < v(A, "benign", "fb")
    assert xd["q_bh"] <= ALPHA and xd["mean_diff"] > 0
    assert xi["q_bh"] <= ALPHA and xi["mean_diff"] < 0
    assert xe["q_bh"] > ALPHA and xe["mean_diff"] < 0
    m.para(f"Without the zero-trust veto, the purely additive score blocked fewer benign devices "
           f"({_pc(v(p, 'benign', 'fb'), 2)}) and was better against flooding ({_pc(v(p, 'ddos', 'asr'), 2)}, "
           f"{_q(xd['q_bh'])}) but worse against data injection ({_pc(v(p, 'injection', 'asr'))}, {_q(xi['q_bh'])}); "
           f"credential misuse rose to {_pc(v(p, 'evasion', 'asr'))}, a difference that was not significant "
           f"({_q(xe['q_bh'])}).")

    # ---------------------------------------------------------------- original design
    p = "apqzto_twinrisk"
    xw, xe, xi = t("worm", p), t("evasion", p), t("injection", p)
    assert xw["q_bh"] <= ALPHA and xw["mean_diff"] > 0
    assert all(y["q_bh"] <= ALPHA and y["mean_diff"] < 0 for y in (xe, xi))
    # 'far worse than every other variant': worst on worm CE, credential misuse and injection
    assert min(ABL, key=lambda q: v(q, "worm", "ce")) == p
    assert max(ABL, key=lambda q: v(q, "evasion", "asr")) == p and max(ABL, key=lambda q: v(q, "injection", "asr")) == p
    second_ev = max(v(q, "evasion", "asr") for q in ABL if q != p)
    assert v(p, "evasion", "asr") > 2 * second_ev
    cont = v(p, "worm", "contained")
    n_c = round(cont * n)
    assert cont < 1.0 and abs(cont * n - n_c) < 1e-6
    # the same additive score without D_i was calibrated to a much more sensitive offset
    assert th[p] < th["apqzto_noveto"] - 0.2
    m.para("The original design, the additive score minus the twin's propagation risk $D_{i}$ of Eq. {eq:twinrisk}, "
           f"performed far worse than every other variant: a containment efficiency of {v(p, 'worm', 'ce'):.4f} "
           f"({_q(xw['q_bh'])}) with {v(p, 'worm', 'ever'):.1f} devices compromised, only {_w(n_c)} of {n} worm "
           f"episodes contained, and {_pc(v(p, 'evasion', 'asr'))} and {_pc(v(p, 'injection', 'asr'))} of the "
           "credential-misuse and data-injection activity left unstopped. The main cause appears to be the calibration: "
           "$D_{i}$ lowers the trust of every device with moderate threat evidence that has many susceptible "
           "neighbours and high criticality, benign devices included, so the budget was reached at a much lower "
           f"offset ($\\theta$ = {_sg(th[p])}, against {_sg(th['apqzto_noveto'])} for the same additive score "
           "without $D_{i}$).")
