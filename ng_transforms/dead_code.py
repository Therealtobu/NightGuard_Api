import sys,os;sys.path.insert(0,os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import random
import ast_nodes as N
from ng_transforms.control_flow import _opaque_false, _opaque_true, _iname

def _dead_block(rng):
    v = _iname(rng)
    k = rng.randint(0, 4)
    if k == 0:
        return N.Block([N.LocalAssign([N.Name(v)], [N.Number(rng.randint(1,9999))])])
    elif k == 1:
        a, b = rng.randint(1,50), rng.randint(1,50)
        return N.Block([N.LocalAssign([N.Name(v)], [N.BinOp('*', N.Number(a), N.Number(b))])])
    elif k == 2:
        return N.Block([N.LocalAssign([N.Name(v)], [N.String('__ng')])])
    elif k == 3:
        return N.Block([N.LocalAssign([N.Name(v)], [N.NilExpr()])])
    else:
        inner = N.Block([N.LocalAssign([N.Name(_iname(rng))], [N.Number(rng.randint(1,99))])])
        return N.Block([N.If(_opaque_false(rng), inner, [])])


class DeadCodePass:
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
            # 20% insert dead block before
            if self._rng.random() < 0.20:
                new_stmts.append(N.If(_opaque_false(self._rng), _dead_block(self._rng), []))
            # 18% wrap in opaque true
            if self._rng.random() < 0.18:
                new_stmts.append(N.If(_opaque_true(self._rng), N.Block([visited]), []))
            else:
                new_stmts.append(visited)
        # 12% dead block at end
        if self._rng.random() < 0.12:
            new_stmts.append(N.If(_opaque_false(self._rng), _dead_block(self._rng), []))
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
    return DeadCodePass(rng).visit(block)
