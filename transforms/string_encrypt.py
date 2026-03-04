"""NightGuard V2 - Pass 2: Rolling-XOR String Encryption"""
import random, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import ast_nodes as N

def rolling_xor_encrypt(s: str, seed: int, step: int) -> list:
    key = seed & 0xFF
    out = []
    for ch in s:
        enc = (ord(ch) ^ key) & 0xFF
        out.append(enc)
        key = (key * step + enc) % 256
        if key == 0: key = 1
    return out

class EncryptedStringNode(N.Node):
    def __init__(self, idx): self.idx = idx

class StringEncryptPass:
    def __init__(self, rng):
        self._rng = rng
        self.string_table = {}  # idx -> (enc_bytes, seed, step)
        self._counter = 0
    def _encrypt(self, s):
        if len(s) < 2: return None
        seed = self._rng.randint(2, 254)
        step = self._rng.randint(3, 251) | 1  # odd for better mixing
        enc  = rolling_xor_encrypt(s, seed, step)
        idx  = self._counter; self._counter += 1
        self.string_table[idx] = (enc, seed, step)
        return idx
    def visit(self, node):
        m = getattr(self, f'_v_{type(node).__name__}', None)
        return m(node) if m else node
    def _v_Block(self, n): return N.Block([r for r in (self.visit(s) for s in n.body) if r is not None])
    def _v_String(self, n):
        idx = self._encrypt(n.s)
        return EncryptedStringNode(idx) if idx is not None else n
    def _v_LocalAssign(self, n):
        return N.LocalAssign(n.targets, [self.visit(v) for v in n.values])
    def _v_Assign(self, n):
        return N.Assign(n.targets, [self.visit(v) for v in n.values])
    def _v_Return(self, n):  return N.Return([self.visit(v) for v in n.values])
    def _v_BinOp(self, n):   return N.BinOp(n.op, self.visit(n.left), self.visit(n.right))
    def _v_UnOp(self, n):    return N.UnOp(n.op, self.visit(n.operand))
    def _v_Call(self, n):    return N.Call(self.visit(n.func), [self.visit(a) for a in n.args])
    def _v_Invoke(self, n):  return N.Invoke(self.visit(n.source), n.func, [self.visit(a) for a in n.args])
    def _v_Field(self, n):   return N.Field(self.visit(n.value), n.key)
    def _v_Index(self, n):   return N.Index(self.visit(n.value), self.visit(n.key))
    def _v_If(self, n):
        t = self.visit(n.test); b = self._v_Block(n.body)
        orelse = []
        for o in n.orelse:
            if isinstance(o, N.ElseIf): orelse.append(N.ElseIf(self.visit(o.test), self._v_Block(o.body)))
            else: orelse.append(N.Else(self._v_Block(o.body)))
        return N.If(t, b, orelse)
    def _v_While(self, n):     return N.While(self.visit(n.test), self._v_Block(n.body))
    def _v_Repeat(self, n):    return N.Repeat(self._v_Block(n.body), self.visit(n.test))
    def _v_Do(self, n):        return N.Do(self._v_Block(n.body))
    def _v_Fornumeric(self, n):
        return N.Fornumeric(n.target, self.visit(n.start), self.visit(n.stop),
                            self.visit(n.step) if n.step else None, self._v_Block(n.body))
    def _v_Forin(self, n):
        return N.Forin(n.targets, [self.visit(e) for e in n.iter], self._v_Block(n.body))
    def _v_Function(self, n):      return N.Function(n.name, n.args, self._v_Block(n.body))
    def _v_LocalFunction(self, n): return N.LocalFunction(n.name, n.args, self._v_Block(n.body))
    def _v_Method(self, n):        return N.Method(n.source, n.name, n.args, self._v_Block(n.body))
    def _v_AnonymousFunction(self, n): return N.AnonymousFunction(n.args, self._v_Block(n.body))
    def _v_Table(self, n):
        flds = []
        for f in n.fields:
            if isinstance(f, N.TableField):   flds.append(N.TableField(f.key, self.visit(f.value)))
            elif isinstance(f, N.TableIndex): flds.append(N.TableIndex(self.visit(f.key), self.visit(f.value)))
            else: flds.append(self.visit(f))
        return N.Table(flds)
    # Passthrough
    def _v_Name(self, n):      return n
    def _v_Number(self, n):    return n
    def _v_NilExpr(self, n):   return n
    def _v_TrueExpr(self, n):  return n
    def _v_FalseExpr(self, n): return n
    def _v_Vararg(self, n):    return n
    def _v_Break(self, n):     return n


def run(block, rng):
    return StringEncryptPass(rng).visit(block)
