import sys,os;sys.path.insert(0,os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import random

def scatter_string_table(string_table:dict,rng)->dict:
    new={}
    for idx,entry in string_table.items():
        if len(entry)==4:
            enc_bytes,seed,step,sub_key=entry
        else:
            enc_bytes,seed,step=entry;sub_key=0
        n=len(enc_bytes)
        if n<4:
            new[idx]=(enc_bytes,seed,step,sub_key,None,[])
            continue
        # Split into 2-4 real chunks IN ORDER — VM reads chunks sequentially = correct assembly
        nc=rng.randint(2,min(4,n))
        cuts=sorted(rng.sample(range(1,n),nc-1))
        starts=[0]+cuts;ends=cuts+[n]
        chunks=[(s,e-s) for s,e in zip(starts,ends)]
        # Noise chunks: VM reads and discards these (the nn loop in LDP)
        noise_n=rng.randint(1,3)
        noise=[(rng.randint(0,max(0,n-2)),rng.randint(1,max(1,n//4))) for _ in range(noise_n)]
        new[idx]=(enc_bytes,seed,step,sub_key,chunks,noise)
    return new
