# -*- coding: utf-8 -*-
"""Mini-lab, palier 2a : le pont vers le papier (arXiv:2611.23182).

Conversions :
    terme nominal (lambda_beta) <-> arbre De Bruijn <-> tokens plats
    (prefixe polonais : LAM=1, APP=2, VAR_n=4+n ; cf. papier §2.1)
Encodage theta-gamma de la profondeur (papier §2.2) :
    phi_fine = d mod 8, phi_coarse = (d // 8) mod 8
Detecteur de redex « facon Jeffress » (papier §2.4) en version
symbolique : un pulse par token, slots de 8 ms, APP retarde de 8 ms,
LAM de 0.5 ms ; coïncidence dans une fenêtre de 1 ms => redex ;
latch WTA : la premiere coïncidence gagne.
"""

import lambda_beta as lb

LAM, APP = 1, 2


def VAR(n):
    return 4 + n


K_F = K_C = 8


# ---- noms -> De Bruijn --------------------------------------------------

def free_level(name, rank):
    """NIVEAU stable d'une variable libre : le suffixe _f<n> pose par
    from_debruijn EST l'identite de la variable (son niveau ne change
    pas d'une etape a l'autre) ; un nom sans suffixe (le terme initial
    de l'utilisateur) prend le rang de premiere occurrence (l'encodage
    initial, §2.11). Ignorer le suffixe re-classait les libres a chaque
    etape : des qu'une reduction changeait leur ordre d'apparition,
    les identites s'echangaient (chantier A, session 37)."""
    if "_f" in name:
        tail = name.rsplit("_f", 1)[1]
        if tail.isdigit():
            return int(tail)
    return rank


def to_debruijn_c(t, fmap):
    """comme to_debruijn, mais les niveaux des libres passent par le
    registre fmap (nom -> niveau, mute par la marche) : un nom suffixe
    _f<n> garde son niveau n ; un nom nouveau recoit le prochain rang ;
    un nom deja registre garde le sien. Deux termes canonises avec le
    MEME fmap sont comparables etape par etape — les echanges de libres
    (le defaut session 37) y sont detectes, la comparaison par simple
    ordre d'apparition les manquait."""
    def rec(t, env):
        if isinstance(t, lb.Var):
            if t.name in env:
                return ("var", env.index(t.name))
            lvl = free_level(t.name, fmap.get(t.name, len(fmap)))
            fmap.setdefault(t.name, lvl)
            return ("var", len(env) + lvl)
        if isinstance(t, lb.Abs):
            return ("lam", rec(t.body, [t.param] + env))
        return ("app", rec(t.func, env), rec(t.arg, env))

    return rec(t, [])


def to_debruijn(t):
    """AST nominal -> arbre DB : ('lam', b) | ('app', f, a) | ('var', n).
    Variables libres : index = hauteur courante + NIVEAU — le niveau =
    le suffixe _f<n> du nom si present (l'identite stable), sinon le
    rang de premiere occurrence (l'encodage initial, §2.11)."""
    return to_debruijn_c(t, {})


_FRESH = "xyzuvwrstab"

def from_debruijn(t):
    """Arbre DB -> AST nominal (lieurs renommes avec des noms frais)."""
    def rec(t, env):
        if t[0] == "var":
            n = t[1]
            if n < len(env):
                return lb.Var(env[n])
            # nom deduit du NIVEAU (n - len(env), invariant par
            # abstraction) — le suffixe _f<n> brut dependait de la
            # profondeur : une meme libre a deux profondeurs etait
            # scindee en deux variables au round-trip (revue externe)
            return lb.Var(_FRESH[(n - len(env)) % len(_FRESH)]
                          + "_f%d" % (n - len(env)))
        if t[0] == "lam":
            base = _FRESH[len(env) % len(_FRESH)]
            name, k = base, 0
            while name in env:
                k += 1
                name = base + str(k)
            return lb.Abs(name, rec(t[1], [name] + env))
        return lb.App(rec(t[1], env), rec(t[2], env))

    return rec(t, [])


# ---- De Bruijn -> tokens plats (prefixe) ---------------------------------

def to_tokens(t):
    """Parcours prefixe : liste de (id, depth).
    depth = nombre de LAM englobants au moment du token (le LAM compte
    pour ses descendants, pas pour lui-meme)."""
    out = []

    def rec(t, d):
        if t[0] == "var":
            out.append((VAR(t[1]), d))
        elif t[0] == "lam":
            out.append((LAM, d))
            rec(t[1], d + 1)
        else:
            out.append((APP, d))
            rec(t[1], d)
            rec(t[2], d)

    rec(t, 0)
    return out


def tokens_to_db(tokens):
    """Reconstruction inverse (le prefixe + VAR feuilles suffisent ;
    les profondeurs servent de verification)."""
    def rec(i, d):
        tid, dd = tokens[i]
        assert dd == d, "profondeur incoherente au token %d" % i
        if tid == LAM:
            body, j = rec(i + 1, d + 1)
            return ("lam", body), j
        if tid == APP:
            f, j = rec(i + 1, d)
            a, j2 = rec(j, d)
            return ("app", f, a), j2
        return ("var", tid - 4), i + 1

    t, j = rec(0, 0)
    assert j == len(tokens)
    return t


# ---- encodage theta-gamma (papier §2.2) ----------------------------------

def phase_table(db):
    """Par token : (id, d, self_fine, self_coarse, bind_fine, bind_coarse,
    libre). BIND = profondeur SELF du binder, trouvee via la pile des
    LAM ancetres (un VAR(n) lie pointe le (n+1)-ieme LAM en remontant)."""
    rows = []

    def rec(t, d, lam_stack):
        if t[0] == "var":
            n = t[1]
            libre = n >= len(lam_stack)
            if libre:
                bf = bc = 0
            else:
                b = lam_stack[len(lam_stack) - 1 - n]
                bf, bc = b % K_F, (b // K_F) % K_C
            rows.append((VAR(n), d, d % K_F, (d // K_F) % K_C, bf, bc, libre))
        elif t[0] == "lam":
            rows.append((LAM, d, d % K_F, (d // K_F) % K_C, 0, 0, True))
            rec(t[1], d + 1, lam_stack + [d])
        else:
            rows.append((APP, d, d % K_F, (d // K_F) % K_C, 0, 0, True))
            rec(t[1], d, lam_stack)
            rec(t[2], d, lam_stack)

    rec(db, 0, [])
    return rows


# ---- detecteur de redex facon Jeffress (papier §2.4, symbolique) ----------

def jeffress_redex(tokens, slot_ms=8.0, window_ms=1.0):
    """Un pulse par token, un slot de 8 ms ; APP -> DET avec delai 8 ms,
    LAM -> DET avec delai 0.5 ms. Coïncidence <= window_ms => redex ;
    WTA : la premiere coïncidence (temps croissants) gagne.
    Renvoie (K, t_detection), K = -1 si aucun redex.

    Propriete (verifiable a la main) : APP@j arrive a 8j+8 et LAM@j a
    8j+0.5 ; deux arrivals a moins de 1 ms d'ecart sont forcement une
    paire (APP@j, LAM@j+1) adjacente — aucun croisement parasite."""
    arrivals = []
    for j, (tid, _d) in enumerate(tokens):
        t0 = slot_ms * j
        if tid == APP:
            arrivals.append((t0 + slot_ms, "APP", j))
        elif tid == LAM:
            arrivals.append((t0 + 0.5, "LAM", j))
    arrivals.sort()
    for i in range(len(arrivals) - 1):
        (t1, k1, j1), (t2, k2, j2) = arrivals[i], arrivals[i + 1]
        if t2 - t1 <= window_ms and {k1, k2} == {"APP", "LAM"}:
            return (j1 if k1 == "APP" else j2), (t1 + t2) / 2
    return -1, None


# ---- reference independante : position du redex sur l'AST nominal --------

def _size(t):
    if isinstance(t, lb.Var):
        return 1
    if isinstance(t, lb.Abs):
        return 1 + _size(t.body)
    return 1 + _size(t.func) + _size(t.arg)


def find_redex(t):
    """Position (ordre prefixe) du redex gauche-exterieur sur l'AST
    nominal — ne passe JAMAIS par l'encodage tokens (reference pure)."""
    path = []

    def rec(t):
        if isinstance(t, lb.App):
            if isinstance(t.func, lb.Abs):
                return True
            if rec(t.func):
                path.insert(0, "func")
                return True
            if rec(t.arg):
                path.insert(0, "arg")
                return True
            return False
        if isinstance(t, lb.Abs):
            if rec(t.body):
                path.insert(0, "body")
                return True
        return False

    if not rec(t):
        return -1
    pos, cur = 0, t
    for step in path:
        if step == "arg":
            pos += 1 + _size(cur.func)     # token du parent + sous-arbre gauche
            cur = cur.arg
        else:
            pos += 1                        # token du parent (APP ou LAM)
            cur = cur.func if step == "func" else cur.body
    return pos
