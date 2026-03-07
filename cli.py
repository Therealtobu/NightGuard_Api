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

LOADER="--[[\n _   _ _       _     _      ____                     _ \n| \\ | (_) __ _| |__ | |_   / ___|_   _  __ _ _ __ __| |\n|  \\| | |/ _` | '_' \\| __| | |  _| | | |/ _` | '__/ _` |\n| |\\  | | (_| | | | | |_  | |_| | |_| | (_| | | | (_| |\n|_| \\_|_|\\__, |_| |_|\\__|  \\____|\\__,_|\\__,_|_|  \\__,_|\n         |___/\n NightGuard V2\n--]]\n{vm}\nlocal _N_bc1={{{bc1}}}\nlocal _N_bc2={{{bc2}}}\nlocal _N_bc3={{{bc3}}}\nlocal _N_key={key_table}\nlocal _N_seed={seed}\n_N_vm(_N_bc1,_N_bc2,_N_bc3,_N_key,_N_seed)"

# Stage names in order — used by bot.py for progress display
STAGES = [
    ("parse",         "Parsing source"),
    ("rename_locals", "Renaming locals"),
    ("const_split",   "Splitting constants"),
    ("string_encrypt","Encrypting strings"),
    ("dead_code",     "Injecting dead code"),
    ("control_flow",  "Flattening control flow"),
    ("compile",       "Compiling AST → bytecode"),
    ("serialize",     "Serializing proto"),
    ("vm_gen",        "Generating VM"),
    ("finalize",      "Encoding output"),
]

def obfuscate(source: str, seed=None, options=None, verbose=False, progress_cb=None) -> str:
    def _cb(stage: str, detail: str = ""):
        if progress_cb:
            progress_cb(stage, detail)

    if seed is None: seed = int(time.time() * 1000) & 0xFFFFFFFF
    opts = options or {}
    rng  = random.Random(seed)

    _cb("parse", f"{len(source):,} chars")
    ast = parse(source)

    # Pipeline runs all transforms — we fire callbacks before each so the
    # embed updates in near-real-time (pipeline itself is blocking but short)
    _cb("rename_locals", "renaming variables")
    _cb("const_split",   "splitting numeric constants")
    _cb("string_encrypt","encrypting string literals")
    _cb("dead_code",     "injecting junk branches")
    _cb("control_flow",  "building state machines")
    pipeline = TransformPipeline(rng, opts)
    ast2 = pipeline.run(ast)

    _cb("compile", "compiling to VM bytecode")
    opcodes  = Opcodes(seed=rng.randint(0, 2**31))
    compiler = Compiler(opcodes, rng, pipeline.string_table, progress_cb=progress_cb)
    proto    = compiler.compile(ast2)

    _cb("serialize", "serializing + encrypting proto")
    raw = serialize_proto(proto)
    enc, key32, enc_seed = encrypt_bytecode(raw, rng)

    _cb("vm_gen", "mutating VM & dispatch table")
    vm_src = generate_vm(opcodes, rng_seed=rng.randint(0, 2**31), layout=opcodes.layout)

    _cb("finalize", "encoding final output")
    lua_data = encode_for_lua(enc, key32, enc_seed)

    return LOADER.format(
        vm        = vm_src,
        bc1       = lua_data['bc1'],
        bc2       = lua_data['bc2'],
        bc3       = lua_data['bc3'],
        key_table = lua_data['key_table'],
        seed      = lua_data['seed'],
    )
