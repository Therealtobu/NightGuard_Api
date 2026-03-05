"""
Night - Lua 5.1 Recursive Descent Parser
Produces an AST of ast_nodes types.
"""

from lexer import Lexer, LexError          
import ast_nodes as N                 

class ParseError(Exception):
    pass


# Operator precedence table (higher = binds tighter)
# from the Lua 5.1 reference manual
BINOP_PREC = {
    'or':  1,
    'and': 2,
    '<':3, '>':3, '<=':3, '>=':3, '==':3, '~=':3,
    '..':  4,   # right-assoc
    '+':5, '-':5,
    '*':6, '/':6, '//':6, '%':6,
    # ^ is handled specially (highest, right-assoc, tighter than unary)
}
RIGHT_ASSOC = frozenset({'..', '^'})

BINOPS = set(BINOP_PREC) | {'^'}


class Parser:
    def __init__(self, source: str):
        self.lex = Lexer(source)

    def parse(self) -> N.Block:
        block = self._parse_block()
        self.lex.consume(type_='eof')
        return block

    # ── Block / Statements ────────────────────────────────────────────────────

    def _parse_block(self) -> N.Block:
        stmts = []
        while True:
            tok = self.lex.peek()
            if tok.type == 'eof':
                break
            if tok.type == 'keyword' and tok.value in ('end','else','elseif','until'):
                break
            stmt = self._parse_stat()
            if stmt is not None:
                stmts.append(stmt)
            if isinstance(stmt, N.Return):
                self.lex.match(type_='op', value=';')
                break
        return N.Block(stmts)

    def _parse_stat(self):
        tok = self.lex.peek()

        if tok.type == 'op' and tok.value == ';':
            self.lex.next(); return None

        if tok.type == 'keyword':
            kw = tok.value
            if kw == 'return':   return self._parse_return()
            if kw == 'break':    self.lex.next(); return N.Break()
            if kw == 'do':       return self._parse_do()
            if kw == 'while':    return self._parse_while()
            if kw == 'repeat':   return self._parse_repeat()
            if kw == 'if':       return self._parse_if()
            if kw == 'for':      return self._parse_for()
            if kw == 'function': return self._parse_function()
            if kw == 'local':    return self._parse_local()
            if kw == 'goto':
                self.lex.next()
                self.lex.consume(type_='name')
                return None       # ignore goto

        # Label ::name::
        if tok.type == 'op' and tok.value == '::':
            self.lex.next()
            self.lex.consume(type_='name')
            self.lex.consume(type_='op', value='::')
            return None

        return self._parse_expr_stat()

    def _parse_return(self) -> N.Return:
        self.lex.consume(type_='keyword', value='return')
        values = []
        tok = self.lex.peek()
        end_tokens = {'end','else','elseif','until'}
        if not (tok.type == 'eof'
                or (tok.type == 'keyword' and tok.value in end_tokens)
                or (tok.type == 'op'      and tok.value == ';')):
            values = self._parse_explist()
        self.lex.match(type_='op', value=';')
        return N.Return(values)

    def _parse_do(self) -> N.Do:
        self.lex.consume(type_='keyword', value='do')
        body = self._parse_block()
        self.lex.consume(type_='keyword', value='end')
        return N.Do(body)

    def _parse_while(self) -> N.While:
        self.lex.consume(type_='keyword', value='while')
        test = self._parse_expr()
        self.lex.consume(type_='keyword', value='do')
        body = self._parse_block()
        self.lex.consume(type_='keyword', value='end')
        return N.While(test, body)

    def _parse_repeat(self) -> N.Repeat:
        self.lex.consume(type_='keyword', value='repeat')
        body = self._parse_block()
        self.lex.consume(type_='keyword', value='until')
        test = self._parse_expr()
        return N.Repeat(body, test)

    def _parse_if(self) -> N.If:
        self.lex.consume(type_='keyword', value='if')
        test = self._parse_expr()
        self.lex.consume(type_='keyword', value='then')
        body = self._parse_block()

        orelse = []
        while self.lex.check(type_='keyword', value='elseif'):
            self.lex.next()
            ei_test = self._parse_expr()
            self.lex.consume(type_='keyword', value='then')
            ei_body = self._parse_block()
            orelse.append(N.ElseIf(ei_test, ei_body))

        if self.lex.match(type_='keyword', value='else'):
            orelse.append(N.Else(self._parse_block()))

        self.lex.consume(type_='keyword', value='end')
        return N.If(test, body, orelse)

    def _parse_for(self):
        self.lex.consume(type_='keyword', value='for')
        first_tok = self.lex.consume(type_='name')
        first_name = N.Name(first_tok.value)

        if self.lex.check(type_='op', value='='):
            # Numeric for
            self.lex.next()
            start = self._parse_expr()
            self.lex.consume(type_='op', value=',')
            stop  = self._parse_expr()
            step  = None
            if self.lex.match(type_='op', value=','):
                step = self._parse_expr()
            self.lex.consume(type_='keyword', value='do')
            body = self._parse_block()
            self.lex.consume(type_='keyword', value='end')
            return N.Fornumeric(first_name, start, stop, step, body)

        # Generic for
        names = [first_name]
        while self.lex.match(type_='op', value=','):
            n = self.lex.consume(type_='name')
            names.append(N.Name(n.value))
        self.lex.consume(type_='keyword', value='in')
        iters = self._parse_explist()
        self.lex.consume(type_='keyword', value='do')
        body = self._parse_block()
        self.lex.consume(type_='keyword', value='end')
        return N.Forin(names, iters, body)

    def _parse_function(self):
        self.lex.consume(type_='keyword', value='function')
        # funcname ::= Name {'.' Name} [':' Name]
        tok = self.lex.consume(type_='name')
        name_expr = N.Name(tok.value)

        while self.lex.check(type_='op', value='.'):
            self.lex.next()
            field_tok = self.lex.consume(type_='name')
            name_expr = N.Field(name_expr, N.Name(field_tok.value))

        is_method = False
        method_name_tok = None
        if self.lex.match(type_='op', value=':'):
            method_name_tok = self.lex.consume(type_='name')
            is_method = True

        args, body = self._parse_funcbody()

        if is_method:
            return N.Method(name_expr, N.Name(method_name_tok.value), args, body)
        return N.Function(name_expr, args, body)

    def _parse_local(self):
        self.lex.consume(type_='keyword', value='local')
        if self.lex.match(type_='keyword', value='function'):
            name_tok = self.lex.consume(type_='name')
            args, body = self._parse_funcbody()
            return N.LocalFunction(N.Name(name_tok.value), args, body)
        # local varlist ['=' explist]
        targets = []
        tok = self.lex.consume(type_='name')
        targets.append(N.Name(tok.value))
        while self.lex.match(type_='op', value=','):
            t = self.lex.consume(type_='name')
            targets.append(N.Name(t.value))
        values = []
        if self.lex.match(type_='op', value='='):
            values = self._parse_explist()
        return N.LocalAssign(targets, values)

    def _parse_funcbody(self):
        self.lex.consume(type_='op', value='(')
        args = []
        if not self.lex.check(type_='op', value=')'):
            if self.lex.check(type_='op', value='...'):
                self.lex.next(); args.append(N.Vararg())
            else:
                tok = self.lex.consume(type_='name')
                args.append(N.Name(tok.value))
                while self.lex.match(type_='op', value=','):
                    if self.lex.check(type_='op', value='...'):
                        self.lex.next(); args.append(N.Vararg()); break
                    tok = self.lex.consume(type_='name')
                    args.append(N.Name(tok.value))
        self.lex.consume(type_='op', value=')')
        body = self._parse_block()
        self.lex.consume(type_='keyword', value='end')
        return args, body

    def _parse_expr_stat(self):
        """Assignment or function call statement."""
        expr = self._parse_suffixed_expr()

        if self.lex.check(type_='op', value=',') or self.lex.check(type_='op', value='='):
            targets = [expr]
            while self.lex.match(type_='op', value=','):
                targets.append(self._parse_suffixed_expr())
            self.lex.consume(type_='op', value='=')
            values = self._parse_explist()
            return N.Assign(targets, values)

        if not isinstance(expr, (N.Call, N.Invoke)):
            tok = self.lex.peek()
            raise ParseError(
                f"Syntax error near '{tok.value}' at line {tok.line}: "
                f"expected function call or assignment"
            )
        return expr

    # ── Expressions ───────────────────────────────────────────────────────────

    def _parse_explist(self) -> list:
        exprs = [self._parse_expr()]
        while self.lex.match(type_='op', value=','):
            exprs.append(self._parse_expr())
        return exprs

    def _parse_expr(self, min_prec: int = 0):
        """Precedence-climbing expression parser."""
        left = self._parse_unary()

        while True:
            tok = self.lex.peek()
            op  = tok.value

            # Is it a known binary op?
            is_binop = (
                (tok.type == 'keyword' and op in ('and','or')) or
                (tok.type == 'op'      and op in BINOPS)
            )
            if not is_binop:
                break

            prec = BINOP_PREC.get(op, 7)      # '^' gets 7 (handled in power)
            if op == '^': prec = 7
            if prec <= min_prec:
                break

            self.lex.next()
            if op in RIGHT_ASSOC:
                right = self._parse_expr(prec - 1)
            else:
                right = self._parse_expr(prec)
            left = N.BinOp(op, left, right)

        return left

    def _parse_unary(self):
        tok = self.lex.peek()
        if tok.type == 'keyword' and tok.value == 'not':
            self.lex.next()
            return N.UnOp('not', self._parse_unary())
        if tok.type == 'op' and tok.value == '-':
            self.lex.next()
            return N.UnOp('-', self._parse_unary())
        if tok.type == 'op' and tok.value == '#':
            self.lex.next()
            return N.UnOp('#', self._parse_unary())
        if tok.type == 'op' and tok.value == '~':
            self.lex.next()
            return N.UnOp('~', self._parse_unary())
        # Power binds tighter than unary per Lua spec
        return self._parse_power()

    def _parse_power(self):
        base = self._parse_suffixed_expr()
        if self.lex.check(type_='op', value='^'):
            self.lex.next()
            exp = self._parse_unary()          # right-assoc
            return N.BinOp('^', base, exp)
        return base

    def _parse_suffixed_expr(self):
        """Primary expr followed by field/index/call suffixes."""
        expr = self._parse_primary()
        while True:
            tok = self.lex.peek()
            if tok.type == 'op' and tok.value == '.':
                self.lex.next()
                field_tok = self.lex.consume(type_='name')
                expr = N.Field(expr, N.Name(field_tok.value))
            elif tok.type == 'op' and tok.value == '[':
                self.lex.next()
                key = self._parse_expr()
                self.lex.consume(type_='op', value=']')
                expr = N.Index(expr, key)
            elif tok.type == 'op' and tok.value == ':':
                self.lex.next()
                meth = self.lex.consume(type_='name')
                args = self._parse_call_args()
                expr = N.Invoke(expr, N.Name(meth.value), args)
            elif (tok.type == 'op' and tok.value in ('(', '{')) \
                    or tok.type == 'string':
                args = self._parse_call_args()
                expr = N.Call(expr, args)
            else:
                break
        return expr

    def _parse_call_args(self) -> list:
        tok = self.lex.peek()
        if tok.type == 'op' and tok.value == '(':
            self.lex.next()
            if self.lex.check(type_='op', value=')'):
                self.lex.next(); return []
            args = self._parse_explist()
            self.lex.consume(type_='op', value=')')
            return args
        if tok.type == 'op' and tok.value == '{':
            return [self._parse_table()]
        if tok.type == 'string':
            tok = self.lex.next()
            return [N.String(tok.value)]
        raise ParseError(f"Expected call args at line {tok.line}")

    def _parse_primary(self):
        tok = self.lex.peek()

        if tok.type == 'name':
            self.lex.next(); return N.Name(tok.value)

        if tok.type == 'keyword':
            if tok.value == 'nil':      self.lex.next(); return N.NilExpr()
            if tok.value == 'true':     self.lex.next(); return N.TrueExpr()
            if tok.value == 'false':    self.lex.next(); return N.FalseExpr()
            if tok.value == 'function':
                self.lex.next()
                args, body = self._parse_funcbody()
                return N.AnonymousFunction(args, body)

        if tok.type == 'number':
            self.lex.next(); return N.Number(tok.value)

        if tok.type == 'string':
            self.lex.next(); return N.String(tok.value)

        if tok.type == 'op' and tok.value == '(':
            self.lex.next()
            expr = self._parse_expr()
            self.lex.consume(type_='op', value=')')
            return expr

        if tok.type == 'op' and tok.value == '{':
            return self._parse_table()

        if tok.type == 'op' and tok.value == '...':
            self.lex.next(); return N.Vararg()

        raise ParseError(
            f"Unexpected token {tok.type!r}={tok.value!r} at line {tok.line}"
        )

    def _parse_table(self) -> N.Table:
        self.lex.consume(type_='op', value='{')
        fields = []
        while not self.lex.check(type_='op', value='}'):
            tok = self.lex.peek()
            if tok.type == 'op' and tok.value == '[':
                # [expr] = expr
                self.lex.next()
                key = self._parse_expr()
                self.lex.consume(type_='op', value=']')
                self.lex.consume(type_='op', value='=')
                val = self._parse_expr()
                fields.append(N.TableIndex(key, val))
            elif tok.type == 'name' and self.lex.peek(1).value == '=':
                # name = expr
                name_tok = self.lex.next()
                self.lex.next()                   # consume '='
                val = self._parse_expr()
                fields.append(N.TableField(N.Name(name_tok.value), val))
            else:
                fields.append(self._parse_expr())
            # field separator
            if not self.lex.match(type_='op', value=','):
                self.lex.match(type_='op', value=';')
                if not (self.lex.check(type_='op', value=',') or
                        self.lex.check(type_='op', value='}')):
                    break
        self.lex.consume(type_='op', value='}')
        return N.Table(fields)


def parse(source: str) -> N.Block:
    """Convenience: parse source and return the top-level Block."""
    return Parser(source).parse()
