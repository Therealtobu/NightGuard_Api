import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
"""NightGuard V2 - Randomized Opcode Table + Instruction Encoding Layout"""
import random

_LOGICAL_OPCODES = [
    ('LOAD_CONST', 2), ('LOAD_NIL', 1), ('LOAD_BOOL', 1),
    ('LOAD_LOCAL', 2), ('STORE_LOCAL', 2),
    ('LOAD_GLOBAL', 2), ('STORE_GLOBAL', 1),
    ('NEW_TABLE', 1), ('GET_TABLE', 1), ('SET_TABLE', 1),
    ('GET_FIELD', 2), ('SET_FIELD', 1),
    ('CALL', 2), ('RETURN', 2),
    ('JUMP', 2), ('JUMP_TRUE', 1), ('JUMP_FALSE', 1),
    ('JUMP_TRUE_POP', 1), ('JUMP_FALSE_POP', 1),
    ('POP', 1),
    ('ADD', 2), ('ADD_ALT', 1),
    ('SUB', 2), ('MUL', 2), ('DIV', 1), ('MOD', 1), ('POW', 1),
    ('CONCAT', 2),
    ('UNM', 1), ('NOT', 1), ('LEN', 1),
    ('EQ', 2), ('NEQ', 1), ('LT', 1), ('LE', 1), ('GT', 1), ('GE', 1),
    ('MAKE_CLOSURE', 1),
    ('DUP', 1), ('SWAP', 1),
    ('VARARG', 1), ('SELF', 1),
    ('JUNK', 1), ('FAKE_STACK', 1), ('FAKE_MATH', 1),
]

_ALIAS_MAP = {'ADD_ALT': 'ADD'}
_FAKE_OPS  = {'JUNK', 'FAKE_STACK', 'FAKE_MATH'}

# Possible instruction encoding layouts
# Each layout: (op_shift, op_bits, a_shift, a_bits, b_shift, b_bits)
_LAYOUTS = [
    (24, 8, 12, 12,  0, 12),   # default: op[31:24] A[23:12] B[11:0]
    (24, 8,  0, 12, 12, 12),   # swap A and B positions
    (16, 8, 24,  8,  0, 16),   # op in middle
    (20, 8,  8, 12,  0,  8),   # compact
]

class Opcodes:
    def __init__(self, seed=None):
        rng = random.Random(seed)

        # Build opcode table
        entries = []
        for name, n_aliases in _LOGICAL_OPCODES:
            canonical = _ALIAS_MAP.get(name, name)
            entries.append((canonical, name))
            for i in range(1, n_aliases):
                entries.append((canonical, f'{name}_V{i}'))

        rng.shuffle(entries)
        self._name2val  = {}
        self._val2canon = {}
        for i, (canon, alias) in enumerate(entries):
            self._name2val[alias]  = i
            self._val2canon[i]     = canon

        self._canon2vals = {}
        for alias, val in self._name2val.items():
            canon = self._val2canon[val]
            self._canon2vals.setdefault(canon, []).append(val)

        self._rng = rng

        # Pick random instruction encoding layout for this build
        layout = rng.choice(_LAYOUTS)
        op_shift, op_bits, a_shift, a_bits, b_shift, b_bits = layout
        op_mask = (1 << op_bits) - 1
        a_mask  = (1 << a_bits)  - 1
        b_mask  = (1 << b_bits)  - 1
        self.__dict__['layout']       = layout  # (op_shift, op_bits, a_shift, a_bits, b_shift, b_bits)

        def _pack(op, a, b):
            return ((op & op_mask) << op_shift) | ((a & a_mask) << a_shift) | (b & b_mask)
        def _unpack(i):
            return (i >> op_shift) & op_mask, (i >> a_shift) & a_mask, i & b_mask

        self.__dict__['pack_instr']   = _pack
        self.__dict__['unpack_instr'] = _unpack

    def get(self, name: str) -> int:
        canon = _ALIAS_MAP.get(name, name)
        vals  = self._canon2vals.get(canon) or self._canon2vals.get(name)
        if vals is None: raise KeyError(f"Unknown opcode: {name}")
        return self._rng.choice(vals)

    def all_values(self, name: str) -> list:
        canon = _ALIAS_MAP.get(name, name)
        return list(self._canon2vals.get(canon, []))

    def canonical(self, val: int) -> str:
        return self._val2canon.get(val, 'UNKNOWN')

    def is_fake(self, val: int) -> bool:
        return self.canonical(val) in _FAKE_OPS

    def all(self) -> dict:
        return dict(self._name2val)

    def __getattr__(self, name):
        if name.startswith('_') or name in ('pack_instr', 'unpack_instr', 'layout'):
            raise AttributeError(name)
        return self.get(name)
