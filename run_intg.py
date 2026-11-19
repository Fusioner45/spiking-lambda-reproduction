# -*- coding: utf-8 -*-
"""Demo palier 5 : INTG_BODY + ARG_MODE reels (§2.5).

Pour chaque terme de test : la sequence sigma (cf. Fig. 3 du papier),
la position de fin de corps selon la verite semantique, puis le circuit
neural : INTG doit decharger au meme slot, et ARG_MODE doit s'auto-
entretenir apres le decharge.
"""

import lambda_beta as lb
import bridge_db as bd
import intg_body as ig

two = "\\f. \\x. f (f x)"
three = "\\f. \\x. f (f (f x))"
one = "\\f. \\x. f x"
plus = "\\m. \\n. \\f. m (n f)"
mult = "\\m. \\n. \\f. m (n f)"
eye = "\\x. x"

cases = [
    ("(%s) (%s) (%s)" % (plus, two, three), "plus 2 3"),
    ("(%s) (%s) (%s)" % (plus, one, one), "plus 1 1"),
    ("(%s) (%s) (%s)" % (mult, two, two), "mult 2 2"),
    ("(%s) (%s)" % (two, eye), "2 I"),
    ("(\\x. x x) (%s)" % eye, "(lam x. x x) I"),
]


def main():
    print("=" * 64)
    print("PALIER 5 - INTG_BODY + ARG_MODE (§2.5)")
    print("=" * 64)

    c = ig.IntgCircuit([(bd.APP, 0)], 0)     # pour la calibration seule
    print("  W_CNT=%.1f (1/epsilon(300,1)=%.5f, eq. 8) ; "
          "W_self_arg=%.2f (1.15/epsilon(10,2)=%.3f)"
          % (c.w_cnt, c.eps_3001, c.w_self_arg, c.eps_102))

    ok = 0
    for s, label in cases:
        t = lb.parse(s)
        toks = bd.to_tokens(bd.to_debruijn(t))
        k = bd.find_redex(t)
        assert k != -1
        truth = ig.body_end_pos(toks, k)
        sigma = ig.sigma_sequence(toks, k)
        r = ig.IntgCircuit(toks, k).run()
        print("  %-14s sigma=%s" % (label, sigma))
        print("                 verite=%s  INTG decharge au slot %s "
              "(t=%s ms), %d re-decharges, ARG_MODE %d spikes"
              % (truth, r["pos"],
                 ("%.1f" % r["t_dis"]) if r["t_dis"] else "aucun",
                 r["n_intg"] - 1, r["n_arg"]))
        assert r["pos"] == truth, (label, r, truth)
        assert r["n_arg"] > 5, (label, r)     # ARG_MODE auto-entretenu
        ok += 1

    print()
    print("TOUTES LES VERIFICATIONS INTG SONT VERTES (%d termes)." % ok)


if __name__ == "__main__":
    main()
