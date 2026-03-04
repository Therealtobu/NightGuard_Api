"""
NightGuard V2 - Randomized Opcode Table with Aliasing + Fake Opcodes

Each build:
  - Each logical op gets 1-3 aliases (all same behavior, different numbers)
  - Fake opcodes are sprinkled in (VM no-ops, but break pattern matching)
  - All 256 slots shuffled randomly per build
"""
import random

# Logical opcodes: (name, n_aliases)
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

# Which aliases map to which canonical behavior
_ALIAS_MAP = {
    'ADD_ALT': 'ADD',  # ADD_ALT performs same as ADD
}

# Fake ops (VM no-ops)
_FAKE_OPS = {'JUNK', 'FAKE_STACK', 'FAKE_MATH'}


class Opcodes:
    """
    Per-build opcode table.
    - Canonical names -> shuffled integer values
    - Aliases resolve to same canonical logic in VM
    """
    def __init__(self, seed=None):
        rng = random.Random(seed)

        # Expand aliases into flat list of (canonical, alias_name)
        entries = []
        for name, n_aliases in _LOGICAL_OPCODES:
            canonical = _ALIAS_MAP.get(name, name)
            entries.append((canonical, name))
            for i in range(1, n_aliases):
                entries.append((canonical, f'{name}_V{i}'))

        # Shuffle and assign values 0..N
        rng.shuffle(entries)
        self._name2val  = {}   # alias_name -> int
        self._val2canon = {}   # int -> canonical_name
        for i, (canon, alias) in enumerate(entries):
            self._name2val[alias]  = i
            self._val2canon[i]     = canon

        # Quick lookup: canonical -> list of values
        self._canon2vals = {}
        for alias, val in self._name2val.items():
            canon = self._val2canon[val]
            self._canon2vals.setdefault(canon, []).append(val)

        self._rng = rng

    def get(self, name: str) -> int:
        """Return one value for canonical name (picks random alias each call for aliased ops)."""
        canon = _ALIAS_MAP.get(name, name)
        vals  = self._canon2vals.get(canon) or self._canon2vals.get(name)
        if vals is None:
            raise KeyError(f"Unknown opcode: {name}")
        return self._rng.choice(vals)

    def all_values(self, name: str) -> list:
        """All numeric values for a canonical op (including all aliases)."""
        canon = _ALIAS_MAP.get(name, name)
        return list(self._canon2vals.get(canon, []))

    def canonical(self, val: int) -> str:
        return self._val2canon.get(val, 'UNKNOWN')

    def is_fake(self, val: int) -> bool:
        return self.canonical(val) in _FAKE_OPS

    def all(self) -> dict:
        return dict(self._name2val)

    def __getattr__(self, name):
        if name.startswith('_'): raise AttributeError(name)
        return self.get(name)
