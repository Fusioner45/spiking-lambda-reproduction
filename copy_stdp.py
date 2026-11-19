# -*- coding: utf-8 -*-
"""Mini-lab, palier 5 : copie de token par theta-cycle STDP (§2.8).

Mecanisme : projection plastique diagonale SRC[k] -> DST[k], poids initial
W_0 = 3.5 (sous-seuil : 3.5 x epsilon(10,2) = 0.48 < 1), STDP LTP-only
(A+ = 1.2, A- = 0, tau_pre = tau_post = 12 ms, w_max = 8).

  - Apprentissage (6 cycles thêta de 12 ms) : les SRC actifs firent a
    offset fixe de chaque cycle ; courant tonique I_theta sur TOUS les
    DST. DST actif fire APRES son SRC -> LTP, W -> w_max. DST inactif :
    tonique seul < 1 -> silence, W inchange.
  - Rappel (sans tonique) : SRC actif -> EPSP 8x0.137 = 1.10 > 1 : DST
    fire. SRC inactif (W_0) : 0.48 < 1 : silence. Le pattern est
    reconstruit a l'identique.

FENETRE DE SELECTIVITE (notre contribution de calibrage) : par
superposition lineaire exacte, le pic de V en apprentissage vaut
V_tonic + EPSP(W_0). Conditions :
    1 - W_0 eps < I_theta < 1        soit ici (0.52, 1.0)
Le papier annonce I_theta = 0.5 et « V ≈ 0.25 » : les deux sont hors
fenêtre / incoherents avec leur propre eq. (2) (V_ss = E_L + I = I) ->
0.48 + 0.5 = 0.98 < 1 : leur LTP ne partirait pas tel que publie
(question ouverte n°6, testee empiriquement ci-dessous). Nous prenons
I_theta = 0.75, au centre de la fenêtre.

Discipline des traces (§2.3.3) : evenement pre incremente AVANT la mise
a jour de poids du post du meme pas (pre-avant-post => LTP plein meme a
delta t = 0) ; A- = 0 rend le cas limite LTD sans objet.
"""

import random

import snn_engine as se

DT = 0.1
TAU_PRE = TAU_POST = 12.0
A_PLUS = 1.2
W0 = 3.5
W_MAX = 8.0
N_CYCLES = 6
CYCLE_MS = 12.0
SRC_OFFSET_MS = 2.0        # fire des SRC dans le cycle
DELAY_MS = 0.5             # SRC -> DST


class CopyBench:
    """N paires plastiques SRC[k] -> DST[k] + tonique thêta."""

    def __init__(self, n=64, i_theta=0.75, seed=0, dt=DT):
        self.n = n
        self.dt = dt
        self.i_theta = i_theta
        self.eps = se.measure_epsilon(10.0, 2.0, dt)
        self.w = [W0] * n
        self.g = [0.0] * n
        self.trace_pre = [0.0] * n
        self.trace_post = [0.0] * n
        self.k_tr = se.MathExp(dt / TAU_PRE) if hasattr(se, "MathExp") \
            else None
        import math
        self.k_tr = math.exp(-dt / TAU_PRE)
        self.k_syn = math.exp(-dt / 2.0)          # tau_syn = 2 ms
        self.dst = [se.Neuron(tau_m=10.0, t_ref=2.0, dt=dt) for _ in range(n)]
        # evenements pre (pas -> liste de k)
        self.pre_events = {}
        self.arrivals = {}
        self.k_step = 0
        self.rng = random.Random(seed)

    def schedule_src(self, k, t_ms):
        """Programme un spike SRC a t_ms a partir de MAINTENANT (horloge
        relative au pas courant — indispensable apres learn())."""
        step = self.k_step + int(round(t_ms / self.dt))
        self.pre_events.setdefault(step, []).append(k)

    # ---- un pas ----
    def step(self, tonic_on):
        n = self.n
        for k in range(n):
            self.g[k] *= self.k_syn
            self.trace_pre[k] *= self.k_tr
            self.trace_post[k] *= self.k_tr
        for k in self.arrivals.pop(self.k_step, []):
            self.g[k] += self.w[k]
        pre_k = self.pre_events.pop(self.k_step, [])
        for k in pre_k:
            self.arrivals.setdefault(self.k_step + int(round(DELAY_MS / self.dt)),
                                     []).append(k)
        spiked = []
        for k in range(n):
            i = self.g[k] + (self.i_theta if tonic_on else 0.0)
            if self.dst[k].step(i):
                spiked.append(k)
        # mise a jour des poids : au spike post, avec la trace pre
        # courante (incluant un pre du meme pas) ; trace post APRES.
        for k in spiked:
            self.w[k] = min(self.w[k] + A_PLUS * self.trace_pre[k], W_MAX)
            self.trace_post[k] = 1.0
        # increment des traces pre APRES les mises a jour de poids
        for k in pre_k:
            self.trace_pre[k] = 1.0
        self.k_step += 1
        return spiked

    # ---- phases ----
    def learn(self, pattern, n_cycles=N_CYCLES):
        # schedule_src est RELATIF au pas courant : au debut de chaque
        # cycle, +SRC_OFFSET_MS suffit (ne pas repasser t0 absolu,
        # sinon double decalage).
        for _c in range(n_cycles):
            for k in pattern:
                self.schedule_src(k, SRC_OFFSET_MS)
            for _ in range(int(CYCLE_MS / self.dt)):
                self.step(tonic_on=True)

    def recall(self, pattern, duration_ms=30.0):
        fired = {k: [] for k in range(self.n)}
        for k in pattern:
            self.schedule_src(k, 1.0)
        for _ in range(int(duration_ms / self.dt)):
            for k in self.step(tonic_on=False):
                fired[k].append(self.k_step * self.dt)
        return fired

    def v_peak_tonic_only(self, duration_ms=60.0):
        vmax = 0.0
        for _ in range(int(duration_ms / self.dt)):
            self.step(tonic_on=True)
            vmax = max(vmax, max(d.v for d in self.dst))
        return vmax
