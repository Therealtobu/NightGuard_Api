import sys,os;sys.path.insert(0,os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
"""NightGuard V3 — Register VM Generator
Full register-based VM (no stack). Each instruction: op|A|B|C or op|A|Bx.
RK(x): x&0x100 → K[x&0xFF], else R[x].
"""
import random,re

# ─────────────────────────────────────────────────────────────────────────────
# INNER VM template — placeholders: __IX_* → random names per build
# ─────────────────────────────────────────────────────────────────────────────
_INNER = r"""
local __IX_XOR__
if bit then __IX_XOR__=bit.bxor
elseif bit32 then __IX_XOR__=bit32.bxor
else __IX_XOR__=function(a,b)local r,m=0,1;while a>0 or b>0 do local x,y=a%2,b%2;if x~=y then r=r+m end;a,b,m=math.floor(a/2),math.floor(b/2),m*2 end;return r end
end
local function __IX_DS__(e,sd,st,sk)
  local d={};for i=1,#e do d[i]=(e[i]-(sk or 0)*i%256+256)%256 end
  local k=sd;local c={}
  for i=1,#d do c[i]=string.char(__IX_XOR__(d[i],k));k=(k*st+d[i])%256;if k==0 then k=1 end end
  return table.concat(c)
end
local function __IX_DSC__(e,sd,st,sk,chunks,order)
  local sorted={}
  if order then for i=1,#order do sorted[order[i]+1]=chunks[i] end
  else sorted=chunks end
  local raw={};local ci=1
  for i=1,#sorted do local ch=sorted[i];local s,l=ch[1],ch[2];for j=s+1,s+l do raw[ci]=e[j];ci=ci+1 end end
  return __IX_DS__(raw,sd,st,sk)
end
local function __IX_RDR__(b)
  local p=1;local R={}
  function R.u8()local v=b[p];p=p+1;return v end
  function R.u32()local a,b2,c,d=b[p],b[p+1],b[p+2],b[p+3];p=p+4;return a+b2*256+c*65536+d*16777216 end
  function R.f64()local B={b[p],b[p+1],b[p+2],b[p+3],b[p+4],b[p+5],b[p+6],b[p+7]};p=p+8
    local s=B[8]>=128 and -1 or 1;local e2=(B[8]%128)*16+math.floor(B[7]/16)
    local m=(B[7]%16)*2^48+B[6]*2^40+B[5]*2^32+B[4]*2^24+B[3]*2^16+B[2]*2^8+B[1]
    if e2==0 then return s*math.ldexp(m,-1074)
    elseif e2==2047 then return s*(1/0)
    else return s*math.ldexp(m+2^52,e2-1075) end
  end
  function R.str()local n=R.u32();local c={};for i=1,n do c[i]=string.char(b[p]);p=p+1 end;return table.concat(c) end
  function R.blk()local n=R.u32();local t={};for i=1,n do t[i]=b[p];p=p+1 end;return t end
  return R
end
local function __IX_LDP__(R)
  local p={};p.np=R.u8();p.va=R.u8()==1;p.mr=R.u8()
  local nc=R.u32();p.code={};for i=1,nc do p.code[i]=R.u32() end
  local nk=R.u32();p.k={}
  for i=1,nk do
    local t=R.u8()
    if t==0 then p.k[i]=nil
    elseif t==1 then p.k[i]=R.u8()~=0
    elseif t==2 then p.k[i]=R.f64()
    elseif t==3 then p.k[i]=R.str()
    elseif t==4 then
      local sd=R.u8();local st=R.u8();local sk=R.u8()
      local n=R.u32();local e={};for j=1,n do e[j]=R.u8() end
      p.k[i]=__IX_DS__(e,sd,st,sk)
    elseif t==5 then
      local sd=R.u8();local st=R.u8();local sk=R.u8()
      local n=R.u32();local e={};for j=1,n do e[j]=R.u8() end
      local nc2=R.u8();local ch={};for j=1,nc2 do local s=R.u32();local l=R.u32();ch[j]={s,l} end
      local nn=R.u8();for j=1,nn do R.u32();R.u32() end
      local no=R.u8();local ord={};for j=1,no do ord[j]=R.u8() end
      p.k[i]=__IX_DSC__(e,sd,st,sk,ch,ord)
    end
  end
  local np=R.u32();p.pr={}
  for i=1,np do local bl=R.blk();p.pr[i]=__IX_LDP__(__IX_RDR__(bl)) end
  return p
end
__IX_OPENC__
local function __IX_EXE__(proto,env,vararg)
  local R={};for i=0,proto.mr+4 do R[i]=nil end
  local K=proto.k;local P=proto.pr;local CD=proto.code
  local pc=1;local DT=__IX_DT__
  local __IX_T1__,__IX_T2__,__IX_T3__=0,0,0
  local function RK(x) if x>=256 then return K[(x-256)+1] else return R[x] end end
  while pc<=#CD do
    local ins=CD[pc];pc=pc+1
    local op=ins&0xFF;local a=(ins>>8)&0xFF
    local b=(ins>>16)&0xFF;local c=(ins>>24)&0xFF
    local bx=(ins>>16)&0xFFFF;local sbx=bx-32767
    __IX_T1__=__IX_T2__;__IX_T2__=__IX_T3__;__IX_T3__=op
    local nm=__IX_OP__[op]
    if nm==nil then
    elseif nm==-1 then
      local n=b-1;if n<0 then n=#vararg end
      local rv={};if n>0 then for i=1,n do rv[i]=vararg[i] end end
      if b==1 then return end
      return table.unpack(rv,1,b-1)
    else
      local h=DT[nm];if h then h(a,b,c,bx,sbx) end
    end
  end
end
"""

# ─────────────────────────────────────────────────────────────────────────────
# OUTER VM — decrypts inner and runs it
# ─────────────────────────────────────────────────────────────────────────────
_OUTER = r"""
local _N_vm
local __OX_XOR__
if bit then __OX_XOR__=bit.bxor
elseif bit32 then __OX_XOR__=bit32.bxor
else __OX_XOR__=function(a,b)local r,m=0,1;while a>0 or b>0 do local x,y=a%2,b%2;if x~=y then r=r+m end;a,b,m=math.floor(a/2),math.floor(b/2),m*2 end;return r end
end
local function __OX_CHK__()
  if debug then
    if type(debug.sethook)=="function" then
      local ok,h=pcall(debug.gethook)
      if ok and h~=nil then local t={};repeat t[#t+1]=0 until #t>5e4 end
    end
    if type(debug.getinfo)~="function" then local t={};repeat t[#t+1]=0 until #t>5e4 end
  end
  if type(math.floor)~="function" or type(pcall)~="function" then local t={};repeat t[#t+1]=0 until #t>5e4 end
end
__OX_CHK__()
local function __OX_DEC__(bc,key,sd)
  local kl=#key;local tmp={}
  for i=1,#bc do tmp[i]=__OX_XOR__(bc[i],key[((i-1)%kl)+1]) end
  local out={};local k=sd
  for i=1,#tmp do local e=tmp[i];out[i]=__OX_XOR__(e,k);k=(k*13+e)%256;if k==0 then k=1 end end
  return out
end
local function __OX_RDR__(b)
  local p=1;local R={}
  function R.u8()local v=b[p];p=p+1;return v end
  function R.u32()local a,b2,c,d=b[p],b[p+1],b[p+2],b[p+3];p=p+4;return a+b2*256+c*65536+d*16777216 end
  function R.f64()local B={b[p],b[p+1],b[p+2],b[p+3],b[p+4],b[p+5],b[p+6],b[p+7]};p=p+8
    local s=B[8]>=128 and -1 or 1;local e2=(B[8]%128)*16+math.floor(B[7]/16)
    local m=(B[7]%16)*2^48+B[6]*2^40+B[5]*2^32+B[4]*2^24+B[3]*2^16+B[2]*2^8+B[1]
    if e2==0 then return s*math.ldexp(m,-1074)
    elseif e2==2047 then return s*(1/0)
    else return s*math.ldexp(m+2^52,e2-1075) end
  end
  function R.str()local n=R.u32();local c={};for i=1,n do c[i]=string.char(b[p]);p=p+1 end;return table.concat(c) end
  function R.blk()local n=R.u32();local t={};for i=1,n do t[i]=b[p];p=p+1 end;return t end
  return R
end
local function __OX_LDP__(R)
  local p={};p.np=R.u8();p.va=R.u8()==1;p.mr=R.u8()
  local nc=R.u32();p.code={};for i=1,nc do p.code[i]=R.u32() end
  local nk=R.u32();p.k={}
  for i=1,nk do
    local t=R.u8()
    if t==0 then p.k[i]=nil
    elseif t==1 then p.k[i]=R.u8()~=0
    elseif t==2 then p.k[i]=R.f64()
    elseif t==3 then p.k[i]=R.str()
    elseif t==4 then
      local sd=R.u8();local st=R.u8();local sk=R.u8()
      local n=R.u32();local e={};for j=1,n do e[j]=R.u8() end
      p.k[i]=__IX_DS_NAME__(e,sd,st,sk)
    elseif t==5 then
      local sd=R.u8();local st=R.u8();local sk=R.u8()
      local n=R.u32();local e={};for j=1,n do e[j]=R.u8() end
      local nc2=R.u8();local ch={};for j=1,nc2 do local s=R.u32();local l=R.u32();ch[j]={s,l} end
      local nn=R.u8();for j=1,nn do R.u32();R.u32() end
      local no=R.u8();local ord={};for j=1,no do ord[j]=R.u8() end
      p.k[i]=__IX_DSC_NAME__(e,sd,st,sk,ch,ord)
    end
  end
  local np=R.u32();p.pr={}
  for i=1,np do local bl=R.blk();p.pr[i]=__OX_LDP__(bl) end
  return p
end
_N_vm=function(bc1,bc2,bc3,key,seed)
  local bc={};for _,seg in ipairs({bc1,bc2,bc3}) do for i=1,#seg do bc[#bc+1]=seg[i] end end
  local dec=__OX_DEC__(bc,key,seed)
  local R=__OX_RDR__(dec)
  local proto=__OX_LDP__(R)
  local env=getfenv and getfenv(0) or _G
  __IX_EXE_NAME__(proto,env,{})
end
"""

_INNER_PH=['__IX_XOR__','__IX_DS__','__IX_DSC__','__IX_RDR__','__IX_LDP__',
           '__IX_OPENC__','__IX_EXE__','__IX_OP__','__IX_DT__','__IX_T1__','__IX_T2__','__IX_T3__']
_OUTER_PH=['__OX_XOR__','__OX_CHK__','__OX_DEC__','__OX_RDR__','__OX_LDP__']

# Canonical op names VM needs to handle (matches opcodes.py _DEFS)
_HANDLED = [
    'LOADK','LOADNIL','LOADBOOL','MOVE',
    'GETGLOBAL','SETGLOBAL',
    'NEWTABLE','GETTABLE','SETTABLE','SELF',
    'ADD','SUB','MUL','DIV','MOD','POW',
    'UNM','NOT','LEN','CONCAT',
    'JMP','EQ','LT','LE','TEST','TESTSET',
    'CALL','TAILCALL','RETURN','VARARG',
    'CLOSURE','FORPREP','FORLOOP','TFORLOOP','SETLIST',
]

def _fresh(rng,used):
    chars='lIO01'
    while True:
        v='_'+rng.choice('lIO')+''.join(rng.choices(chars,k=rng.randint(8,13)))
        if v not in used: used.add(v); return v

def _build_op_table(tbl,xor_fn,opcodes,dispatch_map,rng):
    """Emit encrypted op→dispatch_id table decoded at runtime."""
    raw={}
    for nm in _HANDLED:
        try:
            oid=opcodes.id(nm)
            raw[oid]=dispatch_map[nm]
        except KeyError: pass
    if not raw: return f'local {tbl}={{}}'
    xk=rng.randint(1,255)
    mx=max(raw)
    enc=[(raw.get(i,0)^xk)&0xFFFF for i in range(mx+1)]
    arr='{'+','.join(str(x) for x in enc)+'}'
    return (f'local {tbl}={{}};do local _e={arr};local _k={xk};'
            f'for _i=1,#_e do {tbl}[_i-1]={xor_fn}(_e[_i],_k) end end')

def _build_dispatch(dt,dm,imap,opcodes):
    """Build register VM dispatch table. Each handler: function(a,b,c,bx,sbx)."""
    exe=imap['__IX_EXE__']
    lines=[f'local {dt}={{']
    def h(nm,body): lines.append(f'[{dm[nm]}]=function(a,b,c,bx,sbx) {body} end,')

    h('LOADK',       'R[a]=K[bx+1]')
    h('LOADNIL',     'for i=a,a+b do R[i]=nil end')
    h('LOADBOOL',    'R[a]=(b~=0);if c~=0 then pc=pc+1 end')
    h('MOVE',        'R[a]=R[b]')
    h('GETGLOBAL',   'R[a]=env[K[bx+1]]')
    h('SETGLOBAL',   'env[K[bx+1]]=R[a]')
    h('NEWTABLE',    'R[a]={}')
    h('GETTABLE',    'R[a]=R[b][RK(c)]')
    h('SETTABLE',    'R[a][RK(b)]=RK(c)')
    h('SELF',        'R[a+1]=R[b];R[a]=R[b][RK(c)]')
    h('ADD',         'R[a]=RK(b)+RK(c)')
    h('SUB',         'R[a]=RK(b)-RK(c)')
    h('MUL',         'R[a]=RK(b)*RK(c)')
    h('DIV',         'R[a]=RK(b)/RK(c)')
    h('MOD',         'R[a]=RK(b)%RK(c)')
    h('POW',         'R[a]=RK(b)^RK(c)')
    h('UNM',         'R[a]=-R[b]')
    h('NOT',         'R[a]=not R[b]')
    h('LEN',         'R[a]=#R[b]')
    h('CONCAT',      'local s=tostring(R[b]);for i=b+1,c do s=s..tostring(R[i]) end;R[a]=s')
    h('JMP',         'pc=pc+sbx')
    h('EQ',          'if (RK(b)==RK(c))~=(a~=0) then pc=pc+1 end')
    h('LT',          'if (RK(b)<RK(c))~=(a~=0) then pc=pc+1 end')
    h('LE',          'if (RK(b)<=RK(c))~=(a~=0) then pc=pc+1 end')
    h('TEST',        'if (not not R[a])~=(c~=0) then pc=pc+1 end')
    h('TESTSET',     'if (not not R[b])~=(c~=0) then pc=pc+1 else R[a]=R[b] end')
    h('CALL',
        'local fn=R[a];local args={};local na=b-1;'
        'if na<0 then na=0 end;'  # vararg case simplified
        'for i=1,na do args[i]=R[a+i] end;'
        'local nr=c-1;'
        'if nr<0 then nr=0 end;'
        'local ret={fn(table.unpack(args))};'
        'for i=0,nr-1 do R[a+i]=ret[i+1] end')
    h('TAILCALL',
        'local fn=R[a];local args={};for i=1,b-1 do args[i]=R[a+i] end;'
        'return fn(table.unpack(args))')
    h('VARARG',
        'local n=b-1;if n<0 then n=#vararg end;'
        'for i=0,n-1 do R[a+i]=vararg[i+1] end')
    h('CLOSURE',
        f'local pp=P[bx+1];'
        f'R[a]=function(...)local va={{...}};local lva={{}};'
        f'for i=1,pp.np do lva[i]=va[i] end;'
        f'local vargs={{}};if pp.va then for i=pp.np+1,#va do vargs[#vargs+1]=va[i] end end;'
        f'return {exe}(pp,env,vargs) end')
    h('FORPREP',
        'R[a]=R[a]-R[a+2];pc=pc+sbx')
    h('FORLOOP',
        'R[a]=R[a]+R[a+2];'
        'if R[a+2]>0 and R[a]<=R[a+1] then R[a+3]=R[a];pc=pc+sbx '
        'elseif R[a+2]<=0 and R[a]>=R[a+1] then R[a+3]=R[a];pc=pc+sbx end')
    h('TFORLOOP',
        'local fn=R[a];local st=R[a+1];local ct=R[a+2];'
        'local res={fn(st,ct)};'
        'if res[1]~=nil then R[a+2]=res[1];for i=1,c do R[a+2+i]=res[i] end '
        'else pc=pc+1 end')
    h('SETLIST',
        'for i=1,b do R[a][i]=R[a+i] end')

    lines.append('}')
    return '\n'.join(lines)

def generate_vm(opcodes,rng_seed=None,**_)->str:
    rng=random.Random(rng_seed if rng_seed is not None else random.randint(0,2**31))
    used=set()
    def fresh(): return _fresh(rng,used)

    # Assign random dispatch IDs per build (large ints, not sequential)
    pool=list(range(10000,65000)); rng.shuffle(pool)
    dm={nm:pool[i] for i,nm in enumerate(_HANDLED)}
    # RETURN gets special ID -1 (handled inline in EXE)

    # Inner VM name substitution
    imap={ph:fresh() for ph in _INNER_PH}
    inner=_INNER

    # Build encrypted opcode table
    enc_tbl=_build_op_table(imap['__IX_OP__'],imap['__IX_XOR__'],opcodes,dm,rng)
    inner=inner.replace('__IX_OPENC__',enc_tbl)

    # Build dispatch table — do BEFORE imap substitution so __IX_DT__ still a placeholder
    dt_lua=_build_dispatch('__IX_DT__',dm,imap,opcodes)
    # Replace DT placeholder in inner: embed full DT definition
    inner=inner.replace('local DT=__IX_DT__',dt_lua+'\n  local DT=__IX_DT__')

    # RETURN special case: op id=-1 in OP table, handled inline
    # Add RETURN to OP table as -1
    ret_id=opcodes.id('RETURN')
    inner=inner.replace(
        f'local nm=__IX_OP__[op]',
        f'local nm=__IX_OP__[op];if op=={ret_id} then nm=-1 end'
    )

    for ph,rn in imap.items(): inner=inner.replace(ph,rn)
    inner=re.sub(r'--[^\n]*','',inner)
    inner=re.sub(r'\n{3,}','\n\n',inner).strip()

    # Outer VM
    outer=_OUTER
    omap={ph:fresh() for ph in _OUTER_PH}
    for ph,rn in omap.items(): outer=outer.replace(ph,rn)
    # Inject inner function names into outer's LDP
    outer=outer.replace('__IX_DS_NAME__', imap['__IX_DS__'])
    outer=outer.replace('__IX_DSC_NAME__',imap['__IX_DSC__'])
    outer=outer.replace('__IX_EXE_NAME__',imap['__IX_EXE__'])
    # Outer LDP calls itself recursively — fix the __OX_LDP__ self-ref
    outer=outer.replace(
        f'p.pr[i]={omap["__OX_LDP__"]}(bl)',
        f'p.pr[i]={omap["__OX_LDP__"]}({omap["__OX_RDR__"]}(bl))'
    )
    outer=re.sub(r'--[^\n]*','',outer)
    outer=re.sub(r'\n{3,}','\n\n',outer).strip()

    return inner+'\n'+outer
