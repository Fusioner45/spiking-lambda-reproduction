# -*- coding: utf-8 -*-
"""Demo item 4 : moteur C + test differentiel contre le moteur Python.

1. Calibration differentielle : epsilon mesures par le moteur C vs le
   moteur Python (5 paires tau) — ecart < 1e-12 attendu.
2. Spike-a-spike : le circuit DET du papier (§2.4) cablé avec les MEMES
   poids calibres chez Python, simule par les deux moteurs sur 2 I —
   memes temps de spike DET/INH au pas pres.
3. Benchmark : iterations de mesure d'epsilon Python vs C.
"""

import time

import snn_engine as se
import det_redex as dr
import bridge_db as bd
import lambda_beta as lb
import snn_core as sc

two = "\\f. \\x. f (f x)"
eye = "\\x. x"


def main():
    print("=" * 64)
    print("ITEM 4 - MOTEUR C + TEST DIFFERENTIEL")
    print("=" * 64)

    # 1. calibration differentielle
    print("  epsilon : C vs Python (ecart max < 1e-12 attendu)")
    worst = 0.0
    for (tau_m, tau_syn) in [(2.0, 1.0), (10.0, 2.0), (300.0, 1.0),
                             (5.0, 1.0), (40.0, 2.0)]:
        e_py = se.measure_epsilon(tau_m, tau_syn)
        e_c = sc.c_measure_epsilon(sc.CNetwork, tau_m, tau_syn)
        d = abs(e_py - e_c)
        worst = max(worst, d)
        print("    epsilon(%5.1f, %d) : C=%.12f  Py=%.12f  (d=%.2e)"
              % (tau_m, tau_syn, e_c, e_py, d))
        assert d < 1e-12
    print("    -> calibration du papier reproduite par le moteur C "
          "(ecart max %.2e)" % worst)

    # 2. DET spike-a-spike sur 2 I
    t = lb.parse("(%s) (%s)" % (two, eye))
    toks = bd.to_tokens(bd.to_debruijn(t))
    c_py = dr.DetCircuit(toks)
    r_py = c_py.run()
    n_steps = int((len(toks) * 8.0 + 40.0) / 0.1)

    net = sc.CNetwork(0.1, n_steps_alloc=n_steps + 256)
    port_app, port_lam = 100, 101
    det = net.add(2.0, 1.0)
    inh = net.add(2.0, 1.0)
    net.connect(port_app, det, c_py.w_coin, 8.0, 1)
    net.connect(port_lam, det, c_py.w_coin, 0.5, 1)
    net.connect(det, inh, 5.0, 0.2, 1)
    net.connect(inh, det, -20.0, 0.1, 1)
    net.connect(inh, inh, c_py.w_self_inh, 0.1, 2)
    for j, (tid, _d) in enumerate(toks):
        if tid == bd.APP:
            net.inject(port_app, 8.0 * j)
        elif tid == bd.LAM:
            net.inject(port_lam, 8.0 * j)
    net.alloc_I()
    net.run(n_steps)

    sp = net.spikes()
    det_c = [tms for tms, idx in sp if idx == det]
    inh_c = [tms for tms, idx in sp if idx == inh]
    print("  DET 2 I : C %d spike(s) DET a %s ms / %d spikes INH"
          % (len(det_c), ["%.2f" % x for x in det_c], len(inh_c)))
    print("           Py %d spike(s) DET a %s ms / %d spikes INH"
          % (len(r_py["det_times"]), ["%.2f" % x for x in r_py["det_times"]],
             r_py["n_inh"]))
    assert len(det_c) == len(r_py["det_times"])
    for a, b in zip(det_c, r_py["det_times"]):
        assert abs(a - b) < 1e-9, (a, b)
    assert len(inh_c) == r_py["n_inh"]
    k_c = int(det_c[0] // 8.0) - 1
    assert k_c == r_py["K"]
    print("           -> memes spikes au pas pres, K=%d identique" % k_c)

    # 3. benchmark : iterations de mesure d'epsilon
    n_iter = 300
    t0 = time.perf_counter()
    for _ in range(n_iter):
        se.measure_epsilon(2.0, 1.0)
    t_py = time.perf_counter() - t0
    t0 = time.perf_counter()
    for _ in range(n_iter):
        sc.c_measure_epsilon(sc.CNetwork, 2.0, 1.0)
    t_c = time.perf_counter() - t0
    print("  benchmark (%d mesures d'epsilon, construction+run) : "
          "Python %.1f ms/iter, C %.2f ms/iter -> x%.0f"
          % (n_iter, 1000 * t_py / n_iter, 1000 * t_c / n_iter,
             t_py / t_c))
    assert t_py > 5 * t_c

    print()
    print("MOTEUR C VALIDÉ : MEMES SPIKES AU PAS PRES, PYTHON RESTE LE JUGE.")


if __name__ == "__main__":
    main()
