# -*- coding: utf-8 -*-
"""Section 5.7: stress tests (fast worm, twin fidelity, slower devices) and scalability. Numbers are read from
stress_summary.json and city_extra_summary.json; qualitative statements are guarded by assertions."""
import json
import os

RES = r"E:\A-PQZTO_work\results"
FIG = r"E:\A-PQZTO_work\figures"


def _load(S):
    Z = S.get("stress") or json.load(open(os.path.join(RES, "stress_summary.json")))
    X = S.get("city_extra") or json.load(open(os.path.join(RES, "city_extra_summary.json")))
    return Z, X


def block(m, S):
    Z, X = _load(S)
    st, pq, sc = Z["stress"], Z["pqcost"], Z["scal"]["cells"]
    P = st["policies"]
    ev = lambda p: P[p]["ever"][0]
    T = {t["vs"]: t for t in st["tests_policies"]}
    TW = st["tests_twin"]
    m.heading("5.7 Stress tests and scalability", 2)
    # ------------------------------------------------------------------ fast worm
    fl, ap = T["fl_ids"], ev("apqzto")
    assert fl["q_bh"] > 0.05 and fl["better"] <= 8 and ev("fl_ids") < ap
    assert all(P[p]["contained"] == 1.0 for p in ("fl_ids", "apqzto", "apqzto_notrust", "apqzto_nodt",
                                                     "apqzto_noveto"))
    assert P["static_zta"]["contained"] < 1 and P["dt_ids_nofl"]["contained"] < 1
    assert T["static_zta"]["q_bh"] <= 0.05 and T["dt_ids_nofl"]["q_bh"] <= 0.05
    assert abs(ev("apqzto_notrust") - ev("fl_ids")) < 3
    m.label_next("fig", "stress")
    m.para(
        "Every policy contained the nominal worm, so that scenario says little about the limits of each design. We "
        "therefore repeated the worm scenario with a per-contact propagation probability "
        "of 0.10, about three times the rate the twin assumes, keeping the calibrated operating points and the 20 "
        f"test seeds (Fig. {{fig:stress}}a). Without a response the worm reached all {st['none_ever'][0]:,.0f} "
        f"devices. The two policies with local detectors fell far behind: Static ZTA let {ev('static_zta'):.0f} "
        f"devices become infected on average and DT-assisted IDS w/o FL {ev('dt_ids_nofl'):.0f}, and each failed to "
        "contain the outbreak in some episodes. The policies built on the federated detector contained every "
        f"outbreak, but not equally fast. FL-only IDS averaged {ev('fl_ids'):.0f} infected devices with a median "
        f"time to containment of {P['fl_ids']['ttc_median']:.1f} min, whereas A-PQZTO averaged {ap:.0f} devices and "
        f"took {P['apqzto']['ttc_median']:.1f} min. A-PQZTO was worse in {fl['worse']} of the {fl['n']} seeds "
        f"(p = {fl['p']:.2f} before and {fl['q_bh']:.2f} after the Benjamini–Hochberg correction), so with "
        f"{fl['n']} seeds the difference falls short of significance but should not be dismissed. A-PQZTO w/o "
        "adaptive trust, "
        "which quarantines a device after two consecutive detector hits, matched FL-only IDS "
        f"({ev('apqzto_notrust'):.0f} devices). The slower reaction therefore appears to come from the trust score "
        "of Eq. {eq:trust} itself: it accumulates evidence over several observations, which is meant to keep "
        "benign devices out of quarantine but also lets a fast worm make a few more hops before a device's trust "
        "falls below the quarantine threshold.")
    # ------------------------------------------------------------------ twin fidelity
    nom = X["twin"]["cells"]
    assert max(c["iso_per_h_mean"] for c in nom.values()) == 0.0
    ce_nom = {round(c["ce_mean"], 6) for c in nom.values()}
    assert len(ce_nom) == 1
    cells = st["twin_cells"]
    iso = [c["iso_per_h"][0] for c in cells.values()]
    evs = [c["ever"][0] for c in cells.values()]
    dz = [c["disr_frac"][0] for c in cells.values()]
    q_min = min(t["q_bh"] for t in TW if "fl_ids" not in t["contrast"])
    assert q_min > 0.05
    k_true = "twin_err=0.0|beta_hat=0.1"
    k_low = "twin_err=0.0|beta_hat=0.015"
    assert cells[k_true]["iso_per_h"][0] > cells[k_low]["iso_per_h"][0]
    k_most = max(cells, key=lambda k: cells[k]["iso_per_h"][0])
    assert cells[k_most]["ever"][0] == min(evs), "fewest infections no longer where isolations are most frequent"
    assert cells["twin_err=0.5|beta_hat=0.1"]["iso_per_h"][0] > cells[k_true]["iso_per_h"][0]
    m.para(
        "Errors in the twin's model made no difference in the nominal worm scenario, because the twin never acted "
        f"there: it did not approve a single cluster isolation in any of the {X['twin']['n_runs_apqzto']} runs of "
        "the fidelity sweep, so removing up to half of the true links from its graph or halving or doubling its "
        "propagation rate left every outcome unchanged. Device-level quarantine stopped the worm before an "
        "isolation could pay off in the twin's roll-outs. Under the fast worm the twin did act (Fig. "
        "{fig:stress}b). Isolations became more frequent as its rate estimate approached the true value and as its "
        f"graph contained more spurious links, ranging from {min(iso):.2f} to {max(iso):.2f} per hour. The mean "
        f"number of infected devices ranged from {min(evs):.0f} to {max(evs):.0f}, the lowest values occurring "
        f"where isolations were most frequent, and criticality-weighted disruption from {100 * min(dz):.2f}% to "
        f"{100 * max(dz):.2f}%. None of these differences was significant (adjusted p ≥ {q_min:.2f}). Spurious "
        "links make the twin see more escape routes, so a less accurate graph made it slightly more willing to "
        "isolate, not less. Within this study the twin is therefore best described as a conservative gate on "
        "cluster-wide actions: it rarely acts, and its main measured benefit is the one in Section 5.5, where a "
        "static isolation rule in its place weakened protection against credential misuse and data injection.")
    # ------------------------------------------------------------------ PQ cost on slower devices
    C = pq["cells"]
    dfs = sorted({v["dev_factor"] for v in C.values()})
    imp = {d: C[f"{d}|impostor"] for d in dfs}
    fit = [d for d in dfs if "transport" in imp[d]["slices_fitting"]]
    nofit = [d for d in dfs if "transport" not in imp[d]["slices_fitting"]]
    a0, a1 = imp[fit[0]]["asr"][0], imp[nofit[0]]["asr"][0]
    t0, t1 = imp[fit[0]]["asr_transport"][0], imp[nofit[-1]]["asr_transport"][0]
    assert all(abs(imp[d]["asr"][0] - a0) < 1e-9 for d in fit) and all(abs(imp[d]["asr"][0] - a1) < 1e-9
                                                                       for d in nofit)
    ev_asr = [C[f"{d}|evasion"]["asr"][0] for d in dfs]
    fbs = [C[f"{d}|benign"]["fb"][0] for d in dfs]
    assert max(ev_asr) - min(ev_asr) < 1e-9 and max(fbs) - min(fbs) < 1e-9
    fl_imp = S["city"]["summary"]["fl_ids|impostor"]["asr"][0]
    assert a1 < fl_imp
    hs = lambda d: pq["pq_ms"] * d
    m.para(
        "The adaptive post-quantum rule re-authenticates a suspicious device only if the handshake fits its slice "
        "budget. Constrained devices can be much slower than the laptop processor of Section 5.6, so we scaled the "
        f"2 ms handshake by the slowdown factor $\\kappa$ of Eq. {{eq:pq}} from {dfs[0]:g} to {dfs[-1]:g}, "
        f"giving {hs(dfs[0]):g} to "
        f"{hs(dfs[-1]):g} ms (Fig. {{fig:stress}}c). While the handshake fitted the 10 ms budget of the "
        f"transportation slice, impostor success stayed at {100 * a0:.1f}%. Beyond that point, re-authentication of "
        f"transportation devices was deferred, and impostor success rose to {100 * a1:.1f}% overall, still below "
        f"the {100 * fl_imp:.1f}% of FL-only IDS, and from {100 * t0:.1f}% to {100 * t1:.1f}% within the "
        "transportation slice. It did not rise further for slower devices, because devices in the sensitive slices "
        "receive a post-quantum identity at session set-up and are not re-authenticated on demand; this assumes "
        "that the initial hybrid handshake is performed outside the latency-critical path. Credential-misuse "
        "success and false blocking did not change. On hardware more than about five times slower than our test "
        "machine, the transportation slice therefore loses its post-quantum check and falls back on the detector.")
    # ------------------------------------------------------------------ scalability
    g = lambda p, n: sc[f"{p}|n_dev={n}"]["dec_ms_mean"]
    ns = sorted({v["n_dev"] for v in sc.values()})
    assert g("apqzto", ns[-1]) / g("apqzto", ns[0]) > 4 * (ns[-1] / ns[0])      # super-linear
    assert g("apqzto_nodt", ns[-1]) < 1.0 and g("fl_ids", ns[-1]) < 1.0
    m.para(
        "Decision time grew with city size (Fig. {fig:stress}d). With one worker, A-PQZTO needed "
        f"{g('apqzto', ns[0]):.2f} ms per 10-s control step for {ns[0]:,} devices, {g('apqzto', ns[1]):.1f} ms for "
        f"{ns[1]:,}, {g('apqzto', ns[2]):.1f} ms for {ns[2]:,} and {g('apqzto', ns[-1]):.0f} ms for {ns[-1]:,}. "
        "The growth is faster than linear and comes from the twin, whose roll-outs multiply dense adjacency "
        f"matrices: without the twin the same step took {g('apqzto_nodt', ns[-1]):.2f} ms at {ns[-1]:,} devices, "
        f"and FL-only IDS {g('fl_ids', ns[-1]):.2f} ms. Even the largest value uses "
        f"{100 * g('apqzto', ns[-1]) / 10000:.1f}% of the control interval, but a city-wide deployment would need a "
        "sparse graph representation or roll-outs restricted to the neighbourhood of the candidate cluster. "
        "These timings come from a single-threaded Python implementation; the decision times in Table "
        "{tab:citycost} are higher because several simulations ran in parallel on the same processor.")
    m.figure(os.path.join(FIG, "fig10_stress.png"),
             "Stress tests and scalability (20 test seeds unless stated; mean and 95% bootstrap confidence "
             "interval). (a) Devices ever infected by a worm with per-contact propagation probability 0.10, three "
             "times the twin's prior; 'w/o' marks A-PQZTO ablations. "
             "(b) A-PQZTO under the same worm when the twin's propagation-rate estimate and the share of wrong links "
             "in its graph vary; the dashed line is FL-only IDS. (c) Attack-success ratio of A-PQZTO in the impostor "
             "and credential-misuse scenarios when the post-quantum handshake takes longer on slower "
             "devices; dotted lines mark the slice latency budgets. (d) Decision time per 10-s "
             "control step against city size, one worker, seeds 21–23.", width_in=6.3, label="stress")
