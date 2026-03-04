"""NightGuard V2 - Pass 1: Local Variable Renaming"""
import random, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import ast_nodes as N

def _make_pool(n, rng):
    chars = 'IlO01'; names = set()
    while len(names) < n:
        l = rng.randint(7, 15)
        names.add(rng.choice(('l','I','O')) + ''.join(rng.choices(chars, k=l-1)))
    return list(names)

class RenameLocalsPass:
    def __init__(self, rng):
        self._rng = rng; self._pool = _make_pool(4096, rng)
        self._used = 0; self._scopes = [{}]
    def _fresh(self):
        n = self._pool[self._used % len(self._pool)]; self._used += 1; return n
    def _push(self): self._scopes.append({})
    def _pop(self):  self._scopes.pop()
    def _add(self, orig):
        new = self._fresh(); self._scopes[-1][orig] = new; return new
    def _resolve(self, name):
        for s in reversed(self._scopes):
            if name in s: return s[name]
        return name
    def visit(self, node):
        m = getattr(self, f'_v_{type(node).__name__}', None)
        return m(node) if m else node
    def _v_Block(self, n): return N.Block([r for r in (self.visit(s) for s in n.body) if r is not None])
    def _v_LocalAssign(self, n):
        vals = [self.visit(v) for v in n.values]
        return N.LocalAssign([N.Name(self._add(t.id)) for t in n.targets], vals)
    def _v_Assign(self, n):
        return N.Assign([self._lval(t) for t in n.targets], [self.visit(v) for v in n.values])
    def _lval(self, n):
        if isinstance(n, N.Name):  return N.Name(self._resolve(n.id))
        if isinstance(n, N.Field): return N.Field(self.visit(n.value), n.key)
        if isinstance(n, N.Index): return N.Index(self.visit(n.value), self.visit(n.key))
        return n
    def _v_Name(self, n):     return N.Name(self._resolve(n.id))
    def _v_Number(self, n):   return n
    def _v_String(self, n):   return n
    def _v_NilExpr(self, n):  return n
    def _v_TrueExpr(self, n): return n
    def _v_FalseExpr(self, n):return n
    def _v_Vararg(self, n):   return n
    def _v_Break(self, n):    return n
    def _v_Do(self, n):
        self._push(); b = self._v_Block(n.body); self._pop(); return N.Do(b)
    def _v_While(self, n):
        t = self.visit(n.test); self._push(); b = self._v_Block(n.body); self._pop()
        return N.While(t, b)
    def _v_Repeat(self, n):
        self._push(); b = self._v_Block(n.body); t = self.visit(n.test); self._pop()
        return N.Repeat(b, t)
    def _v_If(self, n):
        t = self.visit(n.test); self._push(); b = self._v_Block(n.body); self._pop()
        orelse = []
        for o in n.orelse:
            if isinstance(o, N.ElseIf):
                t2 = self.visit(o.test); self._push(); b2 = self._v_Block(o.body); self._pop()
                orelse.append(N.ElseIf(t2, b2))
            else:
                self._push(); b2 = self._v_Block(o.body); self._pop(); orelse.append(N.Else(b2))
        return N.If(t, b, orelse)
    def _v_Fornumeric(self, n):
        start = self.visit(n.start); stop = self.visit(n.stop)
        step = self.visit(n.step) if n.step else None
        self._push(); tgt = N.Name(self._add(n.target.id)); body = self._v_Block(n.body); self._pop()
        return N.Fornumeric(tgt, start, stop, step, body)
    def _v_Forin(self, n):
        iters = [self.visit(e) for e in n.iter]
        self._push(); tgts = [N.Name(self._add(t.id)) for t in n.targets]; body = self._v_Block(n.body); self._pop()
        return N.Forin(tgts, iters, body)
    def _fbody(self, args, body):
        self._push()
        new_args = [N.Name(self._add(a.id)) if isinstance(a, N.Name) else a for a in args]
        nb = self._v_Block(body); self._pop(); return new_args, nb
    def _v_Function(self, n):
        args, body = self._fbody(n.args, n.body); return N.Function(self._lval(n.name), args, body)
    def _v_LocalFunction(self, n):
        nm = N.Name(self._add(n.name.id)); args, body = self._fbody(n.args, n.body)
        return N.LocalFunction(nm, args, body)
    def _v_Method(self, n):
        args, body = self._fbody(n.args, n.body); return N.Method(self.visit(n.source), n.name, args, body)
    def _v_AnonymousFunction(self, n):
        args, body = self._fbody(n.args, n.body); return N.AnonymousFunction(args, body)
    def _v_Return(self, n): return N.Return([self.visit(v) for v in n.values])
    def _v_BinOp(self, n):  return N.BinOp(n.op, self.visit(n.left), self.visit(n.right))
    def _v_UnOp(self, n):   return N.UnOp(n.op, self.visit(n.operand))
    def _v_Field(self, n):  return N.Field(self.visit(n.value), n.key)
    def _v_Index(self, n):  return N.Index(self.visit(n.value), self.visit(n.key))
    def _v_Call(self, n):   return N.Call(self.visit(n.func), [self.visit(a) for a in n.args])
    def _v_Invoke(self, n): return N.Invoke(self.visit(n.source), n.func, [self.visit(a) for a in n.args])
    def _v_Table(self, n):
        flds = []
        for f in n.fields:
            if isinstance(f, N.TableField):   flds.append(N.TableField(f.key, self.visit(f.value)))
            elif isinstance(f, N.TableIndex): flds.append(N.TableIndex(self.visit(f.key), self.visit(f.value)))
            else: flds.append(self.visit(f))
        return N.Table(flds)


def run(block, rng):
    return RenameLocalsPass(rng).visit(block)
