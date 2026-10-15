# Real post-quantum cost measurements with OpenSSL 3.5 (FIPS 203 ML-KEM, FIPS 204 ML-DSA) on this host:
#  (1) primitive throughput with `openssl speed` for the algorithms used in the paper (repeated runs),
#  (2) TLS 1.3 handshakes on loopback, classical (X25519 + ECDSA P-256 certificate) versus hybrid post-quantum
#      (X25519MLKEM768 + ML-DSA-65 certificate): handshake bytes from the message trace; full-handshake rate from
#      `openssl s_time` (client user-CPU line and real-time line).
import json, os, re, subprocess, sys, time, tempfile, platform

OSSL = r"C:\Program Files\Git\mingw64\bin\openssl.exe"
OUT = r"E:\A-PQZTO_work\results\pqc"
os.makedirs(OUT, exist_ok=True)
KEMS = ["ML-KEM-512", "ML-KEM-768", "ML-KEM-1024", "X25519MLKEM768", "ecdhx25519", "ecdhp256"]
SIGS = ["ML-DSA-44", "ML-DSA-65", "ML-DSA-87", "ed25519", "ecdsap256", "rsa2048"]


def sh(args, **kw):
    return subprocess.run([OSSL] + args, capture_output=True, text=True, **kw)


def speed(names, reps, seconds):
    outs = []
    for r in range(reps):
        txt = ""
        for a in names:
            p = sh(["speed", "-seconds", str(seconds), a])
            txt += "\n".join(l for l in (p.stdout + p.stderr).splitlines() if not l.startswith("Doing")) + "\n"
        outs.append(txt)
    return outs


def tls_pair(tag, group, key_alg, port):
    d = tempfile.mkdtemp()
    key, crt = os.path.join(d, "k.pem"), os.path.join(d, "c.pem")
    if key_alg == "EC":
        sh(["req", "-x509", "-newkey", "ec", "-pkeyopt", "ec_paramgen_curve:P-256", "-nodes", "-keyout", key, "-out", crt,
            "-subj", "/CN=edge", "-days", "1"])
    else:
        sh(["req", "-x509", "-newkey", key_alg, "-nodes", "-keyout", key, "-out", crt, "-subj", "/CN=edge", "-days", "1"])
    srv = subprocess.Popen([OSSL, "s_server", "-accept", str(port), "-key", key, "-cert", crt, "-tls1_3", "-groups", group,
                            "-www", "-quiet"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(1.5)
    try:
        cl = subprocess.run([OSSL, "s_client", "-connect", f"127.0.0.1:{port}", "-tls1_3", "-groups", group, "-msg",
                             "-brief"], input="", capture_output=True, text=True, timeout=30)
        raw_trace = cl.stdout + cl.stderr
        msgs = re.findall(r"(>>>|<<<) TLS 1.3, Handshake \[length ([0-9a-f]+)\], (\w+)", raw_trace)
        hs = {"client_bytes": 0, "server_bytes": 0, "messages": []}
        for direc, ln, name in msgs:
            n = int(ln, 16)
            hs["client_bytes" if direc == ">>>" else "server_bytes"] += n
            hs["messages"].append((direc, name, n))
        rates = []
        for _ in range(3):
            st = subprocess.run([OSSL, "s_time", "-connect", f"127.0.0.1:{port}", "-new", "-time", "8"],
                                capture_output=True, text=True, timeout=60)
            m1 = re.search(r"([0-9]+) connections in ([0-9.]+)s; ([0-9.]+) connections/user sec", st.stdout)
            m2 = re.search(r"([0-9]+) connections in ([0-9.]+) real seconds", st.stdout)
            if m1:
                rec = {"conns": int(m1.group(1)), "real_s": float(m1.group(2)), "per_user_s": float(m1.group(3))}
                if m2:
                    rec.update(conns_wall=int(m2.group(1)), wall_s=float(m2.group(2)))
                rates.append(rec)
        return {"tag": tag, "group": group, "cert": key_alg, "handshake": hs, "s_time": rates,
                "cert_bytes": os.path.getsize(crt), "trace_raw": raw_trace[-20000:]}
    finally:
        srv.terminate()


if __name__ == "__main__":
    info = {"openssl": sh(["version", "-a"]).stdout, "platform": platform.platform(), "cpu": platform.processor(),
            "python": sys.version, "kems": KEMS, "sigs": SIGS}
    kem = speed(KEMS, reps=5, seconds=3)
    sig = speed(SIGS, reps=3, seconds=2)
    tls = [tls_pair("classical", "x25519", "EC", 44331), tls_pair("hybrid_pq", "X25519MLKEM768", "ML-DSA-65", 44332)]
    json.dump({"info": info, "kem_raw": kem, "sig_raw": sig, "tls": tls},
              open(os.path.join(OUT, "pqc_bench.json"), "w"), indent=1)
    print("saved")
