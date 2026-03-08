import sys,os;sys.path.insert(0,os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import random
import ast_nodes as N

def _iname(rng):
    chars='lI0O1'
    return '_'+''.join(rng.choice(chars) for _ in range(rng.randint(8,12)))

def _opaque_true(rng):
    """Pure-arithmetic always-true predicates — no function calls."""
    k = rng.randint(0, 9)
    if k == 0:
        # n*(n+1) always even  →  n*(n+1)%2 == 0
        v = rng.randint(3, 97)
        return N.BinOp('==',
            N.BinOp('%', N.BinOp('*', N.Number(v), N.Number(v+1)), N.Number(2)),
            N.Number(0))
    elif k == 1:
        # n^2 >= 0
        v = rng.randint(1, 999)
        return N.BinOp('>=', N.BinOp('*', N.Number(v), N.Number(v)), N.Number(0))
    elif k == 2:
        # (a+b)*(a+b) == a*a + 2*a*b + b*b
        a, b = rng.randint(1, 20), rng.randint(1, 20)
        lhs = N.BinOp('*', N.BinOp('+', N.Number(a), N.Number(b)),
                            N.BinOp('+', N.Number(a), N.Number(b)))
        return N.BinOp('==', lhs, N.Number(a*a + 2*a*b + b*b))
    elif k == 3:
        # x % 1 == 0  for integer x
        v = rng.randint(2, 999)
        return N.BinOp('==', N.BinOp('%', N.Number(v), N.Number(1)), N.Number(0))
    elif k == 4:
        # (a-b)^2 >= 0
        a, b = rng.randint(1, 50), rng.randint(1, 50)
        diff = N.BinOp('-', N.Number(a), N.Number(b))
        return N.BinOp('>=',
            N.BinOp('*', diff, N.BinOp('-', N.Number(a), N.Number(b))),
            N.Number(0))
    elif k == 5:
        # a*a - b*b == (a-b)*(a+b)
        a, b = rng.randint(2, 30), rng.randint(1, 20)
        lhs = N.BinOp('-', N.BinOp('*', N.Number(a), N.Number(a)),
                           N.BinOp('*', N.Number(b), N.Number(b)))
        rhs = N.BinOp('*', N.BinOp('-', N.Number(a), N.Number(b)),
                           N.BinOp('+', N.Number(a), N.Number(b)))
        return N.BinOp('==', lhs, rhs)
    elif k == 6:
        # sum of arithmetic series: 1+2+...+n = n*(n+1)/2
        n = rng.randint(3, 20)
        total = n*(n+1)//2
        # express as: n*(n+1) == total*2
        return N.BinOp('==',
            N.BinOp('*', N.Number(n), N.Number(n+1)),
            N.Number(total*2))
    elif k == 7:
        # (a % m) + (b % m) always same parity check: a*2 >= a
        v = rng.randint(1, 500)
        return N.BinOp('>=', N.BinOp('*', N.Number(v), N.Number(2)), N.Number(v))
    elif k == 8:
        # odd number squared is odd: v^2 % 2 == 1
        v = rng.randint(1, 49)*2 + 1  # odd
        return N.BinOp('==',
            N.BinOp('%', N.BinOp('*', N.Number(v), N.Number(v)), N.Number(2)),
            N.Number(1))
    else:
        # a + 0 == a
        v = rng.randint(1, 9999)
        return N.BinOp('==', N.BinOp('+', N.Number(v), N.Number(0)), N.Number(v))

def _opaque_false(rng):
    """Pure-arithmetic always-false predicates — no function calls."""
    k = rng.randint(0, 5)
    if k == 0:
        # odd % 2 == 0  (always false)
        v = rng.randint(1, 49)*2 + 1
        return N.BinOp('==', N.BinOp('%', N.Number(v), N.Number(2)), N.Number(0))
    elif k == 1:
        # n*n < 0  (always false for real n)
        v = rng.randint(1, 99)
        return N.BinOp('<', N.BinOp('*', N.Number(v), N.Number(v)), N.Number(0))
    elif k == 2:
        # a + b < a  where b > 0  (always false)
        a, b = rng.randint(10, 50), rng.randint(1, 9)
        return N.BinOp('<', N.BinOp('+', N.Number(a), N.Number(b)), N.Number(a))
    elif k == 3:
        # a*2 < a  where a > 0  (always false)
        v = rng.randint(1, 500)
        return N.BinOp('<', N.BinOp('*', N.Number(v), N.Number(2)), N.Number(v))
    elif k == 4:
        # n*(n+1) % 2 == 1  (always false — product of consecutive integers is always even)
        v = rng.randint(2, 50)
        return N.BinOp('==',
            N.BinOp('%', N.BinOp('*', N.Number(v), N.Number(v+1)), N.Number(2)),
            N.Number(1))
    else:
        # a*a + 1 <= 0  (always false)
        v = rng.randint(1, 99)
        return N.BinOp('<=',
            N.BinOp('+', N.BinOp('*', N.Number(v), N.Number(v)), N.Number(1)),
            N.Number(0))

def _junk_stmt(rng):
    """Dead assignment that never executes."""
    v = _iname(rng)
    ops = [
        N.LocalAssign([N.Name(v)], [N.Number(rng.randint(1, 9999))]),
        N.LocalAssign([N.Name(v)], [N.BinOp('*', N.Number(rng.randint(1,99)), N.Number(rng.randint(1,99)))]),
        N.LocalAssign([N.Name(v)], [N.BinOp('+', N.Number(rng.randint(1,50)), N.Number(rng.randint(1,50)))]),
        N.LocalAssign([N.Name(v)], [N.String('__ng')]),
        N.LocalAssign([N.Name(v)], [N.NilExpr()]),
    ]
    return rng.choice(ops)

class ControlFlowPass:
    """Wrap real code in opaque-true guards; insert dead opaque-false blocks."""
    def __init__(self, rng):
        self._rng = rng

    def visit(self, node):
        m = getattr(self, f'_v_{type(node).__name__}', None)
        return m(node) if m else node

    def _v_Block(self, n):
        new_stmts = []
        for stmt in n.body:
            visited = self.visit(stmt)
            if visited is None:
                continue
            # 15% chance: wrap in opaque true
            if self._rng.random() < 0.15:
                new_stmts.append(N.If(_opaque_true(self._rng), N.Block([visited]), []))
            else:
                new_stmts.append(visited)
            # 12% chance: insert dead block after
            if self._rng.random() < 0.12:
                new_stmts.append(N.If(_opaque_false(self._rng),
                    N.Block([_junk_stmt(self._rng)]), []))
        return N.Block(new_stmts)

    def _v_If(self, n):
        b = self._v_Block(n.body)
        orelse = []
        for o in n.orelse:
            if isinstance(o, N.ElseIf): orelse.append(N.ElseIf(o.test, self._v_Block(o.body)))
            else: orelse.append(N.Else(self._v_Block(o.body)))
        return N.If(n.test, b, orelse)
    def _v_While(self, n):         return N.While(n.test, self._v_Block(n.body))
    def _v_Repeat(self, n):        return N.Repeat(self._v_Block(n.body), n.test)
    def _v_Do(self, n):            return N.Do(self._v_Block(n.body))
    def _v_Fornumeric(self, n):    return N.Fornumeric(n.target, n.start, n.stop, n.step, self._v_Block(n.body))
    def _v_Forin(self, n):         return N.Forin(n.targets, n.iter, self._v_Block(n.body))
    def _v_Function(self, n):      return N.Function(n.name, n.args, self._v_Block(n.body))
    def _v_LocalFunction(self, n): return N.LocalFunction(n.name, n.args, self._v_Block(n.body))
    def _v_Method(self, n):        return N.Method(n.source, n.name, n.args, self._v_Block(n.body))
    def _v_AnonymousFunction(self, n): return N.AnonymousFunction(n.args, self._v_Block(n.body))

def run(block, rng):
    return ControlFlowPass(rng).visit(block)
