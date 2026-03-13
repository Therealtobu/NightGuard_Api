"""
NightGuard V4 - Per-Instruction Key Mutation
Each instruction is encrypted with a different key derived from execution history.
Makes static decryption impossible without running every previous instruction.
"""

import struct
from typing import List

def _mutate_key(key: int, instruction: int, pc: int) -> int:
    """
    Derive next key from current key + instruction + pc.
    Lua 5.1 compatible: all ops use 32-bit arithmetic.
    """
    k = key
    k = (k * 1664525 + 1013904223) & 0xFFFFFFFF
    k = k ^ (instruction & 0xFF)
    k = k ^ ((pc * 0x9E3779B9) & 0xFFFFFFFF)
    if k == 0:
        k = 1
    return k

def encrypt_instructions(code: List[int], seed: int) -> List[int]:
    """
    Encrypt each instruction with a mutating key.
    instruction[i] = xor(real_instruction[i], key[i])
    key[i] = mutate(key[i-1], real_instruction[i-1], i-1)
    """
    out  = []
    key  = seed
    for i, ins in enumerate(code):
        enc = ins ^ key
        out.append(enc & 0xFFFFFFFF)
        key = _mutate_key(key, ins, i)
    return out

def decrypt_instructions(code: List[int], seed: int) -> List[int]:
    """Decrypt per-instruction encrypted code."""
    out = []
    key = seed
    for i, enc in enumerate(code):
        ins = enc ^ key
        ins = ins & 0xFFFFFFFF
        out.append(ins)
        key = _mutate_key(key, ins, i)
    return out

def generate_lua_decoder(seed: int, var_prefix: str = "_NG_PI") -> str:
    """
    Generate Lua 5.1 compatible per-instruction decoder.
    Injected into Layer2 VM - decodes each instruction at fetch time.
    """
    return f"""-- Per-instruction key mutation decoder
local {var_prefix}_key = {seed}
local function {var_prefix}_decode(enc, pc)
    local ins = enc
    if bit then
        ins = bit.bxor(enc, {var_prefix}_key)
    elseif bit32 then
        ins = bit32.bxor(enc, {var_prefix}_key)
    else
        local a, b = enc, {var_prefix}_key
        local r, m = 0, 1
        while a > 0 or b > 0 do
            if a % 2 ~= b % 2 then r = r + m end
            a, b, m = math.floor(a/2), math.floor(b/2), m*2
        end
        ins = r
    end
    -- Mutate key for next instruction
    local k = {var_prefix}_key
    k = (k * 1664525 + 1013904223) % 0x100000000
    local xv = ins % 256
    if bit then
        k = bit.bxor(k, xv)
        k = bit.bxor(k, (pc * 0x9E3779B9) % 0x100000000)
    else
        -- fallback xor
        local function _xr(a2, b2)
            local r2, m2 = 0, 1
            while a2 > 0 or b2 > 0 do
                if a2 % 2 ~= b2 % 2 then r2 = r2 + m2 end
                a2, b2, m2 = math.floor(a2/2), math.floor(b2/2), m2*2
            end
            return r2
        end
        k = _xr(k, xv)
        k = _xr(k, (pc * 2654435769) % 0x100000000)
    end
    if k == 0 then k = 1 end
    {var_prefix}_key = k
    return ins
end
"""
