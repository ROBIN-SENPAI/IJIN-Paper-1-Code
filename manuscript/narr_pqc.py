# -*- coding: utf-8 -*-
"""Section 5.6: cost of post-quantum protection. Every number is read from pqc_summary.json (S["pqc"], written by
code/pqc_analyze.py from the OpenSSL 3.5.6 measurements) and city_summary.json (S["city"]); qualitative statements
are guarded by assertions, so that a re-run with different outcomes fails loudly instead of producing a wrong
sentence."""
import json
import os

from sections_exp import POL_LAB as L

RES = r"E:\A-PQZTO_work\results"
FIG = r"E:\A-PQZTO_work\figures"
Q_SIM_MS = 2.0              # handshake cost assumed by the city simulator (apq/city.py run_episode, pq_ms=2.0)
LINK_BPS = 250_000          # nominal IEEE 802.15.4 (2.4 GHz O-QPSK) bit rate, used only to illustrate airtime
SLICES = (("transport", "transportation"), ("safety", "public safety"), ("energy", "energy"), ("health", "healthcare"))


def _load(S):
    P = S.get("pqc") or json.load(open(os.path.join(RES, "pqc_summary.json"), encoding="utf-8"))
    C = S.get("city") or json.load(open(os.path.join(RES, "city_summary.json"), encoding="utf-8"))
    return P, C


def _s2(x):
    """Two significant figures, trailing zeros kept (0.090, 0.16, 2.4)."""
    return f"{x:#.2g}".rstrip(".")


def _ms(x):
    """Table format: three decimals below 1 ms, two above."""
    return f"{x:.3f}" if x < 1 else f"{x:.2f}"


def _msg(T, name, d):
    return sum(m["bytes"] for m in T["messages"] if m["msg"] == name and m["dir"] == d)


def block(m, S):
    P, C = _load(S)
    k, g, tc, th = P["kem_ms"], P["sig_ms"], P["tls"]["classical"], P["tls"]["hybrid"]
    kx = P["kex_per_handshake_ms"]
    mlk, hyb, x25 = k["ML-KEM-768"], k["X25519MLKEM768"], k["X25519"]
    dsa, ecd, edd, rsa = g["ML-DSA-65"], g["ECDSA P-256"], g["Ed25519"], g["RSA-2048"]
    x_d = x25["derive"]
    mlk_tot, hyb_tot, x_tot = kx["ML-KEM-768"]["ms"], kx["X25519MLKEM768"]["ms"], kx["X25519"]["ms"]
    # ---------------------------------------------------------------- checks behind the wording
    assert not kx["X25519"]["complete"] and kx["ML-KEM-768"]["complete"] and kx["X25519MLKEM768"]["complete"]
    assert abs(x_tot - 2 * x_d) < 1e-12                                   # lower bound = two derivations
    assert mlk["encaps"] < x_d and mlk["decaps"] < x_d                     # "each faster than one X25519 derivation"
    assert dsa["sign"] > hyb_tot and dsa["sign"] > max(dsa["verify"], mlk_tot)   # signing is the expensive part
    assert dsa["sign"] > 10 * ecd["sign"] and dsa["verify"] > ecd["verify"]
    ob = P["overhead"]["bytes"]
    cb, hb, delta = tc["total_bytes"], th["total_bytes"], ob["total_bytes"]
    assert delta == hb - cb and ob["total_ratio"] > 10                     # "main change was size"
    cert_d = th["cert_der_bytes_from_msg"] - tc["cert_der_bytes_from_msg"]
    cv_c, cv_h = _msg(tc, "CertificateVerify", "S->C"), _msg(th, "CertificateVerify", "S->C")
    sig_delta = cert_d + (cv_h - cv_c)
    ks_delta = (_msg(th, "ClientHello", "C->S") - _msg(tc, "ClientHello", "C->S")
                + _msg(th, "ServerHello", "S->C") - _msg(tc, "ServerHello", "S->C"))
    assert sig_delta + ks_delta == delta and sig_delta > 0.75 * delta      # certificate + signature dominate
    ch = P["sanity"]["ClientHello_delta"]
    ch_clause = ch["measured"] == ch["expected"] - 8 and "ec_point_formats" in ch.get("explanation", "")
    cq, hq = tc["client_cpu_ms"], th["client_cpu_ms"]
    cr, hr = tc["client_cpu_ms_range"], th["client_cpu_ms_range"]
    assert 0 < hq - cq < cr[1] - cr[0] and hr[0] < cr[1]                   # difference within the run-to-run spread
    assert any("X25519MLKEM768 + X25519" in n for n in P["notes"])         # s_time offers both key shares
    cw, hw = tc["wall_ms"], th["wall_ms"]
    assert hw - cw > hq - cq                                               # wall time grows more than client CPU
    stress = (S.get("stress") or {}).get("pqcost") or {}
    assert stress.get("pq_ms", Q_SIM_MS) == Q_SIM_MS
    assert abs(hq - Q_SIM_MS) / Q_SIM_MS < 0.1                             # "close to the assumed 2.0 ms"
    Ld = P["L_d_ms"]
    kap, kap_c = P["kappa_max"], P["kappa_max_classical"]               # L_d / Q, Q = 1000 * real_s / conns
    kap_w = {s: Ld[s] / hw for s, _ in SLICES}
    assert all(abs(Ld[s] / hq / kap[s] - 1) < 0.01 and abs(Ld[s] / cq / kap_c[s] - 1) < 0.01
               for s, _ in SLICES)                                         # same Q as the client CPU in the table
    assert min(kap_w.values()) > 1                                         # every slice admits kappa = 1 even so
    v = lambda p, key: C["summary"][f"{p}|benign"][key][0]
    pq, rq, pqf = v("apqzto", "pq_hs"), v("apqzto", "pq_reauth"), v("zta_fixedpqc", "pq_hs")
    assert 0 < rq < pq < pqf
    mb, mbf = pq * delta / 1e6, pqf * delta / 1e6
    cpu_s = pq * hq / 1000.0
    air_h, air_c = 8 * hb / LINK_BPS, 8 * cb / LINK_BPS
    assert air_h > max(Ld.values()) / 1000.0                               # airtime alone exceeds every budget
    nk, ns, nt = P["n_reps"]["kem"], P["n_reps"]["sig"], P["n_reps"]["s_time"]["hybrid"]

    m.heading("5.6 Cost of post-quantum protection", 2)
    m.label_next("tab", "pqc")
    m.label_next("fig", "pqc")
    m.para(
        "Table {tab:pqc} and Fig. {fig:pqc} give the measured costs. Key establishment was cheap. ML-KEM-768 "
        f"[@nist2024fips203] took {_s2(mlk['keygen'])} ms for key generation, "
        f"{_s2(mlk['encaps'])} ms for encapsulation and {_s2(mlk['decaps'])} ms for decapsulation, "
        f"{_s2(mlk_tot)} ms per exchange; encapsulation and decapsulation were each faster than one X25519 "
        f"derivation ({_s2(x_d)} ms). The hybrid X25519MLKEM768 group [@rfc10024] performs both exchanges and "
        f"took {_s2(hyb['keygen'])}, {_s2(hyb['encaps'])} and {_s2(hyb['decaps'])} ms, or {_s2(hyb_tot)} ms per "
        f"exchange. Signatures were the expensive part: ML-DSA-65 [@nist2024fips204] needed {_s2(dsa['sign'])} ms "
        f"to sign and {_s2(dsa['verify'])} ms to verify, against {_s2(ecd['sign'])} and {_s2(ecd['verify'])} ms "
        f"for ECDSA P-256 and {_s2(edd['sign'])} and {_s2(edd['verify'])} ms for Ed25519; RSA-2048 signing took "
        f"{_s2(rsa['sign'])} ms.")
    m.figure(os.path.join(FIG, "fig9_pqc.png"),
             f"Post-quantum cost measured with OpenSSL 3.5.6 on one laptop processor (Intel Core i7-4810MQ). (a) "
             f"Time per operation, median of {nk} (key establishment) or {ns} (signatures) repetitions, log scale; "
             "for X25519 and ECP-256 only the ECDH shared-secret derivation is timed. (b) Bytes of TLS 1.3 "
             "handshake messages over loopback, without record-layer overhead and session tickets. (c) Client CPU "
             f"time per handshake and wall time per connection, client and server on the same host; bars show the "
             f"median of {nt} runs and whiskers their range.", width_in=6.3, label="pqc")
    clause = (f"; the ClientHello grew by {ch['measured']:,} bytes rather than {ch['expected']:,} because OpenSSL "
              "omits the 8-byte ec_point_formats extension when no elliptic-curve group is offered") if ch_clause else ""
    m.para(
        f"In complete TLS 1.3 handshakes the main change was size. The hybrid handshake exchanged {hb:,} bytes of "
        f"handshake messages against {cb:,} for the classical one, {ob['total_ratio']:.1f} times as many. The "
        f"ML-DSA-65 certificate ({th['cert_der_bytes_from_msg']:,} bytes in DER against "
        f"{tc['cert_der_bytes_from_msg']:,}) and the CertificateVerify message ({cv_h:,} against {cv_c:,} bytes) "
        f"account for {sig_delta:,} of the {delta:,} additional bytes, and the larger key shares for the rest"
        f"{clause}. Client CPU time per handshake rose only from {cq:.2f} to {hq:.2f} ms, less than the spread "
        "between runs: signing happens on the server, and the s_time client offers both default key shares in "
        "either configuration, so its key-generation work is the same. The wall time per connection rose from "
        f"{cw:.2f} to {hw:.2f} ms because it also contains the server's work, ML-DSA-65 signing included.")
    rows = [
        ["*Primitive cost (ms per operation)*", "", "", ""],
        ["Key generation (client)", "n.t.^{a}", _ms(hyb["keygen"]), "–"],
        ["ECDH or encapsulation (server)", _ms(x_d) + "^{a}", _ms(hyb["encaps"]), "–"],
        ["ECDH or decapsulation (client)", _ms(x_d), _ms(hyb["decaps"]), f"+{_ms(hyb['decaps'] - x_d)}"],
        ["Key establishment, both sides", f"≥ {_ms(x_tot)}^{{a}}", _ms(hyb_tot), f"≤ +{_ms(hyb_tot - x_tot)}"],
        ["Sign CertificateVerify (server)", _ms(ecd["sign"]), _ms(dsa["sign"]), f"+{_ms(dsa['sign'] - ecd['sign'])}"],
        ["Verify CertificateVerify (client)", _ms(ecd["verify"]), _ms(dsa["verify"]),
         f"+{_ms(dsa['verify'] - ecd['verify'])}"],
        ["*Handshake messages (bytes)*", "", "", ""],
        ["Client → server", f"{tc['client_bytes']:,}", f"{th['client_bytes']:,}", f"+{ob['client_bytes']:,}"],
        ["Server → client", f"{tc['server_bytes']:,}", f"{th['server_bytes']:,}", f"+{ob['server_bytes']:,}"],
        ["   of which certificate (DER)", f"{tc['cert_der_bytes_from_msg']:,}", f"{th['cert_der_bytes_from_msg']:,}",
         f"+{cert_d:,}"],
        ["   of which CertificateVerify", f"{cv_c:,}", f"{cv_h:,}", f"+{cv_h - cv_c:,}"],
        ["Total", f"{cb:,}", f"{hb:,}", f"+{delta:,}"],
        ["*Time per full handshake (ms)*", "", "", ""],
        ["Client CPU time, $Q$", f"{cq:.2f} ({cr[0]:.2f}–{cr[1]:.2f})", f"{hq:.2f} ({hr[0]:.2f}–{hr[1]:.2f})",
         f"+{hq - cq:.2f}"],
        ["Wall time per connection^{b}", f"{cw:.2f} ({tc['wall_ms_range'][0]:.2f}–{tc['wall_ms_range'][1]:.2f})",
         f"{hw:.2f} ({th['wall_ms_range'][0]:.2f}–{th['wall_ms_range'][1]:.2f})", f"+{hw - cw:.2f}"],
        ["*Largest slowdown factor* $\\kappa_{\\mathrm{max}}=L_{d}/Q$", "", "", ""],
        ["Transportation / safety / energy / health", " / ".join(f"{kap_c[s]:.1f}" for s, _ in SLICES),
         " / ".join(f"{kap[s]:.1f}" for s, _ in SLICES), "–"],
    ]
    m.table([["Quantity", "Classical", "Hybrid post-quantum", "Hybrid − classical"],
             ["", "X25519 + ECDSA P-256", "X25519MLKEM768 + ML-DSA-65", ""]], rows,
            "Cost of one TLS 1.3 handshake with classical and hybrid post-quantum key establishment and "
            f"authentication (OpenSSL 3.5.6; primitive times are medians of {nk} or {ns} repetitions, handshake "
            f"times the median and range of {nt} runs).",
            col_widths=[2.3, 1.6, 1.8, 1.0], label="pqc", header_rows=2, align=["left", "center", "center", "center"],
            notes="^{a} For X25519, openssl speed times only the ECDH shared-secret derivation; each side also "
                  "generates a key pair, which is not timed (n.t.), so the classical sum of two derivations is a "
                  "lower bound. ^{b} Client and server on the same host, so the wall time includes the server's "
                  "work and connection set-up; s_time reports elapsed time in whole seconds. Bytes are handshake "
                  "messages including their 4-byte headers, without record-layer overhead and session tickets. "
                  "In both configurations the s_time client offered the X25519MLKEM768 and X25519 key shares. "
                  "Slice budgets $L_{d}$: transportation 10 ms, public safety 20 ms, energy 50 ms, healthcare "
                  "100 ms.")
    sl = ", ".join(f"{kap[s]:.1f} in {name}" if kap[s] < 20 else f"{kap[s]:.0f} in {name}" for s, name in SLICES[:-1])
    m.para(
        f"The simulator assumed $Q$ = {Q_SIM_MS:.1f} ms (Section 4.6), close to the measured {hq:.2f} ms. With the "
        "measured value, Eq. {eq:pq} admits re-authentication up to a device slowdown factor "
        f"$\\kappa_{{\\mathrm{{max}}}}=L_{{d}}/Q$ of {sl} and {kap['health']:.0f} in {SLICES[-1][1]}. Client CPU "
        "time is a lower bound on latency; taking the wall time as $Q$ lowers $\\kappa_{\\mathrm{max}}$ to "
        f"{kap_w['transport']:.1f} in the transportation slice, so every slice still admits the handshake at "
        f"$\\kappa$ = 1. Counted as full hybrid handshakes, the {pq:,.0f} post-quantum handshakes per hour that "
        "A-PQZTO performed in the city (Table {tab:citycost}) add about "
        f"{mb:.0f} MB of traffic per hour compared with classical handshakes ({mbf:.0f} MB for the {pqf:,.0f} "
        f"handshakes of {L['zta_fixedpqc']}) and take {cpu_s:.0f} s of client CPU time.")
    m.para(
        "These figures come from one laptop processor (Intel Core i7-4810MQ) with both endpoints on the loopback "
        "interface, so they include no radio latency, loss or fragmentation. On constrained radio links the extra "
        f"{delta / 1000:.1f} kB per handshake is likely to matter more than CPU time: at the 250 kbit/s of an IEEE "
        f"802.15.4 link, the hybrid handshake messages alone would need at least {air_h:.2f} s of airtime, against "
        f"{air_c:.2f} s for the classical ones. Microcontroller-class devices can also be one to two orders of "
        "magnitude slower than this processor; Section 5.7 therefore scales the handshake by $\\kappa$ and reports "
        "what happens once the transportation budget is exceeded.")
