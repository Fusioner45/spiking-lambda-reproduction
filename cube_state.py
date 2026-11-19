# -*- coding: utf-8 -*-
"""Chantier « cube STDP comme etat vivant » (revue ChatGPT, addendum
session 14 octies) : le prochain cube est ECRIT par les circuits de
copie (§2.8) et LU par rappel, au lieu d'etre un re-encodage
symbolique verifie en parallele.

Encodage d'un slot : pattern a 7 canaux x 8 phases = 56 bits.
  canaux 0-1 : SELF (profondeur du token) — le papier §2.2 ;
  canaux 2-3 : BIND (profondeur du binder) — le papier §2.2 ; pour un
               VAR libre, le code reserve (7,7) du fix variables libres ;
  canal 4    : TYPE du token. Chez les auteurs l'identite LAM/APP/VAR
               est portee par des populations distinctes (§2.1) ; nous
               l'integrons au pattern pour que la lecture du cube soit
               purement dynamique (rappel -> decode), sans etat
               symbolique entre la memoire et l'etape suivante ;
  canaux 5-6 : indice de la variable libre (VAR libre seulement, 0
               sinon). Pour un VAR lie l'indice est deja recouvrable
               des canaux BIND : b = bf + 8*bc, n = d - 1 - b (pile la
               structure de la pile des LAM ancetres, phase_table).

Fenetre d'encodage : 64 codes par canal, comme le papier (profondeurs
et indices modulo 64 ; le fix variables libres borne les profondeurs
utiles a 62).

Lecture (recall) : on rejoue l'emission source (le SCAN §2.10) et on
observe la destination — celle-ci ne fire que sur les poids APPRIS
(W_0 = 3.5 -> EPSP 0.48 < 1, silence ; W = 8 -> 1.10 > 1, feu), donc
le contenu lu vient bien de la memoire STDP, pas du replay. Toute
corruption d'un poids appris rend un canal muet -> la lecture detecte
l'incompletude (teste par sabotage dans run_cube.py).

Frontiere honnete (meme statut que le §2.11 du papier) : l'ADRESSAGE
des ecritures — quel slot recoit quel token, tri topographique
§2.10.3 — reste le metagestionnaire Python, comme chez les auteurs ;
le CONTENU de chaque slot, lui, vit dans les poids STDP. La
des-symbolisation de l'adressage (SCAN imbriques reels, item 3 du
backlog) est le chantier suivant.
"""

import bridge_db as bd
import free_vars_fix as fv
import copy_stdp
import snn_core

N_CH = 7
N_BITS = N_CH * 8

TY_LAM, TY_APP, TY_VAR = 0, 1, 2


def slot_pattern(tid, d, bf, bc, libre):
    """Pattern 56 bits d'un token : un canal actif par groupe de 8."""
    n = tid - 4
    if tid >= 4 and libre:
        return (d % 8, (d // 8) % 8, fv.RESERVED[0], fv.RESERVED[1],
                TY_VAR, n % 8, (n // 8) % 8)
    if tid >= 4:
        return (d % 8, (d // 8) % 8, bf, bc, TY_VAR, 0, 0)
    ty = TY_LAM if tid == bd.LAM else TY_APP
    return (d % 8, (d // 8) % 8, bf, bc, ty, 0, 0)


def slot_pattern_from_row(row):
    """Depuis une ligne de fv.rows_fix (tid, d, sf, sc, bf, bc, libre)."""
    tid, d, _sf, _sc, bf, bc, libre = row
    return slot_pattern(tid, d, bf, bc, libre)


def pattern_bits(pattern):
    """7 phases -> indices de bits actifs (canal g, phase v -> g*8+v)."""
    return [g * 8 + v for g, v in enumerate(pattern)]


def decode_pattern(phases):
    """(id, depth) depuis les 7 phases lues. Leve ValueError si le
    pattern lu est incomplet (canal muet) — c'est la detection de
    corruption du cube."""
    f0, f1, f2, f3, ty, f5, f6 = phases
    if None in phases:
        raise ValueError("cube corrompu : canal muet %s" % (phases,))
    d = f0 + 8 * f1
    if ty == TY_VAR:
        if (f2, f3) == fv.RESERVED:
            return (bd.VAR(f5 + 8 * f6), d)
        return (bd.VAR(d - 1 - (f2 + 8 * f3)), d)
    if ty == TY_LAM:
        return (bd.LAM, d)
    return (bd.APP, d)


class CubeState:
    """Le prochain cube comme etat vivant : UN canal de copie STDP par
    slot (pas de deduplication — les slots sont des adresses), ecrit
    par apprentissage (6 cycles theta), lu par rappel."""

    def __init__(self, engine="c"):
        self.engine = engine
        self.slots = []              # (pattern source, instance copie)

    def write(self, slot, pattern):
        assert len(pattern) == N_CH and slot == len(self.slots)
        if self.engine == "c":
            b = snn_core.CopyC(n=N_BITS, i_theta=0.75)
        else:
            b = copy_stdp.CopyBench(n=N_BITS, i_theta=0.75, seed=slot + 1)
        b.learn(pattern_bits(pattern))
        self.slots.append((pattern, b))

    def _read_phases(self, slot):
        src, b = self.slots[slot]
        fired = b.recall(pattern_bits(src))
        act = sorted(k for k in range(N_BITS) if fired[k])
        if len(act) != N_CH:
            raise ValueError("cube corrompu : %d canaux lus au lieu de %d"
                             % (len(act), N_CH))
        phases = [None] * N_CH
        for k in act:
            ch, v = divmod(k, 8)
            assert phases[ch] is None, "deux phases actives au canal %d" % ch
            phases[ch] = v
        return tuple(phases)

    def read(self, slot):
        """Token (id, depth) du slot, lu dans la memoire STDP."""
        return decode_pattern(self._read_phases(slot))

    def read_all(self):
        """Le cube entier, en ordre topographique (ordre des slots)."""
        return [self.read(s) for s in range(len(self.slots))]
