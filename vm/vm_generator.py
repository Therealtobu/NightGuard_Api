"""NightGuard V2 - VM Runtime Generator"""

# The VM template – opcode table injected at build time
_VM = r'''local _N_vm
do
--OPCODE_TABLE--

-- XOR helper (Lua 5.1 / Luau compat)
local _bxor
if bit then _bxor=bit.bxor
elseif bit32 then _bxor=bit32.bxor
else
  _bxor=function(a,b)
    local r,m=0,1
    while a>0 or b>0 do
      local ab,bb=a%2,b%2
      if ab~=bb then r=r+m end
      a,b,m=math.floor(a/2),math.floor(b/2),m*2
    end; return r
  end
end

-- ── Rolling-XOR decryptor ────────────────────────────────────────────────────
local function _N_decrypt(bc,key32,seed)
  local klen=#key32
  -- Reverse layer 2 (XOR with key block)
  local tmp={}
  for i=1,#bc do tmp[i]=_bxor(bc[i],key32[((i-1)%klen)+1]) end
  -- Reverse layer 1 (rolling XOR): we need to go forward and un-xor
  local out={}; local k=seed
  for i=1,#tmp do
    local enc=tmp[i]
    out[i]=_bxor(enc,k)
    k=(k*13+enc)%256; if k==0 then k=1 end
  end
  return out
end

-- ── Integrity check ──────────────────────────────────────────────────────────
local function _N_checksum(t)
  local s=0
  for i=1,#t do s=(s+t[i]*i)%65536 end
  return s
end

-- ── Binary reader ─────────────────────────────────────────────────────────────
local function _N_reader(bytes)
  local pos=1; local R={}
  function R.u8() local v=bytes[pos];pos=pos+1;return v end
  function R.u16() local lo=bytes[pos];local hi=bytes[pos+1];pos=pos+2;return lo+hi*256 end
  function R.u32()
    local a,b,c,d=bytes[pos],bytes[pos+1],bytes[pos+2],bytes[pos+3];pos=pos+4
    return a+b*256+c*65536+d*16777216
  end
  function R.f64()
    local b0,b1,b2,b3,b4,b5,b6,b7=bytes[pos],bytes[pos+1],bytes[pos+2],bytes[pos+3],bytes[pos+4],bytes[pos+5],bytes[pos+6],bytes[pos+7]
    pos=pos+8
    local sign=b7>=128 and -1 or 1
    local exp=(b7%128)*16+math.floor(b6/16)
    local mant=(b6%16)*2^48+b5*2^40+b4*2^32+b3*2^24+b2*2^16+b1*2^8+b0
    if exp==0 then return sign*math.ldexp(mant,-1074)
    elseif exp==2047 then return sign*(1/0)
    else return sign*math.ldexp(mant+2^52,exp-1075) end
  end
  function R.str()
    local len=R.u32(); local ch={}
    for i=1,len do ch[i]=string.char(bytes[pos]);pos=pos+1 end
    return table.concat(ch)
  end
  function R.blk()
    local len=R.u32(); local b={}
    for i=1,len do b[i]=bytes[pos];pos=pos+1 end
    return b
  end
  return R
end

-- ── Rolling-XOR string decryptor (for encrypted constants) ────────────────────
local function _N_dec_str(enc,seed,step)
  local k=seed; local ch={}
  for i=1,#enc do
    ch[i]=string.char(_bxor(enc[i],k))
    k=(k*step+enc[i])%256; if k==0 then k=1 end
  end
  return table.concat(ch)
end

-- ── Proto deserialiser ─────────────────────────────────────────────────────────
local function _N_load_proto(R)
  local p={}
  p.nparams=R.u8(); p.is_vararg=R.u8()==1
  local nc=R.u32(); p.code={}
  for i=1,nc do p.code[i]=R.u32() end   -- packed u32
  local nk=R.u32(); p.consts={}
  for i=1,nk do
    local t=R.u8()
    if t==0 then p.consts[i]=nil
    elseif t==1 then p.consts[i]=R.u8()~=0
    elseif t==2 then p.consts[i]=R.f64()
    elseif t==3 then p.consts[i]=R.str()
    elseif t==4 then
      local sd=R.u8(); local st=R.u8()
      local len=R.u32(); local enc={}
      for j=1,len do enc[j]=R.u8() end
      p.consts[i]=_N_dec_str(enc,sd,st)
    end
  end
  local np=R.u32(); p.protos={}
  for i=1,np do local blk=R.blk(); p.protos[i]=_N_load_proto(_N_reader(blk)) end
  return p
end

-- ── Instruction unpacker ──────────────────────────────────────────────────────
local function _unpack(instr)
  local op=math.floor(instr/16777216)%256
  local a =math.floor(instr/4096)%4096
  local b =instr%4096
  return op,a,b
end

-- ── VM executor ───────────────────────────────────────────────────────────────
local function _N_exec(proto,env,varargs)
  local code=proto.code; local consts=proto.consts; local protos=proto.protos
  local stk={}; local sp=0; local locs={}; local pc=1
  local function PUSH(v) sp=sp+1;stk[sp]=v end
  local function POP()   local v=stk[sp];stk[sp]=nil;sp=sp-1;return v end
  local function TOP()   return stk[sp] end

  while pc<=#code do
    local ins=code[pc]; pc=pc+1
    local op,A,B=_unpack(ins)
    local cn=_N_canon[op]

    if cn=="LOAD_CONST" then PUSH(consts[A+1])
    elseif cn=="LOAD_NIL" then PUSH(nil)
    elseif cn=="LOAD_BOOL" then PUSH(A~=0)
    elseif cn=="LOAD_LOCAL" then PUSH(locs[A+1])
    elseif cn=="STORE_LOCAL" then locs[A+1]=POP()
    elseif cn=="LOAD_GLOBAL" then PUSH(env[consts[A+1]])
    elseif cn=="STORE_GLOBAL" then env[consts[A+1]]=POP()
    elseif cn=="NEW_TABLE" then PUSH({})
    elseif cn=="GET_TABLE" then local k=POP();local t=POP();PUSH(t and t[k])
    elseif cn=="SET_TABLE" then local k=POP();local t=POP();local v=POP();if t then t[k]=v end
    elseif cn=="GET_FIELD" then local t=POP();PUSH(t and t[consts[A+1]])
    elseif cn=="SET_FIELD" then local v=POP();local t=POP();if t then t[consts[A+1]]=v end
    elseif cn=="CALL" then
      local args={}; for i=A,1,-1 do args[i]=POP() end
      local fn=POP()
      if type(fn)=="function" then
        if B==0 then fn(table.unpack(args))
        elseif B==1 then PUSH(fn(table.unpack(args)))
        else local res={fn(table.unpack(args))}; for i=1,B do PUSH(res[i]) end end
      end
    elseif cn=="RETURN" then
      if A==0 then return end
      local res={}; for i=A,1,-1 do res[i]=POP() end
      return table.unpack(res)
    elseif cn=="JUMP" then pc=A+1
    elseif cn=="JUMP_TRUE" then if TOP() then pc=A+1 end
    elseif cn=="JUMP_FALSE" then if not TOP() then pc=A+1 end
    elseif cn=="JUMP_TRUE_POP" then if POP() then pc=A+1 end
    elseif cn=="JUMP_FALSE_POP" then if not POP() then pc=A+1 end
    elseif cn=="POP" then POP()
    elseif cn=="ADD" then local b=POP();stk[sp]=stk[sp]+b
    elseif cn=="SUB" then local b=POP();stk[sp]=stk[sp]-b
    elseif cn=="MUL" then local b=POP();stk[sp]=stk[sp]*b
    elseif cn=="DIV" then local b=POP();stk[sp]=stk[sp]/b
    elseif cn=="MOD" then local b=POP();stk[sp]=stk[sp]%b
    elseif cn=="POW" then local b=POP();stk[sp]=stk[sp]^b
    elseif cn=="CONCAT" then local b=POP();stk[sp]=tostring(stk[sp])..tostring(b)
    elseif cn=="UNM" then stk[sp]=-stk[sp]
    elseif cn=="NOT" then stk[sp]=not stk[sp]
    elseif cn=="LEN" then stk[sp]=#stk[sp]
    elseif cn=="EQ"  then local b=POP();stk[sp]=(stk[sp]==b)
    elseif cn=="NEQ" then local b=POP();stk[sp]=(stk[sp]~=b)
    elseif cn=="LT"  then local b=POP();stk[sp]=(stk[sp]<b)
    elseif cn=="LE"  then local b=POP();stk[sp]=(stk[sp]<=b)
    elseif cn=="GT"  then local b=POP();stk[sp]=(stk[sp]>b)
    elseif cn=="GE"  then local b=POP();stk[sp]=(stk[sp]>=b)
    elseif cn=="MAKE_CLOSURE" then
      local p2=protos[A+1]; local uenv=env
      PUSH(function(...)
        local a={...}; local L={}
        for i=1,p2.nparams do L[i]=a[i] end
        local va={}
        if p2.is_vararg then for i=p2.nparams+1,#a do va[#va+1]=a[i] end end
        return _N_exec(p2,uenv,va)
      end)
    elseif cn=="DUP"  then PUSH(TOP())
    elseif cn=="SWAP" then local a=POP();local b=POP();PUSH(a);PUSH(b)
    elseif cn=="VARARG" then
      local n=A==0 and #varargs or A
      for i=1,n do PUSH(varargs[i]) end
    elseif cn=="SELF" then
      local t=POP(); local m=t and t[consts[A+1]]
      PUSH(m); PUSH(t)
    end
    -- JUNK / FAKE_STACK / FAKE_MATH / unknown: no-op
  end
end

-- ── Public entry ──────────────────────────────────────────────────────────────
_N_vm=function(bc,key,seed)
  local dec=_N_decrypt(bc,key,seed)
  local R=_N_reader(dec)
  local proto=_N_load_proto(R)
  local env=getfenv and getfenv(0) or _G
  _N_exec(proto,env,{})
end
end
'''

def generate_vm(opcodes) -> str:
    """
    Substitute the opcode dispatch table into the VM template.
    _N_canon[val] = canonical_name  for every (alias_val -> canon)
    """
    lines = ['local _N_canon={}']
    # For every alias value, map to its canonical op name
    for alias_name, val in opcodes.all().items():
        canon = opcodes.canonical(val)
        lines.append(f'_N_canon[{val}]="{canon}"')

    opcode_block = '\n'.join(lines)
    return _VM.replace('--OPCODE_TABLE--', opcode_block)
