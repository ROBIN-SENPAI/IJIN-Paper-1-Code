# -*- coding: utf-8 -*-
"""Title block, abstract, introduction and related work."""

TITLE = ("Risk-Adaptive Post-Quantum Zero-Trust Orchestration for Smart-City IoT: Architecture and Reproducible "
         "Evaluation")
KEYWORDS = "Zero trust; Post-quantum cryptography; Federated learning; Digital twin; Intrusion detection; Smart-city IoT"
AUTHORS = "Firas H. K. AL-Fadhli^{a,*}, Sarmad Hameed Khazaal AL-Fadhli^{b}"
AFFILS = ["^{a} Department of Research and Development, Ministry of Higher Education and Scientific Research, Baghdad, Iraq",
          "^{b} Scientific Research Commission, Baghdad, Iraq"]
CORR = "^{*} Corresponding author. E-mail address: firas.hameed@mohesr.edu.iq"


def front(m, S):
    m.para(f"**{TITLE}**", align="center", indent=False, size=14, space_after=8)
    m.para(AUTHORS, align="center", indent=False)
    for a in AFFILS:
        m.para(a, align="center", indent=False, italic=True, size=9)
    m.para(CORR, align="center", indent=False, size=9, space_after=8)


def abstract(m, S):
    m.heading("Abstract", 1)
    m.para(S["abstract"], indent=False)
    m.para(f"**Keywords:** {KEYWORDS}", indent=False)


def introduction(m, S):
    m.heading("1. Introduction", 1)
    m.para("A smart city connects traffic controllers, smart meters, medical wearables and surveillance cameras to the "
           "same edge and core infrastructure, and in 6G deployments these services are expected to share it through "
           "network slices with very different requirements [@itu2023m2160; @sharma2024sustainability; "
           "@ogenyi2025frontiers]. A compromised camera can recruit its neighbours into a botnet, a stolen credential can "
           "reach a grid-control endpoint, and a flood aimed at one edge node can delay emergency traffic in another "
           "slice [@oliha2024; @qasim2025ijipm]. In this setting, security decisions must be taken per device and "
           "continuously, and each one has to account for what it costs the service it protects.")
    m.para("Zero trust is a sensible starting point because it removes the implicit trust that perimeter models place "
           "in anything inside the network; every request is evaluated against identity, device state and context "
           "[@rose2020zta]. Reviews of zero-trust deployments, however, find that most work concentrates on "
           "authentication and access control, while orchestration, environmental awareness and lightweight operation "
           "remain underdeveloped [@mushtaq2025]. A zero-trust framework for 6G cyber-physical systems combines "
           "adaptive access control with anomaly detection but leaves quantum-safe cryptography and federated learning "
           "to future work [@alnaim2025]. Three further pressures are specific to the smart city.")
    m.para("The first is cryptographic. Data that health and energy devices send today must remain confidential for "
           "years, yet traffic recorded now could be decrypted once a cryptographically relevant quantum computer exists "
           "(the harvest-now-decrypt-later threat). NIST has standardised ML-KEM for key establishment and ML-DSA and "
           "SLH-DSA for signatures [@nist2024fips203; @nist2024fips204; @nist2024fips205], and hybrid key agreement "
           "for TLS 1.3 is now specified [@rfc10024]. Running these algorithms on every IoT exchange is expensive; "
           "surveys of post-quantum IoT security identify computation, memory and message-size limits as the main "
           "obstacles [@fernandezcarames2020pq; @mansoor2025; @almutairi2025]. The second pressure concerns threat "
           "intelligence. Federated learning (FL) lets edge nodes train a shared intrusion detector without pooling "
           "raw traffic [@lazzarini2023; @karunamurthy2025; @tom2025], but non-IID data and poisoned updates can degrade "
           "the shared model [@bunko2026; @mohammed2025sinkron; @yang2023cose; @thein2024fgcs]. The third concerns "
           "the choice of action. Blocking a suspicious device costs little, whereas isolating a whole slice segment "
           "does not. Digital twins could predict the consequences of such an action, but they are mostly used for "
           "monitoring or detection support [@salim2024fgcs; @yigit2024icc; @sunil2025crc].")
    m.para("These components are rarely combined in a single decision loop, and where they are, the evaluation is "
           "usually conceptual or limited to detector accuracy. Accuracy alone says little about whether attacks are "
           "contained, how many legitimate devices are cut off, or what quantum-safe protection costs. Evaluation "
           "practice introduces a further risk: benchmark choices, partitioning and dataset artefacts can change "
           "conclusions about intrusion detection [@arp2022dosdonts; @bilal2026scirep], and at least one widely used "
           "IoT dataset contains a serialisation artefact that leaks the label [@galal2026provenance].")
    m.para("This paper presents the Adaptive Post-Quantum Zero-Trust Orchestrator (A-PQZTO) and evaluates it with "
           "measured detector outputs and handshake costs. A-PQZTO computes a trust score for every device from "
           "behavioural, reputational, authentication and federated evidence, and a zero-trust veto caps that score at "
           "one minus the federated threat probability, so good credentials cannot outweigh strong threat evidence. It "
           "then decides whether to allow the device, restrict it, re-authenticate it with post-quantum credentials, "
           "quarantine it, block it or isolate its edge cluster. Post-quantum protection and slice latency affect the "
           "choice of action, not the trust score, and the twin checks cluster-wide actions before they are enforced. "
           "The paper makes five contributions.")
    m.bullets([
        "An orchestration loop that computes trust only from evidence about the device and lets post-quantum cost and "
        "slice latency budgets decide when stronger authentication is affordable, so that quantum-safe protection is "
        "a decision variable rather than a fixed add-on.",
        "A trust-aware aggregation rule for federated threat intelligence, compared with FedAvg, FedProx, Krum, "
        "Multi-Krum, coordinate-wise median and trimmed mean on TON_IoT and CICIoT2023 under IID and Dirichlet non-IID "
        f"partitions and under label-flipping and model-poisoning clients ({S['n_fl_runs']:,} training runs).",
        "A simulated city-scale evaluation with 1,500 devices, 12 edge nodes and four 6G slices, in which every device "
        "emits evidence drawn from measured detector outputs on held-out flows. All policies are calibrated on validation "
        "episodes to the same false-blocking and service-disruption budget and then compared on fresh test seeds in "
        "worm, flooding, credential-misuse, data-injection and impostor scenarios. The evaluation also includes "
        "component ablations, a twin-fidelity analysis, stress tests with a faster worm and slower devices, and "
        "scalability tests.",
        "Measurements of ML-KEM and ML-DSA and of hybrid post-quantum TLS 1.3 handshakes with OpenSSL 3.5, together "
        "with an analysis of how adaptive activation trades handshake cost against the exposure of sensitive sessions "
        "to harvest-now-decrypt-later attacks.",
        "A leakage audit of the three datasets considered, which shows that the Edge-IIoTset machine-learning subset "
        "cannot support binary detector benchmarking once identifiers and the placeholder artefact are removed.",
    ], numbered=True)
    m.para("Section 2 reviews related work and identifies the research gap. Section 3 presents the system model, the "
           "threat model and A-PQZTO. Section 4 describes the datasets, experiments and metrics. Section 5 reports the "
           "results, Section 6 discusses them and the limitations of the study, and Section 7 concludes the paper.")


def related_work(m, S):
    m.heading("2. Related Work and Research Gap", 1)
    m.heading("2.1 Post-quantum security for IoT and 6G networks", 2)
    m.para("Healthcare, public-safety, grid and transport data remain valuable for years, so the "
           "harvest-now-decrypt-later threat is relevant to IoT even before large quantum computers exist. Mansoor et "
           "al. review post-quantum schemes for IoT authentication and privacy and identify lightweight implementation, "
           "key exchange and device resources as the main deployment problems [@mansoor2025]. Almutairi and Sheldon "
           "find that most studies test post-quantum cryptography (PQC) in MQTT and CoAP under benign conditions and "
           "seldom under packet loss or high latency [@almutairi2025]. Szymanski proposes a quantum-safe, "
           "hardware-enforced deterministic IIoT design for critical infrastructures; the design addresses "
           "deterministic forwarding rather than adaptive orchestration across slices [@szymanski2024]. "
           "Fernandez-Carames surveys quantum-resistant cryptosystems for IoT and the transition from classical "
           "protection [@fernandezcarames2020pq]. In all of these studies PQC is treated as a cryptographic building "
           "block: whether it is invoked does not depend on trust, slice sensitivity, predicted risk or latency.")
    m.heading("2.2 Zero-trust security in smart-city and 6G IoT", 2)
    m.para("NIST SP 800-207 defines the policy decision and enforcement points, continuous evaluation and least "
           "privilege that zero-trust architectures (ZTA) build on [@rose2020zta]. Mushtaq et al. review 74 ZTA studies "
           "across cloud, IoT, industrial, mobile and edge settings and report that authentication, authorisation and "
           "access control dominate, while orchestration, auditing, environmental perception and lightweight "
           "cryptography are less developed [@mushtaq2025]. Alnaim and Alwakeel combine adaptive access control, "
           "blockchain, encryption and AI-based anomaly detection for 6G cyber-physical systems and report a lower attack "
           "success rate and lower latency than conventional methods [@alnaim2025]. Many ZTA frameworks, however, still "
           "rely on fixed rules or static trust levels and do not update trust from federated threat evidence or "
           "predicted propagation.")
    m.heading("2.3 Federated threat intelligence", 2)
    m.para("In federated intrusion detection, edge nodes train locally and share model updates instead of raw "
           "telemetry [@mcmahan2017fedavg]. Lazzarini et al. show on ToN_IoT and CICIDS2017 that federated detectors "
           "approach centralised accuracy while keeping data local [@lazzarini2023], and Karunamurthy et al. report high "
           "detection performance with an optimised federated IDS on MQTT data [@karunamurthy2025]. Tom et al. map "
           "federated learning to intrusion detection, malware analysis, botnet mitigation and trust management in IIoT "
           "[@tom2025], and Mrabet weights client contributions by reputation in TrustFed-CTI to limit adversarial "
           "influence on shared intelligence [@mrabet2025]. A broader survey stresses heterogeneity, privacy and "
           "deployment constraints [@vashisth2025informatica]. The weaknesses of the approach are well documented. "
           "Keeping data local does not make the updates safe, since they can leak information and can be poisoned "
           "[@bunko2026]; non-IID data slows convergence and destabilises detection [@mohammed2025sinkron; "
           "@hsu2019noniid]; and malicious clients can corrupt the aggregate [@yang2023cose; @thein2024fgcs; "
           "@fang2020localpoison]. Byzantine-robust rules such as Krum, coordinate-wise median and trimmed mean "
           "[@blanchard2017krum; @yin2018median] and proximal local training [@li2020fedprox] address these problems, "
           "but the end product is usually a detection score.")
    m.heading("2.4 Digital-twin-assisted cybersecurity", 2)
    m.para("A digital twin can model how an attack spreads and what a response would do before that response reaches "
           "the network. This matters because the most secure action is not always acceptable for a clinical or "
           "traffic service. Sunil et al. discuss how 6G, blockchain, edge computing, AI and digital twins can be "
           "combined in secure smart cities [@sunil2025crc]. Salim et al. couple a digital twin with optimised "
           "federated learning for IoT threat detection [@salim2024fgcs], Yigit et al. use a twin for autonomous attack "
           "detection in vehicular networks [@yigit2024icc], and Jamil et al. survey the joint use of twins and "
           "federated learning [@jamil2022asi]. In these works the twin supports monitoring, simulation or detection; "
           "it does not validate an enforcement action against predicted spread and service impact.")
    m.heading("2.5 Research gap", 2)
    m.label_next("tab", "related")
    m.para("Table {tab:related} summarises representative studies. Each advances one or two of the capabilities "
           "required here: AI-native 6G and slicing, zero trust, PQC, federated detection, poisoning defence or "
           "twin-assisted detection. None of them closes the loop from distributed evidence to a validated, cost-aware "
           "enforcement decision, and none measures the outcome of such a loop in terms of containment, false blocking "
           "and post-quantum cost. Evaluation practice is a second gap: dataset construction and partitioning "
           "materially change conclusions about federated intrusion detection [@bilal2026scirep], and results reported "
           "without leakage checks can overstate performance [@arp2022dosdonts; @galal2026provenance]. This paper "
           "targets both gaps: A-PQZTO closes the loop, and its evaluation uses a common operating budget and audited "
           "data.")
    rows = [
        ["Ogenyi et al. [@ogenyi2025frontiers]", "AI-native 6G", "Reviews context-aware, intelligence-native 6G",
         "No security orchestration"],
        ["Sharma et al. [@sharma2024sustainability]", "6G smart cities", "Reviews applications and security challenges",
         "No unified ZTA–PQC–FL–twin model"],
        ["Qasim and Chafic [@qasim2025ijipm]", "6G slicing", "Improves latency and resource allocation",
         "Resource management only"],
        ["Mushtaq et al. [@mushtaq2025]", "ZTA review", "Identifies gaps in orchestration and lightweight deployment",
         "No adaptive 6G IoT framework"],
        ["Alnaim and Alwakeel [@alnaim2025]", "ZTA for 6G CPS",
         "Combines adaptive access control, blockchain, encryption and AI detection", "PQC and FL left as future work"],
        ["Mansoor et al. [@mansoor2025]", "PQC for IoT", "Reviews PQC algorithms and IoT constraints",
         "No adaptive policy orchestration"],
        ["Almutairi and Sheldon [@almutairi2025]", "PQC in IoT protocols", "Studies MQTT/CoAP PQC trade-offs",
         "No trust- or slice-aware PQC activation"],
        ["Szymanski [@szymanski2024]", "Quantum-safe IIoT", "Hardware-enforced quantum-safe security",
         "No adaptive city-scale orchestration"],
        ["Lazzarini et al. [@lazzarini2023]", "FL-based IDS", "Keeps IoT data local for intrusion detection",
         "FL not linked to ZTA, PQC or twin"],
        ["Karunamurthy et al. [@karunamurthy2025]", "Optimised FL-IDS", "Improves IoT attack detection",
         "Detection accuracy only"],
        ["Tom et al. [@tom2025]", "FL-based CTI", "Reviews FL aggregation and CTI uses", "No slice-aware ZTA"],
        ["Mrabet [@mrabet2025]", "Trust-aware FL", "Trust-weighted aggregation", "No PQC or twin risk"],
        ["Bunko et al. [@bunko2026]", "Privacy-preserving FL-IDS survey", "Highlights leakage and poisoning risks",
         "No policy enforcement"],
        ["Mohammed and Ali [@mohammed2025sinkron]", "Non-IID FL-IDS", "Studies stability under heterogeneity",
         "No link to zero-trust actions"],
        ["Yang et al. [@yang2023cose]", "Poisoning defence", "Detects anomalous FL participants", "FL robustness only"],
        ["Thein et al. [@thein2024fgcs]", "Personalised FL-IDS", "Addresses heterogeneity and poisoning",
         "No ZTA, PQC or twin validation"],
        ["Sunil et al. [@sunil2025crc]", "6G secure smart cities", "Discusses fusion of emerging technologies",
         "Conceptual, not algorithmic"],
        ["Salim et al. [@salim2024fgcs]", "Twin and FL detection", "Combines twin and FL for IoT threat detection",
         "No adaptive ZTA or PQC"],
        ["Yigit et al. [@yigit2024icc]", "Twin for VANETs", "Twin-boosted autonomous attack detection",
         "Vehicular domain only"],
        ["**A-PQZTO (this work)**", "Adaptive PQC-aware ZTA with FL and twin",
         "Evidence-based trust, cost-aware PQ re-authentication, poisoning-resistant FL and twin-validated isolation, "
         "evaluated in a simulated city driven by measured detector outputs",
         "Simulated city; host-level PQC costs (Section 6.3)"],
    ]
    m.table(["Study", "Main focus", "Main contribution", "Limitation relative to A-PQZTO"], rows,
            "Representative studies and the gap addressed by this work.", col_widths=[1.5, 1.2, 2.2, 1.7],
            label="related", align=["left"] * 4)
