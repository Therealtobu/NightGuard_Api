import sys,os,random,time,argparse
BASE=os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0,BASE)

from lexer      import Lexer
from parser     import Parser,parse
from ng_pipeline import TransformPipeline,obfuscate_v4
from ng_compiler.opcodes     import Opcodes
from ng_compiler.compiler    import Compiler
from ng_compiler.serializer  import serialize_proto,encrypt_bytecode,encode_for_lua
from ng_compiler.proto       import Proto
from ng_transforms.watermark import inject_watermark
from vm.vm_generator         import generate_vm

# ── V3 loader template (unchanged) ───────────────────────────────────────────
V3_LOADER="""--[[
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

V3_STAGES=[
    ('parse',         'Parsing source'),
    ('rename_locals', 'Renaming locals'),
    ('anti_tamper',   'Injecting anti-tamper'),
    ('const_split',   'Splitting constants'),
    ('mba',           'Applying MBA transforms'),
    ('string_encrypt','Encrypting strings'),
    ('dead_code',     'Injecting dead code'),
    ('control_flow',  'Flattening control flow'),
    ('compile',       'Compiling AST → bytecode'),
    ('serialize',     'Serializing proto'),
    ('vm_gen',        'Generating VM'),
    ('finalize',      'Encoding output'),
]

V4_STAGES=[
    ('v4_crypto',     'Deriving per-script keys'),
    ('v4_compress',   'Compressing bytecode'),
    ('v4_encrypt',    'Encrypting with whitebox XOR'),
    ('v4_cfo',        'Injecting bytecode CFO'),
    ('v4_vm_assemble','Assembling double VM'),
    ('v4_vm_obf',     'Obfuscating VM source'),
    ('v4_watermark',  'Injecting watermark'),
    ('v4_done',       'Done'),
]

# ── V3 obfuscate (original logic, unchanged) ─────────────────────────────────
def obfuscate_v3(source:str,seed=None,options=None,
                  verbose=False,progress_cb=None,watermark=None)->str:
    def _cb(stage,detail=''):
        if progress_cb: progress_cb(stage,detail)

    if seed is None: seed=int(time.time()*1000)&0xFFFFFFFF
    opts=options or {}
    rng=random.Random(seed)

    _cb('parse',f'{len(source):,} chars')
    ast=parse(source)

    _cb('rename_locals',''); _cb('anti_tamper','')
    _cb('const_split','');   _cb('mba','')
    _cb('string_encrypt',''); _cb('dead_code','')
    _cb('control_flow','')
    pipeline=TransformPipeline(rng,opts)
    ast2=pipeline.run(ast)

    _cb('compile','')
    opcodes=Opcodes(seed=rng.randint(0,2**31))
    compiler=Compiler(opcodes,rng,pipeline.string_table,progress_cb=progress_cb)
    proto=compiler.compile(ast2)

    if watermark:
        inject_watermark(proto,watermark,rng)

    _cb('serialize','')
    raw=serialize_proto(proto)
    enc,key32,enc_seed=encrypt_bytecode(raw,rng)

    _cb('vm_gen','')
    vm_src=generate_vm(opcodes,rng_seed=rng.randint(0,2**31))

    _cb('finalize','')
    lua_data=encode_for_lua(enc,key32,enc_seed)

    return V3_LOADER.format(
        vm=vm_src,
        bc1=lua_data['bc1'],bc2=lua_data['bc2'],bc3=lua_data['bc3'],
        key_table=lua_data['key_table'],seed=lua_data['seed'],
    )

# ── Progress printer ─────────────────────────────────────────────────────────
def _make_progress(verbose:bool,stages:list):
    stage_map={s:d for s,d in stages}
    def _cb(stage,detail=''):
        if not verbose: return
        label=stage_map.get(stage,stage)
        msg=f'  [{label}]'
        if detail: msg+=f' — {detail}'
        print(msg)
    return _cb

# ── CLI entry point ──────────────────────────────────────────────────────────
def main():
    ap=argparse.ArgumentParser(
        prog='nightguard',
        description='NightGuard Lua/Luau Obfuscator'
    )
    ap.add_argument('input',             help='Input .lua file')
    ap.add_argument('-o','--output',     help='Output file (default: stdout)')
    ap.add_argument('--version',         choices=['3','4'], default='3',
                    help='Obfuscator version (default: 3)')
    ap.add_argument('--seed',            type=int, default=None,
                    help='RNG seed (default: random)')
    ap.add_argument('--watermark',       default=None,
                    help='Watermark string (V3) or user ID (V4)')
    ap.add_argument('--passes',          type=int, choices=[1,2,3], default=2,
                    help='V4 only: obfuscation passes (default: 2)')
    ap.add_argument('--no-rename',       action='store_true')
    ap.add_argument('--no-anti-tamper',  action='store_true')
    ap.add_argument('--no-const-split',  action='store_true')
    ap.add_argument('--no-mba',          action='store_true')
    ap.add_argument('--no-string-encrypt',action='store_true')
    ap.add_argument('--no-dead-code',    action='store_true')
    ap.add_argument('--no-control-flow', action='store_true')
    ap.add_argument('-v','--verbose',    action='store_true')
    args=ap.parse_args()

    # Read input
    try:
        with open(args.input,'r',encoding='utf-8') as f:
            source=f.read()
    except FileNotFoundError:
        print(f'Error: file not found: {args.input}',file=sys.stderr)
        sys.exit(1)

    if args.verbose:
        ver = args.version
        print(f'NightGuard V{ver} — {args.input} ({len(source):,} chars)')
        if args.seed: print(f'  Seed: {args.seed}')

    opts={
        'rename':         not args.no_rename,
        'anti_tamper':    not args.no_anti_tamper,
        'const_split':    not args.no_const_split,
        'mba':            not args.no_mba,
        'string_encrypt': not args.no_string_encrypt,
        'dead_code':      not args.no_dead_code,
        'control_flow':   not args.no_control_flow,
    }

    t0=time.time()

    if args.version == '3':
        cb=_make_progress(args.verbose, V3_STAGES)
        result=obfuscate_v3(
            source,
            seed=args.seed,
            options=opts,
            verbose=args.verbose,
            progress_cb=cb,
            watermark=args.watermark,
        )
    else:
        cb=_make_progress(args.verbose, V4_STAGES)
        result=obfuscate_v4(
            source,
            seed=args.seed,
            options=opts,
            progress_cb=cb,
            user_id=args.watermark or 'anonymous',
            obf_passes=args.passes,
        )

    elapsed=time.time()-t0
    if args.verbose:
        print(f'  Done in {elapsed:.2f}s — output {len(result):,} chars')

    if args.output:
        with open(args.output,'w',encoding='utf-8') as f:
            f.write(result)
        if args.verbose:
            print(f'  Written to {args.output}')
    else:
        print(result)

if __name__=='__main__':
    main()
