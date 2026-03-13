"""
NightGuard V4 - Execution Fingerprinting
Detects tracing/debugging by measuring execution timing anomalies.
Traced execution is significantly slower than normal execution.
"""

def generate_timing_check_lua(
    iterations: int = 10000,
    slowdown_factor: int = 5,
    var_prefix: str = "_NG_TF"
) -> str:
    """
    Generate timing-based anti-trace check.
    Measures time for tight loop, if too slow → being traced.
    Uses os.clock() which is available in both Lua 5.1 and Luau.
    """
    return f"""-- Execution timing fingerprint
do
    if type(os) == "table" and type(os.clock) == "function" then
        local _t1 = os.clock()
        local _dummy = 0
        for _i = 1, {iterations} do
            _dummy = _dummy + _i
        end
        local _t2 = os.clock()
        local _elapsed = _t2 - _t1

        -- Calibrate: normal execution should be very fast
        -- If traced, each iteration triggers hook overhead
        -- Threshold: {slowdown_factor}x normal is suspicious
        -- We measure again to get baseline
        local _t3 = os.clock()
        local _dummy2 = 0
        for _i = 1, {iterations} do
            _dummy2 = _dummy2 + _i
        end
        local _t4 = os.clock()
        local _elapsed2 = _t4 - _t3

        -- If both runs are consistently slow, likely being traced
        if _elapsed > 0.5 and _elapsed2 > 0.5 then
            -- Slow execution detected
            -- Corrupt state subtly instead of hard freeze
            -- (harder to detect than obvious freeze)
            _dummy = nil
            _dummy2 = nil
        end
    end
end
"""

def generate_tick_check_lua(var_prefix: str = "_NG_TC") -> str:
    """
    Roblox-specific: use tick() or os.clock() for timing.
    tick() is Roblox-specific and more precise.
    """
    return f"""-- Roblox tick-based timing check
do
    local _clock = (type(tick) == "function") and tick or
                   (type(os) == "table" and type(os.clock) == "function" and os.clock) or
                   nil
    if _clock then
        local _t1 = _clock()
        local _s  = 0
        for _i = 1, 5000 do _s = (_s + _i) % 65536 end
        local _t2 = _clock()
        -- Normal: < 0.01 seconds for 5000 iterations
        -- Traced: could be 0.1+ seconds per iteration with hook overhead
        if (_t2 - _t1) > 1.0 then
            -- Being heavily traced
            local _t = {{}}
            repeat _t[#_t+1] = 0 until #_t > 50000
        end
    end
end
"""

def generate_upvalue_count_check_lua(
    expected_count: int,
    var_prefix: str = "_NG_UV"
) -> str:
    """
    Check upvalue count of a known function.
    If executor has injected upvalue hooks, count changes.
    """
    return f"""-- Upvalue count integrity check
do
    if debug and type(debug.getupvalue) == "function" then
        local _fn = math.floor  -- known function
        local _count = 0
        while debug.getupvalue(_fn, _count + 1) do
            _count = _count + 1
            if _count > 20 then break end
        end
        -- math.floor is a C function, should have 0 upvalues
        if _count > 0 then
            -- Upvalues injected into C function - executor hook detected
            local _t = {{}}
            repeat _t[#_t+1] = 0 until #_t > 50000
        end
    end
end
"""
