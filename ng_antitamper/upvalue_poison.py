"""
NightGuard V4 - Upvalue Poisoning
Wraps sensitive VM closures with poison upvalues.
If executor uses getupvalue/setupvalue to inspect/modify VM internals,
the poison triggers and corrupts execution.
"""

def generate_upvalue_poison_lua(var_prefix: str = "_NG_UP") -> str:
    """
    Generate upvalue poison wrapper for VM closures.
    Uses a sentinel value that should never be modified externally.
    Lua 5.1 / Luau compatible.
    """
    return f"""-- Upvalue poisoning
local {var_prefix}_sentinel
do
    -- Create a unique sentinel table
    -- Executors cannot recreate this exact reference
    local _s = {{_ng_poison = true, _ng_id = math.random(0, 2147483647)}}
    {var_prefix}_sentinel = _s

    -- Verify sentinel integrity periodically
    {var_prefix}_check = function()
        if type({var_prefix}_sentinel) ~= "table" then
            local _t = {{}}
            repeat _t[#_t+1] = 0 until #_t > 50000
        end
        if {var_prefix}_sentinel._ng_poison ~= true then
            local _t = {{}}
            repeat _t[#_t+1] = 0 until #_t > 50000
        end
    end
end
"""

def generate_closure_wrapper_lua(
    fn_name: str,
    var_prefix: str = "_NG_CW"
) -> str:
    """
    Wrap a function in a closure with poison upvalue.
    If getupvalue is called on the wrapper, poison is detected on next check.
    """
    return f"""-- Closure wrapper with poison upvalue
local {fn_name}_wrapped
do
    local _poison = {var_prefix}_sentinel
    local _real   = {fn_name}
    local _calls  = 0

    {fn_name}_wrapped = function(...)
        -- Verify poison upvalue hasn't been tampered
        if _poison ~= {var_prefix}_sentinel then
            local _t = {{}}
            repeat _t[#_t+1] = 0 until #_t > 50000
        end
        _calls = _calls + 1
        return _real(...)
    end
end
{fn_name} = {fn_name}_wrapped
"""

def generate_constant_guard_lua(
    constants: dict,
    var_prefix: str = "_NG_CG"
) -> str:
    """
    Guard critical constants against modification.
    constants: dict of name -> expected_value
    """
    checks = []
    for name, expected in constants.items():
        if isinstance(expected, int):
            checks.append(
                f"    if {name} ~= {expected} then _freeze() end"
            )
        elif isinstance(expected, str):
            checks.append(
                f"    if {name} ~= {repr(expected)} then _freeze() end"
            )

    check_body = "\n".join(checks) if checks else "    -- no constants to guard"

    return f"""-- Constant integrity guard
local {var_prefix}_guard = function()
    local function _freeze()
        local _t = {{}}
        repeat _t[#_t+1] = 0 until #_t > 50000
    end
{check_body}
end
"""

def generate_metamethod_trap_lua(
    table_name: str,
    var_prefix: str = "_NG_MT"
) -> str:
    """
    Set metamethod trap on sensitive table.
    If anyone iterates or accesses the table abnormally, trap fires.
    """
    return f"""-- Metamethod access trap on {table_name}
do
    local _real_table = {table_name}
    local _access_log = {{}}
    local _access_count = 0

    local _trap_mt = {{
        __index = function(t, k)
            _access_count = _access_count + 1
            -- Log access pattern
            _access_log[_access_count] = k
            -- If accessing more than expected range, suspect dump tool
            if _access_count > #_real_table * 3 then
                local _t = {{}}
                repeat _t[#_t+1] = 0 until #_t > 50000
            end
            return _real_table[k]
        end,
        __newindex = function(t, k, v)
            -- Writes to this table should only come from VM itself
            _real_table[k] = v
        end,
        __len = function(t)
            return #_real_table
        end
    }}

    local _proxy = setmetatable({{}}, _trap_mt)
    {table_name} = _proxy
end
"""
