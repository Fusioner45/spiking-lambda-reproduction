# -*- coding: utf-8 -*-
"""Demo palier 2a : le pont vers le papier — encode/decode De Bruijn et
tokens, phases theta-gamma, detecteur Jeffress symbolique verifie contre
l'oracle nominal du palier 1."""

import sys

import lambda_beta as lb
import bridge_db as bd

# console Windows cp1252 par defaut : les λ/ε des impressions planteraient
# (revue externe) — forcer l'UTF-8 sur la sortie
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")


def trace_steps(t, n_max=12):
    """Termes successifs de la reduction (oracle nominal du palier 1)."""
    out = [t]
    cur = t
    for _ in range(n_max):
        nxt, d = lb.beta_step(cur)
        if not d:
            break
        cur = nxt
        out.append(cur)
    return out


def main():
    print("=" * 64)
    print("PALIER 2a - le pont vers le papier")
    print("=" * 64)

    two = "\\f. \\x. f (f x)"
    eye = "\\x. x"
    two_i = "(%s) (%s)" % (two, eye)

    # 1. aller-retour nominal <-> De Bruijn
    tests = ["(\\x. x) y", "(\\x. \\y. x y) y", two_i,
             "(\\m. \\f. \\x. f (m f x)) (\\f. \\x. f (f x))"
             " (\\f. \\x. f (f (f x)))",
             "(\\x. x x) (\\x. x x)",
             "x (\\z. x)",                # une meme libre a 2 profondeurs
             "(\\x. (x a) (\\y. a)) z"]   # revue externe : round-trip
    for s in tests:
        t = lb.parse(s)
        db = bd.to_debruijn(t)
        assert bd.to_debruijn(bd.from_debruijn(db)) == db
    # le nom d'une libre ne depend pas de la profondeur (revue externe) :
    # les occurrences d'une meme libre gardent UN nom au round-trip
    t = bd.from_debruijn(bd.to_debruijn(lb.parse("x (\\z. x)")))
    frees = set()

    def _free_names(u):
        if isinstance(u, lb.Var):
            if "_f" in u.name:
                frees.add(u.name)
        elif isinstance(u, lb.Abs):
            _free_names(u.body)
        else:
            _free_names(u.func)
            _free_names(u.arg)

    _free_names(t)
    assert len(frees) == 1, ("libre scindee en plusieurs noms", frees)
    print("  aller-retour nominal <-> De Bruijn : OK (%d termes, "
          "libres stables entre profondeurs)" % len(tests))

    # 2. aller-retour De Bruijn <-> tokens plats
    db = bd.to_debruijn(lb.parse(two_i))
    toks = bd.to_tokens(db)
    assert bd.tokens_to_db(toks) == db
    print("  aller-retour De Bruijn <-> tokens : OK")

    # 3. phases theta-gamma de 2 I (10 tokens, cf. papier Fig. 2)
    print("  phases de 2 I (id, depth | self f/c | bind f/c) :")
    for tid, d, sf, sc, bf, bc, libre in bd.phase_table(db):
        kind = {bd.LAM: "LAM", bd.APP: "APP"}.get(tid, "VAR%d" % (tid - 4))
        bnd = "LIBRE" if libre else "%d/%d" % (bf, bc)
        print("    %-4s d=%d  self=%d/%d  bind=%s" % (kind, d, sf, sc, bnd))

    # 4. trace de reduction de 2 I : longueurs de tokens a chaque etape
    print("  trace 2 I (oracle nominal converti en tokens) :")
    lens = [len(bd.to_tokens(bd.to_debruijn(x)))
            for x in trace_steps(lb.parse(two_i))]
    print("    longueurs :", lens)
    print("    papier (§3.1, Fig. 5D) : [10, 7, 5, 2]  -> question ouverte")
    print("    sur le 7 (notre etape 1 = λx. (λy.y) ((λy.y) x) = 8 tokens)")
    assert lens == [10, 8, 5, 2]

    # 5. detecteur Jeffress symbolique = position d'oracle (reference pure)
    battery = [
        two_i,
        "(\\x. x) (a b)",
        "(\\m. \\n. \\f. m (n f)) (\\f. \\x. f (f x))"
        " (\\f. \\x. f (f (f x)))",
        "(\\x. \\y. x y) (a b c)",
        "(\\x. x x) (\\x. x)",
        "((\\x. x) y) ((\\z. z) w)",
    ]
    n_checks = 0
    for s in battery:
        cur = lb.parse(s)
        for _ in range(4):
            k_det, _t = bd.jeffress_redex(bd.to_tokens(bd.to_debruijn(cur)))
            k_or = bd.find_redex(cur)
            assert k_det == k_or, (s, k_det, k_or)
            n_checks += 1
            nxt, d = lb.beta_step(cur)
            if not d:
                break
            cur = nxt
    print("  detecteur Jeffress symbolique = position d'oracle : OK")
    print("    (%d termes, jusqu'a 4 etapes chacun, %d coincidences verifiees)"
          % (len(battery), n_checks))

    print()
    print("TOUTES LES VERIFICATIONS DU PONT SONT VERTES.")


if __name__ == "__main__":
    main()
