"""
Night - Bytecode Serializer + Encryptor
Converts a Proto tree into an encrypted binary blob, then into a
Lua-embeddable string.
"""
import struct
import random
import base64


# ── Binary Serialization ──────────────────────────────────────────────────────

def _pack_u8(v):  return struct.pack('B', v & 0xFF)
def _pack_u16(v): return struct.pack('<H', v & 0xFFFF)
def _pack_u32(v): return struct.pack('<I', v & 0xFFFFFFFF)
def _pack_f64(v): return struct.pack('<d', float(v))

def _pack_str(s: str) -> bytes:
    enc = s.encode('utf-8')
    return _pack_u32(len(enc)) + enc

def _pack_bytes(b: bytes) -> bytes:
    return _pack_u32(len(b)) + b


def serialize_proto(proto) -> bytes:
    """Recursively serialise a Proto object to raw bytes."""
    out = bytearray()

    # Header: nparams, is_vararg
    out += _pack_u8(proto.nparams)
    out += _pack_u8(1 if proto.is_vararg else 0)

    # Instructions: u32 count then (u8 opcode, u16 A, u16 B) * n
    out += _pack_u32(len(proto.code))
    for op, a, b in proto.code:
        out += _pack_u8(op)
        out += _pack_u16(a)
        out += _pack_u16(b)

    # Constants
    out += _pack_u32(len(proto.consts))
    for c in proto.consts:
        if c is None:
            out += _pack_u8(0)                     # TYPE_NIL
        elif isinstance(c, bool):
            out += _pack_u8(1)                     # TYPE_BOOL
            out += _pack_u8(1 if c else 0)
        elif isinstance(c, (int, float)):
            out += _pack_u8(2)                     # TYPE_NUMBER
            out += _pack_f64(c)
        elif isinstance(c, str):
            out += _pack_u8(3)                     # TYPE_STRING
            out += _pack_str(c)
        elif isinstance(c, tuple) and c[0] == '__enc_str':
            # Encrypted string constant
            _, enc_bytes, xor_key = c
            out += _pack_u8(4)                     # TYPE_ENC_STR
            out += _pack_u8(xor_key)
            out += _pack_u32(len(enc_bytes))
            for b in enc_bytes:
                out += _pack_u8(b)
        else:
            # Fallback: store as string repr
            out += _pack_u8(3)
            out += _pack_str(str(c))

    # Nested protos
    out += _pack_u32(len(proto.protos))
    for child in proto.protos:
        child_bytes = serialize_proto(child)
        out += _pack_bytes(child_bytes)

    return bytes(out)


# ── Encryption ────────────────────────────────────────────────────────────────

def _xor_bytes(data: bytes, key: bytes) -> bytes:
    klen = len(key)
    return bytes(b ^ key[i % klen] for i, b in enumerate(data))


def _rolling_xor(data: bytes, seed: int) -> bytes:
    """Simple rolling-XOR cipher with seed."""
    out = bytearray(len(data))
    prev = seed & 0xFF
    for i, b in enumerate(data):
        enc = b ^ prev ^ ((i * 0x1F) & 0xFF)
        out[i] = enc
        prev = enc
    return bytes(out)


def encrypt_bytecode(raw: bytes, rng: random.Random) -> tuple:
    """
    Returns (encrypted_bytes, key_bytes, seed)
    Uses: rolling-XOR with seed, then XOR with a random key block.
    """
    seed = rng.randint(1, 254)
    key  = bytes(rng.randint(1, 254) for _ in range(32))
    step1 = _rolling_xor(raw, seed)
    step2 = _xor_bytes(step1, key)
    return step2, key, seed


# ── Lua-embeddable encoding ───────────────────────────────────────────────────

def bytes_to_lua_string(data: bytes) -> str:
    """
    Encode bytes as a Lua long string with escape sequences.
    Uses base-85-like decimal encoding to avoid null bytes and
    ensure Lua 5.1 compatibility (no \\x escapes in some builds).
    We use \\ddd decimal escape for all bytes.
    """
    # Use long string with decimal escapes
    parts = []
    for i, b in enumerate(data):
        parts.append(f'\\{b}')
        if i % 80 == 79:
            parts.append('\\\n')     # line continuation for readability
    return '"' + ''.join(parts) + '"'


def bytes_to_lua_table(data: bytes, var_name: str = 'bc') -> str:
    """Encode bytes as a Lua table of integers (more obfuscated, slightly bigger)."""
    nums = ','.join(str(b) for b in data)
    return f'local {var_name}={{{nums}}}'


def key_to_lua(key: bytes) -> str:
    nums = ','.join(str(b) for b in key)
    return f'{{{nums}}}'


def encode_for_lua(encrypted: bytes, key: bytes, seed: int) -> dict:
    """Return a dict with all fields needed to embed into the Lua template."""
    return {
        'bc_table':  bytes_to_lua_table(encrypted, '_N_bc'),
        'key_table': key_to_lua(key),
        'seed':      seed,
        'bc_len':    len(encrypted),
    }
