# -*- coding: utf-8 -*-
"""Mini-lab, palier 5 : PERSIST / GATE / SCAN du papier (§2.9-2.10).

PERSIST (§2.9) : un neurone par (role, slot), tau_m = 10 ms, t_ref = 2 ms,
auto-entretenu par synapse recurrente W_SELF = 9 en tau_syn = 2 ms
(9x0.137 = 1.23 > 1). Le papier souligne que tau_syn = 1 casse tout
(9x0.081 = 0.73 < 1) : on REPRODUIT ce diagnostic en test negatif.
Extinction par HALT (W = -15).

GATE (§2.9, eq. 13) : neurone rapide tau_m = 2 ms recevant le tonique
filtre de PERSIST (W_PG, tau_syn = 20 ms -> V_ss cible 0.83, calibre par
mesure) + le pulse du SCAN (W_GATE calibre pour +0.21). AND : le GATE ne
fire que si le slot a un role actif ET que le SCAN passe.

SCAN (§2.10.1) : chaine de delais pos[j] -> pos[j+1]. Le texte dit
d = SLOT = 8 ms mais un ISI reel de 4.9 ms — impossible (ISI >= delai) ;
l'anneau §2.7 utilise d = 4 ms : on prend d = 4 ms et on MESURE l'ISI
(question ouverte n°5).

Incoherence arithmetique notee (question ouverte n°4) : l'eq. (13) ecrit
« 1.5 x 0.263 = 0.21 » ; on cale W_GATE sur l'intention (+0.21), soit
W_GATE = 0.21 / epsilon(2,1).
"""

import bridge_db as bd            # (non utilise directement ; homogeneite)
import snn_engine as se

DT = 0.1


def measure_persist_rate(dt=DT, duration_ms=300.0, w_self=9.0):
    """Taux de fire (Hz) d'un PERSIST auto-entretenu (trigger par 1 pulse)."""
    net = se.Network(dt)
    trig = 100
    p = net.add(se.Neuron(tau_m=10.0, t_ref=2.0, dt=dt))
    net.connect(trig, p, 9.0, delay_ms=0.2, tau_syn=2.0)   # amorce (eps(10,2))
    net.connect(p, p, w_self, delay_ms=0.1, tau_syn=2.0)   # recurrent
    net.inject_spike(trig, 0.2)
    n = 0
    for _ in range(int(duration_ms / dt)):
        if p in net.step():
            n += 1
    return n / (duration_ms / 1000.0)


def measure_vgate_ss(w_pg, rate_hz, dt=DT, duration_ms=300.0):
    """V de repos (tonique) d'un GATE muet alimente par 1 PERSIST."""
    net = se.Network(dt)
    trig = 100
    p = net.add(se.Neuron(tau_m=10.0, t_ref=2.0, dt=dt))
    g = net.add(se.Neuron(tau_m=2.0, t_ref=1.0, dt=dt))
    net.connect(trig, p, 9.0, delay_ms=0.2, tau_syn=2.0)
    net.connect(p, p, 9.0, delay_ms=0.1, tau_syn=2.0)
    net.connect(p, g, w_pg, delay_ms=0.5, tau_syn=20.0)
    net.inject_spike(trig, 0.2)
    vmax = vmin = None
    for k in range(int(duration_ms / dt)):
        net.step()
        t = net.k_step * dt
        if t > duration_ms * 0.5:               # regime etabli
            v = net.neurons[g].v
            vmax = v if vmax is None else max(vmax, v)
            vmin = v if vmin is None else min(vmin, v)
    return 0.5 * (vmax + vmin), vmax - vmin


def calibrate_w_pg(dt=DT, target=0.83):
    """W_PG tel que V_ss(GATE) = target : estimation analytique
    (V_ss ~ rate_ms x W x tau_syn x tau_m) puis correction par mesure."""
    rate_hz = measure_persist_rate(dt)
    w = target / ((rate_hz / 1000.0) * 20.0 * 10.0)
    vss = 0.0
    for _ in range(4):
        vss, ripple = measure_vgate_ss(w, rate_hz, dt)
        if 0.79 <= vss <= 0.87:
            break
        w *= target / max(vss, 1e-6)
    return w, vss, ripple, rate_hz


class GateScanBench:
    """Banc n slots : PERSIST[j] (actifs listes), GATE[j], chaine SCAN."""

    def __init__(self, n_slots, active_slots, dt=DT, warmup_ms=200.0,
                 w_pg=0.052, w_gate=0.8, halt_at_ms=None, run_scan=True):
        self.n = n_slots
        self.dt = dt
        self.warmup = warmup_ms
        net = se.Network(dt)
        self.net = net
        # indices : persist[j] = j ; gate[j] = n+j ; pos[j] = 2n+j
        # ports de trigger persist : 200+j ; port halt : 300
        for j in range(n_slots):
            net.add(se.Neuron(tau_m=10.0, t_ref=2.0, dt=dt))   # persist
        for j in range(n_slots):
            net.add(se.Neuron(tau_m=2.0, t_ref=1.0, dt=dt))    # gate
        for j in range(n_slots):
            net.add(se.Neuron(tau_m=5.0, t_ref=1.0, dt=dt))    # scan pos
        for j in range(n_slots):
            # auto-entretien (tau_syn=2, eq. 12)
            net.connect(j, j, 9.0, delay_ms=0.1, tau_syn=2.0)
            # amorce : port -> persist (W=9, tau_syn=2 : 1.23 > 1)
            net.connect(200 + j, j, 9.0, delay_ms=0.2, tau_syn=2.0)
            # tonique PERSIST -> GATE (tau_syn=20, eq. 13)
            net.connect(j, n_slots + j, w_pg, delay_ms=0.5, tau_syn=20.0)
            # trigger SCAN -> GATE (tau_syn=1, +0.21 vise)
            net.connect(2 * n_slots + j, n_slots + j, w_gate,
                        delay_ms=0.5, tau_syn=1.0)
            if j + 1 < n_slots:
                # chaine SCAN (d=4 ms, cf. question ouverte n°5)
                net.connect(2 * n_slots + j, 2 * n_slots + j + 1,
                            9.0, delay_ms=4.0, tau_syn=1.0)
        # amorce des PERSIST actifs
        for j in active_slots:
            net.inject_spike(200 + j, 0.2)
        # HALT eventuel (§2.9 : W_HALT = -15)
        self.halt_t = halt_at_ms
        if halt_at_ms is not None:
            for j in active_slots:
                net.connect(300, j, -15.0, delay_ms=0.1, tau_syn=1.0)
            net.inject_spike(300, halt_at_ms)
        # depart du SCAN
        self.run_scan = run_scan
        if run_scan:
            net.inject_spike(2 * n_slots, warmup_ms)
        self.active = set(active_slots)

    def run(self, duration_ms=None):
        n_steps = int(((duration_ms or (self.warmup + 120.0)) / self.dt))
        gate_times = {j: [] for j in range(self.n)}
        # pos[0] est declenche par le pulse externe (inject direct) :
        # on l'inscrit au temps connu pour le raster complet
        pos_times = [self.warmup] if self.run_scan else []
        pers_after_halt = 0
        for _ in range(n_steps):
            for idx in self.net.step():
                t = self.net.k_step * self.dt
                if idx < self.n:
                    if self.halt_t is not None and t > self.halt_t:
                        pers_after_halt += 1
                elif idx < 2 * self.n:
                    gate_times[idx - self.n].append(t)
                else:
                    pos_times.append(t)
        return {"gate_times": gate_times, "pos_times": pos_times,
                "pers_after_halt": pers_after_halt}
