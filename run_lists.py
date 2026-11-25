# -*- coding: utf-8 -*-
"""Donnees structurees : les LISTES CHURCH reduites par la boucle fermee
(session 44) : le cap « calcul symbolique sur donnees structurees ».

Encodage (inline, terme clos, aucun nom libre) :
    nil      = \\c n. n
    cons h t = \\h t c n. c h (t c n)     (applique a ses deux arguments)
    cons2 h t = \\c n. c h (t c n)        (deja applique : l'encodage de
                                          la premiere observation)
    append   = \\l1 l2 c n. l1 c (l2 c n)
    map      = \\f l c n. l (\\h t c n. c (f h) (t c n)) (\\c n. n)
    reverse  = \\l. l (\\h acc c n. acc c (c h n)) (\\c n. n)
    succ     = \\n f x. f (n f x)

Pourquoi ces termes sont un vrai test : les cons portent leurs quatre
lieurs, les numeraux deux ; les lieurs internes s'accumulent (lieur a
profondeur 7, puis >= 8), ce qu'aucun banc numerique n'exercait.

  1. L'ORACLE : tailles, comptes d'etapes, forme finale relue comme une
     liste d'entiers.
  2. Les DEUX DEFAUTS DE CONVENTION de la regle KEEP (orchestrate.
     rewrite, avant la session 44) : la FINE du lieur etait comparee a la
     profondeur complete du lambda du redex, et le code reserve aux
     libres teste sur la fine seule.
       A : lieur a profondeur 7 mod 8  (fine = 7 = code libre) -> le VAR
           LIE etait decremente comme un libre ;
       B : lieur a profondeur >= 8     (fine < d_lam par accident) ->
           decremente alors que son lieur est SOUS le redex.
     Les deux cas minimaux, puis quelles demos les declenchent.
  2b. LE DIAGNOSTIC, MESURE sur le terme de la premiere observation
     (append en cons2, 69 tokens) : a l'etape ou l'ancienne regle est
     fausse la premiere fois, la composition canal par canal et le
     rewrite corrige egalent le re-encodage de l'oracle et le re-scan
     neural refuse ; seul l'ancien rewrite differait (deux jetons).
  3. La boucle fermee, segmentation POSITIONNELLE, les deux moteurs.
  4. Le compteur ANALOGIQUE du papier refuse (falsifiable, finding 8).
  5. Le CUBE VIVANT : l'etat passe par les memoires STDP (composition
     KEEP canal-level + ecriture multiplexee).
  6. Le RE-SCAN NEURAL sur ces corps : l'enveloppe MESUREE, deux murs
     distincts, tous deux detectes (jamais un resultat silencieux).
  7. Les TROIS definitions de la verite de la liaison du depot (la
     boucle, le banc de l'anneau, le banc des libres) disent la meme
     chose a chaque etape de chaque demo : une convention ecrite trois
     fois doit etre comparee.
"""

import traceback

import lambda_beta as lb
import bridge_db as bd
import free_vars_fix as fv
import bind_gamma
import cube_state as cs
import cube_write
import intg_body
import orchestrate as orc
import rescan_circuit as rc
import ring_phase
import snn_core as sc

ENGINS = ("py", "c")


def num(n):
    return "(\\f x. " + "f (" * n + "x" + ")" * n + ")"


NIL = "(\\c n. n)"
APPEND = "(\\l1 l2 c n. l1 c (l2 c n))"
MAP = "(\\f l c n. l (\\h t c n. c (f h) (t c n)) (\\c n. n))"
SUCC = "(\\n f x. f (n f x))"
REVERSE = "(\\l. l (\\h acc c n. acc c (c h n)) (\\c n. n))"
CONS2 = "((\\c n. c %s (%s c n)))"


def church_list(xs):
    s = NIL
    for x in reversed(xs):
        s = "((\\h t c n. c h (t c n)) %s %s)" % (num(x), s)
    return s


def church_list2(xs):
    """Meme liste, cons DEJA applique : (\\c n. c h (t c n)). L'encodage
    de la premiere observation (session 43) : append [1,2] [3] y fait
    69 tokens et l'ancienne regle KEEP y est fausse des l'etape 2."""
    s = NIL
    for x in reversed(xs):
        s = CONS2 % (num(x), s)
    return s


def demos():
    """(nom, terme, liste attendue)."""
    l12, l123 = church_list([1, 2]), church_list([1, 2, 3])
    l2, l3, l4 = church_list([2]), church_list([3]), church_list([4])
    return [
        ("[1,2,3]", church_list([1, 2, 3]), [1, 2, 3]),
        ("append [1,2] [3]", "(%s) (%s) (%s)" % (APPEND, l12, l3),
         [1, 2, 3]),
        ("append [1,2,3] [4]", "(%s) (%s) (%s)" % (APPEND, l123, l4),
         [1, 2, 3, 4]),
        ("map succ [1,2]", "(%s) (%s) (%s)" % (MAP, SUCC, l12), [2, 3]),
        ("reverse [1,2,3]", "(%s) (%s)" % (REVERSE, l123), [3, 2, 1]),
        ("append c2 [1,2] [3]",
         "(%s) (%s) (%s)" % (APPEND, church_list2([1, 2]), church_list2([3])),
         [1, 2, 3]),
    ]


def oracle(term_str):
    """Trace (tokens par etape) et forme normale de l'oracle symbolique."""
    cur = lb.parse(term_str)
    trace = []
    while True:
        db = bd.to_debruijn(cur)
        if bd.find_redex(cur) == -1:
            break
        trace.append(len(bd.to_tokens(db)))
        cur, _d = lb.beta_step(cur)
    trace.append(len(bd.to_tokens(bd.to_debruijn(cur))))
    return cur, trace


def strip_vacuous(t):
    """(terme, nb) : les lieurs de tete dont la variable n'apparait pas
    libre sont retires (contraction eta A LA LECTURE, pas une reduction
    de plus : la forme normale beta du map garde les \\c n vacants de sa
    tete, masques par ceux de la liste : \\c n c n. c 2 (c 3 n))."""
    n_eta = 0
    while isinstance(t, lb.Abs) and t.param not in lb.free_vars(t.body):
        t = t.body
        n_eta += 1
    return t, n_eta


def church_list_to_ints(t):
    """\\c.\\n. c h1 (c h2 (... n)) -> [h1, h2, ...] ; None si la forme
    n'est pas une liste de numeraux (relue sur les NOMS du terme, les
    lieurs de tete vacants retires)."""
    t, _n = strip_vacuous(t)
    if not (isinstance(t, lb.Abs) and isinstance(t.body, lb.Abs)):
        return None
    c, n = t.param, t.body.param
    cur, out = t.body.body, []
    while isinstance(cur, lb.App):
        f = cur.func
        if not (isinstance(f, lb.App) and isinstance(f.func, lb.Var)
                and f.func.name == c):
            return None
        v = lb.church_to_int(f.arg)
        if v is None:
            return None
        out.append(v)
        cur = cur.arg
    return out if (isinstance(cur, lb.Var) and cur.name == n) else None


def factory(eng):
    return sc.CNetwork if eng == "c" else None


# ---- 2. les deux defauts de la regle KEEP -------------------------------

def old_keep_index(tid, row, d_lam):
    """La regle KEEP d'AVANT la session 44 : la FINE du lieur comparee a
    la profondeur complete du lambda du redex, le code libre sur la fine
    seule. Reproduite ici pour prouver que les termes choisis la font
    tomber en erreur (regression non vacuite)."""
    n = tid - 4
    if row[4] < d_lam or row[4] == fv.RESERVED[0]:
        n -= 1
    return n


def old_rewrite(tokens, rows, K, l_body, l_arg, bound_sh):
    """L'assemblage d'AVANT la session 44, mot pour mot : seule la regle
    KEEP des VAR gardes differe de orchestrate.rewrite."""
    d_ref = tokens[K][1]
    body_start, body_end = K + 2, K + 2 + l_body
    arg = tokens[body_end:body_end + l_arg]
    out = list(tokens[:K])
    for j in range(body_start, body_end):
        if j in bound_sh:
            sh = bound_sh[j]
            for (ida, da) in arg:
                if ida >= 4 and (ida - 4) >= (da - d_ref):
                    out.append((bd.VAR(ida - 4 + sh), da + sh))
                else:
                    out.append((ida, da + sh))
        else:
            tid, d = tokens[j]
            if tid >= 4:
                out.append((bd.VAR(old_keep_index(tid, rows[j],
                                                  tokens[K + 1][1])),
                            d - 1))
            else:
                out.append((tid, d - 1))
    out.extend(tokens[body_end + l_arg:])
    return out


def diagnose_first_divergence(term_str):
    """L'etat d'AVANT l'etape ou l'ancien assemblage est faux la premiere
    fois, et les jetons faux qu'il y produit contre l'oracle, avec les
    lignes d'ENTREE de ces jetons (le corps garde sort avec deux tokens
    de moins que le redex n'en avait, et l'argument a la place de chaque
    VAR lie)."""
    steps, _k = old_rule_hits(term_str)
    cur, toks, rows, K, l_body, l_arg, bound_sh = step_state(
        term_str, steps[0] - 1)
    oracle_next, _d = lb.beta_step(cur)
    toks_or = bd.to_tokens(bd.to_debruijn(oracle_next))
    fixed = orc.rewrite(toks, rows, K, l_body, l_arg, bound_sh)
    old = old_rewrite(toks, rows, K, l_body, l_arg, bound_sh)
    assert fixed == toks_or and len(old) == len(toks_or), steps[0]
    bad = [i for i in range(len(toks_or)) if old[i] != toks_or[i]]
    out2in = list(range(K))
    for j in range(K + 2, K + 2 + l_body):
        if j in bound_sh:
            out2in.extend([None] * l_arg)
        else:
            out2in.append(j)
    return (steps, cur, toks, rows, K, l_body, l_arg, bound_sh, oracle_next,
            [(i, old[i], toks_or[i]) for i in bad],
            [rows[out2in[i]] for i in bad])


def three_truths(term_str):
    """Par etape de reduction : (K, VAR lies selon le banc de l'ANNEAU,
    selon la BOUCLE, selon le banc des LIBRES restreint au corps)."""
    cur = lb.parse(term_str)
    out = []
    while bd.find_redex(cur) != -1:
        K, _dl, _dr, subs = ring_phase.substitutions_of_step(cur)
        toks = bd.to_tokens(bd.to_debruijn(cur))
        rows = fv.rows_fix(bd.to_debruijn(cur))
        body_end = K + 2 + intg_body.body_end_pos(toks, K) + 1
        canon = bind_gamma.truth_bound_indices(rows, K, body_end)
        free_body = [i for i in fv.truth_bound(rows, toks[K + 1][1])
                     if K + 1 < i < body_end]
        out.append((K, [j for (j, _dv, _sh) in subs], canon, free_body))
        cur, _d = lb.beta_step(cur)
    return out


def old_rule_hits(term_str):
    """Etapes (1-based) ou l'ancienne regle donne un indice faux pour un
    VAR garde du corps, et les defauts touches : 'A' = lieur a
    profondeur 7 mod 8, 'B' = lieur a profondeur >= 8."""
    cur = lb.parse(term_str)
    steps, kinds, n = set(), set(), 0
    while True:
        K = bd.find_redex(cur)
        if K == -1:
            return sorted(steps), sorted(kinds)
        n += 1
        nxt, _d = lb.beta_step(cur)
        db = bd.to_debruijn(cur)
        toks = bd.to_tokens(db)
        rows = fv.rows_fix(db)
        l_body = intg_body.body_end_pos(toks, K) + 1
        l_arg = orc.balance_end(toks, K + 2 + l_body)
        d_lam = toks[K + 1][1]
        truth = bind_gamma.truth_bound_indices(rows, K, K + 2 + l_body)
        bound_sh = {j: toks[j][1] - 1 - toks[K][1] for j in truth}
        new = orc.rewrite(toks, rows, K, l_body, l_arg, bound_sh)
        pos = K
        for j in range(K + 2, K + 2 + l_body):
            if j in bound_sh:
                pos += l_arg
                continue
            tid = toks[j][0]
            if tid >= 4 and old_keep_index(tid, rows[j], d_lam) \
                    != new[pos][0] - 4:
                b = rows[j][4] + 8 * rows[j][5]
                steps.add(n)
                kinds.add("A" if b < 8 else "B")
            pos += 1
        cur = nxt


# ---- 6. l'enveloppe du re-scan neural -----------------------------------

def step_state(term_str, n_steps):
    """L'etat de la (n_steps+1)-ieme etape : atteint par l'oracle."""
    cur = lb.parse(term_str)
    for _ in range(n_steps):
        cur, _d = lb.beta_step(cur)
    db = bd.to_debruijn(cur)
    toks = bd.to_tokens(db)
    rows = fv.rows_fix(db)
    K = bd.find_redex(cur)
    l_body = intg_body.body_end_pos(toks, K) + 1
    l_arg = orc.balance_end(toks, K + 2 + l_body)
    truth = bind_gamma.truth_bound_indices(rows, K, K + 2 + l_body)
    bound_sh = {j: toks[j][1] - 1 - toks[K][1] for j in truth}
    return cur, toks, rows, K, l_body, l_arg, bound_sh


def trace_stack(toks, rows, K, l_body, bound_sh, slot_ms, bus,
                tau_m=1000.0):
    """Le re-scan, token par token, INSTRUMENTE : a chaque token garde,
    ce que le circuit lit (cur, b), la reference, le nombre de niveaux
    crees sur la chaine des lieurs, les fermetures du slot et les
    temps de reponse de l'onde (relatifs au debut du slot, avec la
    profondeur du lieur qui repond). S'arrete a la premiere assertion
    du circuit (entree {'assert': True})."""
    body_rows = rows[K + 2:K + 2 + l_body]
    d_lam = toks[K + 1][1]
    skip = {j - (K + 2) for j in bound_sh}
    spec = cube_write.rescan_body(body_rows, d_lam, skip)
    stack = rc.RescanStack(d_lam, tau_m=tau_m, slot_ms=slot_ms,
                           max_tokens=l_body, binder_bus=bus)
    si, log = 0, []
    for pos, row in enumerate(body_rows):
        if pos in skip:
            stack.feed("SKIP")
            continue
        tid = row[0]
        if tid >= 4:
            kind, binder_n = "VAR", tid - 4
        elif tid == bd.LAM:
            kind, binder_n = "LAM", None
        else:
            kind, binder_n = "APP", None
        t0 = stack.slot * slot_ms
        try:
            cur, b = stack.feed(kind, binder_n)
        except AssertionError:
            log.append({"pos": pos, "kind": kind, "assert": True})
            break
        want = spec[si]
        si += 1
        log.append({
            "pos": pos, "kind": kind, "cur": cur,
            "want": want[0] + 8 * want[1], "b": b,
            "want_b": want[2] + 8 * want[3],
            "chain": sum(1 for lv in stack.all if lv["kind"] == "LAM"),
            "closed": stack.last_closures,
            "resp": [round(t - t0, 1)
                     for t, _k, _d in stack.last_responses],
            "depths": [d for _t, _k, d in stack.last_responses]})
    return log


def self_trace(toks, rows, K, l_body, bound_sh, slot_ms, bus):
    """Le re-scan neural SANS lecture de lieur (bus coupe : la pile
    d'INTG seule), self par token, contre la spec (rescan_body) : la
    liste des (position, self_circuit, self_spec) differents."""
    return [(r["pos"], r["cur"], r["want"])
            for r in trace_stack(toks, rows, K, l_body, bound_sh, slot_ms,
                                 bus)
            if "assert" not in r and r["cur"] != r["want"]]


def main():
    print("=" * 72)
    print("DONNEES STRUCTUREES - listes Church dans la boucle fermee")
    print("=" * 72)

    table = demos()

    # 1. l'oracle
    print("  [1] oracle symbolique (taille, etapes, forme finale relue) :")
    want = [([1, 2, 3], 69, 12, 33), ([1, 2, 3], 87, 18, 33),
            ([1, 2, 3, 4], 113, 22, 47), ([2, 3], 82, 26, 27),
            ([3, 2, 1], 90, 27, 33), ([1, 2, 3], 69, 12, 33)]
    facts = []
    for (name, term, as_list), (w_list, w_tok, w_steps, w_nf) in \
            zip(table, want):
        nf, trace = oracle(term)
        assert (trace[0], len(trace) - 1, trace[-1]) == \
            (w_tok, w_steps, w_nf), (name, trace)
        assert church_list_to_ints(nf) == w_list, (name, lb.to_str(nf))
        assert w_list == as_list
        facts.append((nf, trace))
        print("    %-20s %3d tokens -> %2d etapes -> %2d tokens = %s%s"
              % (name, w_tok, w_steps, w_nf, w_list,
                 ("  (%d lieurs de tete vacants, ignores a la lecture)"
                  % strip_vacuous(nf)[1]) if strip_vacuous(nf)[1] else ""))

    # 2. les deux defauts de la regle KEEP
    print("  [2] les deux defauts de convention de la regle KEEP :")
    minimal = [
        ("A", r"(\y. \a b c d e f g. g) (\z. z)", ["A"]),
        ("B", r"(\u v. (\w. \s1 s2 s3 s4 s5 s6. s6) (\z. z))", ["B"]),
    ]
    for tag, term, kinds in minimal:
        steps, got = old_rule_hits(term)
        assert got == kinds and steps == [1], (tag, steps, got)
        exp_nf, exp_trace = oracle(term)
        for eng in ENGINS:
            nf, trace, _rep = orc.ClosedLoop(
                verbose=False, balance_counter=True, copy_engine=eng,
                net_factory=factory(eng)).run(term, max_steps=4)
            assert trace == exp_trace, (tag, eng, trace)
            assert bd.to_debruijn(nf) == bd.to_debruijn(exp_nf), (tag, eng)
        print("    defaut %s : l'ancienne regle est fausse des l'etape 1 ;"
              " la boucle == oracle sur les 2 moteurs" % tag)
    hit_want = {"[1,2,3]": ["A"], "append [1,2] [3]": ["A"],
                "append [1,2,3] [4]": ["A"], "map succ [1,2]": ["A", "B"],
                "reverse [1,2,3]": ["A"], "append c2 [1,2] [3]": ["A"]}
    for name, term, _l in table:
        steps, kinds = old_rule_hits(term)
        assert kinds == hit_want[name] and steps, (name, steps, kinds)
        print("    %-20s ancienne regle fausse aux etapes %s (%d)"
              % (name, steps, len(steps)))

    # 2b. le diagnostic, MESURE : sur le terme de la premiere observation,
    #     a l'etape ou l'ancien assemblage est faux la premiere fois, tout
    #     ce qui COMPOSE les canaux est exact ; un seul endroit est faux
    (steps_c2, cur, toks, rows, K, l_body, l_arg, bound_sh, oracle_next,
     bad, bad_rows) = diagnose_first_divergence(table[5][1])
    assert steps_c2[:2] == [2, 3]                 # fausse des l'etape 2
    assert bad == [(24, (4, 8), (5, 8)), (26, (4, 8), (5, 8))], bad
    d_lam = toks[K + 1][1]
    for r in bad_rows:
        tid, d, _sf, _sc, bf, bc, libre = r
        # un VAR LIE (indice 1, profondeur 9) dont le lieur est a
        # l'adresse 7 : sa fine est le code reserve des libres
        assert (tid, d, bf, bc, libre) == (5, 9, 7, 0, False), r
    assert d_lam == 0                              # bf < d_lam impossible
    pats_or = [cs.slot_pattern_from_row(r) for r in
               fv.rows_fix(bd.to_debruijn(oracle_next))]
    ring = ring_phase.PhaseRing()
    assert cube_write.compose_cube(
        toks, rows, K, l_body, l_arg, bound_sh, ring, neural=False) \
        == pats_or
    try:
        cube_write.compose_cube(toks, rows, K, l_body, l_arg, bound_sh,
                                ring, neural=True)
        refused = False
    except AssertionError:
        refused = True
    assert refused, "le re-scan neural au slot nominal devrait refuser"
    print("    le diagnostic, sur append c2 [1,2] [3] a l'etape %d :"
          % steps_c2[0])
    print("      ancien assemblage faux sur %d jetons (%s) ; assemblage"
          " corrige == oracle" % (len(bad), ", ".join(
              "pos %d %s au lieu de %s" % b for b in bad)))
    print("      les 2 VAR : lies (indice 1), lieur a l'adresse 7 = code"
          " reserve des libres -> decrements comme des libres")
    print("      composition canal par canal == re-encodage de l'oracle"
          " (%d slots) ; re-scan neural au slot nominal : REFUS"
          % len(pats_or))

    # 3. la boucle fermee, segmentation positionnelle, les deux moteurs
    print("  [3] boucle fermee, compteur POSITIONNEL, les deux moteurs :")
    for (name, term, as_list), (exp_nf, exp_trace) in zip(table, facts):
        for eng in ENGINS:
            nf, trace, _rep = orc.ClosedLoop(
                verbose=False, balance_counter=True, copy_engine=eng,
                net_factory=factory(eng)).run(term, max_steps=60)
            assert trace == exp_trace, (name, eng, trace, exp_trace)
            assert bd.to_debruijn(nf) == bd.to_debruijn(exp_nf), (name, eng)
            assert church_list_to_ints(nf) == as_list, (name, eng)
        print("    %-20s py + c : %2d etapes == oracle, forme finale = %s"
              % (name, len(exp_trace) - 1, as_list))

    # 4. le compteur analogique du papier refuse (falsifiable)
    print("  [4] le compteur ANALOGIQUE refuse (jamais un resultat faux) :")
    term = table[1][1]

    def analog_refusal(tau):
        loop = orc.ClosedLoop(verbose=False, intg_tau_m=tau,
                              copy_engine="c", net_factory=sc.CNetwork)
        cur, done = lb.parse(term), 0
        while True:
            try:
                nxt, _rep = loop.step(cur)
            except AssertionError as e:
                line = traceback.extract_tb(e.__traceback__)[-1].line
                if "l_arg == l_arg_or" in line:
                    return done + 1, "l_arg"
                if "l_body == l_body_or" in line:
                    return done + 1, "l_body"
                return done + 1, "AUTRE ASSERT : %s" % line.strip()
            if nxt is None:
                return None, None
            done += 1
            cur = nxt

    for tau, want_step in ((300.0, (1, "l_arg")), (1000.0, (2, "l_body"))):
        got = analog_refusal(tau)
        assert got == want_step, (tau, got, want_step)
        print("    tau_m=%4.0f ms : refuse a l'etape %d (%s != oracle)"
              % (tau, got[0], got[1]))

    # 5. le cube vivant : l'etat passe par les memoires STDP
    print("  [5] CUBE VIVANT (memoires STDP + composition KEEP + ecriture"
          " multiplexee) :")
    for (name, term, as_list), (exp_nf, exp_trace) in zip(table, facts):
        for eng in (("py", "c") if name == table[0][0] else ("c",)):
            nf, trace, reps = orc.ClosedLoop(
                verbose=False, balance_counter=True, copy_engine=eng,
                net_factory=factory(eng), living_cube=True,
                neural_keep=False).run(term, max_steps=60)
            assert trace == exp_trace, (name, eng, trace)
            assert bd.to_debruijn(nf) == bd.to_debruijn(exp_nf), (name, eng)
            assert all(r["cube_write"] == "composed" for r in reps)
        print("    %-20s %-5s : %2d etapes, chaque cube ecrit par les"
              " copies STDP et relu == %s"
              % (name, "py + c" if name == table[0][0] else "c",
                 len(exp_trace) - 1, as_list))

    # 6. l'enveloppe du re-scan neural sur un corps structure
    print("  [6] RE-SCAN NEURAL sur le corps de l'etape 5 de append"
          " [1,2] [3] : l'enveloppe mesuree")
    cur, toks, rows, K, l_body, l_arg, bound_sh = step_state(table[1][1], 4)
    body_end = K + 2 + l_body
    n_lam = sum(1 for r in rows[K + 2:body_end] if r[0] == bd.LAM)
    d_lam = toks[K + 1][1]
    assert (l_body, n_lam, d_lam) == (38, 11, 2), (l_body, n_lam, d_lam)
    oracle_next, _d = lb.beta_step(cur)
    pats_or = [cs.slot_pattern_from_row(r) for r in
               fv.rows_fix(bd.to_debruijn(oracle_next))]
    pats_keep = cube_write.compose_cube(
        toks, rows, K, l_body, l_arg, bound_sh, ring_phase.PhaseRing(),
        neural=False)
    assert pats_keep == pats_or            # la reference KEEP est exacte
    print("    corps de %d tokens, %d lieurs ; la composition KEEP =="
          " l'oracle (%d slots)" % (l_body, n_lam, len(pats_or)))

    # (a) le slot nominal, avec le bus BIND : la reponse du lieur le plus
    #     bas sort du slot (budget lineaire de l'onde, ~1.8 ms par etage)
    #     : le circuit REFUSE (assertion), il ne repond jamais a cote
    try:
        cube_write.compose_cube(toks, rows, K, l_body, l_arg, bound_sh,
                                ring_phase.PhaseRing(), neural=True)
        refused = False
    except AssertionError:
        refused = True
    assert refused, "le re-scan neural au slot nominal devrait refuser"
    print("    (a) slot nominal 12 ms, bus BIND : REFUS (assertion du"
          " circuit), %d etages sur la chaine" % n_lam)

    # (b) le slot nominal, SANS le bus (la pile d'INTG seule) : la derive
    #     analogique (finding 8) ferme les niveaux externes un token trop
    #     tot : le self du dernier token vaut d_lam au lieu de d_lam + 1
    bad = self_trace(toks, rows, K, l_body, bound_sh, rc.SLOT_MS, False)
    assert bad == [(l_body - 1, d_lam, d_lam + 1)], bad
    print("    (b) slot nominal, INTG seuls : fermeture anticipee d'un"
          " token au dernier token (self %d au lieu de %d) : finding 8"
          % (bad[0][1], bad[0][2]))

    # (c) le slot ADAPTE au budget de l'onde (formule du banc de stress)
    #     ne suffit pas : la derive suit (meme erreur, dernier slot)
    slot = round(3.8 + 1.8 * (n_lam - 1) + 3.0, 1)

    def factory_slot(d, max_tokens=64, _s=slot):
        return rc.RescanStack(d, slot_ms=_s, max_tokens=max_tokens)

    pats_neural = cube_write.compose_cube(
        toks, rows, K, l_body, l_arg, bound_sh, ring_phase.PhaseRing(),
        neural=True, stack_factory=factory_slot)
    n_body_slots = (l_body - len(bound_sh)) + len(bound_sh) * l_arg
    diffs = [i for i, (a, b) in enumerate(zip(pats_neural, pats_keep))
             if a != b]
    assert len(pats_neural) == len(pats_keep)
    assert diffs == [K + n_body_slots - 1], diffs
    assert self_trace(toks, rows, K, l_body, bound_sh, slot, False) == bad
    print("    (c) slot adapte %.1f ms : le bus BIND passe, la derive"
          " INTG reste (1 slot differs sur %d) : deux murs couples"
          % (slot, len(pats_keep)))

    # (d) les MECANISMES, instrumentes (trace_stack) : les chiffres de
    #     docs/design_nested_scan.md, section 6
    log = trace_stack(toks, rows, K, l_body, bound_sh, rc.SLOT_MS, True)
    by_pos = {r["pos"]: r for r in log if "assert" not in r}
    assert log[-1] == {"pos": 21, "kind": "APP", "assert": True}
    r19, r20 = by_pos[19], by_pos[20]
    assert all(r["cur"] == r["want"] for r in by_pos.values())
    assert all(r["b"] == r["want_b"] for p, r in by_pos.items()
               if r["kind"] == "VAR" and p <= 19)
    # l'onde du 20e token (pos 19) : 7 niveaux sur la chaine, le lieur
    # le plus bas (profondeur 2) ne repond pas dans le slot ; sa reponse
    # tombe a 1.3 ms dans le slot SUIVANT et y est comptee en tete
    assert ((r19["chain"], r19["resp"], r19["depths"])
            == (7, [2.9, 4.5, 6.2, 7.9], [6, 5, 4, 3]))
    assert ((r20["resp"][0], r20["depths"][0], r20["b"], r20["want_b"])
            == (1.3, 2, 4, 3))
    print("    (d) le mur 1, mesure : au 20e token 7 niveaux sur la"
          " chaine, le lieur le plus bas repond a 1.3 ms dans le slot"
          " suivant (lu 4 au lieu de 3), refus au slot d'apres")
    closed = {}
    for tau in (1000.0, round(1000.0 * slot / rc.SLOT_MS)):
        log_t = trace_stack(toks, rows, K, l_body, bound_sh, slot, False,
                            tau)
        assert [(r["pos"], r["cur"], r["want"]) for r in log_t
                if r["cur"] != r["want"]] == bad
        closed[tau] = {r["pos"]: r["closed"] for r in log_t}
    assert (closed[1000.0][35], closed[2067.0][35]) == (4, 1)
    print("    (d) le mur 2, mesure : tau_m=2067 ms au slot adapte, 1"
          " fermeture au token 35 (4 a tau_m=1000 ms), meme erreur au"
          " dernier token")

    # 7. les trois definitions de la verite de la liaison
    print("  [7] les TROIS definitions de la verite de la liaison"
          " (boucle, anneau, libres) :")
    n_steps = 0
    for name, term, _l in table:
        for (K, ring_l, loop_l, free_l) in three_truths(term):
            assert ring_l == loop_l == free_l, (name, K)
            n_steps += 1
    assert n_steps == sum(len(f[1]) - 1 for f in facts), n_steps
    print("    identiques sur les %d etapes de reduction des %d demos"
          " (une convention ecrite trois fois, comparee)"
          % (n_steps, len(table)))

    print()
    print("LISTES CHURCH VALIDEES : les deux defauts de la regle KEEP"
          " pieges et corriges, le diagnostic mesure sur le terme de la"
          " premiere observation ; append, map et reverse exacts en"
          " boucle positionnelle sur les deux moteurs ; le cube vivant"
          " porte l'etat ; le re-scan neural a son enveloppe MESUREE sur"
          " les corps structures (deux murs, detectes).")


if __name__ == "__main__":
    main()
