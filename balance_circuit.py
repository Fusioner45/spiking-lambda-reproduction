# -*- coding: utf-8 -*-
"""Circuit spiking du compteur de balance POSITIONNEL (chantier B-2).

La spec (balance_digits.py) est validee ; ce circuit la reproduit en
neurones reels, avec les primitives du papier et rien d'autre :

* CHIFFRE = 8 PERSIST one-hot (§2.9 : tau_m=10, t_ref=2, recurrent
  9/tau_syn=2, ~483 Hz mesures, amorce >= 1.0, extinction HALT -15).
  Exactement un actif = la valeur du chiffre ; l'etat tient entre les
  tokens sans decroir (l'information vit dans QUI tire, pas dans un
  potentiel integre).
* TRANSITION = 8 T+ et 8 T- par chiffre (tau_m=2 — le GATE §2.9). Le
  T+[k] lit l'ETAT de P[k] par son TRAIN RAPIDE (spikes, tau_syn=2 :
  present des l'allumage, disparu ~6 ms apres la mort — PAS par un
  filtre 20 ms, dont la montee a 44 ms derait la machine de 5 slots et
  dont la queue apres le HALT provoquerait des doubles pas). Le pulse
  VAR diffuse (W x eps(2,1) = +0.92) : train seule 0.44 < 1 (jamais de
  feu spontane), train + pulse 1.36 > 1 (feu exactement sur le pas).
  T+[k] -> HALT sur P[k] et allumage de P[(k+1)%8] : la main passe en
  ~2 ms. T-[k] idem vers P[(k-1)%8].
* RETENUE = le wrap T+[7] (resp. T-[0]) re-alimente la diffusion T+
  (resp. T-) du chiffre superieur : le carry EST un pas pour le
  chiffre suivant, les cascades tombent naturellement (les chiffres
  superieurs sont settles : ils ne changent qu'aux retenues).
* COMPARATEUR — le probleme de timing du papier (question ouverte n°7
  en analogique) resolu SANS somme analogique : le comparateur (tau_m=2)
  feure sur le spike de T+[0] de d0 (le pas VAR 0->1 de d0, le seul
  chemin vers sigma = +1) SAUF INHIBITION des etats non-nuls des
  chiffres superieurs : les 14 P de d1.P[1..7] et d2.P[1..7] inhibent
  en tonique. Les faux T+[0] (sigma = -8 -> -7, +8 -> +9...) voient
  d1 ou d2 != 0 -> inhibes ; d1 = d2 = 0 n'offre aucune inhibition ->
  feu exact au handover. Le latch garde le premier feu (§2.5.1).
* WARM-UP : 2 slots pour etablir les trains initiaux ; la position
  rendue est corrigee de W (l'encodage initial reste meta, §2.11).
* LAM : aucun pulse -> aucun pas (traverse sans feu), comme la spec.

Le differentiel spike-a-spike contre la spec est dans run_balance.py
(BLOC B-2) : chiffres par slot, retenues, feu du comparateur, position
de discharge — les deux moteurs.
"""

import bridge_db as bd
import snn_engine as se

DT = 0.1
SLOT_MS = 25.0       # l'horloge interne du compteur (libre : la
                      # montee du train d'un P fraichement allume doit
                      # etre >= 70 % au pas suivant, cf. les marges)
N_BASE = 8
W_SELF = 9.0          # PERSIST recurrent (§2.9)
W_HALT = -15.0        # extinction (§2.9)
W_IGNITE = 9.0        # amorce d'un PERSIST (9 x eps(10,2) = 1.23 > 1)
W_STEP = 5.5          # pulse de step (tau_syn=2 !) : +4.6 x eps(10,2)
                      # = +0.63 x ripple 1.1 = 0.69 < 1 sur train nul
                      # (le runaway 8-T/8-P teste a 3.5/tau_syn=1) ;
                      # train etabli 0.76 + 0.69 = 1.45 > 1
W_T_TRAIN = 0.80       # train P -> T sur lecteur tau_m=10 : V=0.76
                      # (lisse, ripple ±10 %) < 1 < train + pulse
W_CMP_S = 4.0         # le spike T+[0] : +4.0 x eps(2,1) = +1.05 >= 1
W_CMP_INH = -1.2      # l'inhibition d'un etat non-nul de d1/d2 (le
                      # tonique du P actif, x1.3) : +1.05 - 1.56 < 1
WARMUP_SLOTS = 4      # la montee des toniques initiaux (3 tau_m)


def _add(net, tau_m, t_ref):
    if isinstance(net, se.Network):
        return net.add(se.Neuron(tau_m=tau_m, t_ref=t_ref, dt=net.dt))
    return net.add(tau_m, t_ref)


class BalanceCircuit:
    """3 chiffres base 8 en PERSIST one-hot + transitions gatees + le
    comparateur-GATE. Attributs : digits[d] = les 8 indices P,
    tsp[d] / tsm[d] = les 8 T+ / T-, cmp = l'index du comparateur."""

    def __init__(self, tokens, k_redex, n_digits=3, slot_ms=SLOT_MS,
                 dt=DT, net_factory=None):
        self.tokens = tokens
        self.k = k_redex
        self.slot_ms = slot_ms
        self.dt = dt
        self.n_digits = n_digits
        self.warmup = WARMUP_SLOTS * slot_ms
        self.net = (net_factory or se.Network)(dt)
        self.port_var, self.port_app = 100, 101
        self.digits, self.tsp, self.tsm = [], [], []

        for d in range(n_digits):
            P, TP, TM = [], [], []
            for k in range(N_BASE):
                P.append(_add(self.net, 10.0, 2.0))
                TP.append(_add(self.net, 10.0, 1.0))
                TM.append(_add(self.net, 10.0, 1.0))
            self.digits.append(P)
            self.tsp.append(TP)
            self.tsm.append(TM)
            for k in range(N_BASE):
                nxt, prv = P[(k + 1) % N_BASE], P[(k - 1) % N_BASE]
                self.net.connect(P[k], P[k], W_SELF, delay_ms=0.1,
                                 tau_syn=2.0)
                # l'etat de P[k] lu par son TRAIN RAPIDE sur T+[k]/T-[k]
                self.net.connect(P[k], TP[k], W_T_TRAIN, delay_ms=0.5,
                                 tau_syn=2.0)
                self.net.connect(P[k], TM[k], W_T_TRAIN, delay_ms=0.5,
                                 tau_syn=2.0)
                # la main : HALT du courant + allumage du voisin
                self.net.connect(TP[k], P[k], W_HALT, delay_ms=0.2,
                                 tau_syn=2.0)
                self.net.connect(TP[k], nxt, W_IGNITE, delay_ms=0.2,
                                 tau_syn=2.0)
                self.net.connect(TM[k], P[k], W_HALT, delay_ms=0.2,
                                 tau_syn=2.0)
                self.net.connect(TM[k], prv, W_IGNITE, delay_ms=0.2,
                                 tau_syn=2.0)
                # la diffusion des pulses de step ne cable que le
                # chiffre FIN (d=0) : les chiffres superieurs ne
                # steppent QUE par retenues — sinon le broadcast
                # tirerait leurs neurones de wrap a chaque token (le
                # comparateur s'accumulerait)
                if d == 0:
                    self.net.connect(self.port_var, TP[k], W_STEP,
                                     delay_ms=0.2, tau_syn=2.0)
                    self.net.connect(self.port_app, TM[k], W_STEP,
                                     delay_ms=0.2, tau_syn=2.0)

        # retenues : SEUL le wrap re-alimente le chiffre superieur
        for d in range(n_digits - 1):
            for k in range(N_BASE):
                self.net.connect(self.tsp[d][7], self.tsp[d + 1][k],
                                 W_STEP, delay_ms=0.5, tau_syn=2.0)
                self.net.connect(self.tsm[d][0], self.tsm[d + 1][k],
                                 W_STEP, delay_ms=0.5, tau_syn=2.0)

        # comparateur (§2.9 AND) : les trains de d1.P0 et d2.P0 en
        # tonique, le spike de T+[0] de d0 en pulse declencheur
        self.cmp = _add(self.net, 2.0, 1.0)
        self.net.connect(self.tsp[0][0], self.cmp, W_CMP_S,
                         delay_ms=0.2, tau_syn=1.0)
        for k in range(1, N_BASE):
            self.net.connect(self.digits[1][k], self.cmp, W_CMP_INH,
                             delay_ms=0.2, tau_syn=2.0)
            self.net.connect(self.digits[2][k], self.cmp, W_CMP_INH,
                             delay_ms=0.2, tau_syn=2.0)

        # etat initial : sigma = 0 -> P[0] actif sur chaque chiffre ;
        # l'encodage initial reste meta (§2.11, comme le papier)
        for d in range(n_digits):
            self.net.inject_spike(self.digits[d][0], 0.2)

        # les pulses du corps, un slot par token apres le warm-up (LAM :
        # rien) ; le slot 0 de la spec = le slot WARMUP_SLOTS du reseau
        for j in range(k_redex + 2, len(tokens)):
            tid = tokens[j][0]
            t0 = self.warmup + slot_ms * (j - k_redex - 2)
            if tid >= 4:
                self.net.inject_spike(self.port_var, t0 + 0.3)
            elif tid == bd.APP:
                self.net.inject_spike(self.port_app, t0 + 0.3)

    def run(self, extra_ms=30.0):
        """Simule. Renvoie la position (relative, corregee du warm-up)
        du premier feu du comparateur, les chiffres actifs par slot de
        spec et les evenements de retenue par slot — le miroir de la
        trace de balance_digits.run_counter."""
        n_body = len(self.tokens) - self.k - 2
        n_steps = int((self.warmup + n_body * self.slot_ms + extra_ms)
                      / self.dt)
        n_slots = WARMUP_SLOTS + n_body + 3
        P_of = {}
        for d in range(self.n_digits):
            for k in range(N_BASE):
                P_of[self.digits[d][k]] = (d, k)
        TP_wrap = {self.tsp[d][7]: (d, +1) for d in range(self.n_digits)}
        TM_wrap = {self.tsm[d][0]: (d, -1) for d in range(self.n_digits)}
        digits_by_slot = [[None] * self.n_digits for _ in range(n_slots)]
        carries_by_slot = [[] for _ in range(n_slots)]
        cmp_slot = None
        for _i in range(n_steps):
            fired = self.net.step()
            t = self.net.k_step * self.dt
            slot = int(t // self.slot_ms)
            if slot >= n_slots:
                continue
            for idx in fired:
                if idx == self.cmp:
                    if cmp_slot is None:
                        cmp_slot = slot
                elif idx in P_of:
                    d, k = P_of[idx]
                    digits_by_slot[slot][d] = k
                elif idx in TP_wrap:
                    carries_by_slot[slot].append(TP_wrap[idx])
                elif idx in TM_wrap:
                    carries_by_slot[slot].append(TM_wrap[idx])
        # correction du warm-up : les slots de spec commenceraient au
        # slot WARMUP_SLOTS du reseau
        spec_digits = digits_by_slot[WARMUP_SLOTS:]
        spec_carries = carries_by_slot[WARMUP_SLOTS:]
        pos = None if cmp_slot is None else cmp_slot - WARMUP_SLOTS
        return {"pos": pos, "digits": spec_digits,
                "carries": spec_carries}
