-- NightGuard V4 - Layer 1 VM (Deserialization + Validation)
-- Lua 5.1 / Luau compatible
-- Template variables: {{MAGIC}}, {{RUNTIME_KEY}}, {{SEED}}, {{DECOMP_CODE}}

local _NG_L1
do
    -- -- XOR fallback (Lua 5.1 compatible) ----------------------------------
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

    -- -- Constants (filled by generator) ------------------------------------
    local _MAGIC       = {{MAGIC}}
    local _RUNTIME_KEY = {{RUNTIME_KEY}}
    local _SEED        = {{SEED}}

    -- -- Freeze function -----------------------------------------------------
    local function _freeze()
        local _t = {}
        repeat _t[#_t + 1] = 0 until #_t > 50000
    end

    -- -- Line check (anti-tamper) ---------------------------------------------
    local function _lc(expected)
        local ok, e = pcall(error, "", 2)
        if ok then return end
        local ln = tonumber((e or ""):match(":(%d+):") or "0") or 0
        if ln ~= expected then _freeze() end
    end

    -- -- Anti-debug ----------------------------------------------------------
    local function _antidebug()
        if type(math.floor) ~= "function" then _freeze() end
        if type(pcall)       ~= "function" then _freeze() end
        if type(tostring)    ~= "function" then _freeze() end
    end
    _antidebug()

    -- -- Decompressor (injected) ----------------------------------------------
    {{DECOMP_CODE}}

    -- -- Reader --------------------------------------------------------------
    local function _reader(b)
        local p = 1
        local R = {}
        function R.u8()
            local v = b[p]; p = p + 1; return v
        end
        function R.u32()
            local a, b2, c, d = b[p], b[p+1], b[p+2], b[p+3]
            p = p + 4
            return a + b2 * 256 + c * 65536 + d * 16777216
        end
        function R.f64()
            local B = {b[p],b[p+1],b[p+2],b[p+3],b[p+4],b[p+5],b[p+6],b[p+7]}
            p = p + 8
            local s  = B[8] >= 128 and -1 or 1
            local e2 = (B[8] % 128) * 16 + math.floor(B[7] / 16)
            local m  = (B[7]%16)*2^48 + B[6]*2^40 + B[5]*2^32
                     + B[4]*2^24 + B[3]*2^16 + B[2]*2^8 + B[1]
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
            for i = 1, n do c[i] = string.char(b[p]); p = p + 1 end
            return table.concat(c)
        end
        function R.blk()
            local n = R.u32()
            local t = {}
            for i = 1, n do t[i] = b[p]; p = p + 1 end
            return t
        end
        function R.pos()    return p end
        function R.setpos(v) p = v end
        function R.rem()    return (#b - p + 1) end
        return R
    end

    -- -- Decrypt (V4 XOR + feedback) -----------------------------------------
    local function _decrypt(data, key, seed)
        local kl  = #key
        local out = {}
        local k   = seed
        for i = 1, #data do
            local e = data[i]
            local t = _xor(e, k)
            out[i]  = _xor(t, key[((i-1) % kl) + 1])
            k = (k * 13 + e) % 256
            if k == 0 then k = 1 end
        end
        return out
    end

    -- -- Integrity check ------------------------------------------------------
    local function _check_integrity(data)
        -- Simple checksum validation
        local sum = 0
        for i = 1, #data do
            sum = (sum + data[i] * i) % 0xFFFF
        end
        return sum
    end

    local function _dec_str(e, sd, st, sk)
        local d = {}
        for i = 1, #e do
            d[i] = (e[i] - (sk or 0) * i % 256 + 256) % 256
        end
        local k = sd
        local c = {}
        for i = 1, #d do
            c[i] = string.char(_xor(d[i], k))
            k = (k * st + d[i]) % 256
            if k == 0 then k = 1 end
        end
        return table.concat(c)
    end

    local function _dec_scatter(e, sd, st, sk, chunks, order)
        local sorted = {}
        if order then
            for i = 1, #order do sorted[order[i] + 1] = chunks[i] end
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
        return _dec_str(raw, sd, st, sk)
    end

    -- -- Proto parser ---------------------------------------------------------
    local function _parse_proto(R)
        local p = {}
        p.np   = R.u8()
        p.va   = R.u8() == 1
        p.mr   = R.u8()
        local nc = R.u32()
        p.code = {}
        for i = 1, nc do p.code[i] = R.u32() end
        local nk = R.u32()
        p.k    = {}
        for i = 1, nk do
            local t = R.u8()
            if     t == 0 then p.k[i] = nil
            elseif t == 1 then p.k[i] = R.u8() ~= 0
            elseif t == 2 then p.k[i] = R.f64()
            elseif t == 3 then p.k[i] = R.str()
            elseif t == 4 then
                local sd = R.u8(); local st = R.u8(); local sk = R.u8()
                local n = R.u32()
                local e = {}
                for j = 1, n do e[j] = R.u8() end
                p.k[i] = _dec_str(e, sd, st, sk)
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
                    local s0 = R.u32(); local l0 = R.u32()
                    ch[j] = {s0, l0}
                end
                p0 = R.pos(); local nn = R.u32()
                if nn > math.floor(R.rem() / 8) then
                    R.setpos(p0); nn = R.u8(); legacy = true
                end
                for j = 1, nn do R.u32(); R.u32() end
                p0 = R.pos(); local no = R.u32()
                if (not legacy) and no > math.floor(R.rem() / 4) then
                    R.setpos(p0); no = R.u8(); legacy = true
                end
                local ord = {}
                for j = 1, no do ord[j] = legacy and R.u8() or R.u32() end
                p.k[i] = _dec_scatter(e, sd, st, sk, ch, ord)
            end
        end
        local ncaps = R.u32()
        p.caps = {}
        for i = 1, ncaps do
            local nm = R.str()
            local rg = R.u8()
            p.caps[i] = {nm, rg}
        end

        local np = R.u32()
        p.pr = {}
        for i = 1, np do
            local bl = R.blk()
            p.pr[i] = _parse_proto(_reader(bl))
        end
        return p
    end

    -- -- Layer 1 main entry ---------------------------------------------------
    _NG_L1 = function(blob, enc_key, enc_seed, l2_execute)
        -- Step 1: Anti-debug check
        _antidebug()

        -- Step 2: Decrypt
        local decrypted = _decrypt(blob, enc_key, enc_seed)

        -- Step 3: Decompress
        local decompressed = _NG_decompress(decrypted)

        -- Step 4: Integrity check
        local checksum = _check_integrity(decompressed)

        -- Step 5: Parse proto
        local rdr   = _reader(decompressed)
        local proto = _parse_proto(rdr)

        -- Step 6: Compute handshake token
        -- token = xor(MAGIC, RUNTIME_KEY)
        local token = _xor(_MAGIC, _RUNTIME_KEY)

        -- Step 7: Hand off to Layer 2
        l2_execute(proto, token, _MAGIC, _RUNTIME_KEY)
    end
end
