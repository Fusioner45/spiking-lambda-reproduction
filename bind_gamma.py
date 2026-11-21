# -*- coding: utf-8 -*-
"""Mini-lab, palier 5 : detection de liaison theta-gamma (§2.6).

Regle (§2.6, eq. 10) : un VAR du corps est lie au lambda du redex ssi
    BIND_FINE(j) == SELF_FINE(K+1)  ET  BIND_COARSE(j) == SELF_COARSE(K+1)
Circuit : « two fast coincidence neurons check each condition
independently, and a slow integrator (tau_m = 40 ms) accumulates both
coincidence spikes within a theta window ». Notre realisation (le
cadencement fin de presentation des phases n'est pas specifie dans le
papier — note de conception) :
  - 8 neurones de coincidence par canal (une par valeur 0..7) : le
    SELF[k] du lambda et le BIND[k] du VAR pulses au meme instant ne
    font fire que coin[k] — l'egalite de valeur devient co-activation
    (binding by synchrony, forme reduite mais exacte sur le masque) ;
  - integrateur lent tau_m = 40 ms : fire ssi les DEUX coincidences du
    canal fine et du canal coarse arrivent (W_AND calibre : 2 entrees >
    1, 1 entree < 1) ;
  - presentation SERIELLE des VAR du corps, 20 ms d'ecart (note : le
    papier ne specifie pas ce cadencement ; 20 ms place le residu de
    l'integrateur, e^{-20/40} = 0.61, sous le seuil de fausse somme
    croisee — verifie empiriquement sur un cas adversarial) ;
  - encodage = NOTRE fix variables libres (BIND libre = (7,7)) : une
    variable libre ne peut plus coincer avec un lambda de profondeur 0 ;
    contre-test : avec l'encodage PAPIER (0,0), le bug §3.3 se produit
    AU NIVEAU DU CIRCUIT (le libre est marque lie).
"""

import bridge_db as bd
import free_vars_fix as fv
import snn_engine as se

DT = 0.1


def _add_neuron(net, tau_m, t_ref):
    """Constructeur de neurone moteur-agnostique : objet Neuron pour le
    moteur Python, add(tau_m, t_ref) pour le moteur C."""
    if isinstance(net, se.Network):
        return net.add(se.Neuron(tau_m=tau_m, t_ref=t_ref, dt=net.dt))
    return net.add(tau_m, t_ref)


VAR_GAP_MS = 60.0          # cadencement de presentation des VAR (note de
# conception n°7 : le « theta window » du §2.6 est censé réinitialiser
# l'intégrateur entre VAR mais leur cadencement n'est pas spécifié. En
# présentation sérielle, des coïncidences COARSE-seule consécutives
# s'accumulent (le canal coarse ne distingue que depth//8) : à 20 ms
# d'écart, 3 slots consécutifs suffisent (1+0.61+0.37 unités > seuil) —
# observé sur plus 2 3 étape 2. A 60 ms, la somme géométrique des
# résidus, bornee par 1/(e^{1.5}-1) = 0.28 EPSP, garde toute accumulation
# (même infinie) a 0.74 < 1, et le feu légitime garde sa marge (1.31).


class BindCircuit:
    """Circuit de liaison pour le corps du redex en K (tokens, rows)."""

    def __init__(self, rows, k_redex, body_end=None, v_target=1.15, dt=DT,
                 net_factory=None, noisy=None, free_ff=True):
        self.dt = dt
        # les VAR du corps, en ordre prefixe, avec leurs phases BIND
        # (scopés au corps : un VAR de l'ARGUMENT n'est pas candidat,
        # meme si son propre lambda est a la profondeur du redex —
        # roles KEEP/BOUND/ARG §2.9)
        self.d_lam = rows[k_redex + 1][1]              # profondeur du lambda
        lam = rows[k_redex + 1]
        # SELF du lambda = colonnes 2-3 (pas 4-5 = BIND, toujours (0,0)
        # pour un LAM — bug d'indexation qui ne se voyait que sur les
        # redex a profondeur > 0)
        self.kf_lam, self.kc_lam = lam[2], lam[3]
        end = body_end if body_end is not None else len(rows)
        self.vars = [(i, r[4], r[5]) for i, r in enumerate(rows)
                     if k_redex + 1 < i < end and r[0] >= 4]
        # ---- calibration ----
        self.eps402 = se.measure_epsilon(40.0, 2.0, dt)
        # paire SIMULTANEE sur un neurone tau_m=2, tau_syn=1
        net = se.Network(dt)
        a, b = 0, 1
        post = net.add(se.Neuron(tau_m=2.0, v_th=99.0, dt=dt))
        net.connect(a, post, 1.0, delay_ms=0.5, tau_syn=1.0)
        net.connect(b, post, 1.0, delay_ms=0.5, tau_syn=1.0)
        net.inject_spike(a, 0.0)
        net.inject_spike(b, 0.0)
        vmax = 0.0
        for _ in range(300):
            net.step()
            vmax = max(vmax, net.neurons[post].v)
        self.pair_coin = vmax
        self.w_coin = v_target / vmax                  # AND des coins
        self.w_and = v_target / (2.0 * self.eps402)    # AND de l'integrateur

        # ---- reseau (la calibration mini-net reste en Python) ----
        net = (net_factory or se.Network)(dt)
        self.net = net
        # ports : self_fine[k]=100+k, bind_fine[k]=110+k,
        #         self_coarse[k]=120+k, bind_coarse[k]=130+k
        self.coin_f = [_add_neuron(net, 2.0, 1.0) for _ in range(8)]  # 0..7
        self.coin_c = [_add_neuron(net, 2.0, 1.0) for _ in range(8)]  # 8..15
        self.intg = _add_neuron(net, 40.0, 0.1)                       # 16
        for k in range(8):
            net.connect(100 + k, self.coin_f[k], self.w_coin,
                        delay_ms=0.5, tau_syn=1.0)
            net.connect(110 + k, self.coin_f[k], self.w_coin,
                        delay_ms=0.5, tau_syn=1.0)
            net.connect(120 + k, self.coin_c[k], self.w_coin,
                        delay_ms=0.5, tau_syn=1.0)
            net.connect(130 + k, self.coin_c[k], self.w_coin,
                        delay_ms=0.5, tau_syn=1.0)
            net.connect(self.coin_f[k], self.intg, self.w_and,
                        delay_ms=0.5, tau_syn=2.0)
            net.connect(self.coin_c[k], self.intg, self.w_and,
                        delay_ms=0.5, tau_syn=2.0)
        # variante Â« inhibition FREE_F Â» (port 140) : pulse inhibiteur
        # cale a -1.15/epsilon(40,2) sur les slots des VAR libres
        self.w_ff = -(1.15 / self.eps402)
        net.connect(140, self.intg, self.w_ff, delay_ms=0.5, tau_syn=1.0)
        self.noisy = noisy
        self.free_ff = free_ff
        self.free_slots = [bool(rows[i][6]) for (i, _bf, _bc) in self.vars]
        # (pas de quench : l'écart de 60 ms entre slots borne les
        # résidus, voir note de conception n°7 ci-dessus)

    def run(self):
        """Presente les VAR du corps serielement ; renvoie les indices
        (dans l'ordre des VAR du corps) marques BOUND par l'integrateur,
        et les temps de fire des coins (pour les tests adversariaux).

        noisy (optionnel, via __init__) : {"self_f": set, "self_c": set,
        "bind": [(bits_f, bits_c), ...]} — bits ADDITIONNELS actifs par
        canal (bruit WM du papier, §3.2 bloc 9 : bits inactifs actives
        avec proba p, bits actifs conserves). """
        net = self.net
        noisy = self.noisy
        for m, (pos, bf, bc) in enumerate(self.vars):
            t0 = m * VAR_GAP_MS
            if noisy is not None:
                sf_bits = noisy["self_f"]
                sc_bits = noisy["self_c"]
                bfb, bcb = noisy["bind"][m]
            else:
                sf_bits = (self.kf_lam,)
                sc_bits = (self.kc_lam,)
                bfb, bcb = (bf,), (bc,)
            for k in sf_bits:
                net.inject_spike(100 + k, t0)           # SELF_FINE du lambda
            for k in sc_bits:
                net.inject_spike(120 + k, t0)           # SELF_COARSE
            for k in bfb:
                net.inject_spike(110 + k, t0)           # BIND_FINE du VAR
            for k in bcb:
                net.inject_spike(130 + k, t0)           # BIND_COARSE
            if self.free_slots[m] and self.free_ff:
                # variante « inhibition FREE_F » : un libre ne peut jamais
                # etre marque lie, meme sous bruit (pulse inhibiteur cale
                # pour annuler deux coïncidences pleines)
                net.inject_spike(140, t0)
        n_steps = int((len(self.vars) * VAR_GAP_MS + 60.0) / self.dt)
        bound, coin_t = [], {("f", k): [] for k in range(8)}
        coin_t.update({("c", k): [] for k in range(8)})
        for tms, idx in net.bulk_run(n_steps):
            if idx == self.intg:
                m = int(tms // VAR_GAP_MS)
                if m < len(self.vars) and m not in bound:
                    bound.append(m)
            elif idx < 8:
                coin_t[("f", idx)].append(tms)
            elif idx < 16:
                coin_t[("c", idx - 8)].append(tms)
        return {"bound": sorted(bound), "coin_t": coin_t}


# ---- verite semantique (independante du circuit) ------------------------

def truth_bound_indices(rows, k_redex, body_end=None):
    """Les VAR du corps lies au lieur du redex. L'adresse du lieur
    est FINE + COARSE (profondeur mod 8 et // 8, §2.6) : comparer la
    fine seule faisait matcher les VAR a la profondeur d_lam + 8k (le
    lieur d'un autre niveau — expose par append sur les listes
    emboitees, session 43 ; le banc plus 2 3, profondeurs < 8, ne
    pouvait pas le voir)."""
    d_lam = rows[k_redex + 1][1]
    d_fine, d_coarse = d_lam % 8, d_lam // 8
    end = body_end if body_end is not None else len(rows)
    out = []
    for i, r in enumerate(rows):
        if (k_redex + 1 < i < end and r[0] >= 4 and not r[6]
                and r[4] == d_fine and r[5] == d_coarse):
            out.append(i)
    return out


def body_var_order(rows, k_redex, body_end=None):
    """Indices absolus des VAR du corps, en ordre prefixe."""
    end = body_end if body_end is not None else len(rows)
    return [i for i, r in enumerate(rows)
            if k_redex + 1 < i < end and r[0] >= 4]
