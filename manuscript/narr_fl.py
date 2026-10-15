# -*- coding: utf-8 -*-
"""Narrative for Sections 5.2-5.3 (federated detection). Numbers are read from fl_summary.json; the qualitative
statements (which rule is ahead, which differences are significant) were checked against the paired tests in the same
file for the v2 runs and are re-checked by assertions below, so that a re-run with different outcomes fails loudly
instead of producing a wrong sentence."""


def _m(E, k, met="macro_f1"):
    return E[k][met][0]


def _t(T, cond, metric, vs):
    for t in T:
        if t["cond"] == cond and t["metric"] == metric and t["vs"] == vs:
            return t
    raise KeyError((cond, metric, vs))


def build(S):
    F = S["fl"]
    E1, E2, E2n, E3, T = F["E1"], F["E2"], F["E2n"], F.get("E3", {}), F["tests"]
    out = {}
    ton_c, cic_c = _m(E1, "ton|central|None"), _m(E1, "cic|central|None")
    v = {g: _m(E1, f"ton|{g}|None") for g in ("fedavg", "ta", "mkrum", "krum")}
    a01 = {g: _m(E1, f"ton|{g}|0.1") for g in ("fedavg", "ta", "trmean", "krum", "mkrum", "median")}
    c01 = {g: _m(E1, f"cic|{g}|0.1") for g in ("fedavg", "fedprox", "ta", "trmean", "mkrum", "median", "krum")}
    t_auc = min(E1[f"ton|{g}|None"]["auc"][0] for g in ("fedavg", "fedprox", "mkrum", "median", "trmean", "ta"))
    c_fpr, c_auc = E1["cic|fedavg|None"]["fpr"][0], E1["cic|fedavg|None"]["auc"][0]
    t_fa = {(ds, a): _t(T, f"E1|{ds}|{a}", "macro_f1", "fedavg") for ds in ("ton", "cic") for a in ("None", "1.0", "0.1")}
    sig_fa = [k for k, t in t_fa.items() if t["q_bh"] <= 0.05]
    assert sig_fa == [("cic", "1.0")] and t_fa[("cic", "1.0")]["mean_diff"] < 0, "clean TA vs FedAvg changed: revise"
    t_sig = t_fa[("cic", "1.0")]
    q_ns = min(t["q_bh"] for k, t in t_fa.items() if k not in sig_fa)
    gap_max = max(abs(t["mean_diff"]) for t in t_fa.values())
    assert gap_max < 0.01
    assert max(a01, key=a01.get) == "trmean" and a01["ta"] > a01["fedavg"] > a01["mkrum"] > a01["median"] > a01["krum"]
    out["txt_fl_clean"] = (
        "Without attacks, the federated detectors came close to the centralised reference (Fig. {fig:flclean}, "
        f"Table {{tab:flclean}}). On TON_IoT with IID clients the centralised model reached a macro-F1 of {ton_c:.3f}, "
        f"FedAvg {v['fedavg']:.3f}, the trust-aware rule {v['ta']:.3f} and Multi-Krum {v['mkrum']:.3f}. The binary "
        f"attack-versus-benign decision was almost saturated, with an AUC of at least {t_auc:.3f} for every rule "
        "except Krum. Macro-F1 fell for every rule as the client data became more skewed. Under $\\alpha$ = 0.1 the "
        f"trimmed mean reached {a01['trmean']:.3f}, the trust-aware rule {a01['ta']:.3f}, FedAvg {a01['fedavg']:.3f}, "
        f"Multi-Krum {a01['mkrum']:.3f}, the median {a01['median']:.3f} and Krum {a01['krum']:.3f}; Krum keeps a single "
        "update per round and therefore discards most of what the skewed clients know. CICIoT2023 was harder for "
        f"every method: the centralised model reached a macro-F1 of {cic_c:.3f}, the AUC was about {c_auc:.2f} and "
        f"{100 * c_fpr:.0f}% of benign flows were flagged, probably because benign CICIoT2023 traffic overlaps with "
        "low-rate attacks once duplicated and label-conflicting flows are removed. The trust-aware rule did not differ "
        f"significantly from FedAvg in five of the six data settings (adjusted p ≥ {q_ns:.2f}). On CICIoT2023 with "
        f"$\\alpha$ = 1.0 it was lower by {abs(t_sig['mean_diff']):.3f} in macro-F1 (adjusted p = "
        f"{t_sig['q_bh']:.2f}), and the largest gap in any setting was {gap_max:.3f}, so on clean data its "
        "protection costs less than 0.01 in macro-F1.")
    out["cap_fl_clean"] = ("Multi-class macro-F1 of the federated detectors without attacks for three partitions of "
                           "the training data (mean and 95% bootstrap confidence interval over 10 seeds, each with its "
                           "own data split); the dashed line marks the centralised model trained on pooled data.")
    # ---------------------------------------------------------------- poisoning
    sf = lambda ds, n, g: E2[f"{ds}|sf|{n}|{g}"]["detect_rate"][0]
    lf = lambda ds, n, g: E2[f"{ds}|lf|{n}|{g}"]["detect_rate"][0]
    div = sum(E2[f"{ds}|sf|{n}|{g}"]["diverged"] for ds in ("ton", "cic") for n in (1, 2, 3) for g in ("fedavg", "fedprox"))
    robust_min = min(sf(ds, n, g) for ds in ("ton", "cic") for n in (1, 2, 3) for g in ("krum", "mkrum", "median",
                                                                                         "trmean", "ta"))
    assert robust_min > 0.88
    mk_gap = [_t(T, f"E2|{ds}|{att}|2", "macro_f1", "mkrum") for ds in ("ton", "cic") for att in ("lf", "sf")]
    assert all(_t(T, f"E2|{ds}|sf|2", "macro_f1", "fedavg")["cliff"] == 1.0 for ds in ("ton", "cic"))
    out["txt_fl_pois"] = (
        "Model poisoning broke the two averaging rules (Fig. {fig:flpois}, Table {tab:flpois}). With two clients sending "
        f"sign-flipped, scaled updates, FedAvg detected {100 * sf('ton', 2, 'fedavg'):.1f}% of the TON_IoT attacks "
        f"and {100 * sf('cic', 2, 'fedavg'):.1f}% of the CICIoT2023 attacks, and FedAvg and FedProx diverged "
        f"numerically in {div} of their 120 runs with model poisoning. With $\\alpha$ = 1.0, every Byzantine-robust "
        f"rule detected at least {int(1000 * robust_min) / 10:.1f}% of attacks under model poisoning with one to "
        f"three malicious clients; the trust-aware rule reached {100 * sf('ton', 2, 'ta'):.1f}% on TON_IoT and "
        f"{100 * sf('cic', 2, 'ta'):.1f}% on CICIoT2023 with two of them (Cliff's $\\delta$ = 1.00 against FedAvg "
        "in macro-F1 on both datasets). Targeted label flipping did less damage. It barely affected detection on "
        f"TON_IoT, but on CICIoT2023 it lowered FedAvg's detection to {100 * lf('cic', 2, 'fedavg'):.1f}% with two "
        f"flipping clients, against {100 * lf('cic', 2, 'ta'):.1f}% for the trust-aware rule and "
        f"{100 * lf('cic', 2, 'mkrum'):.1f}% for Multi-Krum. Multi-Krum, given a correct upper bound of three "
        "Byzantine clients, was the strongest single rule under poisoning: with two malicious clients its macro-F1 "
        "was higher than that of the trust-aware rule in all four combinations of dataset and attack, by "
        f"{min(-t['mean_diff'] for t in mk_gap):.3f} to {max(-t['mean_diff'] for t in mk_gap):.3f}. The trust-aware "
        "rule was on a par with the median and the trimmed mean.")
    n_mf = {(ds, att): {g: E2n[f"{ds}|{att}|2|{g}"]["macro_f1"][0] for g in ("fedavg", "ta", "mkrum", "median",
                                                                             "trmean", "krum")}
            for ds in ("ton", "cic") for att in ("lf", "sf")}
    md_q = [_t(T, f"E2n|{ds}|{att}|2", "macro_f1", "median")["q_bh"] for ds in ("ton", "cic") for att in ("lf", "sf")]
    n_sig_md = sum(q <= 0.05 for q in md_q)
    best = {k: max(v, key=v.get) for k, v in n_mf.items()}
    assert best[("cic", "lf")] == "ta" and all(best[k] == "mkrum" for k in best if k != ("cic", "lf"))
    md_up = all(_t(T, f"E2n|{ds}|{att}|2", "macro_f1", "median")["mean_diff"] > 0 for ds in ("ton", "cic")
                for att in ("lf", "sf"))
    assert md_up and all(n_mf[k]["ta"] > n_mf[k]["krum"] for k in n_mf)
    second = all(sorted(v, key=v.get)[-2] == "ta" for k, v in n_mf.items() if k != ("cic", "lf"))
    assert second, "trust-aware rule no longer second where Multi-Krum leads: revise text"
    out["txt_fl_pois2"] = (
        "Poisoning combined with strongly non-IID data is a realistic case for an edge federation in a city. With "
        "$\\alpha$ = 0.1 and two malicious clients, Multi-Krum again had the highest macro-F1 in three of the four "
        "combinations; the trust-aware rule was second in those and first on CICIoT2023 with label flipping "
        f"({n_mf[('cic', 'lf')]['ta']:.3f} against {n_mf[('cic', 'lf')]['mkrum']:.3f} for Multi-Krum). It was "
        "significantly better than the median in "
        f"{'all four' if n_sig_md == 4 else str(n_sig_md) + ' of the four'} combinations and better than Krum in all "
        "of them. A plausible reason is that clients with rare classes disagree with the median in some rounds but "
        "not persistently, so the reliability memory lets their weight recover, whereas a malicious client disagrees "
        "in every round.")
    # misspecified Byzantine bound (E3): three attackers, Krum, Multi-Krum and trimmed mean told to expect one
    d3 = lambda ds, att, g: E3[f"{ds}|{att}|3|{g}"]["detect_rate"][0]
    ta3 = lambda ds, att: E2[f"{ds}|{att}|3|ta"]["detect_rate"][0]
    mk3 = lambda ds, att: E2[f"{ds}|{att}|3|mkrum"]["detect_rate"][0]
    div3 = sum(E3[f"{ds}|sf|3|{g}"]["diverged"] for ds in ("ton", "cic") for g in ("mkrum", "trmean"))
    q3 = [_t(T, f"E3|{ds}|sf|3", "macro_f1", f"{g}_f1")["q_bh"] for ds in ("ton", "cic") for g in ("mkrum", "trmean")]
    assert d3("ton", "sf", "mkrum") < 0.1 and d3("ton", "sf", "trmean") < 0.1 and ta3("ton", "sf") > 0.95
    assert all(_t(T, f"E3|{ds}|sf|3", "macro_f1", f"{g}_f1")["cliff"] == 1.0 for ds in ("ton", "cic")
               for g in ("mkrum", "trmean"))
    out["txt_fl_pois3"] = (
        "Multi-Krum's lead depends on knowing how many clients are malicious, which an operator rarely knows in "
        "advance. Table {tab:flmis} repeats the setting with three malicious clients but tells Krum, Multi-Krum and "
        "the trimmed mean to expect only one. Under model poisoning, Multi-Krum then detected "
        f"{100 * d3('ton', 'sf', 'mkrum'):.1f}% of the TON_IoT attacks and {100 * d3('cic', 'sf', 'mkrum'):.1f}% of the "
        f"CICIoT2023 attacks, the trimmed mean {100 * d3('ton', 'sf', 'trmean'):.1f}% and "
        f"{100 * d3('cic', 'sf', 'trmean'):.1f}%, and the two rules diverged in {div3} of their 40 runs. With the bound "
        f"set correctly, Multi-Krum had detected {100 * mk3('ton', 'sf'):.1f}% and {100 * mk3('cic', 'sf'):.1f}%. The "
        f"trust-aware rule, which has no such parameter, detected {100 * ta3('ton', 'sf'):.1f}% and "
        f"{100 * ta3('cic', 'sf'):.1f}% in the same runs (adjusted p ≤ {max(q3):.2f}, Cliff's $\\delta$ = 1.00 in "
        "macro-F1). Krum degrades more gracefully because it keeps one update regardless of the bound, but it pays for "
        "this with the lowest macro-F1 on clean data. A correctly configured Multi-Krum remains the better rule; the "
        "case for the trust-aware rule is that it comes close to it without a parameter whose misconfiguration, in "
        "these runs, left at most "
        f"{100 * max(d3(ds, 'sf', g) for ds in ('ton', 'cic') for g in ('mkrum', 'trmean')):.1f}% of attacks "
        "detected under model poisoning.")
    out["cap_fl_pois"] = ("Attack detection rate of the federated detector as the number of malicious clients grows "
                          "(Dirichlet $\\alpha$ = 1.0; mean and 95% bootstrap confidence band over 10 seeds): (a, c) "
                          "targeted label flipping; (b, d) sign-flipped updates scaled by 4.")
    return out
