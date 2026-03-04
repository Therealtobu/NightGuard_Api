"""
Night - Main Obfuscation Pipeline
Orchestrates: parse → transform → compile → serialize → encrypt → wrap.
"""

import random
import time

from .parser      import parse
from .transformer import Transformer
from .compiler    import Compiler
from .opcodes     import Opcodes
from .serializer  import serialize_proto, encrypt_bytecode, encode_for_lua
from .vm_gen      import generate_vm

ASCII_BANNER = r"""
--[[
 _   _ _       _     _
| \ | (_) __ _| |__ | |_
|  \| | |/ _` | '_ \| __|
| |\  | | (_| | | | | |_
|_| \_|_|\__, |_| |_|\__|  _
 / ___|_ |___/__ _ _ __ __| |
| |  _| | | |/ _` | '__/ _` |
| |_| | |_| | (_| | | | (_| |
 \____|\__,_|\__,_|_|  \__,_|

  Night Guard - VM Bytecode Obfuscator
  Protected by Night  |  Lua 5.1 / Roblox
--]]
"""

LOADER_TEMPLATE = """{banner}

{vm_code}

-- [[ Encrypted Bytecode ]]
{bc_table}
local _N_key  = {key_table}
local _N_seed = {seed}

-- [[ Execute ]]
_N_vm(_N_bc, _N_key, _N_seed)
"""


def obfuscate(source: str, seed: int = None, verbose: bool = False) -> str:
    """
    Full pipeline:
      source (Lua string) -> obfuscated Lua string

    Returns the final Lua script ready for distribution.
    """
    if seed is None:
        seed = int(time.time() * 1000) & 0xFFFFFFFF

    rng = random.Random(seed)

    # ── 1. Parse ──────────────────────────────────────────────────────────────
    if verbose:
        print("[Night] Parsing Lua source...")
    ast = parse(source)

    # ── 2. Transform (rename + encrypt strings) ────────────────────────────────
    if verbose:
        print("[Night] Transforming AST...")
    transformer = Transformer(rng)
    ast_transformed = transformer.visit(ast)

    if verbose:
        print(f"[Night]   Encrypted {len(transformer.string_table)} strings")

    # ── 3. Generate randomized opcodes ────────────────────────────────────────
    if verbose:
        print("[Night] Generating randomized opcodes...")
    opcodes = Opcodes(seed=rng.randint(0, 2**31))

    # ── 4. Compile to custom bytecode ─────────────────────────────────────────
    if verbose:
        print("[Night] Compiling to bytecode...")
    compiler = Compiler(opcodes, rng, transformer.string_table)
    proto = compiler.compile(ast_transformed)

    if verbose:
        print(f"[Night]   Root proto: {len(proto.code)} instructions, "
              f"{len(proto.consts)} consts, {len(proto.protos)} nested protos")

    # ── 5. Serialize + Encrypt ────────────────────────────────────────────────
    if verbose:
        print("[Night] Serializing and encrypting bytecode...")
    raw_bytes = serialize_proto(proto)
    enc_bytes, key, enc_seed = encrypt_bytecode(raw_bytes, rng)

    if verbose:
        print(f"[Night]   Raw: {len(raw_bytes)} bytes  →  Encrypted: {len(enc_bytes)} bytes")

    # ── 6. Generate VM runtime ────────────────────────────────────────────────
    if verbose:
        print("[Night] Generating VM runtime...")
    vm_source = generate_vm(opcodes)

    # ── 7. Encode bytecode for Lua ────────────────────────────────────────────
    lua_data = encode_for_lua(enc_bytes, key, enc_seed)

    # ── 8. Assemble final script ──────────────────────────────────────────────
    if verbose:
        print("[Night] Assembling final script...")

    output = LOADER_TEMPLATE.format(
        banner    = ASCII_BANNER,
        vm_code   = vm_source,
        bc_table  = lua_data['bc_table'],
        key_table = lua_data['key_table'],
        seed      = lua_data['seed'],
    )

    return output
