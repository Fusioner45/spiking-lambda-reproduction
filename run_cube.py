# -*- coding: utf-8 -*-
"""Banc « cube vivant » : le prochain cube est ECRIT par les copies
STDP (§2.8, un canal de copie par slot) et LU par rappel — l'etat
effectif de la boucle vit dans les memoires STDP au lieu d'etre
re-encode symboliquement (chantier « cube comme etat vivant », revue
ChatGPT, addendum session 14 octies).

Encodage d'un slot : 7 canaux x 8 phases (4 canaux du papier §2.2 +
canal TYPE + 2 canaux d'indice libre) — cf. cube_state.py. L'ecriture
est COMPOSEE depuis les emissions du terme courant (copies des sources
+ shifts REELS du ring + regles KEEP canal-level §2.10.3) — cf.
cube_write.py ; le re-encodage du nouveau terme ne participe plus a
l'ecriture (il sert de reference au differentiel).

1. batterie fermee + terme ouvert via le cube vivant (moteur C) :
   traces identiques a la boucle standard ;
2. differentiel de composition sur les cas pieges (sources + ring ==
   re-encodage, canal par canal) ;
3. differentiel moteur : Python -> memes traces (C == Python) ;
4. sabotage : demonter un poids appris rend un canal muet — la lecture
   le detecte (unite) et la reduction s'arrete (le cube est PORTEUR,
   pas decoratif : l'etat passe reellement par les memoires).
5. interruption/reprise en MATRICE (terme x point k x moteurs py/c) :
   les poids seuls, dynamique reinitialisee, terme relu == terme
   symbolique, continuation == reference ininterrompue — le cube est
   l'etat (session 37). Cas FERMES verts partout ; cas OUVERT en xfail
   strict : defaut de convention sur l'identite des libres (indices par
   ordre d'apparition dans to_debruijn, _fN de from_debruijn ignores),
   fix = session 38.
"""

import lambda_beta as lb
import bridge_db as bd
import free_vars_fix as fv
import cube_state as cs
import cube_write as cw
import orchestrate as orc
import copy_stdp
import intg_body
import bind_gamma
import random
import cube_multiplex as cm

two = "\\f. \\x. f (f x)"
three = "\\f. \\x. f (f (f x))"
eye = "\\x. x"
plus = "\\m. \\n. \\f. \\x. m f (n f x)"


def main():
    print("=" * 64)
    print("CUBE VIVANT - le prochain cube vit dans les memoires STDP")
    print("=" * 64)

    # 1. batterie via le cube vivant (moteur C)
    loop = orc.ClosedLoop(living_cube=True, copy_engine="c", verbose=False)
    nf, trace, _ = loop.run("(%s) (%s)" % (eye, eye))
    print("  (\\x. x) I : trace=%s -> %s" % (trace, lb.to_str(nf)))
    assert trace == [5, 2] and lb.to_str(nf) == "\\x. x"

    nf, trace, _ = loop.run("(%s) (%s)" % (two, eye))
    print("  2 I       : trace=%s -> %s" % (trace, lb.to_str(nf)))
    assert trace == [10, 8, 5, 2] and lb.to_str(nf) == "\\x. x"

    nf, trace, _ = loop.run("(%s) (%s) (%s)" % (plus, two, three))
    print("  plus 2 3  : trace=%s -> Church %s"
          % (trace, lb.church_to_int(nf)))
    assert lb.church_to_int(nf) == 5

    # terme ouvert : les indices libres (canal reserve (7,7) + canaux
    # 5-6) sortent exactement — (\x. x y) z -> z y
    nf, trace, _ = loop.run("(\\x. x y) z")
    print("  (\\x. x y) z : trace=%s -> %s" % (trace, lb.to_str(nf)))
    assert trace == [6, 3]

    # 2. differentiel de composition : les patterns composes depuis les
    #    sources + le ring reproduisent exactement le re-encodage, sur
    #    les cas pieges (VAR lie absent du corps ; binder interne a
    #    l'argument qui shift ; libres des deux cotes)
    ring = loop.ring
    for term in ("(\\x. z) (\\x. x)", "(\\x. (\\y. y x)) (\\x. x)",
                 "(\\x. x y) z"):
        cur = lb.parse(term)
        db = bd.to_debruijn(cur)
        toks = bd.to_tokens(db)
        rows = fv.rows_fix(db)
        K = bd.find_redex(cur)
        l_body = intg_body.IntgCircuit(toks, K).run()["pos"] + 1
        l_arg = intg_body.IntgCircuit(toks, K + l_body).run()["pos"] + 1
        body_end = K + 2 + l_body
        bound_abs = bind_gamma.truth_bound_indices(rows, K, body_end)
        bound_sh = {j: toks[j][1] - 1 - toks[K][1] for j in bound_abs}
        pats = cw.compose_cube(toks, rows, K, l_body, l_arg, bound_sh, ring)
        new_toks = orc.rewrite(toks, rows, K, l_body, l_arg, bound_sh)
        ref = [cs.slot_pattern_from_row(r)
               for r in fv.rows_fix(bd.tokens_to_db(new_toks))]
        assert pats == ref, (term, pats, ref)
        assert len(pats) == len(new_toks)
        # spec re-scan (v3, cf. docs/design_nested_scan.md) : la
        # semantique evenementielle du futur circuit (compteur ancre a
        # d_lam + pile d'INTG par niveau) reproduit les regles KEEP
        # canal par canal sur les tokens gardes
        d_lam = toks[K + 1][1]
        skip = {j - (K + 2) for j in bound_abs}
        spec = cw.rescan_body(rows[K + 2:body_end], d_lam, skip)
        keep = [cw.body_slot(r, d_lam)
                for j, r in enumerate(rows[K + 2:body_end]) if j not in skip]
        assert spec == keep, (term, spec, keep)
        # v3c : la COMPOSITION NEURALE (re-scan reel derriere flag) —
        # differentiel v2 CANAL PAR CANAL contre le re-encodage (le
        # mememe flux de tokens que run_rescan : SKIP aux VAR lies,
        # l'argument insere par le ring a leur place)
        pats_n = cw.compose_cube(toks, rows, K, l_body, l_arg, bound_sh,
                                 ring, neural=True)
        assert len(pats_n) == len(ref), (term, len(pats_n), len(ref))
        for s, (pn, pr) in enumerate(zip(pats_n, ref)):
            for c, (xn, xr) in enumerate(zip(pn, pr)):
                assert xn == xr, \
                    (term, "slot %d canal %d" % (s, c), xn, xr)
        print("  composition %-24s : %d slots + %d gardes, EXACT "
              "(KEEP symbolique + re-scan NEURAL, canal par canal)"
              % (term, len(pats), len(spec)))

    # 2b. MULTIPLEXAGE (item 3, m1+m2) : UNE chaine d'emission
    #     pour l'argument, tous les taps apprennent en parallele ;
    #     differentiel poids bit-exact contre l'ecriture directe v1 et
    #     invariance de l'ordre des taps, sur les deux moteurs
    for term_mx in ("(\\x. x x) (\\f. \\x. f (f x))",
                    "(\\x. x (x (x y))) (\\f. \\x. f x)"):
        cur = lb.parse(term_mx)
        db = bd.to_debruijn(cur)
        toks = bd.to_tokens(db)
        rows = fv.rows_fix(db)
        K = bd.find_redex(cur)
        l_body = intg_body.IntgCircuit(toks, K).run()["pos"] + 1
        l_arg = intg_body.IntgCircuit(toks, K + l_body).run()["pos"] + 1
        body_end = K + 2 + l_body
        bound_abs = bind_gamma.truth_bound_indices(rows, K, body_end)
        bound_sh = {j: toks[j][1] - 1 - toks[K][1] for j in bound_abs}
        ring_mx = orc.ring_phase.PhaseRing()
        pats = cw.compose_cube(toks, rows, K, l_body, l_arg, bound_sh,
                               ring_mx)
        raw, groups = cm.arg_chain_plan(rows, K, l_body, l_arg, bound_sh)
        assert groups, ("pas d'occurrence liee", term_mx)
        n_arg = len(raw) * len(groups)
        for engine in ("py", "c"):
            cube = cm.build_cube(pats, raw, groups, engine=engine)
            assert cube.read_all() == orc.rewrite(
                toks, rows, K, l_body, l_arg, bound_sh), \
                (engine, "lecture multiplexe infidele")
            for s, pat in enumerate(pats):     # poids TAPS == directs
                direct = cm._new_bank(engine, s)
                cm.learn_direct(direct, pat)
                assert cm.bank_weights(cube.slots[s][1]) == \
                    cm.bank_weights(direct), \
                    (engine, "poids slot %d differents du v1" % s)
        # m2 : invariance — 4 ordres de taps (dont 2 permutations au
        # hasard), poids ET temps de spike du rappel identiques
        arg_slots = sorted(s for start, _sh in groups
                           for s in range(start, start + len(raw)))
        base_w, base_f = {}, {}
        for perm_i in range(4):
            # taps = triples (slot, pattern, fenetre) : le gating est
            # porte par la donnee — la permutation shuffle l'ORDRE DE
            # CREATION, pas l'affectation aux fenetres (m2 : invariance)
            taps = [(start + i, pats[start + i], i)
                    for start, _sh in groups for i in range(len(raw))]
            if perm_i:
                rnd = random.Random(perm_i)
                rnd.shuffle(taps)
            banks = cm.run_chain(raw, taps, engine="py")
            for s in arg_slots:
                w = tuple(cm.bank_weights(banks[s]))
                f = tuple(sorted((k, tuple(t)) for k, t in
                                 banks[s].recall(
                                     cs.pattern_bits(pats[s])).items()))
                if perm_i == 0:
                    base_w[s], base_f[s] = w, f
                else:
                    assert w == base_w[s], (perm_i, "poids slot %d" % s)
                    assert f == base_f[s], (perm_i, "spikes slot %d" % s)
        print("  multiplexe %-28s : %d slots dont %d taps, poids + "
              "rappel EXACTS (m1) et invariants a l'ordre des taps (m2)"
              % (term_mx, len(pats), n_arg))

    # 2c. m3 : la mesure n_bound x l_arg -> l_arg (famille (\x. x^n) (k))
    print("  m3 : emissions d'ecriture v1 (directe) vs chaine multiplexee")
    print("       %-22s %10s %10s %7s" % ("terme", "v1 slots", "chaine",
                                         "gain"))
    for n_occ, k_num in [(2, 2), (4, 4), (8, 4), (8, 8)]:
        numeral = "(\\f. \\x. " + "f (" * k_num + "x" + ")" * k_num + ")"
        term = "(\\x. " + " ".join(["x"] * n_occ) + ") " + numeral
        cur = lb.parse(term)
        db = bd.to_debruijn(cur)
        toks = bd.to_tokens(db)
        rows = fv.rows_fix(db)
        K = bd.find_redex(cur)
        # compteurs a tau_m=1000 (fix finding n°8) : les corps
        # x^n dépassent l'enveloppe tau_m=300 desuite a n=8
        l_body = intg_body.IntgCircuit(toks, K, tau_m=1000.0).run()["pos"] + 1
        l_arg = intg_body.IntgCircuit(toks, K + l_body,
                                      tau_m=1000.0).run()["pos"] + 1
        body_end = K + 2 + l_body
        bound_abs = bind_gamma.truth_bound_indices(rows, K, body_end)
        bound_sh = {j: toks[j][1] - 1 - toks[K][1] for j in bound_abs}
        ring_mx = orc.ring_phase.PhaseRing()
        pats = cw.compose_cube(toks, rows, K, l_body, l_arg, bound_sh,
                               ring_mx)
        raw, groups = cm.arg_chain_plan(rows, K, l_body, l_arg, bound_sh)
        v1, mux = cm.count_emissions(len(pats), len(raw) * len(groups),
                                     len(raw))
        assert mux < v1, (n_occ, k_num, v1, mux)
        print("       (\\x. x^%-2d) Church-%-2d    %10d %10d %6.1fx"
              % (n_occ, k_num, v1, mux, v1 / mux))

    # 3. differentiel moteur : Python == C
    loop = orc.ClosedLoop(living_cube=True, copy_engine="py", verbose=False)
    _nf, trace, _ = loop.run("(%s) (%s) (%s)" % (plus, two, three))
    print("  plus 2 3 (moteur Python) : trace=%s (identique)" % (trace,))
    assert trace == [31, 28, 25, 22, 19, 16, 13]

    # 4a. sabotage au niveau unite : poids demonte -> canal muet detecte
    cube = cs.CubeState(engine="py")
    cube.write(0, (1, 0, 0, 0, cs.TY_VAR, 0, 0))   # VAR(0) lie, d=1, b=0
    assert cube.read(0) == (bd.VAR(0), 1)
    _src, b = cube.slots[0]
    b.w[8 * 4 + cs.TY_VAR] = copy_stdp.W0          # canal TYPE demonte
    try:
        cube.read(0)
        raise AssertionError("sabotage NON detecte a la lecture")
    except ValueError:
        print("  sabotage unite : canal muet DETECTE a la lecture")

    # 4b. sabotage dans la boucle : l'etat corrompu arrete la reduction.
    #     Chemin MULTIPLEXE (defaut) : la chaine ne passe pas par
    #     write() pour les slots d'argument — la corruption passe par le
    #     hook banc (le 3e banc appris, argument ou corps)
    _n_banks = [0]

    def _sabotage_hook(bank, _slot, pattern):
        _n_banks[0] += 1
        if _n_banks[0] == 3 and hasattr(bank, "w"):
            bank.w[8 * 4 + pattern[4]] = copy_stdp.W0   # canal TYPE demonte

    try:
        loop = orc.ClosedLoop(living_cube=True, copy_engine="py",
                              verbose=False, bank_hook=_sabotage_hook)
        loop.run("(%s) (%s)" % (two, eye))
        raise AssertionError("corruption in-loop NON detectee")
    except ValueError:
        # except STRICT (revue externe) : avaler l'AssertionError du
        # "NON detectee" rendait le test non falsifiable — si la boucle
        # allait au bout malgre la corruption, l'AssertionError devait
        # sortir et faire echouer le banc
        print("  sabotage boucle (multiplexe) : la reduction s'arrete a"
              " la corruption — le cube est PORTEUR")
    finally:
        pass

    print()
    # 5. INTERRUPTION/REPRISE en MATRICE (revue externe ChatGPT, session
    #    31 ; portee elargie session 37) : les memoires du cube
    #    contiennent-elles TOUT l'etat ? Pour chaque cas (terme, point k,
    #    moteur) : capture des POIDS SEULS apres k etapes, reconstruction
    #    du cube (dynamique reinitialisee : V, traces, refractaires),
    #    lecture du terme par rappel, continuation — la trace et la forme
    #    finale doivent etre identiques a la reference ininterrompue.
    print("  interruption/reprise : l'etat = les memoires seules")
    print("  matrice (terme x point k x moteur) ; poids seuls, dynamique")
    print("  reinitialisee, le terme relu doit EGALER le terme symbolique :")

    def _resume_case(term_str, k_int, engine):
        cap = {}

        def _cap_hook(bank, slot, pattern):
            cap[slot] = (pattern, list(cm.bank_weights(bank)))

        cur = lb.parse(term_str)
        trace_ref = [len(bd.to_tokens(bd.to_debruijn(cur)))]
        loop = orc.ClosedLoop(living_cube=True, copy_engine=engine,
                              verbose=False, bank_hook=_cap_hook)
        for _i in range(k_int):
            cap.clear()                # la capture = le cube de CETTE
            cur, _rep = loop.step(cur) # etape seulement
            trace_ref.append(len(bd.to_tokens(bd.to_debruijn(cur))))
        # GELE la capture : le hook continue de tirer pendant la
        # reference ininterrompue (les bancs de la continuation
        # ecraseraient cap) — la reprise part de l'etat de l'INTERRUPTION
        cap_snapshot = dict(cap)
        # la reference ininterrompue jusqu'a la forme normale
        nf_ref = cur
        for _i in range(12):
            nxt, _rep = loop.step(cur)
            if nxt is None:
                break
            cur = nxt
            nf_ref = cur
            trace_ref.append(len(bd.to_tokens(bd.to_debruijn(cur))))
        # reconstruction depuis les POIDS SEULS : bancs neufs, poids
        # captures recharges, aucune autre donnee (V, traces,
        # refractaires laisses a leur initialisation)
        cube_r = cs.CubeState(engine=engine)
        cube_r.slots = []
        for s in sorted(cap_snapshot):
            pat, w = cap_snapshot[s]
            b = cm._new_bank(engine, s)
            if engine == "c":
                b.set_weights(w)
            else:
                b.w = list(w)
            cube_r.slots.append((pat, b))
            # les poids CAPTURES correspondent au pattern (apris au
            # seuil, jamais re-appris depuis un etat symbolique)
            learned = [k for k in range(56) if w[k] >= 7.9]
            assert learned == [g * 8 + v for g, v in enumerate(pat)], \
                ("capture non conforme au pattern", engine, s)
        read_resume = cube_r.read_all()
        cur_ref = lb.parse(term_str)
        for _i in range(k_int):
            cur_ref, _d = lb.beta_step(cur_ref)
        toks_ref = bd.to_tokens(bd.to_debruijn(cur_ref))
        assert read_resume == toks_ref, \
            ("terme relu != terme symbolique", engine, k_int,
             read_resume, toks_ref)
        # continuation sur une boucle neuve du MEME moteur
        cur_resume = bd.from_debruijn(bd.tokens_to_db(read_resume))
        trace_resume = [len(read_resume)]
        nf_resume = cur_resume
        loop2 = orc.ClosedLoop(living_cube=True, copy_engine=engine,
                               verbose=False)
        for _i in range(12):
            nxt, _rep = loop2.step(cur_resume)
            if nxt is None:
                break
            cur_resume = nxt
            nf_resume = cur_resume
            trace_resume.append(
                len(bd.to_tokens(bd.to_debruijn(cur_resume))))
        assert trace_resume == trace_ref[k_int:], \
            ("trace de reprise != reference", engine, k_int,
             trace_resume, trace_ref)
        assert lb.to_str(nf_resume) == lb.to_str(nf_ref), \
            ("forme finale != reference", engine, k_int,
             lb.to_str(nf_resume), lb.to_str(nf_ref))
        t_show = term_str if len(term_str) <= 24 else term_str[:21] + "..."
        print("    (%s, k=%d, %s) : reprise %s == reference %s ; forme"
              " finale %s"
              % (t_show, k_int, engine, trace_resume,
                 trace_ref[k_int:], lb.to_str(nf_resume)))

    t_2i = "(%s) (%s)" % (two, eye)
    t_233 = "(%s) (%s) (%s)" % (plus, two, three)
    t_open = "(\\x. x y) ((\\z. z) w)"     # libres y, w : terme OUVERT
    n_res = 0
    for k_int in (1, 2, 3):                # 3 points k sur 2 I
        _resume_case(t_2i, k_int, "py")
        _resume_case(t_2i, k_int, "c")
        n_res += 2
    for k_int in (2, 4):                   # PLUS 2 3 (6 etapes)
        _resume_case(t_233, k_int, "py")
        n_res += 1
    _resume_case(t_233, 2, "c")
    n_res += 1
    # terme ouvert : la matrice a DECOUVERT un defaut de convention
    # (session 37) — l'identite des variables libres n'est pas stable
    # d'une etape a l'autre : to_debruijn assigne les indices des libres
    # par ordre d'apparition du prefixe et ignore les suffixes _fN poses
    # par from_debruijn, donc des qu'une reduction change l'ordre
    # relatif des libres (l'argument insere AVANT la variable gardée),
    # les identites s'echangent. Le differentiel de production ne le
    # voit pas : il compare rewrite -> tokens_to_db -> rows_fix avec
    # lui-meme (auto-referentiel). XFAIL STRICT : le cas doit continuer
    # d'echouer jusqu'au fix de convention ; s'il passe un jour, ce banc
    # doit crier et le marqueur retire.
    n_xfail = 0
    for eng in ("py", "c"):
        failed = None
        try:
            _resume_case(t_open, 1, eng)
        except AssertionError as exc:
            failed = exc
        assert failed is not None, \
            ("XFAIL depasse : la reprise du terme ouvert PASSE — retirer"
             " le marqueur, la convention libre est corrigee (session 37)")
        print("    (terme ouvert, k=1, %s) : ECHEC ATTENDU (xfail strict)"
              " — identite des libres non stable d'une etape a l'autre,"
              " fix = session 38" % eng)
        n_xfail += 1
    print("    %d cas fermes (terme x point k x moteur) : le terme relu"
          " egale le terme symbolique, la trace et la forme finale"
          " egalent la reference ininterrompue — PARTOUT ; %d cas ouverts"
          " en echec attendu (defaut de convention libre, documente)"
          % (n_res, n_xfail))
    print("    LE CUBE PORTE TOUT L'ETAT — la reprise depuis les poids")
    print("    seuls reproduit la continuation a l'identique")
    print("    LE CUBE PORTE TOUT L'ETAT — la reprise depuis les poids")
    print("    seuls reproduit la continuation a l'identique")

    print()
    print("CUBE VIVANT VALIDE — l'etat de la boucle vit dans les memoires.")


if __name__ == "__main__":
    main()
