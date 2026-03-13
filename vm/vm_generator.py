import sys,os;sys.path.insert(0,os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
"""NightGuard V3 — Register VM Generator
Full register-based VM. Instruction format: op|A|B|C (each 8-bit) or op|A|Bx (16-bit).
RK(x): x >= 128 → K[x-128], else R[x].

Generated Lua is intentionally verbose — multiline handlers, fake local vars,
anti-analysis noise — making static analysis difficult.
"""
import random, re

# ─────────────────────────────────────────────────────────────────────────────
# INNER VM template
# Placeholders __IX_*__ → random obfuscated names per build
# __IX_OPENC__   → encrypted opcode→dispatch_id table
# __IX_DT_DEF__  → dispatch table definition (injected before execute loop)
# ─────────────────────────────────────────────────────────────────────────────
_INNER = r"""
local __IX_XOR__
if bit then
  __IX_XOR__ = bit.bxor
elseif bit32 then
  __IX_XOR__ = bit32.bxor
else
  __IX_XOR__ = function(a, b)
    local r, m = 0, 1
    while a > 0 or b > 0 do
      local x, y = a % 2, b % 2
      if x ~= y then r = r + m end
      a, b, m = math.floor(a / 2), math.floor(b / 2), m * 2
    end
    return r
  end
end

local function __IX_DS__(e, sd, st, sk)
  local d = {}
  for i = 1, #e do
    d[i] = (e[i] - (sk or 0) * i % 256 + 256) % 256
  end
  local k = sd
  local c = {}
  for i = 1, #d do
    c[i] = string.char(__IX_XOR__(d[i], k))
    k = (k * st + d[i]) % 256
    if k == 0 then k = 1 end
  end
  return table.concat(c)
end

local function __IX_DSC__(e, sd, st, sk, chunks, order)
  local sorted = {}
  if order then
    for i = 1, #order do
      sorted[order[i] + 1] = chunks[i]
    end
  else
    sorted = chunks
  end
  local raw = {}
  local ci = 1
  for i = 1, #sorted do
    local ch = sorted[i]
    local s, l = ch[1], ch[2]
    for j = s + 1, s + l do
      raw[ci] = e[j]
      ci = ci + 1
    end
  end
  return __IX_DS__(raw, sd, st, sk)
end

local function __IX_RDR__(b)
  local p = 1
  local R = {}
  function R.u8()
    local v = b[p]; p = p + 1; return v
  end
  function R.pos() return p end
  function R.setpos(v) p = v end
  function R.rem() return (#b - p + 1) end
  function R.u32()
    local a, b2, c, d = b[p], b[p+1], b[p+2], b[p+3]
    p = p + 4
    return a + b2*256 + c*65536 + d*16777216
  end
  function R.f64()
    local B = {b[p],b[p+1],b[p+2],b[p+3],b[p+4],b[p+5],b[p+6],b[p+7]}
    p = p + 8
    local s = B[8] >= 128 and -1 or 1
    local e2 = (B[8] % 128) * 16 + math.floor(B[7] / 16)
    local m = (B[7]%16)*2^48 + B[6]*2^40 + B[5]*2^32 + B[4]*2^24 + B[3]*2^16 + B[2]*2^8 + B[1]
    if e2 == 0 then
      return s * math.ldexp(m, -1074)
    elseif e2 == 2047 then
      return s * (1/0)
    else
      return s * math.ldexp(m + 2^52, e2 - 1075)
    end
  end
  function R.str()
    local n = R.u32()
    local c = {}
    for i = 1, n do
      c[i] = string.char(b[p]); p = p + 1
    end
    return table.concat(c)
  end
  function R.blk()
    local n = R.u32()
    local t = {}
    for i = 1, n do
      t[i] = b[p]; p = p + 1
    end
    return t
  end
  return R
end

local function __IX_LDP__(R)
  local p = {}
  p.np = R.u8()
  p.va = R.u8() == 1
  p.mr = R.u8()
  local nc = R.u32()
  p.code = {}
  for i = 1, nc do
    p.code[i] = R.u32()
  end
  local nk = R.u32()
  p.k = {}
  for i = 1, nk do
    local t = R.u8()
    if t == 0 then
      p.k[i] = nil
    elseif t == 1 then
      p.k[i] = R.u8() ~= 0
    elseif t == 2 then
      p.k[i] = R.f64()
    elseif t == 3 then
      p.k[i] = R.str()
    elseif t == 4 then
      local sd = R.u8(); local st = R.u8(); local sk = R.u8()
      local n = R.u32()
      local e = {}
      for j = 1, n do e[j] = R.u8() end
      p.k[i] = __IX_DS__(e, sd, st, sk)
    elseif t == 5 then
      local sd = R.u8(); local st = R.u8(); local sk = R.u8()
      local n = R.u32()
      local e = {}
      for j = 1, n do e[j] = R.u8() end
      local legacy = false
      local p0 = R.pos(); local nc2 = R.u32()
      if nc2 > math.floor(R.rem() / 8) then
        R.setpos(p0); nc2 = R.u8(); legacy = true
      end
      local ch = {}
      for j = 1, nc2 do
        local s = R.u32(); local l = R.u32()
        ch[j] = {s, l}
      end
      p0 = R.pos(); local nn = R.u32()
      if nn > math.floor(R.rem() / 8) then
        R.setpos(p0); nn = R.u8(); legacy = true
      end
      for j = 1, nn do R.u32(); R.u32() end
      local no
      if legacy then
        no = R.u8()
      else
        p0 = R.pos(); no = R.u32()
        if no > math.floor(R.rem() / 4) then
          R.setpos(p0); no = R.u8(); legacy = true
        end
      end
      local ord = {}
      for j = 1, no do ord[j] = legacy and R.u8() or R.u32() end
      p.k[i] = __IX_DSC__(e, sd, st, sk, ch, ord)
    end
  end
  local np = R.u32()
  p.pr = {}
  for i = 1, np do
    local bl = R.blk()
    p.pr[i] = __IX_LDP__(__IX_RDR__(bl))
  end
  return p
end

__IX_OPENC__

local function __IX_EXE__(proto, env, vararg, args)
  local R = {}
  for i = 0, proto.mr + 8 do R[i] = nil end
  if args then
    for i = 1, #args do
      R[i - 1] = args[i]
    end
  end
  local K  = proto.k
  local P  = proto.pr
  local CD = proto.code
  local pc = 1

  -- Anti-analysis: fake execution state vars that look like VM internals
  local __IX_FA__ = 0x5A3C
  local __IX_FB__ = 0
  local __IX_FC__ = 0
  local __IX_FD__ = false

  local function RK(x)
    if x >= 128 then
      return K[(x - 128) + 1]
    else
      return R[x]
    end
  end

__IX_DT_DEF__

  while pc <= #CD do
    local ins = CD[pc]; pc = pc + 1
    local op  = ins % 256
    local a   = math.floor(ins / 256) % 256
    local b   = math.floor(ins / 65536) % 256
    local c   = math.floor(ins / 16777216) % 256
    local bx  = math.floor(ins / 65536) % 65536
    local sbx = bx - 32767

    -- Fake state mutation (anti-tracing)
    __IX_FA__ = (__IX_FA__ * 1103515245 + 12345) % 0x80000000
    __IX_FB__ = __IX_FA__ % 256
    __IX_FC__ = __IX_XOR__(__IX_FB__, op)

    local nm = __IX_OP__[op]
    if op == __IX_RET_ID__ then
      -- RETURN: handled inline so we can actually return from this function
      local n = b - 1
      if n < 0 then n = 0 end
      if b == 1 then return end
      local rv = {}
      for i = 0, n - 1 do rv[i+1] = R[a + i] end
      return (table.unpack or unpack)(rv, 1, n)
    elseif nm ~= nil then
      local h = __IX_DT__[nm]
      if h then
        __IX_FD__ = h(a, b, c, bx, sbx)
      end
    end

    __IX_FB__ = R[0] or 0
  end
end
"""

# ─────────────────────────────────────────────────────────────────────────────
# OUTER VM template
# ─────────────────────────────────────────────────────────────────────────────
_OUTER = r"""
local _N_vm
local __OX_XOR__
if bit then
  __OX_XOR__ = bit.bxor
elseif bit32 then
  __OX_XOR__ = bit32.bxor
else
  __OX_XOR__ = function(a, b)
    local r, m = 0, 1
    while a > 0 or b > 0 do
      local x, y = a % 2, b % 2
      if x ~= y then r = r + m end
      a, b, m = math.floor(a / 2), math.floor(b / 2), m * 2
    end
    return r
  end
end

local function __OX_CHK__()
  if debug then
    if type(debug.sethook) == "function" then
      local ok, h = pcall(debug.gethook)
      if ok and h ~= nil then
        local t = {}
        repeat t[#t+1] = 0 until #t > 5e4
      end
    end
    if type(debug.getinfo) ~= "function" then
      local t = {}
      repeat t[#t+1] = 0 until #t > 5e4
    end
  end
  if type(math.floor) ~= "function" or type(pcall) ~= "function" then
    local t = {}
    repeat t[#t+1] = 0 until #t > 5e4
  end
end
__OX_CHK__()

local function __OX_DEC__(bc, key, sd)
  local kl = #key
  local out = {}
  local k = sd
  for i = 1, #bc do
    local e = bc[i]
    local t = __OX_XOR__(e, k)
    out[i] = __OX_XOR__(t, key[((i-1) % kl) + 1])
    k = (k * 13 + e) % 256
    if k == 0 then k = 1 end
  end
  return out
end

local function __OX_RDR__(b)
  local p = 1
  local R = {}
  function R.u8()
    local v = b[p]; p = p + 1; return v
  end
  function R.pos() return p end
  function R.setpos(v) p = v end
  function R.rem() return (#b - p + 1) end
  function R.u32()
    local a, b2, c, d = b[p], b[p+1], b[p+2], b[p+3]
    p = p + 4
    return a + b2*256 + c*65536 + d*16777216
  end
  function R.f64()
    local B = {b[p],b[p+1],b[p+2],b[p+3],b[p+4],b[p+5],b[p+6],b[p+7]}
    p = p + 8
    local s  = B[8] >= 128 and -1 or 1
    local e2 = (B[8] % 128) * 16 + math.floor(B[7] / 16)
    local m  = (B[7]%16)*2^48 + B[6]*2^40 + B[5]*2^32 + B[4]*2^24 + B[3]*2^16 + B[2]*2^8 + B[1]
    if e2 == 0 then
      return s * math.ldexp(m, -1074)
    elseif e2 == 2047 then
      return s * (1/0)
    else
      return s * math.ldexp(m + 2^52, e2 - 1075)
    end
  end
  function R.str()
    local n = R.u32()
    local c = {}
    for i = 1, n do
      c[i] = string.char(b[p]); p = p + 1
    end
    return table.concat(c)
  end
  function R.blk()
    local n = R.u32()
    local t = {}
    for i = 1, n do
      t[i] = b[p]; p = p + 1
    end
    return t
  end
  return R
end

local function __OX_LDP__(R)
  local p = {}
  p.np = R.u8()
  p.va = R.u8() == 1
  p.mr = R.u8()
  local nc = R.u32()
  p.code = {}
  for i = 1, nc do
    p.code[i] = R.u32()
  end
  local nk = R.u32()
  p.k = {}
  for i = 1, nk do
    local t = R.u8()
    if t == 0 then
      p.k[i] = nil
    elseif t == 1 then
      p.k[i] = R.u8() ~= 0
    elseif t == 2 then
      p.k[i] = R.f64()
    elseif t == 3 then
      p.k[i] = R.str()
    elseif t == 4 then
      local sd = R.u8(); local st = R.u8(); local sk = R.u8()
      local n = R.u32()
      local e = {}
      for j = 1, n do e[j] = R.u8() end
      p.k[i] = __IX_DS_REF__(e, sd, st, sk)
    elseif t == 5 then
      local sd = R.u8(); local st = R.u8(); local sk = R.u8()
      local n = R.u32()
      local e = {}
      for j = 1, n do e[j] = R.u8() end
      local legacy = false
      local p0 = R.pos(); local nc2 = R.u32()
      if nc2 > math.floor(R.rem() / 8) then
        R.setpos(p0); nc2 = R.u8(); legacy = true
      end
      local ch = {}
      for j = 1, nc2 do
        local s = R.u32(); local l = R.u32()
        ch[j] = {s, l}
      end
      p0 = R.pos(); local nn = R.u32()
      if nn > math.floor(R.rem() / 8) then
        R.setpos(p0); nn = R.u8(); legacy = true
      end
      for j = 1, nn do R.u32(); R.u32() end
      local no
      if legacy then
        no = R.u8()
      else
        p0 = R.pos(); no = R.u32()
        if no > math.floor(R.rem() / 4) then
          R.setpos(p0); no = R.u8(); legacy = true
        end
      end
      local ord = {}
      for j = 1, no do ord[j] = legacy and R.u8() or R.u32() end
      p.k[i] = __IX_DSC_REF__(e, sd, st, sk, ch, ord)
    end
  end
  local np = R.u32()
  p.pr = {}
  for i = 1, np do
    local bl = R.blk()
    p.pr[i] = __OX_LDP__(__OX_RDR__(bl))
  end
  return p
end

_N_vm = function(bc1, bc2, bc3, key, seed)
  local bc = {}
  for _, seg in ipairs({bc1, bc2, bc3}) do
    for i = 1, #seg do bc[#bc+1] = seg[i] end
  end
  local dec   = __OX_DEC__(bc, key, seed)
  local rdr   = __OX_RDR__(dec)
  local proto = __OX_LDP__(rdr)
  local env   = getfenv and getfenv(0) or _G
  __IX_EXE_REF__(proto, env, {}, {})
end
"""

_INNER_PH = [
    '__IX_XOR__','__IX_DS__','__IX_DSC__','__IX_RDR__','__IX_LDP__',
    '__IX_EXE__','__IX_OP__','__IX_DT__',
    '__IX_FA__','__IX_FB__','__IX_FC__','__IX_FD__',
]
_OUTER_PH = ['__OX_XOR__','__OX_CHK__','__OX_DEC__','__OX_RDR__','__OX_LDP__']

_HANDLED = [
    'LOADK','LOADNIL','LOADBOOL','MOVE',
    'GETGLOBAL','SETGLOBAL',
    'NEWTABLE','GETTABLE','SETTABLE','SELF',
    'ADD','SUB','MUL','DIV','MOD','POW',
    'UNM','NOT','LEN','CONCAT',
    'JMP','EQ','LT','LE','TEST','TESTSET',
    'CALL','TAILCALL','VARARG',
    'CLOSURE','FORPREP','FORLOOP','TFORLOOP','SETLIST',
]

def _fresh(rng, used):
    chars = 'lIO01'
    while True:
        v = '_' + rng.choice('lIO') + ''.join(rng.choices(chars, k=rng.randint(8,13)))
        if v not in used:
            used.add(v); return v

def _build_op_table(tbl, xor_fn, opcodes, dispatch_map, rng):
    raw = {}
    for nm in _HANDLED:
        try:
            oid = opcodes.id(nm)
            raw[oid] = dispatch_map[nm]
        except KeyError:
            pass
    if not raw:
        return f'local {tbl} = {{}}'
    xk  = rng.randint(1, 255)
    mx  = max(raw)
    enc = [(raw.get(i, 0) ^ xk) & 0xFFFF for i in range(mx + 1)]
    arr = '{' + ','.join(str(x) for x in enc) + '}'
    return (
        f'local {tbl} = {{}}\n'
        f'do\n'
        f'  local _e = {arr}\n'
        f'  local _k = {xk}\n'
        f'  for _i = 1, #_e do\n'
        f'    {tbl}[_i - 1] = {xor_fn}(_e[_i], _k)\n'
        f'  end\n'
        f'end'
    )

def _noise(rng, nv):
    """Generate a fake assignment line using a noise var name."""
    ops = [
        f'local {nv} = 0',
        f'local {nv} = false',
        f'local {nv} = nil',
        f'local {nv} = -1',
    ]
    return rng.choice(ops)

def _build_dispatch(dt, dm, imap, opcodes, rng):
    """
    Build register VM dispatch table.
    Each handler is multiline with:
    - local vars for intermediate values
    - fake noise locals (look like VM temporaries)
    - proper logic split across lines
    """
    exe = imap['__IX_EXE__']
    used_nv = set()

    def nv():
        return _fresh(rng, used_nv)

    lines = [f'  local {dt} = {{']

    def h(nm, body_lines):
        lines.append(f'    [{dm[nm]}] = function(a, b, c, bx, sbx)')
        for bl in body_lines:
            lines.append(f'      {bl}')
        lines.append(f'    end,')

    # ── LOADK ──────────────────────────────────────────────────────────────
    n1 = nv()
    h('LOADK', [
        f'local {n1} = bx + 1',
        f'R[a] = K[{n1}]',
    ])

    # ── LOADNIL ─────────────────────────────────────────────────────────────
    n1 = nv()
    h('LOADNIL', [
        f'local {n1} = a',
        f'while {n1} <= a + b do',
        f'  R[{n1}] = nil',
        f'  {n1} = {n1} + 1',
        f'end',
    ])

    # ── LOADBOOL ────────────────────────────────────────────────────────────
    n1 = nv()
    h('LOADBOOL', [
        f'local {n1} = (b ~= 0)',
        f'R[a] = {n1}',
        f'if c ~= 0 then',
        f'  pc = pc + 1',
        f'end',
    ])

    # ── MOVE ────────────────────────────────────────────────────────────────
    n1 = nv()
    h('MOVE', [
        f'local {n1} = R[b]',
        f'R[a] = {n1}',
    ])

    # ── GETGLOBAL ───────────────────────────────────────────────────────────
    n1, n2 = nv(), nv()
    h('GETGLOBAL', [
        f'local {n1} = bx + 1',
        f'local {n2} = K[{n1}]',
        f'R[a] = env[{n2}]',
    ])

    # ── SETGLOBAL ───────────────────────────────────────────────────────────
    n1, n2 = nv(), nv()
    h('SETGLOBAL', [
        f'local {n1} = bx + 1',
        f'local {n2} = K[{n1}]',
        f'env[{n2}] = R[a]',
    ])

    # ── NEWTABLE ────────────────────────────────────────────────────────────
    n1 = nv()
    h('NEWTABLE', [
        f'local {n1} = {{}}',
        f'R[a] = {n1}',
    ])

    # ── GETTABLE ────────────────────────────────────────────────────────────
    n1, n2, n3 = nv(), nv(), nv()
    h('GETTABLE', [
        f'local {n1} = R[b]',
        f'local {n2} = RK(c)',
        f'local {n3} = {n1}[{n2}]',
        f'R[a] = {n3}',
    ])

    # ── SETTABLE ────────────────────────────────────────────────────────────
    n1, n2, n3 = nv(), nv(), nv()
    h('SETTABLE', [
        f'local {n1} = R[a]',
        f'local {n2} = RK(b)',
        f'local {n3} = RK(c)',
        f'{n1}[{n2}] = {n3}',
    ])

    # ── SELF ────────────────────────────────────────────────────────────────
    n1, n2, n3 = nv(), nv(), nv()
    h('SELF', [
        f'local {n1} = R[b]',
        f'local {n2} = RK(c)',
        f'local {n3} = {n1}[{n2}]',
        f'R[a + 1] = {n1}',
        f'R[a] = {n3}',
    ])

    # ── Arithmetic ──────────────────────────────────────────────────────────
    for op_nm, lua_op in [('ADD','+'),('SUB','-'),('MUL','*'),('DIV','/'),('MOD','%'),('POW','^')]:
        n1, n2, n3 = nv(), nv(), nv()
        h(op_nm, [
            f'local {n1} = RK(b)',
            f'local {n2} = RK(c)',
            f'local {n3} = {n1} {lua_op} {n2}',
            f'R[a] = {n3}',
        ])

    # ── Unary ───────────────────────────────────────────────────────────────
    for op_nm, lua_op in [('UNM','-'),('NOT','not '),('LEN','#')]:
        n1, n2 = nv(), nv()
        h(op_nm, [
            f'local {n1} = R[b]',
            f'local {n2} = {lua_op}{n1}',
            f'R[a] = {n2}',
        ])

    # ── CONCAT ──────────────────────────────────────────────────────────────
    n1, n2, n3 = nv(), nv(), nv()
    h('CONCAT', [
        f'local {n1} = tostring(R[b])',
        f'local {n2} = b + 1',
        f'while {n2} <= c do',
        f'  local {n3} = tostring(R[{n2}])',
        f'  {n1} = {n1} .. {n3}',
        f'  {n2} = {n2} + 1',
        f'end',
        f'R[a] = {n1}',
    ])

    # ── JMP ─────────────────────────────────────────────────────────────────
    n1 = nv()
    h('JMP', [
        f'local {n1} = sbx',
        f'pc = pc + {n1}',
    ])

    # ── Compare: EQ, LT, LE ─────────────────────────────────────────────────
    for op_nm, lua_op in [('EQ','=='),('LT','<'),('LE','<=')]:
        n1, n2, n3 = nv(), nv(), nv()
        h(op_nm, [
            f'local {n1} = RK(b)',
            f'local {n2} = RK(c)',
            f'local {n3} = ({n1} {lua_op} {n2})',
            f'if {n3} ~= (a ~= 0) then',
            f'  pc = pc + 1',
            f'end',
        ])

    # ── TEST ────────────────────────────────────────────────────────────────
    n1, n2 = nv(), nv()
    h('TEST', [
        f'local {n1} = not not R[a]',
        f'local {n2} = (c ~= 0)',
        f'if {n1} ~= {n2} then',
        f'  pc = pc + 1',
        f'end',
    ])

    # ── TESTSET ─────────────────────────────────────────────────────────────
    n1, n2 = nv(), nv()
    h('TESTSET', [
        f'local {n1} = not not R[b]',
        f'local {n2} = (c ~= 0)',
        f'if {n1} ~= {n2} then',
        f'  pc = pc + 1',
        f'else',
        f'  R[a] = R[b]',
        f'end',
    ])

    # ── CALL ────────────────────────────────────────────────────────────────
    n1, n2, n3, n4, n5, n6 = nv(), nv(), nv(), nv(), nv(), nv()
    h('CALL', [
        f'local {n1} = R[a]',
        f'local {n2} = b - 1',
        f'if {n2} < 0 then {n2} = 0 end',
        f'local {n3} = {{}}',
        f'for {n4} = 1, {n2} do',
        f'  {n3}[{n4}] = R[a + {n4}]',
        f'end',
        f'local {n5} = c - 1',
        f'if {n5} < 0 then {n5} = 0 end',
        f'local {n6} = {{{n1}((table.unpack or unpack)({n3}))}}',
        f'for {n4} = 0, {n5} - 1 do',
        f'  R[a + {n4}] = {n6}[{n4} + 1]',
        f'end',
    ])

    # ── TAILCALL ────────────────────────────────────────────────────────────
    n1, n2, n3, n4 = nv(), nv(), nv(), nv()
    h('TAILCALL', [
        f'local {n1} = R[a]',
        f'local {n2} = {{}}',
        f'for {n3} = 1, b - 1 do',
        f'  {n2}[{n3}] = R[a + {n3}]',
        f'end',
        f'return {n1}((table.unpack or unpack)({n2}))',
    ])

    # ── VARARG ──────────────────────────────────────────────────────────────
    n1, n2, n3 = nv(), nv(), nv()
    h('VARARG', [
        f'local {n1} = b - 1',
        f'if {n1} < 0 then {n1} = #vararg end',
        f'for {n2} = 0, {n1} - 1 do',
        f'  local {n3} = vararg[{n2} + 1]',
        f'  R[a + {n2}] = {n3}',
        f'end',
    ])

    # ── CLOSURE ─────────────────────────────────────────────────────────────
    n1, n2, n3, n4, n5, n6, n7 = nv(), nv(), nv(), nv(), nv(), nv(), nv()
    h('CLOSURE', [
        f'local {n1} = P[bx + 1]',
        f'local {n2} = {n1}.np',
        f'local {n3} = {n1}.va',
        f'R[a] = function(...)',
        f'  local {n4} = {{...}}',
        f'  local {n5} = {{}}',
        f'  for {n6} = 1, {n2} do',
        f'    {n5}[{n6}] = {n4}[{n6}]',
        f'  end',
        f'  local {n7} = {{}}',
        f'  if {n3} then',
        f'    for {n6} = {n2} + 1, #{n4} do',
        f'      {n7}[#{n7} + 1] = {n4}[{n6}]',
        f'    end',
        f'  end',
        f'  return {exe}({n1}, env, {n7}, {n5})',
        f'end',
    ])

    # ── FORPREP ─────────────────────────────────────────────────────────────
    n1, n2 = nv(), nv()
    h('FORPREP', [
        f'local {n1} = R[a + 2]',
        f'local {n2} = R[a] - {n1}',
        f'R[a] = {n2}',
        f'pc = pc + sbx',
    ])

    # ── FORLOOP ─────────────────────────────────────────────────────────────
    n1, n2, n3, n4 = nv(), nv(), nv(), nv()
    h('FORLOOP', [
        f'local {n1} = R[a + 2]',
        f'local {n2} = R[a] + {n1}',
        f'local {n3} = R[a + 1]',
        f'R[a] = {n2}',
        f'local {n4} = false',
        f'if {n1} > 0 and {n2} <= {n3} then',
        f'  {n4} = true',
        f'elseif {n1} <= 0 and {n2} >= {n3} then',
        f'  {n4} = true',
        f'end',
        f'if {n4} then',
        f'  R[a + 3] = {n2}',
        f'  pc = pc + sbx',
        f'end',
    ])

    # ── TFORLOOP ────────────────────────────────────────────────────────────
    n1, n2, n3, n4, n5, n6 = nv(), nv(), nv(), nv(), nv(), nv()
    h('TFORLOOP', [
        f'local {n1} = R[a]',
        f'local {n2} = R[a + 1]',
        f'local {n3} = R[a + 2]',
        f'local {n4} = {{{n1}({n2}, {n3})}}',
        f'local {n5} = {n4}[1]',
        f'if {n5} ~= nil then',
        f'  R[a + 2] = {n5}',
        f'  for {n6} = 1, c do',
        f'    R[a + 2 + {n6}] = {n4}[{n6}]',
        f'  end',
        f'else',
        f'  pc = pc + 1',
        f'end',
    ])

    # ── SETLIST ─────────────────────────────────────────────────────────────
    n1, n2 = nv(), nv()
    h('SETLIST', [
        f'local {n1} = R[a]',
        f'for {n2} = 1, b do',
        f'  {n1}[{n2}] = R[a + {n2}]',
        f'end',
    ])

    lines.append('  }')
    return '\n'.join(lines)


def generate_vm(opcodes, rng_seed=None, **_) -> str:
    rng  = random.Random(rng_seed if rng_seed is not None else random.randint(0, 2**31))
    used = set()
    def fresh(): return _fresh(rng, used)

    # Random dispatch IDs per build
    pool = list(range(10000, 65000)); rng.shuffle(pool)
    dm   = {nm: pool[i] for i, nm in enumerate(_HANDLED)}

    # ── Inner VM ─────────────────────────────────────────────────────────────
    imap = {ph: fresh() for ph in _INNER_PH}
    inner = _INNER

    # Encrypted opcode→dispatch_id table
    enc_tbl = _build_op_table(imap['__IX_OP__'], imap['__IX_XOR__'], opcodes, dm, rng)
    inner = inner.replace('__IX_OPENC__', enc_tbl)

    # Dispatch table — build with placeholder names first, then replace
    dt_lua = _build_dispatch('__IX_DT__', dm, imap, opcodes, rng)
    inner  = inner.replace('__IX_DT_DEF__', dt_lua)

    # RETURN id — inlined in execute loop
    ret_id = opcodes.id('RETURN')
    inner  = inner.replace('__IX_RET_ID__', str(ret_id))

    # Substitute all __IX_*__ → random names
    for ph, rn in imap.items():
        inner = inner.replace(ph, rn)

    inner = re.sub(r'--[^\n]*', '', inner)
    inner = re.sub(r'\n{3,}', '\n\n', inner).strip()

    # ── Outer VM ─────────────────────────────────────────────────────────────
    omap  = {ph: fresh() for ph in _OUTER_PH}
    outer = _OUTER

    for ph, rn in omap.items():
        outer = outer.replace(ph, rn)

    # Wire inner function references into outer
    outer = outer.replace('__IX_DS_REF__',  imap['__IX_DS__'])
    outer = outer.replace('__IX_DSC_REF__', imap['__IX_DSC__'])
    outer = outer.replace('__IX_EXE_REF__', imap['__IX_EXE__'])

    outer = re.sub(r'--[^\n]*', '', outer)
    outer = re.sub(r'\n{3,}', '\n\n', outer).strip()

    return inner + '\n' + outer
