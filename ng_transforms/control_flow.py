import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
"""NightGuard V2 - Control Flow Flattening Engine

Strategy:
  1. Collect ALL top-level statements in a function/block
  2. Assign each a unique state ID (randomized, non-sequential)
  3. Emit: local _st=INIT; while true do if _st==X then ... end end
  4. Every branch tail sets _st to next state
  5. Loops/breaks handled with dedicated states
  6. Opaque predicates guard each state transition
  7. Junk states sprinkled between real ones
"""
import random
import ast_nodes as N

# ─── Helpers ──────────────────────────────────────────────────────────────────

def _iname(rng, length=None):
    length = length or rng.randint(8, 14)
    chars = 'IlO01'
    return '_' + rng.choice('lIO') + ''.join(rng.choices(chars, k=length-1))

def _fresh_ids(rng, count, lo=1000, hi=9999):
    """Generate `count` unique non-sequential state IDs."""
    pool = random.sample(range(lo, hi), count * 3)
    rng.shuffle(pool)
    return pool[:count]

# ─── Opaque predicates ────────────────────────────────────────────────────────
# Use math that's provably constant but looks dynamic to a static analyser

def _opaque_true(rng):
    k = rng.randint(0, 9)
    if k == 0:
        # n*(n+1) always even
        v = rng.randint(3, 97)
        return N.BinOp('==',
            N.BinOp('%', N.BinOp('*', N.Number(v), N.Number(v+1)), N.Number(2)),
            N.Number(0))
    elif k == 1:
        # n^2 >= 0
        v = rng.randint(1, 999)
        return N.BinOp('>=', N.BinOp('*', N.Number(v), N.Number(v)), N.Number(0))
    elif k == 2:
        # math.max(a,b) >= a
        a, b = rng.randint(1, 50), rng.randint(51, 100)
        return N.BinOp('>=',
            N.Call(N.Field(N.Name('math'), N.Name('max')), [N.Number(a), N.Number(b)]),
            N.Number(a))
    elif k == 3:
        # (a+b)*(a+b) == a*a + 2*a*b + b*b  (quadratic identity)
        a, b = rng.randint(1, 20), rng.randint(1, 20)
        lhs = N.BinOp('*', N.BinOp('+', N.Number(a), N.Number(b)),
                            N.BinOp('+', N.Number(a), N.Number(b)))
        rhs = N.Number(a*a + 2*a*b + b*b)
        return N.BinOp('==', lhs, rhs)
    elif k == 4:
        # math.abs(x) == x for x>0
        v = rng.randint(1, 999)
        return N.BinOp('==',
            N.Call(N.Field(N.Name('math'), N.Name('abs')), [N.Number(v)]),
            N.Number(v))
    elif k == 5:
        # x % 1 == 0 for integer x
        v = rng.randint(2, 999)
        return N.BinOp('==', N.BinOp('%', N.Number(v), N.Number(1)), N.Number(0))
    elif k == 6:
        # math.floor(n/1) == n
        v = rng.randint(1, 999)
        return N.BinOp('==',
            N.Call(N.Field(N.Name('math'), N.Name('floor')),
                   [N.BinOp('/', N.Number(v), N.Number(1))]),
            N.Number(v))
    elif k == 7:
        # (a-b)^2 >= 0
        a, b = rng.randint(1, 50), rng.randint(1, 50)
        diff = N.BinOp('-', N.Number(a), N.Number(b))
        return N.BinOp('>=', N.BinOp('*', diff,
            N.BinOp('-', N.Number(a), N.Number(b))), N.Number(0))
    elif k == 8:
        # string.len("x"*n) == n
        s = 'x' * rng.randint(1, 8)
        return N.BinOp('==',
            N.Call(N.Field(N.Name('string'), N.Name('len')), [N.String(s)]),
            N.Number(len(s)))
    else:
        # type(math) == "table"
        return N.BinOp('==',
            N.Call(N.Name('type'), [N.Name('math')]),
            N.String('table'))

def _opaque_false(rng):
    k = rng.randint(0, 5)
    if k == 0:
        # odd % 2 == 0  (always false)
        v = rng.randint(1, 49) * 2 + 1
        return N.BinOp('==', N.BinOp('%', N.Number(v), N.Number(2)), N.Number(0))
    elif k == 1:
        # n^2 < 0
        v = rng.randint(1, 99)
        return N.BinOp('<', N.BinOp('*', N.Number(v), N.Number(v)), N.Number(0))
    elif k == 2:
        # math.max(a,b) < a  where b > a
        a, b = rng.randint(1, 50), rng.randint(51, 100)
        return N.BinOp('<',
            N.Call(N.Field(N.Name('math'), N.Name('max')), [N.Number(a), N.Number(b)]),
            N.Number(a))
    elif k == 3:
        # a+b < a  where b > 0
        a, b = rng.randint(10, 50), rng.randint(1, 9)
        return N.BinOp('<', N.BinOp('+', N.Number(a), N.Number(b)), N.Number(a))
    elif k == 4:
        # type(math) == "number"
        return N.BinOp('==',
            N.Call(N.Name('type'), [N.Name('math')]),
            N.String('number'))
    else:
        # math.abs(-x) < 0
        v = rng.randint(1, 99)
        return N.BinOp('<',
            N.Call(N.Field(N.Name('math'), N.Name('abs')), [N.Number(-v)]),
            N.Number(0))

def _junk_stmt(rng):
    """Dead assignment that never executes."""
    v = _iname(rng)
    ops = [
        N.LocalAssign([N.Name(v)], [N.Number(rng.randint(1, 9999))]),
        N.LocalAssign([N.Name(v)], [N.BinOp('*', N.Number(rng.randint(1,99)), N.Number(rng.randint(1,99)))]),
        N.LocalAssign([N.Name(v)], [N.Call(N.Field(N.Name('math'), N.Name('pi')), [])]),
    ]
    return N.If(_opaque_false(rng), N.Block([rng.choice(ops)]), [])

# ─── Core flattener ───────────────────────────────────────────────────────────

class _Stmt:
    """Wrapper: one logical statement + its assigned state ID."""
    def __init__(self, sid, node):
        self.sid  = sid
        self.node = node

def _is_compound(node):
    return isinstance(node, (N.If, N.While, N.Repeat, N.Fornumeric, N.Forin, N.Do))

def _terminates(node):
    """True if node unconditionally ends control flow (return/break)."""
    if isinstance(node, (N.Return, N.Break)):
        return True
    if isinstance(node, N.Block):
        return bool(node.body) and _terminates(node.body[-1])
    return False

class ControlFlowPass:
    def __init__(self, rng):
        self._rng = rng

    # ── Public entry ──────────────────────────────────────────────────────
    def visit(self, node):
        m = getattr(self, f'_v_{type(node).__name__}', None)
        return m(node) if m else node

    # ── Block: always flatten ALL statements into a state machine ─────────
    def _v_Block(self, blk):
        # Recurse into children first
        stmts = []
        for s in blk.body:
            v = self.visit(s)
            if v is not None:
                stmts.append(v)

        # Don't flatten trivially small blocks (≤1 stmt) — no point
        if len(stmts) <= 1:
            return N.Block(stmts)

        # Don't flatten blocks that are already inside a state-machine loop
        # (detected by presence of only Break/Return at top level — rare edge case)
        return self._flatten_block(stmts)

    def _flatten_block(self, stmts):
        """Convert a flat list of statements into a dispatch state machine."""
        rng = self._rng

        # Assign random non-sequential IDs to each statement
        n = len(stmts)
        ids = _fresh_ids(rng, n + 2)   # +2: INIT, DONE
        s_init = ids[0]
        s_done = ids[1]
        state_ids = ids[2: 2 + n]

        # Build transition map: state_ids[i] -> state_ids[i+1] or s_done
        def next_id(i):
            return state_ids[i + 1] if i + 1 < n else s_done

        sv = _iname(rng)   # state variable name
        sn = N.Name(sv)

        def mk_set(val):
            return N.Assign([sn], [N.Number(val)])

        # Build each case body
        # For statements that transfer control (return/break), don't append transition
        cases = []
        for i, stmt in enumerate(stmts):
            nid = next_id(i)
            body_stmts = [stmt]
            if not _terminates(stmt):
                body_stmts.append(mk_set(nid))
            # Wrap body in opaque-true guard (25% chance per case for noise)
            if rng.random() < 0.25:
                inner = N.Block(body_stmts)
                body_stmts = [N.If(_opaque_true(rng), inner, [])]
            cases.append((state_ids[i], N.Block(body_stmts)))

        # DONE state: break
        cases.append((s_done, N.Block([N.Break()])))

        # Shuffle cases (makes pattern matching harder)
        rng.shuffle(cases)

        # Intersperse junk states between real ones (1 junk per 2 real)
        junk_count = max(1, n // 2)
        junk_ids = _fresh_ids(rng, junk_count, lo=10000, hi=99999)
        junk_cases = []
        for jid in junk_ids:
            jv = _iname(rng)
            junk_cases.append((jid, N.Block([
                N.LocalAssign([N.Name(jv)], [N.Number(rng.randint(1, 9999))]),
                N.Break()   # junk states never reached, just noise
            ])))

        all_cases = cases + junk_cases
        rng.shuffle(all_cases)

        # Build the dispatch chain: if _st==X then ... elseif _st==Y then ...
        loop_if = None
        for (sid, sbody) in all_cases:
            cond = N.BinOp('==', sn, N.Number(sid))
            if loop_if is None:
                loop_if = N.If(cond, sbody, [])
            else:
                loop_if.orelse.append(N.ElseIf(cond, sbody))
        # Final else: break (safety)
        loop_if.orelse.append(N.Else(N.Block([N.Break()])))

        return N.Block([
            N.LocalAssign([sn], [N.Number(s_init)]),
            N.Assign([sn], [N.Number(state_ids[0])]),   # set to first real state
            N.While(N.TrueExpr(), N.Block([loop_if]))
        ])

    # ── Compound statements: recurse, but handle loops specially ──────────

    def _v_If(self, n):
        body = self._v_Block(n.body)
        orelse_v = []
        for o in n.orelse:
            if isinstance(o, N.ElseIf):
                orelse_v.append(N.ElseIf(o.test, self._v_Block(o.body)))
            else:
                orelse_v.append(N.Else(self._v_Block(o.body)))
        return N.If(n.test, body, orelse_v)

    def _v_While(self, n):
        return N.While(n.test, self._v_Block(n.body))

    def _v_Repeat(self, n):
        return N.Repeat(self._v_Block(n.body), n.test)

    def _v_Do(self, n):
        return N.Do(self._v_Block(n.body))

    def _v_Fornumeric(self, n):
        return N.Fornumeric(n.target, n.start, n.stop, n.step, self._v_Block(n.body))

    def _v_Forin(self, n):
        return N.Forin(n.targets, n.iter, self._v_Block(n.body))

    def _v_Function(self, n):
        return N.Function(n.name, n.args, self._v_Block(n.body))

    def _v_LocalFunction(self, n):
        return N.LocalFunction(n.name, n.args, self._v_Block(n.body))

    def _v_Method(self, n):
        return N.Method(n.source, n.name, n.args, self._v_Block(n.body))

    def _v_AnonymousFunction(self, n):
        return N.AnonymousFunction(n.args, self._v_Block(n.body))


def run(block, rng):
    return ControlFlowPass(rng).visit(block)
