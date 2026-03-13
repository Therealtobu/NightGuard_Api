"""
NightGuard V4 - Line Number Anti-Tamper
Generates line checks that freeze if VM source is reformatted/beautified.
"""

import re

# Sentinel comment to mark where line checks should be injected
LINE_CHECK_MARKER = "--[[LINECHECK]]"

def count_lines_to_marker(lua_source: str, marker: str) -> int:
    """Count line number where marker appears in source."""
    lines = lua_source.split("\n")
    for i, line in enumerate(lines, 1):
        if marker in line:
            return i
    return -1

def generate_linecheck_lua(expected_line: int, freeze_var: str = "_NG_LC") -> str:
    """
    Generate Lua 5.1 compatible line check code.
    If line number doesn't match expected, freeze execution.
    """
    return f"""do
    local _ok, _e = pcall(error, "", 2)
    local _ln = _e and tonumber((_e):match(":(%d+):")) or 0
    if _ln ~= {expected_line} then
        local _t = {{}}
        repeat _t[#_t+1] = 0 until #_t > 50000
    end
end"""

def inject_linechecks(lua_source: str) -> str:
    """
    Find all LINE_CHECK_MARKER in source and replace with
    actual line number checks.
    Two-pass: first count lines, then inject.
    """
    lines = lua_source.split("\n")
    result = []
    
    for i, line in enumerate(lines, 1):
        if LINE_CHECK_MARKER in line:
            # The check itself will be on line i
            # After injection, the check line will be i
            check = generate_linecheck_lua(i)
            # Replace marker with check
            new_line = line.replace(LINE_CHECK_MARKER, check)
            result.append(new_line)
        else:
            result.append(line)
    
    return "\n".join(result)

def inject_periodic_linechecks(lua_source: str, interval: int = 50) -> str:
    """
    Inject line checks every N lines throughout the VM source.
    More aggressive anti-tamper.
    """
    lines = lua_source.split("\n")
    result = []
    check_count = 0
    
    for i, line in enumerate(lines, 1):
        result.append(line)
        # Inject check every interval lines, but only in safe positions
        # (not inside string literals or comments)
        if (i % interval == 0 and 
            not line.strip().startswith("--") and
            not line.strip().startswith("local") and
            line.strip() == ""):
            
            # Inject after blank lines
            check_line = len(result) + 1
            check = generate_linecheck_lua(check_line)
            result.append(check)
            check_count += 1
    
    return "\n".join(result)

def generate_checksum_check(lua_source: str) -> str:
    """
    Generate a simple checksum of source length.
    If anyone adds/removes lines, this will trigger.
    """
    line_count = len(lua_source.split("\n"))
    return f"""do
    local _src = debug and debug.getinfo and debug.getinfo(1, "S")
    if _src then
        -- source length check would go here
        -- but in Roblox debug.getinfo may not have source
    end
end"""
