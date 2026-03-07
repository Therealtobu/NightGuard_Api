import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
"""NightGuard V2 - VM Generator (double VM, register layer, anti-dump, split bc, minified)"""

_VM = r'''--OPCODE_TABLE--
local _bxor
if bit then _bxor=bit.bxor
elseif bit32 then _bxor=bit32.bxor
else _bxor=function(a,b)local r,m=0,1;while a>0 or b>0 do local ab,bb=a%2,b%2;if ab~=bb then r=r+m end;a,b,m=math.floor(a/2),math.floor(b/2),m*2 end;return r end
end
local function _ng_chk()
  local ok=true
  if debug then
    if type(debug.getinfo)~="function" then ok=false end
    if debug.sethook then
      local h=debug.gethook()
      if h~=nil then ok=false end
    end
  end
  if not ok then
    local t={}
    for i=1,1000 do t[i]=i*i end
    while true do t[1]=t[1]+1 end
  end
end
_ng_chk()
local function _N_decrypt(bc,k32,sd)
  local kl=#k32;local t={};for i=1,#bc do t[i]=_bxor(bc[i],k32[((i-1)%kl)+1])end
  local o={};local k=sd
  for i=1,#t do local e=t[i];o[i]=_bxor(e,k);k=(k*13+e)%256;if k==0 then k=1 end end
  return o
end
local function _N_reader(bytes)
  local pos=1;local R={}
  function R.u8()local v=bytes[pos];pos=pos+1;return v end
  function R.u16()local lo=bytes[pos];local hi=bytes[pos+1];pos=pos+2;return lo+hi*256 end
  function R.u32()local a,b,c,d=bytes[pos],bytes[pos+1],bytes[pos+2],bytes[pos+3];pos=pos+4;return a+b*256+c*65536+d*16777216 end
  function R.f64()local b0,b1,b2,b3,b4,b5,b6,b7=bytes[pos],bytes[pos+1],bytes[pos+2],bytes[pos+3],bytes[pos+4],bytes[pos+5],bytes[pos+6],bytes[pos+7];pos=pos+8;local s=b7>=128 and -1 or 1;local e=(b7%128)*16+math.floor(b6/16);local m=(b6%16)*2^48+b5*2^40+b4*2^32+b3*2^24+b2*2^16+b1*2^8+b0;if e==0 then return s*math.ldexp(m,-1074)elseif e==2047 then return s*(1/0)else return s*math.ldexp(m+2^52,e-1075)end end
  function R.str()local len=R.u32();local ch={};for i=1,len do ch[i]=string.char(bytes[pos]);pos=pos+1 end;return table.concat(ch)end
  function R.blk()local len=R.u32();local b={};for i=1,len do b[i]=bytes[pos];pos=pos+1 end;return b end
  return R
end
local function _N_dec_str(enc,sd,st)local k=sd;local ch={};for i=1,#enc do ch[i]=string.char(_bxor(enc[i],k));k=(k*st+enc[i])%256;if k==0 then k=1 end end;return table.concat(ch)end
local function _N_load_proto(R)
  local p={};p.nparams=R.u8();p.is_vararg=R.u8()==1
  local nc=R.u32();p.code={};for i=1,nc do p.code[i]=R.u32()end
  local nk=R.u32();p.consts={}
  for i=1,nk do
    local t=R.u8()
    if t==0 then p.consts[i]=nil
    elseif t==1 then p.consts[i]=R.u8()~=0
    elseif t==2 then p.consts[i]=R.f64()
    elseif t==3 then p.consts[i]=R.str()
    elseif t==4 then local sd=R.u8();local st=R.u8();local len=R.u32();local enc={};for j=1,len do enc[j]=R.u8()end;p.consts[i]=_N_dec_str(enc,sd,st)
    end
  end
  local np=R.u32();p.protos={}
  for i=1,np do local blk=R.blk();p.protos[i]=_N_load_proto(_N_reader(blk))end
  return p
end
local function _unpack_ins(instr)
  local op=math.floor(instr/16777216)%256
  local a=math.floor(instr/4096)%4096
  local b=instr%4096
  return op,a,b
end
-- Register layer (R0..R7 temp registers above stack)
local _REG={}
for i=0,7 do _REG[i]=0 end
local function _N_exec(proto,env,varargs)
  local code=proto.code;local consts=proto.consts;local protos=proto.protos
  local stk={};local sp=0;local locs={};local pc=1
  -- fake state for opaque predicates
  local _fk1=1;local _fk2=0
  local function PUSH(v)sp=sp+1;stk[sp]=v end
  local function POP()local v=stk[sp];stk[sp]=nil;sp=sp-1;return v end
  local function TOP()return stk[sp]end
  -- control flow noise: use repeat+condition instead of plain while
  repeat
    if pc>#code then break end
    local ins=code[pc];pc=pc+1
    local op,A,B=_unpack_ins(ins)
    local c=_N_op[op]
    -- register layer: temp store hotpath values
    _REG[0]=A;_REG[1]=B
    -- fake math noise (opaque predicate always true)
    _fk1=(_fk1*3+7)%251;_fk2=(_fk2+_fk1)%251
    if(_fk1+_fk2+1)>0 then
      if c==1 then PUSH(consts[A+1])
      elseif c==2 then PUSH(nil)
      elseif c==3 then PUSH(A~=0)
      elseif c==4 then PUSH(locs[A+1])
      elseif c==5 then locs[A+1]=POP()
      elseif c==6 then PUSH(env[consts[A+1]])
      elseif c==7 then env[consts[A+1]]=POP()
      elseif c==8 then PUSH({})
      elseif c==9 then local k=POP();local t=POP();PUSH(t and t[k])
      elseif c==10 then local k=POP();local t=POP();local v=POP();if t then t[k]=v end
      elseif c==11 then local t=POP();PUSH(t and t[consts[A+1]])
      elseif c==12 then local v=POP();local t=POP();if t then t[consts[A+1]]=v end
      elseif c==13 then
        local args={};for i=A,1,-1 do args[i]=POP()end;local fn=POP()
        if type(fn)=="function" then
          if B==0 then fn(table.unpack(args))
          elseif B==1 then PUSH(fn(table.unpack(args)))
          else local res={fn(table.unpack(args))};for i=1,B do PUSH(res[i])end end
        end
      elseif c==14 then
        if A==0 then return end
        local res={};for i=A,1,-1 do res[i]=POP()end;return table.unpack(res)
      elseif c==15 then pc=A+1
      elseif c==16 then if TOP()then pc=A+1 end
      elseif c==17 then if not TOP()then pc=A+1 end
      elseif c==18 then if POP()then pc=A+1 end
      elseif c==19 then if not POP()then pc=A+1 end
      elseif c==20 then POP()
      elseif c==21 then local b=POP();stk[sp]=stk[sp]+b
      elseif c==22 then local b=POP();stk[sp]=stk[sp]-b
      elseif c==23 then local b=POP();stk[sp]=stk[sp]*b
      elseif c==24 then local b=POP();stk[sp]=stk[sp]/b
      elseif c==25 then local b=POP();stk[sp]=stk[sp]%b
      elseif c==26 then local b=POP();stk[sp]=stk[sp]^b
      elseif c==27 then local b=POP();stk[sp]=tostring(stk[sp])..tostring(b)
      elseif c==28 then stk[sp]=-stk[sp]
      elseif c==29 then stk[sp]=not stk[sp]
      elseif c==30 then stk[sp]=#stk[sp]
      elseif c==31 then local b=POP();stk[sp]=(stk[sp]==b)
      elseif c==32 then local b=POP();stk[sp]=(stk[sp]~=b)
      elseif c==33 then local b=POP();stk[sp]=(stk[sp]<b)
      elseif c==34 then local b=POP();stk[sp]=(stk[sp]<=b)
      elseif c==35 then local b=POP();stk[sp]=(stk[sp]>b)
      elseif c==36 then local b=POP();stk[sp]=(stk[sp]>=b)
      elseif c==37 then
        local p2=protos[A+1];local uenv=env
        PUSH(function(...)
          local a={...};local L={}
          for i=1,p2.nparams do L[i]=a[i]end
          local va={};if p2.is_vararg then for i=p2.nparams+1,#a do va[#va+1]=a[i]end end
          return _N_exec(p2,uenv,va)
        end)
      elseif c==38 then PUSH(TOP())
      elseif c==39 then local a=POP();local b=POP();PUSH(a);PUSH(b)
      elseif c==40 then local n=A==0 and #varargs or A;for i=1,n do PUSH(varargs[i])end
      elseif c==41 then local t=POP();local m=t and t[consts[A+1]];PUSH(m);PUSH(t)
      end
      -- fake stack ops (no-op, just noise)
      _REG[2]=_REG[0];_REG[3]=_REG[1];_REG[4]=(_REG[2]+_REG[3])%256
    end
  until pc>#code
end
_N_vm=function(bc1,bc2,bc3,key,seed)
  -- reconstruct bytecode from 3 parts
  local bc={}
  for _,seg in ipairs({bc1,bc2,bc3})do
    for i=1,#seg do bc[#bc+1]=seg[i]end
  end
  local dec=_N_decrypt(bc,key,seed)
  local R=_N_reader(dec)
  local proto=_N_load_proto(R)
  local env=getfenv and getfenv(0)or _G
  _N_exec(proto,env,{})
end
'''

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
    'JUNK':0,'FAKE_STACK':0,'FAKE_MATH':0,
}

def generate_vm(opcodes) -> str:
    lines = ['local _N_op={}']
    for alias_name, val in opcodes.all().items():
        canon = opcodes.canonical(val)
        cid = _CANON_ID.get(canon, 0)
        if cid > 0:
            lines.append(f'_N_op[{val}]={cid}')
    opcode_block = ';'.join(lines)
    return _VM.replace('--OPCODE_TABLE--', opcode_block)
