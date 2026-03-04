"""NightGuard V2 - Pass 5: Control Flow Flattening
Converts top-level if/else blocks into state-machine dispatch.

  if a then foo() else bar() end
  ->
  local _st = 1
  while true do
    if _st == 1 then
      if a then _st = 2 else _st = 3 end
    elseif _st == 2 then foo(); break
    elseif _st == 3 then bar(); break
    else break end
  end
"""
import random, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import ast_nodes as N

def _fresh_state_var(rng):
    chars = 'IlO01'
    return '_' + ''.join(rng.choices(chars, k=8))

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
            if v is not None:
                new_stmts.append(v)
        return N.Block(new_stmts)

    def _v_If(self, n):
        """Flatten if/elseif/else into a state machine (only when there's an else)."""
        # Recurse first
        body = self._v_Block(n.body)
        orelse_visited = []
        for o in n.orelse:
            if isinstance(o, N.ElseIf):
                orelse_visited.append(N.ElseIf(o.test, self._v_Block(o.body)))
            else:
                orelse_visited.append(N.Else(self._v_Block(o.body)))

        # Only flatten if there's a genuine else/elseif (30% chance to avoid bloat)
        has_else = any(isinstance(o, N.Else) for o in orelse_visited)
        if not has_else or self._rng.random() > 0.35:
            return N.If(n.test, body, orelse_visited)

        # Build state machine
        sv = _fresh_state_var(self._rng)
        sn = N.Name(sv)

        def mk_set(val): return N.Assign([sn], [N.Number(val)])

        # State 1: evaluate condition
        # State 2: then-branch  State 3: else-branch
        INIT, THEN, ELSE_ST = 1, 2, 3

        dispatch_cases = []
        # State 1 -> branch
        branch_if = N.If(n.test,
                         N.Block([mk_set(THEN)]),
                         [N.Else(N.Block([mk_set(ELSE_ST)]))])
        dispatch_cases.append((INIT, N.Block([branch_if])))
        # State 2 -> then body + break
        dispatch_cases.append((THEN, N.Block(list(body.body) + [N.Break()])))
        # State 3 -> else body + break
        else_body = N.Block([])
        for o in orelse_visited:
            if isinstance(o, N.Else):
                else_body = o.body; break
        dispatch_cases.append((ELSE_ST, N.Block(list(else_body.body) + [N.Break()])))

        # Build the while loop body as nested if/elseif
        first = True
        while_body_stmts = []
        loop_if = None
        for state_val, state_body in dispatch_cases:
            cond = N.BinOp('==', sn, N.Number(state_val))
            if loop_if is None:
                loop_if = N.If(cond, state_body, [])
            else:
                loop_if.orelse.append(N.ElseIf(cond, state_body))
        # Final else: break
        loop_if.orelse.append(N.Else(N.Block([N.Break()])))
        while_body_stmts.append(loop_if)

        return N.Block([
            N.LocalAssign([sn], [N.Number(INIT)]),
            N.While(N.TrueExpr(), N.Block(while_body_stmts))
        ])

    # Recurse into all other compound statements
    def _v_While(self, n):      return N.While(n.test, self._v_Block(n.body))
    def _v_Repeat(self, n):     return N.Repeat(self._v_Block(n.body), n.test)
    def _v_Do(self, n):         return N.Do(self._v_Block(n.body))
    def _v_Fornumeric(self, n): return N.Fornumeric(n.target, n.start, n.stop, n.step, self._v_Block(n.body))
    def _v_Forin(self, n):      return N.Forin(n.targets, n.iter, self._v_Block(n.body))
    def _v_Function(self, n):   return N.Function(n.name, n.args, self._v_Block(n.body))
    def _v_LocalFunction(self, n): return N.LocalFunction(n.name, n.args, self._v_Block(n.body))
    def _v_Method(self, n):     return N.Method(n.source, n.name, n.args, self._v_Block(n.body))
    def _v_AnonymousFunction(self, n): return N.AnonymousFunction(n.args, self._v_Block(n.body))


def run(block, rng):
    return ControlFlowPass(rng).visit(block)
