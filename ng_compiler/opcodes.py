import sys,os;sys.path.insert(0,os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
"""NightGuard V3 — Register-VM Opcode Table
Instruction format (32-bit):
  OP [7:0]  A [15:8]  B [23:16]  C [31:24]
  OP [7:0]  A [15:8]  Bx[31:16]          (wide immediate)
  OP [7:0]  A [15:8]  sBx[31:16]         (signed, biased by 0x7FFF)

RK(x): if x & 0x80 → constant K[x & 0x7F], else register R[x]
"""
import random

# (canonical, format)  format ∈ ABC | AB | ABx | AsBx | A
_DEFS = [
    # Loads
    ('LOADK',    'ABx'),   # R[A] = K[Bx]
    ('LOADNIL',  'AB'),    # R[A..A+B] = nil
    ('LOADBOOL', 'ABC'),   # R[A] = (B!=0); if C: pc++
    ('MOVE',     'AB'),    # R[A] = R[B]
    # Globals (env table)
    ('GETGLOBAL','ABx'),   # R[A] = ENV[K[Bx]]
    ('SETGLOBAL','ABx'),   # ENV[K[Bx]] = R[A]
    # Tables
    ('NEWTABLE', 'A'),     # R[A] = {}
    ('GETTABLE', 'ABC'),   # R[A] = R[B][RK(C)]
    ('SETTABLE', 'ABC'),   # R[A][RK(B)] = RK(C)
    ('SELF',     'ABC'),   # R[A+1]=R[B]; R[A]=R[B][RK(C)]
    # Arithmetic  R[A] = RK(B) op RK(C)
    ('ADD',  'ABC'), ('SUB',  'ABC'), ('MUL',  'ABC'),
    ('DIV',  'ABC'), ('MOD',  'ABC'), ('POW',  'ABC'),
    # Unary  R[A] = op R[B]
    ('UNM',  'AB'), ('NOT',  'AB'), ('LEN',  'AB'),
    # Concat R[A] = R[B] .. ... .. R[C]
    ('CONCAT','ABC'),
    # Jumps / compare
    ('JMP',      'AsBx'),  # pc += sBx  (A reserved)
    ('EQ',  'ABC'),   # if (RK(B)==RK(C)) ~= A: pc++
    ('LT',  'ABC'),   # if (RK(B)< RK(C)) ~= A: pc++
    ('LE',  'ABC'),   # if (RK(B)<=RK(C)) ~= A: pc++
    ('TEST','ABC'),   # if bool(R[A])~=C: pc++
    ('TESTSET','ABC'),# if bool(R[B])~=C: pc++ else R[A]=R[B]
    # Calls
    ('CALL',    'ABC'),  # R[A..A+C-2]=R[A](R[A+1..A+B-1]); B=0→vararg args; C=0→vararg rets
    ('RETURN',  'AB'),   # return R[A..A+B-2]  B=1→return nothing
    ('TAILCALL','ABC'),
    ('VARARG',  'AB'),   # R[A..A+B-2]=...
    # Closures
    ('CLOSURE', 'ABx'),  # R[A] = closure(P[Bx])
    # For loops
    ('FORPREP', 'AsBx'), # R[A]-=R[A+2]; pc+=sBx
    ('FORLOOP', 'AsBx'), # R[A]+=R[A+2]; if R[A]<=R[A+1]: R[A+3]=R[A]; pc+=sBx
    ('TFORLOOP','ABC'),  # R[A+3..A+2+C]=R[A](R[A+1],R[A+2]); if R[A+3]≠nil: R[A+2]=R[A+3] else pc++
    ('SETLIST', 'ABC'),  # R[A][(C-1)*FPF+i]=R[A+i] i=1..B
    # Junk no-ops (obfuscation)
    ('JUNK',  'ABC'), ('JUNK2', 'ABC'), ('JUNK3', 'ABC'),
]

_FAKE = {'JUNK','JUNK2','JUNK3'}

# Bit widths
OP_W=8; A_W=8; B_W=8; C_W=8
BX_W=16; BX_BIAS=0x7FFF
RK_BIT=0x80   # bit that marks RK as constant (7-bit const index in B/C)

def pack(op,a,b,c):   return (c&0xFF)<<24|(b&0xFF)<<16|(a&0xFF)<<8|(op&0xFF)
def pack_bx(op,a,bx): return (bx&0xFFFF)<<16|(a&0xFF)<<8|(op&0xFF)
def unpack(i):
    op=i&0xFF; a=(i>>8)&0xFF; b=(i>>16)&0xFF; c=(i>>24)&0xFF
    return op,a,b,c
def unpack_bx(i):
    op=i&0xFF; a=(i>>8)&0xFF; bx=(i>>16)&0xFFFF
    return op,a,bx
def get_sbx(i):
    _,_,bx=unpack_bx(i); return bx-BX_BIAS
def is_rk(x):  return bool(x&RK_BIT)
def rk(k):     return k|RK_BIT   # encode const index as RK

class Opcodes:
    def __init__(self,seed=None):
        rng=random.Random(seed)
        names=[d[0] for d in _DEFS]
        ids=list(range(len(names))); rng.shuffle(ids)
        self._n2i={n:ids[i] for i,n in enumerate(names)}
        self._i2n={ids[i]:n for i,n in enumerate(names)}
        self._i2f={ids[i]:_DEFS[i][1] for i in range(len(names))}
        self._rng=rng
        self.seed=seed

    def id(self,name:str)->int:
        if name not in self._n2i: raise KeyError(f'Unknown opcode: {name}')
        return self._n2i[name]
    def name(self,op_id:int)->str: return self._i2n.get(op_id,'?')
    def fmt(self,op_id:int)->str:  return self._i2f.get(op_id,'ABC')
    def is_fake(self,op_id:int)->bool: return self._i2n.get(op_id,'') in _FAKE
    def fake_ids(self): return [self._n2i[n] for n in _FAKE]
    def all_names(self): return list(self._n2i.keys())

    # ── Pack helpers ──────────────────────────────────────────────────────────
    def mk(self,nm,a=0,b=0,c=0):   return pack(self.id(nm),a,b,c)
    def mk_bx(self,nm,a,bx):       return pack_bx(self.id(nm),a,bx)
    def mk_sbx(self,nm,a,sbx):     return pack_bx(self.id(nm),a,sbx+BX_BIAS)

    def junk(self,rng=None):
        r=rng or self._rng
        jid=r.choice(self.fake_ids())
        return pack(jid,r.randint(0,15),r.randint(0,15),r.randint(0,15))

    # ── Decode helpers ────────────────────────────────────────────────────────
    def decode(self,instr):
        """Return (canon_name, op, a, b, c, bx, sbx)"""
        op,a,b,c=unpack(instr)
        _,_,bx=unpack_bx(instr)
        sbx=bx-BX_BIAS
        nm=self.name(op)
        return nm,op,a,b,c,bx,sbx
