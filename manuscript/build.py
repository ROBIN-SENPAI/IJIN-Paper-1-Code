# -*- coding: utf-8 -*-
"""Build IJIN_formatted.docx from the section modules and the result files (no number is typed by hand)."""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, ".."))
from docxkit import Manuscript  # noqa: E402
from refs import REFS  # noqa: E402
import sections_front as SF  # noqa: E402
import sections_method as SM  # noqa: E402
import sections_exp as SE  # noqa: E402
import sections_results as SR  # noqa: E402
import sections_end as SN  # noqa: E402

RES = r"E:\A-PQZTO_work\results"
OUT_DIR = os.environ.get("APQ_OUT", r"E:\A-PQZTO_work\out")


def load_S():
    from apq.data import prepare
    S = {"data": {k: prepare(k)["info"] for k in ("ton", "edge", "cic")}}
    S["fl"] = json.load(open(os.path.join(RES, "fl_summary.json")))
    S["city"] = json.load(open(os.path.join(RES, "city_summary.json")))
    p = os.path.join(RES, "pqc_summary.json")
    S["pqc"] = json.load(open(p)) if os.path.exists(p) else None
    p = os.path.join(RES, "city_extra_summary.json")
    S["city_extra"] = json.load(open(p)) if os.path.exists(p) else None
    p = os.path.join(RES, "stress_summary.json")
    S["stress"] = json.load(open(p)) if os.path.exists(p) else None
    S["n_fl_runs"] = S["fl"].get("n_runs", 1560)
    S.update(SR.derive(S))
    import narr_fl, narr_city, narr_pqc, narr_stress, narr_end  # noqa: E401
    S.update(narr_fl.build(S))
    S["city_blocks"] = [narr_city.block_main, narr_city.block_ablation, narr_pqc.block, narr_stress.block]
    S.update(narr_end.build(S))      # discussion, conclusions, abstract, highlights, cover_claims
    return S


def one_pass(S, prelabels=None):
    m = Manuscript(REFS, font="Times New Roman", size=10, spacing=2.0, line_numbers=False, prelabels=prelabels,
                   cite_style="elsevier", align="left", page="Letter", margins_cm=1.83)
    SF.front(m, S)
    SF.abstract(m, S)
    SF.introduction(m, S)
    SF.related_work(m, S)
    SM.framework(m, S)
    SE.experimental_design(m, S)
    SR.results(m, S)
    SR.discussion(m, S)
    SR.conclusions(m, S)
    SN.statements(m, S)
    m.references()
    return m


def build(path=None):
    S = load_S()
    m1 = one_pass(S)
    m = one_pass(S, prelabels=dict(m1.labels))
    os.makedirs(OUT_DIR, exist_ok=True)
    path = path or os.path.join(OUT_DIR, "IJIN_formatted.docx")
    m.save(path, title=SF.TITLE)
    info = dict(path=path, figs=m.fig_n, tabs=m.tab_n, eqs=m.eq_n, refs=len(m.cite_order),
                uncited=[k for k in REFS if k not in m.cite_order], abstract_words=len(S["abstract"].split()),
                fig_files=m.fig_files)
    return info, S, m


if __name__ == "__main__":
    info, S, m = build()
    print(json.dumps({k: v for k, v in info.items() if k != "fig_files"}, indent=1))
