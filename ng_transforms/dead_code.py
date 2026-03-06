"""NightGuard V2 - Pass 4: Dead Code + Opaque Predicate Injection
Inserts:
  - if false then ... end  (dead blocks)
  - if (1+1==2) then existing_block end  (opaque predicates wrapping real code)
"""
import random, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import ast_nodes as N

# Templates for dead code bodies
_DEAD_TEMPLATES = [
    lambda: N.Block([N.LocalAssign([N.Name('_')], [N.Call(N.Field(N.Name('math'), N.Name('random')), [])])]),
    lambda: N.Block([N.LocalAssign([N.Name('_')], [N.BinOp('+', N.Number(1), N.Number(1))])]),
    lambda: N.Block([N.LocalAssign([N.Name('_')], [N.String('night')])]),
    lambda: N.Block([N.Return([N.NilExpr()])]),
]

# Opaque predicates that always evaluate true
_TRUE_PREDICATES = [
    lambda: N.BinOp('==', N.BinOp('+', N.Number(1), N.Number(1)), N.Number(2)),
    lambda: N.BinOp('~=', N.Number(0), N.Number(1)),
    lambda: N.BinOp('>=', N.Number(5), N.Number(5)),
    lambda: N.BinOp('==', N.BinOp('%', N.Number(4), N.Number(2)), N.Number(0)),
    lambda: N.UnOp('not', N.FalseExpr()),
]


class DeadCodePass:
    def __init__(self, rng):
        self._rng = rng

    def _dead_if(self):
        body = self._rng.choice(_DEAD_TEMPLATES)()
        return N.If(N.FalseExpr(), body, [])

    def _opaque_wrap(self, stmts):
        pred = self._rng.choice(_TRUE_PREDICATES)()
        return N.If(pred, N.Block(stmts), [])

    def visit(self, node):
        m = getattr(self, f'_v_{type(node).__name__}', None)
        return m(node) if m else node

    def _v_Block(self, n):
        new_stmts = []
        for stmt in n.body:
            visited = self.visit(stmt)
            if visited is None: continue
            # Randomly insert dead block before
            if self._rng.random() < 0.15:
                new_stmts.append(self._dead_if())
            # Randomly wrap in opaque predicate
            if self._rng.random() < 0.12:
                new_stmts.append(self._opaque_wrap([visited]))
            else:
                new_stmts.append(visited)
        # Occasionally append a dead block at end
        if self._rng.random() < 0.1:
            new_stmts.append(self._dead_if())
        return N.Block(new_stmts)

    # Recurse into sub-blocks
    def _v_If(self, n):
        b = self._v_Block(n.body)
        orelse = []
        for o in n.orelse:
            if isinstance(o, N.ElseIf): orelse.append(N.ElseIf(o.test, self._v_Block(o.body)))
            else: orelse.append(N.Else(self._v_Block(o.body)))
        return N.If(n.test, b, orelse)
    def _v_While(self, n):    return N.While(n.test, self._v_Block(n.body))
    def _v_Repeat(self, n):   return N.Repeat(self._v_Block(n.body), n.test)
    def _v_Do(self, n):       return N.Do(self._v_Block(n.body))
    def _v_Fornumeric(self, n): return N.Fornumeric(n.target, n.start, n.stop, n.step, self._v_Block(n.body))
    def _v_Forin(self, n):    return N.Forin(n.targets, n.iter, self._v_Block(n.body))
    def _v_Function(self, n): return N.Function(n.name, n.args, self._v_Block(n.body))
    def _v_LocalFunction(self, n): return N.LocalFunction(n.name, n.args, self._v_Block(n.body))
    def _v_Method(self, n):   return N.Method(n.source, n.name, n.args, self._v_Block(n.body))
    def _v_AnonymousFunction(self, n): return N.AnonymousFunction(n.args, self._v_Block(n.body))


def run(block, rng):
    return DeadCodePass(rng).visit(block)
