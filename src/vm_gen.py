"""
Night - VM Runtime Generator
Generates the Lua 5.1-compatible VM interpreter source code
with randomized opcode dispatch table.
"""

VM_TEMPLATE = r'''
-- [[ Night VM Runtime ]]
local _N_vm
do
    -- Decrypt helper: decode an encrypted string constant
    local function _N_dec(t, k)
        local r = {}
        for i = 1, #t do
            r[i] = string.char(bit32 and bit32.bxor(t[i], k) or (t[i] ~ k))
        end
        return table.concat(r)
    end

    -- Compatibility shim for bitwise XOR (Lua 5.1 / Roblox)
    local _bxor
    if bit then
        _bxor = bit.bxor
    elseif bit32 then
        _bxor = bit32.bxor
    else
        -- Pure Lua fallback XOR (slow but works anywhere)
        _bxor = function(a, b)
            local r, m = 0, 1
            while a > 0 or b > 0 do
                local ab, bb = a % 2, b % 2
                if ab ~= bb then r = r + m end
                a, b, m = math.floor(a / 2), math.floor(b / 2), m * 2
            end
            return r
        end
    end

    -- ── Bytecode decryptor ───────────────────────────────────────────────────
    local function _N_decrypt(bc_tbl, key_tbl, seed)
        -- Step 1: reverse rolling-XOR
        local tmp = {}
        local prev = seed
        for i = 1, #bc_tbl do
            local b = bc_tbl[i]
            tmp[i] = _bxor(_bxor(b, prev), (((i-1) * 31) % 256))
            prev = b
        end
        -- Step 2: reverse XOR with key
        local klen = #key_tbl
        local out = {}
        for i = 1, #tmp do
            out[i] = _bxor(tmp[i], key_tbl[((i-1) % klen) + 1])
        end
        return out
    end

    -- ── Binary reader ────────────────────────────────────────────────────────
    local function _N_reader(bytes)
        local pos = 1
        local R = {}
        function R.u8()
            local v = bytes[pos]; pos = pos + 1; return v
        end
        function R.u16()
            local lo = bytes[pos]; local hi = bytes[pos+1]
            pos = pos + 2
            return lo + hi * 256
        end
        function R.u32()
            local a = bytes[pos]; local b = bytes[pos+1]
            local c = bytes[pos+2]; local d = bytes[pos+3]
            pos = pos + 4
            return a + b*256 + c*65536 + d*16777216
        end
        function R.f64()
            -- Read 8 bytes as IEEE 754 double
            local b0,b1,b2,b3,b4,b5,b6,b7 =
                bytes[pos],bytes[pos+1],bytes[pos+2],bytes[pos+3],
                bytes[pos+4],bytes[pos+5],bytes[pos+6],bytes[pos+7]
            pos = pos + 8
            local sign = b7 >= 128 and -1 or 1
            local exp  = (b7 % 128) * 16 + math.floor(b6 / 16)
            local mant = (b6 % 16) * 2^48 +
                          b5 * 2^40 + b4 * 2^32 + b3 * 2^24 +
                          b2 * 2^16 + b1 * 2^8  + b0
            if exp == 0 then
                return sign * math.ldexp(mant, -1074)
            elseif exp == 2047 then
                return sign * math.huge
            else
                return sign * math.ldexp(mant + 2^52, exp - 1075)
            end
        end
        function R.str()
            local len = R.u32()
            local chars = {}
            for i = 1, len do chars[i] = string.char(bytes[pos]); pos = pos + 1 end
            return table.concat(chars)
        end
        function R.bytes_block()
            local len = R.u32()
            local blk = {}
            for i = 1, len do blk[i] = bytes[pos]; pos = pos + 1 end
            return blk
        end
        return R
    end

    -- ── Proto deserializer ───────────────────────────────────────────────────
    local function _N_load_proto(R)
        local p = {}
        p.nparams   = R.u8()
        p.is_vararg = R.u8() == 1
        -- Instructions
        local ncode = R.u32()
        p.code = {}
        for i = 1, ncode do
            local op = R.u8()
            local a  = R.u16()
            local b  = R.u16()
            p.code[i] = {op, a, b}
        end
        -- Constants
        local nconst = R.u32()
        p.consts = {}
        for i = 1, nconst do
            local t = R.u8()
            if t == 0 then
                p.consts[i] = nil
            elseif t == 1 then
                p.consts[i] = R.u8() ~= 0
            elseif t == 2 then
                p.consts[i] = R.f64()
            elseif t == 3 then
                p.consts[i] = R.str()
            elseif t == 4 then
                local xk = R.u8()
                local len2 = R.u32()
                local enc = {}
                for j = 1, len2 do enc[j] = R.u8() end
                -- Decrypt immediately
                local chars = {}
                for j = 1, #enc do chars[j] = string.char(_bxor(enc[j], xk)) end
                p.consts[i] = table.concat(chars)
            end
        end
        -- Nested protos
        local nproto = R.u32()
        p.protos = {}
        for i = 1, nproto do
            local blk = R.bytes_block()
            local R2  = _N_reader(blk)
            p.protos[i] = _N_load_proto(R2)
        end
        return p
    end

    -- ── Opcode constants (RANDOMIZED PER BUILD) ──────────────────────────────
    --OPCODE_TABLE--

    -- ── VM Executor ──────────────────────────────────────────────────────────
    local function _N_exec(proto, env, upvals, varargs)
        local code   = proto.code
        local consts = proto.consts
        local protos = proto.protos
        local stack  = {}
        local sp     = 0   -- stack pointer (top-of-stack index)
        local locals = {}
        local pc     = 1

        -- Copy params into locals (already set by caller wrapper)

        local function PUSH(v) sp = sp + 1; stack[sp] = v end
        local function POP()   local v = stack[sp]; stack[sp] = nil; sp = sp - 1; return v end
        local function TOP()   return stack[sp] end

        -- Main dispatch loop
        while pc <= #code do
            local ins = code[pc]
            local op, A, B = ins[1], ins[2], ins[3]
            pc = pc + 1

            -- Dispatch
            if op == OP_LOAD_CONST then
                PUSH(consts[A + 1])

            elseif op == OP_LOAD_NIL then
                PUSH(nil)

            elseif op == OP_LOAD_BOOL then
                PUSH(A ~= 0)

            elseif op == OP_LOAD_LOCAL then
                PUSH(locals[A + 1])

            elseif op == OP_STORE_LOCAL then
                locals[A + 1] = POP()

            elseif op == OP_LOAD_GLOBAL then
                PUSH(env[consts[A + 1]])

            elseif op == OP_STORE_GLOBAL then
                env[consts[A + 1]] = POP()

            elseif op == OP_LOAD_UPVAL then
                PUSH(upvals[A + 1] and upvals[A + 1][1])

            elseif op == OP_STORE_UPVAL then
                if upvals[A + 1] then upvals[A + 1][1] = POP()
                else POP() end

            elseif op == OP_NEW_TABLE then
                PUSH({})

            elseif op == OP_GET_TABLE then
                local key = POP(); local tbl = POP()
                PUSH(tbl and tbl[key])

            elseif op == OP_SET_TABLE then
                local key = POP(); local tbl = POP(); local val = POP()
                if tbl then tbl[key] = val end

            elseif op == OP_GET_FIELD then
                local tbl = POP()
                PUSH(tbl and tbl[consts[A + 1]])

            elseif op == OP_SET_FIELD then
                local val = POP(); local tbl = POP()
                if tbl then tbl[consts[A + 1]] = val end

            elseif op == OP_CALL then
                -- A = nargs, B = nret
                local args = {}
                for i = A, 1, -1 do args[i] = POP() end
                local fn = POP()
                if type(fn) == "function" then
                    if B == 0 then
                        fn(table.unpack(args))
                    elseif B == 1 then
                        PUSH(fn(table.unpack(args)))
                    else
                        local results = {fn(table.unpack(args))}
                        for i = 1, B do PUSH(results[i]) end
                    end
                elseif type(fn) == "table" then
                    -- Callable table (metamethod __call)
                    local mt = getmetatable(fn)
                    if mt and mt.__call then
                        local results = {mt.__call(fn, table.unpack(args))}
                        for i = 1, math.max(1, B) do PUSH(results[i]) end
                    end
                end

            elseif op == OP_RETURN then
                if A == 0 then return end
                local results = {}
                for i = A, 1, -1 do results[i] = POP() end
                return table.unpack(results)

            elseif op == OP_JUMP then
                pc = A + 1

            elseif op == OP_JUMP_TRUE then
                if TOP() then pc = A + 1 end

            elseif op == OP_JUMP_FALSE then
                if not TOP() then pc = A + 1 end

            elseif op == OP_JUMP_TRUE_POP then
                if POP() then pc = A + 1 end

            elseif op == OP_JUMP_FALSE_POP then
                if not POP() then pc = A + 1 end

            elseif op == OP_POP then
                POP()

            elseif op == OP_ADD  then local b=POP(); stack[sp]=stack[sp]+b
            elseif op == OP_SUB  then local b=POP(); stack[sp]=stack[sp]-b
            elseif op == OP_MUL  then local b=POP(); stack[sp]=stack[sp]*b
            elseif op == OP_DIV  then local b=POP(); stack[sp]=stack[sp]/b
            elseif op == OP_MOD  then local b=POP(); stack[sp]=stack[sp]%b
            elseif op == OP_POW  then local b=POP(); stack[sp]=stack[sp]^b
            elseif op == OP_CONCAT then local b=POP(); stack[sp]=stack[sp]..b

            elseif op == OP_UNM  then stack[sp] = -stack[sp]
            elseif op == OP_NOT  then stack[sp] = not stack[sp]
            elseif op == OP_LEN  then stack[sp] = #stack[sp]

            elseif op == OP_EQ  then local b=POP(); stack[sp]=(stack[sp]==b)
            elseif op == OP_NEQ then local b=POP(); stack[sp]=(stack[sp]~=b)
            elseif op == OP_LT  then local b=POP(); stack[sp]=(stack[sp]<b)
            elseif op == OP_LE  then local b=POP(); stack[sp]=(stack[sp]<=b)
            elseif op == OP_GT  then local b=POP(); stack[sp]=(stack[sp]>b)
            elseif op == OP_GE  then local b=POP(); stack[sp]=(stack[sp]>=b)

            elseif op == OP_MAKE_CLOSURE then
                local p2    = protos[A + 1]
                local uvs   = {}   -- simple: share parent upvals
                local closure = function(...)
                    local args = {...}
                    local locs = {}
                    for i = 1, p2.nparams do locs[i] = args[i] end
                    local va = {}
                    if p2.is_vararg then
                        for i = p2.nparams + 1, #args do va[#va+1] = args[i] end
                    end
                    return _N_exec(p2, env, uvs, va)
                end
                PUSH(closure)

            elseif op == OP_DUP then
                PUSH(TOP())

            elseif op == OP_SWAP then
                local a = POP(); local b = POP()
                PUSH(a); PUSH(b)

            elseif op == OP_VARARG then
                local n = A == 0 and #varargs or A
                for i = 1, n do PUSH(varargs[i]) end

            elseif op == OP_SELF then
                local tbl = TOP()   -- don't pop
                local method = tbl and tbl[consts[A + 1]]
                PUSH(method)        -- [tbl, method] → after SELF: [tbl, method] then CALL will use
                -- Actually SELF should push method then tbl (for call as method(self,...))
                -- Fix: pop tbl, push method, push tbl
                sp = sp - 1        -- undo the TOP() based PUSH
                local t2 = POP()   -- pop original tbl
                PUSH(t2[consts[A + 1]])  -- push method
                PUSH(t2)           -- push self

            elseif op == OP_JUNK then
                -- deliberate no-op

            end
        end
    end

    -- ── Public VM entry point ─────────────────────────────────────────────────
    _N_vm = function(bc_tbl, key_tbl, seed)
        local decrypted = _N_decrypt(bc_tbl, key_tbl, seed)
        local R         = _N_reader(decrypted)
        local proto     = _N_load_proto(R)
        local env       = getfenv and getfenv(0) or _G
        _N_exec(proto, env, {}, {})
    end
end
'''


def generate_vm(opcodes) -> str:
    """
    Return VM Lua source with the opcode table substituted in.
    `opcodes` is an Opcodes instance.
    """
    # Build the opcode table lines
    lines = []
    for name, value in opcodes.all().items():
        lines.append(f'    local OP_{name} = {value}')
    opcode_block = '\n'.join(lines)

    return VM_TEMPLATE.replace('    --OPCODE_TABLE--', opcode_block)
