# -*- coding: utf-8 -*-
"""Section 3: system model, threat model and the A-PQZTO framework."""
import os

FIG = r"E:\A-PQZTO_work\figures"
ORIG = r"E:\A-PQZTO_work\figures\original"


def framework(m, S):
    m.heading("3. Proposed A-PQZTO Framework", 1)
    m.heading("3.1 System model", 2)
    m.label_next("fig", "system")
    m.para("We consider a 6G-oriented smart-city IoT network with four service domains: intelligent transportation "
           "(roadside sensors, traffic cameras, signal controllers, vehicular gateways), smart energy (smart meters, "
           "distributed-energy sensors, grid automation and substation monitors), healthcare IoT (wearables, hospital "
           "edge gateways, emergency and patient monitors) and public safety (surveillance, emergency communication, "
           "environmental monitoring, incident-response gateways). The reference city has 1,500 devices (450 in "
           "transportation, 375 in energy, 300 in healthcare and 375 in public safety) served by 12 edge nodes, three "
           "per domain (Fig. {fig:system}). Each edge node also acts as a federated-learning client.")
    m.para("Each domain runs on its own slice. The transportation slice is latency-critical; the energy slice gives "
           "priority to integrity, because a forged measurement or command can affect grid stability; the healthcare "
           "slice is privacy-critical; and the public-safety slice must stay available during incidents. We express "
           "these differences with a slice sensitivity $s_{d}$ (0.6, 0.8, 1.0 and 0.9, respectively) and a latency "
           "budget $L_{d}$ for security handshakes (10, 50, 100 and 20 ms). A city-level digital twin mirrors devices, "
           "edge nodes, slices and their dependencies; it simulates attack spread and tests actions before they are "
           "enforced. Raw records remain at the edge, whereas model updates, threat indicators and trust metadata are "
           "shared.")
    m.figure(os.path.join(FIG, "fig2_system_model.png"),
             "Smart-city system model: (a) service domains and device counts; (b) mapping of devices to the 12 edge "
             "nodes and the slice parameters $s_{d}$ and $L_{d}$; (c) the control loop in which device evidence, the "
             "federated detector and the digital twin feed the A-PQZTO policy engine, whose actions are enforced in "
             "the city.", width_in=6.3, label="system")
    m.label_next("tab", "notation")
    m.para("Table {tab:notation} lists the notation used in the rest of the paper.")
    rows = [
        ["$i$, $k$, $d$", "Device, edge node (FL client), service domain", "–"],
        ["$N$, $K$", "Number of devices and edge nodes", "1,500; 12"],
        ["$s_{d}$, $L_{d}$", "Slice sensitivity and handshake latency budget of domain $d$", "0.6–1.0; 10–100 ms"],
        ["$B_{i}$", "Behavioural consistency (from the device's traffic profile)", "[0, 1]"],
        ["$H_{i}$", "Reputation, a slow memory of past evidence", "[0, 1]"],
        ["$A_{i}$", "Authentication validity: PQ-verified, classical, failed", "1, 0.85, 0"],
        ["$F_{i}$", "Federated threat probability from the global detector", "[0, 1]"],
        ["$D_{i}$", "Digital-twin propagation risk (examined as a design variant)", "[0, 1]"],
        ["$T_{i}$", "Trust score, Eq. {eq:trust}", "[0, 1]"],
        ["$\\tau_{a,d}$", "Action threshold for action $a$ in domain $d$, Eq. {eq:thresh}", "–"],
        ["$\\theta$", "Threshold offset that sets the operating point (Section 4.4)", "–"],
        ["$Q$, $\\kappa$", "Post-quantum handshake latency and device slowdown factor", "ms; ≥1"],
        ["$w^{t}$, $\\Delta_{k}^{t}$", "Global model and update of client $k$ in round $t$", "–"],
        ["$r_{k}$, $\\omega_{k}$", "Reliability and aggregation weight of client $k$", "[0, 1]"],
        ["$\\hat{G}$, $\\hat{\\beta}$", "Twin copy of the contact graph and propagation rate", "–"],
        ["$c_{i}$", "Criticality of device $i$", "[0.2, 1]"],
    ]
    m.table(["Symbol", "Meaning", "Range or value"], rows, "Main notation.", col_widths=[1.2, 4.0, 1.4],
            label="notation", align=["left", "left", "left"])

    m.heading("3.2 Threat model", 2)
    m.label_next("fig", "threat")
    m.label_next("tab", "threat")
    m.para("Attackers may target devices, links, slices, edge nodes, federated updates, the zero-trust workflow or "
           "long-lived encrypted traffic. External attackers flood, scan or spoof; internal attackers control "
           "compromised devices that still hold valid credentials, which is why a successful authentication is never "
           "treated as permanent trust. Fig. {fig:threat} and Table {tab:threat} group the threats into five "
           "categories and give, for each category, the scenario that represents it in the evaluation (Section 4.3).")
    m.figure(os.path.join(FIG, "fig3_threat_model.png"),
             "Threat model and the scenario that represents each threat in the evaluation: (a) network attacks; "
             "(b) IoT compromise; (c) poisoning of federated learning; (d) identity and post-quantum threats.",
             width_in=6.3, label="threat")
    rows = [
        ["Network attacks", "DDoS, DoS, scanning", "Links, edge nodes, slices", "Trust reduction, rate limiting, quarantine",
         "Flooding (30 devices)"],
        ["IoT compromise", "Worm-like lateral spread, backdoors, ransomware", "Sensors, gateways, actuators",
         "Behavioural and federated evidence, quarantine, twin-validated cluster isolation", "Worm (3 seed devices)"],
        ["Data manipulation", "False data injection", "Energy-slice devices", "Continuous trust scoring",
         "Data injection (15 devices)"],
        ["FL attacks", "Label flipping, scaled sign-flipped updates", "Local updates, aggregator",
         "Trust-aware aggregation", "1–3 malicious clients of 12"],
        ["ZTA evasion", "Valid-credential misuse; impostor with a forged classical credential",
         "Policy engine, sensitive slices", "Continuous scoring, PQ re-authentication, blocking",
         "Credential misuse (8 devices); impostor (12 entities)"],
    ]
    m.table(["Threat category", "Representative attacks", "Primary target", "A-PQZTO mechanism", "Evaluation scenario"],
            rows, "Threat categories, mitigation mechanisms and the scenarios used in the evaluation.",
            col_widths=[1.15, 1.5, 1.2, 1.7, 1.35], label="threat", align=["left"] * 5)
    m.para("For harvest-now-decrypt-later, we assume an adversary who records traffic today, later breaks the "
           "classical key exchange and then decrypts the recorded traffic. For the impostor scenario, we further assume "
           "that a forged classical credential passes classical verification but fails post-quantum (ML-DSA) "
           "verification. This assumption is ours, not a measured property, and the results that depend on it are "
           "reported separately (Section 5.4).")

    m.heading("3.3 A-PQZTO architecture", 2)
    m.label_next("fig", "arch")
    m.para("A-PQZTO is organised in five layers (Fig. {fig:arch}). The IoT and slice layer generates flows, telemetry "
           "and authentication requests. The edge-intelligence layer scores flows, maintains a behavioural profile and "
           "a reputation for each device, and enforces decisions. The federated layer trains the shared detector "
           "across the 12 edge nodes, and the digital-twin layer estimates propagation risk and validates cluster-wide "
           "actions. Finally, the orchestration layer combines all evidence into a trust score and selects the action, "
           "which includes deciding when to invoke a post-quantum handshake. Enforcement outcomes are fed back into the "
           "reputation, the twin state and the trust that the federation places in each edge node.")
    m.figure(os.path.join(FIG, "fig1_architecture.png"),
             "A-PQZTO architecture. Evidence from the edge, the federation, the digital twin and the post-quantum "
             "identity layer feeds the trust score of Eq. {eq:trust}; the action is chosen with slice-aware "
             "thresholds, Eq. {eq:thresh}, and post-quantum re-authentication is scheduled only when it fits the slice "
             "latency budget, Eq. {eq:pq}.", width_in=6.3, label="arch")

    m.heading("3.4 Adaptive trust scoring and policy decision", 2)
    m.label_next("fig", "trust")
    m.para("At each decision step $t$ (10 s), A-PQZTO computes the trust score of device $i$ as")
    m.equation("T_{i}(t)=\\min\\left\\{\\mathrm{clip}_{[0,1]}\\left(\\alpha_{1}B_{i}+\\alpha_{2}H_{i}+\\alpha_{3}A_{i}"
               "-\\alpha_{4}F_{i}\\right),\\;1-F_{i}\\right\\}", label="trust")
    m.para("with $\\alpha=(0.35,0.25,0.40,0.60)$. Behavioural consistency $B_{i}=1-\\bar{u}_{i}$ is one minus a "
           "smoothed anomaly score of the device's traffic profile; reputation follows "
           "$H_{i}\\leftarrow0.98H_{i}+0.02(1-\\max(\\bar{u}_{i},F_{i}))$; $F_{i}$ is the exponentially smoothed "
           "attack probability that the federated detector assigns to the device's flows. The positive weights sum to one, "
           "so a device with clean evidence and a verified post-quantum identity reaches $T_{i}=1$. The minimum is a "
           "zero-trust veto: however good its credentials and history, a device cannot be trusted more than "
           "$1-F_{i}$, so strong threat evidence lowers its trust whatever its authentication state. The original "
           "A-PQZTO design used the additive score alone and also subtracted the twin's propagation risk $D_{i}$ "
           "(Section 3.7). We compared these variants on validation episodes only (Section 4.4). At the same "
           "false-blocking and disruption budget, the purely additive form let slightly more credential misuse "
           "through, and the $D_{i}$ term weakened containment: it also lowers the trust of benign devices in densely "
           "connected parts of the graph, which forces a less sensitive operating point. Both variants are therefore "
           "reported as ablations (Section 5.5), and the final design uses the twin only to validate cluster-wide "
           "actions. Post-quantum overhead and slice latency are kept out of $T_{i}$ and enter only the choice of "
           "action (Section 3.5), because the cost of protecting a device says nothing about whether it can be "
           "trusted.")
    m.para("Actions are selected with slice-aware thresholds")
    m.equation("\\tau_{a,d}=\\tau_{a}+\\theta+0.1\\left(s_{d}-0.8\\right)", label="thresh")
    m.para("with base values $\\tau_{allow}=0.75$, $\\tau_{restrict}=0.55$, $\\tau_{quar}=0.40$ and "
           "$\\tau_{block}=0.20$, so the same trust value triggers an earlier response in the healthcare slice than in the "
           "transportation slice. A device whose trust falls below $\\tau_{allow,d}$ is still allowed but becomes a "
           "candidate for post-quantum re-authentication (Section 3.5); below $\\tau_{restrict,d}$ it is rate-limited "
           "to 30% of its normal activity; below $\\tau_{quar,d}$ it is quarantined until operator review (5 min); and "
           "below $\\tau_{block,d}$, or after a failed authentication, it is blocked until review (10 min). The offset "
           "$\\theta$ sets the operating point and is calibrated on validation episodes (Section 4.4). Fig. "
           "{fig:trust} shows the complete workflow.")
    m.figure(os.path.join(FIG, "fig4_trust_workflow.png"),
             "Trust and decision workflow: (a) evidence for each device; (b) trust score and slice-aware thresholds; "
             "(c) actions and their conditions; (d) feedback after enforcement.", width_in=6.3, label="trust")

    m.heading("3.5 Post-quantum authentication and key establishment", 2)
    m.para("A-PQZTO uses hybrid key establishment (X25519 combined with ML-KEM-768) and ML-DSA-65 device identities "
           "[@nist2024fips203; @nist2024fips204; @rfc10024]. In the sensitive energy, healthcare and public-safety "
           "slices, every session (at onboarding and at each re-key, every 30 min) uses hybrid key establishment and "
           "verifies the device's ML-DSA identity; transportation sessions start with classical keys and credentials. "
           "A device whose identity has not yet been verified with ML-DSA is "
           "re-authenticated with post-quantum credentials as soon as its trust falls below $\\tau_{allow,d}$, "
           "provided that the handshake fits the slice budget:")
    m.equation("\\mathrm{PQ}_{i}=1\\left[T_{i}<\\tau_{allow,d}\\right]\\cdot1\\left[\\neg V_{i}"
               "\\right]\\cdot1\\left[Q\\kappa\\leq L_{d}\\right]", label="pq")
    m.para("Here $V_{i}$ marks a device whose identity is already ML-DSA-verified, $Q$ is the "
           "measured handshake latency and $\\kappa\\geq1$ a slowdown factor for constrained devices. "
           "A successful re-authentication sets $A_{i}=1$; a failed one sets $A_{i}=0$ and blocks the device. "
           "Post-quantum protection therefore stops entities whose credentials fail ML-DSA verification and affects two "
           "measurable quantities: the cost of handshakes and the share of sensitive sessions exposed to "
           "harvest-now-decrypt-later attacks. It does not detect network attacks.")

    m.heading("3.6 Federated threat intelligence with trust-aware aggregation", 2)
    m.para("The 12 edge nodes train a multi-class detector. In round $t$ each client starts from the global model "
           "$w^{t}$, runs local stochastic gradient steps on its own flows and returns the update "
           "$\\Delta_{k}^{t}$. FedAvg computes $w^{t+1}=w^{t}+\\sum_{k}n_{k}\\Delta_{k}^{t}/\\sum_{k}n_{k}$, where "
           "$n_{k}$ is the number of local samples [@mcmahan2017fedavg]. A-PQZTO replaces this average with a "
           "trust-aware rule. Each update is clipped to 1.5 times the median update norm, compared with the "
           "coordinate-wise median $\\tilde{\\Delta}^{t}$ of all updates and weighted by a reliability score that keeps "
           "a memory of earlier rounds:")
    m.equation("r_{k}^{t}=0.7r_{k}^{t-1}+0.3\\max\\left(0,\\cos(\\bar{\\Delta}_{k}^{t},\\tilde{\\Delta}^{t})\\right),\\quad "
               "w^{t+1}=w^{t}+\\frac{\\sum_{k}\\omega_{k}\\bar{\\Delta}_{k}^{t}}{\\sum_{k}\\omega_{k}},\\quad "
               "\\omega_{k}=n_{k}r_{k}^{t}e_{k}", label="ta")
    m.para("where $\\bar{\\Delta}_{k}^{t}$ is the clipped update and $e_{k}\\in[0,1]$ is the trust that the zero-trust "
           "layer places in edge node $k$ (equal to one in the federated experiments). An update that points away from "
           "the consensus adds nothing to its client's reliability, so the client's weight shrinks by a factor of 0.7 "
           "in every round in which this repeats, while norm clipping bounds its influence in the meantime. A cut-off "
           "on $r_{k}$ that would exclude clients outright was tuned on the validation split (Section 4.2); the selected "
           "value is zero, so no client is ever excluded and the rule relies on weighting alone. It needs no assumed "
           "number of attackers, but its median reference presumes that they are a minority.")

    m.heading("3.7 Digital-twin risk prediction and policy validation", 2)
    m.label_next("fig", "twin")
    m.para("The twin holds its own copy $\\hat{G}$ of the device contact graph and a prior estimate "
           "$\\hat{\\beta}$ = 0.03 of the per-contact propagation probability, which it uses in every situation "
           "because it does not know which attack is under way. The graph is not exact: by default, 10% of the true "
           "links are missing from $\\hat{G}$, and the same number of spurious links between devices of the same "
           "domain is added. For a device with $F_{i}>0.3$, the twin can "
           "estimate how far a compromise could reach within a horizon of $h$ = 12 steps (2 min):")
    m.equation("D_{i}=\\mathrm{clip}_{[0,1]}\\left(\\frac{\\hat{\\beta}hn_{1,i}+\\frac{1}{2}(\\hat{\\beta}h)^{2}n_{2,i}}{5}"
               "\\right)c_{i}s_{d}", label="twinrisk")
    m.para("where $n_{1,i}$ and $n_{2,i}$ count susceptible one- and two-hop neighbours in $\\hat{G}$ and $c_{i}$ is the "
           "device criticality. This risk term enters the trust score only in the original design (Section 3.4), which "
           "is evaluated as an ablation. Because isolating an edge cluster disrupts every device in it, the twin "
           "validates this action before it is taken (Fig. {fig:twin}). For each cluster $k$ that contains suspected devices, the twin "
           "samples initial compromises from the belief $b_{j}=F_{j}(1-H_{j})$ of the suspected devices in $k$. It then "
           "rolls out $M$ = 8 propagation runs over $h$ steps, with and without isolating $k$ and using common random "
           "numbers, and isolates the cluster only if")
    m.equation("\\bar{I}_{out}^{(no\\ isolation)}-\\bar{I}_{out}^{(isolation)}\\geq g_{min}=1", label="twinrule")
    m.para("where $\\bar{I}_{out}$ is the expected number of infections that escape the cluster. Clusters whose expected "
           "number of compromised devices is below 0.5 are not evaluated. Each isolation lasts 30 steps and is then "
           "re-evaluated.")
    m.figure(os.path.join(FIG, "fig5_twin_validation.png"),
             "Digital-twin validation of a cluster isolation: (a) an edge cluster of the simulated city (125 devices) "
             "on the twin's copy of the contact graph, with an example infection belief; (b) the roll-out procedure "
             "and decision rule "
             "of Eq. {eq:twinrule}.", width_in=6.3, label="twin")
