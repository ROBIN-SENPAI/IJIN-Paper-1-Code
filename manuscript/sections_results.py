# -*- coding: utf-8 -*-
"""Sections 5-7. Every number is read from the result summaries; wording that depends on a comparison is chosen from
the data (and was checked by hand against the summaries before submission)."""
import os

FIG = r"E:\A-PQZTO_work\figures"
AGG = ["fedavg", "fedprox", "krum", "mkrum", "median", "trmean", "ta"]
AGG_LAB = {"central": "Centralised", "fedavg": "FedAvg", "fedprox": "FedProx", "krum": "Krum",
           "mkrum": "Multi-Krum", "median": "Median", "trmean": "Trimmed mean", "ta": "Trust-aware (A-PQZTO)"}
ALPHAS = [("None", "IID"), ("1.0", "$\\alpha$=1.0"), ("0.1", "$\\alpha$=0.1")]


def f3(t):
    return f"{t[0]:.3f}"


def pm(t, nd=3, pct=False):
    m, lo, hi = t
    h = (hi - lo) / 2
    if pct:
        return f"{100 * m:.1f} ± {100 * h:.1f}"
    return f"{m:.{nd}f} ± {h:.{nd}f}"


def derive(S):
    """Quantities used in the abstract, highlights and text."""
    F = S["fl"]
    D = {}
    e1, e2, e2n = F["E1"], F["E2"], F["E2n"]
    g = lambda d, k, m="macro_f1": d[k][m][0]
    D["ton_central"] = g(e1, "ton|central|None")
    D["cic_central"] = g(e1, "cic|central|None") if "cic|central|None" in e1 else float("nan")
    for ds in ("ton", "cic"):
        for a in ("None", "1.0", "0.1"):
            for ag in AGG:
                k = f"{ds}|{ag}|{a}"
                if k in e1:
                    D[f"{ds}_{ag}_{a}"] = g(e1, k)
        for att in ("lf", "sf"):
            for ag in AGG:
                k = f"{ds}|{att}|2|{ag}"
                if k in e2:
                    D[f"{ds}_{att}2_{ag}_dr"] = g(e2, k, "detect_rate")
                    D[f"{ds}_{att}2_{ag}_mf"] = g(e2, k)
                k = f"{ds}|{att}|2|{ag}"
                if k in e2n:
                    D[f"{ds}_{att}2n_{ag}_dr"] = g(e2n, k, "detect_rate")
                    D[f"{ds}_{att}2n_{ag}_mf"] = g(e2n, k)
    return {"d": D, "abstract": S.get("abstract_text", "[ABSTRACT TO BE GENERATED]")}


def table_fl_clean(m, S):
    e1 = S["fl"]["E1"]
    rows = []
    for ag in ["central"] + AGG:
        r = [("**" + AGG_LAB[ag] + "**") if ag == "ta" else AGG_LAB[ag]]
        for ds in ("ton", "cic"):
            for a, _ in ALPHAS:
                k = f"{ds}|central|None" if ag == "central" else f"{ds}|{ag}|{a}"
                r.append(pm(e1[k]["macro_f1"]) if k in e1 and (ag != "central" or a == "None") else "–")
        rows.append(r)
    hdr = [["Aggregation", "TON_IoT", "", "", "CICIoT2023", "", ""],
           ["", "IID", "$\\alpha$=1.0", "$\\alpha$=0.1", "IID", "$\\alpha$=1.0", "$\\alpha$=0.1"]]
    m.table(hdr, rows, "Multi-class macro-F1 of the federated detector without attacks (mean ± half-width of the 95% "
            "bootstrap confidence interval over 10 seeds; test split).", col_widths=[1.6, 0.9, 0.9, 0.9, 0.9, 0.9, 0.9],
            label="flclean", header_rows=2, align=["left"] + ["center"] * 6,
            notes="Centralised: one model trained on the pooled training data with the same number of gradient steps.")


def table_fl_poison(m, S):
    e2, e2n = S["fl"]["E2"], S["fl"]["E2n"]
    rows = []
    for ag in AGG:
        r = [("**" + AGG_LAB[ag] + "**") if ag == "ta" else AGG_LAB[ag]]
        for ds in ("ton", "cic"):
            for src, att in ((e2, "lf"), (e2, "sf"), (e2n, "lf"), (e2n, "sf")):
                k = f"{ds}|{att}|2|{ag}"
                r.append(f"{100 * src[k]['detect_rate'][0]:.1f} / {src[k]['macro_f1'][0]:.2f}" if k in src else "–")
        rows.append(r)
    hdr = [["Aggregation", "TON_IoT", "", "", "", "CICIoT2023", "", "", ""],
           ["", "LF, $\\alpha$=1", "MP, $\\alpha$=1", "LF, $\\alpha$=0.1", "MP, $\\alpha$=0.1",
            "LF, $\\alpha$=1", "MP, $\\alpha$=1", "LF, $\\alpha$=0.1", "MP, $\\alpha$=0.1"]]
    m.table(hdr, rows, "Attack detection rate (%) / macro-F1 with two malicious clients out of 12 (mean over 10 seeds). "
            "LF: targeted label flipping; MP: model poisoning with sign-flipped updates scaled by 4.",
            col_widths=[1.0] + [0.8] * 8, label="flpois", header_rows=2, align=["left"] + ["center"] * 8)


def table_fl_misspec(m, S):
    E2, E3 = S["fl"]["E2"], S["fl"]["E3"]
    rows = []
    for g, src, lab in (("krum", E2, "Krum, bound 3 (correct)"), ("krum", E3, "Krum, bound 1"),
                        ("mkrum", E2, "Multi-Krum, bound 3 (correct)"), ("mkrum", E3, "Multi-Krum, bound 1"),
                        ("trmean", E2, "Trimmed mean, bound 3 (correct)"), ("trmean", E3, "Trimmed mean, bound 1"),
                        ("ta", E2, "**Trust-aware (no bound)**")):
        r = [lab]
        for ds in ("ton", "cic"):
            for att in ("lf", "sf"):
                k = f"{ds}|{att}|3|{g}"
                r.append(f"{100 * src[k]['detect_rate'][0]:.1f} / {src[k]['macro_f1'][0]:.2f}" if k in src else "–")
        rows.append(r)
    hdr = [["Aggregation (assumed Byzantine clients)", "TON_IoT", "", "CICIoT2023", ""],
           ["", "LF", "MP", "LF", "MP"]]
    m.table(hdr, rows, "Attack detection rate (%) / macro-F1 with three malicious clients out of 12 ($\\alpha$ = 1.0, mean "
            "over 10 seeds) when the Byzantine bound of Krum, Multi-Krum and the trimmed mean is correct (3) or "
            "underestimated (1). LF: label flipping; MP: model poisoning.", col_widths=[2.4, 1.0, 1.0, 1.0, 1.0],
            label="flmis", header_rows=2, align=["left"] + ["center"] * 4)


def results(m, S):
    d = S["d"]
    D = S["data"]
    m.heading("5. Results", 1)
    # 5.1 audit
    m.heading("5.1 Data quality and leakage audit", 2)
    e = D["edge"]; t = D["ton"]; c = D["cic"]
    ea = e["leakage_audit"]
    assert 0.4 < 1 - t["rows_after_dedup"] / t["rows_raw"] < 0.6, "'about half of the TON_IoT records': revise"
    m.para(f"Deduplication changed all three datasets substantially (Table {{tab:data}}). Once identifiers were "
           f"removed, about half of the TON_IoT records were duplicates or label conflicts, leaving "
           f"{t['rows_after_dedup']:,} unique flows, and "
           f"{c['label_conflicts_removed']:,} CICIoT2023 flows had feature vectors that also occur under another "
           f"label. Edge-IIoTset was affected most. After identifiers and the placeholder artefact were removed, only "
           f"{e['rows_after_dedup']:,} of {e['rows_raw']:,} records remained unique, {e['label_conflicts_removed']:,} "
           f"records ({100 * e['label_conflicts_removed'] / e['rows_raw']:.0f}%) shared their feature vector with a "
           f"record of a different class, and only {e['class_counts'][e['classes'][0]]:,} normal records were left. "
           f"Several attack classes shrank to fewer than ten records. A detector can still reach "
           f"{100 * ea['majority_baseline']:.1f}% binary accuracy on what remains by predicting 'attack' for every flow, "
           "so any accuracy figure would describe the class ratio rather than detection. We therefore do not report "
           "detector benchmarks on Edge-IIoTset; the near-perfect scores often published for this subset probably "
           "owe much to the identifier and placeholder fields [@galal2026provenance]. TON_IoT and CICIoT2023 "
           f"passed the audit: the best single feature separates attack from benign traffic with "
           f"{100 * t['leakage_audit']['max']:.1f}% and {100 * c['leakage_audit']['max']:.1f}% accuracy, against majority "
           f"baselines of {100 * t['leakage_audit']['majority_baseline']:.1f}% and "
           f"{100 * c['leakage_audit']['majority_baseline']:.1f}%.")
    # 5.2 clean FL
    m.heading("5.2 Federated detection without attacks", 2)
    m.label_next("fig", "flclean")
    m.label_next("tab", "flclean")
    m.para(S["txt_fl_clean"])
    m.figure(os.path.join(FIG, "fig6_fl_clean.png"), S["cap_fl_clean"], width_in=6.3, label="flclean")
    table_fl_clean(m, S)
    # 5.3 poisoning
    m.heading("5.3 Robustness to poisoned federations", 2)
    m.label_next("fig", "flpois")
    m.label_next("tab", "flpois")
    m.para(S["txt_fl_pois"])
    m.figure(os.path.join(FIG, "fig7_fl_poisoning.png"), S["cap_fl_pois"], width_in=6.3, label="flpois")
    table_fl_poison(m, S)
    m.para(S["txt_fl_pois2"])
    m.label_next("tab", "flmis")
    m.para(S["txt_fl_pois3"])
    table_fl_misspec(m, S)
    # 5.4-5.7: city, ablation, PQC, twin and scalability
    for blk in S["city_blocks"]:
        blk(m, S)


def discussion(m, S):
    m.heading("6. Discussion", 1)
    for h, paras in S["discussion"]:
        m.heading(h, 2)
        for p in paras:
            m.para(p)


def conclusions(m, S):
    m.heading("7. Conclusions", 1)
    for p in S["conclusions"]:
        m.para(p)
