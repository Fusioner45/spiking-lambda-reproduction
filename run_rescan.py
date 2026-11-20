# -*- coding: utf-8 -*-
r"""Banc v3a+v3b-1 : la pile d'INTG LIF du re-scan
(rescan_circuit.RescanStack) validee contre la specification executable
rescan_body (cube_write.py) sur la batterie — le circuit est juge
token-par-token contre cette spec, comme le moteur C contre son
prototype Python.

Deux modes de gating, traces identiques attendus :
  - 'selective' (v3a) : ports par niveau, injection selective ;
  - 'global' (v3b-1) : ports VAR/APP GLOBAUX connectes a tous les INTG
    au push, coupure par refractaire long au discharge — chaque INTG
    decharge au plus UNE fois (verifie).

Calibrage : tau_m = 1000 ms / W_CNT = 1/epsilon(tau_m, 1) (finding n°8 :
les niveaux externes de la pile restent sous le seuil pendant la
traversee des sous-termes internes ; les 300 ms du papier derivent).

Edge case du banc : (\x. f (x y)) z — sur le dernier token, les INTG
APP2, APP1 et BODY franchissent +1 au MEME slot : trois fermetures
simultanees, chacune projetee independamment (pas de « -1 par slot
actif »). Le terme (\x. (\\y. x (y x))) I pousse jusqu'a quatre
fermetures simultanees (APP2, APP1, LAM, BODY).
"""

import lambda_beta as lb
import bridge_db as bd
import free_vars_fix as fv
import cube_write as cw
import intg_body
import bind_gamma
import rescan_circuit as rc

two = "\\f. \\x. f (f x)"
three = "\\f. \\x. f (f (f x))"
eye = "\\x. x"
plus = "\\m. \\n. \\f. \\x. m f (n f x)"

TERMS = [
    "(%s) (%s)" % (eye, eye),
    "(%s) (%s)" % (two, eye),
    "(%s) (%s) (%s)" % (plus, two, three),
    "(\\x. x y) z",
    "(\\x. z) (%s)" % eye,
    "(\\x. (\\y. y x)) (%s)" % eye,
    "(\\x. (\\y. x (y x))) (%s)" % eye,
    "(\\x. f (x y)) z",            # fermetures simultanees APP2/APP1/BODY
]


def run_battery(gating):
    """Differentiel circuit vs spec sur toute la batterie. Renvoie
    (total_steps, total_tokens, max_simul, max_closes, binder_stats)."""
    total_tokens = 0
    total_steps = 0
    max_simul = 0
    max_closes = 0
    b_stats = {"interne": 0, "hors-corps": 0, "libre": 0}
    for term in TERMS:
        cur_term = lb.parse(term)
        for step in range(12):
            db = bd.to_debruijn(cur_term)
            toks = bd.to_tokens(db)
            rows = fv.rows_fix(db)
            K = bd.find_redex(cur_term)
            if K == -1:
                break
            l_body = intg_body.IntgCircuit(toks, K).run()["pos"] + 1
            l_arg = intg_body.IntgCircuit(toks, K + l_body).run()["pos"] + 1
            body_end = K + 2 + l_body
            bound_abs = bind_gamma.truth_bound_indices(rows, K, body_end)
            d_lam = toks[K + 1][1]
            body_rows = rows[K + 2:body_end]
            skip = {j - (K + 2) for j in bound_abs}

            # spec (semantique evenementielle)
            spec = cw.rescan_body(body_rows, d_lam, skip)
            # circuit LIF : meme flux de tokens
            stack = rc.RescanStack(d_lam, gating=gating,
                                   max_tokens=len(body_rows))
            gi = 0
            for pos, row in enumerate(body_rows):
                tid = row[0]
                if pos in skip:
                    kind = "SKIP"
                elif tid >= 4:
                    kind = "VAR"
                elif tid == bd.LAM:
                    kind = "LAM"
                else:
                    kind = "APP"
                binder_n = (tid - 4) if kind == "VAR" else None
                cur, b_circuit = stack.feed(kind, binder_n)
                if kind != "SKIP":
                    self_spec = spec[gi][0] + 8 * spec[gi][1]
                    assert cur == self_spec, \
                        (term, step + 1, pos, cur, self_spec)
                if kind == "VAR":
                    # lecture v3b-2 du canal BIND depuis l'etat de la pile
                    _tid, _d, _sf, _sc, bf, bc, libre = row
                    b_src = bf + 8 * bc
                    if libre:
                        assert b_circuit is None, (term, "libre: pile muette")
                        assert (spec[gi][2], spec[gi][3]) == (7, 7)
                        b_stats["libre"] += 1
                    elif b_src > d_lam:
                        # binder interne : le (n+1)-ieme LAM actif, a sa
                        # profondeur d'ancrage (= b_src - 1)
                        if b_circuit != b_src - 1:
                            # anti-boucle : UN diagnostic, arret propre
                            print("ECHEC lecture binder :")
                            print("  terme=%s slot=%d binder_n=%d "
                                  "-> b=%s (attendu %d)"
                                  % (term, pos, binder_n, b_circuit,
                                     b_src - 1))
                            print("  reponses (t, depth) : %s"
                                  % (stack.last_responses,))
                            print("  sondes GATE (id, depth, actif, "
                                  "V_avant_onde, V_pic, spiked) :")
                            for rec in stack.last_gate_vs:
                                print("    %s" % (rec,))
                            print("  spikes du slot (t, label), "
                                  "POS inclus — deja collectes :")
                            for t_s, label in stack.last_slot_spikes:
                                print("    %.1f %s" % (t_s, label))
                            raise SystemExit(1)
                        assert spec[gi][2] + 8 * spec[gi][3] == b_src - 1
                        b_stats["interne"] += 1
                    else:
                        # binder hors du corps : pile muette, BIND source
                        assert b_circuit is None, (term, "hors corps")
                        assert (spec[gi][2], spec[gi][3]) == (bf, bc)
                        b_stats["hors-corps"] += 1
                if kind != "SKIP":
                    gi += 1
            assert stack.levels == [], (term, "BODY doit fermer au dernier")
            for lv in stack.all:
                assert lv["closes"] == 1, (term, gating, lv)
                max_closes = max(max_closes, lv["closes"])
            max_simul = max(max_simul, stack.last_closures)
            total_tokens += len(spec)
            total_steps += 1
            cur_term, _ = lb.beta_step(cur_term)
    return total_steps, total_tokens, max_simul, max_closes, b_stats


def main():
    print("=" * 64)
    print("PILE D'INTG DU RE-SCAN (v3a + v3b-1) - circuit LIF vs spec")
    print("=" * 64)

    # 0. test unitaire du AND asymptotique (fix session 21) : un GATE
    #    arme 500 ms SANS onde reste muet (l'asymptote du train PERSIST
    #    ne franchit pas le seuil), puis l'onde a t~500 ms fait fire
    #    EXACTEMENT une fois
    stack = rc.RescanStack(0.0, gating="global", max_tokens=4)
    stack.feed("LAM")                      # un lieur arme
    lam = [lv for lv in stack.all if lv["kind"] == "LAM"][0]
    g_idx = lam["gate"]
    steps = int(round(stack.slot_ms / stack.dt))
    n_before = 0
    for _ in range(int(round(500.0 / stack.slot_ms))):  # ~500 ms sans onde
        for _t, idx in stack.net.bulk_run(steps):
            if idx == g_idx:
                n_before += 1
    assert n_before == 0, \
        "le GATE arme 500 ms doit rester muet (calibrage asymptotique)"
    # ondes aux horloges REELLES du reseau (independantes de SLOT_MS) :
    # onde 1 = 1 slot + 0.6 apres l'armement (meme offset que t_query) ;
    # onde 2 = 1 slot apres l'onde 1 — le reset post-spike a vide le
    # GATE ; le tonique ne recharge qu'a ~0.40 : le saut d'onde 0.78
    # doit faire fire quand meme (le cas des 2 VAR consecutifs)
    t_arm = stack.net.k_step * stack.dt
    t_w1 = t_arm + stack.slot_ms + 0.6
    t_w2 = t_w1 + stack.slot_ms
    stack.net.inject_spike(lam["pq"], t_w1)
    stack.net.inject_spike(lam["pq"], t_w2)
    fires = []
    for _ in range(4):
        for _t, idx in stack.net.bulk_run(steps):
            if idx == g_idx:
                fires.append(_t)
    assert len(fires) == 2, \
        "2 ondes = 2 fires exactement (recus : %s)" % (fires,)
    assert t_w1 <= fires[0] < t_w2 and fires[1] >= t_w2, \
        "un fire par onde, dans l'ordre (recus : %s)" % (fires,)
    print("  AND asymptotique : 0 spike sur 500 ms arme ; 2 ondes "
          "separees de 1 slot = 2 fires (t=%.1f, t=%.1f) — OK"
          % (fires[0], fires[1]))

    # 1. v3a : injection selective par niveau
    st, tk, simul, _c, bs = run_battery("selective")
    print("  v3a  selective : %d etapes, %d tokens, profondeur + binders "
          "exactes ; fermetures simultanees max = %d" % (st, tk, simul))

    # 2. v3b-1 : injection GLOBALE + coupure par refractaire long :
    #    chaque INTG decharge AU PLUS une fois (max_closes <= 1)
    st2, tk2, simul2, mc, _ = run_battery("global")
    print("  v3b  global    : %d etapes, %d tokens, profondeur + binders "
          "exactes ; fermetures simultanees max = %d ; decharges/INTG = %d "
          "(coupure OK)" % (st2, tk2, simul2, mc))
    assert mc == 1, "le refractaire long doit rendre chaque INTG sourd \
        apres son discharge"
    assert (st, tk, simul) == (st2, tk2, simul2), "les deux modes doivent \
        produire les memes traces"

    print()
    print("PILE RE-SCAN VALIDEE : %d etapes, %d tokens gardes, "
          "profondeur + binders exacts dans les deux modes" % (st, tk))
    print("binders lus sur l'etat de la pile : %d internes, %d hors corps, "
          "%d libres (detection automatique par pile muette)"
          % (bs["interne"], bs["hors-corps"], bs["libre"]))
    print("fermetures simultanees max observees sur un slot : %d "
          "(sommee, pas « -1 par slot »)" % simul)
    assert simul >= 3, "le cas limite des fermetures simultanees doit \
        etre exerce par la batterie"


if __name__ == "__main__":
    main()
