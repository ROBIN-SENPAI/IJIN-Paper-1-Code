# Conceptual figures redrawn to match the implemented system: Fig. 1 architecture, Fig. 2 system model, Fig. 3 threat
# model, Fig. 4 trust and decision workflow, Fig. 5 digital-twin validation (drawn on the twin's copy of the simulated
# city graph). All figures are drawn in inch coordinates at about 6.5 in width, so that every text is at least 7 pt when
# the figure is inserted 6.3 in wide.
import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import networkx as nx
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch, Rectangle

FIG = r"E:\A-PQZTO_work\figures"
os.makedirs(FIG, exist_ok=True)
plt.rcParams.update({"font.family": "Times New Roman", "font.size": 8, "mathtext.fontset": "stix"})
INK, INK2 = "#0b0b0b", "#52514e"
C = dict(iot=("#f0efec", "#8a8985"), edge=("#e6f1fb", "#2a78d6"), fl=("#dbe9fb", "#1d5fb3"),
         twin=("#d9f2e8", "#1baf7a"), pqc=("#ece9f8", "#4a3aa7"), zt=("#fde3d7", "#eb6834"),
         # service domains (Okabe-Ito hues) and threat elements
         transport=("#e1edf7", "#0072B2"), energy=("#fcf0d6", "#c98a00"), health=("#f7e5ef", "#b8659a"),
         safety=("#d6efe6", "#00896a"), thr=("#f9ddd2", "#c0461a"), pane=("#ffffff", "#b8b6b0"))
FS, FS_S, FS_H, FS_P = 7.7, 7.5, 8.2, 8.8          # body, smallest, box heading, panel title (pt)
LH = 1.2 / 72                                       # line height per pt of font size (in)


def canvas(w, h):
    fig = plt.figure(figsize=(w, h))
    ax = fig.add_axes([0, 0, 1, 1]); ax.set_xlim(0, w); ax.set_ylim(0, h); ax.axis("off")
    return fig, ax


def box(ax, x, y, w, h, text, key, fs=FS, bold=False, fill=True, lw=0.9, ha="center", r=0.05, ls="-", fc=None,
        ec=None, color=INK, z=2):
    fc0, ec0 = C[key]
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle=f"round,pad=0,rounding_size={r}",
                                fc=fc or (fc0 if fill else "white"), ec=ec or ec0, lw=lw, ls=ls, zorder=z))
    if text:
        tx = x + w / 2 if ha == "center" else x + 0.07
        ax.text(tx, y + h / 2, text, ha=ha, va="center", fontsize=fs, color=color,
                fontweight="bold" if bold else "normal", linespacing=1.18, zorder=z + 1)


def tbox(ax, x, y, w, h, title, body, key, fill=False, ha="center", fs=FS, fsh=FS_H, lw=0.9, top=0.06, fc=None):
    """Box with a bold heading line and a body below it, both anchored at the top."""
    box(ax, x, y, w, h, "", key, fill=fill, lw=lw, fc=fc)
    tx = x + w / 2 if ha == "center" else x + 0.07
    yy = y + h - top
    if title:
        ax.text(tx, yy, title, ha=ha, va="top", fontsize=fsh, fontweight="bold", color=INK, zorder=4)
        yy -= fsh * LH + 0.015
    if body:
        ax.text(tx, yy, body, ha=ha, va="top", fontsize=fs, color=INK, linespacing=1.2, zorder=4)


def arrow(ax, p, q, color=INK2, lw=0.9, ls="-", rad=0.0, text=None, toff=(0, 0), fs=FS_S, ms=8, ha="center",
          style="-|>"):
    ax.add_patch(FancyArrowPatch(p, q, arrowstyle=style, mutation_scale=ms, color=color, lw=lw, linestyle=ls,
                                 connectionstyle=f"arc3,rad={rad}", shrinkA=0, shrinkB=0, zorder=3))
    if text:
        ax.text((p[0] + q[0]) / 2 + toff[0], (p[1] + q[1]) / 2 + toff[1], text, fontsize=fs, color=INK2,
                ha=ha, va="center", style="italic")


def polyarrow(ax, pts, color=INK2, lw=0.9, ms=8):
    xs, ys = zip(*pts)
    ax.plot(xs[:-1], ys[:-1], color=color, lw=lw, solid_capstyle="butt", zorder=3)
    ax.add_patch(FancyArrowPatch(pts[-2], pts[-1], arrowstyle="-|>", mutation_scale=ms, color=color, lw=lw,
                                 shrinkA=0, shrinkB=0, zorder=3))


def pane(ax, x, y, w, h, label):
    box(ax, x, y, w, h, "", "pane", fill=False, lw=0.8, r=0.06, z=1)
    ax.text(x + 0.08, y + h - 0.06, label, ha="left", va="top", fontsize=FS_P, fontweight="bold", color=INK)


def save(fig, name):
    for ext, kw in ((".png", {}), (".tif", {"pil_kwargs": {"compression": "tiff_lzw"}})):
        fig.savefig(os.path.join(FIG, name + ext), dpi=400, bbox_inches="tight", pad_inches=0.04, facecolor="white",
                    **kw)
    plt.close(fig)


# ------------------------------------------------------------------------------------------------------ Fig. 1
def fig1_architecture():
    W, H = 6.5, 5.6
    fig, ax = canvas(W, H)
    R = 6.2                                          # right edge of the layer boxes; the feedback loop runs outside
    # orchestration layer (top)
    box(ax, 0.05, 4.52, R - 0.05, 1.03, "", "zt")
    ax.text(0.13, 5.5, "Adaptive zero-trust orchestration (policy decision point)", ha="left", va="top",
            fontsize=FS_P, fontweight="bold")
    yb, hb = 4.6, 0.66
    box(ax, 0.13, yb, 2.12, hb, "Trust score with zero-trust veto, Eq. (1)\n"
        "$T_i=\\min\\{\\mathrm{clip}(\\alpha_1B_i+\\alpha_2H_i+\\alpha_3A_i$\n$-\\,\\alpha_4F_i),\\;1-F_i\\}$", "zt",
        fill=False, fs=FS_S)
    box(ax, 2.39, yb, 1.82, hb, "Slice-aware action selection, Eq. (2):\nthresholds shifted by $s_d$; PQ re-\n"
        "authentication only if the handshake\nfits the latency budget $L_d$, Eq. (3)", "zt", fill=False, fs=FS_S)
    box(ax, 4.35, yb, 1.77, hb, "Enforcement at the edge (PEP):\nallow | restrict | quarantine |\n"
        "block | PQ re-authenticate |\nisolate edge cluster", "zt", fill=False, fs=FS_S)
    arrow(ax, (2.25, yb + hb / 2), (2.39, yb + hb / 2), ms=7)
    arrow(ax, (4.21, yb + hb / 2), (4.35, yb + hb / 2), ms=7)
    # three middle columns
    cols = [("fl", 0.05, "Federated threat intelligence", "$F_i$",
             ["12 edge clients train locally;\nraw flows never leave the edge",
              "Trust-aware aggregation, Eq. (4):\nmedian reference, norm clipping,\nreliability $r_k$ of each client",
              "Global detector $\\rightarrow$ threat\nprobability $F_i$ of every device"]),
            ("twin", 2.13, "Digital twin (policy validator)", "validated isolation",
             ["Imperfect copy $\\hat{G}$ of the contact\ngraph and propagation rate $\\hat{\\beta}$",
              "Infection belief of suspected devices\nfrom detector evidence and reputation",
              "Monte Carlo roll-outs validate\ncluster isolation before it is applied"]),
            ("pqc", 4.21, "Post-quantum identity and keys", "$A_i$, PQ cost",
             ["Hybrid X25519 + ML-KEM-768 key\nestablishment (FIPS 203); ML-DSA-65\ndevice identity (FIPS 204)",
              "PQ sessions for sensitive slices;\non-demand PQ re-authentication\nwhen trust drops",
              "Authentication validity $A_i$;\nexposure to harvest-now-\ndecrypt-later is measured"])]
    cw, y0, y1 = 1.99, 2.2, 4.22
    for key, x, title, out, items in cols:
        box(ax, x, y0, cw, y1 - y0, "", key)
        ax.text(x + cw / 2, y1 - 0.06, title, ha="center", va="top", fontsize=FS_H, fontweight="bold")
        for j, t in enumerate(items):
            box(ax, x + 0.07, 3.38 - 0.58 * j, cw - 0.14, 0.52, t, key, fill=False, fs=FS_S)
        xc = x + cw / 2
        arrow(ax, (xc, y1), (xc, 4.52), color=C[key][1], lw=1.1)
        ax.text(xc + 0.06, (y1 + 4.52) / 2, out, fontsize=FS_S, color=C[key][1], va="center", ha="left")
    # edge intelligence
    box(ax, 0.05, 1.06, R - 0.05, 0.89, "", "edge")
    ax.text(0.13, 1.9, "Edge intelligence (12 edge nodes, 3 per domain)", ha="left", va="top", fontsize=FS_H,
            fontweight="bold")
    ew = (R - 0.05 - 0.16 - 3 * 0.1) / 4
    for j, t in enumerate(["Flow scoring with the global\n(or local) detector", "Behavioural profile of each\n"
                           "device $\\rightarrow$ consistency $B_i$", "Reputation $H_i$: slow memory\nof past evidence",
                           "Enforcement point for the\ndecisions of the orchestrator"]):
        box(ax, 0.13 + (ew + 0.1) * j, 1.13, ew, 0.5, t, "edge", fill=False, fs=FS_S)
    for x in (1.045, 3.125, 5.205):
        arrow(ax, (x, 1.95), (x, 2.2), lw=1.0)
    # IoT layer
    box(ax, 0.05, 0.0, R - 0.05, 0.81, "", "iot")
    ax.text(0.13, 0.76, "IoT devices and 6G slices (1,500 devices)", ha="left", va="top", fontsize=FS_H,
            fontweight="bold")
    for j, (d, n, s, L, req) in enumerate([("Transportation", 450, 0.6, 10, "latency"),
                                           ("Smart energy", 375, 0.8, 50, "integrity"),
                                           ("Healthcare", 300, 1.0, 100, "privacy"),
                                           ("Public safety", 375, 0.9, 20, "availability")]):
        box(ax, 0.13 + (ew + 0.1) * j, 0.07, ew, 0.47, f"{d}: {n} devices\n{req}, $s_d$ = {s}, $L_d$ = {L} ms", "iot",
            fill=False, fs=FS_S)
    # IoT -> edge
    arrow(ax, (3.125, 0.81), (3.125, 1.06), lw=1.0)
    ax.text(3.19, 0.935, "flows, telemetry, authentication requests", fontsize=FS_S, color=INK2, va="center",
            ha="left", style="italic")
    # feedback loop
    zc = C["zt"][1]
    ax.plot([R, R + 0.12, R + 0.12], [5.0, 5.0, 1.5], color=zc, lw=1.1)
    ax.add_patch(FancyArrowPatch((R + 0.12, 1.5), (R, 1.5), arrowstyle="-|>", mutation_scale=8, color=zc, lw=1.1,
                                 shrinkA=0, shrinkB=0))
    ax.text(R + 0.17, 3.25, "decisions and feedback: reputation, twin state, edge trust", rotation=90, fontsize=FS_S,
            color=zc, va="center", ha="left", style="italic")
    save(fig, "fig1_architecture")


# ------------------------------------------------------------------------------------------------------ Fig. 2
DOMS = [("Transportation", 450, "transport", "roadside sensors, traffic cameras, signal\ncontrollers, vehicular gateways",
         "latency-critical", 0.6, 10, "classical keys"),
        ("Smart energy", 375, "energy", "smart meters, distributed-energy sensors,\ngrid automation, substation monitors",
         "integrity", 0.8, 50, "hybrid PQ keys"),
        ("Healthcare IoT", 300, "health", "wearables, hospital edge gateways,\nemergency and patient monitors",
         "privacy-critical", 1.0, 100, "hybrid PQ keys"),
        ("Public safety", 375, "safety", "surveillance, emergency communication,\nenvironmental monitoring, "
         "incident-response gateways", "availability", 0.9, 20, "hybrid PQ keys")]


def fig2_system_model():
    W, H = 6.5, 4.85
    fig, ax = canvas(W, H)
    # (a) service domains -------------------------------------------------------------------------------------
    ax0, ay0, aw, ah = 0.0, 2.42, 2.62, 2.43
    pane(ax, ax0, ay0, aw, ah, "(a) Service domains and devices")
    top = ay0 + ah - 0.27
    rh = [0.43, 0.43, 0.43, 0.43]
    for (name, n, key, ex, *_), h in zip(DOMS, rh):
        y = top - h
        box(ax, 0.08, y, aw - 0.16, h, "", key, lw=0.8)
        ax.add_patch(Rectangle((0.08, y + 0.04), 0.05, h - 0.08, fc=C[key][1], ec="none", zorder=3))
        ax.text(0.19, y + h - 0.045, f"{name}: {n} devices", ha="left", va="top", fontsize=FS, fontweight="bold")
        ax.text(0.19, y + h - 0.045 - FS * LH - 0.01, ex, ha="left", va="top", fontsize=FS_S, linespacing=1.15)
        top = y - 0.045
    ax.text(ax0 + aw / 2, ay0 + 0.15, "$N$ = 1,500 devices, $K$ = 12 edge nodes, 4 slices", ha="center",
            va="center", fontsize=FS)
    # (b) device-to-edge mapping and slices ---------------------------------------------------------------------
    bx0, by0, bw, bh = 2.7, 2.42, 3.8, 2.43
    pane(ax, bx0, by0, bw, bh, "(b) Device-to-edge mapping and 6G slices")
    gw = 0.9
    gx = [bx0 + 0.1 + gw / 2 + g * gw for g in range(4)]
    nodes = []
    for g, (name, n, key, _, req, s, L, keys) in enumerate(DOMS):
        c = gx[g]
        box(ax, c - 0.42, 4.05, 0.84, 0.39, f"{name}\n3 × {n // 3} devices", key, fs=FS_S, lw=0.8)
        arrow(ax, (c, 4.05), (c, 3.93), color=C[key][1], ms=6)
        box(ax, c - 0.42, 3.35, 0.84, 0.58, f"{req}\n$s_d$ = {s}\n$L_d$ = {L} ms\n{keys}", key, fill=False,
            fs=FS_S, lw=0.9)
        for j in range(3):
            nx_ = c + (j - 1) * 0.28
            nodes.append(nx_)
            arrow(ax, (c + (j - 1) * 0.1, 3.35), (nx_, 3.06), color=C[key][1], lw=0.8, ms=6)
            box(ax, nx_ - 0.125, 2.82, 0.25, 0.24, f"E{3 * g + j + 1}", "edge", fs=FS_S, lw=0.8, r=0.03)
    for g in range(4):                                   # gateway links between the clusters of a domain
        for j in range(2):
            a, b = nodes[3 * g + j], nodes[3 * g + j + 1]
            ax.add_patch(FancyArrowPatch((a, 2.82), (b, 2.82), arrowstyle="-", connectionstyle="arc3,rad=0.6",
                                         color=INK2, lw=0.8, ls=(0, (2.5, 1.5)), shrinkA=0, shrinkB=0))
    for g in range(3):                                   # shared-service links across domains
        a, b = nodes[3 * g + 2], nodes[3 * g + 3]
        ax.add_patch(FancyArrowPatch((a, 2.82), (b, 2.82), arrowstyle="-", connectionstyle="arc3,rad=0.75",
                                     color="#8a8985", lw=1.2, ls=(0, (0.6, 1.6)), shrinkA=0, shrinkB=0))
    ly = 2.53
    ax.plot([bx0 + 0.12, bx0 + 0.36], [ly, ly], color=INK2, lw=0.8, ls=(0, (2.5, 1.5)))
    ax.text(bx0 + 0.41, ly, "gateway links within a domain", ha="left", va="center", fontsize=FS_S)
    ax.plot([bx0 + 2.0, bx0 + 2.24], [ly, ly], color="#8a8985", lw=1.2, ls=(0, (0.6, 1.6)))
    ax.text(bx0 + 2.29, ly, "cross-domain service links", ha="left", va="center", fontsize=FS_S)
    # (c) control loop ------------------------------------------------------------------------------------------
    pane(ax, 0.0, 0.0, W, 2.34, "(c) Control loop: evidence, federated learning, twin validation, enforcement")
    yl, hl, yu, hu = 0.48, 0.7, 1.46, 0.6
    xc, wc = 0.1, 1.06
    x1, x2, wm = 1.43, 3.39, 1.69
    xe, we = 5.35, 1.07
    tbox(ax, xc, yl, wc, yu + hu - yl, "Physical city", "1,500 devices,\n12 edge clusters;\ncontact graph $G$;\n"
         "attacks start\nand spread over\ncontacts", "iot", fill=True, top=0.25)
    tbox(ax, x1, yu, wm, hu, "Federated learning", "12 edge nodes train locally; raw\nflows stay at the edge; "
         "trust-\naware aggregation, Eq. (4)", "fl", fill=True)
    tbox(ax, x1, yl, wm, hl, "Evidence per device (every 10 s)", "$F_i$ threat probability (detector)\n"
         "$B_i$ behaviour, $H_i$ reputation\n$A_i$ authentication validity", "edge", fill=True)
    tbox(ax, x2, yu, wm, hu, "Digital twin", "copy $\\hat{G}$ of the graph, rate $\\hat{\\beta}$;\n"
         "validates isolating cluster $k$, Eq. (6)", "twin", fill=True)
    tbox(ax, x2, yl, wm, hl, "A-PQZTO policy engine", "trust score $T_i$, Eq. (1)\nslice-aware thresholds, Eq. (2)\n"
         "PQ re-authentication, Eq. (3)", "zt", fill=True)
    tbox(ax, xe, yl, we, yu + hu - yl, "Enforcement", "allow\nrestrict\nPQ re-authenticate\nquarantine\nblock\n"
         "isolate cluster $k$", "zt", fill=False, top=0.25)
    ym = yl + hl / 2
    arrow(ax, (xc + wc, yu + hu / 2), (x1, yu + hu / 2))
    arrow(ax, (xc + wc, ym), (x1, ym))
    arrow(ax, (x1 + wm, ym), (x2, ym))
    arrow(ax, (x2 + wm, ym), (xe, ym))
    arrow(ax, (x1 + wm / 2, yu), (x1 + wm / 2, yl + hl), color=C["fl"][1])
    ax.text(x1 + wm / 2 + 0.06, (yu + yl + hl) / 2, "global detector", ha="left", va="center", fontsize=FS_S,
            color=C["fl"][1], style="italic")
    arrow(ax, (x2 + 0.3, yl + hl), (x2 + 0.3, yu), color=C["twin"][1])
    ax.text(x2 + 0.36, (yu + yl + hl) / 2, "isolate $k$?", ha="left", va="center", fontsize=FS_S, color=C["twin"][1],
            style="italic")
    arrow(ax, (x2 + 1.12, yu), (x2 + 1.12, yl + hl), color=C["twin"][1])
    ax.text(x2 + 1.18, (yu + yl + hl) / 2, "validated", ha="left", va="center", fontsize=FS_S, color=C["twin"][1],
            style="italic")
    polyarrow(ax, [(xe + we / 2, yl), (xe + we / 2, 0.29), (xc + wc / 2, 0.29), (xc + wc / 2, yl)],
              color=C["zt"][1], lw=1.0)
    ax.text(W / 2, 0.17, "decisions act on devices and clusters; reputation, twin state and edge trust are updated",
            ha="center", va="center", fontsize=FS_S, color=C["zt"][1], style="italic")
    save(fig, "fig2_system_model")


# ------------------------------------------------------------------------------------------------------ Fig. 3
def _info(ax, x, y, w, lines, h=None):
    h = h or (len(lines) * FS_S * LH + 0.1)
    box(ax, x, y, w, h, "", "iot", fill=True, lw=0.7)
    ax.text(x + 0.07, y + h - 0.05, "\n".join(lines), ha="left", va="top", fontsize=FS_S, linespacing=1.2)
    return h


def fig3_threat_model():
    W, H = 6.5, 4.9
    fig, ax = canvas(W, H)
    pw, ph = 3.2, 2.4
    P = {"a": (0.0, 2.5), "b": (3.3, 2.5), "c": (0.0, 0.0), "d": (3.3, 0.0)}
    red = C["thr"][1]
    # (a) network attacks ----------------------------------------------------------------------------------------
    x0, y0 = P["a"]
    pane(ax, x0, y0, pw, ph, "(a) Network attacks")
    for k, yy in enumerate((y0 + 1.72, y0 + 1.12)):
        for i in range(3):
            for j in range(2):
                ax.add_patch(Rectangle((x0 + 0.14 + 0.13 * i, yy + 0.13 * j), 0.09, 0.09, fc=C["thr"][0], ec=red,
                                       lw=0.7))
        box(ax, x0 + 1.42, yy - 0.04, 0.55, 0.34, "edge\nnode", "edge", fs=FS_S, lw=0.8)
        for dy in (0.02, 0.12, 0.22):
            arrow(ax, (x0 + 0.56, yy + dy), (x0 + 1.42, yy + dy + (0.13 - dy) * 0.4), color=red, lw=1.0, ms=6)
        arrow(ax, (x0 + 1.97, yy + 0.13), (x0 + 2.3, y0 + 1.53 + (0.12 if k == 0 else -0.12)), color=INK2, ls="--",
              lw=0.8, ms=6)
    ax.text(x0 + 0.99, y0 + 1.62, "DDoS / DoS\nfloods", ha="center", va="center", fontsize=FS_S, color=red,
            style="italic")
    ax.text(x0 + 0.12, y0 + 0.97, "compromised devices", ha="left", va="top", fontsize=FS_S, color=red)
    box(ax, x0 + 2.3, y0 + 1.22, 0.8, 0.62, "6G slice:\nlinks and\ncapacity", "iot", fs=FS_S, lw=0.8)
    _info(ax, x0 + 0.08, y0 + 0.07, pw - 0.16, ["Evaluated: flooding by 30 devices in 2 edge clusters",
                                               "Target: links, edge nodes, slices; also scanning",
                                               "Response: trust reduction, rate limiting, quarantine"])
    # (b) IoT compromise -----------------------------------------------------------------------------------------
    x0, y0 = P["b"]
    pane(ax, x0, y0, pw, ph, "(b) IoT compromise")
    n, cx, cy, rr = 12, x0 + 0.72, y0 + 1.5, 0.4
    pos = {i: (cx + rr * np.cos(2 * np.pi * i / n + 0.3), cy + 0.8 * rr * np.sin(2 * np.pi * i / n + 0.3))
           for i in range(n)}
    E = [(i, (i + 1) % n) for i in range(n)] + [(i, (i + 2) % n) for i in range(0, n, 2)] + [(0, 6), (3, 8), (5, 10)]
    seeds, new = {0, 1, 6}, {2, 11, 7}
    for a, b in E:
        if (a in seeds and b in new) or (b in seeds and a in new):
            s, t = (a, b) if a in seeds else (b, a)
            arrow(ax, pos[s], pos[t], color=red, lw=1.0, ms=6)
        else:
            ax.plot(*zip(pos[a], pos[b]), color="#b8b6b0", lw=0.6, zorder=2)
    for i, p in pos.items():
        fc = red if i in seeds else (C["thr"][0] if i in new else "white")
        ax.add_patch(plt.Circle(p, 0.055, fc=fc, ec=red if (i in seeds or i in new) else INK2, lw=0.7, zorder=4))
    ax.text(cx, y0 + 0.98, "worm: 3 seeds (filled) in one\ncluster infect their contacts\n"
            "($\\beta$ = 0.03 per contact and step)", ha="center", va="top", fontsize=FS_S, linespacing=1.15)
    box(ax, x0 + 1.55, y0 + 1.5, 1.57, 0.5, "", "thr", fill=False, lw=0.8)
    ax.text(x0 + 1.62, y0 + 1.95, "False data injection", ha="left", va="top", fontsize=FS, fontweight="bold")
    ax.text(x0 + 1.62, y0 + 1.95 - FS * LH - 0.01, "15 energy devices send\nforged measurements", ha="left", va="top",
            fontsize=FS_S, linespacing=1.15)
    box(ax, x0 + 1.55, y0 + 0.86, 1.57, 0.57, "", "thr", fill=False, lw=0.8)
    ax.text(x0 + 1.62, y0 + 1.38, "Credential misuse", ha="left", va="top", fontsize=FS, fontweight="bold")
    ax.text(x0 + 1.62, y0 + 1.38 - FS * LH - 0.01, "8 compromised devices with\nvalid credentials, active in\n"
            "15% of the steps", ha="left", va="top", fontsize=FS_S, linespacing=1.15)
    _info(ax, x0 + 0.08, y0 + 0.07, pw - 0.16, ["Target: sensors, gateways, actuators",
                                               "Response: behavioural and federated evidence,",
                                               "quarantine, twin-validated cluster isolation"])
    # (c) FL poisoning ---------------------------------------------------------------------------------------------
    x0, y0 = P["c"]
    pane(ax, x0, y0, pw, ph, "(c) Poisoning of federated learning")
    box(ax, x0 + 0.45, y0 + 1.76, 2.3, 0.3, "Aggregator: FedAvg or trust-aware, Eq. (4)", "fl", fs=FS_S, lw=0.8)
    mal = {3, 8}
    for i in range(12):
        xx = x0 + 0.17 + 0.24 * i
        m = i in mal
        box(ax, xx, y0 + 1.1, 0.2, 0.22, str(i + 1), "thr" if m else "edge", fs=FS_S, lw=0.8, r=0.03,
            fill=True)
        ax.plot([xx + 0.1, x0 + 1.6 + (i - 5.5) * 0.12], [y0 + 1.32, y0 + 1.76], color=red if m else "#9fb9d9",
                lw=1.0 if m else 0.6, zorder=1)
    ax.text(x0 + 1.6, y0 + 1.03, "malicious edge clients (1, 2 or 3 of 12):", ha="center", va="top", fontsize=FS_S,
            color=red)
    ax.text(x0 + 0.17, y0 + 1.03 - FS_S * LH - 0.01, "label flipping: attack flows relabelled benign\n"
            "model poisoning: update multiplied by $-4$", ha="left", va="top", fontsize=FS_S, linespacing=1.2)
    _info(ax, x0 + 0.08, y0 + 0.07, pw - 0.16, ["Target: local updates and the global detector",
                                               "Response: median reference, norm clipping,",
                                               "reliability weighting $r_k$ of each client"])
    # (d) identity and post-quantum threats -------------------------------------------------------------------------
    x0, y0 = P["d"]
    pane(ax, x0, y0, pw, ph, "(d) Identity and post-quantum threats")
    yi, hi = y0 + 1.4, 0.6
    ax.text(x0 + 0.1, yi + hi + 0.03, "impostor: 12 entities in all slices", ha="left", va="bottom", fontsize=FS_S,
            style="italic", color=INK2)
    box(ax, x0 + 0.08, yi, 0.98, hi, "impostor with a\nforged or stolen\nclassical credential", "thr", fs=FS_S, lw=0.8)
    box(ax, x0 + 1.2, yi, 0.84, hi, "classical\nverification:\npasses", "iot", fill=False, fs=FS_S, lw=0.8)
    box(ax, x0 + 2.18, yi, 0.94, hi, "ML-DSA check\n(PQ re-auth.):\nfails, blocked*", "pqc", fs=FS_S, lw=0.8)
    arrow(ax, (x0 + 1.06, yi + hi / 2), (x0 + 1.2, yi + hi / 2), color=red, ms=6)
    arrow(ax, (x0 + 2.04, yi + hi / 2), (x0 + 2.18, yi + hi / 2), color=red, ms=6)
    yh, hh = y0 + 0.74, 0.5
    box(ax, x0 + 0.08, yh, 0.98, hh, "today: record\nclassical sessions", "thr", fs=FS_S, lw=0.8)
    box(ax, x0 + 1.2, yh, 0.84, hh, "later: quantum\ncomputer breaks\nX25519 / ECDH", "iot", fill=False, fs=FS_S,
        lw=0.8)
    box(ax, x0 + 2.18, yh, 0.94, hh, "recorded traffic\nis decrypted", "thr", fill=False, fs=FS_S, lw=0.8)
    arrow(ax, (x0 + 1.06, yh + hh / 2), (x0 + 1.2, yh + hh / 2), color=red, ms=6)
    arrow(ax, (x0 + 2.04, yh + hh / 2), (x0 + 2.18, yh + hh / 2), color=red, ms=6)
    ax.text(x0 + 0.1, yh + hh + 0.03, "harvest-now-decrypt-later", ha="left", va="bottom", fontsize=FS_S,
            style="italic", color=INK2)
    _info(ax, x0 + 0.08, y0 + 0.07, pw - 0.16, ["Response: PQ re-authentication; hybrid X25519 +",
                                               "ML-KEM-768 sessions in energy, health, safety",
                                               "* stated assumption: forged credentials fail ML-DSA"])
    save(fig, "fig3_threat_model")


# ------------------------------------------------------------------------------------------------------ Fig. 4
def fig4_trust_workflow():
    W, H = 6.5, 4.05
    fig, ax = canvas(W, H)
    ax.text(0.02, 4.0, "(a) Evidence for device $i$", ha="left", va="top", fontsize=FS_P, fontweight="bold")
    ins = [("$B_i$", "behavioural consistency", "edge traffic profile", "edge"),
           ("$H_i$", "reputation", "slow memory at the edge", "edge"),
           ("$A_i$", "authentication validity", "PQ 1 / classical 0.85 / failed 0", "pqc"),
           ("$F_i$", "federated threat probability", "global detector", "fl")]
    xt0, xt1, yt0, yt1 = 2.18, 4.52, 2.86, 3.72          # trust box
    for j, (sym, nm, src, key) in enumerate(ins):
        y = 3.12 - 0.72 * j
        box(ax, 0.02, y, 1.92, 0.6, "", key, fill=False)
        ax.text(0.1, y + 0.3, sym, fontsize=11, va="center")
        ax.text(0.47, y + 0.4, nm, fontsize=FS, va="center")
        ax.text(0.47, y + 0.18, src, fontsize=FS_S, va="center", color=INK2, style="italic")
        ax.plot([1.94, 2.06], [y + 0.3, y + 0.3], color=INK2, lw=0.8)
    ax.plot([2.06, 2.06], [3.12 - 0.72 * 3 + 0.3, 3.42], color=INK2, lw=0.8)
    arrow(ax, (2.06, (yt0 + yt1) / 2), (xt0, (yt0 + yt1) / 2), lw=0.8, ms=7)
    ax.text((xt0 + xt1) / 2, 4.0, "(b) Trust score and thresholds", ha="center", va="top", fontsize=FS_P,
            fontweight="bold")
    box(ax, xt0, yt0, xt1 - xt0, yt1 - yt0, "$T_i=\\min\\{\\mathrm{clip}_{[0,1]}(0.35B_i+0.25H_i+0.40A_i$\n"
        "$-\\,0.60F_i),\\;1-F_i\\}$   (1)\npositive evidence adds trust, threat evidence\n"
        "removes it; no credential lifts trust above $1-F_i$", "zt", fill=False, fs=FS_S)
    # threshold bar: discrete regions with base thresholds tau_a
    x0, x1, yb, hb = 2.12, 4.58, 2.06, 0.34
    arrow(ax, ((xt0 + xt1) / 2, yt0), ((xt0 + xt1) / 2, yb + hb + 0.2), lw=0.9)
    regs = [(0.0, 0.20, "block", "#e9a184"), (0.20, 0.40, "quaran-\ntine", "#f3c98a"),
            (0.40, 0.55, "rate\nlimit", "#f6ec9e"), (0.55, 0.75, "allow +\nPQ re-auth.", "#bfe0f3"),
            (0.75, 1.0, "allow", "#8fc3e6")]
    for a, b, lab, col in regs:
        xa, xb = x0 + (x1 - x0) * a, x0 + (x1 - x0) * b
        ax.add_patch(Rectangle((xa, yb), xb - xa, hb, fc=col, ec="white", lw=0.8))
        ax.text((xa + xb) / 2, yb + hb / 2, lab, ha="center", va="center", fontsize=FS_S, linespacing=1.0)
    for v in (0.20, 0.40, 0.55, 0.75):
        xx = x0 + (x1 - x0) * v
        ax.plot([xx, xx], [yb + hb, yb + hb + 0.05], color=INK, lw=0.8)
        ax.text(xx, yb + hb + 0.07, f"{v:.2f}", fontsize=FS_S, ha="center", va="bottom")
    ax.text(x0 + 0.1, yb + hb + 0.115, "$\\tau_a$:", fontsize=FS_S, ha="left", va="center")
    ax.text(x0, yb - 0.04, "0", fontsize=FS_S, ha="center", va="top", color=INK2)
    ax.text(x1, yb - 0.04, "1", fontsize=FS_S, ha="center", va="top", color=INK2)
    ax.text((x0 + x1) / 2, yb - 0.06, "trust $T_i$", fontsize=FS_S, ha="center", va="top", color=INK2)
    ax.text((x0 + x1) / 2, 1.5, "$\\tau_{a,d}=\\tau_a+\\theta+0.1\\,(s_d-0.8)$   (2)\nstricter thresholds in more "
            "sensitive slices;\n$\\theta$ sets the operating point (validation)", fontsize=FS_S, ha="center",
            va="center", linespacing=1.25)
    ax.text(5.62, 4.0, "(c) Actions", ha="center", va="top", fontsize=FS_P, fontweight="bold")
    acts = [("allow", "$T_i\\geq\\tau_{restrict,d}$", "zt"),
            ("PQ re-authenticate", "$T_i<\\tau_{allow,d}$, $\\neg V_i$, $Q\\kappa\\leq L_d$  (3)", "pqc"),
            ("restrict (rate limit)", "$T_i<\\tau_{restrict,d}$", "zt"),
            ("quarantine (review)", "$T_i<\\tau_{quar,d}$", "zt"),
            ("block", "$T_i<\\tau_{block,d}$ or $A_i=0$", "zt"),
            ("isolate edge cluster", "twin roll-outs, Eq. (6)", "twin")]
    xa0, wa = 4.78, 1.7
    for j, (a, cnd, key) in enumerate(acts):
        y = 3.27 - 0.58 * j
        box(ax, xa0, y, wa, 0.5, "", key, fill=False)
        ax.text(xa0 + 0.08, y + 0.35, a, fontsize=FS, va="center", fontweight="bold")
        ax.text(xa0 + 0.08, y + 0.14, cnd, fontsize=FS_S, va="center", color=INK2)
    arrow(ax, (x1, yb + hb / 2), (xa0, yb + hb / 2), lw=0.9)
    # (d) feedback
    yf0, yf1 = 0.12, 0.84
    box(ax, xt0, yf0, xt1 - xt0, yf1 - yf0, "", "edge", fill=False)
    ax.text((xt0 + xt1) / 2, yf1 - 0.06, "(d) Feedback after enforcement", ha="center", va="top", fontsize=FS_H,
            fontweight="bold")
    ax.text((xt0 + xt1) / 2, yf1 - 0.06 - FS_H * LH - 0.02, "reputation $H_i$ and twin belief are updated;\n"
            "a failed PQ verification sets $A_i=0$; quarantined\nbenign devices return after operator review",
            ha="center", va="top", fontsize=FS_S, linespacing=1.2)
    polyarrow(ax, [(xa0 + wa / 2, 0.37), (xa0 + wa / 2, 0.24), (xt1, 0.24)])
    polyarrow(ax, [(xt0, 0.44), (0.98, 0.44), (0.98, 0.96)])
    save(fig, "fig4_trust_workflow")


# ------------------------------------------------------------------------------------------------------ Fig. 5
def fig5_twin(seed=1):
    import sys
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from apq.city import City
    c = City(seed)
    k = 4
    ii = np.flatnonzero(c.edge == k)
    G = nx.Graph()
    sub = c.Ahat[ii][:, ii].tocoo()                  # the twin's own (imperfect) copy of the contact graph
    G.add_nodes_from(range(len(ii)))
    G.add_edges_from(zip(sub.row, sub.col))
    rng = np.random.default_rng(3)
    pos = nx.spring_layout(G, seed=2, k=0.18)
    belief = np.zeros(len(ii)); hot = rng.choice(len(ii), 4, replace=False); belief[hot] = [0.95, 0.8, 0.6, 0.35]
    W, H = 6.5, 3.05
    fig = plt.figure(figsize=(W, H))
    ax = fig.add_axes([0.0, 0.13, 0.42, 0.74])
    cm = plt.get_cmap("OrRd")
    nx.draw_networkx_edges(G, pos, ax=ax, width=0.35, edge_color="#b8b6b0")
    col = [cm(0.15 + 0.85 * b) for b in belief]
    nx.draw_networkx_nodes(G, pos, ax=ax, node_size=[60 if b > 0 else 9 for b in belief], node_color=col,
                           edgecolors=[INK if b > 0 else "none" for b in belief], linewidths=0.5)
    ax.axis("off")
    fig.text(0.21, 0.985, f"(a) Edge cluster {k + 1} in the twin graph $\\hat{{G}}$ ({len(ii)} devices)\n"
             "with an example belief of suspected devices", ha="center", va="top", fontsize=FS_H)
    cax = fig.add_axes([0.08, 0.075, 0.26, 0.035])
    cb = fig.colorbar(plt.cm.ScalarMappable(cmap=matplotlib.colors.ListedColormap(cm(np.linspace(0.15, 1, 256)))),
                      cax=cax, orientation="horizontal")
    cb.set_ticks([0, 0.5, 1]); cb.ax.tick_params(labelsize=FS_S, length=2, width=0.5); cb.outline.set_linewidth(0.5)
    cb.set_label("belief $b_j=F_j(1-H_j)$", fontsize=FS_S, labelpad=1)
    ax = fig.add_axes([0.44, 0.0, 0.56, 1.0]); ax.set_xlim(0, 0.56 * W); ax.set_ylim(0, H); ax.axis("off")
    bw = 0.56 * W
    ax.text(bw / 2, H - 0.045, "(b) Validation of a cluster isolation before enforcement", ha="center", va="top",
            fontsize=FS_H)
    steps = [("twin", "Pre-filter: belief $b_j=F_j(1-H_j)$ for suspected devices $j$\n"
                      "in cluster $k$; skip $k$ if $\\Sigma_{j\\in k}\\,b_j<0.5$"),
             ("twin", "Sample initial infections inside $k$ from $b_j$ ($M$ = 8 samples)"),
             ("twin", "Roll out $h$ = 12 steps (2 min) on $\\hat{G}$ with $\\hat{\\beta}$, without and\n"
                      "with isolation of $k$ (common random numbers)"),
             ("twin", "Expected infections that escape $k$: $\\bar{I}_{out}$(no isolation)\n"
                      "and $\\bar{I}_{out}$(isolation)"),
             ("zt", "Isolate $k$ if $\\bar{I}_{out}$(no isolation) $-$ $\\bar{I}_{out}$(isolation) "
                    "$\\geq g_{min}=1$   (6)\nthe isolation lasts 30 steps (5 min), then $k$ is re-evaluated")]
    hs = [0.46, 0.34, 0.46, 0.44, 0.48]
    y = H - 0.36
    for j, ((key, t), h) in enumerate(zip(steps, hs)):
        box(ax, 0.04, y - h, bw - 0.08, h, t, key, fill=False, fs=FS_S)
        y -= h
        if j < 4:
            arrow(ax, (bw / 2, y), (bw / 2, y - 0.12), ms=7)
            y -= 0.12
    save(fig, "fig5_twin_validation")


if __name__ == "__main__":
    fig1_architecture(); fig2_system_model(); fig3_threat_model(); fig4_trust_workflow(); fig5_twin()
    print("ok")
