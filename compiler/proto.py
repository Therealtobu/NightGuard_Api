"""
NightGuard V2 - Proto (Function Prototype)
Instructions are packed into 32-bit integers:
  bits 31-24 = opcode (8 bits)
  bits 23-12 = A      (12 bits)
  bits 11-0  = B      (12 bits)
"""

def pack_instr(op: int, a: int, b: int) -> int:
    return ((op & 0xFF) << 24) | ((a & 0xFFF) << 12) | (b & 0xFFF)

def unpack_instr(i: int):
    op = (i >> 24) & 0xFF
    a  = (i >> 12) & 0xFFF
    b  =  i        & 0xFFF
    return op, a, b

class Proto:
    def __init__(self):
        self.code:      list = []   # packed u32 instructions
        self.consts:    list = []
        self.protos:    list = []
        self.nparams:   int  = 0
        self.is_vararg: bool = False

    def emit(self, op, a=0, b=0) -> int:
        idx = len(self.code)
        self.code.append(pack_instr(op, a, b))
        return idx

    def patch(self, idx, a=None, b=None):
        op, oa, ob = unpack_instr(self.code[idx])
        self.code[idx] = pack_instr(op, a if a is not None else oa, b if b is not None else ob)

    def add_const(self, v) -> int:
        for i, c in enumerate(self.consts):
            if c == v and type(c) == type(v): return i
        self.consts.append(v); return len(self.consts) - 1

    def add_proto(self, p) -> int:
        idx = len(self.protos); self.protos.append(p); return idx
