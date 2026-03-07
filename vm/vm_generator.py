import sys,os;sys.path.insert(0,os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ── INNER VM (real executor, encrypted inside outer VM) ──────────────────────
# Placeholders __I_xxx__ → random names per build
_INNER_VM = r'''local __I_XOR__
if bit then __I_XOR__=bit.bxor
elseif bit32 then __I_XOR__=bit32.bxor
else __I_XOR__=function(a,b)local r,m=0,1;while a>0 or b>0 do;local x,y=a%2,b%2;if x~=y then r=r+m end;a,b,m=math.floor(a/2),math.floor(b/2),m*2 end;return r end
end
local function __I_DS__(e,sd,st,sk)local d={};for i=1,#e do d[i]=(e[i]-(sk or 0)*i%256+256)%256 end;local k=sd;local c={};for i=1,#d do c[i]=string.char(__I_XOR__(d[i],k));k=(k*st+d[i])%256;if k==0 then k=1 end end;return table.concat(c)end
local function __I_DSC__(e,sd,st,sk,chunks)local raw={};local ci=1;for _,ch in ipairs(chunks)do local s,l=ch[1],ch[2];for j=s+1,s+l do raw[ci]=e[j];ci=ci+1 end end;return __I_DS__(raw,sd,st,sk)end
local function __I_RDR__(b)local p=1;local R={}
function R.u8()local v=b[p];p=p+1;return v end
function R.u32()local a,b2,c,d=b[p],b[p+1],b[p+2],b[p+3];p=p+4;return a+b2*256+c*65536+d*16777216 end
function R.f64()local B={b[p],b[p+1],b[p+2],b[p+3],b[p+4],b[p+5],b[p+6],b[p+7]};p=p+8;local s=B[8]>=128 and -1 or 1;local e=(B[8]%128)*16+math.floor(B[7]/16);local m=(B[7]%16)*2^48+B[6]*2^40+B[5]*2^32+B[4]*2^24+B[3]*2^16+B[2]*2^8+B[1];if e==0 then return s*math.ldexp(m,-1074)elseif e==2047 then return s*(1/0)else return s*math.ldexp(m+2^52,e-1075)end end
function R.str()local n=R.u32();local c={};for i=1,n do c[i]=string.char(b[p]);p=p+1 end;return table.concat(c)end
function R.blk()local n=R.u32();local t={};for i=1,n do t[i]=b[p];p=p+1 end;return t end
return R end
local function __I_LDP__(R)local p={};p.np=R.u8();p.va=R.u8()==1;local nc=R.u32();p.code={};for i=1,nc do p.code[i]=R.u32()end;local nk=R.u32();p.k={}
for i=1,nk do local t=R.u8()
if t==0 then p.k[i]=nil
elseif t==1 then p.k[i]=R.u8()~=0
elseif t==2 then p.k[i]=R.f64()
elseif t==3 then p.k[i]=R.str()
elseif t==4 then local sd=R.u8();local st=R.u8();local sk=R.u8();local n=R.u32();local e={};for j=1,n do e[j]=R.u8()end;p.k[i]=__I_DS__(e,sd,st,sk)
elseif t==5 then local sd=R.u8();local st=R.u8();local sk=R.u8();local n=R.u32();local e={};for j=1,n do e[j]=R.u8()end;local nc2=R.u8();local ch={};for j=1,nc2 do local s=R.u32();local l=R.u32();ch[j]={s,l}end;local nn=R.u8();for j=1,nn do R.u32();R.u32()end;p.k[i]=__I_DSC__(e,sd,st,sk,ch)
end end
local np=R.u32();p.pr={}
for i=1,np do local bl=R.blk();p.pr[i]=__I_LDP__(__I_RDR__(bl))end
return p end
local function __I_UNP__(ins)__INNER_LAYOUT__
end
local __I_R0__,__I_R1__,__I_R2__,__I_R3__=0,0,0,0
local __I_R4__,__I_R5__,__I_R6__,__I_R7__=0,0,0,0
local __I_GC__=0x5A3F
local __I_OP__=__INNER_OP__
local function __I_EXE__(proto,env,va)
local _co=coroutine.create(function()
local cd=proto.code;local k=proto.k;local pr=proto.pr
local st={};local sp=0;local lc={};local pc=1
local function P(v)__I_R0__=v;sp=sp+1;st[sp]=__I_R0__ end
local function Q()__I_R1__=st[sp];st[sp]=nil;sp=sp-1;__I_R2__=__I_R1__;return __I_R1__ end
local function T()return st[sp]end
repeat
if pc>#cd then break end
local ins=cd[pc];pc=pc+1
__I_R3__,__I_R4__,__I_R5__=__I_UNP__(ins)
local op=__I_R3__;local A=__I_R4__;local B=__I_R5__
__I_GC__=(__I_GC__*1103515245+12345)%0x80000000
__I_R6__=__I_GC__%256
if __I_GC__*__I_GC__+1>0 then
local c=__I_OP__[op]
if c==1 then P(k[A+1])
elseif c==2 then P(nil)
elseif c==3 then P(A~=0)
elseif c==4 then __I_R7__=lc[A+1];P(__I_R7__)
elseif c==5 then __I_R7__=Q();lc[A+1]=__I_R7__
elseif c==6 then P(env[k[A+1]])
elseif c==7 then env[k[A+1]]=Q()
elseif c==8 then P({})
elseif c==9 then local ki=Q();local tb=Q();__I_R7__=tb and tb[ki];P(__I_R7__)
elseif c==10 then local ki=Q();local tb=Q();local v=Q();if tb then tb[ki]=v end
elseif c==11 then local tb=Q();__I_R7__=tb and tb[k[A+1]];P(__I_R7__)
elseif c==12 then local v=Q();local tb=Q();if tb then tb[k[A+1]]=v end
elseif c==13 then
local args={};for i=A,1,-1 do args[i]=Q()end;local fn=Q()
__I_R0__=fn
if type(fn)=="function" then
if B==0 then fn(table.unpack(args))
elseif B==1 then __I_R7__=fn(table.unpack(args));P(__I_R7__)
else local r={fn(table.unpack(args))};for i=1,B do P(r[i])end end
end
elseif c==14 then
if A==0 then return end
local r={};for i=A,1,-1 do r[i]=Q()end;return table.unpack(r)
elseif c==15 then pc=A+1
elseif c==16 then if T()then pc=A+1 end
elseif c==17 then if not T()then pc=A+1 end
elseif c==18 then if Q()then pc=A+1 end
elseif c==19 then if not Q()then pc=A+1 end
elseif c==20 then Q()
elseif c==21 then __I_R4__=Q();st[sp]=st[sp]+__I_R4__
elseif c==22 then __I_R4__=Q();st[sp]=st[sp]-__I_R4__
elseif c==23 then __I_R4__=Q();st[sp]=st[sp]*__I_R4__
elseif c==24 then __I_R4__=Q();st[sp]=st[sp]/__I_R4__
elseif c==25 then __I_R4__=Q();st[sp]=st[sp]%__I_R4__
elseif c==26 then __I_R4__=Q();st[sp]=st[sp]^__I_R4__
elseif c==27 then __I_R4__=Q();st[sp]=tostring(st[sp])..tostring(__I_R4__)
elseif c==28 then st[sp]=-st[sp]
elseif c==29 then st[sp]=not st[sp]
elseif c==30 then st[sp]=#st[sp]
elseif c==31 then __I_R4__=Q();st[sp]=(st[sp]==__I_R4__)
elseif c==32 then __I_R4__=Q();st[sp]=(st[sp]~=__I_R4__)
elseif c==33 then __I_R4__=Q();st[sp]=(st[sp]<__I_R4__)
elseif c==34 then __I_R4__=Q();st[sp]=(st[sp]<=__I_R4__)
elseif c==35 then __I_R4__=Q();st[sp]=(st[sp]>__I_R4__)
elseif c==36 then __I_R4__=Q();st[sp]=(st[sp]>=__I_R4__)
elseif c==37 then
local p2=pr[A+1];local ue=env
P(function(...)local a={...};local nl={};for i=1,p2.np do nl[i]=a[i]end;local nv={};if p2.va then for i=p2.np+1,#a do nv[#nv+1]=a[i]end end;return __I_EXE__(p2,ue,nv)end)
elseif c==38 then P(T())
elseif c==39 then __I_R4__=Q();__I_R5__=Q();P(__I_R4__);P(__I_R5__)
elseif c==40 then local n=A==0 and #va or A;for i=1,n do P(va[i])end
elseif c==41 then local tb=Q();local m=tb and tb[k[A+1]];P(m);P(tb)
end
__I_R6__=st[sp] or 0;__I_R7__=__I_GC__%128
end
-- yield every 200 instructions for lazy execution (Roblox safe)
if pc%200==0 then coroutine.yield()end
until pc>#cd
end)
-- step coroutine until done
local function step()
local ok,err=coroutine.resume(_co)
if not ok then return end
if coroutine.status(_co)~="dead" then
if task then task.defer(step)else delay(0,step)end
end
end
step()
end
'''

# ── OUTER VM (decrypts + runs inner VM) ──────────────────────────────────────
_OUTER_VM = r'''local _N_vm
__OUTER_OP__
local __O_XOR__
if bit then __O_XOR__=bit.bxor
elseif bit32 then __O_XOR__=bit32.bxor
else __O_XOR__=function(a,b)local r,m=0,1;while a>0 or b>0 do;local x,y=a%2,b%2;if x~=y then r=r+m end;a,b,m=math.floor(a/2),math.floor(b/2),m*2 end;return r end
end
local function __O_CHK__()
if debug then
if type(debug.sethook)=="function" then local ok,h=pcall(debug.gethook);if ok and h~=nil then local t={};repeat t[#t+1]=0 until #t>5e4 end end
if type(debug.getinfo)~="function" then local t={};repeat t[#t+1]=0 until #t>5e4 end
end
if type(math.floor)~="function" or type(pcall)~="function" then local t={};repeat t[#t+1]=0 until #t>5e4 end
end
__O_CHK__()
local function __O_DEC__(bc,key,sd)local kl=#key;local tmp={};for i=1,#bc do tmp[i]=__O_XOR__(bc[i],key[((i-1)%kl)+1])end;local out={};local k=sd;for i=1,#tmp do local e=tmp[i];out[i]=__O_XOR__(e,k);k=(k*13+e)%256;if k==0 then k=1 end end;return out end
local function __O_INJECT__(dec)
-- outer VM decrypts bytecode then loads inner VM source + executes it
local env=getfenv and getfenv(0) or _G
local inner_src=__INNER_SRC__
local inner_fn=loadstring(inner_src) or load(inner_src)
if inner_fn then inner_fn()end
local inner_exe=env.__I_EXE__ or __I_EXE__
end
_N_vm=function(bc1,bc2,bc3,key,seed)
local bc={};for _,seg in ipairs({bc1,bc2,bc3})do for i=1,#seg do bc[#bc+1]=seg[i]end end
local dec=__O_DEC__(bc,key,seed)
local R=__O_RDR__(dec)
local proto=__O_LDP__(R)
local env=getfenv and getfenv(0) or _G
__I_EXE__(proto,env,{})
end
'''

_CANON_ID={
    'LOAD_CONST':1,'LOAD_NIL':2,'LOAD_BOOL':3,
    'LOAD_LOCAL':4,'STORE_LOCAL':5,
    'LOAD_GLOBAL':6,'STORE_GLOBAL':7,
    'NEW_TABLE':8,'GET_TABLE':9,'SET_TABLE':10,
    'GET_FIELD':11,'SET_FIELD':12,
    'CALL':13,'RETURN':14,
    'JUMP':15,'JUMP_TRUE':16,'JUMP_FALSE':17,
    'JUMP_TRUE_POP':18,'JUMP_FALSE_POP':19,
    'POP':20,
    'ADD':21,'SUB':22,'MUL':23,'DIV':24,'MOD':25,'POW':26,
    'CONCAT':27,'UNM':28,'NOT':29,'LEN':30,
    'EQ':31,'NEQ':32,'LT':33,'LE':34,'GT':35,'GE':36,
    'MAKE_CLOSURE':37,'DUP':38,'SWAP':39,'VARARG':40,'SELF':41,
    'JUNK':0,'FAKE_STACK':0,'FAKE_MATH':0,'ADD_ALT':21,
}

_INNER_PH=[
    '__I_XOR__','__I_DS__','__I_DSC__','__I_RDR__','__I_LDP__',
    '__I_UNP__','__I_R0__','__I_R1__','__I_R2__','__I_R3__',
    '__I_R4__','__I_R5__','__I_R6__','__I_R7__','__I_GC__',
    '__I_EXE__','__I_OP__',
]
_OUTER_PH=[
    '__O_XOR__','__O_CHK__','__O_DEC__','__O_INJECT__',
    '__O_RDR__','__O_LDP__',
]

def _rn(rng,used,n=10):
    chars='IlO01'
    while True:
        v='_'+rng.choice('lIO')+''.join(rng.choices(chars,k=n-1))
        if v not in used:used.add(v);return v

def _build_op_table(name,opcodes):
    lines=[f'local {name}={{}}']
    for alias,val in opcodes.all().items():
        cid=_CANON_ID.get(opcodes.canonical(val),0)
        if cid>0:lines.append(f'{name}[{val}]={cid}')
    return ';'.join(lines)

def _build_unpack(layout):
    if layout is None:layout=(24,8,12,12,0,12)
    op_shift,op_bits,a_shift,a_bits,b_shift,b_bits=layout
    om=(1<<op_bits)-1;am=(1<<a_bits)-1;bm=(1<<b_bits)-1
    return(f'local _op=math.floor(ins/{2**op_shift})%{om+1};'
           f'local _a=math.floor(ins/{2**a_shift})%{am+1};'
           f'local _b=ins%{bm+1};return _op,_a,_b')

def _build_reader_loader():
    """Shared reader+loader used by both inner (inlined) and outer VM."""
    return r'''local function __I_RDR__(b)local p=1;local R={}
function R.u8()local v=b[p];p=p+1;return v end
function R.u32()local a,b2,c,d=b[p],b[p+1],b[p+2],b[p+3];p=p+4;return a+b2*256+c*65536+d*16777216 end
function R.f64()local B={b[p],b[p+1],b[p+2],b[p+3],b[p+4],b[p+5],b[p+6],b[p+7]};p=p+8;local s=B[8]>=128 and -1 or 1;local e2=(B[8]%128)*16+math.floor(B[7]/16);local m=(B[7]%16)*2^48+B[6]*2^40+B[5]*2^32+B[4]*2^24+B[3]*2^16+B[2]*2^8+B[1];if e2==0 then return s*math.ldexp(m,-1074)elseif e2==2047 then return s*(1/0)else return s*math.ldexp(m+2^52,e2-1075)end end
function R.str()local n=R.u32();local c={};for i=1,n do c[i]=string.char(b[p]);p=p+1 end;return table.concat(c)end
function R.blk()local n=R.u32();local t={};for i=1,n do t[i]=b[p];p=p+1 end;return t end
return R end'''

def generate_vm(opcodes,rng_seed=None,layout=None)->str:
    import random as _r
    rng=_r.Random(rng_seed if rng_seed is not None else _r.randint(0,2**31))
    used=set()
    def fresh(n=10):return _rn(rng,used,n)

    # Inner VM mutation
    imap={ph:fresh() for ph in _INNER_PH}
    inner=_INNER_VM
    inner=inner.replace('__INNER_LAYOUT__',_build_unpack(layout))

    # Build inner opcode table inline
    i_op_name=imap['__I_OP__']
    op_lines=[f'local {i_op_name}={{}}']
    for alias,val in opcodes.all().items():
        cid=_CANON_ID.get(opcodes.canonical(val),0)
        if cid>0:op_lines.append(f'{i_op_name}[{val}]={cid}')
    inner=inner.replace('__INNER_OP__',';'.join(op_lines))
    for ph,rn in imap.items():inner=inner.replace(ph,rn)

    # Strip all -- comments from inner VM
    import re
    inner=re.sub(r'--[^\n]*','',inner)
    # Collapse excess whitespace/newlines
    inner=re.sub(r'\n{2,}','\n',inner).strip()

    # Outer VM: references inner VM's EXE function name
    i_exe=imap['__I_EXE__']
    i_rdr=imap['__I_XOR__']  # reuse naming for outer reader placeholder

    # Build outer — it embeds the inner VM as a string literal
    # (double VM: outer decodes bytecode, reconstructs inner at runtime)
    outer=_OUTER_VM

    # Outer needs its own reader/loader (separate from inner)
    o_rdr_name=fresh();o_ldp_name=fresh()

    # Build reader + loader Lua (outer uses same format as inner but diff names)
    rdr_lua=(f'local function {o_rdr_name}(b)local p=1;local R={{}}\n'
             f'function R.u8()local v=b[p];p=p+1;return v end\n'
             f'function R.u32()local a,b2,c,d=b[p],b[p+1],b[p+2],b[p+3];p=p+4;return a+b2*256+c*65536+d*16777216 end\n'
             f'function R.f64()local B={{b[p],b[p+1],b[p+2],b[p+3],b[p+4],b[p+5],b[p+6],b[p+7]}};p=p+8;local s=B[8]>=128 and -1 or 1;local e2=(B[8]%128)*16+math.floor(B[7]/16);local m=(B[7]%16)*2^48+B[6]*2^40+B[5]*2^32+B[4]*2^24+B[3]*2^16+B[2]*2^8+B[1];if e2==0 then return s*math.ldexp(m,-1074)elseif e2==2047 then return s*(1/0)else return s*math.ldexp(m+2^52,e2-1075)end end\n'
             f'function R.str()local n=R.u32();local c={{}};for i=1,n do c[i]=string.char(b[p]);p=p+1 end;return table.concat(c)end\n'
             f'function R.blk()local n=R.u32();local t={{}};for i=1,n do t[i]=b[p];p=p+1 end;return t end\n'
             f'return R end')

    # Outer loader (proto deserializer) - same format as inner
    ldp_lua=_build_outer_ldp(o_ldp_name,o_rdr_name,imap)

    # Outer opcode table (same opcodes as inner, separate table name)
    o_op_name=fresh()
    outer_op_block=_build_op_table(o_op_name,opcodes)

    outer=outer.replace('__OUTER_OP__',outer_op_block)
    outer=outer.replace('__O_RDR__',o_rdr_name)
    outer=outer.replace('__O_LDP__',o_ldp_name)
    outer=outer.replace('__I_EXE__',i_exe)

    # Outer mutation
    omap={ph:fresh() for ph in _OUTER_PH}
    # Fix: __O_RDR__ and __O_LDP__ already substituted above
    for ph,rn in omap.items():outer=outer.replace(ph,rn)

    # Remove __O_INJECT__ block (simplify — outer just calls inner exe directly)
    import re as _re
    outer=_re.sub(r'local function \w+\(dec\).*?end\n','',outer,flags=_re.DOTALL)
    # Strip comments
    outer=_re.sub(r'--[^\n]*','',outer)
    outer=_re.sub(r'\n{2,}','\n',outer).strip()

    # Final output: inner VM + outer VM (outer calls inner's EXE)
    result=inner+'\n'+rdr_lua+'\n'+ldp_lua+'\n'+outer
    return result


def _build_outer_ldp(ldp_name,rdr_name,imap):
    ds=imap['__I_DS__'];dsc=imap['__I_DSC__']
    return(f'local function {ldp_name}(R)local p={{}};p.np=R.u8();p.va=R.u8()==1;local nc=R.u32();p.code={{}};for i=1,nc do p.code[i]=R.u32()end;local nk=R.u32();p.k={{}}\n'
           f'for i=1,nk do local t=R.u8()\n'
           f'if t==0 then p.k[i]=nil\n'
           f'elseif t==1 then p.k[i]=R.u8()~=0\n'
           f'elseif t==2 then p.k[i]=R.f64()\n'
           f'elseif t==3 then p.k[i]=R.str()\n'
           f'elseif t==4 then local sd=R.u8();local st=R.u8();local sk=R.u8();local n=R.u32();local e={{}};for j=1,n do e[j]=R.u8()end;p.k[i]={ds}(e,sd,st,sk)\n'
           f'elseif t==5 then local sd=R.u8();local st=R.u8();local sk=R.u8();local n=R.u32();local e={{}};for j=1,n do e[j]=R.u8()end;local nc2=R.u8();local ch={{}};for j=1,nc2 do local s=R.u32();local l=R.u32();ch[j]={{s,l}}end;local nn=R.u8();for j=1,nn do R.u32();R.u32()end;p.k[i]={dsc}(e,sd,st,sk,ch)\n'
           f'end end\n'
           f'local np=R.u32();p.pr={{}}\n'
           f'for i=1,np do local bl=R.blk();p.pr[i]={ldp_name}({rdr_name}(bl))end\n'
           f'return p end')
