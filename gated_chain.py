# -*- coding: utf-8 -*-
"""GATE_BOUND neural (item 3, sessions C-D) : la chaine d'emission avec
PROJECTIONS ROUTEES REELLES et GATES LIF §2.9 par tap.

Ce qui change par rapport a la chaine m1 (cube_multiplex.run_chain) :
la - chaque tap recoit TOUTES les fenetres de la chaine (le bus est
diffuse a tous) par une PROJECTION ROUTEE : la table de routage
(canal -> bit d'arrivee, par fenetre) est posee a la creation du tap
depuis les patterns composes du ring — c'est du CABLAGE, pas des
evenements re-programmes ;
la - l'apprentissage est selectionne par une GATE LIF reelle (§2.9 :
courant d'armement pendant SA fenetre, coupe sinon — le courant suit
l'ETAT D'EMISSION de la chaine, pas une decision independante) : le
tonique du banc suit gate.v > seuil, les DST ne tirent (et
n'apprennent) que fenetre ouverte ;
la - consequence mesurable : les evenements SRC ne sont plus que
l'emission brute de la chaine (l_arg x 6 x 7) — les relais de routage
du m4 deviennent du cablage (des evenements synaptiques, pas des
emissions). C'est exactement ce que la table m4 quantifiait.

Mechanique de copie INCHANGEE (meme pas, meme trace discipline, meme
tonique) — seule la SOURCE du tonique (la gate) et le CABLAGE des
arrivees (la table routee) sont nouveaux. Les poids finaux sont
bit-exacts contre l'ecriture directe v1 (verifie par run_multiplex).
"""

import math

import snn_engine as se
import copy_stdp
import cube_state as cs

DT = copy_stdp.DT
N_BITS = cs.N_BITS
DELAY_STEPS = int(round(copy_stdp.DELAY_MS / DT))
CYCLE_STEPS = int(round(copy_stdp.CYCLE_MS / DT))


class GatedTap:
    """Un tap : memoire STDP (DST + poids + traces), table de routage
    par fenetre, et sa GATE LIF (le courant d'armement suit la fenetre
    courante de la chaine)."""

    def __init__(self, slot, routed, my_window,
                 i_on=0.8, thr=0.5, tau_gate=2.0, dt=DT):
        self.slot = slot
        self.routed = routed              # par fenetre : 7 phases
        self.my_window = my_window
        n = N_BITS
        self.w = [copy_stdp.W0] * n
        self.g = [0.0] * n
        self.trace_pre = [0.0] * n
        self.trace_post = [0.0] * n
        self.dst = [se.Neuron(tau_m=10.0, t_ref=2.0, dt=dt)
                    for _ in range(n)]
        self.arrivals = {}
        self.k_step = 0
        self.i_theta = 0.75               # le tonique v1 (fenetre ouverte)
        self.k_syn = math.exp(-dt / 2.0)
        self.k_tr = math.exp(-dt / copy_stdp.TAU_PRE)
        # la GATE : LIF RAPIDE (tau 2 ms — montee en ~1.8 ms, chute en
        # ~1 ms : sans la chute rapide, les premieres arrivees de la
        # fenetre SUIVANTE toucheraient le banc pendant que le tonique
        # decline — fuite d'apprentissage sur les bits du voisin) ;
        # courant I_ON pendant SA fenetre, 0 sinon ; etat = v (grade),
        # seuil de tonique thr
        self.gate = se.Neuron(tau_m=tau_gate, t_ref=0.5, dt=dt)
        self.i_on = i_on
        self.thr = thr

    def step(self, pre_canals, window):
        """Un pas de simulation partage. pre_canals : les canaux dont le
        bit SRC de la chaine tire A CE PAS (l'offset de cycle), ou [].
        window : l'index de la fenetre courante de la chaine. Renvoie
        les DST qui tirent."""
        # la GATE d'abord : son courant suit l'etat d'emission
        i_gate = self.i_on if window == self.my_window else 0.0
        self.gate.step(i_gate)
        tonic = self.gate.v > self.thr
        # mecanique v1 (CopyBench.step) : decays, arrivees, DST,
        # poids, traces — dans le meme ordre
        for k in range(N_BITS):
            self.g[k] *= self.k_syn
            self.trace_pre[k] *= self.k_tr
            self.trace_post[k] *= self.k_tr
        for k in self.arrivals.pop(self.k_step, []):
            self.g[k] += self.w[k]
        spiked = []
        for k in range(N_BITS):
            i = self.g[k] + (self.i_theta if tonic else 0.0)
            if self.dst[k].step(i):
                spiked.append(k)
        for k in spiked:
            self.w[k] = min(self.w[k] + copy_stdp.A_PLUS * self.trace_pre[k],
                            copy_stdp.W_MAX)
            self.trace_post[k] = 1.0
        # les pre de la chaine : PROJECTION ROUTEE (cablage) — chaque
        # canal emis arrive a SON bit route pour cette fenetre ; trace
        # pre incrementee APRES la mise a jour des poids (discipline v1)
        if pre_canals:
            table = self.routed[window]
            for g in pre_canals:
                k2 = g * 8 + table[g]
                self.arrivals.setdefault(
                    self.k_step + DELAY_STEPS, []).append(k2)
                self.trace_pre[k2] = 1.0
        self.k_step += 1
        return spiked

    def recall(self, pattern, duration_ms=30.0):
        """Rappel : rejoue le pattern route comme pre de chaine (sans
        tonique) — les DST ne tirent que sur les poids APPRIS."""
        fired = {k: [] for k in range(N_BITS)}
        for g, v in enumerate(pattern):
            k2 = g * 8 + v
            self.trace_pre[k2] = 1.0
            self.arrivals.setdefault(
                self.k_step + DELAY_STEPS, []).append(k2)
        for _ in range(int(duration_ms / DT)):
            for k in range(N_BITS):
                self.g[k] *= self.k_syn
                self.trace_pre[k] *= self.k_tr
                self.trace_post[k] *= self.k_tr
            for k in self.arrivals.pop(self.k_step, []):
                self.g[k] += self.w[k]
            for k in range(N_BITS):
                if self.dst[k].step(self.g[k]):
                    fired[k].append(self.k_step * DT)
            self.k_step += 1
        return fired


class GatedChain:
    """La chaine gatee : UNE emission brute partagee, tous les taps
    recoivent toutes les fenetres par leurs projections routees, et
    n'apprennent que fenetre ouverte (GATE LIF)."""

    def __init__(self, raw, groups, pats, i_on=0.8, thr=0.5):
        self.raw = raw
        self.taps = {}
        for start, _sh in groups:
            for i in range(len(raw)):
                slot = start + i
                routed = [pats[start + w] for w in range(len(raw))]
                self.taps[slot] = GatedTap(slot, routed, i,
                                           i_on=i_on, thr=thr)

    def run(self, ctr=None):
        """Deroule la chaine : l_arg fenetres de 6 cycles ; a l'offset
        de chaque cycle, les canaux du token courant tirent (l'UNIQUE
        emission) et les projections routent vers tous les taps.
        ctr (m4) : {"cycles", "src", "dst"} — les evenements SRC sont
        l'emission brute SEULE (les livraisons sont du cablage) ; les
        spikes DST comptent les tires de tous les taps (fenetre propre
        + re-tirs clampes hors fenetre)."""
        offset = int(round(copy_stdp.SRC_OFFSET_MS / DT))
        raw_bits = [cs.pattern_bits(p) for p in self.raw]
        for i in range(len(self.raw)):
            canals = [k // 8 for k in raw_bits[i]]
            if ctr is not None:
                ctr["cycles"] += copy_stdp.N_CYCLES
            for _c in range(copy_stdp.N_CYCLES):
                for _s in range(CYCLE_STEPS):
                    pre = canals if _s == offset else []
                    if ctr is not None and pre:
                        ctr["src"] += len(pre)
                    for tap in self.taps.values():
                        spiked = tap.step(pre, i)
                        if ctr is not None:
                            ctr["dst"] += len(spiked)

    def weights(self, slot):
        return list(self.taps[slot].w)

    def recall(self, slot, pattern):
        return self.taps[slot].recall(pattern)
