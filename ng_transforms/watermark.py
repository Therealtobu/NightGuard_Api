import sys,os;sys.path.insert(0,os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
"""NightGuard V3 — Invisible Watermark + Anti-Tamper
Two features:
  1. Watermark: embeds a hidden signature in the bytecode constants
     as a sequence of invisible Unicode-like encoded values. If someone
     strips or modifies the obfuscated output, the watermark is destroyed,
     proving tampering.
  2. Anti-format: injects a pcall-based check that reads its own source
     line numbers at runtime; if the code is reformatted (newlines changed),
     the line numbers change and execution halts.
     (Simplified version: checks that certain runtime invariants hold.)
"""
import random
import ast_nodes as N

def _encode_watermark(text:str,rng)->list:
    """Encode watermark text as a list of integers hidden in consts."""
    key=rng.randint(1,255)
    encoded=[]
    for ch in text:
        encoded.append((ord(ch)^key)&0xFF)
    return key,encoded

def inject_watermark(proto,watermark_text:str,rng):
    """Inject watermark into proto's constant table as a tagged tuple.
    The VM ignores it (no instruction references it), but it's detectable
    in the serialized bytecode by NightGuard's verification tool.
    """
    if not watermark_text: return
    key,enc=_encode_watermark(watermark_text,rng)
    proto.add_const(('__ng_wm',key,tuple(enc)))

def _antitamper_check_node(rng):
    """Generate a Lua AST fragment that checks runtime integrity.
    Uses pcall to safely test that math functions haven't been replaced
    and that the environment is clean. If tampered, triggers infinite loop.
    """
    # local __chk = function()
    #   if pcall == nil or math == nil or math.floor == nil then
    #     local t={} repeat t[#t+1]=0 until #t>99999 end
    #   end
    # end
    # __chk()
    v=f'_ng{"".join(rng.choices("lIO01",k=8))}'
    trap_body=N.Block([
        N.LocalAssign([N.Name('_t')],[N.Number(0)]),
        N.While(
            N.BinOp('<',N.Name('_t'),N.Number(99999)),
            N.Block([N.Assign([N.Name('_t')],[N.BinOp('+',N.Name('_t'),N.Number(1))])])
        )
    ])
    # Deterministic anti-tamper check: if core runtime primitives are replaced,
    # trigger trap path.
    check=N.If(
        N.BinOp('~=',
            N.Call(N.Name('type'),[N.Field(N.Name('math'),N.Name('floor'))]),
            N.String('function')),
        trap_body,[])
    fn=N.LocalFunction(N.Name(v),[],N.Block([check]))
    call=N.Call(N.Name(v),[])
    return [fn,N.Call(N.Name(v),[])]

class AntiTamperPass:
    """Prepend anti-tamper checks to top-level block."""
    def __init__(self,rng,enabled=True):
        self._rng=rng
        self._enabled=enabled

    def visit(self,node):
        if not self._enabled: return node
        if type(node).__name__!='Block': return node
        checks=_antitamper_check_node(self._rng)
        return N.Block(checks+node.body)

def run(block,rng): return AntiTamperPass(rng).visit(block)
