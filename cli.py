import sys, os, random, time
BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)

from lexer import Lexer
from parser import Parser, parse
from ng_pipeline import TransformPipeline
from ng_compiler.opcodes import Opcodes
from ng_compiler.compiler import Compiler
from ng_compiler.serializer import serialize_proto, encrypt_bytecode, encode_for_lua
from vm.vm_generator import generate_vm

BANNER = r"""
--[[
  _   _ _       _     _      ___
 | \ | (_) __ _| |__ | |_   / __|_   _  __ _ _ __ __| |
 |  \| | |/ _` | '_ \| __| | |  _| | |/ _` | '__/ _` |
 | |\  | | (_| | | | | |_  | |_| |_| | (_| | | | (_| |
 |_| \_|_|\__, |_| |_|\__|  \____\__,_|\__,_|_|  \__,_|
          |___/
  NightGuard V2
--]]
"""

LOADER = """{banner}
local _N_vm
do
{vm}
end
local _N_bc   = {{{bc_table}}}
local _N_key  = {{{key_table}}}
local _N_seed = {seed}
_N_vm(_N_bc, _N_key, _N_seed)
"""

def obfuscate(source: str, seed=None, options=None, verbose=False) -> str:
    if seed is None: seed = int(time.time() * 1000) & 0xFFFFFFFF
    opts = options or {}
    rng  = random.Random(seed)

    ast  = parse(source)
    pipeline = TransformPipeline(rng, opts)
    ast2 = pipeline.run(ast)

    opcodes = Opcodes(seed=rng.randint(0, 2**31))
    compiler = Compiler(opcodes, rng, pipeline.string_table)
    proto = compiler.compile(ast2)

    raw = serialize_proto(proto)
    enc, key32, enc_seed = encrypt_bytecode(raw, rng)
    vm_src = generate_vm(opcodes)
    lua_data = encode_for_lua(enc, key32, enc_seed)

    return LOADER.format(
        banner    = BANNER,
        vm        = vm_src,
        bc_table  = lua_data['bc_table'],
        key_table = lua_data['key_table'],
        seed      = lua_data['seed'],
    )
