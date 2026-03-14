import sys,os;sys.path.insert(0,os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
"""NightGuard V3 — Register VM Proto"""
from ng_compiler.opcodes import pack_bx, unpack_bx, BX_BIAS

class Proto:
    def __init__(self):
        self.code     = []   # list[int] packed instrs
        self.consts   = []   # K[] mixed types
        self.protos   = []   # nested Protos
        self.nparams  = 0
        self.is_vararg= False
        self.maxreg   = 0    # max register used (set after compile)
        self.name     = '?'
        self.captures = []  # list[(name:str, reg:int)]

    # ── Emit ──────────────────────────────────────────────────────────────────
    def emit(self,instr:int)->int:
        idx=len(self.code); self.code.append(instr); return idx

    # ── Jump patching ─────────────────────────────────────────────────────────
    def patch_sbx(self,idx:int,target_pc:int):
        """Patch instruction at idx: sBx = target_pc-(idx+1)"""
        op,a,_=unpack_bx(self.code[idx])
        sbx=target_pc-(idx+1)
        self.code[idx]=pack_bx(op,a,sbx+BX_BIAS)

    def patch_bx(self,idx:int,bx:int):
        op,a,_=unpack_bx(self.code[idx])
        self.code[idx]=pack_bx(op,a,bx)

    # ── Constants ─────────────────────────────────────────────────────────────
    def add_const(self,v)->int:
        for i,c in enumerate(self.consts):
            if c==v and type(c)==type(v): return i
        self.consts.append(v); return len(self.consts)-1

    # ── Sub-protos ────────────────────────────────────────────────────────────
    def add_proto(self,p)->'Proto':
        idx=len(self.protos); self.protos.append(p); return idx
