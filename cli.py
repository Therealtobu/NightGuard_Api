#!/usr/bin/env python3
"""
NightGuard V2 - CLI
Usage: python cli.py input.lua [output.lua] [options]
"""
import sys, os, argparse, random, time, json

sys.path.insert(0, os.path.dirname(__file__))

from lexer              import Lexer
from parser             import Parser, parse
from ng_pipeline import TransformPipeline
from compiler.opcodes   import Opcodes
from compiler.compiler  import Compiler
from compiler.serializer import serialize_proto, encrypt_bytecode, encode_for_lua
from vm.vm_generator    import generate_vm

BANNER = r"""
--[[
  _   _ _       _     _      ___
 | \ | (_) __ _| |__ | |_   / __|_   _  __ _ _ __ __| |
 |  \| | |/ _` | '_ \| __| | |  _| | |/ _` | '__/ _` |
 | |\  | | (_| | | | | |_  | |_| |_| | (_| | | | (_| |
 |_| \_|_|\__, |_| |_|\__|  \____\__,_|\__,_|_|  \__,_|
           |___/
   NightGuard V2 — VM-Based Lua Obfuscator
   Lua 5.1 / Roblox Luau Compatible
--]]
"""

LOADER = """{banner}
{vm}

-- [[ Encrypted Bytecode ]]
{bc_table}
local _N_key  = {key_table}
local _N_seed = {seed}

_N_vm(_N_bc, _N_key, _N_seed)
"""


def obfuscate(source: str, seed=None, options=None, verbose=False) -> str:
    if seed is None: seed = int(time.time() * 1000) & 0xFFFFFFFF
    opts = options or {}
    rng  = random.Random(seed)

    def log(msg):
        if verbose: print(f"  [Night] {msg}")

    # 1. Parse
    log("Parsing...")
    ast = parse(source)

    # 2. Transform
    log("Transforming AST...")
    pipeline = TransformPipeline(rng, opts)
    ast2 = pipeline.run(ast)
    log(f"  Strings encrypted: {len(pipeline.string_table)}")

    # 3. Opcodes
    log("Generating opcode table...")
    opcodes = Opcodes(seed=rng.randint(0, 2**31))

    # 4. Compile
    log("Compiling to bytecode...")
    compiler = Compiler(opcodes, rng, pipeline.string_table)
    proto = compiler.compile(ast2)
    log(f"  Root proto: {len(proto.code)} instructions, {len(proto.consts)} consts, {len(proto.protos)} nested")

    # 5. Serialize + encrypt
    log("Serializing and encrypting...")
    raw = serialize_proto(proto)
    enc, key32, enc_seed = encrypt_bytecode(raw, rng)
    log(f"  {len(raw)} bytes -> {len(enc)} bytes encrypted")

    # 6. VM runtime
    log("Generating VM runtime...")
    vm_src = generate_vm(opcodes)

    # 7. Encode
    lua_data = encode_for_lua(enc, key32, enc_seed)

    # 8. Assemble
    return LOADER.format(
        banner    = BANNER,
        vm        = vm_src,
        bc_table  = lua_data['bc_table'],
        key_table = lua_data['key_table'],
        seed      = lua_data['seed'],
    )


def main():
    p = argparse.ArgumentParser(prog='nightguard', description='NightGuard V2 Lua Obfuscator')
    p.add_argument('input')
    p.add_argument('output', nargs='?')
    p.add_argument('--seed',       type=int,   default=None)
    p.add_argument('--no-rename',  action='store_true')
    p.add_argument('--no-strings', action='store_true')
    p.add_argument('--no-split',   action='store_true')
    p.add_argument('--no-dead',    action='store_true')
    p.add_argument('--no-flow',    action='store_true')
    p.add_argument('--verbose',    action='store_true')
    p.add_argument('--debug',      action='store_true', help='Print AST + opcode table')
    args = p.parse_args()

    if not os.path.isfile(args.input):
        print(f"Error: {args.input} not found"); sys.exit(1)

    with open(args.input, 'r', encoding='utf-8') as f:
        source = f.read()

    print("""
  _   _ _       _     _      ___
 | \\ | (_) __ _| |__ | |_   / __|_   _  __ _ _ __ __| |
 |  \\| | |/ _` | '_  | __| | |  _| | |/ _` | '__/ _` |
 | |\\  | | (_| | | | | |_  | |_| |_| | (_| | | | (_| |
 |_| \\_|_|\\__, |_| |_|\\__|  \\____\\__,_|\\__,_|_|  \\__,_|
           |___/
  NightGuard V2  |  {input}""".format(input=args.input))
    print()

    opts = {
        'rename':        not args.no_rename,
        'string_encrypt':not args.no_strings,
        'const_split':   not args.no_split,
        'dead_code':     not args.no_dead,
        'control_flow':  not args.no_flow,
    }

    try:
        result = obfuscate(source, seed=args.seed, options=opts, verbose=args.verbose or args.debug)
    except Exception as e:
        import traceback
        print(f"\n  [FAILED] {e}")
        traceback.print_exc()
        sys.exit(2)

    out_path = args.output or (os.path.splitext(args.input)[0] + '_ng.lua')
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(result)

    print(f"  [OK]  {args.input} ({len(source):,}B) -> {out_path} ({len(result):,}B)")


if __name__ == '__main__':
    main()
