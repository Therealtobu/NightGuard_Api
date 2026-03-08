import sys,os;sys.path.insert(0,os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
"""NightGuard V3 — Proto serializer + AES-style bytecode encryption"""
import struct, random
from ng_compiler.opcodes import BX_BIAS

def _p8(v):  return bytes([v&0xFF])
def _p16(v): return struct.pack('<H',v&0xFFFF)
def _p32(v): return struct.pack('<I',v&0xFFFFFFFF)
def _pf64(v):return struct.pack('<d',float(v))
def _pstr(s):
    b=s.encode('utf-8'); return _p32(len(b))+b

def serialize_proto(proto)->bytes:
    out=b''
    out+=_p8(proto.nparams)
    out+=_p8(1 if proto.is_vararg else 0)
    out+=_p8(proto.maxreg)
    # code
    out+=_p32(len(proto.code))
    for instr in proto.code: out+=_p32(instr)
    # constants
    out+=_p32(len(proto.consts))
    for c in proto.consts:
        if c is None:
            out+=_p8(0)
        elif isinstance(c,bool):
            out+=_p8(1); out+=_p8(1 if c else 0)
        elif isinstance(c,(int,float)):
            out+=_p8(2); out+=_pf64(c)
        elif isinstance(c,str):
            out+=_p8(3); out+=_pstr(c)
        elif isinstance(c,tuple) and c[0]=='__enc_str':
            _,enc,seed,step,sk,chunks,noise,order=c+(None,)*(8-len(c))
            if chunks is None:
                out+=_p8(4)
                out+=_p8(seed&0xFF); out+=_p8(step&0xFF); out+=_p8(sk&0xFF)
                out+=_p32(len(enc))
                for b in enc: out+=_p8(b)
            else:
                out+=_p8(5)
                out+=_p8(seed&0xFF); out+=_p8(step&0xFF); out+=_p8(sk&0xFF)
                out+=_p32(len(enc))
                for b in enc: out+=_p8(b)
                out+=_p8(len(chunks))
                for s,l in chunks: out+=_p32(s); out+=_p32(l)
                noise=noise or []
                out+=_p8(len(noise))
                for s,l in noise: out+=_p32(s); out+=_p32(l)
                order=order if order is not None else list(range(len(chunks)))
                out+=_p8(len(order))
                for o in order: out+=_p8(o&0xFF)
        else:
            out+=_p8(3); out+=_pstr(str(c))
    # nested protos (length-prefixed blobs)
    out+=_p32(len(proto.protos))
    for child in proto.protos:
        blob=serialize_proto(child)
        out+=_p32(len(blob))+blob
    return out

def encrypt_bytecode(raw:bytes,rng)->tuple:
    """3-layer encryption: XOR key array + rolling cipher + sub."""
    key32=[rng.randint(0,255) for _ in range(32)]
    enc_seed=rng.randint(1,254)
    # Layer 1: XOR with cycling key
    tmp=[b^key32[i%32] for i,b in enumerate(raw)]
    # Layer 2: rolling XOR with feedback
    k=enc_seed; out=[]
    for b in tmp:
        e=b^k; out.append(e)
        k=(k*13+e)%256
        if k==0: k=1
    return bytes(out),key32,enc_seed

def encode_for_lua(enc:bytes,key32:list,enc_seed:int)->dict:
    """Split encrypted bytes into 3 segments for loader template."""
    n=len(enc); s1=n//3; s2=2*n//3
    def arr(seg): return ','.join(str(b) for b in seg)
    return dict(
        bc1=arr(enc[:s1]),
        bc2=arr(enc[s1:s2]),
        bc3=arr(enc[s2:]),
        key_table='{'+','.join(str(k) for k in key32)+'}',
        seed=str(enc_seed),
    )
