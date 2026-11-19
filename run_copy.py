# -*- coding: utf-8 -*-
"""Demo palier 5 : copie de pattern par theta-cycle STDP (§2.8).

1. Identites de seuil du papier avec NOS epsilon (rappel) :
   w_max x eps = 1.10 > 1 (DST fire) ; W_0 x eps = 0.48 < 1 (silence).
2. Fenetre de selectivite : tonique seul < 1, tonique + EPSP(W_0) > 1 ;
   et le contre-test empirique : avec l'I_theta publie (0.5), le pic
   reste < 1 -> leur LTP ne partirait pas (question ouverte n°6).
3. Apprentissage d'un pattern aleatoire (64 canaux, ~moitie actifs) :
   W actifs -> w_max=8, W inactifs -> W_0=3.5.
4. Rappel : DST fire EXACTEMENT sur les canaux actifs, silence ailleurs ;
   un canal inactif force a fire ne declenche pas son DST.
5. Robustesse : 10 patterns aleatoires (graines differentes) -> 100 %.
"""

import random

import snn_engine as se
import copy_stdp as cs


def main():
    print("=" * 64)
    print("PALIER 5 - COPIE STDP ONE-SHOT (§2.8)")
    print("=" * 64)

    eps = se.measure_epsilon(10.0, 2.0)

    # 1. identites de seuil du rappel
    print("  rappel : w_max x eps = %.2f x %.3f = %.2f > 1 (fire) ; "
          % (cs.W_MAX, eps, cs.W_MAX * eps))
    print("           W_0   x eps = %.1f x %.3f = %.2f < 1 (silence)"
          % (cs.W0, eps, cs.W0 * eps))
    assert cs.W_MAX * eps > 1 > cs.W0 * eps

    # 2. fenetre de selectivite + contre-test de l'I_theta publie
    print("  fenêtre de selectivite : I_theta dans (%.2f, 1.0) ; nous : 0.75"
          % (1 - cs.W0 * eps))
    b = cs.CopyBench(n=16, i_theta=0.75)
    v_tonique = b.v_peak_tonic_only()
    print("  tonique seul (I=0.75) : pic V = %.3f < 1 (pas de faux fire)"
          % v_tonique)
    assert v_tonique < 1.0
    b2 = cs.CopyBench(n=16, i_theta=0.5)          # la valeur publiee
    v_publie = b2.v_peak_tonic_only() + cs.W0 * eps   # superposition lineaire
    print("  I_theta publie (0.5) : pic V = tonique %.3f + EPSP %.2f = %.2f"
          " < 1 -> leur LTP ne partirait pas (question ouverte n°6)"
          % (b2.v_peak_tonic_only(), cs.W0 * eps, v_publie))
    assert v_publie < 1.0

    # 3. apprentissage d'un pattern aleatoire
    rng = random.Random(7)
    pattern = set(rng.sample(range(64), 30))
    b = cs.CopyBench(n=64, i_theta=0.75, seed=7)
    b.learn(sorted(pattern))
    w_act = [b.w[k] for k in sorted(pattern)]
    w_inact = [b.w[k] for k in range(64) if k not in pattern]
    print("  apprentissage (30/64 actifs, 6 cycles) : W actifs [%s] "
          "(w_max attendu) ; W inactifs [%s] (W_0 attendu)"
          % ("%.2f..%.2f" % (min(w_act), max(w_act)),
             "%.2f..%.2f" % (min(w_inact), max(w_inact))))
    assert all(w == cs.W_MAX for w in w_act)
    assert all(w == cs.W0 for w in w_inact)

    # 4. rappel exact + selectivite
    fired = b.recall(sorted(pattern))
    ok = sorted(k for k in range(64) if fired[k])
    print("  rappel : DST fires sur %d/%d canaux actifs, silence ailleurs"
          % (len(ok), len(pattern)))
    assert ok == sorted(pattern)
    # un canal inactif force a fire ne doit pas declencher son DST
    inact = [k for k in range(64) if k not in pattern][0]
    b.w[inact] = cs.W0
    fired2 = b.recall([inact])
    assert not fired2[inact]
    print("  canal inactif force (W_0) : DST silencieux au rappel OK")

    # 5. robustesse sur 10 graines
    perfect = 0
    for seed in range(10):
        rng = random.Random(seed)
        pat = set(rng.sample(range(64), rng.randint(10, 50)))
        b = cs.CopyBench(n=64, i_theta=0.75, seed=seed)
        b.learn(sorted(pat))
        f = b.recall(sorted(pat))
        if sorted(k for k in range(64) if f[k]) == sorted(pat):
            perfect += 1
    print("  robustesse : %d/10 patterns reconstruits a 100 %%"
          % perfect)
    assert perfect == 10

    print()
    print("TOUTES LES VERIFICATIONS COPIE STDP SONT VERTES.")


if __name__ == "__main__":
    main()
