# -*- coding: utf-8 -*-
"""Cube vivant v2 : les patterns du prochain cube sont COMPOSES depuis
les emissions du terme courant — plus aucun re-encodage du nouveau
terme (rows_fix / tokens_to_db ne participent plus a l'ecriture).

Provenance de chaque canal d'un slot destination :

  - token garde a l'identique (prefixe / suffixe) : pattern source
    emis par le token courant, copie tel quel (§2.8 : la copie copie
    l'emission) ;
  - token de l'ARGUMENT insere (self +sh, bind +sh si son binder est
    interne a l'argument, indice libre +sh si sa reference sort de
    l'argument) : le FINE vient de l'onde reelle de l'anneau (§2.7)
    et la RETENUE est comptee sur les rebouclages observes de la
    sequence de feux — l'evenement neural qui porte le registre
    COARSE (grille 1000/1000 de la session 9) ;
  - token du CORPS garde (v3c, neural=True — le DEFAUT production) :
    self et bind sortent du RE-SCAN NEURAL reel (rescan_circuit.
    RescanStack, sessions 18-24) — le compteur de profondeur ANCRE a
    d_lam produit self (l'ancrage EST le decrement KEEP : plus aucune
    regle -1 appliquee) et l'onde ordinale du bus BIND lit le lieur ;
    les regles KEEP canal-level §2.10.3 (neural=False) ne servent plus
    que de REFERENCE au differentiel, comme le re-encodage. SEULE
    EXCEPTION : l'indice -1 des VAR LIBRES reste applique par le
    meta-controleur (l'indice libre compte les lieurs au-dessus du
    corps, invisibles du scan) — meme statut que le §2.11 des auteurs ;
    le port libre neural est le jalon suivant.

Les DECISIONS de composition (qui est garde, qui recoit l'argument,
quels canaux sont shifts) viennent des circuits reels : K de DET,
l_body/l_arg de INTG, le masque des VAR lies de la liaison, les sh par
occurrence du ring. La comparaison d'adresse binder-interne/externe
(b >= dA) est une regle de routage du §2.10.3, au meme statut que le
tri topographique chez les auteurs.
"""

import bridge_db as bd
import cube_state as cs
import rescan_circuit as rc

LAM, APP = bd.LAM, bd.APP


def _dec(pair):
    """Decremente une profondeur codee (fine, coarse) : emprunt du canal
    fine sur le coarse. Jamais appele sur (0, 0) : les profondeurs
    decrementees (token du corps, binder sous le redex, indice libre du
    corps) sont toujours >= 1."""
    v, c = pair
    assert not (v == 0 and c == 0), "decrement de la profondeur 0"
    if v > 0:
        return (v - 1, c)
    return (7, c - 1)


def ring_shift(ring, pair, sh):
    """Shift +sh d'une profondeur codee (fine, coarse) PAR LE RING :
    le fine de destination est le feu ordinal sh de l'onde reelle, la
    retenue est le nombre de rebouclages observes dans la sequence de
    feux (evenement COARSE du papier §2.7)."""
    v, c = pair
    f, _t, _isi = ring.run(v, sh + 1)
    assert f[sh] == (v + sh) % 8, (v, sh, f[sh])
    carries = sum(1 for i in range(1, sh + 1) if f[i] < f[i - 1])
    assert carries == (v + sh) // 8, (v, sh, carries)
    return ((v + sh) % 8, (c + carries) % 8)


def _ty_of(tid):
    if tid >= 4:
        return cs.TY_VAR
    return cs.TY_LAM if tid == LAM else cs.TY_APP


def body_slot(row, d_lam):
    """Slot destination d'un token du CORPS garde (regle KEEP §2.10.3)."""
    tid, d, sf, sc, bf, bc, libre = row
    self2 = _dec((sf, sc))
    if tid < 4:
        return (self2[0], self2[1], 0, 0, _ty_of(tid), 0, 0)
    if libre:
        n2 = _dec(((tid - 4) % 8, ((tid - 4) // 8) % 8))
        return (self2[0], self2[1], 7, 7, cs.TY_VAR, n2[0], n2[1])
    b = bf + 8 * bc
    b2 = _dec((bf, bc)) if b > d_lam else (bf, bc)
    return (self2[0], self2[1], b2[0], b2[1], cs.TY_VAR, 0, 0)


def rescan_body(body_rows, d_lam, skip=()):
    """Specification executable du re-scan neural du corps du redex
    (v3, cf. docs/design_nested_scan.md). Sémantique événementielle du
    futur circuit : un scan préfixe avec

      - un compteur de profondeur ANCRE a d_lam (le lambda du redex a
        disparu : le corps pendait a d_lam+1, il pend a d_lam) — le
        decrement KEEP n'est PAS une operation sur les tokens, c'est
        l'ancrage du scan ;
      - une pile de niveaux ouverts, chacun avec son integrateur de
        balance (VAR +1, APP -1, LAM 0) : un niveau ferme quand son
        sigma franchit +1 (INTG_BODY §2.5, une instance par niveau —
        c'est le sens de « SCAN imbriques ») ; la fermeture rend au
        compteur la profondeur d'ouverture du niveau ;
      - les VAR lies au redex sont SKIPPES (remplaces par l'argument
        insere) : l'argument est un sous-terme complet, contribution
        +1 au sigma de tous les niveaux ouverts — comme le VAR
        remplace ; la balance du flux de sortie est preservee ;
      - un VAR garde lit son binder sur la pile : le (n+1)-ieme LAM
        depuis le sommet, a sa profondeur d'ouverture (deja decremente
        par l'ancrage) ; binder hors du corps (pas assez de LAMs dans
        la pile) : canaux BIND source inchanges ;
      - un VAR libre garde le code reserve (7,7) et emet son indice
        decremente d'un niveau d'environnement (port libre du
        contexte).

    Renvoie les patterns 7 canaux des tokens gardes, dans l'ordre du
    scan. Le circuit neural (compteur + pile d'INTG) sera juge
    spike-a-spike contre cette specification."""
    cur = d_lam
    stack = [["BODY", d_lam, 0]]           # (kind, depth_at_open, sigma)
    out = []
    for pos, row in enumerate(body_rows):
        tid, d, _sf, _sc, bf, bc, libre = row
        if pos in skip:
            for lv in stack:               # l'argument insere : +1
                lv[2] += 1
        else:
            sf_n, sc_n = cur % 8, (cur // 8) % 8
            if tid == bd.LAM:
                out.append((sf_n, sc_n, 0, 0, cs.TY_LAM, 0, 0))
                stack.append(["LAM", cur, 0])
                cur += 1
            elif tid == bd.APP:
                for lv in stack:           # l'APP : -1 partout ou il est
                    lv[2] -= 1
                out.append((sf_n, sc_n, 0, 0, cs.TY_APP, 0, 0))
                stack.append(["APP", cur, -1])
            else:
                n = tid - 4
                if libre:
                    n2 = _dec((n % 8, (n // 8) % 8))
                    pat = (sf_n, sc_n, 7, 7, cs.TY_VAR, n2[0], n2[1])
                else:
                    b_new = None
                    lam_seen = 0
                    for lv in reversed(stack):
                        if lv[0] == "LAM":
                            if lam_seen == n:
                                b_new = lv[1]
                                break
                            lam_seen += 1
                    if b_new is None:      # binder hors du corps
                        pat = (sf_n, sc_n, bf, bc, cs.TY_VAR, 0, 0)
                    else:
                        pat = (sf_n, sc_n, b_new % 8, (b_new // 8) % 8,
                               cs.TY_VAR, 0, 0)
                for lv in stack:           # le VAR : enfant complet, +1
                    lv[2] += 1
                out.append(pat)
        while stack and stack[-1][2] == 1: # fermetures en cascade
            cur = stack.pop()[1]
    assert not stack, "le corps entier doit se fermer au dernier token"
    assert len(out) == len(body_rows) - len(skip)
    return out


def arg_slot(ring, row_arg, sh, d_arg_root):
    """Slot destination d'un token de l'ARGUMENT insere a la place d'un
    VAR lie : self +sh par le ring ; bind +sh si le binder est interne
    a l'argument, inchange sinon ; VAR libre : indice +sh (le shift de
    De Bruijn standard a l'insertion). Pour un VAR lie, l'indice reste
    recouvrable des canaux binder (n = d - 1 - b), canaux 5-6 = 0."""
    tid, d, sf, sc, bf, bc, libre = row_arg
    self2 = ring_shift(ring, (sf, sc), sh)
    if tid < 4:
        return (self2[0], self2[1], 0, 0, _ty_of(tid), 0, 0)
    if libre:
        n2 = ring_shift(ring, ((tid - 4) % 8, ((tid - 4) // 8) % 8), sh)
        return (self2[0], self2[1], 7, 7, cs.TY_VAR, n2[0], n2[1])
    b = bf + 8 * bc
    if b >= d_arg_root:                    # binder interne a l'argument
        b2 = ring_shift(ring, (bf, bc), sh)
        return (self2[0], self2[1], b2[0], b2[1], cs.TY_VAR, 0, 0)
    return (self2[0], self2[1], bf, bc, cs.TY_VAR, 0, 0)


def _neural_slot(row, kind, cur, b):
    """Slot destination d'un token du CORPS garde depuis les SORTIES du
    re-scan neural (v3c) : self = compteur ANCRE (l'ancrage est le
    decrement KEEP — plus aucune regle -1), bind = profondeur lue par
    l'onde ordinale du bus BIND (None : binder hors du corps, canaux
    source inchanges ; libre : (7,7) + indice decremente — la SEULE
    regle KEEP encore meta-controlee, cf. docstring d'en-tete)."""
    tid, _d, _sf, _sc, bf, bc, libre = row
    self2 = (cur % 8, (cur // 8) % 8)
    if kind == "LAM":
        return (self2[0], self2[1], 0, 0, cs.TY_LAM, 0, 0)
    if kind == "APP":
        return (self2[0], self2[1], 0, 0, cs.TY_APP, 0, 0)
    if libre:
        n2 = _dec(((tid - 4) % 8, ((tid - 4) // 8) % 8))
        return (self2[0], self2[1], 7, 7, cs.TY_VAR, n2[0], n2[1])
    if b is None:                          # binder hors du corps
        return (self2[0], self2[1], bf, bc, cs.TY_VAR, 0, 0)
    return (self2[0], self2[1], b % 8, (b // 8) % 8, cs.TY_VAR, 0, 0)


def compose_cube(toks, rows, K, l_body, l_arg, bound_sh, ring,
                 neural=False, stack_factory=None):
    """Les patterns 7 canaux des slots du prochain cube, dans l'ordre
    topographique (§2.10.3) : prefixe garde, corps (avec insertion de
    l'argument aux positions des VAR lies), suffixe garde. Aucune
    reconstruction du terme : seules les emissions du terme courant
    (patterns sources) et le ring sont consommees.

    neural=False : le corps passe par les regles KEEP canal-level
    (§2.10.3, body_slot) — la REFERENCE du differentiel. neural=True
    (v3c, DEFAUT production via orchestrate) : le corps est RE-SCANNE
    par le circuit reel (RescanStack, sessions 18-24) — les self/bind
    des tokens gardes sortent du compteur ancre et du bus BIND, plus
    aucune regle -1 appliquee par le meta-controleur (excepte l'indice
    libre, cf. docstring d'en-tete). stack_factory permet d'injecter
    une fabrique alternative (meme convention que net_factory)."""
    d_lam = toks[K + 1][1]
    d_ref = toks[K][1]
    d_arg_root = toks[K + 2 + l_body][1]
    assert d_arg_root == d_ref             # l'argument est sous l'APP
    body_end = K + 2 + l_body
    slots = []
    for j in range(K):                     # prefixe : copie directe
        slots.append(cs.slot_pattern_from_row(rows[j]))
    body_rows = rows[K + 2:body_end]
    skip = {j - (K + 2) for j in bound_sh}
    if neural:
        # v3c : re-scan NEURAL du corps — le meme flux que le banc
        # run_rescan (SKIP aux positions des VAR lies, l'argument
        # insere par le ring a leur place)
        stack = (stack_factory or rc.RescanStack)(d_lam,
                                                  max_tokens=len(body_rows))
        for pos, row in enumerate(body_rows):
            tid = row[0]
            if pos in skip:
                stack.feed("SKIP")
                sh = bound_sh[pos + K + 2]
                for jj in range(body_end, body_end + l_arg):
                    slots.append(arg_slot(ring, rows[jj], sh, d_arg_root))
            else:
                if tid >= 4:
                    kind, binder_n = "VAR", tid - 4
                elif tid == bd.LAM:
                    kind, binder_n = "LAM", None
                else:
                    kind, binder_n = "APP", None
                cur, b = stack.feed(kind, binder_n)
                slots.append(_neural_slot(row, kind, cur, b))
        assert stack.levels == [], "le corps doit fermer au dernier token"
    else:
        for pos, row in enumerate(body_rows):  # reference KEEP §2.10.3
            if pos in skip:
                sh = bound_sh[pos + K + 2]
                for jj in range(body_end, body_end + l_arg):
                    slots.append(arg_slot(ring, rows[jj], sh, d_arg_root))
            else:
                slots.append(body_slot(row, d_lam))
    for j in range(body_end + l_arg, len(rows)):   # suffixe : copie directe
        slots.append(cs.slot_pattern_from_row(rows[j]))
    return slots
