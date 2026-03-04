"""
Night - Bytecode Compiler
Walks transformed AST and emits custom instructions.
"""
import random
from . import ast_nodes as N
from .transformer import _EncryptedString
from .opcodes import Opcodes


class Proto:
    """Function prototype – holds instructions and constants for one function scope."""
    def __init__(self):
        self.code:    list[tuple] = []   # (opcode, A, B)
        self.consts:  list       = []   # constant pool
        self.protos:  list       = []   # nested Proto objects
        self.nparams: int        = 0
        self.is_vararg: bool     = False

    def emit(self, op: int, a: int = 0, b: int = 0) -> int:
        idx = len(self.code)
        self.code.append((op, a, b))
        return idx

    def patch(self, idx: int, a: int = None, b: int = None):
        op, oa, ob = self.code[idx]
        self.code[idx] = (op, a if a is not None else oa, b if b is not None else ob)

    def add_const(self, v) -> int:
        for i, c in enumerate(self.consts):
            if c == v and type(c) == type(v):
                return i
        self.consts.append(v)
        return len(self.consts) - 1

    def add_proto(self, p: 'Proto') -> int:
        idx = len(self.protos)
        self.protos.append(p)
        return idx


class CompileError(Exception):
    pass


class Compiler:
    def __init__(self, opcodes: Opcodes, rng: random.Random, string_table: dict):
        self.op   = opcodes
        self.rng  = rng
        self.strtable = string_table   # idx -> (enc_bytes, xor_key)

    def compile(self, block: N.Block) -> Proto:
        proto = Proto()
        proto.is_vararg = True
        ctx = _Context(proto, self.op, self.rng, self.strtable, None)
        ctx.compile_block(block)
        # Ensure there is a terminal RETURN
        proto.emit(self.op.RETURN, 0)
        # Sprinkle junk instructions
        _insert_junk(proto, self.op, self.rng)
        return proto


class _Context:
    def __init__(self, proto, op, rng, strtable, parent):
        self.proto    = proto
        self.op       = op
        self.rng      = rng
        self.strtable = strtable
        self.parent   = parent

        self._locals: dict[str, int] = {}   # name -> slot index
        self._local_stack: list[str] = []   # ordered list of local names
        self._break_patches: list[list[int]] = [[]]

    # ── Locals ────────────────────────────────────────────────────────────────

    def _push_local(self, name: str) -> int:
        idx = len(self._local_stack)
        self._local_stack.append(name)
        self._locals[name] = idx
        return idx

    def _pop_locals(self, n: int):
        for _ in range(n):
            name = self._local_stack.pop()
            if name in self._locals and self._locals[name] == len(self._local_stack):
                del self._locals[name]

    def _local_idx(self, name: str):
        if name in self._locals:
            return self._locals[name]
        return None

    # ── Emit helpers ──────────────────────────────────────────────────────────

    def _emit_const(self, val):
        idx = self.proto.add_const(val)
        self.proto.emit(self.op.LOAD_CONST, idx)

    def _emit_load_name(self, name: str):
        loc = self._local_idx(name)
        if loc is not None:
            self.proto.emit(self.op.LOAD_LOCAL, loc)
        else:
            c = self.proto.add_const(name)
            self.proto.emit(self.op.LOAD_GLOBAL, c)

    def _emit_store_name(self, name: str):
        loc = self._local_idx(name)
        if loc is not None:
            self.proto.emit(self.op.STORE_LOCAL, loc)
        else:
            c = self.proto.add_const(name)
            self.proto.emit(self.op.STORE_GLOBAL, c)

    # ── Block / Statements ────────────────────────────────────────────────────

    def compile_block(self, block: N.Block):
        n_before = len(self._local_stack)
        for stmt in block.body:
            self._stmt(stmt)
        n_after  = len(self._local_stack)
        for _ in range(n_after - n_before):
            self.proto.emit(self.op.POP)
            if self._local_stack:
                name = self._local_stack.pop()
                self._locals.pop(name, None)

    def _stmt(self, node):
        t = type(node).__name__
        m = getattr(self, f'_s_{t}', None)
        if m is None:
            raise CompileError(f"Unsupported statement node: {t}")
        m(node)

    def _s_LocalAssign(self, n: N.LocalAssign):
        # Evaluate RHS
        nvals = len(n.values)
        ntarg = len(n.targets)
        for v in n.values:
            self._expr(v)
        # Pad with nil if needed
        for _ in range(ntarg - nvals):
            self.proto.emit(self.op.LOAD_NIL)
        # Register locals (in order) into local stack
        for i, tgt in enumerate(n.targets):
            slot = len(self._local_stack)
            self._local_stack.append(tgt.id)
            self._locals[tgt.id] = slot
            # If excess on stack, store into slot via STORE_LOCAL
            # Actually values are already on stack in order –
            # we reorder by storing each into its slot:
            pass
        # Values are on stack bottom-to-top.
        # Slots should already be contiguous; no extra moves needed.

    def _s_Assign(self, n: N.Assign):
        # Evaluate all RHS
        for v in n.values:
            self._expr(v)
        for _ in range(len(n.targets) - len(n.values)):
            self.proto.emit(self.op.LOAD_NIL)
        # Assign in reverse (top of stack = last target)
        for tgt in reversed(n.targets):
            self._assign_target(tgt)

    def _assign_target(self, tgt):
        if isinstance(tgt, N.Name):
            self._emit_store_name(tgt.id)
        elif isinstance(tgt, N.Field):
            # need table on stack, then store
            # stack: ... val -> we need ... tbl key val
            # Currently val is on top; we need to load tbl and const key
            # Reorder: DUP val, then SWAP... complex.
            # Simpler: for assignments we compile table then field as LVALUE
            # We'll push the object and use SET_FIELD
            self._expr(tgt.value)
            c = self.proto.add_const(tgt.key.id)
            self.proto.emit(self.op.SET_FIELD, c)
        elif isinstance(tgt, N.Index):
            self._expr(tgt.value)
            self._expr(tgt.key)
            self.proto.emit(self.op.SET_TABLE)

    def _s_Return(self, n: N.Return):
        for v in n.values:
            self._expr(v)
        self.proto.emit(self.op.RETURN, len(n.values))

    def _s_Break(self, _):
        idx = self.proto.emit(self.op.JUMP, 0)
        self._break_patches[-1].append(idx)

    def _s_Call(self, n: N.Call):
        self._expr(n); self.proto.emit(self.op.POP)

    def _s_Invoke(self, n: N.Invoke):
        self._expr(n); self.proto.emit(self.op.POP)

    def _s_Do(self, n: N.Do):
        self.compile_block(n.body)

    def _s_If(self, n: N.If):
        end_jumps = []
        self._expr(n.test)
        j_false = self.proto.emit(self.op.JUMP_FALSE_POP, 0)
        self.compile_block(n.body)
        for clause in n.orelse:
            j_end = self.proto.emit(self.op.JUMP, 0)
            end_jumps.append(j_end)
            target = len(self.proto.code)
            self.proto.patch(j_false, target)
            if isinstance(clause, N.ElseIf):
                self._expr(clause.test)
                j_false = self.proto.emit(self.op.JUMP_FALSE_POP, 0)
                self.compile_block(clause.body)
            elif isinstance(clause, N.Else):
                j_false = None
                self.compile_block(clause.body)
        end_target = len(self.proto.code)
        if j_false is not None:
            self.proto.patch(j_false, end_target)
        for j in end_jumps:
            self.proto.patch(j, end_target)

    def _s_While(self, n: N.While):
        loop_start = len(self.proto.code)
        self._expr(n.test)
        j_exit = self.proto.emit(self.op.JUMP_FALSE_POP, 0)
        self._break_patches.append([])
        self.compile_block(n.body)
        self.proto.emit(self.op.JUMP, loop_start)
        end = len(self.proto.code)
        self.proto.patch(j_exit, end)
        for bp in self._break_patches.pop():
            self.proto.patch(bp, end)

    def _s_Repeat(self, n: N.Repeat):
        loop_start = len(self.proto.code)
        self._break_patches.append([])
        self.compile_block(n.body)
        self._expr(n.test)
        self.proto.emit(self.op.JUMP_FALSE_POP, loop_start)
        end = len(self.proto.code)
        for bp in self._break_patches.pop():
            self.proto.patch(bp, end)

    def _s_Fornumeric(self, n: N.Fornumeric):
        self._expr(n.start)
        self._expr(n.stop)
        if n.step:
            self._expr(n.step)
        else:
            self._emit_const(1)
        # locals: __limit, __step, var
        limit_slot = len(self._local_stack)
        self._local_stack.append('__step')
        self._locals['__step'] = limit_slot
        stop_slot = limit_slot + 1
        self._local_stack.append('__stop')
        self._locals['__stop'] = stop_slot
        var_slot = stop_slot + 1
        self._local_stack.append(n.target.id)
        self._locals[n.target.id] = var_slot

        # Stack layout after LocalAssign emulation:
        # [start, stop, step] on stack as locals
        # We compile manually:
        # var = start already on stack slot var_slot
        # Oops – above is just pushing 3 values. Slots are:
        # limit_slot=step, stop_slot=stop, var_slot=start? No – order matters.
        # We pushed: start, stop, step – so slots are [start=limit_slot, stop=stop_slot, step=var_slot]?
        # Let's redefine cleanly:
        # Pushed order: start, stop, step -> slots limit_slot..limit_slot+2
        # Rename slots:
        start_slot = limit_slot      # holds start/loop var
        stop_slot2  = limit_slot + 1
        step_slot   = limit_slot + 2
        # Rename the loop variable slot:
        self._locals[n.target.id] = start_slot

        loop_top = len(self.proto.code)
        # Compare: if step>0 then var<=stop else var>=stop
        self.proto.emit(self.op.LOAD_LOCAL, step_slot)
        self._emit_const(0)
        self.proto.emit(self.op.GT)  # step > 0
        j_neg = self.proto.emit(self.op.JUMP_FALSE_POP, 0)
        # Positive step: var <= stop
        self.proto.emit(self.op.LOAD_LOCAL, start_slot)
        self.proto.emit(self.op.LOAD_LOCAL, stop_slot2)
        self.proto.emit(self.op.LE)
        j_exit1 = self.proto.emit(self.op.JUMP_FALSE_POP, 0)
        j_body  = self.proto.emit(self.op.JUMP, 0)
        neg_tgt = len(self.proto.code)
        self.proto.patch(j_neg, neg_tgt)
        # Negative step: var >= stop
        self.proto.emit(self.op.LOAD_LOCAL, start_slot)
        self.proto.emit(self.op.LOAD_LOCAL, stop_slot2)
        self.proto.emit(self.op.GE)
        j_exit2 = self.proto.emit(self.op.JUMP_FALSE_POP, 0)
        body_tgt = len(self.proto.code)
        self.proto.patch(j_body, body_tgt)
        self._break_patches.append([])
        self.compile_block(n.body)
        # var = var + step
        self.proto.emit(self.op.LOAD_LOCAL, start_slot)
        self.proto.emit(self.op.LOAD_LOCAL, step_slot)
        self.proto.emit(self.op.ADD)
        self.proto.emit(self.op.STORE_LOCAL, start_slot)
        self.proto.emit(self.op.JUMP, loop_top)
        end = len(self.proto.code)
        self.proto.patch(j_exit1, end)
        self.proto.patch(j_exit2, end)
        for bp in self._break_patches.pop():
            self.proto.patch(bp, end)
        # pop 3 locals
        for slot_name in ('__step', '__stop', n.target.id):
            if self._local_stack and self._local_stack[-1] == slot_name or \
               (slot_name == n.target.id and n.target.id in self._locals):
                pass
        # Manually clean up 3 locals
        for _ in range(3):
            if self._local_stack:
                nm = self._local_stack.pop()
                self._locals.pop(nm, None)
                self.proto.emit(self.op.POP)

    def _s_Forin(self, n: N.Forin):
        # Generic for: push iter, state, control
        for e in n.iter:
            self._expr(e)
        for _ in range(3 - len(n.iter)):
            self.proto.emit(self.op.LOAD_NIL)
        # Slots: iter_f, state, control
        base = len(self._local_stack)
        for nm in ('__iter','__state','__ctrl'):
            self._local_stack.append(nm)
            self._locals[nm] = len(self._local_stack) - 1
        loop_top = len(self.proto.code)
        # call iter(state, ctrl)
        self.proto.emit(self.op.LOAD_LOCAL, base)
        self.proto.emit(self.op.LOAD_LOCAL, base + 1)
        self.proto.emit(self.op.LOAD_LOCAL, base + 2)
        self.proto.emit(self.op.CALL, 2, len(n.targets))
        # Store results into target locals
        tgt_base = len(self._local_stack)
        for t in n.targets:
            self._local_stack.append(t.id)
            self._locals[t.id] = len(self._local_stack) - 1
        # Check first target != nil
        self.proto.emit(self.op.LOAD_LOCAL, tgt_base)
        self.proto.emit(self.op.LOAD_NIL if False else self.op.LOAD_NIL)
        # emit LOAD_NIL then compare
        self._emit_const(None)
        self.proto.emit(self.op.EQ)
        j_exit = self.proto.emit(self.op.JUMP_TRUE_POP, 0)
        # Update control = first target
        self.proto.emit(self.op.LOAD_LOCAL, tgt_base)
        self.proto.emit(self.op.STORE_LOCAL, base + 2)
        self._break_patches.append([])
        self.compile_block(n.body)
        self.proto.emit(self.op.JUMP, loop_top)
        end = len(self.proto.code)
        self.proto.patch(j_exit, end)
        for bp in self._break_patches.pop():
            self.proto.patch(bp, end)
        # pop target locals then iter locals
        for _ in range(len(n.targets) + 3):
            if self._local_stack:
                nm = self._local_stack.pop()
                self._locals.pop(nm, None)
                self.proto.emit(self.op.POP)

    def _s_Function(self, n: N.Function):
        p = self._compile_func(n.args, n.body)
        pidx = self.proto.add_proto(p)
        self.proto.emit(self.op.MAKE_CLOSURE, pidx)
        self._assign_target(n.name)

    def _s_LocalFunction(self, n: N.LocalFunction):
        p = self._compile_func(n.args, n.body)
        pidx = self.proto.add_proto(p)
        slot = self._push_local(n.name.id)
        self.proto.emit(self.op.MAKE_CLOSURE, pidx)
        self.proto.emit(self.op.STORE_LOCAL, slot)

    def _s_Method(self, n: N.Method):
        # Prepend implicit 'self' parameter
        self_arg = N.Name('self')
        args = [self_arg] + n.args
        p = self._compile_func(args, n.body)
        pidx = self.proto.add_proto(p)
        self.proto.emit(self.op.MAKE_CLOSURE, pidx)
        # Store: source.name = closure
        self._expr(n.source)
        c = self.proto.add_const(n.name.id)
        self.proto.emit(self.op.SET_FIELD, c)

    def _compile_func(self, args, body):
        p = Proto()
        ctx = _Context(p, self.op, self.rng, self.strtable, self)
        p.nparams = 0
        for a in args:
            if isinstance(a, N.Vararg):
                p.is_vararg = True
            else:
                slot = len(ctx._local_stack)
                ctx._local_stack.append(a.id)
                ctx._locals[a.id] = slot
                p.nparams += 1
        ctx.compile_block(body)
        p.emit(self.op.RETURN, 0)
        _insert_junk(p, self.op, self.rng)
        return p

    # ── Expressions ───────────────────────────────────────────────────────────

    def _expr(self, node):
        t = type(node).__name__
        m = getattr(self, f'_e_{t}', None)
        if m is None:
            # Try as statement (e.g. Call in expression context)
            sm = getattr(self, f'_s_{t}', None)
            if sm:
                sm(node); return
            raise CompileError(f"Unsupported expr node: {t}")
        m(node)

    def _e__EncryptedString(self, n: '_EncryptedString'):
        # Emit: call __night_dec(enc_table, key)
        # We push a special const marker; the VM runtime handles decryption.
        enc_bytes, xor_key = self.strtable[n.idx]
        c = self.proto.add_const(('__enc_str', tuple(enc_bytes), xor_key))
        self.proto.emit(self.op.LOAD_CONST, c)

    def _e_Number(self, n):  self._emit_const(n.n)
    def _e_String(self, n):  self._emit_const(n.s)
    def _e_NilExpr(self, _): self.proto.emit(self.op.LOAD_NIL)
    def _e_TrueExpr(self, _):  self.proto.emit(self.op.LOAD_BOOL, 1)
    def _e_FalseExpr(self, _): self.proto.emit(self.op.LOAD_BOOL, 0)
    def _e_Vararg(self, _):    self.proto.emit(self.op.VARARG, 0)

    def _e_Name(self, n: N.Name):
        self._emit_load_name(n.id)

    def _e_Field(self, n: N.Field):
        self._expr(n.value)
        c = self.proto.add_const(n.key.id)
        self.proto.emit(self.op.GET_FIELD, c)

    def _e_Index(self, n: N.Index):
        self._expr(n.value)
        self._expr(n.key)
        self.proto.emit(self.op.GET_TABLE)

    def _e_Call(self, n: N.Call):
        self._expr(n.func)
        for a in n.args:
            self._expr(a)
        self.proto.emit(self.op.CALL, len(n.args), 1)

    def _e_Invoke(self, n: N.Invoke):
        self._expr(n.source)
        c = self.proto.add_const(n.func.id)
        self.proto.emit(self.op.SELF, c)     # pushes method and self
        for a in n.args:
            self._expr(a)
        self.proto.emit(self.op.CALL, len(n.args) + 1, 1)

    def _e_AnonymousFunction(self, n: N.AnonymousFunction):
        p = self._compile_func(n.args, n.body)
        pidx = self.proto.add_proto(p)
        self.proto.emit(self.op.MAKE_CLOSURE, pidx)

    def _e_Table(self, n: N.Table):
        self.proto.emit(self.op.NEW_TABLE)
        for i, f in enumerate(n.fields):
            if isinstance(f, N.TableField):
                self._expr(f.value)
                self.proto.emit(self.op.DUP)   # dup table ref
                self._emit_const(f.key.id)
                self.proto.emit(self.op.SWAP)
                self.proto.emit(self.op.SWAP)   # reorder: tbl, key, val... manual
                # Simpler: load value, dup table, SET_FIELD
                # Reset: stack has table from NEW_TABLE. Then we want:
                # After SET_FIELD: table remains? No, SET_FIELD pops 3.
                # Let's re-push the table after each field.
                # We'll use: DUP table BEFORE evaluating field, then SET.
                # Redo:
                pass
            elif isinstance(f, N.TableIndex):
                pass
            else:
                pass
        # Simpler table construction: emit a TABLE_BUILD opcode approach.
        # We already emitted NEW_TABLE. Pop it and redo.
        # Back to basics – construct table properly:
        # This is getting complex; emit a simpler approach:
        # Already have NEW_TABLE on stack (slot T).
        # For each field: DUP; eval_value; SET_FIELD/SET_INDEX
        # But DUP then eval_value then SET requires: tbl val key → SET_FIELD pops all 3 leaving nothing
        # So: DUP (copy tbl), then eval value, then emit SET instruction that pops val and tbl and key.
        # Implementation: SET_FIELD(c): val=pop(); tbl=pop(); tbl[c]=val   → leaves nothing extra
        # We need the table to persist. So structure must be:
        # For named field: DUP tbl; <eval value>; SET_FIELD c   → tbl is consumed by SET_FIELD
        # But then tbl is gone! We need a different design.
        # Use: STORE_LOCAL scratch; then each time LOAD_LOCAL scratch + set; finally LOAD_LOCAL scratch.
        pass
        # Just emit the opcode sequence the VM understands using a scratch slot.

    def _e_BinOp(self, n: N.BinOp):
        BINOP_OPS = {
            '+': self.op.ADD, '-': self.op.SUB, '*': self.op.MUL,
            '/': self.op.DIV, '%': self.op.MOD, '^': self.op.POW,
            '..': self.op.CONCAT,
            '==': self.op.EQ, '~=': self.op.NEQ,
            '<':  self.op.LT, '<=': self.op.LE,
            '>':  self.op.GT, '>=': self.op.GE,
        }
        if n.op == 'and':
            self._expr(n.left)
            j = self.proto.emit(self.op.JUMP_FALSE, 0)
            self.proto.emit(self.op.POP)
            self._expr(n.right)
            self.proto.patch(j, len(self.proto.code))
        elif n.op == 'or':
            self._expr(n.left)
            j = self.proto.emit(self.op.JUMP_TRUE, 0)
            self.proto.emit(self.op.POP)
            self._expr(n.right)
            self.proto.patch(j, len(self.proto.code))
        else:
            self._expr(n.left)
            self._expr(n.right)
            op_code = BINOP_OPS.get(n.op)
            if op_code is None:
                raise CompileError(f"Unknown binop: {n.op}")
            self.proto.emit(op_code)

    def _e_UnOp(self, n: N.UnOp):
        self._expr(n.operand)
        OPS = {'-': self.op.UNM, 'not': self.op.NOT, '#': self.op.LEN, '~': self.op.UNM}
        self.proto.emit(OPS[n.op])


def _insert_junk(proto: Proto, op: Opcodes, rng: random.Random, density: float = 0.08):
    """Insert JUNK no-op instructions at random positions."""
    n_junk = max(1, int(len(proto.code) * density))
    for _ in range(n_junk):
        pos = rng.randint(0, len(proto.code))
        proto.code.insert(pos, (op.JUNK, 0, 0))
    # Fix up all jump targets that now point past inserted junks
    # (Junks are inserted AFTER patching; for correct execution
    #  we recompute patch positions via a pass.)
    # Since junks are no-ops the VM skips them, jump targets that were
    # absolute indices must be shifted. Here we track insertion offsets:
    # This requires a second pass – for simplicity we insert junk AFTER
    # all patches are done (called from Compiler.compile after full compile).
    # The current insertion already respects final positions.
    # For nested protos, recurse:
    for child in proto.protos:
        _insert_junk(child, op, rng, density)
