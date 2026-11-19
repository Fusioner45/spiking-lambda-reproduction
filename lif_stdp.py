# -*- coding: utf-8 -*-
"""Mini-lab, palier 1b : neurone LIF + plasticite STDP pair-based (stdlib).

Modeles (temps en ms, unites arbitraires mais coherentes) :
  - LIF : dv/dt = (v_rest - v)/tau_m + i/c_m ; spike si v >= v_th, reset.
  - Synapse exponentielle : un spike pre ajoute w a un courant qui decroit
    avec tau_syn.
  - STDP en ligne (forme pair-based type Bi & Poo / Song et al.) :
      au spike POST : w += A_plus  * trace_pre    (trace_pre, tau_plus)
      au spike PRE  : w -= A_minus * trace_post   (trace_post, tau_minus)
    Donc pre avant post (delta_t = t_post - t_pre > 0) -> potentialisation,
    post avant pre -> depression.
"""

import math


class LIF:
    """Neurone leaky integrate-and-fire, integration d'Euler explicite."""

    def __init__(self, tau_m=20.0, c_m=1.0, v_rest=-70.0, v_reset=-70.0,
                 v_th=-55.0, dt=0.1):
        self.tau_m, self.c_m = tau_m, c_m
        self.v_rest, self.v_reset, self.v_th = v_rest, v_reset, v_th
        self.dt = dt
        self.v = v_rest

    def step(self, i=0.0):
        """Un pas de dt ms avec courant total i. True si spike sur ce pas."""
        self.v += self.dt * ((self.v_rest - self.v) / self.tau_m + i / self.c_m)
        if self.v >= self.v_th:
            self.v = self.v_reset
            return True
        return False


def lif_period(i, tau_m=20.0, c_m=1.0, v_rest=-70.0, v_th=-55.0):
    """Periode theorique (ms) en tir regulier sous courant constant i
    (depart a v = v_rest). None si le courant ne suffit pas a spiker."""
    v_inf = v_rest + i * tau_m / c_m
    if v_inf <= v_th:
        return None
    return tau_m * math.log((v_inf - v_rest) / (v_inf - v_th))


class StdpSynapse:
    """Synapse pre -> post avec STDP en ligne et courant exponentiel."""

    def __init__(self, w0=0.5, tau_syn=5.0, a_plus=0.01, a_minus=0.01,
                 tau_plus=20.0, tau_minus=20.0, w_min=0.0, w_max=2.0,
                 dt=0.1):
        self.w = w0
        self.a_plus, self.a_minus = a_plus, a_minus
        self.w_min, self.w_max = w_min, w_max
        self.i_syn = 0.0
        self.trace_pre = 0.0
        self.trace_post = 0.0
        # facteurs de decay par pas
        self.k_syn = math.exp(-dt / tau_syn)
        self.k_pre = math.exp(-dt / tau_plus)
        self.k_post = math.exp(-dt / tau_minus)

    def tick(self, pre_spike=False):
        """Un pas cote pre : decay des traces/courant, injection de w si
        spike pre, depression eventuelle. Renvoie le courant synaptique
        a ajouter au courant externe du pas."""
        self.i_syn *= self.k_syn
        self.trace_pre *= self.k_pre
        self.trace_post *= self.k_post
        if pre_spike:
            self.trace_pre = 1.0
            self.i_syn += self.w
            self.w -= self.a_minus * self.trace_post
            self.w = min(max(self.w, self.w_min), self.w_max)
        return self.i_syn

    def on_post(self):
        """A appeler au pas ou le neurone post vient de spiker (apres
        avoir eteinti le pas) : potentiation selon la trace pre."""
        self.trace_post = 1.0
        self.w += self.a_plus * self.trace_pre
        self.w = min(max(self.w, self.w_min), self.w_max)


def stdp_window(delta_t, a_plus=0.01, a_minus=0.01, tau_plus=20.0,
                tau_minus=20.0):
    """delta_w theorique de la fenetre STDP pour un pair isole,
    delta_t = t_post - t_pre en ms."""
    if delta_t > 0:
        return a_plus * math.exp(-delta_t / tau_plus)
    if delta_t < 0:
        return -a_minus * math.exp(delta_t / tau_minus)
    return 0.0


def run_stdp_protocol(n_cycles=5, post_offset_ms=2.0, pre_period_ms=20.0,
                      i_pulse=20.0, pulse_ms=1.0, w0=0.5, dt=0.1):
    """Protocole classique : pre spike periodique, et le post est force
    de spiker a post_offset_ms de chaque pre (avant si negatif) grace a un
    pulse de courant externe bref (latence du pulse ~ 0.8 ms avec i=20).
    Renvoie (w_initial, w_final, liste des delta_t observes en ms)."""
    post = LIF(dt=dt)
    syn = StdpSynapse(dt=dt, w0=w0)
    w_init = syn.w
    pre_times = [pre_period_ms * k for k in range(1, n_cycles + 1)]
    pulse_starts = [p + post_offset_ms - 0.8 for p in pre_times]
    post_times = []
    for k in range(int((pre_times[-1] + pre_period_ms) / dt)):
        t = k * dt
        pre = any(abs(t - p) < 1e-6 for p in pre_times)
        in_pulse = any(ps - 1e-6 <= t < ps + pulse_ms - 1e-6
                       for ps in pulse_starts)
        i_syn = syn.tick(pre_spike=pre)
        if post.step(i=(i_pulse if in_pulse else 0.0) + i_syn):
            post_times.append(t)
            syn.on_post()
    # appariement pour le rapport : le spike post le plus proche de
    # p + offset (fenetre de 5 ms)
    dts = []
    for p in pre_times:
        cand = [q for q in post_times if abs(q - p - post_offset_ms) < 5.0]
        if cand:
            dts.append(min(cand, key=lambda q: abs(q - p - post_offset_ms)) - p)
    return w_init, syn.w, dts
