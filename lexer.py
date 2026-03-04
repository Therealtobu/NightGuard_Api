"""
Night - Lua 5.1 Lexer
Tokenizes Lua source code.
"""

KEYWORDS = frozenset({
    'and', 'break', 'do', 'else', 'elseif', 'end',
    'false', 'for', 'function', 'goto', 'if', 'in',
    'local', 'nil', 'not', 'or', 'repeat', 'return',
    'then', 'true', 'until', 'while'
})

class Token:
    __slots__ = ('type', 'value', 'line')
    def __init__(self, type_, value, line):
        self.type  = type_
        self.value = value
        self.line  = line
    def __repr__(self):
        return f'Token({self.type}, {self.value!r}, L{self.line})'

class LexError(Exception):
    pass

class Lexer:
    def __init__(self, source: str):
        self.source = source
        self._tokens: list[Token] = []
        self._pos = 0
        self._tokenize()

    # ── Public API ────────────────────────────────────────────────────────────

    def peek(self, offset: int = 0) -> Token:
        idx = self._pos + offset
        if idx < len(self._tokens):
            return self._tokens[idx]
        return self._tokens[-1]          # EOF sentinel

    def next(self) -> Token:
        tok = self._tokens[self._pos]
        if self._pos < len(self._tokens) - 1:
            self._pos += 1
        return tok

    def consume(self, type_=None, value=None) -> Token:
        tok = self.peek()
        if type_ and tok.type != type_:
            raise LexError(
                f"Expected token type '{type_}', got '{tok.type}' "
                f"({tok.value!r}) at line {tok.line}"
            )
        if value is not None and tok.value != value:
            raise LexError(
                f"Expected {value!r}, got {tok.value!r} at line {tok.line}"
            )
        return self.next()

    def check(self, type_=None, value=None) -> bool:
        tok = self.peek()
        if type_ and tok.type != type_:
            return False
        if value is not None and tok.value != value:
            return False
        return True

    def match(self, type_=None, value=None) -> bool:
        if self.check(type_=type_, value=value):
            self.next()
            return True
        return False

    # ── Tokenizer ─────────────────────────────────────────────────────────────

    def _tokenize(self):
        src = self.source
        pos = 0
        line = 1
        toks: list[Token] = []
        L = len(src)

        while pos < L:
            c = src[pos]

            # Whitespace
            if c in ' \t\r':
                pos += 1
                continue
            if c == '\n':
                line += 1
                pos += 1
                continue

            # Comments
            if src[pos:pos+2] == '--':
                pos += 2
                if pos < L and src[pos] == '[':
                    level, is_long = self._check_long_bracket(src, pos)
                    if is_long:
                        _, pos, line = self._read_long_string(src, pos, line, level)
                        continue
                # Single-line comment
                while pos < L and src[pos] != '\n':
                    pos += 1
                continue

            # Long strings
            if c == '[':
                level, is_long = self._check_long_bracket(src, pos)
                if is_long:
                    val, pos, line = self._read_long_string(src, pos, line, level)
                    toks.append(Token('string', val, line))
                    continue

            # Quoted strings
            if c in ('"', "'"):
                val, pos = self._read_quoted_string(src, pos, line)
                toks.append(Token('string', val, line))
                continue

            # Numbers
            if c.isdigit() or (c == '.' and pos+1 < L and src[pos+1].isdigit()):
                val, pos = self._read_number(src, pos)
                toks.append(Token('number', val, line))
                continue

            # Identifiers / keywords
            if c.isalpha() or c == '_':
                start = pos
                while pos < L and (src[pos].isalnum() or src[pos] == '_'):
                    pos += 1
                word = src[start:pos]
                kind = 'keyword' if word in KEYWORDS else 'name'
                toks.append(Token(kind, word, line))
                continue

            # Operators (longest match first)
            three = src[pos:pos+3]
            if three == '...':
                toks.append(Token('op', '...', line)); pos += 3; continue

            two = src[pos:pos+2]
            if two in ('..', '==', '~=', '<=', '>=', '::', '//', '<<', '>>'):
                toks.append(Token('op', two, line)); pos += 2; continue

            if c in '+-*/%^&|~<>=(){}[];:,.#[]':
                toks.append(Token('op', c, line)); pos += 1; continue

            raise LexError(f"Unexpected character {c!r} at line {line}")

        toks.append(Token('eof', None, line))
        self._tokens = toks
        self._pos = 0

    def _check_long_bracket(self, src, pos):
        """Returns (level, is_long) for a potential long bracket starting at pos."""
        if pos >= len(src) or src[pos] != '[':
            return 0, False
        i = pos + 1
        level = 0
        while i < len(src) and src[i] == '=':
            level += 1; i += 1
        if i < len(src) and src[i] == '[':
            return level, True
        return 0, False

    def _read_long_string(self, src, pos, line, level):
        """Read a long string/comment. Returns (content, new_pos, new_line)."""
        # Skip opening [==..==[
        pos += level + 2          # [ + level×= + [
        # Strip leading newline
        if pos < len(src) and src[pos] == '\n':
            line += 1; pos += 1
        elif pos < len(src) and src[pos] == '\r':
            pos += 1
            if pos < len(src) and src[pos] == '\n':
                pos += 1
            line += 1

        close = ']' + '=' * level + ']'
        idx = src.find(close, pos)
        if idx == -1:
            raise LexError(f"Unfinished long string starting at line {line}")
        content = src[pos:idx]
        line += content.count('\n')
        return content, idx + len(close), line

    def _read_quoted_string(self, src, pos, line):
        """Read a single- or double-quoted string."""
        quote = src[pos]; pos += 1
        chars = []
        L = len(src)
        while pos < L:
            c = src[pos]
            if c == quote:
                return ''.join(chars), pos + 1
            if c == '\n':
                raise LexError(f"Unfinished string at line {line}")
            if c != '\\':
                chars.append(c); pos += 1; continue
            # Escape sequence
            pos += 1
            if pos >= L:
                raise LexError("Unfinished escape sequence")
            e = src[pos]; pos += 1
            ESC = {
                'a': '\a', 'b': '\b', 'f': '\f', 'n': '\n',
                'r': '\r', 't': '\t', 'v': '\v', '\\': '\\',
                "'": "'",  '"': '"',  '\n': '\n', '\r': '\n',
            }
            if e in ESC:
                chars.append(ESC[e])
            elif e == '0':
                chars.append('\0')
            elif e.isdigit():
                num = e
                for _ in range(2):
                    if pos < L and src[pos].isdigit():
                        num += src[pos]; pos += 1
                chars.append(chr(int(num) & 0xFF))
            elif e == 'x':
                h = src[pos:pos+2]; pos += 2
                chars.append(chr(int(h, 16)))
            elif e == 'z':            # skip whitespace (Lua 5.2+)
                while pos < L and src[pos] in ' \t\r\n':
                    if src[pos] == '\n': line += 1
                    pos += 1
            else:
                chars.append(e)
        raise LexError(f"Unfinished string at line {line}")

    def _read_number(self, src, pos):
        """Read a numeric literal. Returns (value, new_pos)."""
        start = pos
        L = len(src)
        # Hex
        if src[pos:pos+2] in ('0x', '0X'):
            pos += 2
            while pos < L and (src[pos] in '0123456789abcdefABCDEF_'):
                pos += 1
            # Optional float suffix for Lua 5.3 hex floats (p/P)
            if pos < L and src[pos] in 'pP':
                pos += 1
                if pos < L and src[pos] in '+-': pos += 1
                while pos < L and src[pos].isdigit(): pos += 1
                return float.fromhex(src[start:pos].replace('_', '')), pos
            return int(src[start:pos].replace('_', ''), 16), pos
        # Decimal
        while pos < L and (src[pos].isdigit() or src[pos] == '_'):
            pos += 1
        is_float = False
        if pos < L and src[pos] == '.':
            is_float = True; pos += 1
            while pos < L and (src[pos].isdigit() or src[pos] == '_'):
                pos += 1
        if pos < L and src[pos] in 'eE':
            is_float = True; pos += 1
            if pos < L and src[pos] in '+-': pos += 1
            while pos < L and src[pos].isdigit(): pos += 1
        s = src[start:pos].replace('_', '')
        return (float(s) if is_float else int(s)), pos
