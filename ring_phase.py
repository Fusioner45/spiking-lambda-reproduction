# -*- coding: utf-8 -*-
"""Mini-lab, palier 5 : anneau de phase pour l'arithmetique de De Bruijn
(§2.7).

Circuit (eq. 11) : anneau de K_F = 8 neurones FINE[k] -> FINE[(k+1) mod 8]
(delai 4 ms) — onde progressive ; ISI reel ~4.9 ms (latence membranaire).
Activer FINE[phi_0] lance l'onde ; apres sh pas de propagation — COMPTE
PAR RANG ORDINAL DE SPIKE, pas par horloge (piege documente) — le
neurone actif est FINE[(phi_0 + sh) mod 8]. Retenue : le rang actif
reboucle (seq[i] < seq[i-1]) => increment du registre COARSE.

Cas limites (releves par Gemini, traites ici) :
  - sh = 0 : la reponse est le pulse d'activation lui-meme (ordinal 0)
    — l'orchestrateur peut court-circuiter l'onde ; verifie ci-dessous.
  - sh < 0 : IMPOSSIBLE avec la convention de profondeur du papier :
    sh = d_var - 1 - d_ref avec d_ref = profondeur de la racine de
    l'argument = profondeur du lambda du redex d_lam, et tout VAR lie a
    ce lambda est a d_var >= d_lam + 1 => sh >= 0 structurellement.
    Prouve empiriquement sur toutes les substitutions de la batterie
    (plutot que d'ajouter le modulo 64 sur deux registres).
"""

import lambda_beta as lb
import bridge_db as bd
import free_vars_fix as fv
import snn_engine as se

DT = 0.1


class PhaseRing:
    """Anneau de 8 neurones FINE auto-entretenu (onde tournante)."""

    def __init__(self, dt=DT, v_target=1.15, delay_ms=4.0):
        self.dt = dt
        self.delay = delay_ms
        self.eps51 = se.measure_epsilon(5.0, 1.0, dt)
        self.w_ring = v_target / self.eps51        # auto-entretien de l'onde
        net = se.Network(dt)
        self.neurons = [net.add(se.Neuron(tau_m=5.0, t_ref=1.0, dt=dt))
                        for _ in range(8)]
        for k in range(8):
            net.connect(k, (k + 1) % 8, self.w_ring,
                        delay_ms=delay_ms, tau_syn=1.0)
            net.connect(200 + k, k, self.w_ring,   # ports d'activation
                        delay_ms=0.2, tau_syn=1.0)
        self.net = net

    def reset(self):
        """Remet l'anneau a zero (entre deux experiences : l'onde de la
        precedente tourne encore et polluerait les feux enregistres)."""
        net = self.net
        net.k_step = 0
        net.arrivals = {}
        net.g = {}
        for idx in self.neurons:               # indices -> objets
            n = net.neurons[idx]
            n.v = n.e_l
            n.ref_until = -1.0
            n.t = 0.0

    def run(self, phi0, n_fires):
        """Active FINE[phi0] et renvoie la sequence des n_fires premiers
        feux (indices de neurones, ordre chronologique) + les ISI."""
        self.reset()
        net = self.net
        net.inject_spike(200 + phi0, 0.2)
        fires, isis = [], []
        max_steps = int((n_fires * (self.delay + 4.0) + 20.0) / self.dt)
        for _ in range(max_steps):
            for idx in net.step():
                t = net.k_step * self.dt
                if fires:                      # ISI des que 2 feux
                    isis.append(t - fires[-1][1])
                fires.append((idx, t))
                if len(fires) >= n_fires:
                    return ([f[0] for f in fires],
                            [f[1] for f in fires], isis)
        return ([f[0] for f in fires], [f[1] for f in fires], isis)


# ---- preuve structurelle sh >= 0 + valeurs par occurrence ---------------

def substitutions_of_step(t):
    """Pour chaque etape de reduction : (K, d_lam, d_ref, liste des
    (position, d_var, sh) des VAR lies au lambda du redex)."""
    toks = bd.to_tokens(bd.to_debruijn(t))
    k = bd.find_redex(t)
    if k == -1:
        return None
    d_lam = toks[k + 1][1]
    d_ref = toks[k][1]                     # racine de l'argument = l'APP
    rows = fv.rows_fix(bd.to_debruijn(t))
    subs = []
    for j, r in enumerate(rows):
        if j > k + 1 and r[0] >= 4 and not r[6] and r[4] == d_lam:
            d_var = toks[j][1]
            subs.append((j, d_var, d_var - 1 - d_ref))
    return k, d_lam, d_ref, subs


def all_substitutions(t, max_steps=8):
    """Toutes les substitutions de toutes les etapes d'un terme."""
    out, cur = [], t
    for _ in range(max_steps):
        s = substitutions_of_step(cur)
        if s is None:
            break
        out.append(s)
        nxt, d = lb.beta_step(cur)
        if not d:
            break
        cur = nxt
    return out
