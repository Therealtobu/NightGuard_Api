-- NightGuard V4 - Layer 2 VM (Execution + CFO State Machine)
-- Lua 5.1 / Luau compatible
-- Template variables: {{OPMAP}}, {{RETURN_OP}}, {{FLOW_SEED}}

local _NG_L2
do
    -- -- XOR fallback --------------------------------------------------------
    local _xor
    if bit then
        _xor = bit.bxor
    elseif bit32 then
        _xor = bit32.bxor
    else
        _xor = function(a, b)
            local r, m = 0, 1
            while a > 0 or b > 0 do
                local x, y = a % 2, b % 2
                if x ~= y then r = r + m end
                a, b, m = math.floor(a / 2), math.floor(b / 2), m * 2
            end
            return r
        end
    end

    -- -- Constants ------------------------------------------------------------
    local _RETURN_OP  = {{RETURN_OP}}
    local _FLOW_SEED  = {{FLOW_SEED}}

    -- -- Opcode map (unique per script) --------------------------------------
    local _OPMAP = {{OPMAP}}

    -- -- State machine constants ----------------------------------------------
    local _S_FETCH    = 0
    local _S_DECODE   = 1
    local _S_DISPATCH = 2
    local _S_JUNK1    = 3
    local _S_JUNK2    = 4
    local _S_ADVANCE  = 5
    local _S_COUNT    = 6

    -- -- Freeze ---------------------------------------------------------------
    local function _freeze()
        local _t = {}
        repeat _t[#_t + 1] = 0 until #_t > 50000
    end

    -- -- Anti-debug -----------------------------------------------------------
    local function _antidebug()
        if type(math.floor) ~= "function" then _freeze() end
        if type(pcall)       ~= "function" then _freeze() end
    end

    -- -- VM executor ----------------------------------------------------------
    local function _exec(proto, env, vararg, args)
        -- Register file (plain table for Lua 5.1 compat; buffer in Luau version)
        local R = {}
        for i = 0, proto.mr + 8 do R[i] = nil end
        if args then
            for i = 1, #args do R[i - 1] = args[i] end
        end

        local K   = proto.k
        local P   = proto.pr
        local CD  = proto.code
        local pc  = 1

        -- -- RK helper ------------------------------------------------------
        local function RK(x)
            if x >= 256 then return K[(x - 256) + 1] end
            return R[x]
        end

        -- -- Handler table (keyed by mapped opcode name) ---------------------
        local _H = {}

        -- LOADK
        _H[_OPMAP[0]] = function(a, b, c, bx, sbx)
            R[a] = K[bx + 1]
        end
        -- LOADNIL
        _H[_OPMAP[1]] = function(a, b, c, bx, sbx)
            for i = a, a + b do R[i] = nil end
        end
        -- LOADBOOL
        _H[_OPMAP[2]] = function(a, b, c, bx, sbx)
            R[a] = (b ~= 0)
            if c ~= 0 then pc = pc + 1 end
        end
        -- MOVE
        _H[_OPMAP[3]] = function(a, b, c, bx, sbx)
            R[a] = R[b]
        end
        -- GETGLOBAL
        _H[_OPMAP[4]] = function(a, b, c, bx, sbx)
            R[a] = env[K[bx + 1]]
        end
        -- SETGLOBAL
        _H[_OPMAP[5]] = function(a, b, c, bx, sbx)
            env[K[bx + 1]] = R[a]
        end
        -- NEWTABLE
        _H[_OPMAP[6]] = function(a, b, c, bx, sbx)
            R[a] = {}
        end
        -- GETTABLE
        _H[_OPMAP[7]] = function(a, b, c, bx, sbx)
            R[a] = R[b][RK(c)]
        end
        -- SETTABLE
        _H[_OPMAP[8]] = function(a, b, c, bx, sbx)
            R[a][RK(b)] = RK(c)
        end
        -- SELF
        _H[_OPMAP[9]] = function(a, b, c, bx, sbx)
            R[a + 1] = R[b]
            R[a]     = R[b][RK(c)]
        end
        -- ADD
        _H[_OPMAP[10]] = function(a, b, c, bx, sbx)
            R[a] = RK(b) + RK(c)
        end
        -- SUB
        _H[_OPMAP[11]] = function(a, b, c, bx, sbx)
            R[a] = RK(b) - RK(c)
        end
        -- MUL
        _H[_OPMAP[12]] = function(a, b, c, bx, sbx)
            R[a] = RK(b) * RK(c)
        end
        -- DIV
        _H[_OPMAP[13]] = function(a, b, c, bx, sbx)
            R[a] = RK(b) / RK(c)
        end
        -- MOD
        _H[_OPMAP[14]] = function(a, b, c, bx, sbx)
            R[a] = RK(b) % RK(c)
        end
        -- POW
        _H[_OPMAP[15]] = function(a, b, c, bx, sbx)
            R[a] = RK(b) ^ RK(c)
        end
        -- UNM
        _H[_OPMAP[16]] = function(a, b, c, bx, sbx)
            R[a] = -R[b]
        end
        -- NOT
        _H[_OPMAP[17]] = function(a, b, c, bx, sbx)
            R[a] = not R[b]
        end
        -- LEN
        _H[_OPMAP[18]] = function(a, b, c, bx, sbx)
            R[a] = #R[b]
        end
        -- CONCAT
        _H[_OPMAP[19]] = function(a, b, c, bx, sbx)
            local s = tostring(R[b])
            for i = b + 1, c do s = s .. tostring(R[i]) end
            R[a] = s
        end
        -- JMP
        _H[_OPMAP[20]] = function(a, b, c, bx, sbx)
            pc = pc + sbx
        end
        -- EQ
        _H[_OPMAP[21]] = function(a, b, c, bx, sbx)
            if (RK(b) == RK(c)) ~= (a ~= 0) then pc = pc + 1 end
        end
        -- LT
        _H[_OPMAP[22]] = function(a, b, c, bx, sbx)
            if (RK(b) < RK(c)) ~= (a ~= 0) then pc = pc + 1 end
        end
        -- LE
        _H[_OPMAP[23]] = function(a, b, c, bx, sbx)
            if (RK(b) <= RK(c)) ~= (a ~= 0) then pc = pc + 1 end
        end
        -- TEST
        _H[_OPMAP[24]] = function(a, b, c, bx, sbx)
            if (not not R[a]) ~= (c ~= 0) then pc = pc + 1 end
        end
        -- TESTSET
        _H[_OPMAP[25]] = function(a, b, c, bx, sbx)
            if (not not R[b]) ~= (c ~= 0) then
                pc = pc + 1
            else
                R[a] = R[b]
            end
        end
        -- CALL
        _H[_OPMAP[26]] = function(a, b, c, bx, sbx)
            local fn  = R[a]
            local n   = b - 1
            if n < 0 then n = 0 end
            local argv = {}
            for i = 1, n do argv[i] = R[a + i] end
            local ret_n = c - 1
            if ret_n < 0 then ret_n = 0 end
            local rets = {fn((table.unpack or unpack)(argv))}
            for i = 0, ret_n - 1 do R[a + i] = rets[i + 1] end
        end
        -- TAILCALL
        _H[_OPMAP[27]] = function(a, b, c, bx, sbx)
            local fn  = R[a]
            local argv = {}
            for i = 1, b - 1 do argv[i] = R[a + i] end
            return fn((table.unpack or unpack)(argv))
        end
        -- RETURN
        -- Handled separately in main loop
        -- FORLOOP
        _H[_OPMAP[29]] = function(a, b, c, bx, sbx)
            local step = R[a + 2]
            R[a] = R[a] + step
            local limit = R[a + 1]
            local ok = (step > 0 and R[a] <= limit) or
                       (step <= 0 and R[a] >= limit)
            if ok then
                R[a + 3] = R[a]
                pc = pc + sbx
            end
        end
        -- FORPREP
        _H[_OPMAP[30]] = function(a, b, c, bx, sbx)
            R[a] = R[a] - R[a + 2]
            pc = pc + sbx
        end
        -- TFORLOOP
        _H[_OPMAP[31]] = function(a, b, c, bx, sbx)
            local fn  = R[a]
            local s   = R[a + 1]
            local var = R[a + 2]
            local rets = {fn(s, var)}
            local v1 = rets[1]
            if v1 ~= nil then
                R[a + 2] = v1
                for i = 1, c do R[a + 2 + i] = rets[i] end
            else
                pc = pc + 1
            end
        end
        -- SETLIST
        _H[_OPMAP[32]] = function(a, b, c, bx, sbx)
            local t = R[a]
            for i = 1, b do t[i] = R[a + i] end
        end
        -- CLOSE (no-op in our VM)
        _H[_OPMAP[33]] = function(a, b, c, bx, sbx) end
        -- CLOSURE
        _H[_OPMAP[34]] = function(a, b, c, bx, sbx)
            local sub   = P[bx + 1]
            local np    = sub.np
            local va    = sub.va
            R[a] = function(...)
                local passed = {...}
                local fargs  = {}
                for i = 1, np do fargs[i] = passed[i] end
                local fva    = {}
                if va then
                    for i = np + 1, #passed do
                        fva[#fva + 1] = passed[i]
                    end
                end
                return _exec(sub, env, fva, fargs)
            end
        end
        -- VARARG
        _H[_OPMAP[35]] = function(a, b, c, bx, sbx)
            local n = b - 1
            if n < 0 then n = #vararg end
            for i = 0, n - 1 do R[a + i] = vararg[i + 1] end
        end

        -- -- CFO State machine execute loop ----------------------------------
        local _FLOW  = _FLOW_SEED
        local _STATE = _S_FETCH

        -- Current instruction state
        local _ins, _op, _a, _b, _c, _bx, _sbx
        local _junk_accum = 0

        while true do

            -- -- State: FETCH -----------------------------------------------
            if _STATE == _S_FETCH then
                if pc > #CD then break end
                _ins   = CD[pc]
                pc     = pc + 1
                -- Route to junk occasionally
                _FLOW  = (_FLOW * 1103515245 + 12345) % 0x80000000
                _STATE = (_FLOW % 3 == 0) and _S_JUNK1 or _S_DECODE

            -- -- State: JUNK1 -----------------------------------------------
            elseif _STATE == _S_JUNK1 then
                _junk_accum = (_junk_accum + pc) % 0xFFFF
                _STATE = _S_JUNK2

            -- -- State: JUNK2 -----------------------------------------------
            elseif _STATE == _S_JUNK2 then
                local _ = (R[0] or 0) + _junk_accum
                _STATE = _S_DECODE

            -- -- State: DECODE ----------------------------------------------
            elseif _STATE == _S_DECODE then
                _op  = _ins % 256
                _a   = math.floor(_ins / 256) % 256
                _b   = math.floor(_ins / 65536) % 256
                _c   = math.floor(_ins / 16777216) % 256
                _bx  = math.floor(_ins / 65536) % 65536
                _sbx = _bx - 32767
                _STATE = _S_DISPATCH

            -- -- State: DISPATCH --------------------------------------------
            elseif _STATE == _S_DISPATCH then
                if _op == _RETURN_OP then
                    -- RETURN
                    local n = _b - 1
                    if n < 0 then n = 0 end
                    if _b == 1 then return end
                    local rv = {}
                    for i = 0, n - 1 do rv[i + 1] = R[_a + i] end
                    return (table.unpack or unpack)(rv, 1, n)
                else
                    local h = _H[_op]
                    if h then h(_a, _b, _c, _bx, _sbx) end
                end
                _STATE = _S_ADVANCE

            -- -- State: ADVANCE ---------------------------------------------
            elseif _STATE == _S_ADVANCE then
                -- Periodic anti-debug check (every 31 instructions)
                if pc % 31 == 0 then _antidebug() end
                _STATE = _S_FETCH

            else
                -- Unknown state: should never happen
                _STATE = _S_FETCH
            end

        end -- while true
    end -- _exec

    -- -- Layer 2 main entry ------------------------------------------------
    _NG_L2 = function(proto, token, expected_magic, runtime_key)
        -- Verify Layer 1 handshake
        local _xv = _xor(token, runtime_key)
        if _xv ~= expected_magic then
            _freeze()
            return
        end

        -- Execute
        local env = (getfenv and getfenv(0)) or _G
        _exec(proto, env, {}, {})
    end
end
