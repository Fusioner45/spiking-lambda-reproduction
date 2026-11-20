# -*- coding: utf-8 -*-
"""Multiplexage de la copie de l'argument (item 3, m1/m2/m3).

AUJOURD'HUI (v1-v3c) : chaque occurrence d'un VAR lie declenche la copie
COMPLETE de l'argument — n_bound x l_arg emissions theta (§2.8, une
sequence d'apprentissage par slot). Le papier §2.10.2 (nested
SCANs) cree UNE chaine pos_arg PAR occurrence ; notre mode
multiplexe : UNE chaine
temporelle PARTAGEE par toutes les occurrences (architecture
alternative repondant au cout du schema §2.10.2) — UNE chaine
temporelle pos_arg de longueur l_arg, et chaque occurrence y puise par
adressage temporel depuis GATE_BOUND.

m1 (ce module) : la chaine = UNE sequence de fenetres theta (une par
token de l'argument, 6 cycles chacune) pendant laquelle TOUS les taps
(bancs destination) apprennent leur pattern route EN PARALLELE — le
cout d'emission tombe de n_bound x l_arg a l_arg fenetres. Le routage
brut -> shifte de chaque tap est porte par le RING reel (arg_slot /
ring_shift : le fine de destination est le feu ordinal de l'onde, la
retenue est comptee sur les rebouclages observes) — le meme mecanisme
que la composition v2. Le GATING (quel tap ecoute dans quelle fenetre)
reste meta-controleur pour m1 (statut §2.11, cf. note de conception §5).

Memoire : un banc STDP par slot destination, INCHANGE par construction
(les slots sont des adresses) — l'economie porte sur l'EMISSION, la
ressource temporelle partagee, pas sur la memoire.

m2 : l'invariance — l'ordre d'interleaving des taps ne change ni les
poids appris ni les temps de spike du rappel (banc differentiel,
run_cube.py).
m3 : la mesure n_bound x l_arg -> l_arg sur la famille
(\\x. x^n) (numeral k) (run_cube.py).
"""

import copy_stdp
import snn_core
import cube_state as cs

N_BITS = cs.N_BITS


def _new_bank(engine, seed, n_steps_alloc=None):
    """Un banc de copie. La CHAINE a besoin d'une capacite d'evenements
    etendue (l_arg fenetres de 6 cycles) — les bancs d'ecriture directe
    gardent la capacite par defaut (un learn + un rappel)."""
    if engine == "c":
        return snn_core.CopyC(n=N_BITS, i_theta=0.75,
                              n_steps_alloc=n_steps_alloc)
    return copy_stdp.CopyBench(n=N_BITS, i_theta=0.75, seed=seed + 1)


def bank_weights(bank):
    """Poids des N paires plastiques du banc (les deux moteurs)."""
    if hasattr(bank, "weights"):
        return bank.weights()
    return list(bank.w)


def arg_chain_plan(rows, K, l_body, l_arg, bound_sh):
    """Plan de chaine pour une etape : les patterns BRUTS de l'argument
    (l'emission unique de la chaine) et les groupes de slots destination
    (un par occurrence : l_arg slots topographiques consecutifs a la
    place du VAR lie). Le patterns ROUTES de chaque groupe sont ceux de
    la composition (slot_pats), deja calcules par le ring reel."""
    body_end = K + 2 + l_body
    raw = [cs.slot_pattern_from_row(rows[body_end + i])
           for i in range(l_arg)]
    groups = []
    s = K                                   # le prefixe occupe K slots
    for j in range(K + 2, body_end):
        if j in bound_sh:
            groups.append((s, bound_sh[j]))
            s += l_arg                      # l'argument insere ici
        else:
            s += 1                          # token du corps garde
    assert s == K + (l_body - len(groups)) + l_arg * len(groups)
    return raw, groups


def learn_direct(bank, pattern):
    """Ecriture directe v1 (6 cycles theta, une emission par slot)."""
    bank.learn(cs.pattern_bits(pattern))


def learn_counted(bank, pattern, ctr, engine):
    """Ecriture directe v1 AVEC comptage m4 — MEMES mecaniques que
    learn (meme schedule, meme pas, meme tonique), le comptage se fait
    au harnais : cycles executes, evenements SRC programmes, spikes DST
    decales (definitions et fenetres : run_multiplex.py)."""
    bits = cs.pattern_bits(pattern)
    steps_per_cycle = int(round(copy_stdp.CYCLE_MS / copy_stdp.DT))
    if engine == "c":
        n0 = snn_core._LIB.cp_n_spikes(bank.h)
        bank.learn(bits)                    # mecanique v1 inchangee
        ctr["cycles"] += copy_stdp.N_CYCLES
        ctr["src"] += copy_stdp.N_CYCLES * len(bits)
        ctr["fanin"] += copy_stdp.N_CYCLES * len(bits)
        ctr["dst"] += snn_core._LIB.cp_n_spikes(bank.h) - n0
    else:
        for _c in range(copy_stdp.N_CYCLES):
            for k in bits:
                bank.schedule_src(k, copy_stdp.SRC_OFFSET_MS)
                ctr["src"] += 1
                ctr["fanin"] += 1
            for _ in range(steps_per_cycle):
                ctr["dst"] += len(bank.step(True))
            ctr["cycles"] += 1


def run_chain(raw, taps, engine="py", bank_hook=None, ctr=None):
    """LA chaine : l_arg fenetres de 6 cycles ; l'emetteur brut tire les
    evenements du token i dans la fenetre i (UNE emission par token, a
    CHAQUE cycle comme le learn v1), et chaque tap apprend son pattern
    route pendant LES MEMES cycles (tous les bancs avancent en pas de
    temps partages — les traces/weights sont par banc, l'entrelacement
    n'a donc aucun effet : c'est l'invariance m2, verifiee par banc).

    LE GATING (m4) : taps = liste (slot, pattern_route, fenetre) — le
    tap n'est programme que pendant SA fenetre (celle du token qu'il
    destine ; c'est le role de GATE_BOUND §2.10.2, porte ici par la donnee
    de fenetre, statut meta-controleur). Avant le m4, le tap re-recevait
    son pattern a CHAQUE fenetre : poids finaux inchanges (clamp W=8)
    mais flux SRC gonfle x l_arg et adressage temporel viole — detecte
    par les assertions de formules du banc m4.

    L'EMETTEUR est une source d'emission pure : ses DST sont maintenus
    sans tonique (silencieuses, aucun apprentissage parasite) — seul le
    flux SRC de la chaine compte.

    L'ordre de creation des taps est libre (m2). bank_hook(bank, slot,
    pattern) : appele UNE fois par banc apres la fin de la chaine (le
    sabotage in-loop de run_cube passe par la). ctr : dict optionnel
    {"cycles", "src", "dst"} — comptage m4 (definitions :
    run_multiplex.py). Renvoie {slot: bank}."""
    steps_per_cycle = int(round(copy_stdp.CYCLE_MS / copy_stdp.DT))
    offset_steps = int(round(copy_stdp.SRC_OFFSET_MS / copy_stdp.DT))
    n_cycles = copy_stdp.N_CYCLES
    by_window = {}
    for s, pat, w in taps:
        assert 0 <= w < len(raw), ("fenetre hors chaine", s, w)
        by_window.setdefault(w, []).append((s, pat))
    # capacite etendue pour la chaine : l_arg fenetres de 6 cycles +
    # un rappel + marge (les evenements sont indexes en pas ABSOLUS)
    alloc = len(raw) * n_cycles * steps_per_cycle \
        + int(round(copy_stdp.CYCLE_MS * 3 / copy_stdp.DT)) + 128
    banks = {}
    for s, _pat, _w in taps:                # l'ordre de creation est libre
        banks[s] = _new_bank(engine, s, n_steps_alloc=alloc)
    chain = _new_bank(engine, -1, n_steps_alloc=alloc)  # emetteur brut
    if engine == "c":
        t0 = 0                              # horloge globale (pas absolus)
        for i, raw_pat in enumerate(raw):
            raw_bits = cs.pattern_bits(raw_pat)
            taps_i = by_window.get(i, [])
            for c in range(n_cycles):       # SRC a CHAQUE cycle (v1)
                for k in raw_bits:          # l'emission brute, UNE fois
                    snn_core._LIB.cp_schedule_src(
                        chain.h, k, t0 + c * steps_per_cycle + offset_steps)
                    if ctr is not None:
                        ctr["src"] += 1
                for s, pat in taps_i:       # les taps de CETTE fenetre
                    for k in cs.pattern_bits(pat):
                        snn_core._LIB.cp_schedule_src(
                            banks[s].h, k,
                            t0 + c * steps_per_cycle + offset_steps)
                        if ctr is not None:
                            ctr["src"] += 1
                            ctr["fanin"] += 1
            n0_chain = snn_core._LIB.cp_n_spikes(chain.h)
            snn_core._LIB.cp_run(chain.h, n_cycles * steps_per_cycle, 0)
            if ctr is not None:
                ctr["dst"] += snn_core._LIB.cp_n_spikes(chain.h) - n0_chain
            chain._k += n_cycles * steps_per_cycle
            for s, _pat, _w in taps:
                n0 = snn_core._LIB.cp_n_spikes(banks[s].h)
                snn_core._LIB.cp_run(banks[s].h,
                                     n_cycles * steps_per_cycle, 1)
                if ctr is not None:
                    ctr["dst"] += snn_core._LIB.cp_n_spikes(banks[s].h) - n0
                banks[s]._k += n_cycles * steps_per_cycle
            if ctr is not None:
                ctr["cycles"] += n_cycles
            t0 += n_cycles * steps_per_cycle
    else:
        for i, raw_pat in enumerate(raw):   # fenetres successives
            raw_bits = cs.pattern_bits(raw_pat)
            taps_i = by_window.get(i, [])
            for _c in range(n_cycles):      # SRC a CHAQUE cycle (v1)
                for k in raw_bits:          # l'emission brute, UNE fois
                    chain.schedule_src(k, copy_stdp.SRC_OFFSET_MS)
                    if ctr is not None:
                        ctr["src"] += 1
                for s, pat in taps_i:       # les taps de CETTE fenetre
                    for k in cs.pattern_bits(pat):
                        banks[s].schedule_src(k, copy_stdp.SRC_OFFSET_MS)
                        if ctr is not None:
                            ctr["src"] += 1
                            ctr["fanin"] += 1
                for _ in range(steps_per_cycle):   # pas de temps PARTAGES
                    if ctr is not None:
                        ctr["dst"] += len(chain.step(False))
                        for s, _pat, _w in taps:
                            ctr["dst"] += len(banks[s].step(True))
                    else:
                        chain.step(False)
                        for s, _pat, _w in taps:
                            banks[s].step(True)
                if ctr is not None:
                    ctr["cycles"] += 1
    if bank_hook is not None:
        for s, pat, _w in taps:             # UNE fois par banc, apres la
            bank_hook(banks[s], s, pat)     # chaine (sabotage in-loop)
    return banks


def build_cube(slot_pats, raw, groups, engine="py", bank_hook=None):
    """Cube vivant avec copie multiplexee : slots hors argument en
    ecriture directe v1, slots d'argument appris par les taps pendant
    UNE chaine. L'ordre des slots reste topographique (lecture v1
    inchangee). Renvoie un CubeState equivalent a l'ecriture directe
    (verifie par le differentiel de run_cube.py)."""
    n_slots = len(slot_pats)
    arg_slots = set()
    for start, _sh in groups:
        arg_slots.update(range(start, start + len(raw)))
    cube = cs.CubeState(engine=engine)
    banks = [None] * n_slots
    for s in range(n_slots):                # ecriture directe v1 (hors arg)
        if s not in arg_slots:
            banks[s] = _new_bank(engine, s)
            learn_direct(banks[s], slot_pats[s])
            if bank_hook is not None:
                bank_hook(banks[s], s, slot_pats[s])
    taps = [(start + i, slot_pats[start + i], i)
            for start, _sh in groups for i in range(len(raw))]
    chain_banks = run_chain(raw, taps, engine=engine, bank_hook=bank_hook)
    for s, b in chain_banks.items():
        banks[s] = b
    cube.slots = [(slot_pats[s], banks[s]) for s in range(n_slots)]
    return cube


def count_emissions(n_slots, n_arg_slots, l_arg):
    """Cout d'emission (m3) : ecritures directes v1 vs chaine.
    v1 : une emission par slot. Chaine : les slots hors argument + les
    l_arg fenetres de la chaine (tous les taps partages)."""
    v1 = n_slots
    mux = (n_slots - n_arg_slots) + l_arg
    return v1, mux
