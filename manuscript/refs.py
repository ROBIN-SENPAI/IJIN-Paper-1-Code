# -*- coding: utf-8 -*-
"""Reference list: every entry was checked against Crossref / publisher / standards-body records
(verified_refs.json, produced by the reference audit). Keys are cited in the text as [@key]."""
import json
import os

_HERE = os.path.dirname(os.path.abspath(__file__))
_R = json.load(open(os.path.join(_HERE, "verified_refs.json"), encoding="utf-8"))
REFS = {r["key"]: r["final"] for r in _R}
STATUS = {r["key"]: (r["orig_no"], r["status"], r["notes"]) for r in _R}
