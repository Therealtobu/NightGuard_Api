"""
NightGuard V4 - Key Schedule
Per-script unique key derivation
"""

import hashlib
import hmac
import struct
import random

# Version secret - change this per deployment
_VERSION_SECRET = b"NightGuard_V4_2025"

def hash_script(source: str) -> bytes:
    """SHA-256 hash of script source."""
    return hashlib.sha256(source.encode("utf-8")).digest()

def derive_key(script_source: str, length: int = 32) -> bytes:
    """
    Derive unique encryption key from script source.
    Each script gets a completely different key.
    """
    script_hash = hash_script(script_source)
    # HKDF-like expand
    key = hmac.new(_VERSION_SECRET, script_hash + b"key", hashlib.sha256).digest()
    # Stretch to desired length
    out = b""
    counter = 0
    while len(out) < length:
        out += hmac.new(key, struct.pack(">I", counter) + b"expand", hashlib.sha256).digest()
        counter += 1
    return out[:length]

def derive_seed(script_source: str) -> int:
    """Derive unique seed (0-255) for VM from script source."""
    h = hmac.new(_VERSION_SECRET, hash_script(script_source) + b"seed", hashlib.sha256).digest()
    return h[0]

def derive_child_key(parent_key: bytes, proto_index: int) -> bytes:
    """
    Derive child proto key from parent key.
    Child protos can't be decrypted without parent executing first.
    """
    data = parent_key + struct.pack(">I", proto_index) + b"child"
    return hmac.new(parent_key, data, hashlib.sha256).digest()

def derive_opcode_map(script_source: str) -> dict:
    """
    Generate unique opcode mapping per script.
    Returns dict: real_opcode -> shuffled_opcode
    """
    h = hmac.new(_VERSION_SECRET, hash_script(script_source) + b"opcodes", hashlib.sha256).digest()
    
    # Seed RNG with script hash
    rng = random.Random(int.from_bytes(h[:8], "big"))
    
    slots = list(range(256))
    rng.shuffle(slots)
    
    return {i: slots[i] for i in range(256)}

def derive_state_seed(script_source: str) -> int:
    """Derive initial state for VM CFO state machine."""
    h = hmac.new(_VERSION_SECRET, hash_script(script_source) + b"state", hashlib.sha256).digest()
    return struct.unpack(">I", h[:4])[0]

def derive_magic_token(script_source: str) -> int:
    """Derive Layer1→Layer2 handshake magic token."""
    h = hmac.new(_VERSION_SECRET, hash_script(script_source) + b"magic", hashlib.sha256).digest()
    return struct.unpack(">I", h[:4])[0] & 0xFFFFFFFF

def derive_runtime_key(script_source: str) -> int:
    """Derive runtime XOR key for magic token obfuscation."""
    h = hmac.new(_VERSION_SECRET, hash_script(script_source) + b"rtkey", hashlib.sha256).digest()
    return struct.unpack(">I", h[4:8])[0] & 0xFFFFFFFF
