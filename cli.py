import sys, os, random, time, argparse
BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)

from stages import V3_STAGES, V4_STAGES, STAGES, stage_order, stage_map
from ng_pipeline import TransformPipeline, obfuscate_v4
from ng_compiler.opcodes    import Opcodes
from ng_compiler.compiler   import Compiler
from ng_compiler.serializer import serialize_proto, encrypt_bytecode, encode_for_lua
from ng_transforms.watermark import inject_watermark
from vm.vm_generator        import generate_vm

try:
    from parser import parse
except ImportError:
    parse = None

# ── V3 loader template ────────────────────────────────────────────────────────
V3_LOADER = """--[[
 _   _ _       _     _      ____                     _
| \\ | (_) __ _| |__ | |_   / ___|_   _  __ _ _ __ __| |
|  \\| | |/ _` | '_ \\| __| | |  _| | | |/ _` | '__/ _` |
| |\\  | | (_| | | | | |_  | |_| | |_| | (_| | | | (_| |
|_| \\_|_|\\__, |_| |_|\\__|  \\____|\\__,_|\\__,_|_|  \\__,_|
         |___/
 NightGuard V3
--]]
{vm}
local _N_bc1={{{bc1}}}
local _N_bc2={{{bc2}}}
local _N_bc3={{{bc3}}}
local _N_key={key_table}
local _N_seed={seed}
_N_vm(_N_bc1,_N_bc2,_N_bc3,_N_key,_N_seed)"""

# ── V3 obfuscate ──────────────────────────────────────────────────────────────
def obfuscate_v3(source: str, seed=None, options=None,
                  progress_cb=None, watermark=None) -> str:
    def _cb(stage, detail=""):
        if progress_cb: progress_cb(stage, detail)

    if seed is None: seed = int(time.time() * 1000) & 0xFFFFFFFF
    opts = options or {}
    rng  = random.Random(seed)

    _cb("parse",          f"{len(source):,} chars")
    ast = parse(source)

    for s in ("rename_locals","anti_tamper","const_split",
              "mba","string_encrypt","dead_code","control_flow"):
        _cb(s, "")

    pipeline = TransformPipeline(rng, opts)
    ast2     = pipeline.run(ast)

    _cb("compile", "")
    opcodes  = Opcodes(seed=rng.randint(0, 2**31))
    compiler = Compiler(opcodes, rng, pipeline.string_table, progress_cb=progress_cb)
    proto    = compiler.compile(ast2)

    if watermark:
        inject_watermark(proto, watermark, rng)

    _cb("serialize", "")
    raw                  = serialize_proto(proto)
    enc, key32, enc_seed = encrypt_bytecode(raw, rng)

    _cb("vm_gen",   "")
    vm_src   = generate_vm(opcodes, rng_seed=rng.randint(0, 2**31))

    _cb("finalize", "")
    lua_data = encode_for_lua(enc, key32, enc_seed)

    return V3_LOADER.format(
        vm        = vm_src,
        bc1       = lua_data["bc1"],
        bc2       = lua_data["bc2"],
        bc3       = lua_data["bc3"],
        key_table = lua_data["key_table"],
        seed      = lua_data["seed"],
    )


# ── Unified obfuscate() — called by bot.py ───────────────────────────────────
def obfuscate(source: str, seed=None, options=None,
               progress_cb=None, watermark=None,
               version: int = 3,
               user_id: str = "anonymous",
               obf_passes: int = 2) -> str:
    if version == 4:
        return obfuscate_v4(
            source, seed=seed, options=options,
            progress_cb=progress_cb,
            user_id=user_id, obf_passes=obf_passes,
        )
    return obfuscate_v3(
        source, seed=seed, options=options,
        progress_cb=progress_cb, watermark=watermark,
    )


# ── Progress printer ──────────────────────────────────────────────────────────
def _make_progress(verbose: bool, version: int):
    smap = stage_map(version)
    def _cb(stage, detail=""):
        if not verbose: return
        label = smap.get(stage, stage)
        print(f"  [{label}]{' — ' + detail if detail else ''}")
    return _cb


# ── CLI ───────────────────────────────────────────────────────────────────────
def main():
    ap = argparse.ArgumentParser(prog="nightguard",
                                  description="NightGuard Lua/Luau Obfuscator")
    ap.add_argument("input")
    ap.add_argument("-o", "--output", default=None)
    ap.add_argument("--version",      choices=["3","4"], default="3")
    ap.add_argument("--seed",         type=int, default=None)
    ap.add_argument("--watermark",    default=None,
                    help="Watermark string (V3) or user-id (V4)")
    ap.add_argument("--passes",       type=int, choices=[1,2,3], default=2,
                    help="V4 only: obfuscation passes")
    ap.add_argument("--no-rename",          action="store_true")
    ap.add_argument("--no-anti-tamper",     action="store_true")
    ap.add_argument("--no-const-split",     action="store_true")
    ap.add_argument("--no-mba",             action="store_true")
    ap.add_argument("--no-string-encrypt",  action="store_true")
    ap.add_argument("--no-dead-code",       action="store_true")
    ap.add_argument("--no-control-flow",    action="store_true")
    ap.add_argument("-v", "--verbose",      action="store_true")
    args = ap.parse_args()

    try:
        with open(args.input, "r", encoding="utf-8") as f:
            source = f.read()
    except FileNotFoundError:
        print(f"Error: {args.input} not found", file=sys.stderr); sys.exit(1)

    ver = int(args.version)
    if args.verbose:
        print(f"NightGuard V{ver} — {args.input} ({len(source):,} chars)")

    opts = {
        "rename":         not args.no_rename,
        "anti_tamper":    not args.no_anti_tamper,
        "const_split":    not args.no_const_split,
        "mba":            not args.no_mba,
        "string_encrypt": not args.no_string_encrypt,
        "dead_code":      not args.no_dead_code,
        "control_flow":   not args.no_control_flow,
    }

    t0     = time.time()
    result = obfuscate(
        source, seed=args.seed, options=opts,
        progress_cb=_make_progress(args.verbose, ver),
        watermark=args.watermark, version=ver,
        user_id=args.watermark or "anonymous",
        obf_passes=args.passes,
    )
    elapsed = time.time() - t0

    if args.verbose:
        print(f"  Done in {elapsed:.2f}s — {len(result):,} chars")

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(result)
        if args.verbose:
            print(f"  Written to {args.output}")
    else:
        print(result)


if __name__ == "__main__":
    main()
