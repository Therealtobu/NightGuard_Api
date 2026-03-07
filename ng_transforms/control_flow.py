import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
"""NightGuard V2 - Control Flow Flattening + Noise + Opaque Predicates"""
import random
import ast_nodes as N

def _fresh(rng, prefix='_'):
    chars = 'IlO01'
    return prefix + ''.join(rng.choices(chars, k=rng.randint(7,12)))

# ── Opaque predicates (always true, hard to analyze statically) ───────
def _opaque_true(rng):
    k = rng.randint(0, 5)
    if k == 0:
        # (n * (n+1)) % 2 == 0  -- always true for any integer n
        v = rng.randint(2, 99)
        n = N.Number(v)
        np1 = N.Number(v + 1)
        prod = N.BinOp('*', n, np1)
        return N.BinOp('==', N.BinOp('%', prod, N.Number(2)), N.Number(0))
    elif k == 1:
        # math.floor(x) == x  for integer x
        v = rng.randint(1, 999)
        return N.BinOp('==',
            N.Call(N.Field(N.Name('math'), N.Name('floor')), [N.Number(v)]),
            N.Number(v))
    elif k == 2:
        # x^0 == 1
        v = rng.randint(2, 99)
        return N.BinOp('==', N.BinOp('^', N.Number(v), N.Number(0)), N.Number(1))
    elif k == 3:
        # (x % x) == 0 for x > 0
        v = rng.randint(2, 99)
        return N.BinOp('==', N.BinOp('%', N.Number(v), N.Number(v)), N.Number(0))
    elif k == 4:
        # not false
        return N.UnOp('not', N.FalseExpr())
    else:
        # x >= x
        v = rng.randint(0, 999)
        return N.BinOp('>=', N.Number(v), N.Number(v))

def _opaque_false(rng):
    k = rng.randint(0, 2)
    if k == 0:
        v = rng.randint(2, 99)
        return N.BinOp('==', N.BinOp('%', N.Number(v * 2 + 1), N.Number(2)), N.Number(0))
    elif k == 1:
        return N.BinOp('==', N.Number(1), N.Number(2))
    else:
        return N.BinOp('>', N.Number(0), N.Number(1))

# ── Dead code block (safe no-op) ──────────────────────────────────────
def _dead_block(rng):
    v = _fresh(rng)
    templates = [
        N.Block([N.LocalAssign([N.Name(v)], [N.Number(rng.randint(1,999))])]),
        N.Block([N.LocalAssign([N.Name(v)], [N.BinOp('+', N.Number(rng.randint(1,50)), N.Number(rng.randint(1,50)))])]),
        N.Block([N.LocalAssign([N.Name(v)], [N.String('__ng')])]),
    ]
    return rng.choice(templates)

class ControlFlowPass:
    def __init__(self, rng):
        self._rng = rng

    def visit(self, node):
        m = getattr(self, f'_v_{type(node).__name__}', None)
        return m(node) if m else node

    def _v_Block(self, n):
        new_stmts = []
        for stmt in n.body:
            v = self.visit(stmt)
            if v is None:
                continue
            # 20% chance: wrap real stmt in opaque true predicate
            if self._rng.random() < 0.20:
                pred = _opaque_true(self._rng)
                v = N.If(pred, N.Block([v]), [])
            # 15% chance: insert dead if false block before
            if self._rng.random() < 0.15:
                new_stmts.append(N.If(_opaque_false(self._rng), _dead_block(self._rng), []))
            new_stmts.append(v)
        # 10% chance: append dead block at end
        if self._rng.random() < 0.10:
            new_stmts.append(N.If(_opaque_false(self._rng), _dead_block(self._rng), []))
        return N.Block(new_stmts)

    def _v_If(self, n):
        body = self._v_Block(n.body)
        orelse_v = []
        for o in n.orelse:
            if isinstance(o, N.ElseIf):
                orelse_v.append(N.ElseIf(o.test, self._v_Block(o.body)))
            else:
                orelse_v.append(N.Else(self._v_Block(o.body)))

        has_else = any(isinstance(o, N.Else) for o in orelse_v)
        # Flatten ~40% of if/else into state machine
        if not has_else or self._rng.random() > 0.40:
            return N.If(n.test, body, orelse_v)

        sv = _fresh(self._rng)
        sn = N.Name(sv)
        def mk_set(val): return N.Assign([sn], [N.Number(val)])

        S_COND, S_THEN, S_ELSE = (
            self._rng.randint(10, 99),
            self._rng.randint(100, 199),
            self._rng.randint(200, 299),
        )

        else_body = N.Block([])
        for o in orelse_v:
            if isinstance(o, N.Else):
                else_body = o.body; break

        # Add noise state
        S_NOISE = self._rng.randint(300, 399)
        noise_var = _fresh(self._rng)

        cases = [
            (S_COND,  N.Block([N.If(n.test,
                                    N.Block([mk_set(S_THEN)]),
                                    [N.Else(N.Block([mk_set(S_ELSE)]))])])),
            (S_THEN,  N.Block(list(body.body) + [mk_set(S_NOISE)])),
            (S_ELSE,  N.Block(list(else_body.body) + [mk_set(S_NOISE)])),
            (S_NOISE, N.Block([
                N.LocalAssign([N.Name(noise_var)],
                              [N.BinOp('+', N.Number(self._rng.randint(1,9)), N.Number(self._rng.randint(1,9)))]),
                N.Break()
            ])),
        ]

        loop_if = None
        for state_val, state_body in cases:
            cond = N.BinOp('==', sn, N.Number(state_val))
            if loop_if is None:
                loop_if = N.If(cond, state_body, [])
            else:
                loop_if.orelse.append(N.ElseIf(cond, state_body))
        loop_if.orelse.append(N.Else(N.Block([N.Break()])))

        return N.Block([
            N.LocalAssign([sn], [N.Number(S_COND)]),
            N.While(N.TrueExpr(), N.Block([loop_if]))
        ])

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
