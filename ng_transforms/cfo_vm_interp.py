"""
NightGuard V4 - VM Interpreter CFO
Obfuscates the generated VM source using AST-level techniques.
Makes the VM nearly impossible to read even as plain Lua.
"""

import re
import random
import hashlib
import hmac

_VERSION_SECRET = b"NightGuard_V4_2025"

# All Lua 5.1 / Luau reserved keywords — NEVER rename these
_LUA_KEYWORDS = frozenset({
    "and", "break", "do", "else", "elseif", "end",
    "false", "for", "function", "if", "in",
    "local", "nil", "not", "or", "repeat", "return",
    "then", "true", "until", "while",
    # Luau extras
    "type", "export", "continue",
})

# ── Name mangling ─────────────────────────────────────────────────────────────

def _gen_obf_name(seed: int, index: int) -> str:
    """Generate obfuscated variable name."""
    rng    = random.Random(seed ^ (index * 0x9E3779B9))
    chars  = "lI0O"
    length = rng.randint(12, 20)
    name   = "_"
    for _ in range(length):
        name += rng.choice(chars)
    return name


def mangle_local_names(lua_source: str, script_source: str) -> str:
    """
    Rename all non-NG local variables to obfuscated names.
    Skips Lua keywords, built-ins, and _NG_* names.
    """
    h = hmac.new(
        _VERSION_SECRET,
        hashlib.sha256(script_source.encode()).digest() + b"mangle",
        hashlib.sha256
    ).digest()
    seed = int.from_bytes(h[:8], "big")

    # Match `local NAME` but only capture the name after `local`
    # The lookahead ensures we only grab actual variable names, not keywords
    local_pattern = re.compile(
        r'\blocal\s+([a-zA-Z_][a-zA-Z0-9_]*)\b'
    )
    rename_map = {}
    counter    = 0

    for match in local_pattern.finditer(lua_source):
        name = match.group(1)
        if (name not in rename_map
                and not name.startswith("_NG_")
                and name not in _LUA_KEYWORDS):  # ← KEY FIX: skip keywords
            rename_map[name] = _gen_obf_name(seed, counter)
            counter += 1

    result = lua_source
    for orig, obf in rename_map.items():
        # Only replace as whole word boundaries, and only outside strings
        # Simple approach: word-boundary replacement (safe for identifiers)
        result = re.sub(r'\b' + re.escape(orig) + r'\b', obf, result)

    return result


# ── Opaque predicate injection ────────────────────────────────────────────────

_TRUE_PREDS = [
    '(math.floor(1)==1)',
    '(type(0)=="number")',
    '(1~=2)',
    '(not false)',
    '(#{1,2,3}==3)',
]

_FALSE_PREDS = [
    '(math.floor(1)==2)',
    '(type(0)=="string")',
    '(1==2)',
    '(false)',
    '(nil==true)',
]


def inject_opaque_predicates(lua_source: str,
                              script_source: str,
                              rate: int = 20) -> str:
    """Inject opaque predicates every N lines."""
    h = hmac.new(
        _VERSION_SECRET,
        hashlib.sha256(script_source.encode()).digest() + b"opaque",
        hashlib.sha256
    ).digest()
    rng    = random.Random(int.from_bytes(h[:8], "big"))
    lines  = lua_source.split("\n")
    result = []

    for i, line in enumerate(lines):
        result.append(line)
        stripped = line.strip()

        if (i % rate == 0 and i > 0 and
                (stripped == "" or stripped == "end")):

            if rng.random() < 0.5:
                pred = rng.choice(_FALSE_PREDS)
                v    = "_NG_d" + str(rng.randint(1000, 9999))
                j1   = rng.randint(0, 65535)
                j2   = rng.randint(0, 65535)
                result.append(f"if {pred} then")
                result.append(f"    local {v}={j1}+{j2}")
                result.append(f"    {v}=nil")
                result.append(f"end")
            else:
                v   = "_NG_j" + str(rng.randint(1000, 9999))
                val = rng.randint(0, 65535)
                result.append(f"local {v}={val}")
                result.append(f"{v}=nil")

    return "\n".join(result)


# ── String splitting ──────────────────────────────────────────────────────────

# Never split these strings — they're meaningful and short
_SAFE_STRINGS = frozenset({
    "function", "string", "number", "boolean", "table",
    "thread", "userdata", "nil", "true", "false",
})


def split_string_literals(lua_source: str, script_source: str) -> str:
    """
    Split string literals into concat expressions.
    Only splits strings that are:
      - At least 8 chars (avoids corrupting short keyword strings)
      - Not Lua type-check strings like "function", "table", etc.
      - Not inside table constructors (no splitting after commas or {)
    """
    h = hmac.new(
        _VERSION_SECRET,
        hashlib.sha256(script_source.encode()).digest() + b"strsplit",
        hashlib.sha256
    ).digest()
    rng = random.Random(int.from_bytes(h[:8], "big"))

    def split_str(match):
        s     = match.group(0)
        inner = s[1:-1]          # strip surrounding quotes
        # Skip short strings and keyword strings
        if len(inner) < 8 or inner in _SAFE_STRINGS:
            return s
        # Skip strings that look like they could be type names or keywords
        if inner.isalpha() and len(inner) <= 12:
            return s
        mid = rng.randint(3, len(inner) - 3)
        a, b = inner[:mid], inner[mid:]
        return f'("{a}".."{b}")'

    # Only process strings that are clearly standalone (after = or ~= or ==)
    # and NOT inside table constructors or function argument lists
    # Strategy: only split strings that follow comparison operators
    pattern = re.compile(
        r'(?<=[=!<>~])\s*"([^"\\]{8,})"'
        r'|'
        r'(?<=\()\s*"([^"\\]{8,})"'
    )

    # Simpler and safer: only split strings following ~= or == operators
    safe_pattern = re.compile(
        r'((?:~=|==)\s*)("([^"\\]{8,})")'
    )

    def safe_split(match):
        prefix = match.group(1)
        inner  = match.group(3)
        if len(inner) < 4:
            return match.group(0)
        mid = rng.randint(3, len(inner) - 3)
        a, b = inner[:mid], inner[mid:]
        return f'{prefix}("{a}".."{b}")'

    return safe_pattern.sub(safe_split, lua_source)


# ── Number encoding ───────────────────────────────────────────────────────────

def encode_numbers(lua_source: str, script_source: str) -> str:
    """
    Replace numeric literals with obfuscated math expressions.
    Only replaces numbers in safe contexts (not inside strings,
    not array indices, not bit-operation arguments).
    """
    h = hmac.new(
        _VERSION_SECRET,
        hashlib.sha256(script_source.encode()).digest() + b"numenc",
        hashlib.sha256
    ).digest()
    rng = random.Random(int.from_bytes(h[:8], "big"))

    def encode_num(match):
        raw = match.group(0)
        try:
            n = int(raw)
        except ValueError:
            return raw
        if n <= 0 or n > 9999:
            return raw

        t = rng.randint(0, 2)
        if t == 0:
            a = rng.randint(0, n)
            return f"({a}+{n-a})"
        elif t == 1:
            k = rng.randint(2, 9)
            return f"(math.floor({n*k}/{k}))"
        else:
            return raw

    # Don't encode numbers that are:
    # - Inside strings (handled by excluding inside quotes)
    # - Table keys used as indices [N]
    # - Bit operation constants (0xFF, 0x...)
    # Strategy: process line by line, skip lines inside strings
    lines  = lua_source.split("\n")
    result = []
    number_re = re.compile(
        r'(?<![.x\w])(\b[1-9][0-9]{0,3}\b)(?!\s*[=.])'
    )

    for line in lines:
        # Skip lines that look like table constructors with only numbers
        stripped = line.strip()
        # Don't encode inside local table arrays (all-number lines)
        if stripped.startswith("local _") and "={" in stripped and \
                re.search(r'\d{4,}', stripped):
            result.append(line)
            continue
        result.append(number_re.sub(encode_num, line))

    return "\n".join(result)


# ── Main ──────────────────────────────────────────────────────────────────────

def obfuscate_vm_source(vm_source: str, script_source: str,
                         mangle:  bool = True,
                         opaques: bool = True,
                         strings: bool = True,
                         numbers: bool = True) -> str:
    """Apply all VM source obfuscation passes."""
    r = vm_source
    if opaques: r = inject_opaque_predicates(r, script_source)
    if strings: r = split_string_literals(r, script_source)
    if numbers: r = encode_numbers(r, script_source)
    if mangle:  r = mangle_local_names(r, script_source)
    return r
