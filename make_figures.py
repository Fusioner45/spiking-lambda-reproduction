# -*- coding: utf-8 -*-
"""Genere les figures du README (rasters de spikes, trace INTG, onde du
ring) a partir des circuits reels. Sortie : assets/*.png."""
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

import lambda_beta as lb
import bridge_db as bd
import det_redex as dr
import intg_body as ig
import ring_phase as rp
import balance_digits as bdc

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
os.makedirs(OUT, exist_ok=True)

C_APP, C_LAM, C_DET, C_INH = "#e07b39", "#7b5cc4", "#c23333", "#666666"


def fig_det():
    """Fig 1 : detection du redex sur 2 I — coïncidence + latch WTA."""
    two = "(\\f. \\x. f (f x)) (\\x. x)"
    toks = bd.to_tokens(bd.to_debruijn(lb.parse(two)))
    c = dr.DetCircuit(toks)
    n_steps = int((len(toks) * 8.0 + 40.0) / 0.1)
    ev = []
    for j, (tid, _d) in enumerate(toks):
        t0 = 8.0 * j
        if tid == bd.APP:
            ev.append((t0, 0, C_APP))
        elif tid == bd.LAM:
            ev.append((t0, 1, C_LAM))
    for tms, idx in c.net.bulk_run(n_steps):
        if idx == c.det:
            ev.append((tms, 2, C_DET))
        elif idx == c.inh:
            ev.append((tms, 3, C_INH))
    fig, ax = plt.subplots(figsize=(10, 2.6))
    for t, row, col in ev:
        ax.axvline(t, ymin=(row + 0.12) / 4, ymax=(row + 0.88) / 4,
                   color=col, lw=1.6 if row < 2 else 1.2)
    ax.set_yticks([0.5, 1.5, 2.5, 3.5])
    ax.set_yticklabels(["APP", "LAM", "DET", "INH"])
    ax.set_xlabel("time (ms)")
    ax.set_title("Redex detection on 2 I: single coincidence at 9.1 ms, "
                 "WTA latch afterwards", fontsize=10)
    ax.spines[["top", "right", "left"]].set_visible(False)
    ax.grid(axis="x", ls=":", lw=0.4, alpha=0.5)
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "fig_det.png"), dpi=150)
    plt.close(fig)


def fig_intg():
    """Fig 2 : compteur de balance sur plus 2 3 — V(INTG) + decharge."""
    plus = "(\\m. \\n. \\f. \\x. m f (n f x)) (\\a. \\b. a (a b)) " \
           "(\\a. \\b. a (a (a b)))"
    t = lb.parse(plus)
    toks = bd.to_tokens(bd.to_debruijn(t))
    k = bd.find_redex(t)
    truth = ig.body_end_pos(toks, k)
    c = ig.IntgCircuit(toks, k)
    n_steps = int(((len(toks) - c.k - 2) * 8.0 + 40.0) / 0.1)
    vs, fires = [], []
    for _ in range(n_steps):
        spiked = [i for i in c.net.step()]
        vs.append(c.net.neurons[c.intg].v)
        if c.intg in spiked:
            fires.append(c.net.k_step * 0.1)
    fig, ax = plt.subplots(figsize=(10, 3.0))
    ax.plot([i * 0.1 for i in range(len(vs))], vs, lw=1.0, color="#1a4480")
    ax.axhline(1.0, color="#c23333", ls="--", lw=0.8)
    for f in fires:
        ax.axvline(f, color="#c23333", lw=0.8, alpha=0.6)
    ax.set_xlabel("time (ms)")
    ax.set_ylabel("V(INTG)")
    ax.set_title("Balance counter on plus 2 3: discharge at every subterm "
                 "boundary", fontsize=10)
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="y", ls=":", lw=0.4, alpha=0.5)
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "fig_intg.png"), dpi=150)
    plt.close(fig)


def fig_ring():
    """Fig 3 : onde tournante sur l'anneau de phase (K_F = 8)."""
    ring = rp.PhaseRing()
    fires, times, _isi = ring.run(0, 26)
    fig, ax = plt.subplots(figsize=(10, 2.6))
    ax.scatter(times, fires, s=18, color="#1a4480")
    ax.set_yticks(range(8))
    ax.set_xlabel("time (ms)")
    ax.set_ylabel("FINE[k]")
    ax.set_title("Phase ring: traveling wave, ISI ~4.9 ms for a 4 ms "
                 "axonal delay", fontsize=10)
    ax.invert_yaxis()
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="x", ls=":", lw=0.4, alpha=0.5)
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "fig_ring.png"), dpi=150)
    plt.close(fig)


def fig_balance():
    """Fig 4 : finding 8 et son fix — le compteur analogique derive
    (V croise le seuil 2 slots avant la vraie balance) ; le compteur
    positionnel decharge exactement (les chiffres base 8)."""
    import intg_body as ig_mod
    n_x = 20
    wide = "(\\x. " + " ".join(["x"] * n_x) + ")"
    toks = bd.to_tokens(bd.to_debruijn(lb.parse(wide)))
    K = bd.find_redex(lb.parse(wide))
    truth = ig_mod.body_end_pos(toks, K)          # 38 (0-based) = slot 39
    sigma = ig_mod.sigma_sequence(toks, K)
    slot = 8.0

    # (a) le V mesure du compteur analogique (tau_m = 1000), echantillonne
    #     au bord de chaque slot — DEUX circuits : les pulses sont
    #     injectes au constructeur, le reseau est a usage unique
    c = ig_mod.IntgCircuit(toks, K, tau_m=1000.0)
    n_slots = len(sigma)
    n_steps = int((n_slots * slot + 40.0) / c.dt)
    vs = []
    prev_slot = 0
    for _ in range(n_steps):
        c.net.step()
        t = c.net.k_step * c.dt
        s = int(t // slot)
        if s != prev_slot:
            if len(vs) >= n_slots:
                break
            vs.append(c.net.neurons[c.intg].v)
            prev_slot = s
    r_pos = int(ig_mod.IntgCircuit(toks, K, tau_m=1000.0).run()["pos"])

    # (b) les chiffres du compteur positionnel (la spec, exacte)
    r = bdc.run_counter(toks, K)

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 5.2), sharex=True)
    slots = list(range(1, n_slots + 1))
    ax1.plot(slots, sigma, lw=1.2, color="#1a4480", label="true balance")
    ax1.plot(slots, vs, lw=1.2, color="#e07b39", label="analog V (tau_m=1000)")
    ax1.axhline(1.0, color="#c23333", ls="--", lw=0.8, label="threshold")
    ax1.axvline(truth + 1, color="#1a4480", ls=":", lw=1.0)
    ax1.axvline(r_pos + 1, color="#c23333", lw=1.0, alpha=0.7)
    ax1.set_ylim(-20, 4)
    ax1.annotate("analog fires here\n(2 slots early)", xy=(r_pos + 1, 1.0),
                 xytext=(20, -3.5), fontsize=8, color="#c23333",
                 arrowprops=dict(arrowstyle="->", color="#c23333", lw=0.8))
    ax1.annotate("truth", xy=(truth + 1, 1.0), xytext=(29, -7.5),
                 fontsize=8, color="#1a4480",
                 arrowprops=dict(arrowstyle="->", color="#1a4480", lw=0.8))
    ax1.set_ylabel("balance / V")
    ax1.legend(fontsize=8, loc="lower left")
    ax1.set_title("Finding 8 on the x^20 body (39 tokens): the analog "
                  "counter crosses the threshold 2 slots early",
                  fontsize=10)
    ax1.spines[["top", "right"]].set_visible(False)
    ax1.grid(axis="y", ls=":", lw=0.4, alpha=0.5)

    digs = list(zip(*[e["digits"] for e in r["trace"]]))
    for i, (col, lab) in enumerate([("#e07b39", "d0 (fine)"),
                                    ("#7b5cc4", "d1"),
                                    ("#1a4480", "d2")]):
        ax2.plot(slots, digs[i], drawstyle="steps-post", lw=1.4,
                 color=col, label=lab)
    ax2.axvline(truth + 1, color="#1a4480", ls=":", lw=1.0)
    ax2.annotate("discharge: digits (1, 0, 0)", xy=(truth + 1, 1),
                 xytext=(truth - 14, 3.2), fontsize=8,
                 arrowprops=dict(arrowstyle="->", color="#444444", lw=0.8))
    ax2.set_yticks(range(8))
    ax2.set_xlabel("body token (slot)")
    ax2.set_ylabel("digit")
    ax2.legend(fontsize=8, loc="lower right")
    ax2.set_title("The positional counter holds the same balance in "
                  "base-8 digits: exact discharge at the truth",
                  fontsize=10)
    ax2.spines[["top", "right"]].set_visible(False)
    ax2.grid(axis="y", ls=":", lw=0.4, alpha=0.5)
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "fig_balance.png"), dpi=150)
    plt.close(fig)


def fig_multiplex():
    """Fig 5 : les gains du multiplexage (m4) — cycles theta simules,
    les deux modes a poids finaux bit-exacts."""
    from run_multiplex import build_case
    N_LIST = (1, 2, 4, 8)
    K_NUM_LIST = (1, 4, 8)                    # l_arg = 2k + 3
    fig, ax = plt.subplots(figsize=(10, 3.4))
    width = 0.26
    xs = range(len(K_NUM_LIST))
    l_args = []
    for gi, n_bound in enumerate(N_LIST):
        gains, l_args = [], []
        for k_num in K_NUM_LIST:
            case = build_case(n_bound, k_num)
            l_args.append(case["l_arg"])
            seq = case["n_slots"] * 6
            mux = (case["n_direct"] + case["l_arg"]) * 6
            gains.append(seq / mux)
        ax.bar([x + (gi - 1.5) * width for x in xs], gains, width,
               label="n_bound = %d" % n_bound,
               color=["#e07b39", "#7b5cc4", "#1a4480", "#2a7a3b"][gi])
        for x, g in zip(xs, gains):
            ax.text(x + (gi - 1.5) * width, g + 0.08, "%.1f" % g,
                    ha="center", fontsize=7)
    ax.set_xticks(list(xs))
    ax.set_xticklabels(["l_arg = %d" % l for l in l_args])
    ax.axhline(1.0, color="#666666", ls=":", lw=0.8)
    ax.set_ylabel("theta-cycle speedup (sequential / multiplexed)")
    ax.set_title("Multiplexed argument write: up to 6.1x fewer theta "
                 "cycles at bit-exact final weights (m4)", fontsize=10)
    ax.legend(fontsize=8, ncol=4, loc="upper left")
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="y", ls=":", lw=0.4, alpha=0.5)
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "fig_multiplex.png"), dpi=150)
    plt.close(fig)


if __name__ == "__main__":
    fig_det()
    fig_intg()
    fig_ring()
    fig_balance()
    fig_multiplex()
    print("figures :", sorted(os.listdir(OUT)))
