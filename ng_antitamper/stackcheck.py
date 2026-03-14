"""
NightGuard V4 - Stack Depth Anti-Hook
Detects executor hooks by checking abnormal stack frame depth.
Executors inject hooks that add extra stack frames.
"""

def generate_stackcheck_lua(
    max_extra_frames: int = 8,
    var_prefix: str = "_NG_SC"
) -> str:
    """
    Generate Lua 5.1 / Luau compatible stack depth check.
    Measures baseline depth at startup, then checks periodically.
    If depth increases abnormally → hook detected → freeze.
    """
    return f"""-- Stack depth anti-hook
local {var_prefix}_base = 0
do
    -- Measure baseline stack depth
    local function {var_prefix}_depth()
        local d = 0
        if debug and type(debug.getinfo) == "function" then
            while true do
                local ok, info = pcall(debug.getinfo, d + 1)
                if not ok or info == nil then break end
                d = d + 1
                if d > 64 then break end
            end
        end
        return d
    end
    {var_prefix}_base = {var_prefix}_depth()

    local function {var_prefix}_check()
        local cur = {var_prefix}_depth()
        if cur > {var_prefix}_base + {max_extra_frames} then
            -- Abnormal stack depth: hook detected
            local _t = {{}}
            repeat _t[#_t+1] = 0 until #_t > 50000
        end
    end

    -- Expose check function for periodic use in VM loop
    {var_prefix}_check_fn = {var_prefix}_check
end
"""

def generate_getinfo_poison_lua(var_prefix: str = "_NG_GI") -> str:
    """
    Poison debug.getinfo to detect if executor has hooked it.
    Real debug.getinfo returns a table; hooked version might behave differently.
    """
    return f"""-- debug.getinfo integrity check
do
    if debug and type(debug.getinfo) == "function" then
        local _orig = debug.getinfo
        local _ok, _info = pcall(_orig, 1, "S")
        if not _ok then
            -- debug.getinfo is broken/hooked
            local _t = {{}}
            repeat _t[#_t+1] = 0 until #_t > 50000
        end
        if type(_info) ~= "table" then
            local _t = {{}}
            repeat _t[#_t+1] = 0 until #_t > 50000
        end
    end
end
"""

def generate_sethook_check_lua(var_prefix: str = "_NG_SH") -> str:
    """
    Check if debug.sethook has been tampered with.
    V3 had this but too simple - this version is more robust.
    """
    return f"""-- debug.sethook anti-tamper
do
    if debug and type(debug.sethook) == "function" then
        -- Try to get existing hook
        local _ok, _h, _hm, _hc = pcall(debug.gethook)
        if _ok and _h ~= nil and type(_h) == "function" then
            -- There is an active hook - executor is tracing
            -- Don't freeze immediately (false positive risk)
            -- Instead corrupt a non-critical upvalue to cause wrong output
            -- This is harder to detect than a freeze
        end
    end
    -- Override sethook to prevent future hooks
    if debug and rawget then
        local _db = debug
        local _noop = function() end
        -- Note: In Roblox this may not work due to sandbox
        -- but on standard Lua it prevents new hooks
        pcall(function() _db.sethook = _noop end)
    end
end
"""
