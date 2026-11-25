# -*- coding: utf-8 -*-
"""Demo item 4 : moteur C + test differentiel contre le moteur Python.

1. Calibration differentielle : epsilon mesures par le moteur C vs le
   moteur Python (5 paires tau) — ecart < 1e-12 attendu.
2. Spike-a-spike : le circuit DET du papier (§2.4) cablé avec les MEMES
   poids calibres chez Python, simule par les deux moteurs sur 2 I —
   memes temps de spike DET/INH au pas pres.
3. Benchmark : iterations de mesure d'epsilon Python vs C.
4. Limites du coeur (audit session 44) : le C est un miroir du Python
   aussi aux BORNES — horizon, ports, neurones ajoutes en cours de route,
   indices invalides, banc de copie au-dela de son allocation, reset.
"""

import ctypes
import time

import snn_engine as se
import det_redex as dr
import bridge_db as bd
import lambda_beta as lb
import snn_core as sc
from snn_core import _LIB

two = "\\f. \\x. f (f x)"
eye = "\\x. x"

DT = 0.1
W_IN, TAU_M = 30.0, 10.0


def limits_of_the_core():
    """Bloc 4 : chaque cas etait un defaut du noyau C (session 44) :
    arret MUET de snn_run a l'horizon alloue (10 s par defaut) et
    arrivees ignorees au-dela ; synapse d'un port >= 4096 morte en
    silence ; neurones ajoutes apres un run (ecriture hors tampon au-dela
    de la capacite du premier pas) ; dst inexistant accepte (hors tampon
    au run) ; banc de copie tronque au 2e rappel, push sans controle ;
    reset qui gardait l'ordre des buckets du run precedent.

    Convention : le neurone 0 est un ANCRAGE sans entree (il ne tire
    jamais) ; ses sorties servent de port d'injection — l'indice 0 est
    sinon le neurone d'indice 0 lui-meme (piege : auto-excitation)."""
    print("  limites du coeur : le C suit le Python aux bornes")

    def duo(alloc):
        py = se.Network(DT)
        c = sc.CNetwork(DT, alloc)
        py.add(se.Neuron(tau_m=TAU_M, t_ref=1.0, dt=DT))     # ancrage
        c.add(TAU_M, 1.0)
        return py, c

    def one_neuron(alloc):
        """(py, c, n_py, n_c) : un neurone pendu a l'ancrage 0."""
        py, c = duo(alloc)
        n_py = py.add(se.Neuron(tau_m=TAU_M, t_ref=1.0, dt=DT))
        n_c = c.add(TAU_M, 1.0)
        assert n_py == n_c == 1
        py.connect(0, n_py, W_IN, delay_ms=0.5, tau_syn=1.0)
        c.connect(0, n_c, W_IN, 0.5, 1)
        return py, c, n_py, n_c

    # 4a. horizon : alloue pour 1000 pas, on en simule 5000, avec un
    #     spike programme AU-DELA de l'horizon (pas 1500)
    py, c, _n_py, _n_c = one_neuron(1000)
    py.inject_spike(0, 150.0)
    c.inject(0, 150.0)
    sp_py, sp_c = py.bulk_run(5000), c.bulk_run(5000)
    assert (c.k_step, py.k_step) == (5000, 5000), (c.k_step, py.k_step)
    assert sp_c == sp_py and sp_c, (sp_c, sp_py)
    assert sp_c[0][0] > 100.0                    # au-dela de l'horizon
    print("    horizon : 5000 pas sur un reseau alloue pour 1000, spike"
          " au pas 1500 -> %d feux identiques au Python, le premier a"
          " %.1f ms (avant : arret muet au pas 1000)" % (len(sp_c),
                                                         sp_c[0][0]))

    # 4b. port source au-dela de 4096 (avant : synapse jamais declenchee)
    py, c, _n_py, _n_c = one_neuron(1000)
    py.connect(9000, 1, W_IN, delay_ms=0.5, tau_syn=1.0)
    c.connect(9000, 1, W_IN, 0.5, 1)
    py.inject_spike(9000, 5.0)
    c.inject(9000, 5.0)
    sp_py, sp_c = py.bulk_run(120), c.bulk_run(120)
    assert sp_c == sp_py and sp_c, (sp_c, sp_py)
    print("    port source 9000 : %d feux identiques au Python"
          % len(sp_c))

    # 4c. neurones ajoutes APRES un premier run (une pile construite au
    #     fil d'un scan) : 100 neurones en etalement depuis le neurone 1
    #     et l'ancrage, deux taux synaptiques par destination
    py, c, n_py, n_c = one_neuron(1000)
    py.bulk_run(50)
    c.bulk_run(50)
    for k in range(100):
        q = py.add(se.Neuron(tau_m=TAU_M, t_ref=1.0, dt=DT))
        r = c.add(TAU_M, 1.0)
        assert q == r == 2 + k
        py.connect(n_py, q, 9.0, delay_ms=0.5, tau_syn=2.0)
        py.connect(0, q, 9.0, delay_ms=0.5, tau_syn=1.0)
        c.connect(n_c, r, 9.0, 0.5, 2)
        c.connect(0, r, 9.0, 0.5, 1)
    py.inject_spike(0, 10.0)
    c.inject(0, 10.0)
    sp_py, sp_c = py.bulk_run(400), c.bulk_run(400)
    assert sp_c == sp_py and len(sp_c) > 100, (len(sp_c), len(sp_py))
    print("    100 neurones ajoutes apres un run : %d feux identiques au"
          " Python (avant : ecriture hors tampon au-dela de 64 neurones)"
          % len(sp_c))

    # 4d. connexions et lectures INVALIDES : refus visible, jamais muet
    py, c, _n_py, _n_c = one_neuron(1000)
    for bad in ((0, 7, 1.0, 0.5, 1), (0, 1, 1.0, -0.5, 1),
                (0, 1, 1.0, 0.5, 0)):
        try:
            c.connect(*bad)
            raised = False
        except ValueError:
            raised = True
        assert raised, bad
    assert c.v(99) != c.v(99) and c.vmax(-1) != c.vmax(-1)   # NaN
    st, ix = ctypes.c_int(), ctypes.c_int()
    _LIB.snn_spike(c.h, 0, ctypes.byref(st), ctypes.byref(ix))
    assert (st.value, ix.value) == (-1, -1)
    print("    dst inexistant / delai negatif / tau nul : ValueError ;"
          " lecture hors indice : NaN / -1")

    # 4e. banc de copie AU-DELA de son allocation (defaut : 1 learn +
    #     1 rappel = 1020 pas sur 1048) : trois rappels
    import copy_stdp as cs
    pat = [1, 4, 7, 10, 20, 31]
    b_py = cs.CopyBench(n=32, i_theta=0.75, seed=3)
    b_c = sc.CopyC(n=32, i_theta=0.75)
    b_py.learn(pat)
    b_c.learn(pat)
    n_fires = 0
    for _r in range(3):
        f_py = b_py.recall(pat)
        f_c = b_c.recall(pat)
        assert b_c.weights() == b_py.w, "poids differents"
        assert {k: v for k, v in f_c.items() if v} == \
            {k: v for k, v in f_py.items() if v}, "rappels differents"
        n_fires += sum(len(v) for v in f_c.values())
    assert n_fires == 3 * len(pat)
    print("    copie : 1 learn + 3 rappels (1620 pas sur 1048 alloues) :"
          " poids bit-exacts, %d feux de rappel identiques (avant :"
          " troncature muet du 2e rappel)" % n_fires)

    # 4f. reset() = reseau NEUF : l'ordre d'insertion des taux (qui fixe
    #     l'ordre de sommation des courants) repart a zero. Avant le
    #     reset, le taux 2 arrive le premier ; apres, le taux 1.
    def c_scenario(pre_run):
        net = sc.CNetwork(DT, 1000)
        net.add(TAU_M, 1.0)                          # ancrage
        n = net.add(TAU_M, 1.0)
        net.connect(0, n, 9.0, 0.5, 1)
        net.connect(2, n, 9.0, 0.5, 2)
        if pre_run:
            net.inject(2, 0.0)
            net.run(60)
            net.reset()
        net.inject(0, 1.0)
        net.inject(2, 3.0)
        return net.bulk_run(400), net.vmax(n)

    fresh = c_scenario(False)
    reused = c_scenario(True)
    assert fresh[0], "le scenario doit faire tirer le neurone"
    assert reused == fresh, (fresh, reused)
    print("    reset() apres un run : spikes et Vmax == reseau neuf")


def main():
    print("=" * 64)
    print("ITEM 4 - MOTEUR C + TEST DIFFERENTIEL")
    print("=" * 64)

    # 0. regression (revue externe) : reset() AVANT tout run() ne doit
    #    pas planter (bucket alloue seulement au premier run)
    _net = sc.CNetwork(dt=0.1)
    _net.add(2.0, 1.0)
    _net.reset()                           # bucket NULL avant le fix
    _net.run(10)
    print("  reset() avant run() : survecu, puis run() nominal OK")

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

    # 4. limites du coeur (audit session 44)
    limits_of_the_core()

    print()
    print("MOTEUR C VALIDÉ : MEMES SPIKES AU PAS PRES, PYTHON RESTE LE JUGE.")


if __name__ == "__main__":
    main()
