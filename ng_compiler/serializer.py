import sys,os;sys.path.insert(0,os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import struct,random

def _p8(v):  return struct.pack('B',v&0xFF)
def _p32(v): return struct.pack('<I',v&0xFFFFFFFF)
def _pf64(v):return struct.pack('<d',float(v))
def _pstr(s):e=s.encode('utf-8');return _p32(len(e))+e
def _pblk(b):return _p32(len(b))+b

def serialize_proto(proto)->bytes:
    out=bytearray()
    out+=_p8(proto.nparams)
    out+=_p8(1 if proto.is_vararg else 0)
    out+=_p32(len(proto.code))
    for instr in proto.code: out+=_p32(instr)
    out+=_p32(len(proto.consts))
    for c in proto.consts:
        if c is None:
            out+=_p8(0)
        elif isinstance(c,bool):
            out+=_p8(1);out+=_p8(1 if c else 0)
        elif isinstance(c,(int,float)):
            out+=_p8(2);out+=_pf64(c)
        elif isinstance(c,str):
            out+=_p8(3);out+=_pstr(c)
        elif isinstance(c,tuple) and c[0]=='__enc_str':
            # Format: ('__enc_str', enc_bytes, seed, step, sub_key, chunks, noise)
            # chunks = list of (start,length) or None
            # noise  = list of (start,length) fake chunks
            if len(c)==7:
                _,enc_bytes,seed,step,sub_key,chunks,noise=c
            elif len(c)==5:
                _,enc_bytes,seed,step,sub_key=c;chunks=None;noise=[]
            else:
                _,enc_bytes,seed,step=c;sub_key=0;chunks=None;noise=[]
            if chunks is None:
                # no scatter — emit as type 4 (contiguous)
                out+=_p8(4)
                out+=_p8(seed&0xFF);out+=_p8(step&0xFF);out+=_p8(sub_key&0xFF)
                out+=_p32(len(enc_bytes))
                for b in enc_bytes:out+=_p8(b)
            else:
                # scattered — type 5
                # layout: seed,step,sub_key | n_real_chunks | [(off,len),...] | n_noise | [(off,len),...] | raw_bytes
                out+=_p8(5)
                out+=_p8(seed&0xFF);out+=_p8(step&0xFF);out+=_p8(sub_key&0xFF)
                out+=_p32(len(enc_bytes))
                for b in enc_bytes:out+=_p8(b)
                out+=_p8(len(chunks))
                for s,l in chunks:out+=_p32(s);out+=_p32(l)
                noise=noise or []
                out+=_p8(len(noise))
                for s,l in noise:out+=_p32(s);out+=_p32(l)
        else:
            out+=_p8(3);out+=_pstr(str(c))
    out+=_p32(len(proto.protos))
    for child in proto.protos:
        cb=serialize_proto(child);out+=_pblk(cb)
    return bytes(out)

def encrypt_bytecode(raw:bytes,rng:random.Random):
    seed=rng.randint(2,253)
    key32=bytes(rng.randint(2,253) for _ in range(32))
    layer1=bytearray(raw)
    key=seed
    for i in range(len(layer1)):
        orig=layer1[i];layer1[i]=orig^key
        key=(key*13+layer1[i])%256
        if key==0:key=1
    klen=len(key32)
    layer2=bytes(b^key32[i%klen] for i,b in enumerate(layer1))
    return layer2,key32,seed

def encode_for_lua(enc:bytes,key32:bytes,seed:int)->dict:
    n=len(enc);s1=n//3;s2=(n*2)//3
    def nums(b):return ','.join(str(x) for x in b)
    return {
        'bc1':nums(enc[:s1]),'bc2':nums(enc[s1:s2]),'bc3':nums(enc[s2:]),
        'key_table':'{'+','.join(str(b) for b in key32)+'}',
        'seed':seed,
    }
