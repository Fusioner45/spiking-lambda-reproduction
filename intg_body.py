# -*- coding: utf-8 -*-
"""Mini-lab, palier 5 : le compteur de balance INTG_BODY du papier (§2.5).

Role : apres le redex en K, trouver la fin du CORPS du sous-terme. En
prefixe polonais, un sous-terme se termine quand la balance
    sigma(j) = somme des (1[VAR] - 1[APP])   depuis K+2
atteint +1 pour la premiere fois (eq. 7).

Circuit (§2.5) : UN neurone tres lent (tau_m = 300 ms, t_ref = 0.1 ms)
qui integre +W_CNT par VAR et -W_CNT par APP, avec
    W_CNT = 1 / epsilon(300, 1)                 (eq. 8)
=> exactement un pic de seuil par unite de balance ; la fuite entre
slots (8 ms << tau_m) est < 2.6 % par slot. Il decharge quand sigma
atteint +1 et active ARG_MODE (§2.5.1), neurone auto-entretenu
(tau_m = 10 ms, synapse recurrente calibree, ~165 Hz chez nous).
"""

import bridge_db as bd            # APP, et find_redex (reference)
import snn_engine as se

SLOT_MS = 8.0
DT = 0.1


def _add_neuron(net, tau_m, t_ref):
    """Constructeur de neurone moteur-agnostique : objet Neuron pour le
    moteur Python, add(tau_m, t_ref) pour le moteur C."""
    if isinstance(net, se.Network):
        return net.add(se.Neuron(tau_m=tau_m, t_ref=t_ref, dt=net.dt))
    return net.add(tau_m, t_ref)




def body_end_pos(tokens, k_redex):
    """Verite semantique : position (relative au corps) du premier +1 de
    la balance sigma depuis K+2. None si le corps ne se referme jamais."""
    sigma = 0
    for j in range(k_redex + 2, len(tokens)):
        tid = tokens[j][0]
        if tid >= 4:
            sigma += 1
        elif tid == bd.APP:
            sigma -= 1
        if sigma == 1:
            return j - (k_redex + 2)
    return None


def sigma_sequence(tokens, k_redex):
    """La sequence sigma token par token (pour affichage, cf. Fig. 3)."""
    out, sigma = [], 0
    for j in range(k_redex + 2, len(tokens)):
        tid = tokens[j][0]
        if tid >= 4:
            sigma += 1
        elif tid == bd.APP:
            sigma -= 1
        out.append(sigma)
    return out


class IntgCircuit:
    """INTG_BODY + ARG_MODE reels pour le corps du redex en K."""

    def __init__(self, tokens, k_redex, slot_ms=SLOT_MS, dt=DT,
                 v_target=1.15, w_intg_arg=9.0, net_factory=None,
                 tau_m=300.0):
        # tau_m=300 = le parametre du papier (§2.5) ; tau_m plus grand
        # approche l'attracteur lineaire de Seung [53] que le papier cite
        # (« the slow tau_m performs the same role ») — finding n°8 : le
        # discharge derive sur les longs sous-termes, la montee de tau_m
        # est la compensation de fuite (fix valide par bench, cf. scale).
        self.tokens = tokens
        self.k = k_redex
        self.slot_ms = slot_ms
        self.dt = dt
        self.tau_m = tau_m

        # ---- calibration par mesure (methode §2.3.2) ----
        self.eps_3001 = se.measure_epsilon(self.tau_m, 1.0, dt)
        self.eps_102 = se.measure_epsilon(10.0, 2.0, dt)
        self.w_cnt = 1.0 / self.eps_3001          # eq. (8) : 1 pulse = 1 unite
        self.w_self_arg = v_target / self.eps_102  # ARG_MODE auto-entretenu

        # ---- reseau ----
        self.net = (net_factory or se.Network)(dt)
        self.port_var, self.port_app = 100, 101   # sources virtuelles
        self.intg = _add_neuron(self.net, self.tau_m, 0.1)
        self.arg = _add_neuron(self.net, 10.0, 2.0)
        self.net.connect(self.port_var, self.intg, +self.w_cnt,
                         delay_ms=0.5, tau_syn=1.0)
        self.net.connect(self.port_app, self.intg, -self.w_cnt,
                         delay_ms=0.5, tau_syn=1.0)
        # lien INTG -> ARG en tau_syn=2 ms : eq. (9) du papier vaut
        # W x epsilon(10,2) = 9x0.137 = 1.23 > 1 (tau_syn=1 donnerait
        # 9x0.081 = 0.73 < 1 : ARG_MODE ne partirait jamais)
        self.net.connect(self.intg, self.arg, w_intg_arg,
                         delay_ms=0.2, tau_syn=2.0)
        self.net.connect(self.arg, self.arg, self.w_self_arg,
                         delay_ms=0.1, tau_syn=2.0)

        # ---- pulses : les tokens du corps, un slot par token ----
        for j in range(k_redex + 2, len(tokens)):
            tid = tokens[j][0]
            t0 = slot_ms * (j - k_redex - 2)
            if tid >= 4:
                self.net.inject_spike(self.port_var, t0)
            elif tid == bd.APP:
                self.net.inject_spike(self.port_app, t0)

    def run(self, extra_ms=80.0):
        """Simule. Renvoie : position relative du premier decharge d'INTG
        (= fin du corps), son temps, et le compte de spikes d'ARG_MODE."""
        n_steps = int(((len(self.tokens) - self.k - 2) * self.slot_ms
                       + extra_ms) / self.dt)
        intg_times, arg_count = [], 0
        for tms, idx in self.net.bulk_run(n_steps):
            if idx == self.intg:
                intg_times.append(tms)
            elif idx == self.arg:
                arg_count += 1
        if intg_times:
            pos = int(intg_times[0] // self.slot_ms)
        else:
            pos = None
        return {"pos": pos, "t_dis": intg_times[0] if intg_times else None,
                "n_intg": len(intg_times), "n_arg": arg_count}
