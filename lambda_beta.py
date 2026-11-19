# -*- coding: utf-8 -*-
"""Mini-lab, palier 1a : lambda-calcul symbolique pur Python (stdlib).

Representation des termes :
    Var('x')      variable
    Abs('x', b)   abstraction   \\x. b
    App(f, a)     application   f a

API : parse (chaine -> terme), to_str (terme -> chaine minimal-parens),
subst (substitution capture-safe avec alpha-renommage), beta_step /
normalize (ordre normal, limite anti-divergence), church_to_int.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Var:
    name: str


@dataclass(frozen=True)
class Abs:
    param: str
    body: object


@dataclass(frozen=True)
class App:
    func: object
    arg: object


# ---- variables libres / noms frais ------------------------------------

def free_vars(t):
    if isinstance(t, Var):
        return {t.name}
    if isinstance(t, Abs):
        return free_vars(t.body) - {t.param}
    return free_vars(t.func) | free_vars(t.arg)


def fresh_name(base, forbidden):
    """base', base'', ... : premier nom de la famille non deja pris."""
    name = base
    while name in forbidden:
        name += "'"
    return name


# ---- substitution capture-safe -----------------------------------------

def subst(t, var, val):
    """t[var := val], en evitant la capture des variables libres de val."""
    if isinstance(t, Var):
        return val if t.name == var else t
    if isinstance(t, App):
        return App(subst(t.func, var, val), subst(t.arg, var, val))
    # Abs : si le lieur masque var, rien a faire ; sinon alpha-renommer
    # si le lieur risquerait de capturer une variable libre de val.
    if t.param == var:
        return t
    if t.param in free_vars(val):
        forbidden = free_vars(t.body) | free_vars(val) | {var}
        fresh = fresh_name(t.param, forbidden)
        return Abs(fresh, subst(subst(t.body, t.param, Var(fresh)), var, val))
    return Abs(t.param, subst(t.body, var, val))


# ---- reduction beta (ordre normal) --------------------------------------

def beta_step(t):
    """Une etape d'ordre normal (redex le plus a gauche, le plus exterieur).
    Renvoie (terme, reduit) ; reduit=False signifie forme normale atteinte."""
    if isinstance(t, App):
        if isinstance(t.func, Abs):                     # redex
            return subst(t.func.body, t.func.param, t.arg), True
        f2, d = beta_step(t.func)                       # gauche d'abord
        if d:
            return App(f2, t.arg), True
        a2, d = beta_step(t.arg)
        if d:
            return App(t.func, a2), True
        return t, False
    if isinstance(t, Abs):
        b2, d = beta_step(t.body)
        return Abs(t.param, b2), d
    return t, False                                     # Var


def normalize(t, max_steps=200):
    """Reduit jusqu'a forme normale ou max_steps etapes.
    Renvoie (terme, nb_etapes_faites, converge)."""
    for i in range(max_steps):
        t2, d = beta_step(t)
        if not d:
            return t, i, True
        t = t2
    return t, max_steps, False


# ---- parsing / impression -----------------------------------------------

class ParseError(ValueError):
    pass


def parse(s):
    """Accepte '\\x y. x y', '(\\x. x) y', 'λx. x' (espaces libres)."""
    tokens = _tokenize(s)
    term, pos = _parse_term(tokens, 0)
    if pos != len(tokens):
        raise ParseError("symbole inattendu : %r" % (tokens[pos],))
    return term


def _tokenize(s):
    s = s.replace("λ", "\\")
    out, i = [], 0
    while i < len(s):
        c = s[i]
        if c in "().\\.":
            out.append(c)
            i += 1
        elif c.isspace():
            i += 1
        elif c.isalnum() or c == "_":
            j = i
            while j < len(s) and (s[j].isalnum() or s[j] == "_"):
                j += 1
            out.append(s[i:j])
            i = j
        else:
            raise ParseError("caractere invalide : %r" % (c,))
    return out


def _parse_term(tk, i):
    atoms = []
    while i < len(tk) and tk[i] != ")":
        a, i = _parse_atom(tk, i)
        atoms.append(a)
    if not atoms:
        raise ParseError("terme vide ou ')' inattendue")
    t = atoms[0]
    for a in atoms[1:]:
        t = App(t, a)
    return t, i


def _parse_atom(tk, i):
    tok = tk[i]
    if tok == "(":
        t, i = _parse_term(tk, i + 1)
        if i >= len(tk) or tk[i] != ")":
            raise ParseError("parenthese fermante manquante")
        return t, i + 1
    if tok == "\\":
        params = []
        i += 1
        while i < len(tk) and tk[i] != ".":
            if tk[i] in "().\\":
                raise ParseError("parametre invalide : %r" % (tk[i],))
            params.append(tk[i])
            i += 1
        if i >= len(tk):
            raise ParseError("'.' manquant apres les parametres")
        body, i = _parse_term(tk, i + 1)          # corps aussi loin que possible
        for p in reversed(params):
            body = Abs(p, body)
        return body, i
    if tok in (".", ")"):
        raise ParseError("symbole inattendu : %r" % (tok,))
    return Var(tok), i + 1


def to_str(t):
    """Impression lisible : lieurs groupes ('\\x y.'), parens minimales."""
    return _str(t, top=True)


def _str(t, top=False):
    if isinstance(t, Var):
        return t.name
    if isinstance(t, Abs):
        params = [t.param]
        b = t.body
        while isinstance(b, Abs):
            params.append(b.param)
            b = b.body
        s = "\\" + " ".join(params) + ". " + _str(b)
        return s if top else "(" + s + ")"
    # App : les Abs se parenthesent deja seuls ; seul un App en position
    # d'argument doit etre entoure.
    f = _str(t.func)
    a = _str(t.arg)
    if isinstance(t.arg, App):
        a = "(" + a + ")"
    return f + " " + a


def church_to_int(t):
    """Reconnait \\f.\\x. f (f (... x)) -> n ; None sinon."""
    if not (isinstance(t, Abs) and isinstance(t.body, Abs)):
        return None
    f, x = t.param, t.body.param
    if x == f:
        return None                                # lieur masque : pas un numerau
    cur, n = t.body.body, 0
    while isinstance(cur, App):
        if not (isinstance(cur.func, Var) and cur.func.name == f):
            return None
        cur = cur.arg
        n += 1
    if isinstance(cur, Var) and cur.name == x:
        return n
    return None


def show(t, label=""):
    s = to_str(t)
    n = church_to_int(t)
    if n is not None:
        s += "   [= Eglise %d]" % n
    print(label + s)
