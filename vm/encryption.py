import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
"""
NightGuard V2 — Bytecode Encryption

Three-layer encryption applied before the bytes are embedded in Lua output:

  Layer 1: Rolling-XOR with seed mixing
      byte[i] = byte[i] XOR key
      key = (key * 13 + byte[i]) % 256

  Layer 2: Byte permutation using a Fisher-Yates shuffle driven by a second seed
      Permutes blocks of the ciphertext (shuffles 256-byte segments).

  Layer 3: XOR with a 32-byte random key block (repeating)

Decryption is performed inside the VM runtime in Lua before any execution.
"""

import random
import struct


# ── Layer 1: Rolling-XOR ──────────────────────────────────────────────────────

def _rolling_xor_enc(data: bytes, seed: int) -> bytes:
    out = bytearray(len(data))
    key = seed & 0xFF
    for i, b in enumerate(data):
        enc     = (b ^ key) & 0xFF
        key     = (key * 13 + enc) & 0xFF
        out[i]  = enc
    return bytes(out)


def _rolling_xor_dec(data: bytes, seed: int) -> bytes:
    out = bytearray(len(data))
    key = seed & 0xFF
    for i, b in enumerate(data):
        plain   = (b ^ key) & 0xFF
        key     = (key * 13 + b) & 0xFF
        out[i]  = plain
    return bytes(out)


# ── Layer 2: Block permutation ────────────────────────────────────────────────

BLOCK_SIZE = 64   # permute within 64-byte blocks

def _permute(data: bytes, perm_seed: int, reverse: bool = False) -> bytes:
    data = bytearray(data)
    n    = len(data)
    rng  = random.Random(perm_seed)

    # Build per-block permutations
    out  = bytearray(n)
    for block_start in range(0, n, BLOCK_SIZE):
        block_end = min(block_start + BLOCK_SIZE, n)
        size      = block_end - block_start
        indices   = list(range(size))
        rng_block = random.Random(perm_seed ^ (block_start * 0x1F))
        rng_block.shuffle(indices)

        for i, j in enumerate(indices):
            if reverse:
                out[block_start + j] = data[block_start + i]
            else:
                out[block_start + i] = data[block_start + j]

    return bytes(out)


# ── Layer 3: Key-block XOR ────────────────────────────────────────────────────

KEY_BLOCK_LEN = 32

def _key_block_xor(data: bytes, key: bytes) -> bytes:
    klen = len(key)
    return bytes(b ^ key[i % klen] for i, b in enumerate(data))


# ── Public API ────────────────────────────────────────────────────────────────

class Encryptor:
    def __init__(self, rng: random.Random):
        self.seed1      = rng.randint(1, 254)              # rolling-XOR seed
        self.perm_seed  = rng.randint(0, 0xFFFFFF)         # permutation seed
        self.key_block  = bytes(rng.randint(1, 254) for _ in range(KEY_BLOCK_LEN))

    def encrypt(self, data: bytes) -> bytes:
        d = _rolling_xor_enc(data,      self.seed1)
        d = _permute(d,                 self.perm_seed, reverse=False)
        d = _key_block_xor(d,           self.key_block)
        return d

    def decrypt_lua_code(self) -> str:
        """
        Return a Lua function body string that decrypts the bytecode.
        Inlined into the VM runtime so the key material lives there.
        """
        key_nums    = ",".join(str(b) for b in self.key_block)
        seed1       = self.seed1
        perm_seed   = self.perm_seed
        block_size  = BLOCK_SIZE

        return f"""
    local function _NG_decrypt(data)
        local key1 = {seed1}
        local perm_seed = {perm_seed}
        local block_size = {block_size}
        local key_block = {{{key_nums}}}
        local klen = #key_block
        local n = #data

        -- Layer 3 reverse: key-block XOR
        local tmp1 = {{}}
        for i = 1, n do
            tmp1[i] = _bxor(data[i], key_block[((i-1) % klen) + 1])
        end

        -- Layer 2 reverse: block permutation
        local tmp2 = {{}}
        for i = 1, n do tmp2[i] = tmp1[i] end
        for block_start = 0, n - 1, block_size do
            local block_end = math.min(block_start + block_size, n)
            local size = block_end - block_start
            -- Rebuild the same shuffle
            local indices = {{}}
            for i = 0, size - 1 do indices[i+1] = i end
            -- Deterministic shuffle using perm_seed ^ (block_start * 0x1F)
            local rs = _bxor(perm_seed, block_start * 31)
            for i = size, 2, -1 do
                rs = (rs * 1664525 + 1013904223) % (2^32)
                local j = (rs % i) + 1
                indices[i], indices[j] = indices[j], indices[i]
            end
            -- Reverse the permutation: out[indices[i]] = tmp1[i]
            for i = 1, size do
                tmp2[block_start + indices[i] + 1] = tmp1[block_start + i]
            end
        end

        -- Layer 1 reverse: rolling-XOR
        local out = {{}}
        local key = key1
        for i = 1, n do
            local b = tmp2[i]
            out[i] = _bxor(b, key)
            key = (key * 13 + b) % 256
        end

        return out
    end
"""


def encode_bytecode_lua(enc_bytes: bytes) -> str:
    """Embed encrypted bytes as a compact Lua table literal."""
    nums = ",".join(str(b) for b in enc_bytes)
    return f"local _NG_bc = {{{nums}}}"
