import sys,os,random,time
BASE=os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0,BASE)

from lexer import Lexer
from parser import Parser,parse
from ng_pipeline import TransformPipeline
from ng_compiler.opcodes import Opcodes
from ng_compiler.compiler import Compiler
from ng_compiler.serializer import serialize_proto,encrypt_bytecode,encode_for_lua
from ng_compiler.proto import Proto
from ng_transforms.watermark import inject_watermark
from vm.vm_generator import generate_vm

LOADER="""--[[
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

STAGES=[
    ('parse',         'Parsing source'),
    ('rename_locals', 'Renaming locals'),
    ('anti_tamper',   'Injecting anti-tamper'),
    ('const_split',   'Splitting constants'),
    ('mba',           'Applying MBA transforms'),
    ('string_encrypt','Encrypting strings'),
    ('dead_code',     'Injecting dead code'),
    ('control_flow',  'Flattening control flow (state machine)'),
    ('compile',       'Compiling AST → register bytecode'),
    ('serialize',     'Serializing proto'),
    ('vm_gen',        'Generating register VM'),
    ('finalize',      'Encoding output'),
]

def obfuscate(source:str,seed=None,options=None,verbose=False,progress_cb=None,watermark=None)->str:
    def _cb(stage,detail=''):
        if progress_cb: progress_cb(stage,detail)

    if seed is None: seed=int(time.time()*1000)&0xFFFFFFFF
    opts=options or {}
    rng=random.Random(seed)

    _cb('parse',f'{len(source):,} chars')
    ast=parse(source)

    _cb('rename_locals','renaming variables')
    _cb('anti_tamper','injecting checks')
    _cb('const_split','splitting numeric constants')
    _cb('mba','MBA constant obfuscation')
    _cb('string_encrypt','encrypting string literals')
    _cb('dead_code','injecting junk branches')
    _cb('control_flow','building state machines')
    pipeline=TransformPipeline(rng,opts)
    ast2=pipeline.run(ast)

    _cb('compile','compiling to register VM bytecode')
    opcodes=Opcodes(seed=rng.randint(0,2**31))
    compiler=Compiler(opcodes,rng,pipeline.string_table,progress_cb=progress_cb)
    proto=compiler.compile(ast2)

    # Optional watermark injection
    if watermark:
        inject_watermark(proto,watermark,rng)

    _cb('serialize','serializing + encrypting proto')
    raw=serialize_proto(proto)
    enc,key32,enc_seed=encrypt_bytecode(raw,rng)

    _cb('vm_gen','generating register VM')
    vm_src=generate_vm(opcodes,rng_seed=rng.randint(0,2**31))

    _cb('finalize','encoding final output')
    lua_data=encode_for_lua(enc,key32,enc_seed)

    return LOADER.format(
        vm=vm_src,
        bc1=lua_data['bc1'],bc2=lua_data['bc2'],bc3=lua_data['bc3'],
        key_table=lua_data['key_table'],seed=lua_data['seed'],
    )
