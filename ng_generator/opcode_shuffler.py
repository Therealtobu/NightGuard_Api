"""
NightGuard V4 - Opcode Shuffler
Generates unique opcode mapping per script.
Every script gets a completely different opcode layout.
"""

import random
import hashlib
import hmac

_VERSION_SECRET = b"NightGuard_V4_2025"

# Canonical opcode names in order (matches Layer2 handler indices)
CANONICAL_OPCODES = [
    "LOADK",      # 0
    "LOADNIL",    # 1
    "LOADBOOL",   # 2
    "MOVE",       # 3
    "GETGLOBAL",  # 4
    "SETGLOBAL",  # 5
    "NEWTABLE",   # 6
    "GETTABLE",   # 7
    "SETTABLE",   # 8
    "SELF",       # 9
    "ADD",        # 10
    "SUB",        # 11
    "MUL",        # 12
    "DIV",        # 13
    "MOD",        # 14
    "POW",        # 15
    "UNM",        # 16
    "NOT",        # 17
    "LEN",        # 18
    "CONCAT",     # 19
    "JMP",        # 20
    "EQ",         # 21
    "LT",         # 22
    "LE",         # 23
    "TEST",       # 24
    "TESTSET",    # 25
    "CALL",       # 26
    "RETURN",     # 27
    "TAILCALL",   # 28
    "VARARG",     # 29
    "CLOSURE",    # 30
    "FORPREP",    # 31
    "FORLOOP",    # 32
    "TFORLOOP",   # 33
    "SETLIST",    # 34
    "JUNK",       # 35
    "JUNK2",      # 36
    "JUNK3",      # 37
]

NUM_OPCODES = len(CANONICAL_OPCODES)

def generate_opcode_map(script_source: str) -> dict:
    """
    Generate unique opcode mapping for a script.
    Returns: {canonical_index: shuffled_opcode_byte}
    e.g. {0: 76, 1: 143, ...}  (ADD is no longer always opcode 10)
    """
    h = hmac.new(
        _VERSION_SECRET,
        hashlib.sha256(script_source.encode()).digest() + b"opcodes_v4",
        hashlib.sha256
    ).digest()

    rng = random.Random(int.from_bytes(h[:8], "big"))

    # Generate shuffled values 0-255
    slots = list(range(256))
    rng.shuffle(slots)

    # First NUM_OPCODES slots are real opcodes
    mapping = {}
    for i in range(NUM_OPCODES):
        mapping[i] = slots[i]

    return mapping

def get_return_op(mapping: dict) -> int:
    """Get the shuffled opcode value for RETURN."""
    return mapping[27]  # RETURN is canonical index 27

def get_op(mapping: dict, name: str) -> int:
    """Get the shuffled opcode value by canonical name."""
    idx = CANONICAL_OPCODES.index(name)
    return mapping[idx]

def generate_lua_opmap(mapping: dict, var_name: str = "_NG_OP") -> str:
    """
    Generate Lua table literal for opcode map values in canonical order.
    Example: {12, 99, ...}
    """
    first = str(mapping[0])
    rest = ", ".join(str(mapping[i]) for i in range(1, NUM_OPCODES))
    if rest:
        return "{[0]=" + first + ", " + rest + "}"
    return "{[0]=" + first + "}"

def generate_reverse_map(mapping: dict) -> dict:
    """
    Generate reverse mapping: shuffled_opcode → canonical_index
    Used by VM to decode instructions.
    """
    return {v: k for k, v in mapping.items()}

def apply_mapping_to_bytecode(code: list, mapping: dict) -> list:
    """
    Remap opcodes in compiled bytecode from canonical to shuffled.
    code: list of u32 instructions
    Returns: remapped code
    """
    result = []
    for ins in code:
        op  = ins & 0xFF
        rest = ins >> 8

        # Only remap if within canonical range
        if op < NUM_OPCODES:
            new_op = mapping[op]
        else:
            new_op = op  # leave unknown opcodes as-is

        result.append((new_op & 0xFF) | (rest << 8))
    return result
