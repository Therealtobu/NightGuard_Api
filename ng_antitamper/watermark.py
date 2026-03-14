"""
NightGuard V4 - Hidden Watermark
Injects invisible watermarks into obfuscated output.
Allows identifying the source of leaked scripts.
"""

import hashlib
import hmac
import random
import re

_VERSION_SECRET = b"NightGuard_V4_2025"

# Lines ending with these patterns must NOT be followed by a `local` statement
# because it would be a Lua syntax error
# Lines after which injecting `local` would be a syntax error
_UNSAFE_KEYWORDS = ("return", "break", "continue")

# Line endings that indicate the expression/block continues on the next line
_UNSAFE_ENDINGS = (
    # Arithmetic / string / comparison operators
    "+", "-", "*", "/", "%", "^", "..", "=", "==", "~=",
    "<", ">", "<=", ">=", "and", "or", "not",
    # Opening brackets  (multi-line table / function call)
    "(", "{", "[",
    # Trailing comma (inside table or arg list)
    ",",
    # Block openers (next line is inside the block, not after it)
    "then", "do", "else", "repeat",
)


def _safe_to_inject_after(line: str) -> bool:
    """Return True if it is safe to inject a `local` statement after this line."""
    stripped = line.strip()
    if not stripped:
        return False
    # After control-flow terminators
    for kw in _UNSAFE_KEYWORDS:
        if stripped == kw or stripped.startswith(kw + " ") or stripped.startswith(kw + "("):
            return False
    # After lines ending with continuation operators or block openers
    for end in _UNSAFE_ENDINGS:
        if stripped == end or stripped.endswith(" " + end) or stripped.endswith("\t" + end):
            return False
        if stripped.endswith(end) and end in ("+", "-", "*", "/", "%", "^", "..",
                                               "(", "{", "[", ","):
            return False
    return True


def generate_watermark(user_id: str, script_source: str) -> bytes:
    """Generate unique 16-byte watermark for user + script."""
    data = (user_id + ":" + script_source[:64]).encode()
    return hmac.new(
        _VERSION_SECRET,
        data + b"watermark",
        hashlib.sha256
    ).digest()[:16]


def inject_watermark_numeric(vm_source: str, wm: bytes) -> str:
    """
    Inject watermark as arithmetic junk locals hidden in VM source.
    Each watermark byte stored as: local _NG_wmXXXXX = bit32.bxor(enc,mask)
    Skips injection after return/break/continue to avoid syntax errors.
    """
    rng      = random.Random(int.from_bytes(wm[:8], "big"))
    lines    = vm_source.split("\n")
    total    = len(lines)
    wm_bytes = list(wm)
    n        = len(wm_bytes)

    # Spread injection points evenly across file
    interval = max(1, total // (n + 1))
    inject_at = {(i + 1) * interval: i for i in range(n)}

    result    = []
    wm_placed = {}  # track which wm indices were placed

    for i, line in enumerate(lines):
        result.append(line)
        if i in inject_at:
            wm_index = inject_at[i]
            # Safety check: do NOT inject after return/break/continue
            if not _safe_to_inject_after(line):
                # Find next safe line to inject (scan forward up to interval lines)
                for offset in range(1, interval):
                    future_idx = i + offset
                    if future_idx < total and _safe_to_inject_after(lines[future_idx]):
                        # Mark for later — use deferred dict
                        inject_at[future_idx] = wm_index
                        break
                continue
            byte    = wm_bytes[wm_index]
            mask    = rng.randint(1, 127)
            encoded = byte ^ mask
            v       = "_NG_wm" + str(rng.randint(10000, 99999))
            result.append(
                f"local {v}=bit32.bxor({encoded},{mask})--NG_WM_{wm_index}"
            )
            result.append(f"{v}=nil")
            wm_placed[wm_index] = True

    return "\n".join(result)


def inject_watermark(vm_source: str,
                      script_source: str,
                      user_id: str = "anonymous") -> str:
    """Inject watermark into VM source."""
    wm = generate_watermark(user_id, script_source)
    return inject_watermark_numeric(vm_source, wm)


def extract_watermark(vm_source: str) -> list:
    """Extract watermark bytes from obfuscated source."""
    pattern = re.compile(
        r'local _NG_wm\d+=bit32\.bxor\((\d+),(\d+)\)--NG_WM_(\d+)'
    )
    results = {}
    for m in pattern.finditer(vm_source):
        enc   = int(m.group(1))
        mask  = int(m.group(2))
        index = int(m.group(3))
        results[index] = enc ^ mask
    return [results[i] for i in sorted(results.keys())]


def verify_watermark(vm_source: str,
                      user_id: str,
                      script_source: str) -> bool:
    """Verify watermark matches expected user."""
    extracted = bytes(extract_watermark(vm_source))
    expected  = generate_watermark(user_id, script_source)
    return extracted == expected
