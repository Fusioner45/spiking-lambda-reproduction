# -*- coding: utf-8 -*-
"""Demo item 2 : le bug variables libres du papier, reproduit puis corrige
par l'encodage a code reserve (7,7).

1. Preuve d'absence de collision du code reserve.
2. Masques : cas buggues (lambda du redex a profondeur 0 + libres) :
   le masque PAPIER marque les libres comme lies (bug §3.3 reproduit),
   le masque FIXE est exact ; cas controles (lambda a profondeur > 0,
   terme ferme) : papier == fix == verite.
3. Tenue au bruit additif 10 % : le fix retombe a ~1-2 % de tirages
   touches (contre 100 % structurels pour le papier a profondeur 0).
"""

import lambda_beta as lb
import bridge_db as bd
import free_vars_fix as fv
from run_bridge import trace_steps

two = "\\f. \\x. f (f x)"
eye = "\\x. x"
two_i = "(%s) (%s)" % (two, eye)


def mask_report(s):
    t = lb.parse(s)
    db = bd.to_debruijn(t)
    d_lam = fv.redex_lam_depth(t)
    rows_p = fv.rows_papier(db)
    rows_f = fv.rows_fix(db)
    lam_self = (d_lam % bd.K_F, (d_lam // bd.K_F) % bd.K_C)
    truth = fv.truth_bound(rows_p, d_lam)
    mask_p = fv.bound_mask_papier(rows_p, lam_self)
    mask_f = fv.bound_mask_papier(rows_f, lam_self)
    return {"s": s, "d_lam": d_lam, "lam_self": lam_self,
            "truth": truth, "papier": mask_p, "fix": mask_f}


def main():
    print("=" * 64)
    print("ITEM 2 - FIX DES VARIABLES LIBRES (§3.3)")
    print("=" * 64)

    # 1. preuve d'absence de collision du code reserve
    fv.proof_no_self_collision()
    print("  code reserve (7,7) : aucun lambda de profondeur 0..62 ne peut")
    print("  ne peut l'egaler ; il n'appartient qu'a d=63, bornee hors usage. OK")

    # 1b. la garde de profondeur est APPLIQUEE (revue externe) : un token
    #     a la profondeur 63 (SELF=(7,7)) ou au-dela est refuse
    deep = "w"
    for _ in range(64):                  # lambda le plus interne a d=63
        deep = "(\\v. %s)" % deep
    try:
        fv.rows_fix(bd.to_debruijn(lb.parse(deep)))
        raise AssertionError("garde de profondeur NON appliquee")
    except ValueError:
        print("  garde de profondeur : un lambda a d=63 est REFUSE "
              "(collision (7,7) evitee) OK")

    # 2. cas buggues : lambda du redex a profondeur 0 + variables libres
    bug_cases = [
        "(\\x. x y) z",
        "(\\x. y x) z",
        "(\\x. x) y",
        "(\\x. x (\\y. y z)) w",
        "((\\x. x) y) w",   # lambda du redex a d=0 (aucun lambda englobant)
    ]
    print("  cas buggues (lambda a profondeur 0, libres presentes) :")
    for s in bug_cases:
        r = mask_report(s)
        assert r["papier"] != r["truth"], (s, r)     # bug §3.3 reproduit
        assert r["fix"] == r["truth"], (s, r)        # fix exact
        print("    %-24s papier=%s  fix=%s  verite=%s"
              % (r["s"], r["papier"], r["fix"], r["truth"]))
    print("    -> le masque PAPIER marque les libres comme lies (bug")
    print("       reproduit) ; le masque FIXE est exact sur les %d cas")

    # 3. cas controles : lambda a profondeur > 0, et terme ferme
    ctrl_cases = [
        "\\a. ((\\x. x y) z)",   # lambda du redex a d=1 (sous \a)
        two_i,                   # terme ferme : aucun libre
    ]
    for s in ctrl_cases:
        r = mask_report(s)
        assert r["papier"] == r["truth"], (s, r)
        assert r["fix"] == r["truth"], (s, r)
    print("  cas controles (lambda a d=1, terme ferme) : papier == fix")
    print("  == verite sur %d cas -> le fix ne degrade rien d'existant"
          % len(ctrl_cases))

    # 4. tenue au bruit additif 10 % (Monte-Carlo, 4000 tirages)
    s = bug_cases[0]
    r = mask_report(s)
    db_s = bd.to_debruijn(lb.parse(s))
    rate_p = fv.noise_false_positive_rate(fv.rows_papier(db_s), r["lam_self"])
    rate_f = fv.noise_false_positive_rate(fv.rows_fix(db_s), r["lam_self"])
    print("  bruit 10%%/bit, '%s' : papier %.0f %% de tirages touches,"
          % (s, 100 * rate_p))
    print("  fix %.1f %% (residu ~p^2 par libre ; annulable par la variante"
          % (100 * rate_f))
    print("  « inhibition FREE_F » si on la cable un jour)")
    assert rate_p > 0.95 and rate_f < 0.05

    print()
    print("TOUTES LES VERIFICATIONS DU FIX SONT VERTES.")


if __name__ == "__main__":
    main()
