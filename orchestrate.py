# -*- coding: utf-8 -*-
"""Mini-lab, palier final : orchestration de l'Algorithme 1 — la boucle
fermee.

Architecture (fidele aux limites que se fixe le papier lui-meme, §2.11 :
« Python code only: initialises the working-memory cube... calls
net.step(dt)... reads the result after HALT ») :
  - chaque mecanisme est exeCUTE par son circuit reel :
      1. K         <- DET (Jeffress, §2.4)
      2. fin corps <- INTG_BODY (§2.5) ; fin argument <- le MEME circuit
                      relance sur la racine de l'argument
      3. masque    <- liaison theta-gamma (§2.6)
      4. shifts    <- anneau de phase (§2.7), par occurrence
      5. patterns  <- copie theta-cycle STDP (§2.8), par token emis
  - l'ASSEMBLAGE des evenements de sortie (§2.10.3) est symbolique
    (tri topographique par position d'entree, comme chez les auteurs).
  - Option living_cube (cf. cube_state.py) : le prochain cube est
    ECRIT slot par slot par les copies STDP et LU par rappel — l'etat
    vit dans les memoires au lieu d'etre re-encode symboliquement.

Regles d'assemblage (le piege signale par Gemini, §2.10.3 shift_bind) :
  - jetons du CORPS conserves (KEEP) : profondeur -1 (le lambda du redex
    disparait) ;
  - VAR conserve dans le corps : indice -1 si son lieur est au-dessus du
    lambda du redex (bf < d_lam) ou s'il est libre (le lambda compte
    dans son indice), indice inchange si son lieur est en dessous
    (bf > d_lam) ; bf == d_lam <=> lie au redex => remplace ;
  - jetons de l'ARGUMENT inseres a la place d'un VAR lie : profondeur
    +sh, indice +sh si la reference sort de l'argument (n >= dA - d_ref),
    inchange sinon (lie a un lambda interne a l'argument) ;
  - jetons avant le redex et apres l'argument : inchangés.
"""

import lambda_beta as lb
import bridge_db as bd
import free_vars_fix as fv
import snn_engine as se            # noqa: F401 (homogeneite des imports)
import det_redex
import intg_body
import bind_gamma
import ring_phase
import copy_stdp
import cube_state
import snn_core

RESERVED_FINE = 7                  # code (7,7) des libres (notre fix)


def balance_end(tokens, start):
    """Longueur du sous-terme qui debute a `start` (premier +1 de sigma,
    eq. 7 — VAR +1, APP -1, LAM 0)."""
    sigma = 0
    for j in range(start, len(tokens)):
        tid = tokens[j][0]
        sigma += 1 if tid >= 4 else (-1 if tid == bd.APP else 0)
        if sigma == 1:
            return j - start + 1
    return None


def rewrite(tokens, rows, K, l_body, l_arg, bound_sh):
    """Assemblage topographique. bound_sh : {position absolue du VAR lie:
    sh}. Renvoie la liste (id, depth) du terme reduit."""
    d_lam = tokens[K + 1][1]
    d_ref = tokens[K][1]
    body_start, body_end = K + 2, K + 2 + l_body
    arg_start, arg_end = body_end, body_end + l_arg
    arg = tokens[arg_start:arg_end]
    out = []
    for j in range(K):                     # avant le redex : inchange
        out.append(tokens[j])
    for j in range(body_start, body_end):  # corps
        if j in bound_sh:
            sh = bound_sh[j]
            for (ida, da) in arg:          # insertion de l'argument
                if ida >= 4 and (ida - 4) >= (da - d_ref):
                    out.append((bd.VAR(ida - 4 + sh), da + sh))
                else:
                    out.append((ida, da + sh))
        else:
            tid, d = tokens[j]
            if tid >= 4:
                bf = rows[j][4]
                # -1 si le lambda du redex etait dans le chemin vers le
                # lieur (bf < d_lam) ou si la variable est libre (bf=7) ;
                # inchange si le lieur est plus profond (bf > d_lam).
                n = tid - 4
                if bf < d_lam or bf == RESERVED_FINE:
                    n -= 1
                out.append((bd.VAR(n), d - 1))
            else:
                out.append((tid, d - 1))
    for j in range(arg_end, len(tokens)):  # apres l'argument : inchange
        out.append(tokens[j])
    return out


def token_pattern(rows, j):
    """Pattern 32 bits d'un token (4 canaux x 8 phases) pour la copie."""
    _tid, _d, sf, sc, bf, bc, _libre = rows[j]
    return tuple(g * 8 + v for g, v in enumerate((sf, sc, bf, bc)))


class ClosedLoop:
    """Boucle fermee : terme nominal -> suites de reductions par les
    circuits reels, verifiee etape par etape contre l'oracle."""

    def __init__(self, verify_copy=True, verbose=True, net_factory=None,
                 copy_engine="py", production=False, intg_tau_m=300.0,
                 living_cube=False):
        self.verify_copy = verify_copy
        self.verbose = verbose
        self.net_factory = net_factory
        self.copy_engine = copy_engine
        # cube vivant : le prochain cube est ECRIT par les copies STDP
        # (un canal par slot, §2.8) et LU par rappel — l'etat passe par
        # les memoires au lieu du re-encodage symbolique (chantier
        # revue ChatGPT, cf. cube_state.py)
        self.living_cube = living_cube
        self.intg_tau_m = intg_tau_m
        # mode production : sans comparaison oracle a chaque etape (la
        # correction du rewrite est deja etablie par la batterie ; ici on
        # mesure le cout de la boucle elle-meme). Arret = DET ne trouve
        # plus de redex (le circuit, pas l'oracle).
        self.production = production
        self._copy_ok = {}                 # patterns deja verifies
        self.ring = ring_phase.PhaseRing()

    def _check_copy(self, patterns):
        if not self.verify_copy:
            return
        for pat in patterns:
            if pat in self._copy_ok:
                continue
            act = sorted(pat)
            if self.copy_engine == "c":
                b = snn_core.CopyC(n=32, i_theta=0.75)
                b.learn(act)
                fired = b.recall(act)
                got = sorted(k for k in range(32) if fired[k])
            else:
                b = copy_stdp.CopyBench(n=32, i_theta=0.75, seed=1)
                b.learn(act)
                fired = b.recall(act)
                got = sorted(k for k in range(32) if fired[k])
            assert got == act, (pat, got)
            self._copy_ok[pat] = True

    def step(self, cur):
        """Une etape de reduction par les circuits reels. Renvoie
        (nouveau terme, rapport) ou (None, rapport) si forme normale."""
        db = bd.to_debruijn(cur)
        toks = bd.to_tokens(db)
        rows = fv.rows_fix(db)
        rep = {"n_in": len(toks)}
        # 1. DET reel
        r_det = det_redex.DetCircuit(
            toks, net_factory=self.net_factory).run()
        K, K_or = r_det["K"], bd.find_redex(cur)
        rep["K_circuit"], rep["K_oracle"] = K, K_or
        assert K == K_or, rep
        if K == -1:
            return None, rep
        # 2. INTG reel : corps puis argument (meme circuit relance)
        r_body = intg_body.IntgCircuit(
            toks, K, net_factory=self.net_factory,
            tau_m=self.intg_tau_m).run()
        l_body = r_body["pos"] + 1
        l_body_or = intg_body.body_end_pos(toks, K) + 1
        assert l_body == l_body_or, rep
        r_arg = intg_body.IntgCircuit(
            toks, K + l_body, net_factory=self.net_factory,
            tau_m=self.intg_tau_m).run()
        l_arg = r_arg["pos"] + 1
        l_arg_or = balance_end(toks, K + 2 + l_body)
        assert l_arg == l_arg_or, rep
        rep["l_body"], rep["l_arg"] = l_body, l_arg
        # 3. liaison reelle (scopEe au corps)
        body_end = K + 2 + l_body
        r_bind = bind_gamma.BindCircuit(
            rows, K, body_end=body_end,
            net_factory=self.net_factory).run()
        order = bind_gamma.body_var_order(rows, K, body_end)
        bound_abs = [order[m] for m in r_bind["bound"]]
        truth = bind_gamma.truth_bound_indices(rows, K, body_end)
        assert bound_abs == truth, rep
        rep["n_bound"] = len(bound_abs)
        # 4. shifts par le ring (reel), par occurrence
        bound_sh, emitted = {}, set()
        for j in bound_abs:
            d_var = toks[j][1]
            sh = d_var - 1 - toks[K][1]
            f, _t, _isi = self.ring.run(d_var % 8, sh + 1)
            assert f[sh] == (d_var % 8 + sh) % 8, (j, sh)
            bound_sh[j] = sh
        rep["shifts"] = sorted(set(bound_sh.values()))
        # 5. assemblage topographique
        new_toks = rewrite(toks, rows, K, l_body, l_arg, bound_sh)
        # patterns emis (sources) -> copie STDP reelle, dedupliquee
        for j in range(K):
            emitted.add(token_pattern(rows, j))
        for j in range(K + 2, K + 2 + l_body):
            if j not in bound_sh:
                emitted.add(token_pattern(rows, j))
        for j in bound_sh:
            for jj in range(K + 2 + l_body, K + 2 + l_body + l_arg):
                emitted.add(token_pattern(rows, jj))
        for j in range(K + 2 + l_body + l_arg, len(toks)):
            emitted.add(token_pattern(rows, j))
        self._check_copy(emitted)
        rep["n_copied_patterns"] = len(emitted)
        rep["n_out"] = len(new_toks)
        # 6. cube vivant : chaque slot du prochain cube est ECRIT par
        #    sa copie STDP (§2.8) et LU par rappel — l'etat effectif
        #    passe par les memoires, pas par le symbole (un canal muet
        #    ou corrompu casse l'assertion : le cube est porteur)
        if self.living_cube:
            new_rows = fv.rows_fix(bd.tokens_to_db(new_toks))
            assert [(r[0], r[1]) for r in new_rows] == new_toks
            cube = cube_state.CubeState(engine=self.copy_engine)
            for s, row in enumerate(new_rows):
                cube.write(s, cube_state.slot_pattern_from_row(row))
            read_toks = cube.read_all()
            assert read_toks == new_toks, rep   # memoire fidele sinon stop
            rep["cube_slots"] = len(cube.slots)
            new_toks = read_toks                # l'ETAT vient du cube
        # reconstruction du terme (NOTRE boucle, pas l'oracle)
        nxt = bd.from_debruijn(bd.tokens_to_db(new_toks))
        return nxt, rep

    def run(self, term_str, max_steps=8):
        cur = lb.parse(term_str)
        trace, steps = [], []
        for _ in range(max_steps):
            trace.append(len(bd.to_tokens(bd.to_debruijn(cur))))
            nxt, rep = self.step(cur)
            if nxt is None:
                if not self.production:
                    oracle, d = lb.beta_step(cur)
                    assert d is False      # DET : forme normale == oracle
                break
            if not self.production:
                # verification contre l'oracle a chaque etape
                oracle, d = lb.beta_step(cur)
                assert bd.to_debruijn(nxt) == bd.to_debruijn(oracle), rep
            if self.verbose:
                print("    etape : %s" % rep)
            steps.append(rep)
            cur = nxt
        return cur, trace, steps
