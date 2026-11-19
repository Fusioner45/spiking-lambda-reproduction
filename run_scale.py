# -*- coding: utf-8 -*-
"""Bench de scale : la boucle fermee sur des termes qui grossissent.

Famille : chaines de I — I (I (I ...)) — P identites imbriquees :
  * tokens = 2P+1, etapes = P, NF = I ;
  * corps/arguments de chaque redex restent minuscules (1-3 tokens) ->
    les circuits restent dans l'enveloppe validee du papier (§2.5 : le
    compteur de balance tau_m=300 derive sur les longs sous-termes —
    finding n°8, cf. journal) ;
  * la taille du terme fait scaler le SCAN (L*8 ms), la liaison et la
    copie -> c'est bien le cout d'architecture qu'on mesure.

Mode production (sans oracle par etape) ; NF = I verifiee ; traces
identiques entre moteurs.
"""

import time

import lambda_beta as lb
import orchestrate as orc
import snn_core as sc


def church_str(n):
    """Church n = lam a. lam b. a (a (... b)) — n applications de a."""
    return "(\\a. \\b. " + "a (" * (n - 1) + "a b" + ")" * (n - 1) + ")"


def mult_term(n):
    return "(\\m. \\n. \\f. m (n f)) %s %s" % (church_str(n),
                                               church_str(n))


def chain_term(p):
    """I (I (I ... I)) avec p identites."""
    s = "(\\x. x)"
    for _ in range(p - 1):
        s = "(\\x. x) " + s
    return s


def run_one(p, net_factory, copy_engine):
    loop = orc.ClosedLoop(verbose=False, net_factory=net_factory,
                          copy_engine=copy_engine, production=True)
    t0 = time.perf_counter()
    nf, trace, _ = loop.run(chain_term(p), max_steps=400)
    dt = time.perf_counter() - t0
    assert lb.to_str(nf) == "\\x. x", (p, lb.to_str(nf))
    return trace, dt


def run_mult55(net_factory, copy_engine, intg_tau_m=1000.0):
    """mult 5 5 : hors enveloppe INTG en tau_m=300 (finding n°8) —
    le fix tau_m=1000 debloque la boucle fermee."""
    loop = orc.ClosedLoop(verbose=False, net_factory=net_factory,
                          copy_engine=copy_engine, production=True,
                          intg_tau_m=intg_tau_m)
    t0 = time.perf_counter()
    nf, trace, _ = loop.run(mult_term(5), max_steps=100)
    dt = time.perf_counter() - t0
    k = lb.church_to_int(nf)
    assert k == 25, (k, lb.to_str(nf))
    return trace, dt


def main():
    print("=" * 64)
    print("SCALE - BOUCLE FERMEE SUR DES CHAINES DE I (mode production)")
    print("=" * 64)
    rows = []
    for p in [5, 25, 50, 100, 150]:
        tr_p, t_py = run_one(p, None, "py")
        tr_c, t_c = run_one(p, sc.CNetwork, "c")
        assert tr_p == tr_c
        rows.append((p, tr_p[0], max(tr_p), len(tr_p) - 1, t_py, t_c))
        print("  P=%3d : tokens %3d -> max %3d, %3d etapes | "
              "Py %8.0f ms | C %8.0f ms | x%.1f"
              % (p, tr_p[0], max(tr_p), len(tr_p) - 1,
                 1000 * t_py, 1000 * t_c, t_py / t_c))
    print()
    tr_p, t_py = run_mult55(None, "py")
    tr_c, t_c = run_mult55(sc.CNetwork, "c")
    assert tr_p == tr_c
    print("  mult 5 5 (tau_m INTG=1000, fix finding n°8) : tokens %d -> "
          "max %d, %d etapes | Py %.0f ms | C %.0f ms | x%.1f"
          % (tr_p[0], max(tr_p), len(tr_p) - 1, 1000 * t_py, 1000 * t_c,
             t_py / t_c))
    rows.append(("m55", tr_p[0], max(tr_p), len(tr_p) - 1, t_py, t_c))
    print()
    with open("bench_scale_results.md", "w", encoding="utf-8") as f:
        f.write("# Bench scale — boucle fermée, chaînes de I\n\n")
        f.write("| P | tokens init | tokens max | étapes | Python ms | C ms | "
                "speedup |\n")
        f.write("|---|---|---|---|---|---|---|\n")
        for (p, t0, tm, st, tp, tc) in rows:
            f.write("| %s | %d | %d | %d | %.0f | %.0f | %.1f |\n"
                    % (p, t0, tm, st, 1000 * tp, 1000 * tc, tp / tc))
        f.write("\nMode production (sans oracle par étape) ; NF = I vérifiée ;"
                " traces identiques entre moteurs. Famille choisie pour "
                "rester dans l'enveloppe du compteur de balance (finding "
                "n°8 : dérive du discharge sur les longs sous-termes).\n")
    print("resultats ecrits dans bench_scale_results.md")


if __name__ == "__main__":
    main()
