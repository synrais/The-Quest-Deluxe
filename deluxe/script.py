"""Level scripts: a small, safe subset of Python used for quests and events.

A level's script (the pack's levels/<n>/script.qs, Python-like text) defines handlers:

    def talk(npc):        # the hero walks into a talking NPC (x, y = the NPC's square)
    def turn():           # every turn (the original deadenemycheck() position checks)
    def dies(e):          # a creature has just died (e = the dead enemy, before removal)
    def pickup(item):     # the hero picked something up at (x, y)
    def chest():          # the hero opened a chest at (x, y)

Scripts may use if/elif/else, for loops over lists the host gives them, and/or/not, comparisons,
arithmetic, assignments to host variables (m1 = 1, rep += 1) and to fields of host objects
(room(3, 4).mon = 0, e.att = 9), and calls of host functions (say(10), remove(5, 8), ...).
Nothing else is allowed (no imports, no attribute access starting with '_', no names the host doesn't
provide), so a level file from anywhere can't do anything outside the game.
"""
from __future__ import annotations

import ast
import operator

BINOPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Mod: operator.mod,
          ast.FloorDiv: operator.floordiv, ast.Div: lambda a, b: int(a / b)}
CMPOPS = {ast.Eq: operator.eq, ast.NotEq: operator.ne, ast.Lt: operator.lt, ast.LtE: operator.le,
          ast.Gt: operator.gt, ast.GtE: operator.ge, ast.In: lambda a, b: a in b,
          ast.NotIn: lambda a, b: a not in b}


class ScriptError(Exception):
    pass


class _Return(Exception):
    def __init__(self, value):
        self.value = value


class Script:
    """A parsed level script. run(name, host, *args) calls one of its handlers."""

    def __init__(self, source: str, filename: str = '<level script>'):
        self.filename = filename
        tree = ast.parse(source, filename)
        self.handlers: dict[str, ast.FunctionDef] = {}
        self.constants: dict[str, object] = {}
        for node in tree.body:
            if isinstance(node, ast.FunctionDef):
                self.handlers[node.name] = node
            elif isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
                self.constants[node.targets[0].id] = ast.literal_eval(node.value)
            elif isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant):
                continue                      # docstring
            else:
                raise ScriptError(f'{filename}:{node.lineno}: only functions and constants at the top level')
        for fn in self.handlers.values():
            for n in ast.walk(fn):
                self._check(n)

    def _check(self, n):
        allowed = (ast.FunctionDef, ast.arguments, ast.arg, ast.If, ast.For, ast.Assign, ast.AugAssign, ast.Expr,
                   ast.Return, ast.Pass, ast.Break, ast.Continue, ast.Call, ast.Name, ast.Attribute, ast.Constant,
                   ast.Compare, ast.BoolOp, ast.UnaryOp, ast.BinOp, ast.Tuple, ast.List, ast.Load, ast.Store,
                   ast.And, ast.Or, ast.Not, ast.USub, ast.UAdd, ast.IfExp, ast.keyword,
                   *BINOPS, *CMPOPS)
        if not isinstance(n, allowed):
            raise ScriptError(f'{self.filename}:{getattr(n, "lineno", "?")}: {type(n).__name__} is not allowed')
        if isinstance(n, ast.Attribute) and n.attr.startswith('_'):
            raise ScriptError(f'{self.filename}:{n.lineno}: private attribute {n.attr}')

    def has(self, name):
        return name in self.handlers

    def run(self, name, host, *args):
        fn = self.handlers.get(name)
        if fn is None:
            return None
        local = dict(zip((a.arg for a in fn.args.args), args))
        try:
            self._block(fn.body, host, local)
        except _Return as r:
            return r.value
        return None

    # ── statements ──────────────────────────────────────────────────────────
    def _block(self, body, host, local):
        for st in body:
            self._stmt(st, host, local)

    def _stmt(self, st, host, local):
        if isinstance(st, ast.Expr):
            self._eval(st.value, host, local)
        elif isinstance(st, ast.If):
            self._block(st.body if self._eval(st.test, host, local) else st.orelse, host, local)
        elif isinstance(st, ast.Assign):
            v = self._eval(st.value, host, local)
            for t in st.targets:
                self._assign(t, v, host, local)
        elif isinstance(st, ast.AugAssign):
            cur = self._eval(_as_load(st.target), host, local)
            self._assign(st.target, BINOPS[type(st.op)](cur, self._eval(st.value, host, local)), host, local)
        elif isinstance(st, ast.For):
            for item in list(self._eval(st.iter, host, local)):
                self._assign(st.target, item, host, local)
                try:
                    self._block(st.body, host, local)
                except _Break:
                    break
                except _Continue:
                    continue
        elif isinstance(st, ast.Return):
            raise _Return(self._eval(st.value, host, local) if st.value else None)
        elif isinstance(st, ast.Break):
            raise _Break()
        elif isinstance(st, ast.Continue):
            raise _Continue()
        elif isinstance(st, ast.Pass):
            pass
        else:
            raise ScriptError(f'{self.filename}:{st.lineno}: unsupported statement')

    def _assign(self, t, v, host, local):
        if isinstance(t, ast.Name):
            if t.id in local or not host.has_var(t.id):
                local[t.id] = v
            else:
                host.set_var(t.id, v)
        elif isinstance(t, ast.Attribute):
            obj = self._eval(t.value, host, local)
            host.set_attr(obj, t.attr, v)
        elif isinstance(t, ast.Tuple):
            for tt, vv in zip(t.elts, v):
                self._assign(tt, vv, host, local)
        else:
            raise ScriptError(f'{self.filename}:{t.lineno}: cannot assign to this')

    # ── expressions ─────────────────────────────────────────────────────────
    def _eval(self, e, host, local):
        if isinstance(e, ast.Constant):
            return e.value
        if isinstance(e, ast.Name):
            if e.id in local:
                return local[e.id]
            if e.id in self.constants:
                return self.constants[e.id]
            if host.has_var(e.id):
                return host.get_var(e.id)
            if e.id in ('True', 'False', 'None'):
                return {'True': True, 'False': False, 'None': None}[e.id]
            raise ScriptError(f'{self.filename}:{e.lineno}: unknown name {e.id}')
        if isinstance(e, ast.Attribute):
            return host.get_attr(self._eval(e.value, host, local), e.attr)
        if isinstance(e, ast.Call):
            if not isinstance(e.func, ast.Name) or not host.has_func(e.func.id):
                raise ScriptError(f'{self.filename}:{e.lineno}: unknown function')
            args = [self._eval(a, host, local) for a in e.args]
            kw = {k.arg: self._eval(k.value, host, local) for k in e.keywords}
            return host.call(e.func.id, *args, **kw)
        if isinstance(e, ast.BinOp):
            return BINOPS[type(e.op)](self._eval(e.left, host, local), self._eval(e.right, host, local))
        if isinstance(e, ast.UnaryOp):
            v = self._eval(e.operand, host, local)
            return {ast.USub: operator.neg, ast.UAdd: operator.pos, ast.Not: operator.not_}[type(e.op)](v)
        if isinstance(e, ast.BoolOp):
            if isinstance(e.op, ast.And):
                v = True
                for x in e.values:
                    v = self._eval(x, host, local)
                    if not v:
                        return v
                return v
            v = False
            for x in e.values:
                v = self._eval(x, host, local)
                if v:
                    return v
            return v
        if isinstance(e, ast.Compare):
            left = self._eval(e.left, host, local)
            for op, c in zip(e.ops, e.comparators):
                right = self._eval(c, host, local)
                if not CMPOPS[type(op)](left, right):
                    return False
                left = right
            return True
        if isinstance(e, ast.IfExp):
            return self._eval(e.body if self._eval(e.test, host, local) else e.orelse, host, local)
        if isinstance(e, (ast.Tuple, ast.List)):
            return [self._eval(x, host, local) for x in e.elts]
        raise ScriptError(f'{self.filename}:{getattr(e, "lineno", "?")}: unsupported expression')


class _Break(Exception):
    pass


class _Continue(Exception):
    pass


def _as_load(t):
    if isinstance(t, ast.Name):
        return ast.Name(id=t.id, ctx=ast.Load())
    if isinstance(t, ast.Attribute):
        return ast.Attribute(value=t.value, attr=t.attr, ctx=ast.Load())
    return t
