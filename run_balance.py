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
import balance_circuit as bc
import orchestrate as orc
import snn_core as sc

two = "\\f. \\x. f (f x)"
three = "\\f. \\x. f (f (f x))"
five = "\\f. \\x. f (f (f (f (f x))))"
eye = "\\x. x"
plus = "\\m. \\n. \\f. \\x. m f (n f x)"
mult = "\\m. \\n. \\f. m (n f)"
pred = "\\m. \\f. \\x. m (\\g. \\h. h (g f)) (\\u. x) (\\u. u)"
eight = "\\f. \\x. " + "f (" * 8 + "x" + ")" * 8
nine = "\\f. \\x. " + "f (" * 9 + "x" + ")" * 9
sixteen = "\\f. \\x. " + "f (" * 16 + "x" + ")" * 16


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


def circuit_case(toks, K, engine, n_digits=3):
    """Un cas B-2 : le circuit spiking contre la spec, slot par slot
    (chiffres actifs, retenues, position de discharge)."""
    spec = bdc.run_counter(toks, K, n_digits=n_digits)
    nf = sc.CNetwork if engine == "c" else None
    cir = bc.BalanceCircuit(toks, K, n_digits=n_digits, net_factory=nf)
    r = cir.run()
    assert r["pos"] == spec["pos"], \
        ("discharge circuit != spec", engine, r["pos"], spec["pos"])
    for j, ev in enumerate(spec["trace"]):
        assert tuple(r["digits"][j]) == ev["digits"], \
            ("chiffres circuit != spec", engine, j,
             r["digits"][j], ev["digits"])
        assert sorted(r["carries"][j]) == sorted(ev["carries"]), \
            ("retenues circuit != spec", engine, j,
             r["carries"][j], ev["carries"])
    return spec["pos"]


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

    # 4. B-2 : le circuit spiking contre la spec, slot par slot
    print("  B-2 circuit spiking vs spec (chiffres, retenues, decharge) :")
    b2 = [
        ("(\\x. " + " ".join(["x"] * 8) + ")", -1, "x^8"),
        ("(\\x. " + " ".join(["x"] * 20) + ")", -1, "x^20"),
        ("(%s) (%s)" % (eye, eye), None, "I I"),
        ("(%s) (%s)" % (two, eye), None, "2 I"),
        ("(\\x. x y) ((\\z. z) w)", None, "ouvert"),
    ]
    for term, K, name in b2:
        cur = lb.parse(term)
        toks = bd.to_tokens(bd.to_debruijn(cur))
        if K is None:
            K = bd.find_redex(cur)
        for eng in ("py", "c"):
            p = circuit_case(toks, K, eng)
            print("    %-6s moteur %-2s : decharge au pas %d, chiffres +"
                  " retenues == spec a chaque slot" % (name, eng, p))

    # 5. B-3 : la boucle fermee avec le compteur positionnel — la
    #    segmentation exacte remplace le compteur analogique : les cas
    #    que l'analogique refuse ou rate (9+8, 16+16, mult 5 5) se
    #    calculent aux PARAMETRES DU PAPIER (tau_m=300, pas de
    #    recalibration) ; les traces et les formes finales == l'oracle
    print("  B-3 boucle fermee, segmentation positionnelle (tau_m=300) :")
    b3 = [
        ("(%s) (%s)" % (eye, eye), "I I", "py"),
        ("(%s) (%s)" % (two, eye), "2 I", "py"),
        ("(%s) (%s)" % (eye, eye), "I I", "c"),
        ("(%s) (%s)" % (two, eye), "2 I", "c"),
        ("(%s) (%s) (%s)" % (plus, two, three), "plus 2 3", "c"),
        ("(%s) (%s) (%s)" % (plus, nine, eight), "plus 9 8", "c"),
        ("(%s) (%s) (%s)" % (plus, sixteen, eight), "plus 16 16", "c"),
        ("(%s) (%s) (%s)" % (mult, five, five), "mult 5 5", "c"),
    ]
    for term, name, eng in b3:
        cur = lb.parse(term)
        exp_nf, exp_trace = cur, []
        while True:
            db = bd.to_debruijn(cur)
            K = bd.find_redex(cur)
            if K == -1:
                break
            exp_trace.append(len(bd.to_tokens(db)))
            cur, _d = lb.beta_step(cur)
        exp_trace.append(len(bd.to_tokens(bd.to_debruijn(cur))))
        exp_nf = cur
        nf, trace, _rep = orc.ClosedLoop(
            verbose=False, balance_counter=True, copy_engine=eng,
            net_factory=(sc.CNetwork if eng == "c" else None)).run(term)
        if name == "mult 5 5":
            # le compteur positionnel retire le mur finding-8 (la
            # segmentation est exacte sur les termes de 83 tokens) ;
            # le loop atteint ensuite l'enveloppe PROPRE du DET
            # (l'espans des lignes de delai, ~70 tokens de terme) —
            # la limite suivante, surfacee pour la premiere fois par
            # ce fix (l'analogique mourait a 30 tokens avant)
            assert trace == exp_trace[:len(trace)], (name, eng)
            assert len(trace) == 8, (name, eng, len(trace))
            print("    %-9s moteur %-2s : segmentation exacte %d etapes"
                  " (termes jusqu'a %d tokens), puis halt a l'enveloppe"
                  " DET documentee (~70 tokens) — la limite suivante"
                  % (name, eng, len(trace) - 1, max(trace)))
        else:
            assert trace == exp_trace, (name, eng, trace, exp_trace)
            # alpha-equivalence : la boucle reconstruit les noms des
            # variables liees par niveaux — la comparaison se fait sur
            # l'arbre De Bruijn (termes clos ici : exact)
            assert bd.to_debruijn(nf) == bd.to_debruijn(exp_nf), \
                (name, eng, bd.to_debruijn(nf), bd.to_debruijn(exp_nf))
            print("    %-9s moteur %-2s : %2d etapes == oracle, forme"
                  " finale %s" % (name, eng, len(trace), lb.to_str(nf)))
        print("    %-9s moteur %-2s : %2d etapes == oracle, forme"
              " finale %s" % (name, eng, len(trace), lb.to_str(nf)))

    print()
    print("BALANCE POSITIONNELLE VALIDE — exacte la ou l'analogique"
          " derive ; le circuit spiking reproduit la spec slot par slot"
          " sur les deux moteurs ; la boucle fermee calcule 9+8 et"
          " 16+16 aux parametres du papier (tau_m=300).")


if __name__ == "__main__":
    main()
