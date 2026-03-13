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
    Each watermark byte stored as: local _NG_wmXXXXX = (enc) ~ (mask)
    """
    rng      = random.Random(int.from_bytes(wm[:8], "big"))
    lines    = vm_source.split("\n")
    result   = []
    wm_index = 0
    wm_bytes = list(wm)

    for i, line in enumerate(lines):
        result.append(line)
        if (i % 47 == 0 and
                wm_index < len(wm_bytes) and
                line.strip() == ""):
            byte    = wm_bytes[wm_index]
            mask    = rng.randint(1, 127)
            encoded = byte ^ mask
            v       = "_NG_wm" + str(rng.randint(10000, 99999))
            result.append(
                f"local {v}=({encoded})~({mask})--NG_WM_{wm_index}"
            )
            result.append(f"{v}=nil")
            wm_index += 1

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
        r'local _NG_wm\d+=\((\d+)\)~\((\d+)\)--NG_WM_(\d+)'
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
