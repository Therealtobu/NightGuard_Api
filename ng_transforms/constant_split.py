"""NightGuard V2 - Pass 3: Constant Splitting
Splits numeric literals: 100 -> (40 + 60) or (50 * 2) etc.
"""
import random, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import ast_nodes as N

class ConstantSplitPass:
    def __init__(self, rng):
        self._rng = rng

    def _split_num(self, val):
        """Return a BinOp that evaluates to val, or None to leave unchanged."""
        if not isinstance(val, (int, float)): return None
        if val == 0: return None
        if abs(val) > 1e9: return None   # don't split huge numbers

        rng = self._rng
        choice = rng.randint(0, 3)
        try:
            if choice == 0:
                # a + b where a + b = val
                a = rng.randint(1, max(1, int(abs(val)) - 1)) * (1 if val >= 0 else -1)
                b = val - a
                return N.BinOp('+', N.Number(a), N.Number(b))
            elif choice == 1:
                # a - b
                a = val + rng.randint(1, max(1, int(abs(val))))
                b = a - val
                return N.BinOp('-', N.Number(a), N.Number(b))
            elif choice == 2 and val != 0 and isinstance(val, int) and abs(val) < 10000:
                # a * b
                for _ in range(10):
                    f = rng.randint(2, max(2, int(abs(val) ** 0.5) + 1))
                    if val % f == 0:
                        return N.BinOp('*', N.Number(val // f), N.Number(f))
            elif choice == 3:
                # val ^ 0 + val  -- too obvious. Use: (val + 1) - 1
                return N.BinOp('-', N.BinOp('+', N.Number(val), N.Number(1)), N.Number(1))
        except Exception:
            pass
        return None

    def visit(self, node):
        m = getattr(self, f'_v_{type(node).__name__}', None)
        return m(node) if m else node

    def _v_Block(self, n): return N.Block([r for r in (self.visit(s) for s in n.body) if r is not None])

    def _v_Number(self, n):
        # Only split ~40% of the time to avoid too much bloat
        if self._rng.random() < 0.4:
            split = self._split_num(n.n)
            if split: return split
        return n

    # Passthrough visitors
    def _v_LocalAssign(self, n):  return N.LocalAssign(n.targets, [self.visit(v) for v in n.values])
    def _v_Assign(self, n):       return N.Assign(n.targets, [self.visit(v) for v in n.values])
    def _v_Return(self, n):       return N.Return([self.visit(v) for v in n.values])
    def _v_BinOp(self, n):        return N.BinOp(n.op, self.visit(n.left), self.visit(n.right))
    def _v_UnOp(self, n):         return N.UnOp(n.op, self.visit(n.operand))
    def _v_Call(self, n):         return N.Call(self.visit(n.func), [self.visit(a) for a in n.args])
    def _v_Invoke(self, n):       return N.Invoke(self.visit(n.source), n.func, [self.visit(a) for a in n.args])
    def _v_Field(self, n):        return N.Field(self.visit(n.value), n.key)
    def _v_Index(self, n):        return N.Index(self.visit(n.value), self.visit(n.key))
    def _v_If(self, n):
        orelse = []
        for o in n.orelse:
            if isinstance(o, N.ElseIf): orelse.append(N.ElseIf(self.visit(o.test), self._v_Block(o.body)))
            else: orelse.append(N.Else(self._v_Block(o.body)))
        return N.If(self.visit(n.test), self._v_Block(n.body), orelse)
    def _v_While(self, n):        return N.While(self.visit(n.test), self._v_Block(n.body))
    def _v_Repeat(self, n):       return N.Repeat(self._v_Block(n.body), self.visit(n.test))
    def _v_Do(self, n):           return N.Do(self._v_Block(n.body))
    def _v_Fornumeric(self, n):   return N.Fornumeric(n.target, self.visit(n.start), self.visit(n.stop), self.visit(n.step) if n.step else None, self._v_Block(n.body))
    def _v_Forin(self, n):        return N.Forin(n.targets, [self.visit(e) for e in n.iter], self._v_Block(n.body))
    def _v_Function(self, n):     return N.Function(n.name, n.args, self._v_Block(n.body))
    def _v_LocalFunction(self, n):return N.LocalFunction(n.name, n.args, self._v_Block(n.body))
    def _v_Method(self, n):       return N.Method(n.source, n.name, n.args, self._v_Block(n.body))
    def _v_AnonymousFunction(self, n): return N.AnonymousFunction(n.args, self._v_Block(n.body))
    def _v_Table(self, n):
        flds = []
        for f in n.fields:
            if isinstance(f, N.TableField):   flds.append(N.TableField(f.key, self.visit(f.value)))
            elif isinstance(f, N.TableIndex): flds.append(N.TableIndex(self.visit(f.key), self.visit(f.value)))
            else: flds.append(self.visit(f))
        return N.Table(flds)
    def _v_Name(self, n):      return n
    def _v_String(self, n):    return n
    def _v_NilExpr(self, n):   return n
    def _v_TrueExpr(self, n):  return n
    def _v_FalseExpr(self, n): return n
    def _v_Vararg(self, n):    return n
    def _v_Break(self, n):     return n


def run(block, rng):
    return ConstantSplitPass(rng).visit(block)
