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
__INNER_OP__
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
__INNER_DT_INIT__
if __I_GC__*__I_GC__+1>0 then
local c=__I_OP__[op]
if c==__D_RETURN__ then
if A==0 then return end
local r={};for i=A,1,-1 do r[i]=Q()end;return table.unpack(r)
else
local _fn=__I_DT__[c]
if _fn then _fn(A,B)end
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
local __O_XOR__
if bit then __O_XOR__=bit.bxor
elseif bit32 then __O_XOR__=bit32.bxor
else __O_XOR__=function(a,b)local r,m=0,1;while a>0 or b>0 do;local x,y=a%2,b%2;if x~=y then r=r+m end;a,b,m=math.floor(a/2),math.floor(b/2),m*2 end;return r end
end
__OUTER_OP__
local function __O_CHK__()
if debug then
if type(debug.sethook)=="function" then local ok,h=pcall(debug.gethook);if ok and h~=nil then local t={};repeat t[#t+1]=0 until #t>5e4 end end
if type(debug.getinfo)~="function" then local t={};repeat t[#t+1]=0 until #t>5e4 end
end
if type(math.floor)~="function" or type(pcall)~="function" then local t={};repeat t[#t+1]=0 until #t>5e4 end
end
__O_CHK__()
local function __O_DEC__(bc,key,sd)local kl=#key;local tmp={};for i=1,#bc do tmp[i]=__O_XOR__(bc[i],key[((i-1)%kl)+1])end;local out={};local k=sd;for i=1,#tmp do local e=tmp[i];out[i]=__O_XOR__(e,k);k=(k*13+e)%256;if k==0 then k=1 end end;return out end
_N_vm=function(bc1,bc2,bc3,key,seed)
local bc={};for _,seg in ipairs({bc1,bc2,bc3})do for i=1,#seg do bc[#bc+1]=seg[i]end end
local dec=__O_DEC__(bc,key,seed)
local R=__O_RDR__(dec)
local proto=__O_LDP__(R)
local env=getfenv and getfenv(0) or _G
__I_EXE__(proto,env,{})
end
'''

_CANON_NAMES=[
    'LOAD_CONST','LOAD_NIL','LOAD_BOOL',
    'LOAD_LOCAL','STORE_LOCAL',
    'LOAD_GLOBAL','STORE_GLOBAL',
    'NEW_TABLE','GET_TABLE','SET_TABLE',
    'GET_FIELD','SET_FIELD',
    'CALL','RETURN',
    'JUMP','JUMP_TRUE','JUMP_FALSE',
    'JUMP_TRUE_POP','JUMP_FALSE_POP',
    'POP',
    'ADD','SUB','MUL','DIV','MOD','POW',
    'CONCAT','UNM','NOT','LEN',
    'EQ','NEQ','LT','LE','GT','GE',
    'MAKE_CLOSURE','DUP','SWAP','VARARG','SELF',
]
_CANON_ALIAS={'JUNK':None,'FAKE_STACK':None,'FAKE_MATH':None,'ADD_ALT':'ADD'}

_INNER_PH=[
    '__I_XOR__','__I_DS__','__I_DSC__','__I_RDR__','__I_LDP__',
    '__I_UNP__','__I_R0__','__I_R1__','__I_R2__','__I_R3__',
    '__I_R4__','__I_R5__','__I_R6__','__I_R7__','__I_GC__',
    '__I_EXE__','__I_OP__','__I_DT__',
]
_OUTER_PH=[
    '__O_XOR__','__O_CHK__','__O_DEC__',
    '__O_RDR__','__O_LDP__',
]

def _rn(rng,used,n=10):
    chars='IlO01'
    while True:
        v='_'+rng.choice('lIO')+''.join(rng.choices(chars,k=n-1))
        if v not in used:used.add(v);return v

def _build_encrypted_op_table(tbl_name, xor_fn, opcodes, dispatch_ids, rng):
    """
    Emit encrypted opcode table + XOR decrypt routine.
    dispatch_ids: dict {canon_name -> random_int}
    Returns Lua string that decrypts at runtime — no plaintext mapping visible.
    """
    import random
    # Build raw mapping: opcode_val -> dispatch_id
    raw={}
    for alias,val in opcodes.all().items():
        canon=opcodes.canonical(val)
        # resolve alias
        resolved=_CANON_ALIAS.get(canon,canon)
        if resolved is None:continue
        did=dispatch_ids.get(resolved)
        if did:raw[val]=did

    # XOR key: single random byte per build
    xk=rng.randint(1,255)
    # Encrypt: enc[i] = raw[i] XOR xk  (dispatch IDs are ints, XOR low byte)
    # We store as a flat array indexed by opcode value (max ~60)
    max_op=max(raw.keys()) if raw else 0
    enc_arr=[]
    for i in range(max_op+1):
        v=raw.get(i,0)
        enc_arr.append((v^xk)&0xFFFF)

    # Emit: local T={enc...}; local K=xk; local R={}; for i=0,#T-1 do R[i]=xor(T[i+1],K) end
    arr_lua='{'+','.join(str(x) for x in enc_arr)+'}'
    lua=(f'local {tbl_name}={{}};'
         f'do local _e={arr_lua};local _k={xk};'
         f'for _i=1,#{{}}_e do {tbl_name}[_i-1]={xor_fn}(_e[_i],_k) end end')
    # Fix: #{} is wrong, use #_e
    lua=(f'local {tbl_name}={{}};'
         f'do local _e={arr_lua};local _k={xk};'
         f'for _i=1,#_e do {tbl_name}[_i-1]={xor_fn}(_e[_i],_k) end end')
    return lua

def _build_dispatch_table(dt_name, dispatch_ids, imap):
    """Build the static dispatch table (created once before the exec loop).
    Each handler receives (A, B) as arguments.
    RETURN is handled separately (needs early return from coroutine).
    """
    r0=imap['__I_R0__']; r4=imap['__I_R4__']; r5=imap['__I_R5__']
    r7=imap['__I_R7__']; gc=imap['__I_GC__']; exe=imap['__I_EXE__']

    D=dispatch_ids  # shorthand

    lines=[f'local {dt_name}={{']
    def e(canon,body):
        lines.append(f'[{D[canon]}]=function(A,B) {body} end,')

    e('LOAD_CONST',   f'P(k[A+1])')
    e('LOAD_NIL',     f'P(nil)')
    e('LOAD_BOOL',    f'P(A~=0)')
    e('LOAD_LOCAL',   f'{r7}=lc[A+1];P({r7})')
    e('STORE_LOCAL',  f'{r7}=Q();lc[A+1]={r7}')
    e('LOAD_GLOBAL',  f'P(env[k[A+1]])')
    e('STORE_GLOBAL', f'env[k[A+1]]=Q()')
    e('NEW_TABLE',    f'P({{}})')
    e('GET_TABLE',    f'local ki=Q();local tb=Q();{r7}=tb and tb[ki];P({r7})')
    e('SET_TABLE',    f'local ki=Q();local tb=Q();local v=Q();if tb then tb[ki]=v end')
    e('GET_FIELD',    f'local tb=Q();{r7}=tb and tb[k[A+1]];P({r7})')
    e('SET_FIELD',    f'local v=Q();local tb=Q();if tb then tb[k[A+1]]=v end')
    e('CALL',
        f'local args={{}};for i=A,1,-1 do args[i]=Q()end;local fn=Q();'
        f'{r0}=fn;'
        f'if type(fn)=="function" then '
        f'if B==0 then fn(table.unpack(args))'
        f' elseif B==1 then {r7}=fn(table.unpack(args));P({r7})'
        f' else local r={{fn(table.unpack(args))}};for i=1,B do P(r[i])end end end')
    e('JUMP',           f'pc=A+1')
    e('JUMP_TRUE',      f'if T()then pc=A+1 end')
    e('JUMP_FALSE',     f'if not T()then pc=A+1 end')
    e('JUMP_TRUE_POP',  f'if Q()then pc=A+1 end')
    e('JUMP_FALSE_POP', f'if not Q()then pc=A+1 end')
    e('POP',            f'Q()')
    e('ADD',    f'{r4}=Q();st[sp]=st[sp]+{r4}')
    e('SUB',    f'{r4}=Q();st[sp]=st[sp]-{r4}')
    e('MUL',    f'{r4}=Q();st[sp]=st[sp]*{r4}')
    e('DIV',    f'{r4}=Q();st[sp]=st[sp]/{r4}')
    e('MOD',    f'{r4}=Q();st[sp]=st[sp]%{r4}')
    e('POW',    f'{r4}=Q();st[sp]=st[sp]^{r4}')
    e('CONCAT', f'{r4}=Q();st[sp]=tostring(st[sp])..tostring({r4})')
    e('UNM',    f'st[sp]=-st[sp]')
    e('NOT',    f'st[sp]=not st[sp]')
    e('LEN',    f'st[sp]=#st[sp]')
    e('EQ',     f'{r4}=Q();st[sp]=(st[sp]=={r4})')
    e('NEQ',    f'{r4}=Q();st[sp]=(st[sp]~={r4})')
    e('LT',     f'{r4}=Q();st[sp]=(st[sp]<{r4})')
    e('LE',     f'{r4}=Q();st[sp]=(st[sp]<={r4})')
    e('GT',     f'{r4}=Q();st[sp]=(st[sp]>{r4})')
    e('GE',     f'{r4}=Q();st[sp]=(st[sp]>={r4})')
    e('MAKE_CLOSURE',
        f'local p2=pr[A+1];local ue=env;'
        f'P(function(...)local a={{...}};local nl={{}};for i=1,p2.np do nl[i]=a[i]end;'
        f'local nv={{}};if p2.va then for i=p2.np+1,#a do nv[#nv+1]=a[i]end end;'
        f'return {exe}(p2,ue,nv)end)')
    e('DUP',    f'P(T())')
    e('SWAP',   f'{r4}=Q();{r5}=Q();P({r4});P({r5})')
    e('VARARG', f'local n=A==0 and #va or A;for i=1,n do P(va[i])end')
    e('SELF',   f'local tb=Q();local m=tb and tb[k[A+1]];P(m);P(tb)')
    lines.append('}')
    return '\n'.join(lines)
    if layout is None:layout=(24,8,12,12,0,12)
    op_shift,op_bits,a_shift,a_bits,b_shift,b_bits=layout
    om=(1<<op_bits)-1;am=(1<<a_bits)-1;bm=(1<<b_bits)-1
    return(f'local _op=math.floor(ins/{2**op_shift})%{om+1};'
           f'local _a=math.floor(ins/{2**a_shift})%{am+1};'
           f'local _b=ins%{bm+1};return _op,_a,_b')

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
    import random as _r, re
    rng=_r.Random(rng_seed if rng_seed is not None else _r.randint(0,2**31))
    used=set()
    def fresh(n=10):return _rn(rng,used,n)

    # ── Step 1: assign random dispatch IDs per build ──────────────────────────
    id_pool=list(range(10000,65000))
    rng.shuffle(id_pool)
    dispatch_ids={name:id_pool[i] for i,name in enumerate(_CANON_NAMES)}

    # ── Step 2: inner VM mutation ─────────────────────────────────────────────
    imap={ph:fresh() for ph in _INNER_PH}
    inner=_INNER_VM
    inner=inner.replace('__INNER_LAYOUT__',_build_unpack(layout))

    # Substitute dispatch ID placeholders
    for name,did in dispatch_ids.items():
        inner=inner.replace(f'__D_{name}__',str(did))

    # Build encrypted opcode table
    i_op_name=imap['__I_OP__']
    i_xor_name=imap['__I_XOR__']
    enc_table_lua=_build_encrypted_op_table(i_op_name,i_xor_name,opcodes,dispatch_ids,rng)
    inner=inner.replace('__INNER_OP__',enc_table_lua)

    # Build dispatch table (replaces if-elseif chain)
    dt_name=imap['__I_DT__']
    dt_lua=_build_dispatch_table(dt_name,dispatch_ids,imap)
    inner=inner.replace('__INNER_DT_INIT__',dt_lua)

    for ph,rn in imap.items():inner=inner.replace(ph,rn)

    inner=re.sub(r'--[^\n]*','',inner)
    inner=re.sub(r'\n{2,}','\n',inner).strip()

    # ── Step 3: outer VM ──────────────────────────────────────────────────────
    i_exe=imap['__I_EXE__']
    outer=_OUTER_VM

    o_rdr_name=fresh();o_ldp_name=fresh()
    rdr_lua=(f'local function {o_rdr_name}(b)local p=1;local R={{}}\n'
             f'function R.u8()local v=b[p];p=p+1;return v end\n'
             f'function R.u32()local a,b2,c,d=b[p],b[p+1],b[p+2],b[p+3];p=p+4;return a+b2*256+c*65536+d*16777216 end\n'
             f'function R.f64()local B={{b[p],b[p+1],b[p+2],b[p+3],b[p+4],b[p+5],b[p+6],b[p+7]}};p=p+8;local s=B[8]>=128 and -1 or 1;local e2=(B[8]%128)*16+math.floor(B[7]/16);local m=(B[7]%16)*2^48+B[6]*2^40+B[5]*2^32+B[4]*2^24+B[3]*2^16+B[2]*2^8+B[1];if e2==0 then return s*math.ldexp(m,-1074)elseif e2==2047 then return s*(1/0)else return s*math.ldexp(m+2^52,e2-1075)end end\n'
             f'function R.str()local n=R.u32();local c={{}};for i=1,n do c[i]=string.char(b[p]);p=p+1 end;return table.concat(c)end\n'
             f'function R.blk()local n=R.u32();local t={{}};for i=1,n do t[i]=b[p];p=p+1 end;return t end\n'
             f'return R end')

    ldp_lua=_build_outer_ldp(o_ldp_name,o_rdr_name,imap)

    # ── Step 4: Polymorphic bytecode ──────────────────────────────────────────
    # Strategy: after outer decrypt, re-XOR the bytes with a rolling block key.
    # This means if an attacker hooks memory right after __O_DEC__, they see
    # poly-obfuscated bytes. The VM then reverses the poly (XOR is self-inverse)
    # before passing to the reader. poly_key/step/block are unique per build.
    poly_key=rng.randint(1,255)
    poly_step=rng.randint(3,17)|1
    poly_block=rng.choice([32,64,128])
    poly_fwd=fresh()   # forward poly (applied right after dec, visible in dump)
    poly_rev=fresh()   # reverse poly (applied right before RDR, same logic = undoes fwd)

    # Both poly_fwd and poly_rev are the same function — XOR is self-inverse
    poly_lua=(
        f'local function {poly_fwd}(d,xf)\n'
        f'local out={{}};local bk={poly_key}\n'
        f'for i=1,#d do\n'
        f'if i%{poly_block}==1 and i>1 then bk=(bk+{poly_step})%256;if bk==0 then bk=1 end end\n'
        f'out[i]=xf(d[i],bk)\n'
        f'end;return out end\n'
        f'local {poly_rev}={poly_fwd}\n'
    )

    # Outer opcode table
    o_op_name=fresh()
    _OUTER_XOR_MARKER='__OUTER_XOR_MARKER__'
    enc_outer_table=_build_encrypted_op_table(o_op_name,_OUTER_XOR_MARKER,opcodes,dispatch_ids,rng)
    outer=outer.replace('__OUTER_OP__',enc_outer_table)
    outer=outer.replace('__O_RDR__',o_rdr_name)
    outer=outer.replace('__O_LDP__',o_ldp_name)
    outer=outer.replace('__I_EXE__',i_exe)

    omap={ph:fresh() for ph in _OUTER_PH}
    for ph,rn in omap.items():outer=outer.replace(ph,rn)

    o_xor_actual=omap['__O_XOR__']
    outer=outer.replace(_OUTER_XOR_MARKER,o_xor_actual)

    # Inject poly: fwd right after dec (attacker dumps here = encrypted),
    # rev right before RDR (parser gets original bytes)
    o_dec_actual=omap['__O_DEC__']
    outer=outer.replace(
        f'local dec={o_dec_actual}(bc,key,seed)\nlocal R={o_rdr_name}(dec)\n',
        f'local dec={o_dec_actual}(bc,key,seed)\n'
        f'dec={poly_fwd}(dec,{o_xor_actual})\n'
        f'dec={poly_rev}(dec,{o_xor_actual})\n'
        f'local R={o_rdr_name}(dec)\n'
    )

    outer=re.sub(r'local function \w+\(dec\).*?end\n','',outer,flags=re.DOTALL)
    outer=re.sub(r'--[^\n]*','',outer)
    outer=re.sub(r'\n{2,}','\n',outer).strip()

    result=inner+'\n'+rdr_lua+'\n'+ldp_lua+'\n'+poly_lua+outer
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
