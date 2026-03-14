"""
NightGuard V4 - Junk Builder
Generates unique junk code blocks injected into VM interpreter.
Makes VM source harder to read and static analysis produce wrong results.
"""

import random
import hashlib
import hmac

_VERSION_SECRET = b"NightGuard_V4_2025"

_JUNK_TEMPLATES = [
    # Template 0: useless math
    """local {v1} = ({seed1} * {seed2} + {seed3}) % {mod1}
local {v2} = bit32.bxor({v1},0)~=0 and {v1} or {seed4}
{v1} = ({v1} + {v2}) % {mod2}""",

    # Template 1: dead conditional
    """local {v1} = math.floor({seed1} / {seed2})
if {v1} == {val1} then
    local {v2} = {v1} * {seed3}
    {v1} = {v2} % {mod1}
end""",

    # Template 2: string op junk
    """local {v1} = tostring({seed1})
local {v2} = #({v1} .. tostring({seed2}))
{v1} = nil""",

    # Template 3: table junk
    """local {v1} = {{}}
for _={seed1}%{mod1}+1, {seed2}%{mod2}+{seed3}%4+2 do
    {v1}[#({v1})+1] = 0
end
{v1} = nil""",

    # Template 4: pcall junk
    """local {v1} = pcall(function()
    local {v2} = {seed1} + {seed2}
    return {v2}
end)""",
]

def generate_junk_block(script_source: str,
                         block_index: int,
                         var_prefix: str = "_jnk") -> str:
    """Generate a unique junk code block for injection into VM source."""
    h = hmac.new(
        _VERSION_SECRET,
        hashlib.sha256(script_source.encode()).digest()
        + b"junk_block_"
        + block_index.to_bytes(4, "big"),
        hashlib.sha256
    ).digest()

    rng = random.Random(int.from_bytes(h[:8], "big"))

    template = _JUNK_TEMPLATES[rng.randint(0, len(_JUNK_TEMPLATES) - 1)]

    # Generate unique variable names and values
    suffix = "".join(rng.choices("abcdefghijklmnopqrstuvwxyz", k=6))
    v1 = f"{var_prefix}_{suffix}_1"
    v2 = f"{var_prefix}_{suffix}_2"

    vals = {
        "v1":    v1,
        "v2":    v2,
        "seed1": rng.randint(1, 65535),
        "seed2": rng.randint(1, 255),
        "seed3": rng.randint(1, 255),
        "seed4": rng.randint(0, 255),
        "mod1":  rng.choice([256, 512, 1024, 65536]),
        "mod2":  rng.choice([256, 512, 1024, 65536]),
        "val1":  rng.randint(0, 255),
    }

    try:
        return template.format(**vals)
    except KeyError:
        return f"local {v1} = {rng.randint(0,255)}"

def generate_vm_junk_blocks(script_source: str,
                              count: int = 8) -> list:
    """Generate multiple junk blocks for injection into VM."""
    return [
        generate_junk_block(script_source, i)
        for i in range(count)
    ]

def wrap_in_do_block(code: str) -> str:
    """Wrap junk code in a do...end block for scoping."""
    indented = "\n".join("    " + line for line in code.split("\n"))
    return f"do\n{indented}\nend"

def generate_fake_constant_table(script_source: str,
                                  size: int = 10,
                                  var_name: str = "_NG_FK") -> str:
    """
    Generate a fake constant table that looks like real VM data
    but is never actually used. Confuses dump tools.
    """
    h = hmac.new(
        _VERSION_SECRET,
        hashlib.sha256(script_source.encode()).digest() + b"fake_consts",
        hashlib.sha256
    ).digest()

    rng = random.Random(int.from_bytes(h[:8], "big"))
    values = [rng.randint(0, 65535) for _ in range(size)]
    entries = ",".join(str(v) for v in values)
    return f"local {var_name} = {{{entries}}}\n"
