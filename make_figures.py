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


if __name__ == "__main__":
    fig_det()
    fig_intg()
    fig_ring()
    print("figures :", os.listdir(OUT))
