# -*- coding: utf-8 -*-
"""m4 : COMPARAISON FORMELLE sequentiel vs multiplexe (item 3, §4.5).

Baseline : `multiplexed=False` = NOTRE implementation sequentielle de
reference (la copie §2.8 du papier, une emission theta par occurrence
de VAR lie) ; `multiplexed=True` = emission theta PARTAGEE (une chaine,
taps appris en parallele). Les deux modes partagent STRICTEMENT les
mêmes entrees (patterns composes, plan de chaine, graines par slot),
paramètres (DT, CYCLE_MS, N_CYCLES, i_theta, W0 — intouches), règles
d'arrêt (fin des fenêtres d'émission) et conditions de simulation
(même moteur C). La comparaison N'EST PAS une comparaison avec le code
original des auteurs (aucun code public) : la baseline est notre
implémentation séquentielle de référence.

DEFINITIONS DES METRIQUES (fenetre de comptage = la PHASE DE COPIE :
du premier pas de la premiere fenetre d'emission au dernier pas de la
derniere ; le rappel/lecture en est EXCLU et est verifie a l'identique
dans les deux modes comme precondition d'acceptation) :

  cycles_theta  : cycles theta (12 ms SIMULES) executes pendant la
                  phase de copie. En mux, les taps vivent pendant les
                  fenêtres partagées (parallélisme biologique) ; le
                  compteur mesure la durée séquentielle du harnais.
                  CE N'EST PAS DU WALL-CLOCK.
  emissions_SRC : événements SRC programmés (schedule_src) pendant la
                  phase de copie. En mux, ce compte littéral inclut
                  (i) l'émission brute de la chaîne (l'argument présenté
                  UNE fois) et (ii) les relais de routage vers chaque
                  tap. Dans une réalisation physique, les relais seraient
                  le MÊME spike arrivant par les portes de routage (pas
                  de re-présentation) ; notre simulation les matérialise
                  comme des re-programmations : le compte littéral
                  surestime donc le coût physique du mux du terme de
                  routage, décomposé dans le résumé final.
  spikes_DST    : spikes DST déclenchés pendant la phase de copie.
  neurones      : bancs DST alloués x 56. Les SRC sont VIRTUELS
                  (programmés) dans notre harnais ; l'émetteur de chaîne
                  représente pos_arg (tonique coupé : source d'émission
                  pure, DST silencieuses).
  synapses      : paires diagonales allouées x 56 par banc.
  bancs         : instances de copie (mémoire par slot + émetteur de
                  chaîne en mux).
  wall_clock    : perf_counter autour de la phase de copie, vérifications
                  de sortie exclues. OVERHEAD MOTEUR — à ne PAS comparer
                  au temps simulé (métriques séparées, jamais sommées).

COUT FIXE DU MULTIPLEXAGE : la préparation (plan de chaîne + liste des
taps) est mesurée séparément (prep_mux_ms) ; la composition et le
routage par le ring sont des PRÉCONDITIONS partagées par les deux modes
(calculées une fois, hors phases mesurées — le delta attribué à la copie
exclut donc le gating, vérifié structurellement par identité d'objet).

REPETITIONS : chaque mesure est répétée REPS fois ; les compteurs
déterministes (cycles, SRC, DST, poids) sont ASSERTÉS identiques entre
répétitions ; le wall-clock est rapporté en médiane.
"""

import random
import time

import lambda_beta as lb
import bridge_db as bd
import free_vars_fix as fv
import intg_body
import bind_gamma
import cube_write as cw
import cube_state as cs
import cube_multiplex as cm
import gated_chain as gc
import orchestrate as orc

ENGINE = "c"                    # les DEUX modes sur le même moteur ;
REPS = 3                        # l'égalité py est prouvée par le m1
N_BOUND_LIST = (1, 2, 4, 8)     # de run_cube (bit-exact sur py)
K_NUM_LIST = (1, 4, 8)          # l_arg = 2k + 3


def num(k):
    return "(\\f. \\x. " + "f (" * k + "x" + ")" * k + ")"


def build_case(n_bound, k_num):
    """UNE famille : terme, composition, plan — calculés UNE fois et
    partagés par les deux modes (gating et composition exclus du delta
    de copie). Compteurs de segmentation à tau_m=1000 (finding n°8 :
    les corps x^n sortent de l'enveloppe tau_m=300 dès n=8)."""
    term = "(\\x. " + " ".join(["x"] * n_bound) + ") " + num(k_num)
    cur = lb.parse(term)
    db = bd.to_debruijn(cur)
    toks = bd.to_tokens(db)
    rows = fv.rows_fix(db)
    K = bd.find_redex(cur)
    l_body = intg_body.IntgCircuit(toks, K, tau_m=1000.0).run()["pos"] + 1
    l_arg = intg_body.IntgCircuit(toks, K + l_body,
                                  tau_m=1000.0).run()["pos"] + 1
    body_end = K + 2 + l_body
    bound_abs = bind_gamma.truth_bound_indices(rows, K, body_end)
    bound_sh = {j: toks[j][1] - 1 - toks[K][1] for j in bound_abs}
    ring = orc.ring_phase.PhaseRing()
    pats = cw.compose_cube(toks, rows, K, l_body, l_arg, bound_sh, ring)
    raw, groups = cm.arg_chain_plan(rows, K, l_body, l_arg, bound_sh)
    new_toks = orc.rewrite(toks, rows, K, l_body, l_arg, bound_sh)
    n_arg = len(raw) * len(groups)
    return {"term": term, "pats": pats, "raw": raw, "groups": groups,
            "new_toks": new_toks, "n_slots": len(pats), "l_arg": l_arg,
            "n_bound": len(groups), "n_arg": n_arg,
            "n_direct": len(pats) - n_arg}


def tap_list(case):
    """La liste des taps AVEC LEUR FENETRE (le gating est porte par la
    donnee : le tap du token i n'ecoute que la fenetre i), construite
    depuis les patterns PARTAGES (identite d'objet avec la composition :
    le gating et le routage sont hors delta de copie)."""
    taps = [(start + i, case["pats"][start + i], i)
            for start, _sh in case["groups"]
            for i in range(len(case["raw"]))]
    for s, pat, _w in taps:
        assert pat is case["pats"][s], "gating hors delta : objet partagé"
    return taps


def copy_direct(case, ctr):
    """Mode sequentiel : un banc par slot, appris l'un après l'autre."""
    banks = {}
    for s, pat in enumerate(case["pats"]):
        b = cm._new_bank(ENGINE, s)
        cm.learn_counted(b, pat, ctr, ENGINE)
        banks[s] = b
    return banks


def copy_mux(case, taps, ctr):
    """Mode multiplexe : slots hors argument en direct compté + UNE
    chaine pour l'argument (taps en parallele, fenetres partagees)."""
    arg_slots = {s for s, _pat, _w in taps}
    banks = {}
    for s, pat in enumerate(case["pats"]):
        if s not in arg_slots:
            b = cm._new_bank(ENGINE, s)
            cm.learn_counted(b, pat, ctr, ENGINE)
            banks[s] = b
    banks.update(cm.run_chain(case["raw"], taps, engine=ENGINE, ctr=ctr))
    return banks


def assemble(case, banks):
    cube = cs.CubeState(engine=ENGINE)
    cube.slots = [(case["pats"][s], banks[s])
                  for s in range(case["n_slots"])]
    return cube


def accepted(case, banks_d, banks_m):
    """Precondition d'acceptation d'une mesure : lecture fidele des deux
    modes ET poids finaux identiques slot par slot."""
    assert assemble(case, banks_d).read_all() == case["new_toks"], \
        "lecture sequentielle infidele"
    assert assemble(case, banks_m).read_all() == case["new_toks"], \
        "lecture multiplexee infidele"
    for s in range(case["n_slots"]):
        assert cm.bank_weights(banks_m[s]) == cm.bank_weights(banks_d[s]), \
            ("poids finaux differents au slot %d" % s)


def main():
    print("=" * 72)
    print("m4 - COMPARAISON FORMELLE : copie sequentielle (v1) vs"
          " multiplexee")
    print("=" * 72)
    print("moteur : %s (les deux modes) ; repetitions : %d ; rappel exclu"
          " des fenetres de comptage" % (ENGINE, REPS))
    print("definitions et contraintes : voir le docstring du module")
    print()

    rows = []
    for n_bound in N_BOUND_LIST:
        for k_num in K_NUM_LIST:
            case = build_case(n_bound, k_num)
            n_slots, l_arg = case["n_slots"], case["l_arg"]
            n_arg, n_direct = case["n_arg"], case["n_direct"]
            taps = tap_list(case)
            t0 = time.perf_counter()
            _ = tap_list(case)              # prep mux (plan deja calcule)
            prep_mux_ms = (time.perf_counter() - t0) * 1e6   # microsecondes

            walls_d, walls_m = [], []
            ref = None
            for rep in range(REPS):
                ctr_d = {"cycles": 0, "src": 0, "dst": 0}
                t0 = time.perf_counter()
                banks_d = copy_direct(case, ctr_d)
                walls_d.append(time.perf_counter() - t0)

                ctr_m = {"cycles": 0, "src": 0, "dst": 0}
                t0 = time.perf_counter()
                banks_m = copy_mux(case, taps, ctr_m)
                walls_m.append(time.perf_counter() - t0)

                accepted(case, banks_d, banks_m)   # precondition d'acceptation
                cur = (dict(ctr_d), dict(ctr_m))
                if ref is None:
                    ref = cur
                else:
                    assert cur == ref, \
                        ("non determinisme inter-repetitions", rep, cur, ref)
                if rep == REPS - 1:
                    # les bancs de la derniere rep servent aux asserts
                    pass

            ctr_d, ctr_m = ref
            # assertions strictes (formules documentees)
            assert ctr_d["cycles"] == n_slots * 6, (ctr_d, n_slots)
            assert ctr_d["src"] == n_slots * 6 * 7, ctr_d
            assert ctr_m["cycles"] == (n_direct + l_arg) * 6, (ctr_m, case)
            assert ctr_m["src"] == (n_direct + l_arg + n_arg) * 6 * 7, ctr_m
            # spikes_DST : DYNAMIQUE MESUREE, pas de formule fermee — a
            # W=8 (clamp), un DST re-tire plusieurs fois par cycle (le
            # PSC decroit sous le seuil a travers la periode refractaire)
            # ; le comptage est deterministe et asserte entre repetitions
            assert ctr_d["dst"] > 0 and ctr_m["dst"] > 0, ctr_d
            # le cout analytique m3 retombe sur la mesure
            v1_a, mux_a = cm.count_emissions(n_slots, n_arg, l_arg)
            assert (v1_a, mux_a) == (n_slots, n_direct + l_arg)
            if n_bound > 1:
                assert ctr_m["cycles"] < ctr_d["cycles"], \
                    ("pas de gain temporel", n_bound, k_num)
            # spikes_DST : dynamique MESUREE, pas forcee
            # egale — les bancs mux traversent la chaine
            # sous tonique (demarrage chaud, 1er tir plus
            # precoce) vs bancs directs frais ; poids
            # finaux IDENTIQUES (asserte ci-dessus).

            rows.append({
                "n_bound": n_bound, "k_num": k_num, "l_arg": l_arg,
                "n_slots": n_slots, "n_arg": n_arg, "prep_mux_ms": prep_mux_ms,
                "d": {"cycles": ctr_d["cycles"], "src": ctr_d["src"],
                      "dst": ctr_d["dst"], "bancs": n_slots,
                      "wall": sorted(walls_d)[REPS // 2] * 1000.0},
                "m": {"cycles": ctr_m["cycles"], "src": ctr_m["src"],
                      "dst": ctr_m["dst"], "bancs": n_slots + 1,
                      "wall": sorted(walls_m)[REPS // 2] * 1000.0},
            })
            for mode, r in (("sequentiel", rows[-1]["d"]),
                            ("multiplexe", rows[-1]["m"])):
                bancs = r["bancs"]
                print("famille (n=%d, k=%d) l_arg=%-3d n_slots=%-4d"
                      " | %-10s cycles_theta=%-6d emissions_SRC=%-7d"
                      " spikes_DST=%-7d neurones=%-6d synapses=%-6d"
                      " bancs=%-4d wall=%.1f ms"
                      % (n_bound, k_num, l_arg, n_slots, mode,
                         r["cycles"], r["src"], r["dst"],
                         56 * bancs, 56 * bancs, bancs, r["wall"]))

    print()
    print("RESUME DES GAINS (cycles theta, simules — pas du wall-clock) :")
    print("  %-16s %10s %10s %8s" % ("famille", "sequentiel", "mux", "gain"))
    for r in rows:
        print("  (n=%d, k=%d) l_arg=%-3d %10d %10d %7.1fx"
              % (r["n_bound"], r["k_num"], r["l_arg"],
                 r["d"]["cycles"], r["m"]["cycles"],
                 r["d"]["cycles"] / r["m"]["cycles"]))
    print()
    print("notes honnetes :")
    print("  1. cycles_theta = temps SIMULE (fenetres x 6 cycles) — le")
    print("     wall_clock est l'overhead moteur, rapporte separement.")
    print("  2. baseline = NOTRE implementation sequentielle de reference")
    print("     (copie §2.8, une emission par occurrence) — pas le code")
    print("     des auteurs (aucun code public).")
    print("  3. le gating (quel tap ecoute dans quelle fenetre) et la")
    print("     composition/routage ring sont des preconditions partagees,")
    print("     exclues du delta de copie (identite d'objet verifiee) ;")
    print("     le cout fixe prep_mux = %.0f-%.0f us (harnais Python)."
          % (min(r["prep_mux_ms"] for r in rows),
             max(r["prep_mux_ms"] for r in rows)))
    print("  4. emissions_SRC litterales : mux = sequentiel + l' emission")
    print("     brute de la chaine (l_arg x 6 x 7) — dans une realisation")
    print("     physique, les relais de routage sont le meme spike arrive")
    print("     par les portes (pas de re-presentation) ; le gating neural")
    print("     (GATE_BOUND) est le jalon qui materialiserait ce gain.")
    print("  5. spikes_DST rapports tels quels : le travail d'apprentissage")
    print("     est le meme (poids finaux identiques, asserte) ; le petit ecart")
    print("     mesure vient du demarrage chaud des taps (tonique etabli pendant")
    print("     toute la chaine) vs bancs directs frais — documente, non force.")
    print()
    print("M4 VALIDE : egalite de sortie et de poids verifiee avant chaque")
    print("mesure, determinisme asserte, formules de comptage assertees.")

    # m5 : la mesure du GATE_BOUND neural (gated_chain.py, moteur py) —
    # les evenements SRC au MINIMUM theorique (l'emission brute de la
    # chaine seulement : les relais de routage du m4 deviennent du
    # cablage — compte ici comme ressource, pas comme emissions)
    print()
    print("M5 - GATE_BOUND neural (gated_chain, moteur py) :")
    print("  %-18s %7s %8s %8s %10s %8s" %
          ("famille", "cycles", "SRC", "DST", "cablage", "wall ms"))
    for n_occ, k_num in [(2, 2), (4, 4)]:   # le harnais py impose des
        # familles modestes (le m5 demontre le minimum, pas la montee)
        numeral = "(\\f. \\x. " + "f (" * k_num + "x" + ")" * k_num + ")"
        term = "(\\x. " + " ".join(["x"] * n_occ) + ") " + numeral
        cur = lb.parse(term)
        db = bd.to_debruijn(cur)
        toks = bd.to_tokens(db)
        rows = fv.rows_fix(db)
        K = bd.find_redex(cur)
        l_body = intg_body.IntgCircuit(toks, K,
                                       tau_m=1000.0).run()["pos"] + 1
        l_arg = intg_body.IntgCircuit(toks, K + l_body,
                                      tau_m=1000.0).run()["pos"] + 1
        body_end = K + 2 + l_body
        bound_abs = bind_gamma.truth_bound_indices(rows, K, body_end)
        bound_sh = {j: toks[j][1] - 1 - toks[K][1] for j in bound_abs}
        ring_mx = orc.ring_phase.PhaseRing()
        pats = cw.compose_cube(toks, rows, K, l_body, l_arg, bound_sh,
                               ring_mx)
        raw, groups = cm.arg_chain_plan(rows, K, l_body, l_arg, bound_sh)
        n_arg = len(raw) * len(groups)
        ctr_g = {"cycles": 0, "src": 0, "dst": 0}
        chain_g = gc.GatedChain(raw, groups, pats)
        t0 = time.perf_counter()
        chain_g.run(ctr=ctr_g)
        wall_g = (time.perf_counter() - t0) * 1000.0
        wiring = n_arg * len(raw) * 7          # tables de routage (56/canal)
        # acceptance : poids bit-exacts vs directs (py) + lecture fidele
        arg_slots = sorted(s for start, _sh in groups
                           for s in range(start, start + len(raw)))
        new_toks = orc.rewrite(toks, rows, K, l_body, l_arg, bound_sh)
        for s in arg_slots:
            direct = cm._new_bank("py", s)
            cm.learn_direct(direct, pats[s])
            assert cm.bank_weights(chain_g.taps[s]) == \
                cm.bank_weights(direct), \
                ("m5 : poids slot %d differents du v1" % s)
        read = []
        for s in range(len(pats)):
            if s in arg_slots:
                ph = chain_g.recall(s, pats[s])
            else:
                direct = cm._new_bank("py", s)
                cm.learn_direct(direct, pats[s])
                ph = direct.recall(cs.pattern_bits(pats[s]))
            act = sorted(k for k in range(56) if ph[k])
            chs = [None] * 7
            for k in act:
                g, v = divmod(k, 8)
                chs[g] = v
            read.append(cs.decode_pattern(tuple(chs)))
        assert read == new_toks, ("m5 : lecture infidele", term)
        # le minimum theorique : SRC = l'emission brute de la chaine
        assert ctr_g["src"] == len(raw) * 6 * 7, \
            (ctr_g, "SRC au-dessus du minimum")
        assert ctr_g["cycles"] == len(raw) * 6, ctr_g
        print("  (n=%d, k=%d) l_arg=%-3d  %7d %8d %8d %10d %8.1f"
              % (n_occ, k_num, l_arg, ctr_g["cycles"], ctr_g["src"],
                 ctr_g["dst"], wiring, wall_g))
    print("  (le cablage = les tables de routage n_arg x l_arg x 7 ;")
    print("  c'est la ressource que le mode evenements du m4 payait en")
    print("  emissions — le GATE_BOUND la transforme en cablage.)")

    # m5 : GATING NEURAL (GATE_BOUND, sessions C-D) — la chaine gatee :
    # UNE emission brute, projections ROUTEES reelles (cablage pose a la
    # creation depuis le ring) vers TOUS les taps, et une GATE LIF par
    # tap (§2.9 : courant d'armement pendant SA fenetre) qui selectionne
    # l'apprentissage. Les evenements SRC tombent au minimum theorique
    # (l'emission brute seulement) : les relais de routage du m4
    # deviennent du cablage. Differentiel : poids bit-exacts vs v1 +
    # lecture fidele, apres avoir traverse TOUTES les fenetres.
    import gated_chain as _gc
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
        chain_g = _gc.GatedChain(raw, groups, pats)
        chain_g.run()
        arg_slots = sorted(s for start, _sh in groups
                           for s in range(start, start + len(raw)))
        for s in arg_slots:
            direct = cm._new_bank("py", s)
            cm.learn_direct(direct, pats[s])
            assert cm.bank_weights(chain_g.taps[s]) == \
                cm.bank_weights(direct), \
                ("m5 : poids slot %d differents du v1" % s)
        read = []
        for s in range(len(pats)):
            if s in arg_slots:
                ph = chain_g.recall(s, pats[s])
            else:
                direct = cm._new_bank("py", s)
                cm.learn_direct(direct, pats[s])
                ph = direct.recall(cs.pattern_bits(pats[s]))
            act = sorted(k for k in range(56) if ph[k])
            chs = [None] * 7
            for k in act:
                g, v = divmod(k, 8)
                assert chs[g] is None, (s, "deux phases au canal")
                chs[g] = v
            read.append(cs.decode_pattern(tuple(chs)))
        assert read == orc.rewrite(toks, rows, K, l_body, l_arg,
                                   bound_sh), \
            ("m5 : lecture infidele", term_mx)
        print("  m5 gate neurale %-28s : %d taps traversent toutes les"
              " fenetres, poids + rappel EXACTS (GATE_BOUND)"
              % (term_mx, len(arg_slots)))


if __name__ == "__main__":
    main()
