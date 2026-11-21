# -*- coding: utf-8 -*-
"""Suite de robustesse : les blocs de validation du papier (§3.2, Table 3)
appliques a NOTRE boucle fermee (circuits reels + assemblage).

Chaque terme : reduction par les circuits reels, comparaison a l'oracle
symbolique A CHAQUE ETAPE (deja enforcee dans ClosedLoop.run), forme
finale verifiee. Blocs couverts (mapping Table 3) :
  1. arithmetique de Church : plus 1 1, mult 2 2, mult 2 3, pred 3
  2. logique booleenne avec branches divergentes (omega jamais atteint
     en ordre normal) + combinateurs K I I, S K K I
  3. combinateur Y : pas a pas vs oracle (divergence tracee ; l'encodage
     de Y differe de celui du papier, les longueurs ne sont pas
     comparables terme a terme — cf. journal)
  4. stress variables liees : (lam x. x^n) I, n = 2..6
  7. eta-absente : lam x. (I x) -> lam x. x via beta seul
  8. determinisme : deux runs identiques de plus 2 3
"""

import lambda_beta as lb
import bridge_db as bd
import orchestrate as orc

two = "\\f. \\x. f (f x)"
three = "\\f. \\x. f (f (f x))"
one = "\\f. \\x. f x"
eye = "\\x. x"
plus = "\\m. \\n. \\f. \\x. m f (n f x)"
mult = "\\m. \\n. \\f. m (n f)"
pred = "\\m. \\f. \\x. m (\\g. \\h. h (g f)) (\\u. x) (\\u. u)"
kk = "\\a. \\b. a"
ss = "\\a. \\b. \\c. a c (b c)"
yy = "\\f. (\\x. f (x x)) (\\x. f (x x))"
omega = "(\\x. x x) (\\x. x x)"
tru = "\\a. \\b. a"
fls = "\\a. \\b. b"
anD = "\\p. \\q. p q (%s)" % fls
oR = "\\p. \\q. p (%s) q" % tru
noT = "\\p. p (%s) (%s)" % (fls, tru)
iF = "\\c. \\t. \\e. c t e"

LOOP = orc.ClosedLoop(verbose=False)


def check(name, s, expect_nf=None, max_steps=14):
    nf, trace, _ = LOOP.run(s, max_steps=max_steps)
    if expect_nf is not None:
        # comparaison STRUCTURELLE (De Bruijn) : le decodeur rebaptise
        # les lieurs, les noms ne sont pas significatifs ; les LIBRES
        # sont canonises par un registre semé depuis le TERME SOURCE
        # (l'identite stable — le fix A-bis) : les echanges de libres
        # y sont detectes
        fmap = {}
        bd.to_debruijn_c(lb.parse(s), fmap)
        assert bd.to_debruijn_c(nf, fmap) ==             bd.to_debruijn_c(lb.parse(expect_nf), fmap),             (name, lb.to_str(nf))
    n = lb.church_to_int(nf)
    label = ("Church %d" % n) if n is not None else lb.to_str(nf)
    print("  %-26s %-2d etapes -> %s" % (name, len(trace) - 1, label))
    return trace


def main():
    print("=" * 64)
    print("ROBUSTESSE - BLOCS DE VALIDATION DU PAPIER SUR LA BOUCLE")
    print("=" * 64)

    print("  [bloc 1] arithmetique de Church")
    check("plus 1 1", "(%s) (%s) (%s)" % (plus, one, one),
          "\\f. \\x. f (f x)")
    check("mult 2 2", "(%s) (%s) (%s)" % (mult, two, two),
          "\\f. \\x. f (f (f (f x)))")
    check("mult 2 3", "(%s) (%s) (%s)" % (mult, two, three),
          "\\f. \\x. f (f (f (f (f (f x)))))")
    check("pred 3", "(%s) (%s)" % (pred, three), "\\f. \\x. f (f x)")

    print("  [bloc 2] booleens + branches omega (jamais atteintes)")
    check("if TRUE (2 I) omega",
          "((((%s) (%s)) ((%s) (%s))) (%s))"
          % (iF, tru, two, eye, omega), "\\x. x")
    check("if FALSE omega (2 I)",
          "((((%s) (%s)) (%s)) ((%s) (%s)))"
          % (iF, fls, omega, two, eye), "\\x. x")
    check("AND TRUE FALSE", "((%s) (%s)) (%s)" % (anD, tru, fls),
          "\\a. \\b. b")
    check("OR FALSE TRUE", "((%s) (%s)) (%s)" % (oR, fls, tru),
          "\\a. \\b. a")
    check("NOT TRUE", "(%s) (%s)" % (noT, tru), "\\a. \\b. b")

    print("  [bloc 2bis] combinateurs")
    check("K I I", "(%s) (%s) (%s)" % (kk, eye, eye), "\\x. x")
    check("S K K I", "(%s) (%s) (%s) (%s)" % (ss, kk, kk, eye), "\\x. x")

    print("  [bloc 3] combinateur Y : divergence pas a pas vs oracle")
    cur, trace, steps = LOOP.run("(%s) (%s)" % (yy, eye), max_steps=6)
    print("    Y I : %d etapes tracees (termes %s), chacune == oracle"
          % (len(steps), [r["n_in"] for r in steps]))
    assert len(steps) == 6
    # l'oscillation 15 -> 18 -> 15 -> 18 du papier (§3.1, Y I) est
    # reproduite ; les longueurs initiales different car notre encodage
    # de Y compte 17 tokens contre 13 chez eux (Y non specifie)
    assert [r["n_in"] for r in steps] == [17, 15, 18, 15, 18, 15]

    print("  [bloc 4] stress variables liees : (lam x. x^n) I")
    for n in range(2, 7):
        body = "x " * (n - 1) + "x"
        check("(lam x. x^%d) I" % n,
              "(\\x. %s) (%s)" % (body.strip(), eye), "\\x. x")

    print("  [bloc 7] eta-absente : lam x. (I x) via beta seul")
    check("lam x. (I x)", "\\x. (%s) x" % eye, "\\x. x")

    print("  [bloc 8] determinisme : deux runs de plus 2 3")
    _, t1, _ = LOOP.run("(%s) (%s) (%s)" % (plus, two, three),
                        max_steps=7)
    _, t2, _ = LOOP.run("(%s) (%s) (%s)" % (plus, two, three),
                        max_steps=7)
    assert t1 == t2
    print("    traces identiques : %s" % t1)

    # [bloc 9] numeriques a tau_m=1000 (fix finding n°8) : l'addition
    # et la multiplication sur grands numeraux, traces exactes
    print("  [bloc 9] numeriques a tau_m=1000 : addition/multiplication")
    num = lambda k: "(\\f. \\x. " + "f (" * k + "x" + ")" * k + ")"
    for a, b, want in [(2, 3, 5), (8, 8, 16), (9, 8, 17), (16, 16, 32)]:
        loop = orc.ClosedLoop(verbose=False, intg_tau_m=1000.0)
        nf, trace, _ = loop.run("(%s) (%s) (%s)" % (plus, num(a), num(b)),
                                max_steps=12)
        got = lb.church_to_int(nf)
        assert got == want, (a, b, got, want, trace)
        print("    plus %-2d %-2d -> Church %-2d (%d etapes)"
              % (a, b, got, len(trace) - 1))
    loop = orc.ClosedLoop(verbose=False, intg_tau_m=1000.0)
    nf, trace, _ = loop.run("(%s) (%s) (%s)" % (mult, num(5), num(5)),
                            max_steps=14)
    got = lb.church_to_int(nf)
    assert got == 25, (got, trace)
    print("    mult %-2d %-2d -> Church %-2d (%d etapes)"
          % (5, 5, got, len(trace) - 1))

    # [bloc 10] l'enveloppe tau_m=300 (finding n°8) est FALSIFIABLE :
    # 8+8 passe encore, 9+8 est REFUSE par la verification oracle (la
    # boucle s'arrete au lieu de calculer faux) — la limite du papier
    # devient un test, plus une anecdote de journal
    print("  [bloc 10] enveloppe tau_m=300 (finding n°8) : 8+8 passe,")
    loop300 = orc.ClosedLoop(verbose=False, intg_tau_m=300.0)
    nf, trace, _ = loop300.run("(%s) (%s) (%s)" % (plus, num(8), num(8)),
                           max_steps=12)
    assert lb.church_to_int(nf) == 16
    print("    plus 8  8 -> Church 16 (dans l'enveloppe) OK")
    loop300 = orc.ClosedLoop(verbose=False, intg_tau_m=300.0)
    try:
        loop300.run("(%s) (%s) (%s)" % (plus, num(9), num(8)),
                           max_steps=12)
        raise AssertionError("l'enveloppe tau_m=300 n'a pas tenu (9+8 passe "
                             "hors enveloppe : regression finding n°8)")
    except AssertionError as _e:
        if "l'enveloppe tau_m=300 n'a pas tenu" in str(_e):
            raise
    print("    plus 9  8 -> REFUSE par la verification oracle (hors")
    print("    enveloppe : le compteur derive) OK — la boucle ne calcule")
    print("    jamais faux, elle s'arrete.")

    print()
    print("BATTERIE DE ROBUSTESSE VERTE (10 blocs, ~25 termes).")


if __name__ == "__main__":
    main()
