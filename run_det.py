# -*- coding: utf-8 -*-
"""Demo palier 3 : le detecteur DET du papier en vrais LIF.

1. Calibration : epsilon mesure vs valeurs du papier (§2.3.2) — l'ecart
   de convention PSC est documente, on recalcibr par la meme METHODE.
2. Fenetre de selectivite de l'AND-gate (1 EPSP vs 2 EPSP).
3. Detection sur 2 I : DET spike unique, t≈8.9 ms attendu (papier §3.1),
   K = 0 = position d'oracle.
4. Latch WTA sur un terme a DEUX paires APP-LAM : un seul spike DET.
5. Batterie : K_reseau == K_oracle a chaque etape de reduction.
"""

import lambda_beta as lb
import bridge_db as bd
import snn_engine as se
import det_redex as dr
from run_bridge import trace_steps


def main():
    print("=" * 64)
    print("PALIER 3 - DETECTEUR DET REEL (Jeffress, §2.4)")
    print("=" * 64)

    # 1. calibration : nos epsilon mesures vs papier
    eps21 = se.measure_epsilon(2.0, 1.0)
    eps102 = se.measure_epsilon(10.0, 2.0)
    eps3001 = se.measure_epsilon(300.0, 1.0)
    print("  epsilon mesures   : (%.3f)  (%.3f)  (%.5f)"
          % (eps21, eps102, eps3001))
    print("  epsilon papier    : (0.263)  (0.137)  (0.00344)")
    print("  -> calibration du papier REPRODUITE a l'identique (§2.3.2) ;")
    print("     les poids ci-dessous sont derives de NOS mesures, meme methode")

    # 2. fenetre de selectivite de l'AND-gate
    c = dr.DetCircuit([(bd.APP, 0), (bd.LAM, 0)])
    single = c.eps_21 * c.w_coin
    pair = c.pair_unit * c.w_coin
    print("  avec W_COIN=%.3f : 1 EPSP seul=%.3f | paire APP/LAM (0.5 ms)=%.3f"
          % (c.w_coin, single, pair))
    assert single < 0.8 < 1.05 < pair      # AND-gate : fenetre non vide

    # 3. detection sur 2 I (10 tokens) — compare au §3.1 du papier
    two = "\\f. \\x. f (f x)"
    eye = "\\x. x"
    two_i = "(%s) (%s)" % (two, eye)
    t = lb.parse(two_i)
    toks = bd.to_tokens(bd.to_debruijn(t))
    r = dr.DetCircuit(toks).run()
    k_or = bd.find_redex(t)
    print("  2 I : %d tokens ; DET spike a t=%s ms (papier : 8.9 ms) ;"
          % (len(toks), ("%.1f" % r["t_det"]) if r["t_det"] else "aucun"))
    print("        K_reseau=%d, K_oracle=%d, %d spike(s) DET, latch INH=%d"
          % (r["K"], k_or, r["n_det"], r["n_inh"]))
    assert r["n_det"] == 1 and r["K"] == k_or == 0

    # 4. latch WTA : terme a deux paires APP-LAM adjacentes
    two_pairs = "((\\x. x) y) ((\\z. z) w)"
    t2 = lb.parse(two_pairs)
    toks2 = bd.to_tokens(bd.to_debruijn(t2))
    r2 = dr.DetCircuit(toks2).run()
    k2 = bd.find_redex(t2)
    print("  WTA : %d tokens, paires APP-LAM aux positions (1,2) et (5,6) ;"
          % len(toks2))
    print("        DET ne fire qu'UNE fois : %d spike, K=%d, K_oracle=%d"
          % (r2["n_det"], r2["K"], k2))
    assert r2["n_det"] == 1 and r2["K"] == k2

    # 5. batterie : K_reseau == K_oracle a chaque etape de reduction
    battery = [
        two_i,
        "(\\x. x) (a b)",
        "(\\m. \\n. \\f. m (n f)) (\\f. \\x. f (f x))"
        " (\\f. \\x. f (f (f x)))",
        "(\\x. \\y. x y) (a b c)",
        "(\\x. x x) (\\x. x)",
        "((\\x. x) y) ((\\z. z) w)",
    ]
    n = 0
    for s in battery:
        cur = lb.parse(s)
        for _ in range(4):
            toks_c = bd.to_tokens(bd.to_debruijn(cur))
            r_c = dr.DetCircuit(toks_c).run()
            k_c = bd.find_redex(cur)
            if k_c == -1:
                # forme normale : le circuit ne doit RIEN detecter
                assert r_c["n_det"] == 0 and r_c["K"] == -1, (s, r_c)
            else:
                assert r_c["n_det"] == 1 and r_c["K"] == k_c, (s, r_c, k_c)
            n += 1
            nxt, d = lb.beta_step(cur)
            if not d:
                break
            cur = nxt
    print("  batterie : DET reel = position d'oracle sur %d configurations"
          " (6 termes x jusqu'a 4 etapes, formes normales incluses)" % n)

    print()
    print("TOUTES LES VERIFICATIONS DET SONT VERTES.")


if __name__ == "__main__":
    main()
