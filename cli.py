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
{vm}
local _N_bc1={{{bc1}}}
local _N_bc2={{{bc2}}}
local _N_bc3={{{bc3}}}
local _N_key={key_table}
local _N_seed={seed}
_N_vm(_N_bc1,_N_bc2,_N_bc3,_N_key,_N_seed)
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
    vm_src = generate_vm(opcodes, rng_seed=rng.randint(0, 2**31))
    lua_data = encode_for_lua(enc, key32, enc_seed)

    return LOADER.format(
        banner    = BANNER,
        vm        = vm_src,
        bc1       = lua_data['bc1'],
        bc2       = lua_data['bc2'],
        bc3       = lua_data['bc3'],
        key_table = lua_data['key_table'],
        seed      = lua_data['seed'],
    )
