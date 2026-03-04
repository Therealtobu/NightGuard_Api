"""
Night - AST Transformer
Renames locals and encrypts string literals.
"""
import random
from . import ast_nodes as N


def _make_name_pool(n: int, rng: random.Random) -> list:
    chars = 'IlO01'
    names = set()
    while len(names) < n:
        length = rng.randint(6, 14)
        name = rng.choice(('l','I','O')) + ''.join(rng.choices(chars, k=length-1))
        names.add(name)
    return list(names)


def _xor_encrypt(s: str, key: int) -> list:
    return [(ord(c) ^ key) for c in s]


class Transformer:
    def __init__(self, rng: random.Random):
        self._rng = rng
        self._pool = _make_name_pool(4096, rng)
        self._used = 0
        self._scopes = [{}]
        self.string_table = {}   # encrypted_key -> (encrypted_bytes, xor_key)
        self._str_counter = 0

    def _fresh(self):
        name = self._pool[self._used % len(self._pool)]
        self._used += 1
        return name

    def _push(self): self._scopes.append({})
    def _pop(self):  self._scopes.pop()

    def _add_local(self, original):
        new = self._fresh()
        self._scopes[-1][original] = new
        return new

    def _lookup(self, name):
        for scope in reversed(self._scopes):
            if name in scope:
                return scope[name]
        return name

    def _encrypt_string(self, s):
        key = self._rng.randint(1, 255)
        enc = _xor_encrypt(s, key)
        idx = self._str_counter
        self._str_counter += 1
        self.string_table[idx] = (enc, key)
        return idx

    def visit(self, node):
        m = getattr(self, f'_v_{type(node).__name__}', None)
        if m:
            return m(node)
        return node

    def _v_Block(self, n):
        return N.Block([r for r in (self.visit(s) for s in n.body) if r is not None])

    def _v_LocalAssign(self, n):
        vals = [self.visit(v) for v in n.values]
        targets = [N.Name(self._add_local(t.id)) for t in n.targets]
        return N.LocalAssign(targets, vals)

    def _v_Assign(self, n):
        targets = [self._lvalue(t) for t in n.targets]
        values  = [self.visit(v) for v in n.values]
        return N.Assign(targets, values)

    def _lvalue(self, n):
        if isinstance(n, N.Name):   return N.Name(self._lookup(n.id))
        if isinstance(n, N.Field):  return N.Field(self.visit(n.value), n.key)
        if isinstance(n, N.Index):  return N.Index(self.visit(n.value), self.visit(n.key))
        return n

    def _v_Name(self, n):   return N.Name(self._lookup(n.id))
    def _v_Number(self, n): return n
    def _v_NilExpr(self, n):   return n
    def _v_TrueExpr(self, n):  return n
    def _v_FalseExpr(self, n): return n
    def _v_Vararg(self, n):    return n
    def _v_Break(self, n):     return n

    def _v_String(self, n):
        # Don't encrypt very short strings to avoid noise
        if len(n.s) < 2:
            return n
        idx = self._encrypt_string(n.s)
        # Return a placeholder that the compiler will resolve
        return _EncryptedString(idx)

    def _v_Do(self, n):
        self._push(); body = self._v_Block(n.body); self._pop()
        return N.Do(body)

    def _v_While(self, n):
        test = self.visit(n.test)
        self._push(); body = self._v_Block(n.body); self._pop()
        return N.While(test, body)

    def _v_Repeat(self, n):
        self._push()
        body = self._v_Block(n.body)
        test = self.visit(n.test)
        self._pop()
        return N.Repeat(body, test)

    def _v_If(self, n):
        test = self.visit(n.test)
        self._push(); body = self._v_Block(n.body); self._pop()
        orelse = []
        for o in n.orelse:
            if isinstance(o, N.ElseIf):
                t2 = self.visit(o.test)
                self._push(); b2 = self._v_Block(o.body); self._pop()
                orelse.append(N.ElseIf(t2, b2))
            elif isinstance(o, N.Else):
                self._push(); b2 = self._v_Block(o.body); self._pop()
                orelse.append(N.Else(b2))
        return N.If(test, body, orelse)

    def _v_Fornumeric(self, n):
        start = self.visit(n.start)
        stop  = self.visit(n.stop)
        step  = self.visit(n.step) if n.step else None
        self._push()
        tgt  = N.Name(self._add_local(n.target.id))
        body = self._v_Block(n.body)
        self._pop()
        return N.Fornumeric(tgt, start, stop, step, body)

    def _v_Forin(self, n):
        iters = [self.visit(e) for e in n.iter]
        self._push()
        tgts = [N.Name(self._add_local(t.id)) for t in n.targets]
        body = self._v_Block(n.body)
        self._pop()
        return N.Forin(tgts, iters, body)

    def _funcbody(self, args, body):
        self._push()
        new_args = [N.Name(self._add_local(a.id)) if isinstance(a, N.Name) else a
                    for a in args]
        new_body = self._v_Block(body)
        self._pop()
        return new_args, new_body

    def _v_Function(self, n):
        name = self._lvalue(n.name)
        args, body = self._funcbody(n.args, n.body)
        return N.Function(name, args, body)

    def _v_LocalFunction(self, n):
        new_name = N.Name(self._add_local(n.name.id))
        args, body = self._funcbody(n.args, n.body)
        return N.LocalFunction(new_name, args, body)

    def _v_Method(self, n):
        src = self.visit(n.source)
        args, body = self._funcbody(n.args, n.body)
        return N.Method(src, n.name, args, body)

    def _v_AnonymousFunction(self, n):
        args, body = self._funcbody(n.args, n.body)
        return N.AnonymousFunction(args, body)

    def _v_Return(self, n): return N.Return([self.visit(v) for v in n.values])
    def _v_BinOp(self, n):  return N.BinOp(n.op, self.visit(n.left), self.visit(n.right))
    def _v_UnOp(self, n):   return N.UnOp(n.op, self.visit(n.operand))
    def _v_Field(self, n):  return N.Field(self.visit(n.value), n.key)
    def _v_Index(self, n):  return N.Index(self.visit(n.value), self.visit(n.key))
    def _v_Call(self, n):   return N.Call(self.visit(n.func), [self.visit(a) for a in n.args])
    def _v_Invoke(self, n): return N.Invoke(self.visit(n.source), n.func, [self.visit(a) for a in n.args])

    def _v_Table(self, n):
        fields = []
        for f in n.fields:
            if isinstance(f, N.TableField):
                fields.append(N.TableField(f.key, self.visit(f.value)))
            elif isinstance(f, N.TableIndex):
                fields.append(N.TableIndex(self.visit(f.key), self.visit(f.value)))
            else:
                fields.append(self.visit(f))
        return N.Table(fields)


class _EncryptedString(N.Node):
    """Placeholder – resolved by the compiler using Transformer.string_table."""
    def __init__(self, idx):
        self.idx = idx
