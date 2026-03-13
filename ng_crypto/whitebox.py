"""
NightGuard V4 - Whitebox XOR Tables
Key is "baked into" lookup tables - never appears as plain bytes.
"""

import hashlib
import hmac
import struct
import random

_VERSION_SECRET = b"NightGuard_V4_2025"

def generate_whitebox_table(key: bytes) -> list:
    """
    Generate 256x256 whitebox substitution table.
    table[i][j] = xor(j, key_stream[i])
    Key is embedded, never visible.
    Returns flat list of 65536 bytes.
    """
    # Expand key to 256 bytes using PRNG seeded with key
    rng = random.Random(int.from_bytes(
        hmac.new(key, b"whitebox_expand", hashlib.sha256).digest()[:8],
        "big"
    ))
    
    key_stream = [rng.randint(0, 255) for _ in range(256)]
    
    table = []
    for i in range(256):
        row = [(j ^ key_stream[i]) for j in range(256)]
        table.extend(row)
    
    return table

def lua_whitebox_table(key: bytes, var_name: str = "_NG_WB") -> str:
    """
    Generate Lua code for whitebox table.
    Returns Lua 5.1 compatible code.
    """
    table = generate_whitebox_table(key)
    
    # Split into rows of 64 for readability
    rows = []
    for i in range(0, len(table), 64):
        row = table[i:i+64]
        rows.append(",".join(str(b) for b in row))
    
    lua = f"local {var_name} = {{{','.join(str(b) for b in table)}}}\n"
    lua += f"""local function _NG_wb_decrypt(data, offset)
    local out = {{}}
    for i = 1, #data do
        local ki = ((i - 1 + (offset or 0)) % 256) + 1
        out[i] = {var_name}[(ki - 1) * 256 + data[i] + 1]
    end
    return out
end
"""
    return lua

def apply_whitebox(data: bytes, key: bytes, offset: int = 0) -> list:
    """Apply whitebox encryption to data."""
    table = generate_whitebox_table(key)
    out = []
    for i, b in enumerate(data):
        ki = (i + offset) % 256
        out.append(table[ki * 256 + b])
    return out

def verify_whitebox(encrypted: list, key: bytes, offset: int = 0) -> bytes:
    """Verify whitebox by decrypting - should return original data."""
    # Whitebox XOR is self-inverse
    return bytes(apply_whitebox(encrypted, key, offset))
