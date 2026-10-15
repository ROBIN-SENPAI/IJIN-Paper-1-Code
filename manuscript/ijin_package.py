# -*- coding: utf-8 -*-
"""Assemble the IJIN (International Journal of Intelligent Networks, KeAi/Elsevier) submission package.

    package(dest_dir, info, S, checks, highlights, pdf_path=None, dry_run=False)

Inputs
  dest_dir    folder that receives the package (normally the authors' journal folder).
  info        dict returned by build.build(): path (the built IJIN_formatted.docx), figs, tabs, eqs, refs, uncited,
              abstract_words, fig_files = [(n, source_path, width_in), ...] in order of appearance.
              Optional: original_path (default ORIGINAL), graphical_abstract (path of a new GA file, if any).
  S           build state; uses S["cover_claims"] (2-3 sentences) and S["n_fl_runs"].
  checks      dict returned by ijin_check.verify(path, pdf_path).
  highlights  list of 3-5 strings, each <= 85 characters including spaces.
  pdf_path    optional PDF rendering of IJIN_formatted.docx (copied as IJIN_formatted.pdf).
  dry_run     True: write to DRYRUN_DIR instead of dest_dir; any of info/S/checks/highlights given as None is
              replaced by fake inputs (fake original + fake formatted docx built with python-docx, real figure files).

Outputs in dest_dir
  backup/<original stem>_original_backup.docx   byte-identical copy of the original manuscript
  IJIN_formatted.docx (+ IJIN_formatted.pdf)
  IJIN_Figures/Fig_N.tif                        RGB, LZW, same pixel size and source dpi
  IJIN_Highlights.docx, IJIN_Cover_Letter.docx
  IJIN_formatting_report.txt                    Arabic, UTF-8 with BOM

Nothing else in dest_dir is created, modified or deleted: every write goes through _Writer, which only accepts the
file names above, and the original manuscript is hashed before and after packaging.
"""
import argparse
import collections
import datetime
import hashlib
import json
import os
import re
import shutil
import string
import sys
import zipfile

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Pt
from docx.text.paragraph import Paragraph
from lxml import etree
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
WORK = r"E:\A-PQZTO_work"
USER_DIR = (r"C:\Users\ROBIN\OneDrive\Desktop\البحث الاول - Computer Networks - Risk-Adaptive"
            r"\Intelligence Networks- المجلة الثانية")
ORIGINAL = os.path.join(USER_DIR, "Risk-Adaptive - ntelligence Networks  .docx")
IJIN_COVER = os.path.join(USER_DIR, "coverletter.docx")
CN_COVER = os.path.join(USER_DIR, "cover letter .docx")
CREDIT_FILE = os.path.join(USER_DIR, "CRediT author statement.docx")
OLD_HIGHLIGHTS = os.path.join(USER_DIR, "Highlights .docx")
LIMITATIONS_FILE = os.path.join(USER_DIR, "Limitations and Future Work .docx")
FORMATTED_SRC = os.path.join(WORK, "out", "IJIN_formatted.docx")
VERIFIED_REFS = os.path.join(WORK, "refs", "verified_refs.json")
DRYRUN_DIR = os.path.join(WORK, "out", "package_dryrun")

TITLE = ("Risk-Adaptive Post-Quantum Zero-Trust Orchestration for Smart-City IoT: Architecture and Reproducible "
         "Evaluation")
JOURNAL = "International Journal of Intelligent Networks"

OUT_DOCX, OUT_PDF = "IJIN_formatted.docx", "IJIN_formatted.pdf"
FIG_DIR, BACKUP_DIR = "IJIN_Figures", "backup"
OUT_HL, OUT_COVER, OUT_REPORT = "IJIN_Highlights.docx", "IJIN_Cover_Letter.docx", "IJIN_formatting_report.txt"
ALLOWED = [re.escape(BACKUP_DIR) + r"\\[^\\]+_original_backup\.docx", re.escape(OUT_DOCX), re.escape(OUT_PDF),
           re.escape(FIG_DIR) + r"\\Fig_\d+\.tif", re.escape(OUT_HL), re.escape(OUT_COVER), re.escape(OUT_REPORT)]

HL_MIN, HL_MAX, HL_CHARS = 3, 5, 85
STRICT_HIGHLIGHT_NUMBERS = True  # every number in a highlight must occur in the manuscript text
FONT = "Times New Roman"
# Elsevier general artwork guidance (minimum resolution at final size)
DPI_HALFTONE, DPI_COMBINATION, DPI_LINEART = 300, 500, 1000

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
M = "{http://schemas.openxmlformats.org/officeDocument/2006/math}"
WP = "{http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing}"
WE = "{http://schemas.microsoft.com/office/webextensions/webextension/2010/11}"
DC = "{http://purl.org/dc/elements/1.1/}"
CP = "{http://schemas.openxmlformats.org/package/2006/metadata/core-properties}"

TAG_AUTHOR = "[AUTHOR INFORMATION REQUIRED]"
TAG_CREDIT = "[CRediT AUTHOR CONTRIBUTIONS REQUIRED]"
TAG_AI = "[AI USE DECLARATION REQUIRES AUTHOR CONFIRMATION]"
TAG_ETHICS = "[ETHICS INFORMATION REQUIRED FROM AUTHORS]"
TAG_METHOD = "[METHODOLOGICAL DETAIL REQUIRED]"
TAG_CAPTION = "[CAPTION OR SOURCE REQUIRED]"

# --------------------------------------------------------------------------------------------- cover letter
# Fallbacks only: the authors' own sentences are read verbatim from their IJIN cover letter (IJIN_COVER) at run time.
AUTHOR_ORIGINALITY = ("We confirm that this manuscript is original, has not been published elsewhere, and is not under "
                      "consideration by another journal. All authors have approved the submission.")
AUTHOR_SCOPE = ("We believe this manuscript aligns well with the scope of the International Journal of Intelligent "
                "Networks, particularly its focus on communication network architectures and security, wireless "
                "communication and network protocols, intelligent computing for sustainable and connected systems, "
                "distributed security, and artificial intelligence for networking. The integration of post-quantum "
                "cryptography and zero-trust principles into a network-centric decision loop contributes directly to "
                "the development of secure and intelligent communication networks for heterogeneous IoT environments.")
AUTHOR_THANKS = "Thank you for considering our work. We look forward to your feedback."
AUTHOR_CLOSING = ["Sincerely,", "Firas H. K. Al-Fadhli", "Department of Research and Development",
                  "Ministry of Higher Education and Scientific Research", "Baghdad, Iraq",
                  "Email: firas.hameed@mohesr.edu.iq"]

COVER_TEMPLATE = """The Editor-in-Chief
{journal}

Dear Editor-in-Chief,

I am pleased to submit our manuscript entitled \u201c{title}\u201d for consideration in the {journal}. The paper introduces A-PQZTO, an orchestration architecture that combines adaptive zero-trust policy, post-quantum authentication, federated threat intelligence and digital-twin validation of containment actions for 6G-oriented smart-city IoT networks.

Existing studies often treat post-quantum cryptography, zero trust, federated learning and digital twins separately. In A-PQZTO, the trust score of a device is computed only from evidence about that device; post-quantum cost and slice latency budgets decide when stronger authentication is affordable, and the digital twin checks cluster-wide actions before they are enforced. The evaluation is based on measured data: {n_fl_runs} federated training runs on public IoT intrusion-detection datasets, a city-scale simulation driven by real detector outputs, and measurements of post-quantum primitives and hybrid post-quantum TLS 1.3 handshakes. The main findings are:

{claims}

{scope}

{originality}

{thanks}

{closing}"""
COVER_FORBIDDEN = ("competing", "conflict of interest", "conflicts of interest", "funding", "ethic", "no conflict")

# one-line notes (Arabic) for the original references whose metadata was corrected; key = original number
REF_NOTES_AR = {
    16: "أُضيف نطاق الصفحات 1889–1899 وDOI والاسم الكامل لمجلة Sinkron.",
    17: "أُضيف رقم المجلد 132 وDOI (Comput. Secur. 2023، المقال 103381).",
    18: "صُحّحت السنة من 2023 إلى 2024، وأُضيف المجلد 153 والصفحات 182–192 وDOI.",
    19: "أُضيف محررو الكتاب والصفحات 229–251 ومكان النشر (Boca Raton) وDOI لفصل CRC Press.",
    20: "أُضيف المجلد 161 والصفحات 701–713 وDOI.",
    21: "أُضيفت الصفحات 2167–2172 وDOI لبحث مؤتمر ICC 2024.",
    22: "صُحّح العنوان إلى \"...in IoT Environment\" بالمفرد (لا Environments)، وأُضيف DOI.",
    23: "المقال لمؤلف واحد هو N. Moustafa؛ حُذف \"M. Ahmed, S. Ahmed\" غير الموجودين في السجل، وأُضيف المجلد 72 "
        "والرقم 102994 وDOI.",
    25: "كان المرجع نسخة arXiv (2402.00790) رُفعت عام 2024 لمقال منشور عام 2020؛ استُبدلت بالنسخة المحكّمة "
        "IEEE Internet Things J. 7 (7) (2020) 6457–6480.",
    26: "خطأ في نسبة المؤلف: لا يوجد مقال لـ M.A. Ferrag في Informatica؛ المقال المطابق للعنوان هو لـ S. Vashisth "
        "وA. Goyal، Informatica 49 (17) (2025) — على المؤلفين تأكيد أنه المقصود.",
    27: "اسم المجلة خاطئ: المقال منشور في Applied System Innovation 5 (3) (2022) 56 وليس في Journal of Autonomous "
        "Intelligence، وكان العنوان مبتورًا.",
    28: "كان المرجع بلا مؤلفين: أُضيف المؤلفون الستة، وصُحّحت السنة إلى 2026 (Sci. Rep. 16، المقال 2683).",
    29: "أُضيف المجلد 6 ورقم المقال 1655410 وDOI.",
    31: "صُحّح اسم المؤلف المشارك إلى Chafic (لا Chadic)، وأُكملت بيانات العدد الخاص 4 والصفحات 1541–1573 وDOI.",
}


# ============================================================================================= small helpers
def _sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def _same(a, b):
    try:
        return os.path.samefile(a, b)
    except OSError:
        return False


class _Slots(dict):
    def __missing__(self, k):
        return f"⟦قيمة غير متوفرة: {k}⟧"


def _fill(tpl, slots):
    """Fill {slot} placeholders; a missing slot is rendered as a clearly marked gap instead of raising."""
    return string.Formatter().vformat(tpl, (), _Slots({k: str(v) for k, v in slots.items()}))


def _num(x):
    return f"{x:,}" if isinstance(x, int) else str(x)


def _mb(n):
    return f"{n / 2 ** 20:.1f} MB" if n >= 2 ** 20 else f"{max(1, round(n / 1024))} KB"


class _Writer:
    """Single gate for every file written into dest_dir: only the package names in ALLOWED are accepted, and the
    protected files (original manuscript and the authors' documents) can never be targets."""

    def __init__(self, dest, protected):
        self.dest = os.path.abspath(dest)
        self.protected = [os.path.abspath(p) for p in protected if p]
        self.created = []

    def target(self, rel):
        rel = rel.replace("/", "\\")
        if not any(re.fullmatch(p, rel) for p in ALLOWED):
            raise PermissionError(f"refusing to write a non-package file: {rel}")
        p = os.path.abspath(os.path.join(self.dest, rel))
        if os.path.commonpath([p, self.dest]) != self.dest:
            raise PermissionError(f"refusing to write outside dest_dir: {p}")
        for q in self.protected:
            if os.path.normcase(p) == os.path.normcase(q) or (os.path.exists(p) and _same(p, q)):
                raise PermissionError(f"refusing to overwrite a protected file: {p}")
        os.makedirs(os.path.dirname(p), exist_ok=True)
        return p

    def done(self, p):
        if p not in self.created:
            self.created.append(p)


def _xml_paragraph_texts(root):
    """Text of every w:p (in document order, including table cells), with math text (m:t) included."""
    out = []
    for p in root.iter(W + "p"):
        out.append("".join((t.text or "") for t in p.iter() if t.tag in (W + "t", M + "t")))
    return out


def _docx_text(path):
    with zipfile.ZipFile(path) as z:
        root = etree.fromstring(z.read("word/document.xml"))
    return "\n".join(_xml_paragraph_texts(root))


def _docx_paragraphs(path):
    """Non-empty paragraph texts of a small docx (cover letters, CRediT, highlights); read-only."""
    if not path or not os.path.exists(path):
        return None
    return [p.text for p in Document(path).paragraphs if p.text.strip()]


# ============================================================================================= scans
def scan_original(path):
    """Read-only structural scan of the original manuscript (zip + XML, the file is never opened for writing)."""
    R = {"path": path, "name": os.path.basename(path), "size": os.path.getsize(path), "sha256": _sha(path)}
    with zipfile.ZipFile(path) as z:
        names = z.namelist()
        root = etree.fromstring(z.read("word/document.xml"))
        sty = {}
        if "word/styles.xml" in names:
            for s in etree.fromstring(z.read("word/styles.xml")).iter(W + "style"):
                nm = s.find(W + "name")
                sty[s.get(W + "styleId")] = (nm.get(W + "val") if nm is not None else s.get(W + "styleId")) or ""
        R["comments"] = 0
        if "word/comments.xml" in names:
            R["comments"] = sum(1 for _ in etree.fromstring(z.read("word/comments.xml")).iter(W + "comment"))
        R["webextensions"] = []
        for n in names:
            if re.fullmatch(r"word/webextensions/webextension\d*\.xml", n):
                e = etree.fromstring(z.read(n))
                ref = e.find(WE + "reference")
                R["webextensions"].append({"part": n, "store_id": ref.get("id") if ref is not None else "",
                                           "properties": [p.get("name") for p in e.iter(WE + "property")]})
        R["core_author"] = R["core_last_modified_by"] = ""
        if "docProps/core.xml" in names:
            c = etree.fromstring(z.read("docProps/core.xml"))
            a, lm = c.find(DC + "creator"), c.find(CP + "lastModifiedBy")
            R["core_author"] = (a.text or "") if a is not None else ""
            R["core_last_modified_by"] = (lm.text or "") if lm is not None else ""
        R["footnotes_parts"] = [n for n in names if n in ("word/footnotes.xml", "word/endnotes.xml")]
        R["media"] = [n for n in names if n.startswith("word/media/")]
    body = root.find(W + "body")
    heads, figcap, tabcap, texts = [], {}, {}, []
    for p in body.iter(W + "p"):
        txt = "".join((t.text or "") for t in p.iter(W + "t")).strip()
        ps = p.find(W + "pPr/" + W + "pStyle")
        sname = sty.get(ps.get(W + "val"), ps.get(W + "val")) if ps is not None else ""
        mlev = re.match(r"heading (\d)", sname or "", re.I)
        if mlev and txt:
            heads.append((int(mlev.group(1)), txt))
        mf = re.match(r"Fig(?:ure)?\.?\s*(\d+)\.\s*(.*)", txt)
        if mf:
            figcap.setdefault(int(mf.group(1)), mf.group(2))
        mt = re.match(r"Table\s*(\d+)\.\s*(.*)", txt)
        if mt:
            tabcap.setdefault(int(mt.group(1)), mt.group(2))
        if txt:
            texts.append(txt)
    R["title"] = texts[0] if texts else ""
    R["keywords"] = next((t for t in texts if t.lower().startswith("keywords")), "")
    R["headings"], R["fig_captions"], R["table_captions"] = heads, figcap, tabcap
    R["graphical_abstract"] = any("graphical abstract" in t.lower() for _, t in heads)
    R["drawings"] = sum(1 for _ in body.iter(W + "drawing"))
    R["anchored"] = sum(1 for _ in body.iter(WP + "anchor"))
    R["tables"] = sum(1 for _ in body.iter(W + "tbl"))
    R["math"] = sum(1 for _ in body.iter(M + "oMath"))
    R["math_para"] = sum(1 for _ in body.iter(M + "oMathPara"))
    R["tracked"] = sum(1 for e in body.iter() if e.tag in (W + "ins", W + "del", W + "moveFrom", W + "moveTo"))
    R["ole"] = sum(1 for e in body.iter() if e.tag in (W + "object", W + "pict"))
    R["textboxes"] = sum(1 for _ in body.iter(W + "txbxContent"))
    cols = [int(c.get(W + "num", "1")) for c in body.iter(W + "cols")]
    R["max_cols"] = max(cols) if cols else 1
    R["ai_addin"] = any("claude" in (p or "").lower() for w in R["webextensions"] for p in w["properties"])
    return R


def inspect_formatted(path):
    """Facts about the built manuscript that the report quotes (all read from the file, none typed by hand)."""
    d = Document(path)
    F = {}
    st = d.styles["Normal"]
    F["font"] = st.font.name
    F["size"] = st.font.size.pt if st.font.size else None
    F["spacing"] = st.paragraph_format.line_spacing
    sec = d.sections[0]
    F["page"] = f"{sec.page_width.inches:.2f} × {sec.page_height.inches:.2f} in"
    F["margins_cm"] = f"{sec.left_margin.cm:.2f}"
    heads, tags_at, cur = [], [], ""
    corr, first = "", ""
    tags = (TAG_AUTHOR[:-1], TAG_METHOD, TAG_CAPTION, TAG_AI, TAG_CREDIT, TAG_ETHICS)
    for el in d.element.body.iterchildren():
        if el.tag == W + "p":
            p = Paragraph(el, d)
            txt = p.text
            if not first and txt.strip():
                first = txt.strip()
            if p.style.name.startswith("Heading"):
                heads.append((p.style.name, txt))
                cur = txt
            if "Corresponding author" in txt and not corr:
                corr = txt
            chunks = [txt]
        elif el.tag == W + "tbl":
            chunks = _xml_paragraph_texts(el)
        else:
            continue
        for c in chunks:
            for t in tags:
                pat = re.escape(t) + ("" if t.endswith("]") else r"(?::\s*([^\]]*))?\]")
                for m in re.finditer(pat, c):
                    what = (m.group(1) or "").strip() if m.lastindex else ""
                    tags_at.append((t if t.endswith("]") else t + "]", cur or "(صفحة العنوان)", what))
    F["title"], F["corr"] = first, corr
    F["headings"] = heads
    F["h_counts"] = collections.Counter(s for s, _ in heads)
    F["h1"] = [t for s, t in heads if s == "Heading 1"]
    kw = next((p.text for p in d.paragraphs if p.text.startswith("Keywords")), "")
    F["keywords"] = [k.strip() for k in kw.split(":", 1)[1].split(";") if k.strip()] if ":" in kw else []
    F["tags_at"] = tags_at
    full = _docx_text(path)
    F["text"] = full
    F["n_AL"], F["n_Al"] = full.count("AL-Fadhli"), full.count("Al-Fadhli")
    low = [t.lower() for t in F["h1"]]
    F["has_credit"] = any("credit" in t for t in low)
    F["has_ai_decl"] = any("generative ai" in t or "ai-assisted" in t for t in low)
    F["has_ethics"] = any("ethic" in t for t in low)
    F["has_competing"] = any("competing" in t for t in low)
    F["has_ga"] = any("graphical abstract" in t.lower() for _, t in heads)
    F["limitations"] = [t for _, t in heads if "limitation" in t.lower()]
    F["eq_tables"] = sum(1 for t in d.tables if t._tbl.find(".//" + M + "oMathPara") is not None)
    F["tables_total"] = len(d.tables)
    F["anchored"] = sum(1 for _ in d.element.body.iter(WP + "anchor"))
    F["ole"] = sum(1 for e in d.element.body.iter() if e.tag in (W + "object", W + "pict"))
    F["textboxes"] = sum(1 for _ in d.element.body.iter(W + "txbxContent"))
    refs, inref = {}, False
    for p in d.paragraphs:
        if p.style.name.startswith("Heading") and p.text.strip() == "References":
            inref = True
            continue
        if inref:
            m = re.match(r"\[(\d+)\]\s*(.*)", p.text.strip())
            if m:
                refs[m.group(2).strip()] = int(m.group(1))
    F["reflist"] = refs
    return F


# ============================================================================================= figures
def _clean_dpi(dpi):
    """PNG stores whole pixels per metre, so 400 dpi comes back as 399.9992 and 220 dpi as 219.9894; a value within one
    pixel-per-metre step (0.0254 dpi) of an integer is that integer."""
    if not dpi:
        return None
    out = []
    for v in dpi[:2]:
        v = float(v)
        out.append(int(round(v)) if abs(v - round(v)) <= 0.0254 else round(v, 4))
    return tuple(out) if out[0] > 0 else None


def _to_rgb(im):
    """RGB without loss of pixels: transparent areas are composited onto white (dropping alpha would turn them black)."""
    flattened = False
    if im.mode == "P":
        im = im.convert("RGBA" if "transparency" in im.info else "RGB")
    if im.mode in ("RGBA", "LA", "PA"):
        im = im.convert("RGBA")
        a = im.getchannel("A")
        flattened = a.getextrema()[0] < 255
        bg = Image.new("RGB", im.size, (255, 255, 255))
        bg.paste(im, mask=a)
        return bg, flattened
    if im.mode == "I;16" or im.mode == "I":
        im = im.point(lambda x: x * (1 / 256)).convert("L")
    return (im if im.mode == "RGB" else im.convert("RGB")), flattened


def _fig_origin(path, orig_caps):
    base = os.path.basename(path)
    m = re.match(r"fig(\d+)_", base, re.I)
    on = int(m.group(1)) if m else None
    kept = os.path.basename(os.path.dirname(os.path.abspath(path))).lower() == "original"
    return kept, on, (orig_caps.get(on, "") if on else "")


def export_figures(fig_files, wr, orig_caps):
    ns = [n for n, _, _ in fig_files]
    if ns != list(range(1, len(ns) + 1)):
        raise ValueError(f"fig_files are not numbered 1..N in order of appearance: {ns}")
    rows = []
    for n, src, width_in in fig_files:
        with Image.open(src) as im:
            im.load()
            mode, (w, h), dpi_raw, icc = im.mode, im.size, im.info.get("dpi"), im.info.get("icc_profile")
            rgb, flattened = _to_rgb(im)
        dpi = _clean_dpi(dpi_raw)
        eff = w / float(width_in)
        dpi_note = "source"
        if dpi is None:  # no resolution stored in the source: tag the TIFF with its resolution at the inserted width
            dpi, dpi_note = (int(round(eff)), int(round(eff))), "effective (source had none)"
        out = wr.target(f"{FIG_DIR}\\Fig_{n}.tif")
        kw = {"compression": "tiff_lzw", "dpi": dpi}
        if icc:
            kw["icc_profile"] = icc
        rgb.save(out, format="TIFF", **kw)
        wr.done(out)
        with Image.open(out) as chk:
            ok = (chk.size == (w, h) and chk.mode == "RGB" and chk.info.get("compression") == "tiff_lzw")
            got_dpi = _clean_dpi(chk.info.get("dpi"))
        if not ok:
            raise RuntimeError(f"TIFF check failed for Fig. {n}: {out}")
        kept, on, cap = _fig_origin(src, orig_caps)
        rows.append(dict(n=n, src=src, out=out, w=w, h=h, mode=mode, dpi=dpi, dpi_note=dpi_note, tif_dpi=got_dpi,
                         width_in=float(width_in), height_in=float(width_in) * h / w, eff=eff, flattened=flattened,
                         kept=kept, orig_no=on, orig_cap=cap, bytes=os.path.getsize(out)))
    return rows


# ============================================================================================= highlights
def validate_highlights(highlights, manuscript_text=None):
    items = [h.strip() for h in (highlights or [])]
    if not HL_MIN <= len(items) <= HL_MAX:
        raise ValueError(f"Highlights must have {HL_MIN}-{HL_MAX} bullet points; got {len(items)}.")
    for h in items:
        if not h:
            raise ValueError("Empty highlight.")
        if len(h) > HL_CHARS:
            raise ValueError(f"Highlight longer than {HL_CHARS} characters ({len(h)}): {h!r}")
    if len(set(items)) != len(items):
        raise ValueError("Duplicate highlight.")
    if STRICT_HIGHLIGHT_NUMBERS and manuscript_text is not None:
        body = manuscript_text.replace(",", "")
        for h in items:
            for num in re.findall(r"\d[\d,]*(?:\.\d+)?", h):
                if num.replace(",", "") not in body:
                    raise ValueError(f"Highlight number {num!r} does not occur in the manuscript text: {h!r}")
    return items


def _style_font(style, size, bold=None):
    style.font.name = FONT
    style.font.size = Pt(size)
    if bold is not None:
        style.font.bold = bold
    rpr = style.element.get_or_add_rPr()
    rf = rpr.find(qn("w:rFonts"))
    if rf is None:
        rf = OxmlElement("w:rFonts")
        rpr.insert(0, rf)
    for a in ("w:ascii", "w:hAnsi", "w:eastAsia", "w:cs"):
        rf.set(qn(a), FONT)
    for a in ("w:asciiTheme", "w:hAnsiTheme", "w:eastAsiaTheme", "w:cstheme"):
        if rf.get(qn(a)) is not None:
            del rf.attrib[qn(a)]


def _run(p, text, size, bold=False):
    r = p.add_run(text)
    r.font.name = FONT
    r.font.size = Pt(size)
    r.bold = True if bold else None
    rpr = r._r.get_or_add_rPr()
    rf = rpr.find(qn("w:rFonts"))
    for a in ("w:eastAsia", "w:cs"):
        rf.set(qn(a), FONT)
    return r


def _clean_core(doc, title):
    cp = doc.core_properties
    cp.author = cp.last_modified_by = cp.comments = ""
    cp.title = title


def write_highlights(path, items):
    doc = Document()
    _style_font(doc.styles["Normal"], 11)
    _style_font(doc.styles["List Bullet"], 11)
    t = doc.add_paragraph()
    t.alignment = WD_ALIGN_PARAGRAPH.LEFT
    t.paragraph_format.space_after = Pt(6)
    _run(t, "Highlights", 11, bold=True)
    for h in items:
        p = doc.add_paragraph(style="List Bullet")
        p.alignment = WD_ALIGN_PARAGRAPH.LEFT
        _run(p, h, 11)
    _clean_core(doc, "Highlights")
    doc.save(path)
    chk = Document(path)
    got = [p.text for p in chk.paragraphs if p.style.name == "List Bullet"]
    if got != items:
        raise RuntimeError("Highlights file check failed")


# ============================================================================================= cover letter
def authors_letter_parts(path=IJIN_COVER):
    """The authors' own sentences, verbatim from their IJIN cover letter (fallback constants if unreadable)."""
    paras = _docx_paragraphs(path)
    src = {"file": path if paras else None, "differs": []}
    if not paras:
        return dict(originality=AUTHOR_ORIGINALITY, scope=AUTHOR_SCOPE, thanks=AUTHOR_THANKS,
                    closing=list(AUTHOR_CLOSING)), src
    pick = lambda start, fb: next((p.strip() for p in paras if p.strip().startswith(start)), fb)
    parts = dict(originality=pick("We confirm that this manuscript is original", AUTHOR_ORIGINALITY),
                 scope=pick("We believe this manuscript aligns well", AUTHOR_SCOPE),
                 thanks=pick("Thank you for considering", AUTHOR_THANKS))
    k = next((i for i, p in enumerate(paras) if p.strip() == "Sincerely,"), None)
    parts["closing"] = [p.strip() for p in paras[k:]] if k is not None else list(AUTHOR_CLOSING)
    for key, fb in (("originality", AUTHOR_ORIGINALITY), ("scope", AUTHOR_SCOPE), ("thanks", AUTHOR_THANKS)):
        if parts[key] != fb:
            src["differs"].append(key)
    if parts["closing"] != AUTHOR_CLOSING:
        src["differs"].append("closing")
    return parts, src


def write_cover_letter(path, S, parts):
    claims = [c.strip() for c in (S.get("cover_claims") or [])]
    if not 2 <= len(claims) <= 3 or not all(claims):
        raise ValueError(f'S["cover_claims"] must hold 2-3 non-empty sentences; got {len(claims)}')
    n_runs = S.get("n_fl_runs")
    if not isinstance(n_runs, int):
        raise ValueError('S["n_fl_runs"] must be an int')
    slots = dict(journal=JOURNAL, title=TITLE, n_fl_runs=f"{n_runs:,}", claims="{claims}", scope=parts["scope"],
                 originality=parts["originality"], thanks=parts["thanks"], closing="{closing}")
    needed = {f for _, f, _, _ in string.Formatter().parse(COVER_TEMPLATE) if f}
    missing = needed - set(slots)
    if missing:
        raise KeyError(f"cover-letter template slots without a value: {sorted(missing)}")
    text = COVER_TEMPLATE.format(**slots)
    doc = Document()
    _style_font(doc.styles["Normal"], 12)
    _style_font(doc.styles["List Bullet"], 12)
    for block in text.split("\n\n"):
        if block == "{claims}":
            for c in claims:
                p = doc.add_paragraph(style="List Bullet")
                p.alignment = WD_ALIGN_PARAGRAPH.LEFT
                p.paragraph_format.space_after = Pt(4)
                _run(p, c, 12)
            continue
        lines = parts["closing"] if block == "{closing}" else block.split("\n")
        for j, line in enumerate(lines):
            p = doc.add_paragraph()
            p.alignment = WD_ALIGN_PARAGRAPH.LEFT
            p.paragraph_format.space_after = Pt(10 if j == len(lines) - 1 else 0)
            _run(p, line, 12)
    _clean_core(doc, "Cover letter")
    doc.save(path)
    full = "\n".join(p.text for p in Document(path).paragraphs)
    if f"\u201c{TITLE}\u201d" not in full:
        raise RuntimeError("cover letter: exact title missing")
    if parts["originality"] not in full or not all(line in full for line in parts["closing"]):
        raise RuntimeError("cover letter: authors' originality sentence or closing block not verbatim")
    bad = [w for w in COVER_FORBIDDEN if w in full.lower()]
    if bad:
        raise RuntimeError(f"cover letter contains a declaration the authors did not supply: {bad}")
    return full


# ============================================================================================= report
CHECK_SPEC = [
    ("reopen", "إعادة فتح IJIN_formatted.docx برمجيًا", "true"),
    ("justified_paragraphs", "فقرات مضبوطة على المحاذاة الكاملة Justify", "zero"),
    ("auto_hyphenation", "التقسيم الآلي للكلمات Hyphenation مفعّل", "false"),
    ("multi_column_sections", "أقسام متعددة الأعمدة", "zero"),
    ("heading_format_ok", "صيغة العناوين المرقّمة متسقة (1. / 2.1 / 2.1.1)", "true"),
    ("headings", "عدد العناوين بأنماط Heading", "count"),
    ("numbered_headings", "عدد العناوين المرقّمة", "count"),
    ("display_equations", "معادلات العرض القابلة للتحرير (oMathPara)", "info"),
    ("math_objects", "كائنات معادلات Word الأصلية (oMath)", "info"),
    ("images", "الصور المضمّنة في المستند", "info"),
    ("figure_captions", "أرقام عناوين الأشكال بالترتيب", "info"),
    ("figures_sequential", "ترقيم الأشكال متسلسل", "true"),
    ("figures_not_cited", "أشكال غير مُشار إليها في النص", "empty"),
    ("table_captions", "أرقام عناوين الجداول بالترتيب", "info"),
    ("tables_sequential", "ترقيم الجداول متسلسل", "true"),
    ("tables_not_cited", "جداول غير مُشار إليها في النص", "empty"),
    ("references_listed", "عدد المراجع في القائمة", "info"),
    ("citations_in_order", "المراجع مرقّمة حسب ترتيب أول ظهور في النص", "true"),
    ("cited_not_listed", "استشهادات في النص بلا مرجع في القائمة", "empty"),
    ("listed_not_cited", "مراجع في القائمة بلا استشهاد في النص", "empty"),
    ("tags", "وسوم المعلومات الناقصة داخل المخطوطة", "info"),
    ("leftover_placeholders", "عناصر نائبة غير محلولة (?? أو {fig:…})", "empty"),
    ("comments_part", "وجود جزء تعليقات في الملف", "false"),
    ("tracked_changes", "تغييرات متعقَّبة (w:ins / w:del)", "zero"),
    ("core_author", "اسم المؤلف في خصائص الملف (core properties)", "info"),
    ("pdf_pages", "عدد صفحات PDF", "info"),
    ("pdf_blank_pages", "صفحات PDF فارغة أو شبه فارغة", "empty"),
]


def _val(v):
    if isinstance(v, bool):
        return "نعم" if v else "لا"
    if isinstance(v, dict):
        return "؛ ".join(f"{k}: {x}" for k, x in v.items()) if v else "لا يوجد"
    if isinstance(v, (list, tuple)):
        return ", ".join(str(x) for x in v) if v else "لا يوجد"
    if v == "":
        return "(فارغ)"
    return str(v)


def render_checks(checks, extra):
    """✓/✗ lines from ijin_check.verify(...) plus the package's own checks (extra = [(ok, label, value)])."""
    lines, seen = [], set()
    for key, label, kind in CHECK_SPEC:
        if key not in checks:
            continue
        seen.add(key)
        v = checks[key]
        if key == "tags" and isinstance(v, dict):  # ijin_check counts "[AUTHOR INFORMATION REQUIRED" as a prefix
            v = {(k if k.endswith("]") else k + "]"): n for k, n in v.items()}
            lines.append(f"  • {label}: " + ("؛ ".join(f"{k} × {n}" for k, n in v.items()) if v else "لا يوجد"))
            continue
        if kind == "count":
            lines.append(f"  • {label}: {len(v)}")
            continue
        ok = {"true": v is True, "false": v is False, "zero": v == 0, "empty": not v}.get(kind)
        mark = "•" if ok is None else ("✓" if ok else "✗")
        lines.append(f"  {mark} {label}: {_val(v)}")
    for key in checks:
        if key not in seen:
            lines.append(f"  • {key}: {_val(checks[key])}")
    if extra:
        lines.append("")
        lines.append("  فحوص الحزمة نفسها:")
        for ok, label, value in extra:
            mark = "•" if ok is None else ("✓" if ok else "✗")
            lines.append(f"  {mark} {label}: {value}")
    return lines


REPORT_HEAD = """تقرير تنسيق المخطوطة — {journal} (IJIN)
ISSN 2666-6030 — KeAi Publishing / Elsevier
تاريخ الإنشاء: {date}
{dry_banner}
====================================================================================================

تنبيه أساسي: أُعيد بناء المخطوطة بطلب من المؤلفين
----------------------------------------------------------------------------------------------------
• بناءً على طلب صريح من المؤلفين، لم يقتصر العمل على التنسيق: أُعيد بناء المخطوطة (تجارب جديدة ونص أُعيدت كتابته)، مع الإبقاء على العنوان حرفيًا كما هو:
  "{title}"
  تطابق العنوان مع الأصل: {title_ok}
• لذلك لا تنطبق على هذه النسخة قاعدتا ملف التعليمات «لا تغيّر النتائج أو الأرقام» و«لا تعِد كتابة النص»: استُبدلت جميع النتائج العددية الأصلية بنتائج جديدة قابلة للتحقق تُقرأ من ملفات النتائج عند بناء المستند (build.py)، ويمكن إعادة توليدها من الشيفرة.
• المخطوطة الأصلية بنتائجها الأصلية محفوظة دون أي تعديل في النسخة الاحتياطية (البند 2).
• أرقام النسخة الجديدة كما بُنيت: عدد تشغيلات تدريب التعلّم الاتحادي = {n_fl_runs}؛ الأشكال = {n_figs}؛ الجداول = {n_tabs}؛ المعادلات المرقّمة = {n_eqs}؛ المراجع = {n_refs}.
"""

REPORT_ITEMS = """
1) اسم الملف الأصلي الذي تمت معالجته
----------------------------------------------------------------------------------------------------
• الاسم: {orig_name}
• المسار الكامل: {orig_path}
• الحجم: {orig_size} بايت — SHA-256: {orig_sha}
• محتواه (للمرجعية): الأقسام الرئيسية = {orig_h1}؛ الأشكال المرقّمة = {orig_figs}؛ الجداول المعنونة = {orig_tabs}؛ كائنات المعادلات = {orig_math}؛ ملخص رسومي مضمَّن: {orig_ga}.
• لم يُعدَّل الملف الأصلي ولم يُنقل ولم يُحذف؛ بصمته قبل التحزيم وبعده متطابقة: {orig_unchanged}.

2) نسخة الملف الاحتياطية التي تم إنشاؤها
----------------------------------------------------------------------------------------------------
• {backup_path}
• نسخة مطابقة بايتًا ببايت للأصل (SHA-256 متطابق): {backup_ok} {backup_state}

3) اسم الملف النهائي
----------------------------------------------------------------------------------------------------
• {final_docx}
{final_pdf}

4) التغييرات التنسيقية التي أجريت
----------------------------------------------------------------------------------------------------
• مستند Word قابل للتحرير وبعمود واحد (أقسام متعددة الأعمدة: {multi_col}).
• المحاذاة لليسار؛ لا فقرات مضبوطة على Justify (عددها: {justified}). التقسيم الآلي للكلمات غير مفعّل: {hyph_off}.
• أنماط Word للعناوين: Heading 1 = {n_h1}، Heading 2 = {n_h2}، Heading 3 = {n_h3}. الملخص غير مرقّم، والأقسام مرقّمة بصيغة «1. Introduction» و«2.1 …»؛ اتساق الصيغة: {heads_ok}.
• الخط {font} بحجم {size} pt، تباعد الأسطر {spacing}، الصفحة {page}، الهوامش {margins} سم. ملاحظة: دليل IJIN لا ينص على خط أو حجم أو هوامش؛ هذه اختيارات محايدة للبناء وليست متطلبات للمجلة، ويمكن تغييرها.
• صفحة العنوان: المؤلفون بترتيبهم الأصلي، والانتماءات بحروف مرتفعة (a، b)، والمؤلف المراسل بعلامة * مع بريده الإلكتروني.
• الملخص: {abstract_words} كلمة، بلا مراجع. الكلمات المفتاحية: {n_kw} (الحد الأقصى 6): {kw_list}
• المعادلات: كائنات معادلات Word أصلية (OMML) قابلة للتحرير (عدد الكائنات = {math_objects}، منها معادلات عرض مرقّمة = {display_eqs})، ولا توجد معادلات بصيغة صور.
• الجداول: قابلة للتحرير بنمط الخطوط الأفقية الثلاثة (بلا خطوط عمودية وبلا تظليل)، والعنوان «Table N.» فوق الجدول، والملاحظات أسفله.
• الأشكال: عنوان «Fig. N.» في فقرة نصية مستقلة أسفل الشكل (ليس داخل الصورة).
• المراجع: نمط رقمي بأقواس مربعة مثل [1] و[2,3] و[4–6]، مرتبة حسب أول ظهور، وبصيغة Elsevier الواردة في ملف التعليمات.
• Track Changes غير مفعّل ولا توجد تعليقات؛ {core_author_line}.
• ترقيم الصفحات في التذييل.

5) الأقسام التي أعيد ترتيبها
----------------------------------------------------------------------------------------------------
• بسبب إعادة البناء تغيّرت بنية الأقسام. الأقسام الرئيسية في الأصل:
{orig_h1_list}
• الأقسام الرئيسية في النسخة الجديدة:
{new_h1_list}
{sections_notes}

6) الجداول والأشكال التي تمت مراجعتها
----------------------------------------------------------------------------------------------------
• الجداول: العدد = {n_tabs}، وكلها قابلة للتحرير (أرقامها: {tab_caps})؛ الترقيم متسلسل: {tabs_seq}؛ جداول غير مُشار إليها: {tabs_uncited}.
  ملاحظة تقنية: المعادلات المرقّمة موضوعة في جداول تخطيط بلا حدود (1×3) عددها {eq_tables} لمحاذاة رقم المعادلة إلى اليمين؛ هذه ليست جداول بيانات ولا تحمل أرقام جداول.
• الأشكال: العدد = {n_figs} (أرقامها: {fig_caps})؛ الترقيم متسلسل: {figs_seq}؛ أشكال غير مُشار إليها: {figs_uncited}؛ مرات ظهور الوسم {tag_caption} = {n_tag_caption}.
• {fig_summary}
• صُدّر كل شكل بترتيب ظهوره إلى ملف TIFF منفصل في المجلد IJIN_Figures (RGB، ضغط LZW، بنفس عدد البكسلات ودقة المصدر دون أي تصغير):
{fig_table}
• مرجع الدقة (إرشادات Elsevier العامة للأشكال، بالحجم النهائي): {dpi_half} dpi للصور النصفية، {dpi_comb} dpi للأشكال المركبة (نص/خطوط مع ألوان)، {dpi_line} dpi للرسوم الخطية. لم تُرفع الدقة اصطناعيًا (إعادة التحجيم لا تضيف تفاصيل).
{dpi_notes}

7) مشكلات المراجع والاستشهادات
----------------------------------------------------------------------------------------------------
• تحقُّق كامل من كل مرجع في Crossref وصفحات الناشرين والهيئات المعيارية (التفاصيل: {refs_json}).
• من أصل {n_orig_refs} مرجعًا في المخطوطة الأصلية، كانت بيانات {n_corrected} مرجعًا خاطئة أو ناقصة وصُحّحت؛ وتأكدت صحة {n_verified} مرجعًا (أُضيف إليها DOI أو الشهر حيث لزم).
• المراجع المصحَّحة (الرقم الأصلي ← الرقم في النسخة الجديدة: الملاحظة):
{corrected_list}
• أُضيف {n_added} مرجعًا منهجيًا جديدًا (خوارزميات التجميع، الاختبارات الإحصائية، المعايير ومجموعات البيانات):
{added_list}
• تنبيه — احتمال نشر مكرر في المرجع [1] (Oliha et al.): المقال المستشهد به صحيح، لكن للمؤلفين أنفسهم مقالًا بعنوان مطابق في مجلة أخرى (Engineering Science & Technology Journal 5 (2) (2024) 496–506، doi:10.51594/estj.v5i2.827) نُشر قبله بثلاثة أيام. على المؤلفين التحقق وتقرير الإبقاء عليه.
• المرجع الأصلي [26]: نُسب في الأصل إلى M.A. Ferrag، والمقال الوحيد المطابق للعنوان هو لـ S. Vashisth وA. Goyal؛ على المؤلفين تأكيد أنه المقصود.
• ملاحظات تحقق ثانوية: نسختا arXiv (Hsu et al. 2019؛ Galal 2026) مُعلَّمتان صراحة كمطبوعات أولية؛ مسودة IETF استُبدلت بـ RFC 10024 بعد نشرها؛ سجل NeurIPS الرسمي لبحث Krum لا يذكر أرقام صفحات فلم تُضَف؛ الصفحة الأخيرة لمرجع Wilcoxon (83) من مصادر ببليوغرافية مستقلة؛ DOI كتاب Efron & Tibshirani يشير إلى نسخة CRC الإلكترونية المؤرخة 1994 بينما الطبعة الورقية 1993.
• أسماء المجلات اختُصرت حين يكون الاختصار القياسي مؤكدًا، وتُركت كاملة حيث لم يمكن تأكيده.
• مراجع من القائمة المتحقَّق منها لم يُستشهد بها في النص الجديد (لذلك لم تُدرج في القائمة): {uncited}
• مطابقة الاستشهادات والقائمة: المراجع في القائمة {references_listed}؛ الترتيب حسب أول ظهور: {cit_order}؛ استشهادات بلا مرجع: {cited_not_listed}؛ مراجع بلا استشهاد: {listed_not_cited}.

8) العناصر غير القابلة للتحرير
----------------------------------------------------------------------------------------------------
• الأشكال صور نقطية (PNG) بطبيعتها. جميع الأشكال العشرة مولَّدة بشيفرة (figs_concept.py وسكربتات التحليل) ويمكن إعادة توليدها بأي دقة؛ لم يبقَ في المخطوطة أي شكل نقطي مأخوذ من الأصل.
• لا توجد جداول بصيغة صور، ولا معادلات بصيغة صور، ولا كائنات OLE ({ole_new})، ولا مربعات نص ({tbx_new})، ولا صور عائمة ({anchored_new}).
• في الملف الأصلي: الصور العائمة (anchored) = {anchored_orig}، كائنات OLE = {ole_orig}، مربعات النص = {tbx_orig}{ga_line}
{webext_line}

9) التعليقات أو Track Changes التي تم العثور عليها
----------------------------------------------------------------------------------------------------
• الملف الأصلي: تعليقات = {orig_comments}، تغييرات متعقَّبة = {orig_tracked}. لم يُحذف أي تعليق.
• الملف النهائي: جزء تعليقات = {new_comments}، تغييرات متعقَّبة = {new_tracked}؛ Track Changes غير مفعّل.
• خصائص الملف الأصلي: المؤلف = "{orig_core_author}"، آخر من عدّل = "{orig_core_lastmod}".

10) معلومات يلزم استكمالها
----------------------------------------------------------------------------------------------------
{missing_info}

11) سبب إنشاء ملف Highlights
----------------------------------------------------------------------------------------------------
{highlights_reason}
"""


def _ref_tables(F, uncited_keys):
    data = json.load(open(VERIFIED_REFS, encoding="utf-8"))
    newno = {}
    for r in data:
        n = F["reflist"].get(r["final"].strip())
        if n is None:  # tolerate small trailing differences
            n = next((v for k, v in F["reflist"].items() if k[:80] == r["final"].strip()[:80]), None)
        newno[r["key"]] = n
    orig = [r for r in data if r["orig_no"] is not None]
    added = [r for r in data if r["orig_no"] is None]
    corr = [r for r in orig if r["status"] == "CORRECTED"]
    fmt_new = lambda k: f"[{newno[k]}]" if newno.get(k) else "(غير مستشهد به)"
    lines = []
    for r in sorted(corr, key=lambda r: r["orig_no"]):
        note = REF_NOTES_AR.get(r["orig_no"]) or r["notes"].split(". ")[0].strip() + "."
        lines.append(f"   - [{r['orig_no']}] ← {fmt_new(r['key'])}: {note}")
    alines = []
    for r in added:
        st = "  (مصحَّح أثناء التحقق: المسودة نُشرت RFC)" if r["status"] == "CORRECTED" else ""
        txt = r["final"] if len(r["final"]) <= 110 else r["final"][:110].rstrip() + "…"
        alines.append(f"   - {fmt_new(r['key'])} {txt}{st}")
    keyorig = {r["key"]: r["orig_no"] for r in data}
    unc = [f"{k} (الأصلي [{keyorig[k]}])" if keyorig.get(k) else k for k in (uncited_keys or [])]
    return dict(n_orig_refs=len(orig), n_corrected=len(corr), n_verified=len(orig) - len(corr), n_added=len(added),
                corrected_list="\n".join(lines), added_list="\n".join(alines), uncited=", ".join(unc) or "لا يوجد")


def _fig_report(rows, O, ga_new):
    tab = []
    for r in rows:
        if r["kept"]:
            origin = f"من الأصل (الشكل {r['orig_no']} الأصلي)"
        elif r["orig_no"]:
            origin = f"جديد، يحل محل الشكل {r['orig_no']} الأصلي"
        else:
            origin = "جديد"
        flag = ("✓ ≥ 500" if r["eff"] >= DPI_COMBINATION else "⚠ 300–499" if r["eff"] >= DPI_HALFTONE else "✗ < 300")
        dpi = r["dpi"][0] if r["dpi"][0] == r["dpi"][1] else f"{r['dpi'][0]}×{r['dpi'][1]}"
        tab.append(f"   Fig. {r['n']} | {os.path.basename(r['src'])} | {origin} | {r['w']}×{r['h']} px "
                   f"({r['mode']}{', الشفافية دُمجت على أبيض' if r['flattened'] else ''}) | dpi المصدر {dpi}"
                   f"{'' if r['dpi_note'] == 'source' else ' (فعلي: المصدر بلا dpi)'} | العرض المُدرج "
                   f"{r['width_in']:.2f} in → dpi فعلي {r['eff']:.0f} {flag} | {os.path.basename(r['out'])} "
                   f"({_mb(r['bytes'])})")
    kept = sorted(r["orig_no"] for r in rows if r["kept"] and r["orig_no"])
    repl = sorted(r["orig_no"] for r in rows if not r["kept"] and r["orig_no"])
    gone = sorted(n for n in O["fig_captions"] if n not in kept and n not in repl)
    s = ("مصدر الأشكال: جميع الأشكال جديدة. الشكلان 1 و2 (نموذج النظام ونموذج التهديدات) أُعيد رسمهما بوضوح من محتوى "
         "الشكلين 2 و3 في الأصل بعد إزالة العناوين المطبوعة داخل الصور وتصحيح ما يخالف الشيفرة (ربط الأجهزة بعُقد الحافة، "
         "ودور التوأم الرقمي، وسيناريوهات التهديد المقيَّمة فعلًا)؛ والأشكال 3–5 أُعيد رسمها لتطابق التصميم النهائي؛ "
         "والأشكال 6–10 تعرض نتائج التجارب الجديدة")
    if O["graphical_abstract"]:
        s += "، والملخص الرسومي المضمَّن في الأصل استُبدل أيضًا ولم يعد جزءًا من متن المخطوطة"
        s += (f" (ملف الملخص الرسومي الجديد: {ga_new})" if ga_new else
              "؛ إن رغب المؤلفون في تقديم ملخص رسومي فيُقدَّم ملفًا منفصلًا يعكس النتائج الجديدة")
    s += "."
    if gone:
        s += f" أشكال أصلية بلا مقابل في النسخة الجديدة: {', '.join(map(str, gone))}."
    low = [r for r in rows if r["eff"] < DPI_COMBINATION]
    notes = []
    if low:
        notes.append("• أشكال دقتها الفعلية أقل من 500 dpi بالعرض المُدرج: " +
                     ", ".join(f"Fig. {r['n']} ({r['eff']:.0f} dpi)" for r in low) + ".")
        if any(r["kept"] for r in low):
            notes.append("  الأشكال المأخوذة من الأصل لا يمكن تحسينها إلا إذا وفّر المؤلفون ملفات مصدرها الأعلى دقة "
                         "أو نسخًا متجهية.")
        if any(not r["kept"] for r in low):
            notes.append("  الأشكال الجديدة مولَّدة بشيفرة، ويمكن إعادة تصديرها بدقة أعلى أو بصيغة متجهية (PDF/EPS) "
                         "إذا طلبت المجلة ذلك.")
    return "\n".join(tab), s, "\n".join(notes)


def _missing_info(F, O, side, rows):
    L = []
    by_tag = collections.defaultdict(list)
    for t, where, what in F["tags_at"]:
        by_tag[t].append((where, what))
    L.append(f"{TAG_AUTHOR}")
    for where, what in by_tag.get(TAG_AUTHOR, []):
        L.append(f"   - في المخطوطة، القسم «{where}»" + (f": {what}" if what else ""))
    corr = F["corr"]
    rest = re.sub(r"[\w.+-]+@[\w.-]+", "", corr)
    rest = re.sub(r"(?i)[*\s]*corresponding author\.?|e-?mail address(es)?:?", "", rest).strip(" .,;:*")
    if len(rest) < 10:
        L.append("   - العنوان البريدي الكامل للمؤلف المراسل غير موجود في المخطوطة الأصلية (يوجد البريد الإلكتروني فقط).")
    if F["n_AL"] and (F["n_Al"] or side.get("al_elsewhere")):
        L.append(f"   - توحيد كتابة اسم العائلة: صفحة العنوان تكتب «AL-Fadhli» (مرات الظهور في المخطوطة = {F['n_AL']})، "
                 f"بينما بيان CRediT داخل المخطوطة (مرات الظهور = {F['n_Al']}) وملف «CRediT author statement.docx» "
                 f"ورسالة التقديم تكتب «Al-Fadhli». على المؤلفين اختيار صيغة واحدة وتوحيدها في كل الملفات وفي نظام "
                 f"التقديم (حُفظ التوقيع في رسالة التقديم كما كتبه المؤلفون).")
    if side.get("cn_letter"):
        L.append("   - يوجد في المجلد خطاب تقديم ما زال موجّهًا إلى مجلة Computer Networks («cover letter .docx»). جملة "
                 "الأصالة في خطاب IJIN تنص على أن المخطوطة «ليست قيد النظر في مجلة أخرى»؛ على المؤلفين التأكد من "
                 "انتهاء أي تقديم سابق (سحب أو رفض) قبل التقديم إلى IJIN.")
    L.append("   - المرجع [1]: التحقق من مسألة النشر المكرر (البند 7)، والمرجع الأصلي [26]: تأكيد المقال المقصود.")
    if F["limitations"]:
        L.append(f"   - ملف «Limitations and Future Work .docx» كُتب للنسخة الأصلية ولم يُدرج؛ النسخة الجديدة تحتوي قسم "
                 f"«{F['limitations'][0]}». على المؤلفين مراجعته.")
    else:
        L.append("   - ملف «Limitations and Future Work .docx» المنفصل لم يُدمج في المخطوطة؛ على المؤلفين تقرير ذلك.")
    L.append("")
    if F["has_credit"]:
        L.append("بيان مساهمات المؤلفين (CRediT): موجود في المخطوطة ومأخوذ من ملف المؤلفين «CRediT author statement.docx»، "
                 "فلا حاجة لوسم المساهمات الناقصة. لكن بما أن العمل أُعيد بناؤه (برمجيات وتجارب وتحليل جديدة)، على "
                 "المؤلفين التأكد من أن الأدوار المذكورة ما زالت تصف مساهماتهم الفعلية.")
    else:
        L.append(f"{TAG_CREDIT}")
        L.append("   - لا يوجد بيان CRediT في المخطوطة؛ لم يُنشأ بالتخمين.")
    L.append("")
    L.append(f"{TAG_AI}")
    if F["has_ai_decl"]:
        L.append("   - يوجد قسم إقرار في المخطوطة؛ على المؤلفين التأكد من أنه يصف الاستخدام الفعلي كاملًا كما يلي.")
    else:
        L.append("   - لا يوجد في المخطوطة إقرار باستخدام الذكاء الاصطناعي التوليدي، ولم يُنشأ نيابة عن المؤلفين.")
    L.append("   - هذا الإقرار إلزامي في مجلات Elsevier وKeAi، ويوضع في قسم مستقل قبل قائمة المراجع بعنوان:")
    L.append("     Declaration of Generative AI and AI-assisted Technologies in the Writing Process")
    L.append("   - يجب أن يصف بصدق المساعدة الفعلية الواسعة التي قدّمتها أداة ذكاء اصطناعي توليدي (Claude من Anthropic، عبر "
             "Claude Code) في إعادة البناء: كتابة الشيفرة البرمجية، وتصميم التجارب وتشغيلها، وتحليل النتائج وإعداد "
             "الأشكال والجداول، وكتابة النص وإعادة صياغته، والتحقق من بيانات المراجع. لا يكفي وصفها بأنها «تحسين لغوي».")
    L.append("   - يذكر الإقرار اسم الأداة (وإصدارها إن عُرف) والغرض من استخدامها، وأن المؤلفين راجعوا كل المحتوى وتحققوا "
             "منه ويتحمّلون المسؤولية الكاملة عنه. ولأن الأداة استُخدمت في العملية البحثية نفسها (الشيفرة والتجارب "
             "والتحليل)، ينبغي وصف ذلك أيضًا في قسم الطرائق/التنفيذ.")
    L.append("   - لا تُدرج أداة الذكاء الاصطناعي مؤلفًا أو مؤلفًا مشاركًا، ولا تُنسب إليها أدوار CRediT.")
    if O.get("ai_addin"):
        L.append("   - ملاحظة: الملف الأصلي يحتوي ربطًا لإضافة Office (webextension) خاصة بمساعد ذكاء اصطناعي (الخاصية "
                 "claude.fileId)، أي أن أداة ذكاء اصطناعي استُخدمت مع المخطوطة الأصلية أيضًا.")
    L.append("")
    if F["has_ethics"]:
        L.append("بيان الأخلاقيات: موجود في المخطوطة.")
    else:
        L.append(f"بيان الأخلاقيات: غير مطلوب — لا تتضمن الدراسة مشاركين بشريين أو بيانات شخصية أو أنسجة بشرية أو "
                 f"حيوانات؛ تستخدم فقط مجموعات بيانات عامة لحركة الشبكات (TON_IoT وEdge-IIoTset وCICIoT2023) ومحاكاة. "
                 f"لذلك لم يُستخدم الوسم {TAG_ETHICS}.")
    for tag in (TAG_METHOD, TAG_CAPTION):
        if by_tag.get(tag):
            L.append("")
            L.append(tag)
            for where, what in by_tag[tag]:
                L.append(f"   - القسم «{where}»" + (f": {what}" if what else ""))
    L.append("")
    L.append("اختياري: الملخص الرسومي (Graphical abstract) لم يُدرج؛ إن رغب المؤلفون فيه فيُعدّ ملفًا منفصلًا يعكس النتائج "
             "الجديدة.")
    return "\n".join(L)


def _highlights_reason(items, side):
    L = []
    old = side.get("old_highlights")
    if old:
        L.append(f"• كان في مجلد المؤلفين ملف «Highlights .docx» بالنقاط: {' | '.join(old)}")
        nums = sorted({n for h in old for n in re.findall(r"\d+\.\d+", h)})
        if nums:
            L.append(f"  هذه النقاط تتضمن أرقامًا من النتائج الأصلية التي استُبدلت ({', '.join(nums)})، فلا يمكن استخدامها مع "
                     f"المخطوطة الجديدة.")
        typos = [m.group(0) for h in old for m in [re.search(r"\b[A-Za-z]+\. [A-Z]{2,}[\w-]*", h)] if m]
        if typos:
            L.append(f"  وتتضمن خطأً طباعيًا محتملًا (نقطة زائدة في «{'»، «'.join(typos)}»).")
    L.append(f"• لذلك أُنشئ ملف IJIN_Highlights.docx جديد (عدد النقاط = {len(items)}) مستند فقط إلى النتائج والجدة "
             f"المذكورة في المخطوطة المعاد بناؤها، دون أي ادعاء جديد. كل رقم في النقاط موجود حرفيًا في نص المخطوطة (فحص "
             f"آلي)، وطول كل نقطة ≤ {HL_CHARS} حرفًا بما في ذلك المسافات (الطول بين القوسين):")
    for h in items:
        L.append(f"   - ({len(h)}) {h}")
    return "\n".join(L)


def write_report(path, ctx):
    head = _fill(REPORT_HEAD, ctx)
    items = _fill(REPORT_ITEMS, ctx)
    tail = ["", "12) التحقق البرمجي (ijin_check.verify)", "-" * 100] + ctx["check_lines"]
    tail += ["", "13) المسارات الكاملة لجميع الملفات المنشأة", "-" * 100]
    tail += [f"  {p}  ({_mb(os.path.getsize(p))})" if os.path.exists(p) else f"  {p}" for p in ctx["created"]]
    tail += [f"  {path}  (هذا التقرير)", "", "ملاحظات عملية", "-" * 100, ctx["disk_note"],
             "• لم يُرفع أي ملف ولم يُرسل أو يُقدَّم إلى المجلة؛ كل الملفات مُعدّة محليًا فقط."]
    with open(path, "w", encoding="utf-8-sig", newline="\r\n") as f:
        f.write(head + items + "\n".join(tail) + "\n")


# ============================================================================================= main entry
def package(dest_dir, info, S, checks, highlights, pdf_path=None, dry_run=False):
    """Assemble the IJIN package in dest_dir (see module docstring). Returns a dict with the created paths."""
    if dry_run:
        dest_dir = DRYRUN_DIR
        if any(x is None for x in (info, S, checks, highlights)):
            f_info, f_S, f_checks, f_hl, f_pdf = make_fake_inputs()
            info = info if info is not None else f_info
            S = S if S is not None else f_S
            checks = checks if checks is not None else f_checks
            highlights = highlights if highlights is not None else f_hl
            pdf_path = pdf_path or f_pdf
    if not dest_dir:
        raise ValueError("dest_dir is required")
    original = info.get("original_path", ORIGINAL)
    formatted = info.get("path", FORMATTED_SRC)
    for p in (original, formatted):
        if not os.path.isfile(p):
            raise FileNotFoundError(p)
    if pdf_path and not os.path.isfile(pdf_path):
        raise FileNotFoundError(pdf_path)

    # ---- validate the inputs before writing anything
    ms_text = _docx_text(formatted)
    items = validate_highlights(highlights, ms_text)
    parts, letter_src = authors_letter_parts()
    sha_before, mtime_before = _sha(original), os.path.getmtime(original)
    O = scan_original(original)

    # ---- free space (the C: drive holding the Desktop is nearly full)
    need = O["size"] + os.path.getsize(formatted) + (os.path.getsize(pdf_path) if pdf_path else 0) + 2 ** 21
    for _, src, _ in info["fig_files"]:
        with Image.open(src) as im:
            need += im.size[0] * im.size[1] * 3
    os.makedirs(dest_dir, exist_ok=True)
    free0 = shutil.disk_usage(dest_dir).free
    if free0 < need + 25 * 2 ** 20:
        raise OSError(f"not enough free space in {dest_dir}: {_mb(free0)} free, about {_mb(need)} needed (+25 MB margin)")

    protected = [original, IJIN_COVER, CN_COVER, CREDIT_FILE, OLD_HIGHLIGHTS, LIMITATIONS_FILE]
    wr = _Writer(dest_dir, protected)

    # 1. backup of the original (never overwritten if a different backup already exists)
    stem = os.path.splitext(os.path.basename(original))[0]
    bpath = wr.target(f"{BACKUP_DIR}\\{stem}_original_backup.docx")
    if os.path.exists(bpath):
        if _sha(bpath) != sha_before:
            raise FileExistsError(f"a different backup already exists, not overwriting: {bpath}")
        backup_state = "(كانت النسخة موجودة من تشغيل سابق ومطابقة، فلم تُكتب مجددًا)"
    else:
        shutil.copy2(original, bpath)
        backup_state = ""
    wr.done(bpath)
    backup_ok = _sha(bpath) == sha_before

    # 2. manuscript (+ PDF)
    out_docx = wr.target(OUT_DOCX)
    if not _same(formatted, out_docx):
        shutil.copy2(formatted, out_docx)
    wr.done(out_docx)
    out_pdf = None
    if pdf_path:
        out_pdf = wr.target(OUT_PDF)
        if not _same(pdf_path, out_pdf):
            shutil.copy2(pdf_path, out_pdf)
        wr.done(out_pdf)

    # 3. figures
    rows = export_figures(info["fig_files"], wr, O["fig_captions"])
    stale = sorted(f for f in os.listdir(os.path.join(dest_dir, FIG_DIR))
                   if re.fullmatch(r"Fig_(\d+)\.tif", f) and int(f[4:-4]) > len(rows))

    # 4. highlights
    hl_path = wr.target(OUT_HL)
    write_highlights(hl_path, items)
    wr.done(hl_path)

    # 5. cover letter
    cl_path = wr.target(OUT_COVER)
    write_cover_letter(cl_path, S, parts)
    wr.done(cl_path)

    # 6. report
    F = inspect_formatted(out_docx)
    side = {"old_highlights": [t for t in (_docx_paragraphs(OLD_HIGHLIGHTS) or []) if t.strip() != "Highlights"],
            "cn_letter": any("Computer Networks" in t for t in (_docx_paragraphs(CN_COVER) or [])),
            "al_elsewhere": any("Al-Fadhli" in t for t in (_docx_paragraphs(CREDIT_FILE) or []) + parts["closing"])}
    orig_unchanged = _sha(original) == sha_before and os.path.getmtime(original) == mtime_before
    rp_path = wr.target(OUT_REPORT)
    fig_table, fig_summary, dpi_notes = _fig_report(rows, O, info.get("graphical_abstract"))
    if stale:
        dpi_notes += ("\n" if dpi_notes else "") + f"• تنبيه: ملفات أشكال قديمة من تشغيل سابق في IJIN_Figures لم تُحذف: {stale}"
    c = checks
    tags = c.get("tags", {})
    extra = [
        (backup_ok, "النسخة الاحتياطية مطابقة للأصل (SHA-256)", "مطابقة" if backup_ok else "غير مطابقة"),
        (orig_unchanged, "الملف الأصلي لم يتغير أثناء التحزيم", "لم يتغير" if orig_unchanged else "تغيّر!"),
        (c.get("images") == len(rows), "عدد الصور في المستند = عدد ملفات الأشكال المصدَّرة", f"{c.get('images')} / {len(rows)}"),
        (len(c.get("figure_captions", [])) == info.get("figs", len(rows)), "عدد عناوين الأشكال = عدد الأشكال المبنية",
         f"{len(c.get('figure_captions', []))} / {info.get('figs')}"),
        (c.get("references_listed") == info.get("refs"), "عدد المراجع في القائمة = عدد المراجع المستشهد بها عند البناء",
         f"{c.get('references_listed')} / {info.get('refs')}"),
        (all(r["tif_dpi"] and abs(r["tif_dpi"][0] - r["dpi"][0]) < 0.01 and abs(r["tif_dpi"][1] - r["dpi"][1]) < 0.01
             for r in rows), "ملفات TIFF: RGB وLZW وبنفس البكسلات وdpi المصدر", f"عدد الملفات = {len(rows)}"),
        (HL_MIN <= len(items) <= HL_MAX and max(map(len, items)) <= HL_CHARS, "Highlights: العدد 3–5 وكل نقطة ≤ 85 حرفًا",
         f"عدد النقاط = {len(items)}، وأطولها = {max(map(len, items))} حرفًا"),
        (True, "رسالة التقديم: العنوان مطابق حرفيًا، وجملة الأصالة والتوقيع منقولة حرفيًا، ولا إقرارات مضافة",
         "خطاب IJIN للمؤلفين" if letter_src["file"] else "نص احتياطي (تعذرت قراءة خطاب المؤلفين)"),
        (len(F["keywords"]) <= 6, "عدد الكلمات المفتاحية ≤ 6", len(F["keywords"])),
        (F["title"] == TITLE, "عنوان المخطوطة مطابق حرفيًا للعنوان المعتمد", "مطابق" if F["title"] == TITLE else F["title"]),
    ]
    free1 = shutil.disk_usage(dest_dir).free
    drive = os.path.splitdrive(os.path.abspath(dest_dir))[0] or dest_dir
    cfree = shutil.disk_usage("C:\\").free if os.path.exists("C:\\") else None
    disk_note = (f"• المساحة الحرة على القرص {drive}: {_mb(free1)} بعد التحزيم (كانت {_mb(free0)})."
                 + (f" القرص C: (الذي يحوي سطح المكتب ومجلد OneDrive) شبه ممتلئ: {_mb(cfree)} فقط حرة؛ يُنصح بتحرير "
                    f"مساحة قبل أي تعديل أو مزامنة إضافية." if cfree is not None and cfree < 2 * 2 ** 30 else ""))
    hc = F["h_counts"]
    proto = [t.split(" ")[0] for lv, t in O["headings"] if lv >= 2 and "protocol" in t.lower()]
    ctx = dict(
        journal=JOURNAL, date=datetime.datetime.now().strftime("%Y-%m-%d %H:%M"), title=TITLE,
        dry_banner=("تشغيل تجريبي (dry run): كل المدخلات وهمية (مخطوطة أصلية ومخطوطة منسّقة مصطنعتان)، "
                    "والمخرجات في مجلد التجربة فقط." if dry_run else ""),
        title_ok="✓ مطابق" if O["title"].strip() == TITLE and F["title"] == TITLE else
        f"✗ غير مطابق (الأصل: {O['title']!r}؛ الجديد: {F['title']!r})",
        n_fl_runs=_num(S.get("n_fl_runs")) if S.get("n_fl_runs") is not None else "⟦قيمة غير متوفرة: n_fl_runs⟧",
        n_figs=info.get("figs", len(rows)), n_tabs=info.get("tabs"), n_eqs=info.get("eqs"), n_refs=info.get("refs"),
        orig_name=O["name"], orig_path=O["path"], orig_size=_num(O["size"]), orig_sha=O["sha256"],
        orig_h1=sum(1 for lv, _ in O["headings"] if lv == 1), orig_figs=len(O["fig_captions"]),
        orig_tabs=len(O["table_captions"]), orig_math=O["math"], orig_ga="نعم" if O["graphical_abstract"] else "لا",
        orig_unchanged="✓ نعم" if orig_unchanged else "✗ لا",
        backup_path=bpath, backup_ok="✓" if backup_ok else "✗", backup_state=backup_state,
        final_docx=out_docx, final_pdf=f"• {out_pdf}" if out_pdf else "• (لم يُقدَّم ملف PDF)",
        multi_col=c.get("multi_column_sections"), justified=c.get("justified_paragraphs"),
        hyph_off="✓" if c.get("auto_hyphenation") is False else "✗",
        n_h1=hc.get("Heading 1", 0), n_h2=hc.get("Heading 2", 0), n_h3=hc.get("Heading 3", 0),
        heads_ok="✓" if c.get("heading_format_ok") else "✗", font=F["font"], size=F["size"], spacing=F["spacing"],
        page=F["page"], margins=F["margins_cm"], abstract_words=info.get("abstract_words"),
        n_kw=len(F["keywords"]), kw_list="; ".join(F["keywords"]) or "—",
        math_objects=c.get("math_objects"), display_eqs=c.get("display_equations"),
        core_author_line=("حقل المؤلف في خصائص الملف فارغ (لا أسماء أو هويات في بيانات الملف)" if not c.get("core_author")
                          else f"حقل المؤلف في خصائص الملف: {c.get('core_author')}"),
        ga_line=("؛ والملخص الرسومي المضمَّن في الأصل لم يُنقل إلى النسخة الجديدة." if O["graphical_abstract"] else "."),
        orig_h1_list="\n".join(f"   - {t}" for lv, t in O["headings"] if lv == 1) or "   - —",
        new_h1_list="\n".join(f"   - {t}" for t in F["h1"]) or "   - —",
        sections_notes="\n".join(x for x in [
            "• قسم «Graphical Abstract» داخل المتن أُزيل؛ لا يوضع الملخص الرسومي داخل المخطوطة." if O["graphical_abstract"]
            and not F["has_ga"] else "",
            "• أقسام الإقرارات (CRediT، تضارب المصالح، التمويل، إتاحة البيانات) وُضعت قبل قائمة المراجع، والناقص منها "
            "موسوم ولم يُخترع." if F["has_credit"] or F["has_competing"] else "",
            ("• الأقسام الوصفية من نوع «protocol» في الأصل (" + ", ".join(proto) + ") استُبدلت بتجارب منفَّذة ونتائج "
             "فعلية في قسمي التصميم التجريبي والنتائج.") if proto else "",
        ] if x),
        tab_caps=_val(c.get("table_captions", [])), tabs_seq="✓" if c.get("tables_sequential") else "✗",
        tabs_uncited=_val(c.get("tables_not_cited", [])), eq_tables=F["eq_tables"],
        fig_caps=_val(c.get("figure_captions", [])), figs_seq="✓" if c.get("figures_sequential") else "✗",
        figs_uncited=_val(c.get("figures_not_cited", [])), tag_caption=TAG_CAPTION,
        n_tag_caption=tags.get(TAG_CAPTION, 0), fig_summary=fig_summary, fig_table=fig_table, dpi_notes=dpi_notes,
        dpi_half=DPI_HALFTONE, dpi_comb=DPI_COMBINATION, dpi_line=DPI_LINEART, refs_json=VERIFIED_REFS,
        references_listed=c.get("references_listed"), cit_order="✓" if c.get("citations_in_order") else "✗",
        cited_not_listed=_val(c.get("cited_not_listed", [])), listed_not_cited=_val(c.get("listed_not_cited", [])),
        ole_new=F["ole"], tbx_new=F["textboxes"], anchored_new=F["anchored"], anchored_orig=O["anchored"],
        ole_orig=O["ole"], tbx_orig=O["textboxes"],
        webext_line=("• الملف الأصلي يحتوي إضافات Office مضمَّنة (webextensions: " +
                     ", ".join(w["store_id"] for w in O["webextensions"]) + ")؛ لم تُنقل إلى النسخة الجديدة."
                     if O["webextensions"] else ""),
        orig_comments=O["comments"], orig_tracked=O["tracked"], new_comments=_val(c.get("comments_part")),
        new_tracked=c.get("tracked_changes"), orig_core_author=O["core_author"],
        orig_core_lastmod=O["core_last_modified_by"],
        missing_info=_missing_info(F, O, side, rows), highlights_reason=_highlights_reason(items, side),
        check_lines=render_checks(c, extra), created=list(wr.created), disk_note=disk_note,
    )
    ctx.update(_ref_tables(F, info.get("uncited")))
    write_report(rp_path, ctx)
    wr.done(rp_path)
    if _sha(original) != sha_before:
        raise RuntimeError("the original manuscript changed during packaging")
    return dict(dest=dest_dir, files=list(wr.created), figures=rows, report=rp_path, backup=bpath,
                backup_ok=backup_ok, original_unchanged=orig_unchanged, letter_source=letter_src)


# ============================================================================================= dry run
FAKE_HIGHLIGHTS = [
    "Device trust uses only device evidence; PQ cost and slice latency choose the action",
    "Trust-aware aggregation compared with six robust rules over 1,560 federated runs",
    "City-scale test with 1,500 devices, 12 edge nodes and four 6G slices",
    "Hybrid X25519+ML-KEM-768 TLS 1.3 handshakes measured with OpenSSL 3.5",
]
FAKE_FIGS = [("original", "fig2_system_model.png"), ("original", "fig3_threat_model.png"), ("", "fig1_architecture.png"),
             ("", "fig4_trust_workflow.png"), ("", "fig5_twin_validation.png"), ("", "fig6_fl_clean.png"),
             ("", "fig7_fl_poisoning.png")]


def make_fake_inputs():
    """Fake original + fake formatted manuscript (python-docx), fake info/S/checks; real figure files (read-only)."""
    sys.path.insert(0, HERE)
    from docxkit import Manuscript
    from refs import REFS
    import ijin_check
    src = os.path.join(DRYRUN_DIR, "_fake_inputs")
    os.makedirs(src, exist_ok=True)
    figs = [os.path.join(WORK, "figures", sub, f) if sub else os.path.join(WORK, "figures", f) for sub, f in FAKE_FIGS]

    # fake ORIGINAL manuscript (same file name as the real one, to exercise the backup naming)
    orig = os.path.join(src, os.path.basename(ORIGINAL))
    d = Document()
    d.add_paragraph(TITLE)
    d.add_paragraph("Firas H. K. AL-Fadhli a,*, Sarmad Hameed Khazaal AL-Fadhli b")
    d.add_heading("Abstract", 1)
    d.add_paragraph("[DRY-RUN] Fake original abstract.")
    d.add_paragraph("Keywords: Adaptive Zero Trust; Post-Quantum Cryptography; Digital Twin Security")
    d.add_heading("Graphical Abstract", 1)
    d.add_heading("1. Introduction", 1)
    d.add_heading("4. Experimental Design and Evaluation protocol", 1)
    d.add_heading("4.6 Detection-performance protocol", 2)
    for n, cap in enumerate(["A-PQZTO overview", "Smart city system model", "Threat model", "Trust and policy workflow",
                             "Digital twin validation", "Detection and Zero-Trust evaluation protocol",
                             "Digital-twin validation protocol"], 1):
        d.add_paragraph(f"Fig. {n}. {cap}.")
    d.add_paragraph("Table 1. Comparison of related studies and research gap.")
    d.add_heading("References", 1)
    d.save(orig)

    # fake FORMATTED manuscript built with the same toolkit as build.py
    m = Manuscript(REFS, font="Times New Roman", size=10, spacing=2.0, line_numbers=False, cite_style="elsevier",
                   align="left", page="Letter", margins_cm=1.83)
    m.para(f"**{TITLE}**", align="center", indent=False, size=14)
    m.para("Firas H. K. AL-Fadhli^{a,*}, Sarmad Hameed Khazaal AL-Fadhli^{b}", align="center", indent=False)
    m.para("^{*} Corresponding author. E-mail address: firas.hameed@mohesr.edu.iq", align="center", indent=False)
    m.heading("Abstract", 1)
    m.para("[DRY-RUN] Fake abstract: 1,560 federated runs; 1,500 devices, 12 edge nodes, four 6G slices.", indent=False)
    m.para("**Keywords:** Zero trust; Post-quantum cryptography; Federated learning; Digital twin; Intrusion "
           "detection; Smart-city IoT", indent=False)
    m.heading("1. Introduction", 1)
    keys = list(REFS)
    for i in range(0, len(keys), 6):
        m.para("[DRY-RUN] Citation filler [@" + ";@".join(keys[i:i + 6]) + "].")
    m.para("Device trust uses only device evidence; post-quantum (PQ) cost and slice latency choose the action. "
           "Trust-aware aggregation is compared with six robust rules over 1,560 federated runs. The city-scale test "
           "has 1,500 devices, 12 edge nodes and four 6G slices. Hybrid X25519+ML-KEM-768 TLS 1.3 handshakes are "
           "measured with OpenSSL 3.5.")
    m.heading("2. Method", 1)
    for k, f in enumerate(figs, 1):
        m.label_next("fig", f"f{k}")
        m.para(f"Fig. {{fig:f{k}}} shows panel {k}.")
        m.figure(f, f"[DRY-RUN] caption {k}.", width_in=6.3, label=f"f{k}")
    m.label_next("tab", "t1")
    m.para("Table {tab:t1} lists values.")
    m.table(["A", "B"], [["1", "2"]], "[DRY-RUN] table.", label="t1")
    try:
        m.equation("T_{i}=B_{i}+H_{i}", label="e1")
    except Exception:  # MML2OMML.XSL missing: the dry run does not need an equation
        pass
    m.heading("6. Discussion", 1)
    m.heading("6.3 Limitations and threats to validity", 2)
    m.para("[DRY-RUN] limitations.")
    m.heading("CRediT authorship contribution statement", 1)
    m.para("**Firas H. K. Al-Fadhli:** Conceptualization. **Sarmad Hameed Khazaal Al-Fadhli:** Software.", indent=False)
    m.heading("Declaration of competing interest", 1)
    m.para(TAG_AUTHOR, indent=False)
    m.heading("Funding", 1)
    m.para(TAG_AUTHOR, indent=False)
    m.heading("Data availability", 1)
    m.para(f"Code: {TAG_AUTHOR[:-1]}: repository link or DOI].", indent=False)
    m.references()
    fmt = os.path.join(src, "IJIN_formatted_fake.docx")
    m.save(fmt, title=TITLE)

    pdf = os.path.join(src, "IJIN_formatted_fake.pdf")
    Image.new("RGB", (850, 1100), (255, 255, 255)).save(pdf, "PDF", resolution=100)

    info = dict(path=fmt, original_path=orig, figs=m.fig_n, tabs=m.tab_n, eqs=m.eq_n, refs=len(m.cite_order),
                uncited=[k for k in REFS if k not in m.cite_order], abstract_words=17, fig_files=m.fig_files)
    S = {"n_fl_runs": 1560,
         "cover_claims": ["[DRY-RUN placeholder claim 1 - replaced by S['cover_claims'] in the real run.]",
                          "[DRY-RUN placeholder claim 2 - replaced by S['cover_claims'] in the real run.]"]}
    checks = ijin_check.verify(fmt, pdf)
    return info, S, checks, list(FAKE_HIGHLIGHTS), pdf


def _selftest_refusals():
    """The highlight and cover-letter guards must refuse bad input."""
    ok = []
    cases = [("2 bullets", ["a", "b"]), ("6 bullets", list("abcdef")), ("86 chars", ["x" * 86, "b", "c"]),
             ("number not in text", ["Detection reaches 99.9% everywhere", "b", "c"])]
    for name, hl in cases:
        try:
            validate_highlights(hl, "manuscript text with 1,560 runs")
            ok.append((name, False))
        except ValueError:
            ok.append((name, True))
    try:
        write_cover_letter(os.path.join(DRYRUN_DIR, "_fake_inputs", "never.docx"), {"cover_claims": ["one"],
                                                                                    "n_fl_runs": 1}, {})
        ok.append(("1 cover claim", False))
    except ValueError:
        ok.append(("1 cover claim", True))
    try:
        _Writer(DRYRUN_DIR, []).target("some_other_file.docx")
        ok.append(("non-package file name", False))
    except PermissionError:
        ok.append(("non-package file name", True))
    return ok


def main(argv=None):
    ap = argparse.ArgumentParser(description="Assemble the IJIN submission package.")
    ap.add_argument("--dry-run", action="store_true", help=f"fake inputs, output to {DRYRUN_DIR}")
    ap.add_argument("--dest", help="destination folder (required unless --dry-run)")
    ap.add_argument("--highlights", help="JSON file with the list of 3-5 highlights (default: S['highlights'])")
    ap.add_argument("--pdf", help="PDF rendering of IJIN_formatted.docx")
    a = ap.parse_args(argv)
    if a.dry_run:
        if os.path.isdir(DRYRUN_DIR):
            shutil.rmtree(DRYRUN_DIR)
        res = package(None, None, None, None, None, dry_run=True)
        for name, refused in _selftest_refusals():
            print(f"refusal test [{name}]: {'refused (OK)' if refused else 'NOT refused (FAIL)'}")
    else:
        if not a.dest:
            ap.error("--dest is required (or use --dry-run)")
        sys.path.insert(0, HERE)
        import build
        import ijin_check
        info, S, _ = build.build()
        checks = ijin_check.verify(info["path"], a.pdf)
        hl = json.load(open(a.highlights, encoding="utf-8")) if a.highlights else S.get("highlights")
        res = package(a.dest, info, S, checks, hl, pdf_path=a.pdf)
    print(json.dumps({k: v for k, v in res.items() if k != "figures"}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
