# -*- coding: utf-8 -*-
"""Mini-lab, palier 3 : le detecteur de redex DET du papier (§2.4) en
vrais neurones LIF.

Circuit (§2.4) : un pulse par token, un slot de 8 ms ; APP -> DET avec
delai axonal 8 ms, LAM -> DET avec delai 0.5 ms (tau_syn=1) ; DET et INH
sont des neurones rapides (tau_m=2 ms, t_ref=1 ms).
  - paire APP@j + LAM@j+1 : les deux EPSP arrivent ensemble (a 0.5 ms
    d'ecart, sommation sub-threshold->supra grace au pic large) => DET
    spike, et K = floor(t_DET/8) - 1.
  - un EPSP seul : 0.63·W/1.26 du pic de paire => sous le seuil (AND-gate).
  - DET -> INH (W=5) ; INH -> DET (W=-20) ; INH -> INH (self-sustain) :
    latch WTA, seule la premiere paire gagne.

Poids calibres par MESURE (méthode §2.3.2) : W_COIN = V_cible / somme
mesurée de la paire ; W_SELF_INH = V_cible / epsilon(2,2) mesuré.
"""

import bridge_db as bd            # pour LAM/APP et find_redex (reference)
import snn_engine as se

SLOT_MS = 8.0
DT = 0.1


def _add_neuron(net, tau_m, t_ref):
    """Constructeur de neurone moteur-agnostique : objet Neuron pour le
    moteur Python, add(tau_m, t_ref) pour le moteur C."""
    if isinstance(net, se.Network):
        return net.add(se.Neuron(tau_m=tau_m, t_ref=t_ref, dt=net.dt))
    return net.add(tau_m, t_ref)




class DetCircuit:
    """Detecteur Jeffress reel pour une sequence de tokens (id, depth)."""

    def __init__(self, tokens, slot_ms=SLOT_MS, dt=DT,
                 v_target=1.15, w_inh_det=-20.0, w_det_inh=5.0,
                 net_factory=None):
        self.tokens = tokens
        self.slot_ms = slot_ms
        self.dt = dt

        # ---- calibration par mesure (pas de hand-tuning) ----
        self.eps_21 = se.measure_epsilon(2.0, 1.0, dt)      # EPSP unitaire DET
        self.eps_22 = se.measure_epsilon(2.0, 2.0, dt)      # recurrent INH
        pair_unit = se.pair_pulse_sum(dt)                   # paire APP/LAM (0.5 ms)
        self.pair_unit = pair_unit
        self.w_coin = v_target / pair_unit                  # AND-gate calibre
        self.w_self_inh = v_target / self.eps_22            # latch INH

        # ---- reseau ----
        self.net = (net_factory or se.Network)(dt)
        # ports virtuels : indices HORS plage des neurones (sources a la main)
        self.port_app, self.port_lam = 100, 101
        self.det = _add_neuron(self.net, 2.0, 1.0)
        self.inh = _add_neuron(self.net, 2.0, 1.0)
        self.net.connect(self.port_app, self.det, self.w_coin,
                         delay_ms=slot_ms, tau_syn=1.0)
        self.net.connect(self.port_lam, self.det, self.w_coin,
                         delay_ms=0.5, tau_syn=1.0)
        self.net.connect(self.det, self.inh, w_det_inh, delay_ms=0.2, tau_syn=1.0)
        self.net.connect(self.inh, self.det, w_inh_det, delay_ms=0.1, tau_syn=1.0)
        self.net.connect(self.inh, self.inh, self.w_self_inh,
                         delay_ms=0.1, tau_syn=2.0)

        # ---- pulses : un spike par token, un slot de 8 ms ----
        for j, (tid, _d) in enumerate(tokens):
            t0 = slot_ms * j
            if tid == bd.APP:
                self.net.inject_spike(self.port_app, t0)
            elif tid == bd.LAM:
                self.net.inject_spike(self.port_lam, t0)

    def run(self, extra_ms=40.0):
        """Simule la duree du scan + marge. Renvoie un rapport :
        K detecte, temps du spike DET, nombre total de spikes DET/INH."""
        n_steps = int((len(self.tokens) * self.slot_ms + extra_ms) / self.dt)
        det_times, inh_spikes = [], 0
        for tms, idx in self.net.bulk_run(n_steps):
            if idx == self.det:
                det_times.append(tms)
            elif idx == self.inh:
                inh_spikes += 1
        if det_times:
            k = int(det_times[0] // self.slot_ms) - 1
        else:
            k = -1
        return {"K": k, "t_det": det_times[0] if det_times else None,
                "n_det": len(det_times), "n_inh": inh_spikes,
                "det_times": det_times}
