# -*- coding: utf-8 -*-
"""Declarations (IJIN / Elsevier). Only statements supplied by the authors are written out; everything else is a tag
for the authors to complete (see IJIN_formatting_report.txt)."""

CREDIT = ("**Firas H. K. Al-Fadhli:** Conceptualization, Methodology, Formal analysis, Writing – Original Draft, "
          "Supervision, Project administration. **Sarmad Hameed Khazaal Al-Fadhli:** Data curation, Software, "
          "Validation, Visualization, Writing – Review & Editing.")

HASHES = {"train_test_network.csv (TON_IoT)": "26ddc513552de36de6428b2e578efaed2b57504c716dfba847cc0109a64e1974",
          "ML-EdgeIIoT-dataset.csv (Edge-IIoTset)": "53101fad091af20bee815860962a5016b802ee45d456a141042f6183094c3c1a",
          "Merged01.csv (CICIoT2023)": "8b43d6552a8cafd3b0ca2cedf6464ca3fe644d7fc9bb5dfe906368f1542792fe",
          "Merged02.csv (CICIoT2023)": "0745a3649a5688616ce58f58fc68d18bfc652ad0b0760b5f486e6976925f001b"}


def statements(m, S):
    m.heading("CRediT authorship contribution statement", 1)
    m.para(CREDIT, indent=False)
    m.heading("Declaration of competing interest", 1)
    m.para("[AUTHOR INFORMATION REQUIRED]", indent=False)
    m.heading("Funding", 1)
    m.para("[AUTHOR INFORMATION REQUIRED]", indent=False)
    m.heading("Data availability", 1)
    m.para("The datasets are public: TON_IoT [@moustafa2021toniot], Edge-IIoTset [@ferrag2022edgeiiot] and CICIoT2023 "
           "[@neto2023ciciot]. The SHA-256 hashes of the files used are: " +
           "; ".join(f"{k}: {v}" for k, v in HASHES.items()) + ". The code, the per-run result files and the "
           "scripts that regenerate every table and figure: [AUTHOR INFORMATION REQUIRED: repository link or DOI].",
           indent=False)
