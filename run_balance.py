# -*- coding: utf-8 -*-
"""Banc « compteur de balance positionnel » (chantier B, 21e banc).

La spec des chiffres (balance_digits.py) contre la verite semantique
(body_end_pos) et contre la balance directe (sigma_sequence), partout ou
le compteur analogique du papier (§2.5) derive :

1. famille de stress x^n (le pire cas : prefixe APP^(n-1) VAR^n, la
   plongee a -n) : la spec est EXACTE la ou l'analogique derive
   (mesure : -2 slots a 39 tokens, -7 a 69, -27 a 149 en tau_m=1000) ;
2. toutes les etapes de reduction symbolique de la batterie (plus,
   mult, pred, conditionnelles, combinateurs, termes ouverts) : la spec
   suit la verite a chaque etape, valeur des chiffres == sigma pas par
   pas ;
3. la derive analogique en regard (info : le defaut documente, pas une
   cible d'assert — si l'analogique est un jour corrige, ces chiffres
   changent sans casser le banc) ;
4. le contrat d'evenements B-2 : retenues signees par chiffre et feu du
   comparateur, comptes assertes — le circuit devra les reproduire
   spike par spike.

Aucun reglage force : la spec est de l'arithmetique exacte, sa
comparaison a la verite est binaire (position egale ou pas).
"""

import lambda_beta as lb
import bridge_db as bd
import intg_body
import balance_digits as bdc

two = "\\f. \\x. f (f x)"
three = "\\f. \\x. f (f (f x))"
five = "\\f. \\x. f (f (f (f (f x))))"
eye = "\\x. x"
plus = "\\m. \\n. \\f. \\x. m f (n f x)"
mult = "\\m. \\n. \\f. m (n f)"
pred = "\\m. \\f. \\x. m (\\g. \\h. h (g f)) (\\u. x) (\\u. u)"


def spec_case(toks, K, n_digits=3):
    """Un cas : spec vs verite vs balance directe, pas par pas."""
    r = bdc.run_counter(toks, K, n_digits=n_digits)
    truth = intg_body.body_end_pos(toks, K)
    sigma = intg_body.sigma_sequence(toks, K)
    # la valeur des chiffres == sigma a CHAQUE pas (differentiel interne
    # de la machine a chiffres contre la somme directe)
    c = bdc.DigitCounter(n_digits)
    for i, ev in enumerate(r["trace"]):
        if ev["kind"] != 'lam':
            c.step(ev["kind"])
        assert c.value() == sigma[i], \
            ("chiffres != sigma", i, c.digits, sigma[i])
    assert r["pos"] == truth, \
        ("spec != verite", K, r["pos"], truth, sigma)
    return r, truth


def main():
    print("=" * 64)
    print("BALANCE POSITIONNELLE - la spec des chiffres vs la verite")
    print("=" * 64)

    # 1. famille de stress : le pire cas de la derive analogique
    print("  famille de stress (corps x^n, K = -1, plongee a -n) :")
    n_tot = 0
    for n_x in (2, 8, 20, 35, 75):
        wide = "(\\x. " + " ".join(["x"] * n_x) + ")"
        toks = bd.to_tokens(bd.to_debruijn(lb.parse(wide)))
        r, truth = spec_case(toks, -1)
        ana = intg_body.IntgCircuit(toks, -1, tau_m=1000.0).run()
        ana_pos = None if ana["pos"] is None else ana["pos"] + 1
        print("    corps %3d tokens : verite %3d ; spec %3d ; analogique"
              " (tau_m=1000) %s"
              % (2 * n_x - 1, truth + 1, r["pos"] + 1, ana_pos))
        n_tot += 1

    # 2. toutes les etapes de reduction de la batterie
    print("  batterie (chaque etape de reduction = un cas) :")
    battery = [
        ("(%s) (%s)" % (eye, eye), "I I"),
        ("(%s) (%s)" % (two, eye), "2 I"),
        ("(%s) (%s) (%s)" % (plus, two, three), "plus 2 3"),
        ("(%s) (%s) (%s)" % (mult, two, three), "mult 2 3"),
        ("(%s) (%s)" % (mult, five), "mult 5 _"),
        ("(%s) (%s)" % (pred, three), "pred 3"),
        ("(\\x. x y) ((\\z. z) w)", "ouvert"),
    ]
    n_steps, n_tot_steps = 0, 0
    for term, name in battery:
        cur = lb.parse(term)
        n0 = n_steps
        step = 0
        while True:
            db = bd.to_debruijn(cur)
            toks = bd.to_tokens(db)
            K = bd.find_redex(cur)
            if K == -1:
                break
            spec_case(toks, K)
            n_steps += 1
            cur, _d = lb.beta_step(cur)
            step += 1
            assert step < 40, (name, "trop d'etapes")
        print("    %-9s : %2d etapes, spec == verite a chaque etape"
              % (name, n_steps - n0))
    n_tot_steps = n_steps
    print("    total : %d cas de batterie, tous exacts" % n_tot_steps)

    # 3. contrat d'evenements B-2 : retenues signees et feu, comptes
    print("  contrat d'evenements (le circuit B-2 reproduira ceci) :")
    wide = "(\\x. " + " ".join(["x"] * 20) + ")"
    toks = bd.to_tokens(bd.to_debruijn(lb.parse(wide)))
    r = bdc.run_counter(toks, -1)
    up = sum(1 for e in r["trace"] for c in e["carries"] if c[1] == +1)
    dn = sum(1 for e in r["trace"] for c in e["carries"] if c[1] == -1)
    fires = sum(1 for e in r["trace"] if e["fired"])
    print("    corps x^20 : %d pas, retenues %d montantes / %d"
          " descendantes, feux comparateur %d, discharge au pas %d"
          % (len(r["trace"]), up, dn, fires, r["pos"]))
    assert (up, dn) == (5, 5) and fires == 1 and r["pos"] == 38, \
        (up, dn, fires, r["pos"])
    # le pas de discharge vu du contrat : chiffres (1, 0, 0)
    last = r["trace"][r["pos"]]
    assert last["digits"] == (1, 0, 0) and last["fired"], last
    print("    discharge : chiffres (1, 0, 0), comparateur feux une fois")

    print()
    print("BALANCE POSITIONNELLE VALIDE — exacte la ou l'analogique"
          " derive ; le circuit B-2 a son contrat d'evenements.")


if __name__ == "__main__":
    main()
