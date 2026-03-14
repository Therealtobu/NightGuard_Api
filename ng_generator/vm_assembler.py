"""
NightGuard V4 - VM Assembler
Assembles Layer1 + Layer2 templates with all per-script unique values.
Produces final VM Lua source ready for deployment.
"""

import os
import re

from .opcode_shuffler import (
    generate_opcode_map, get_return_op,
    generate_lua_opmap, apply_mapping_to_bytecode
)
from .state_builder import (
    generate_state_ids, generate_flow_seed,
    generate_junk_expressions, generate_lua_states
)
from .junk_builder import (
    generate_vm_junk_blocks, wrap_in_do_block,
    generate_fake_constant_table
)

# Import from other modules
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from ng_crypto.key_schedule import (
    derive_key, derive_seed,
    derive_magic_token, derive_runtime_key,
    derive_state_seed
)
from ng_crypto.compression import LUA_DECOMPRESSOR
from ng_antitamper.linecheck import inject_linechecks
from ng_generator.lua_minifier import minify_and_fix as minify

TEMPLATES_DIR = os.path.join(
    os.path.dirname(__file__), "..", "vm", "v4", "templates"
)

def _load_template(name: str) -> str:
    path = os.path.join(TEMPLATES_DIR, name)
    with open(path, "r") as f:
        return f.read()

def _fill_template(template: str, replacements: dict) -> str:
    """Replace {{KEY}} placeholders in template."""
    result = template
    for key, value in replacements.items():
        result = result.replace("{{" + key + "}}", str(value))
    return result

def _lua_table(values: list) -> str:
    """Convert list of ints to Lua table literal."""
    return "{" + ",".join(str(v) for v in values) + "}"

def assemble_vm(script_source: str) -> str:
    """
    Assemble complete V4 VM for a given script source.
    Returns Lua source string ready to prepend to encrypted bytecode.
    """
    # ── Derive all per-script values ────────────────────────────────────────
    enc_key     = list(derive_key(script_source, 32))
    enc_seed    = derive_seed(script_source)
    magic       = derive_magic_token(script_source)
    runtime_key = derive_runtime_key(script_source)
    flow_seed   = generate_flow_seed(script_source)
    state_seed  = derive_state_seed(script_source)

    # ── Opcode mapping ───────────────────────────────────────────────────────
    opmap      = generate_opcode_map(script_source)
    return_op  = get_return_op(opmap)
    lua_opmap  = generate_lua_opmap(opmap, "_NG_OP")

    # ── State machine ────────────────────────────────────────────────────────
    state_ids  = generate_state_ids(script_source)
    junk_exprs = generate_junk_expressions(script_source, 4)

    # ── Junk blocks ──────────────────────────────────────────────────────────
    junk_blocks = generate_vm_junk_blocks(script_source, 6)
    junk_lua    = "\n".join(wrap_in_do_block(b) for b in junk_blocks)
    fake_consts = generate_fake_constant_table(script_source)

    # ── Load templates ───────────────────────────────────────────────────────
    layer1_tpl = _load_template("layer1.lua.tpl")
    layer2_tpl = _load_template("layer2.lua.tpl")

    # ── Fill Layer1 ──────────────────────────────────────────────────────────
    layer1 = _fill_template(layer1_tpl, {
        "MAGIC":       magic,
        "RUNTIME_KEY": runtime_key,
        "SEED":        enc_seed,
        "DECOMP_CODE": LUA_DECOMPRESSOR,
    })

    # ── Build state machine Lua code ─────────────────────────────────────────
    state_lua = generate_lua_states(
        state_ids, flow_seed, junk_exprs, "_NG_ST"
    )

    # ── Fill Layer2 ──────────────────────────────────────────────────────────
    layer2 = _fill_template(layer2_tpl, {
        "RETURN_OP":  return_op,
        "FLOW_SEED":  flow_seed,
        "OPMAP":      lua_opmap.strip(),
    })

    # ── Inject per-instruction decoder ──────────────────────────────────────
    from ng_crypto.per_instruction import generate_lua_decoder
    pi_decoder = generate_lua_decoder(state_seed, "_NG_PI")

    # ── Inject anti-tamper ───────────────────────────────────────────────────
    from ng_antitamper.stackcheck  import generate_stackcheck_lua
    from ng_antitamper.fingerprint import generate_tick_check_lua
    from ng_antitamper.upvalue_poison import generate_upvalue_poison_lua

    antitamper_lua = "\n".join([
        generate_stackcheck_lua(8, "_NG_SC"),
        generate_tick_check_lua("_NG_TC"),
        generate_upvalue_poison_lua("_NG_UP"),
    ])

    # ── Assemble full VM ─────────────────────────────────────────────────────
    parts = [
        fake_consts,
        junk_lua,
        antitamper_lua,
        pi_decoder,
        state_lua,
        layer1,
        layer2,
    ]

    vm_source = "\n".join(parts)


    # ── Inject line checks ────────────────────────────────────────────────────
    vm_source = inject_linechecks(vm_source)

    vm_source = minify(vm_source)
    return vm_source

def assemble_final_output(script_source: str,
                           encrypted_blob: list) -> str:
    """
    Assemble complete obfuscated output:
    VM source + encrypted bytecode call.
    """
    vm = assemble_vm(script_source)

    # Convert encrypted blob to Lua table segments (split into 3 like V3)
    seg_size = len(encrypted_blob) // 3
    bc1 = encrypted_blob[:seg_size]
    bc2 = encrypted_blob[seg_size:seg_size*2]
    bc3 = encrypted_blob[seg_size*2:]

    key  = list(derive_key(script_source, 32))
    seed = derive_seed(script_source)

    call = f"""
local _NG_bc1 = {_lua_table(bc1)}
local _NG_bc2 = {_lua_table(bc2)}
local _NG_bc3 = {_lua_table(bc3)}
local _NG_key = {_lua_table(key)}
local _NG_seed = {seed}
_NG_L1(_NG_bc1, _NG_bc2, _NG_bc3, _NG_key, _NG_seed, _NG_L2)
"""
    return vm + "\n" + call
