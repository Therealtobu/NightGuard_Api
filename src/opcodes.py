"""
Night - Opcode Definitions
Each build gets a freshly shuffled opcode table so bytecode is non-standard.
"""

import random

# Canonical opcode names in fixed logical order.
# The *values* are randomized per build.
OPCODE_NAMES = [
    'LOAD_CONST',    # A: push consts[A]
    'LOAD_NIL',      # push nil
    'LOAD_BOOL',     # A: push (A!=0)
    'LOAD_LOCAL',    # A: push locals[A]
    'STORE_LOCAL',   # A: locals[A] = pop()
    'LOAD_GLOBAL',   # A: push env[consts[A]]
    'STORE_GLOBAL',  # A: env[consts[A]] = pop()
    'LOAD_UPVAL',    # A: push upvals[A]
    'STORE_UPVAL',   # A: upvals[A] = pop()
    'NEW_TABLE',     # push {}
    'GET_TABLE',     # pop key; pop tbl; push tbl[key]
    'SET_TABLE',     # pop val; pop key; pop tbl; tbl[key]=val
    'GET_FIELD',     # A: pop tbl; push tbl[consts[A]]
    'SET_FIELD',     # A: pop val; pop tbl; tbl[consts[A]]=val
    'CALL',          # A=nargs, B=nret
    'RETURN',        # A=nvals  (0 = return nothing)
    'JUMP',          # A=target pc (1-based)
    'JUMP_TRUE',     # A=target; if stack[sp] then pc=A (don't pop)
    'JUMP_FALSE',    # A=target; if not stack[sp] then pc=A (don't pop)
    'JUMP_TRUE_POP', # A=target; if stack[sp] then pc=A; sp--
    'JUMP_FALSE_POP',# A=target; if not stack[sp] then pc=A; sp--
    'POP',           # sp--
    'ADD',           # pop b; stk[sp] = stk[sp]+b
    'SUB',           # pop b; stk[sp] = stk[sp]-b
    'MUL',           # pop b; stk[sp] = stk[sp]*b
    'DIV',           # pop b; stk[sp] = stk[sp]/b
    'MOD',           # pop b; stk[sp] = stk[sp]%b
    'POW',           # pop b; stk[sp] = stk[sp]^b
    'CONCAT',        # pop b; stk[sp] = stk[sp]..b
    'UNM',           # stk[sp] = -stk[sp]
    'NOT',           # stk[sp] = not stk[sp]
    'LEN',           # stk[sp] = #stk[sp]
    'EQ',            # pop b; stk[sp] = (stk[sp]==b)
    'NEQ',           # pop b; stk[sp] = (stk[sp]~=b)
    'LT',            # pop b; stk[sp] = (stk[sp]<b)
    'LE',            # pop b; stk[sp] = (stk[sp]<=b)
    'GT',            # pop b; stk[sp] = (stk[sp]>b)
    'GE',            # pop b; stk[sp] = (stk[sp]>=b)
    'MAKE_CLOSURE',  # A=proto_idx; create closure from p[A]; capture upvals
    'DUP',           # push stk[sp]  (duplicate top)
    'SWAP',          # stk[sp],stk[sp-1] = stk[sp-1],stk[sp]
    'VARARG',        # A=n; push n varargs (0=push all)
    'JUNK',          # no-op (anti-analysis padding)
    'SELF',          # A: peek obj; push obj[consts[A]]; swap  → [method,obj]
]

N_OPCODES = len(OPCODE_NAMES)


class Opcodes:
    """
    Holds a randomly-shuffled opcode mapping for one build.

    Usage:
        op = Opcodes()
        vm_code = vm_gen.generate(op)
        # use op.LOAD_CONST, op.CALL, etc. in the compiler
    """

    def __init__(self, seed=None):
        rng = random.Random(seed)
        values = list(range(N_OPCODES))
        rng.shuffle(values)
        self._n2v: dict[str, int] = dict(zip(OPCODE_NAMES, values))
        self._v2n: dict[int, str] = {v: k for k, v in self._n2v.items()}

    # Attribute access: op.LOAD_CONST  →  integer value
    def __getattr__(self, name: str) -> int:
        if name.startswith('_'):
            raise AttributeError(name)
        try:
            return self._n2v[name]
        except KeyError:
            raise AttributeError(f"Opcodes has no attribute {name!r}")

    def get(self, name: str) -> int:
        return self._n2v[name]

    def name(self, value: int) -> str:
        return self._v2n.get(value, f'OP_{value}')

    def all(self) -> dict[str, int]:
        return dict(self._n2v)
