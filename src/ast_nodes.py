"""
Night - Lua AST Node Definitions
"""

class Node:
    pass

# ─── Statements ───────────────────────────────────────────────────────────────

class Block(Node):
    def __init__(self, body):
        self.body = body

class Assign(Node):
    def __init__(self, targets, values):
        self.targets = targets
        self.values = values

class LocalAssign(Node):
    def __init__(self, targets, values):
        self.targets = targets
        self.values = values

class Do(Node):
    def __init__(self, body):
        self.body = body

class While(Node):
    def __init__(self, test, body):
        self.test = test
        self.body = body

class Repeat(Node):
    def __init__(self, body, test):
        self.body = body
        self.test = test

class If(Node):
    def __init__(self, test, body, orelse):
        self.test = test
        self.body = body
        self.orelse = orelse  # list of ElseIf/Else

class ElseIf(Node):
    def __init__(self, test, body):
        self.test = test
        self.body = body

class Else(Node):
    def __init__(self, body):
        self.body = body

class Fornumeric(Node):
    def __init__(self, target, start, stop, step, body):
        self.target = target
        self.start = start
        self.stop = stop
        self.step = step
        self.body = body

class Forin(Node):
    def __init__(self, targets, iter, body):
        self.targets = targets
        self.iter = iter
        self.body = body

class Function(Node):
    """function name(...) body end"""
    def __init__(self, name, args, body):
        self.name = name
        self.args = args
        self.body = body

class LocalFunction(Node):
    """local function name(...) body end"""
    def __init__(self, name, args, body):
        self.name = name
        self.args = args
        self.body = body

class Method(Node):
    """function obj:method(...) body end"""
    def __init__(self, source, name, args, body):
        self.source = source
        self.name = name
        self.args = args
        self.body = body

class Return(Node):
    def __init__(self, values):
        self.values = values

class Break(Node):
    pass

# ─── Expressions ──────────────────────────────────────────────────────────────

class Name(Node):
    def __init__(self, id):
        self.id = id

class Number(Node):
    def __init__(self, n):
        self.n = n

class String(Node):
    def __init__(self, s):
        self.s = s

class TrueExpr(Node):
    pass

class FalseExpr(Node):
    pass

class NilExpr(Node):
    pass

class Vararg(Node):
    pass

class BinOp(Node):
    def __init__(self, op, left, right):
        self.op = op
        self.left = left
        self.right = right

class UnOp(Node):
    def __init__(self, op, operand):
        self.op = op
        self.operand = operand

class Call(Node):
    def __init__(self, func, args):
        self.func = func
        self.args = args

class Invoke(Node):
    """Method call: obj:method(args)"""
    def __init__(self, source, func, args):
        self.source = source
        self.func = func
        self.args = args

class Index(Node):
    """Table index: tbl[key]"""
    def __init__(self, value, key):
        self.value = value
        self.key = key

class Field(Node):
    """Field access: tbl.name"""
    def __init__(self, value, key):
        self.value = value
        self.key = key  # Name node

class AnonymousFunction(Node):
    def __init__(self, args, body):
        self.args = args
        self.body = body

class Table(Node):
    def __init__(self, fields):
        self.fields = fields

class TableField(Node):
    """name = expr in table constructor"""
    def __init__(self, key, value):
        self.key = key   # Name node
        self.value = value

class TableIndex(Node):
    """[expr] = expr in table constructor"""
    def __init__(self, key, value):
        self.key = key
        self.value = value
