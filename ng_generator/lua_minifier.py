"""
NightGuard V4 - Lua Minifier
Strips all comments and blank lines from Lua source.
Handles: -- line comments, --[[ block comments ]], strings, multiline strings.
Does NOT join lines (unsafe without a full parser) — just removes noise.
"""

import re

def _strip_lua(src: str) -> str:
    """
    Remove all Lua comments and blank lines.
    State-machine approach: respects string literals so we never
    accidentally touch quoted content.
    """
    out    = []
    i      = 0
    n      = len(src)
    line   = []          # chars for current line (stripped at EOL)

    def flush(force_newline=False):
        s = "".join(line).strip()
        line.clear()
        if s:
            out.append(s)

    while i < n:
        c = src[i]

        # ── Long string / long comment  [=*[ ... ]=*] ──────────────────────
        if c == '-' and i+1 < n and src[i+1] == '-' and \
           i+2 < n and src[i+2] == '[':
            # Detect level
            j = i + 2
            level = 0
            while j < n and src[j] == '=':
                level += 1
                j += 1
            if j < n and src[j] == '[':
                # Long comment — skip until ]=*]
                close = ']' + '='*level + ']'
                end = src.find(close, j+1)
                if end == -1:
                    # Malformed — skip rest
                    break
                i = end + len(close)
                continue
            else:
                # Short comment — skip to EOL
                while i < n and src[i] != '\n':
                    i += 1
                flush()
                if i < n:  # consume the \n
                    i += 1
                continue

        # ── Short comment  -- ───────────────────────────────────────────────
        if c == '-' and i+1 < n and src[i+1] == '-':
            while i < n and src[i] != '\n':
                i += 1
            flush()
            if i < n:
                i += 1
            continue

        # ── Long string literal  [=*[ ... ]=*] ─────────────────────────────
        if c == '[':
            j = i + 1
            level = 0
            while j < n and src[j] == '=':
                level += 1
                j += 1
            if j < n and src[j] == '[':
                close = ']' + '='*level + ']'
                end = src.find(close, j+1)
                if end == -1:
                    line.append(c); i += 1; continue
                raw = src[i:end+len(close)]
                line.append(raw)
                i = end + len(close)
                continue

        # ── Quoted string  ' or " ───────────────────────────────────────────
        if c in ('"', "'"):
            q = c
            line.append(c)
            i += 1
            while i < n:
                ch = src[i]
                line.append(ch)
                if ch == '\\':
                    i += 1
                    if i < n:
                        line.append(src[i])
                        i += 1
                    continue
                if ch == q:
                    i += 1
                    break
                i += 1
            continue

        # ── Newline ─────────────────────────────────────────────────────────
        if c == '\n':
            flush()
            i += 1
            continue

        # ── Normal char ─────────────────────────────────────────────────────
        line.append(c)
        i += 1

    flush()  # last line

    return "\n".join(out)


def minify(src: str) -> str:
    """
    Full minification:
    1. Strip all Lua comments and blank lines
    2. Strip leading/trailing whitespace per line
    3. Return compact single-block string with no blank lines
    """
    return _strip_lua(src)


import re as _re

def fix_lua_xor(src: str) -> str:
    """
    Replace Lua 5.3+ ~ (bitwise XOR) with bit32.bxor() for Roblox/Luau compat.
    Handles every pattern NightGuard generates. Never touches ~= comparisons.

    Patterns covered:
      (N)~(M)            → bit32.bxor(N,M)       -- watermark lines
      v ~ 0 and v or s   → bit32.bxor(v,0)~=0 and v or s  -- junk template
      word ~ word        → bit32.bxor(word,word)  -- dispatch / junk fragments
    """
    # P1: (N)~(M) — parens around both operands (watermark pattern)
    P1 = _re.compile(r'\((\d+)\)\s*~\s*\((\d+)\)')
    # P2: VAR ~ 0 and VAR or SEED  (junk template 0)
    P2 = _re.compile(r'(\b\w+\b)\s*~\s*0\s+and\s+\1\s+or\b')
    # P3: word ~ word  (not followed by =)
    P3 = _re.compile(r'(\b\w+\b)\s*~(?!=)\s*(\b\w+\b)')

    lines = src.split('\n')
    out = []
    for line in lines:
        line = P1.sub(lambda m: f'bit32.bxor({m.group(1)},{m.group(2)})', line)
        line = P2.sub(lambda m: f'bit32.bxor({m.group(1)},0)~=0 and {m.group(1)} or', line)
        line = P3.sub(lambda m: f'bit32.bxor({m.group(1)},{m.group(2)})', line)
        out.append(line)
    return '\n'.join(out)


def minify_and_fix(src: str) -> str:
    """Minify Lua source AND fix all ~ XOR operators for Roblox compat."""
    return fix_lua_xor(minify(src))
