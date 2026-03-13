-- NightGuard V4 - Layer 1 VM (Deserialization + Validation)
-- Lua 5.1 / Luau compatible
-- Template variables: {{MAGIC}}, {{RUNTIME_KEY}}, {{SEED}}, {{DECOMP_CODE}}

local _NG_L1
do
    -- ── XOR fallback (Lua 5.1 compatible) ──────────────────────────────────
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

    -- ── Constants (filled by generator) ────────────────────────────────────
    local _MAGIC       = {{MAGIC}}
    local _RUNTIME_KEY = {{RUNTIME_KEY}}
    local _SEED        = {{SEED}}

    -- ── Freeze function ─────────────────────────────────────────────────────
    local function _freeze()
        local _t = {}
        repeat _t[#_t + 1] = 0 until #_t > 50000
    end

    -- ── Line check (anti-tamper) ─────────────────────────────────────────────
    local function _lc(expected)
        local ok, e = pcall(error, "", 2)
        if ok then return end
        local ln = tonumber((e or ""):match(":(%d+):") or "0") or 0
        if ln ~= expected then _freeze() end
    end

    -- ── Anti-debug ──────────────────────────────────────────────────────────
    local function _antidebug()
        if type(math.floor) ~= "function" then _freeze() end
        if type(pcall)       ~= "function" then _freeze() end
        if type(tostring)    ~= "function" then _freeze() end
    end
    _antidebug()

    -- ── Decompressor (injected) ──────────────────────────────────────────────
    {{DECOMP_CODE}}

    -- ── Reader ──────────────────────────────────────────────────────────────
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

    -- ── Decrypt (V4 XOR + feedback) ─────────────────────────────────────────
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

    -- ── Integrity check ──────────────────────────────────────────────────────
    local function _check_integrity(data)
        -- Simple checksum validation
        local sum = 0
        for i = 1, #data do
            sum = (sum + data[i] * i) % 0xFFFF
        end
        return sum
    end

    -- ── Proto parser ─────────────────────────────────────────────────────────
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
            end
        end
        local np = R.u32()
        p.pr = {}
        for i = 1, np do
            local bl = R.blk()
            p.pr[i] = _parse_proto(_reader(bl))
        end
        return p
    end

    -- ── Layer 1 main entry ───────────────────────────────────────────────────
    _NG_L1 = function(blob, enc_key, enc_seed, l2_execute)
        -- Step 1: Anti-debug check
        _antidebug()

        -- Step 2: Decompress
        local decompressed = _NG_decompress(blob)

        -- Step 3: Decrypt
        local decrypted = _decrypt(decompressed, enc_key, enc_seed)

        -- Step 4: Integrity check
        local checksum = _check_integrity(decrypted)

        -- Step 5: Parse proto
        local rdr   = _reader(decrypted)
        local proto = _parse_proto(rdr)

        -- Step 6: Compute handshake token
        -- token = xor(MAGIC, xor(RUNTIME_KEY, checksum))
        local token = _xor(_MAGIC, _xor(_RUNTIME_KEY, checksum % 0xFFFF))

        -- Step 7: Hand off to Layer 2
        l2_execute(proto, token, _MAGIC, _RUNTIME_KEY)
    end
end
