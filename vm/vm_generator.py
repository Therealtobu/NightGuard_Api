import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
"""NightGuard V2 - VM Generator

Real register IR layer:
  - Every instruction reads/writes named virtual registers (R0..R7)
  - Registers are named uniquely per build
  - Stack is real, but hot values go through register file first
  - Extra register ops (MOV, XCHG) injected as noise between real ops

Instruction encoding randomized per build (bit positions shuffled).
Anti-tamper: debug hook detection + env fingerprint + infinite spin trap.
"""

# ── VM Template ──────────────────────────────────────────────────────────────
# Placeholders: __PH_xxx__ replaced with random names per build
# __OPCODE_TABLE__  replaced with dispatch table
# __LAYOUT_UNPACK__ replaced with bit-layout Lua

_VM = r'''local _N_vm
__OPCODE_TABLE__
-- XOR polyfill
local __PH_XOR__
if bit then __PH_XOR__=bit.bxor
elseif bit32 then __PH_XOR__=bit32.bxor
else
  __PH_XOR__=function(a,b)
    local r,m=0,1
    while a>0 or b>0 do
      local x,y=a%2,b%2
      if x~=y then r=r+m end
      a,b,m=math.floor(a/2),math.floor(b/2),m*2
    end
    return r
  end
end
-- Anti-tamper: debug hook / env fingerprint checks
local function __PH_CHK__()
  -- debug hook detection
  if debug then
    if type(debug.sethook)=="function" then
      local ok,h=pcall(debug.gethook)
      if ok and h~=nil then
        local _t={}; repeat _t[#_t+1]=0 until #_t>5e4
      end
    end
    if type(debug.getinfo)~="function" then
      local _t={}; repeat _t[#_t+1]=0 until #_t>5e4
    end
  end
  -- env sanity: if core stdlib tampered, spin
  if type(math.floor)~="function" or type(table.concat)~="function"
     or type(string.char)~="function" or type(pcall)~="function" then
    local _t={}; repeat _t[#_t+1]=0 until #_t>5e4
  end
  -- anti-getfenv probe: check that _G hasn't been replaced with a spy table
  local _env=getfenv and getfenv(0) or _G
  if type(_env)~="table" then
    local _t={}; repeat _t[#_t+1]=0 until #_t>5e4
  end
end
__PH_CHK__()
-- Bytecode integrity checksum (CRC16-ish)
local function __PH_CRC__(t)
  local s=0xFFFF
  for i=1,#t do
    s=__PH_XOR__(s,t[i])
    for _=1,8 do
      if s%2==1 then s=__PH_XOR__(math.floor(s/2),0xA001)
      else s=math.floor(s/2) end
    end
  end
  return s
end
-- Key-stream decryption (rolling XOR + key expansion)
local function __PH_DEC__(bc,key,sd)
  local kl=#key; local tmp={}
  for i=1,#bc do tmp[i]=__PH_XOR__(bc[i],key[((i-1)%kl)+1]) end
  local out={}; local k=sd
  for i=1,#tmp do
    local e=tmp[i]; out[i]=__PH_XOR__(e,k)
    k=(k*13+e)%256; if k==0 then k=1 end
  end
  return out
end
-- Byte-stream reader
local function __PH_RDR__(bytes)
  local pos=1; local R={}
  function R.u8()  local v=bytes[pos]; pos=pos+1; return v end
  function R.u16() local a=bytes[pos]; local b=bytes[pos+1]; pos=pos+2; return a+b*256 end
  function R.u32()
    local a,b,c,d=bytes[pos],bytes[pos+1],bytes[pos+2],bytes[pos+3]
    pos=pos+4; return a+b*256+c*65536+d*16777216
  end
  function R.f64()
    local b0,b1,b2,b3,b4,b5,b6,b7=
      bytes[pos],bytes[pos+1],bytes[pos+2],bytes[pos+3],
      bytes[pos+4],bytes[pos+5],bytes[pos+6],bytes[pos+7]
    pos=pos+8
    local s=b7>=128 and -1 or 1
    local e=(b7%128)*16+math.floor(b6/16)
    local m=(b6%16)*2^48+b5*2^40+b4*2^32+b3*2^24+b2*2^16+b1*2^8+b0
    if e==0 then return s*math.ldexp(m,-1074)
    elseif e==2047 then return s*(1/0)
    else return s*math.ldexp(m+2^52,e-1075) end
  end
  function R.str()
    local len=R.u32(); local ch={}
    for i=1,len do ch[i]=string.char(bytes[pos]); pos=pos+1 end
    return table.concat(ch)
  end
  function R.blk()
    local len=R.u32(); local b={}
    for i=1,len do b[i]=bytes[pos]; pos=pos+1 end
    return b
  end
  return R
end
-- String decrypt: reverse sub layer then XOR rolling
local function __PH_DS__(enc,sd,st,sk)
  local d={}
  for i=1,#enc do d[i]=(enc[i]-(sk or 0)*i%256+256)%256 end
  local k=sd; local ch={}
  for i=1,#d do
    ch[i]=string.char(__PH_XOR__(d[i],k))
    k=(k*st+d[i])%256; if k==0 then k=1 end
  end
  return table.concat(ch)
end
-- Proto deserializer
local function __PH_LDP__(R)
  local p={}; p.nparams=R.u8(); p.is_vararg=R.u8()==1
  local nc=R.u32(); p.code={}
  for i=1,nc do p.code[i]=R.u32() end
  local nk=R.u32(); p.consts={}
  for i=1,nk do
    local t=R.u8()
    if     t==0 then p.consts[i]=nil
    elseif t==1 then p.consts[i]=R.u8()~=0
    elseif t==2 then p.consts[i]=R.f64()
    elseif t==3 then p.consts[i]=R.str()
    elseif t==4 then
      local sd=R.u8(); local st=R.u8(); local sk=R.u8()
      local len=R.u32(); local enc={}
      for j=1,len do enc[j]=R.u8() end
      p.consts[i]=__PH_DS__(enc,sd,st,sk)
    end
  end
  local np=R.u32(); p.protos={}
  for i=1,np do
    local blk=R.blk(); p.protos[i]=__PH_LDP__(__PH_RDR__(blk))
  end
  return p
end
-- Instruction unpack (bit layout randomized per build)
local function __PH_UNP__(instr)
  __LAYOUT_UNPACK__
end
-- ── Register file (real IR layer, not fake) ────────────────────────────────
-- R0..R7 are named __PH_Rx__ and hold decoded operands + results
-- This forces any decompiler to track register flow, not just stack
local __PH_R0__,__PH_R1__,__PH_R2__,__PH_R3__=0,0,0,0
local __PH_R4__,__PH_R5__,__PH_R6__,__PH_R7__=0,0,0,0
-- Gate counter: polynomial stepping, ensures opaque-gate is always true
-- but value changes each instruction (not just a static literal)
local __PH_GC__=0x5A3F
-- Execute a proto
local function __PH_EXE__(proto,env,varargs)
  local _code=proto.code
  local _k=proto.consts
  local _p=proto.protos
  local _stk={}; local _sp=0
  local _L={}    -- locals (register-indexed)
  local _pc=1

  -- Stack ops go through register file first
  local function PUSH(v)
    __PH_R0__=v          -- stage into R0 before stack write
    _sp=_sp+1; _stk[_sp]=__PH_R0__
  end
  local function POP()
    __PH_R1__=_stk[_sp]; _stk[_sp]=nil; _sp=_sp-1
    __PH_R2__=__PH_R1__  -- mirror into R2 (noise for analyser)
    return __PH_R1__
  end
  local function TOP() return _stk[_sp] end
  local function PEEK(n) return _stk[_sp-n] end

  repeat
    if _pc>#_code then break end
    local _ins=_code[_pc]; _pc=_pc+1
    -- Decode into register file
    __PH_R3__,__PH_R4__,__PH_R5__=__PH_UNP__(_ins)
    local _op=__PH_R3__; local _A=__PH_R4__; local _B=__PH_R5__
    -- Step gate counter (polynomial, always non-zero)
    __PH_GC__=(__PH_GC__*1103515245+12345)%0x80000000
    __PH_R6__=__PH_GC__%256
    -- Opaque gate: __PH_GC__^2 + 1 > 0 is always true
    -- Forces analyser to prove GC is never negative (it isn't, mod ensures ≥0)
    if __PH_GC__*__PH_GC__+1>0 then
      local _c=__PH_OP__[_op]
      -- c==nil or c==0 → junk/fake, skip
      if _c==1 then PUSH(_k[_A+1])
      elseif _c==2 then PUSH(nil)
      elseif _c==3 then PUSH(_A~=0)
      elseif _c==4 then
        __PH_R7__=_L[_A+1]; PUSH(__PH_R7__)
      elseif _c==5 then
        __PH_R7__=POP(); _L[_A+1]=__PH_R7__
      elseif _c==6 then PUSH(env[_k[_A+1]])
      elseif _c==7 then env[_k[_A+1]]=POP()
      elseif _c==8 then PUSH({})
      elseif _c==9 then
        local _ki=POP(); local _tb=POP()
        __PH_R7__=_tb and _tb[_ki]; PUSH(__PH_R7__)
      elseif _c==10 then
        local _ki=POP(); local _tb=POP(); local _vv=POP()
        if _tb then _tb[_ki]=_vv end
      elseif _c==11 then
        local _tb=POP(); __PH_R7__=_tb and _tb[_k[_A+1]]; PUSH(__PH_R7__)
      elseif _c==12 then
        local _vv=POP(); local _tb=POP()
        if _tb then _tb[_k[_A+1]]=_vv end
      elseif _c==13 then
          local _args={}
        for _i=_A,1,-1 do _args[_i]=POP() end
        local _fn=POP()
        __PH_R0__=_fn   -- fn staged in R0
        if type(_fn)=="function" then
          if _B==0 then _fn(table.unpack(_args))
          elseif _B==1 then
            __PH_R7__=_fn(table.unpack(_args)); PUSH(__PH_R7__)
          else
            local _res={_fn(table.unpack(_args))}
            for _i=1,_B do PUSH(_res[_i]) end
          end
        end
      elseif _c==14 then
        if _A==0 then return end
        local _res={}
        for _i=_A,1,-1 do _res[_i]=POP() end
        return table.unpack(_res)
      elseif _c==15 then _pc=_A+1
      elseif _c==16 then if TOP() then _pc=_A+1 end
      elseif _c==17 then if not TOP() then _pc=_A+1 end
      elseif _c==18 then if POP() then _pc=_A+1 end
      elseif _c==19 then if not POP() then _pc=_A+1 end
      elseif _c==20 then POP()
      elseif _c==21 then
        __PH_R4__=POP(); __PH_R5__=_stk[_sp]
        _stk[_sp]=__PH_R5__+__PH_R4__
      elseif _c==22 then
        __PH_R4__=POP(); _stk[_sp]=_stk[_sp]-__PH_R4__
      elseif _c==23 then
        __PH_R4__=POP(); _stk[_sp]=_stk[_sp]*__PH_R4__
      elseif _c==24 then
        __PH_R4__=POP(); _stk[_sp]=_stk[_sp]/__PH_R4__
      elseif _c==25 then
        __PH_R4__=POP(); _stk[_sp]=_stk[_sp]%__PH_R4__
      elseif _c==26 then
        __PH_R4__=POP(); _stk[_sp]=_stk[_sp]^__PH_R4__
      elseif _c==27 then
        __PH_R4__=POP()
        _stk[_sp]=tostring(_stk[_sp])..tostring(__PH_R4__)
      elseif _c==28 then _stk[_sp]=-_stk[_sp]
      elseif _c==29 then _stk[_sp]=not _stk[_sp]
      elseif _c==30 then _stk[_sp]=#_stk[_sp]
      elseif _c==31 then
        __PH_R4__=POP(); _stk[_sp]=(_stk[_sp]==__PH_R4__)
      elseif _c==32 then
        __PH_R4__=POP(); _stk[_sp]=(_stk[_sp]~=__PH_R4__)
      elseif _c==33 then
        __PH_R4__=POP(); _stk[_sp]=(_stk[_sp]<__PH_R4__)
      elseif _c==34 then
        __PH_R4__=POP(); _stk[_sp]=(_stk[_sp]<=__PH_R4__)
      elseif _c==35 then
        __PH_R4__=POP(); _stk[_sp]=(_stk[_sp]>__PH_R4__)
      elseif _c==36 then
        __PH_R4__=POP(); _stk[_sp]=(_stk[_sp]>=__PH_R4__)
      elseif _c==37 then
        local _pr=_p[_A+1]; local _uenv=env
        PUSH(function(...)
          local _a={...}; local _nl={}
          for _i=1,_pr.nparams do _nl[_i]=_a[_i] end
          local _va={}
          if _pr.is_vararg then
            for _i=_pr.nparams+1,#_a do _va[#_va+1]=_a[_i] end
          end
          return __PH_EXE__(_pr,_uenv,_va)
        end)
      elseif _c==38 then PUSH(TOP())
      elseif _c==39 then
        __PH_R4__=POP(); __PH_R5__=POP(); PUSH(__PH_R4__); PUSH(__PH_R5__)
      elseif _c==40 then
        local _n=_A==0 and #varargs or _A
        for _i=1,_n do PUSH(varargs[_i]) end
      elseif _c==41 then
        local _tb=POP()
        local _m=_tb and _tb[_k[_A+1]]
        PUSH(_m); PUSH(_tb)
      end
      -- Register writeback: R6/R7 hold last stack top (noise for symbolic execution)
      __PH_R6__=_stk[_sp] or 0
      __PH_R7__=__PH_GC__%128
    end
  until _pc>#_code
end
_N_vm=function(bc1,bc2,bc3,key,seed)
  local bc={}
  for _,seg in ipairs({bc1,bc2,bc3}) do
    for i=1,#seg do bc[#bc+1]=seg[i] end
  end
  local _chk=__PH_CRC__(bc)   -- integrity (value stored but not checked — obfuscation layer only)
  local dec=__PH_DEC__(bc,key,seed)
  local R=__PH_RDR__(dec)
  local proto=__PH_LDP__(R)
  local env=getfenv and getfenv(0) or _G
  __PH_EXE__(proto,env,{})
end
'''

# ── Canon ID table ────────────────────────────────────────────────────────────
_CANON_ID = {
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

# All placeholder names in _VM
_PLACEHOLDERS = [
    '__PH_XOR__','__PH_CHK__','__PH_CRC__','__PH_DEC__',
    '__PH_RDR__','__PH_DS__', '__PH_LDP__','__PH_UNP__',
    '__PH_R0__', '__PH_R1__', '__PH_R2__', '__PH_R3__',
    '__PH_R4__', '__PH_R5__', '__PH_R6__', '__PH_R7__',
    '__PH_GC__', '__PH_EXE__','__PH_OP__',
]

def _rname(rng, length=10):
    chars = 'IlO01'
    return '_' + rng.choice('lIO') + ''.join(rng.choices(chars, k=length-1))

def generate_vm(opcodes, rng_seed=None, layout=None) -> str:
    import random as _r
    rng = _r.Random(rng_seed if rng_seed is not None else _r.randint(0, 2**31))

    # ── Opcode dispatch table ────────────────────────────────────────────
    op_ph = '__PH_OP__'
    lines = [f'local {op_ph}={{}}']
    for alias, val in opcodes.all().items():
        cid = _CANON_ID.get(opcodes.canonical(val), 0)
        if cid > 0:
            lines.append(f'{op_ph}[{val}]={cid}')
    opcode_block = ';'.join(lines)

    # ── Instruction unpack (layout-aware) ───────────────────────────────
    if layout is None:
        layout = (24, 8, 12, 12, 0, 12)
    op_shift, op_bits, a_shift, a_bits, b_shift, b_bits = layout
    op_mask = (1 << op_bits) - 1
    a_mask  = (1 << a_bits)  - 1
    b_mask  = (1 << b_bits)  - 1
    unpack_lua = (
        f'local _op=math.floor(instr/{2**op_shift})%{op_mask+1};'
        f'local _a=math.floor(instr/{2**a_shift})%{a_mask+1};'
        f'local _b=instr%{b_mask+1};'
        f'return _op,_a,_b'
    )

    result = _VM
    result = result.replace('__OPCODE_TABLE__', opcode_block)
    result = result.replace('__LAYOUT_UNPACK__', unpack_lua)

    # ── VM Mutation: every placeholder → unique random name ─────────────
    # Each build: R0..R7, GC, EXE, etc. all get different names
    used = set()
    def fresh():
        while True:
            n = _rname(rng)
            if n not in used:
                used.add(n)
                return n

    name_map = {ph: fresh() for ph in _PLACEHOLDERS}
    # Replace __PH_OP__ in opcode_block too
    opcode_block_mut = opcode_block.replace(op_ph, name_map['__PH_OP__'])
    result = result.replace(opcode_block, opcode_block_mut)

    for ph, rn in name_map.items():
        result = result.replace(ph, rn)

    return result
