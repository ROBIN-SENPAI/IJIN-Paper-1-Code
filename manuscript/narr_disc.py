# -*- coding: utf-8 -*-
"""Limitations and threats to validity (Section 6.3). The paragraphs contain no result numbers (only design
constants); the qualitative statements about results (the twin approved no isolation in the nominal worm and only a
few during flooding, its effect under the fast worm was not significant, the behavioural term had no measurable
effect) are checked by assertions in narr_end.build before this list is used. Previous version:
backup/narr_disc_before_update.py."""

LIMITATIONS = [
    "The city is simulated, and no part of A-PQZTO has been deployed. The threat scores are measured detector "
    "outputs, but the contact graph is a synthetic small-world graph, the worm follows a simple susceptible–infected "
    "process and attackers act at fixed rates, without throttling their activity as suspicion rises. Operator review "
    "is idealised, which favours policies that quarantine early.",
    "All detector evidence in the simulator is re-sampled from one dataset, TON_IoT, and every attack flow belongs "
    "to a class the detectors saw in training, so the results show how the loop uses a detector that recognises the "
    "attack, not how it copes with unseen traffic. TON_IoT has no session identifiers, so related flows may sit in "
    "both training and test data, and its detection rates are probably optimistic. The exclusion of Edge-IIoTset "
    "depends on our cleaning rules.",
    "Design choices and operating points were fixed on validation episodes. Earlier development runs (seeds 1–20), "
    "which drew on the same test evidence pool, had shown that the original design reacted more slowly than FL-only "
    "IDS and prompted the validation-only comparison of variants; the reported runs (seeds 21–40) were made after "
    "the design was fixed. All policies were compared at one budget (0.5% false blocking, 0.5% weighted "
    "disruption), and their ranking may change at another.",
    "Two results follow from modelling assumptions rather than measurement. Impostor success under post-quantum "
    "re-authentication is low because we assume that a forged classical credential fails ML-DSA verification, and "
    "harvest-now-decrypt-later exposure is an accounting of how each session's keys were established; no recorded "
    "traffic was attacked.",
    "Post-quantum costs were measured with OpenSSL on one x86 laptop processor over the loopback interface. They "
    "capture the computation and message sizes of real handshakes but not the processors and memories of IoT "
    "devices, and the extra kilobytes were not simulated on radio links, where they cost airtime and energy; energy "
    "was not measured.",
    "The digital twin has the weakest evidence of all components. It approved no isolation in the nominal worm "
    "scenario and only a few during flooding, and under the fast worm its isolations reduced infections slightly "
    "and not significantly; its demonstrated value is as a gate against unnecessary cluster isolations. The behavioural "
    "profile, the one modelled input, made no measurable difference; since we chose its separation between benign "
    "and attacking devices, this says little about real behavioural features.",
    "The federated experiments simulate all 12 clients on one machine, with full participation and no stragglers "
    "or network delay. They cover one model family and two poisoning attacks, without attackers that know the "
    "aggregation rule, and they provide data locality, not formal privacy, since neither differential privacy nor "
    "secure aggregation was used.",
]
