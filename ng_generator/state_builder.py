"""
NightGuard V4 - State Machine Builder
Generates unique state machine transitions for VM CFO.
Each script gets different state IDs and transition logic.
"""

import random
import hashlib
import hmac

_VERSION_SECRET = b"NightGuard_V4_2025"

# Canonical state names
STATES = [
    "FETCH",
    "DECODE",
    "DISPATCH",
    "JUNK1",
    "JUNK2",
    "ADVANCE",
]

NUM_STATES = len(STATES)

def generate_state_ids(script_source: str) -> dict:
    """
    Generate unique state ID values per script.
    Returns: {state_name: unique_id}
    """
    h = hmac.new(
        _VERSION_SECRET,
        hashlib.sha256(script_source.encode()).digest() + b"states_v4",
        hashlib.sha256
    ).digest()

    rng = random.Random(int.from_bytes(h[:8], "big"))

    # Generate unique non-zero state IDs
    ids = set()
    while len(ids) < NUM_STATES:
        ids.add(rng.randint(1000, 99999))

    state_ids = {}
    for i, name in enumerate(STATES):
        state_ids[name] = list(ids)[i]

    return state_ids

def generate_flow_seed(script_source: str) -> int:
    """Generate unique initial flow seed for state machine."""
    h = hmac.new(
        _VERSION_SECRET,
        hashlib.sha256(script_source.encode()).digest() + b"flow_seed",
        hashlib.sha256
    ).digest()
    return int.from_bytes(h[:4], "big") & 0x7FFFFFFF

def generate_junk_expressions(script_source: str, count: int = 4) -> list:
    """
    Generate unique junk expressions per script.
    These go into JUNK states and do nothing but look confusing.
    """
    h = hmac.new(
        _VERSION_SECRET,
        hashlib.sha256(script_source.encode()).digest() + b"junk_exprs",
        hashlib.sha256
    ).digest()

    rng = random.Random(int.from_bytes(h[:8], "big"))

    exprs = []
    ops = ["+", "-", "*", "%"]
    vars_ = ["pc", "_a", "_b", "_c", "(R[0] or 0)"]

    for _ in range(count):
        v1  = rng.choice(vars_)
        v2  = rng.choice(vars_)
        op  = rng.choice(ops)
        mod = rng.choice([256, 512, 1024, 65536])
        c   = rng.randint(1, 255)
        exprs.append(f"(({v1} {op} {v2} + {c}) % {mod})")

    return exprs

def generate_lua_states(state_ids: dict, flow_seed: int,
                         junk_exprs: list,
                         var_prefix: str = "_NG_ST") -> str:
    """
    Generate Lua code for state machine constants.
    Unique per script - state IDs and junk expressions differ.
    """
    lines = []

    # State ID constants
    lines.append("-- State machine IDs (unique per script)")
    for name, sid in state_ids.items():
        lines.append(f"local {var_prefix}_{name} = {sid}")

    lines.append(f"local {var_prefix}_FLOW = {flow_seed}")
    lines.append(f"local {var_prefix}_COUNT = {NUM_STATES}")
    lines.append("")

    # Junk accumulator init
    lines.append("-- Junk accumulators")
    lines.append(f"local {var_prefix}_junk1 = 0")
    lines.append(f"local {var_prefix}_junk2 = 0")
    lines.append("")

    # State transition helper
    lines.append("-- State transition function")
    lines.append(f"local function {var_prefix}_next(cur_state, op, pc)")
    lines.append(f"    {var_prefix}_FLOW = ({var_prefix}_FLOW * 1103515245 + 12345) % 0x80000000")
    lines.append(f"    if cur_state == {var_prefix}_FETCH then")
    lines.append(f"        return ({var_prefix}_FLOW % 3 == 0)")
    lines.append(f"               and {var_prefix}_JUNK1")
    lines.append(f"               or  {var_prefix}_DECODE")
    lines.append(f"    elseif cur_state == {var_prefix}_JUNK1 then")
    lines.append(f"        return {var_prefix}_JUNK2")
    lines.append(f"    elseif cur_state == {var_prefix}_JUNK2 then")
    lines.append(f"        return {var_prefix}_DECODE")
    lines.append(f"    elseif cur_state == {var_prefix}_DECODE then")
    lines.append(f"        return {var_prefix}_DISPATCH")
    lines.append(f"    elseif cur_state == {var_prefix}_DISPATCH then")
    lines.append(f"        return {var_prefix}_ADVANCE")
    lines.append(f"    else")
    lines.append(f"        return {var_prefix}_FETCH")
    lines.append(f"    end")
    lines.append(f"end")
    lines.append("")

    # Junk computation functions (unique per script)
    lines.append("-- Junk computations (unique per script)")
    lines.append(f"local function {var_prefix}_do_junk1(pc, _a, _b, _c, R)")
    if junk_exprs:
        lines.append(f"    {var_prefix}_junk1 = {junk_exprs[0]}")
    lines.append(f"end")
    lines.append("")
    lines.append(f"local function {var_prefix}_do_junk2(pc, _a, _b, _c, R)")
    if len(junk_exprs) > 1:
        lines.append(f"    {var_prefix}_junk2 = ({var_prefix}_junk1 + {junk_exprs[1]}) % 65536")
    lines.append(f"end")

    return "\n".join(lines)
