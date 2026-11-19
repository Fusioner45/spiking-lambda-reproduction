# -*- coding: utf-8 -*-
"""Demo palier 5 : PERSIST / GATE / SCAN (§2.9-2.10).

1. Le diagnostic « critique » du papier reproduit : PERSIST avec synapse
   recurrente tau_syn=1 MEURT (9x eps(10,1)=0.73<1), tau_syn=2 tient
   (9x eps(10,2)=1.23>1).
2. HALT (W=-15) eteint bien le PERSIST.
3. SCAN seul : un fire par slot, ordre strict, ISI mesure (~4.9 ms
   attendus cf. §2.10.1, avec d=4 ms cf. question ouverte n°5).
4. W_PG calibre par mesure : V_ss du GATE dans la fenetre [0.79, 0.87].
5. AND fonctionnel : PERSIST actifs sur {2,5} -> GATE fire aux slots
   2 et 5 au passage du SCAN, silence ailleurs ; sans SCAN, aucun GATE
   ne fire spontanement.
"""

import snn_engine as se
import persist_gate as pg


def main():
    print("=" * 64)
    print("PALIER 5 - PERSIST / GATE / SCAN (§2.9-2.10)")
    print("=" * 64)

    # 1. le diagnostic « critique » du §2.9
    e101 = se.measure_epsilon(10.0, 1.0)
    e102 = se.measure_epsilon(10.0, 2.0)
    print("  epsilon(10,1)=%.3f -> 9x0.081=%.2f<1 ; "
          "epsilon(10,2)=%.3f -> 9x0.137=%.2f>1" % (e101, 9 * e101, e102, 9 * e102))
    rate1 = pg.measure_persist_rate(w_self=9.0)      # attention : tau_syn=2
    # variante tau_syn=1 : re-mesure avec la mauvaise constante, a la main
    net = se.Network(pg.DT)
    trig = 100
    p = net.add(se.Neuron(tau_m=10.0, t_ref=2.0, dt=pg.DT))
    net.connect(trig, p, 9.0, delay_ms=0.2, tau_syn=2.0)
    net.connect(p, p, 9.0, delay_ms=0.1, tau_syn=1.0)   # le « critique »
    net.inject_spike(trig, 0.2)
    n_bad = 0
    for _ in range(int(300.0 / pg.DT)):
        if p in net.step():
            n_bad += 1
    print("  PERSIST 300 ms : tau_syn=2 -> %d spikes (tient) ; "
          "tau_syn=1 -> %d spikes (meurt) : diagnostic du papier reproduit"
          % (round(rate1 * 0.3), n_bad))
    assert n_bad <= 3 and round(rate1 * 0.3) >= 40

    # 2. HALT
    bench = pg.GateScanBench(3, [0, 1, 2], halt_at_ms=100.0, run_scan=False,
                             w_pg=0.052)
    r = bench.run(duration_ms=150.0)
    print("  HALT a 100 ms : spikes PERSIST apres HALT = %d (attendu 0)"
          % r["pers_after_halt"])
    assert r["pers_after_halt"] == 0

    # 3. SCAN seul : un fire par slot, ordre strict, ISI
    bench = pg.GateScanBench(10, [], run_scan=True, w_pg=0.052)
    r = bench.run()
    pos = r["pos_times"]
    isi = [pos[i + 1] - pos[i] for i in range(len(pos) - 1)]
    print("  SCAN : %d pos fires (attendu 10), ISI moyen %.2f ms "
          "(papier : ~4.9)" % (len(pos), sum(isi) / len(isi)))
    assert len(pos) == 10 and pos == sorted(pos)
    assert 3.5 < sum(isi) / len(isi) < 7.0

    # 4. calibration de W_PG
    w_pg, vss, ripple, rate = pg.calibrate_w_pg()
    print("  PERSIST rate=%.0f Hz ; W_PG=%.4f calibre -> V_ss=%.3f "
          "(ripple %.3f), fenetre [0.79, 0.87]" % (rate, w_pg, vss, ripple))
    assert 0.79 <= vss <= 0.87

    # 5. AND fonctionnel : actifs {2,5}, SCAN -> GATE fire aux slots 2 et 5
    bench = pg.GateScanBench(10, [2, 5], run_scan=True, w_pg=w_pg,
                             w_gate=0.8)
    r = bench.run()
    fired = sorted(j for j in range(10) if r["gate_times"][j])
    print("  AND : PERSIST actifs sur {2, 5} -> GATE fires aux slots %s"
          % fired)
    assert fired == [2, 5]
    assert all(len(r["gate_times"][j]) == 1 for j in fired)
    # et sans SCAN : aucun GATE ne fire spontanement
    bench = pg.GateScanBench(10, [2, 5], run_scan=False, w_pg=w_pg)
    r = bench.run()
    spont = [j for j in range(10) if r["gate_times"][j]]
    print("  sans SCAN : GATE fires spontanes = %s (attendu [])" % spont)
    assert spont == []

    print()
    print("TOUTES LES VERIFICATIONS PERSIST/GATE/SCAN SONT VERTES.")


if __name__ == "__main__":
    main()
