# -*- coding: utf-8 -*-
"""Mini-lab, palier 3 : moteur spiking minimal fidele au papier (§2.3).

  - Neurone CUBA-LIF avec solution exponentielle EXACTE (eq. 2 du papier,
    pas d'Euler), periode refractaire, E_L=0, R_m=1, V_th=1 normalise.
  - Synapses : PSC exponentielle (eq. 3) + DELAIS axonaux (buffer de
    file d'attente par pas) ; poids signes (W<0 = inhibition).
  - Calibration : epsilon(tau_m, tau_syn) = pic d'EPSP par unite de
    poids, MESURE sur un neurone test V_th=99 (eq. 4 du papier).

Différence assumée avec le papier : la normalisation exacte de leur PSC
n'est pas spécifiée ; on mesure epsilon avec CE moteur et on calibre les
poids par la même méthode (W = V_cible / (n·epsilon)) — la méthode est
le point important, pas les valeurs absolues.
"""

import math


class Neuron:
    """CUBA-LIF, solution exacte par pas : V <- E_L + (V-E_L)k + I(1-k)."""

    def __init__(self, tau_m=2.0, t_ref=1.0, dt=0.1, v_th=1.0,
                 v_reset=0.0, e_l=0.0):
        self.tau_m, self.t_ref = tau_m, t_ref
        self.dt, self.v_th, self.v_reset, self.e_l = dt, v_th, v_reset, e_l
        self.k_m = math.exp(-dt / tau_m)
        self.v = e_l
        self.ref_until = -1.0
        self.t = 0.0

    def step(self, i=0.0):
        """Un pas de dt ms avec courant total i. True si spike.
        Refractaire « soft » (choix documente, le papier ne specifie pas
        ce detail) : V continue de s'integrer pendant t_ref (plafonne a
        v_th) mais aucun spike ne peut etre emis — sinon les synapses
        recurrentes (self-sustain d'INH/PERSIST) meurent au premier
        spike, leur EPSP arrivant pendant t_ref."""
        refrac = self.t < self.ref_until
        v_new = self.e_l + (self.v - self.e_l) * self.k_m \
            + i * (1.0 - self.k_m)
        if refrac:
            self.v = min(v_new, self.v_th)
            spiked = False
        elif v_new >= self.v_th:
            self.v = self.v_reset
            self.ref_until = self.t + self.t_ref
            spiked = True
        else:
            self.v = v_new
            spiked = False
        self.t += self.dt
        return spiked


class Network:
    """Reseau : neurones + synapses orientees (delai, tau_syn, poids signe).

    Les « ports » (indices >= len(neurons)) sont des sources virtuelles :
    on y injecte des spikes a la main (les populations encodeurs APP/LAM/
    VAR du papier)."""

    def __init__(self, dt=0.1):
        self.dt = dt
        self.neurons = []
        self.synapses = []                # (src, dst, w, delay_steps, tau_syn)
        self.out = {}                     # src -> [index synapses]
        self.g = {}                       # dst -> {tau_syn: courant}
        self.arrivals = {}                # pas -> [(dst, w, tau_syn)]
        self.k_step = 0
        self._k_syn = {}

    def add(self, neuron):
        self.neurons.append(neuron)
        return len(self.neurons) - 1

    def connect(self, src, dst, w, delay_ms, tau_syn):
        self.synapses.append((src, dst, w,
                              int(round(delay_ms / self.dt)), tau_syn))
        self.out.setdefault(src, []).append(len(self.synapses) - 1)

    def inject_spike(self, src, t_ms):
        """Le port/neurone src fire au temps t_ms : programme ses sorties."""
        step = int(round(t_ms / self.dt))
        for si in self.out.get(src, []):
            _s, dst, w, d, tau_syn = self.synapses[si]
            self.arrivals.setdefault(step + d, []).append((dst, w, tau_syn))

    def _decay(self, tau_syn):
        if tau_syn not in self._k_syn:
            self._k_syn[tau_syn] = math.exp(-self.dt / tau_syn)
        return self._k_syn[tau_syn]

    def bulk_run(self, n_steps):
        """n pas de simulation ; renvoie [(temps_ms, idx), ...] des spikes
        (convention k_step apres increment, comme les circuits)."""
        out = []
        for _ in range(n_steps):
            for idx in self.step():
                out.append((self.k_step * self.dt, idx))
        return out

    def step(self):
        """Un pas de simulation. Renvoie la liste des indices qui spikent."""
        for dst in self.g:
            for tau_syn in self.g[dst]:
                self.g[dst][tau_syn] *= self._decay(tau_syn)
        for dst, w, tau_syn in self.arrivals.pop(self.k_step, []):
            self.g.setdefault(dst, {}).setdefault(tau_syn, 0.0)
            self.g[dst][tau_syn] += w
        spikes = []
        for idx, n in enumerate(self.neurons):
            buckets = self.g.get(idx, {})
            if n.step(sum(buckets.values())):
                spikes.append(idx)
        for idx in spikes:
            self.inject_spike(idx, self.k_step * self.dt)
        self.k_step += 1
        return spikes


def measure_epsilon(tau_m, tau_syn, dt=0.1, duration_ms=40.0, w=1.0):
    """epsilon(tau_m, tau_syn) : pic de V pour 1 spike de poids w
    (methode du papier §2.3.2 : neurone test V_th=99, jamais spike)."""
    net = Network(dt)
    src = 0                                   # port virtuel
    post = net.add(Neuron(tau_m=tau_m, v_th=99.0, dt=dt))
    net.connect(src, post, w, delay_ms=0.5, tau_syn=tau_syn)
    net.inject_spike(src, 0.0)
    vmax = 0.0
    for _ in range(int(duration_ms / dt)):
        net.step()
        vmax = max(vmax, net.neurons[post].v)
    return vmax / w


def pair_pulse_sum(dt=0.1, slot_ms=8.0, duration_ms=30.0):
    """Pic max de V (poids unitaires) sur DET (tau_m=2, tau_syn=1) pour la
    geometrie EXACTE de la paire APP@j / LAM@j+1 : pulses sources separes
    d'un slot (8 ms), delais axonaux 8 ms et 0.5 ms => les deux EPSP
    arrivent a DET avec 0.5 ms d'ecart (8j+8 et 8j+8.5)."""
    net = Network(dt)
    a, b = 0, 1                               # ports virtuels
    post = net.add(Neuron(tau_m=2.0, v_th=99.0, dt=dt))
    net.connect(a, post, 1.0, delay_ms=8.0, tau_syn=1.0)
    net.connect(b, post, 1.0, delay_ms=0.5, tau_syn=1.0)
    net.inject_spike(a, 0.0)
    net.inject_spike(b, slot_ms)              # le pulse LAM, un slot apres
    vmax = 0.0
    for _ in range(int(duration_ms / dt)):
        net.step()
        vmax = max(vmax, net.neurons[post].v)
    return vmax
