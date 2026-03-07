"""NightGuard V2 - Bytecode Serializer + Dual-Layer Encryptor"""
import struct, random

def _p8(v):  return struct.pack('B', v & 0xFF)
def _p16(v): return struct.pack('<H', v & 0xFFFF)
def _p32(v): return struct.pack('<I', v & 0xFFFFFFFF)
def _pf64(v):return struct.pack('<d', float(v))
def _pstr(s):
    e = s.encode('utf-8'); return _p32(len(e)) + e
def _pblk(b):
    return _p32(len(b)) + b

def serialize_proto(proto) -> bytes:
    out = bytearray()
    out += _p8(proto.nparams)
    out += _p8(1 if proto.is_vararg else 0)
    out += _p32(len(proto.code))
    for instr in proto.code:
        out += _p32(instr)   # packed u32
    out += _p32(len(proto.consts))
    for c in proto.consts:
        if c is None:
            out += _p8(0)
        elif isinstance(c, bool):
            out += _p8(1); out += _p8(1 if c else 0)
        elif isinstance(c, (int, float)):
            out += _p8(2); out += _pf64(c)
        elif isinstance(c, str):
            out += _p8(3); out += _pstr(c)
        elif isinstance(c, tuple) and len(c) == 4 and c[0] == '__enc_str':
            _, enc_bytes, seed, step = c
            out += _p8(4)
            out += _p8(seed & 0xFF)
            out += _p8(step & 0xFF)
            out += _p32(len(enc_bytes))
            for b in enc_bytes: out += _p8(b)
        else:
            out += _p8(3); out += _pstr(str(c))
    out += _p32(len(proto.protos))
    for child in proto.protos:
        cb = serialize_proto(child); out += _pblk(cb)
    return bytes(out)

def encrypt_bytecode(raw: bytes, rng: random.Random):
    """
    Double-layer encryption:
    Layer 1: rolling-XOR cipher  byte[i] ^= key; key = (key*13 + byte[i]) % 256
    Layer 2: XOR with 32-byte random key block
    Returns: (encrypted_bytes, key32, seed)
    """
    seed = rng.randint(2, 253)
    key32= bytes(rng.randint(2, 253) for _ in range(32))
    # Layer 1
    layer1 = bytearray(raw)
    key = seed
    for i in range(len(layer1)):
        orig = layer1[i]
        layer1[i] = orig ^ key
        key = (key * 13 + layer1[i]) % 256
        if key == 0: key = 1
    # Layer 2 - byte permutation via key32
    klen = len(key32)
    layer2 = bytes(b ^ key32[i % klen] for i, b in enumerate(layer1))
    return layer2, key32, seed

def encode_for_lua(enc: bytes, key32: bytes, seed: int) -> dict:
    nums  = ','.join(str(b) for b in enc)
    key_s = ','.join(str(b) for b in key32)
    return {
        'bc_table':  f'local _N_bc={{{nums}}}',
        'key_table': f'{{{key_s}}}',
        'seed':      seed,
  }
