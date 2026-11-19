# -*- coding: utf-8 -*-
"""snn_core.py — wrapper ctypes du coeur C (item 4).

Offre la meme API que snn_engine.Network (sous-ensemble utilise par les
circuits) pour permettre le test differentiel : meme cablage, memes
poids calibres, memes pulses -> memes spikes au pas pres.
"""

import ctypes
import os

_DIR = os.path.dirname(os.path.abspath(__file__))
_LIB = None
for _name in ("snn_core.dll", "libsnn_core.so", "snn_core.so"):
    _p = os.path.join(_DIR, _name)
    if os.path.exists(_p):
        _LIB = ctypes.CDLL(_p)
        break
if _LIB is None:
    raise ImportError(
        "snn_core not compiled. Run: "
        "gcc -O2 -shared -fPIC -o libsnn_core.so snn_core.c -lm  "
        "(Linux/macOS) or gcc -O2 -shared -o snn_core.dll snn_core.c -lm "
        "(Windows).")
_LIB.snn_create.restype = ctypes.c_void_p
_LIB.snn_create.argtypes = [ctypes.c_double, ctypes.c_int]
_LIB.snn_add_neuron.restype = ctypes.c_int
_LIB.snn_add_neuron.argtypes = [ctypes.c_void_p, ctypes.c_double,
                                ctypes.c_double]
_LIB.snn_connect.restype = ctypes.c_int
_LIB.snn_connect.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int,
                             ctypes.c_double, ctypes.c_int, ctypes.c_int]
_LIB.snn_inject.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int]
_LIB.snn_run.argtypes = [ctypes.c_void_p, ctypes.c_int]
_LIB.snn_reset.argtypes = [ctypes.c_void_p]
_LIB.snn_n_spikes.restype = ctypes.c_int
_LIB.snn_n_spikes.argtypes = [ctypes.c_void_p]
_LIB.snn_spike.argtypes = [ctypes.c_void_p, ctypes.c_int,
                           ctypes.POINTER(ctypes.c_int),
                           ctypes.POINTER(ctypes.c_int)]
_LIB.snn_v.restype = ctypes.c_double
_LIB.snn_v.argtypes = [ctypes.c_void_p, ctypes.c_int]
_LIB.snn_k_step.restype = ctypes.c_int
_LIB.snn_k_step.argtypes = [ctypes.c_void_p]
_LIB.cp_create.restype = ctypes.c_void_p
_LIB.cp_create.argtypes = [ctypes.c_int, ctypes.c_double, ctypes.c_double,
                            ctypes.c_int]
_LIB.cp_schedule_src.argtypes = [ctypes.c_void_p, ctypes.c_int,
                                  ctypes.c_int]
_LIB.cp_run.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int]
_LIB.cp_reset.argtypes = [ctypes.c_void_p]
_LIB.cp_weight.restype = ctypes.c_double
_LIB.cp_weight.argtypes = [ctypes.c_void_p, ctypes.c_int]
_LIB.cp_n_spikes.restype = ctypes.c_int
_LIB.cp_n_spikes.argtypes = [ctypes.c_void_p]
_LIB.cp_spike.argtypes = [ctypes.c_void_p, ctypes.c_int,
                           ctypes.POINTER(ctypes.c_int),
                           ctypes.POINTER(ctypes.c_int)]
_LIB.cp_free.argtypes = [ctypes.c_void_p]
_LIB.snn_vmax.restype = ctypes.c_double
_LIB.snn_vmax.argtypes = [ctypes.c_void_p, ctypes.c_int]
_LIB.snn_alloc_I.argtypes = [ctypes.c_void_p]
_LIB.snn_free.argtypes = [ctypes.c_void_p]


class CNetwork:
    """Reseau C. Convention identique a snn_engine : ports virtuels =
    ids hors plage des neurones (>= 4096 interdits)."""

    def __init__(self, dt=0.1, n_steps_alloc=100000):
        self.h = _LIB.snn_create(dt, n_steps_alloc)
        self.dt = dt

    def add(self, tau_m, t_ref=1.0):
        return _LIB.snn_add_neuron(self.h, tau_m, t_ref)

    def connect(self, src, dst, w, delay_ms, tau_syn):
        return _LIB.snn_connect(self.h, src, dst, w,
                                int(round(delay_ms / self.dt)), int(tau_syn))

    def inject(self, src, t_ms):
        _LIB.snn_inject(self.h, src, int(round(t_ms / self.dt)))

    inject_spike = inject          # meme nom que snn_engine.Network

    @property
    def k_step(self):
        return _LIB.snn_k_step(self.h)

    def step(self):
        """Un pas de simulation ; renvoie la liste des idx qui spikent
        (semantique de snn_engine.Network.step)."""
        before = _LIB.snn_n_spikes(self.h)
        _LIB.snn_run(self.h, 1)
        return [idx for (_t, idx) in self.spikes()[before:]]

    def alloc_I(self):
        _LIB.snn_alloc_I(self.h)

    def run(self, n_steps):
        _LIB.snn_run(self.h, n_steps)

    def reset(self):
        _LIB.snn_reset(self.h)

    def bulk_run(self, n_steps):
        """n pas en UN appel ctypes ; renvoie [(temps_ms, idx), ...]
        (convention (pas+1)*dt, alignee sur snn_engine.bulk_run)."""
        _LIB.snn_run(self.h, n_steps)
        return self.spikes()

    def spikes(self):
        """[(temps_ms, idx), ...] — convention Python : k_step APRES
        increment (=(pas+1)*dt), pour l'egalite spike-a-spike."""
        out = []
        n = _LIB.snn_n_spikes(self.h)
        st, idx = ctypes.c_int(), ctypes.c_int()
        for i in range(n):
            _LIB.snn_spike(self.h, i, ctypes.byref(st), ctypes.byref(idx))
            out.append(((st.value + 1) * self.dt, idx.value))
        return out

    def v(self, idx):
        return _LIB.snn_v(self.h, idx)

    def vmax(self, idx):
        return _LIB.snn_vmax(self.h, idx)

    def __del__(self):
        try:
            _LIB.snn_free(self.h)
        except Exception:
            pass


def c_measure_epsilon(net_factory, tau_m, tau_syn, dt=0.1, duration_ms=40.0):
    """epsilon mesure par le moteur C (methode §2.3.2 : neurone test
    V_th=99, 1 spike de poids 1)."""
    net = net_factory(dt, int(duration_ms / dt) + 128)
    post = net.add(tau_m, t_ref=1.0)
    _LIB.snn_connect(net.h, 0, post, 1.0, 5, int(tau_syn))   # port 0 -> delay 0.5 ms
    net.inject(0, 0.0)
    net.alloc_I()
    net.run(int(duration_ms / dt))
    return net.vmax(post)


class CopyC:
    """Banc de copie STDP sur moteur C — miroir de copy_stdp.CopyBench."""

    def __init__(self, n=64, i_theta=0.75, dt=0.1):
        self.n = n
        self.h = _LIB.cp_create(n, i_theta, dt,
                                int(6 * 12.0 / dt) + int(30.0 / dt) + 128)
        self.dt = dt

    def learn(self, pattern, n_cycles=6):
        cycle_steps = int(12.0 / self.dt)
        offset = int(round(cs_offset / self.dt))
        for _c in range(n_cycles):
            for k in pattern:
                _LIB.cp_schedule_src(self.h, k, _c * cycle_steps + offset)
            _LIB.cp_run(self.h, cycle_steps, 1)

    def recall(self, pattern, duration_ms=30.0):
        for k in pattern:
            _LIB.cp_schedule_src(self.h, k, int(round(1.0 / self.dt)))
        _LIB.cp_run(self.h, int(duration_ms / self.dt), 0)
        n = _LIB.cp_n_spikes(self.h)
        st, k = ctypes.c_int(), ctypes.c_int()
        fired = {k2: [] for k2 in range(self.n)}
        for i in range(n):
            _LIB.cp_spike(self.h, i, ctypes.byref(st), ctypes.byref(k))
            fired[k.value].append((st.value + 1) * self.dt)
        return fired

    def weights(self):
        return [_LIB.cp_weight(self.h, k) for k in range(self.n)]

    def reset(self):
        _LIB.cp_reset(self.h)

    def __del__(self):
        try:
            _LIB.cp_free(self.h)
        except Exception:
            pass


cs_offset = 2.0        # SRC_OFFSET_MS de copy_stdp (import cycle evite)
