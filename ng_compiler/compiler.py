import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
"""
NightGuard V2 - Bytecode Compiler
Walks transformed AST, emits packed instructions into Proto objects.
"""
import random, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import ast_nodes as N
from ng_transforms.string_encrypt import EncryptedStringNode
from ng_compiler.proto import Proto
from ng_compiler.opcodes import Opcodes

class CompileError(Exception): pass

class Compiler:
    def __init__(self, opcodes, rng, string_table):
        self.op  = opcodes
        self.rng = rng
        self.st  = string_table

    def compile(self, block):
        proto = Proto(); proto.is_vararg = True
        ctx = _Ctx(proto, self.op, self.rng, self.st, None)
        ctx.compile_block(block)
        proto.emit(self.op.get('RETURN'), 0)
        _inject_junk(proto, self.op, self.rng, 0.10)
        return proto


class _Ctx:
    def __init__(self, proto, op, rng, st, parent):
        self.proto = proto; self.op = op; self.rng = rng; self.st = st; self.parent = parent
        self._locals = {}; self._local_stack = []; self._break_patches = [[]]

    # ── Locals ────────────────────────────────────────────────────────────────
    def _push_local(self, name):
        idx = len(self._local_stack); self._local_stack.append(name)
        self._locals[name] = idx; return idx
    def _local_idx(self, name):
        return self._locals.get(name)

    # ── Emit helpers ──────────────────────────────────────────────────────────
    def E(self, opname, a=0, b=0):
        return self.proto.emit(self.op.get(opname), a, b)
    def _emit_const(self, v):
        self.E('LOAD_CONST', self.proto.add_const(v))
    def _load_name(self, name):
        loc = self._local_idx(name)
        if loc is not None: self.E('LOAD_LOCAL', loc)
        else: self.E('LOAD_GLOBAL', self.proto.add_const(name))
    def _store_name(self, name):
        loc = self._local_idx(name)
        if loc is not None: self.E('STORE_LOCAL', loc)
        else: self.E('STORE_GLOBAL', self.proto.add_const(name))

    # ── Block / Statements ────────────────────────────────────────────────────
    def compile_block(self, block):
        n_before = len(self._local_stack)
        for stmt in block.body: self._stmt(stmt)
        n_after  = len(self._local_stack)
        for _ in range(n_after - n_before):
            self.E('POP')
            if self._local_stack:
                nm = self._local_stack.pop()
                self._locals.pop(nm, None)

    def _stmt(self, node):
        t = type(node).__name__
        m = getattr(self, f'_s_{t}', None)
        if m is None: raise CompileError(f"Unsupported statement: {t}")
        m(node)

    def _s_LocalAssign(self, n):
        vals = n.values; nv = len(vals); nt = len(n.targets)
        for v in vals: self._expr(v)
        for _ in range(nt - nv): self.E('LOAD_NIL')
        for t in n.targets:
            slot = len(self._local_stack)
            self._local_stack.append(t.id); self._locals[t.id] = slot

    def _s_Assign(self, n):
        for v in n.values: self._expr(v)
        for _ in range(len(n.targets) - len(n.values)): self.E('LOAD_NIL')
        for tgt in reversed(n.targets): self._assign_target(tgt)

    def _assign_target(self, tgt):
        if isinstance(tgt, N.Name):  self._store_name(tgt.id)
        elif isinstance(tgt, N.Field):
            self._expr(tgt.value); self.E('SET_FIELD', self.proto.add_const(tgt.key.id))
        elif isinstance(tgt, N.Index):
            self._expr(tgt.value); self._expr(tgt.key); self.E('SET_TABLE')

    def _s_Return(self, n):
        for v in n.values: self._expr(v)
        self.E('RETURN', len(n.values))

    def _s_Break(self, _):
        idx = self.E('JUMP', 0); self._break_patches[-1].append(idx)

    def _s_Call(self, n):   self._expr(n); self.E('POP')
    def _s_Invoke(self, n): self._expr(n); self.E('POP')
    def _s_Block(self, n):  self.compile_block(n)
    def _s_Do(self, n):     self.compile_block(n.body)

    def _s_If(self, n):
        end_jumps = []
        self._expr(n.test)
        j_false = self.E('JUMP_FALSE_POP', 0)
        self.compile_block(n.body)
        for clause in n.orelse:
            j_end = self.E('JUMP', 0); end_jumps.append(j_end)
            self.proto.patch(j_false, len(self.proto.code))
            if isinstance(clause, N.ElseIf):
                self._expr(clause.test)
                j_false = self.E('JUMP_FALSE_POP', 0)
                self.compile_block(clause.body)
            else:
                j_false = None; self.compile_block(clause.body)
        end_tgt = len(self.proto.code)
        if j_false is not None: self.proto.patch(j_false, end_tgt)
        for j in end_jumps: self.proto.patch(j, end_tgt)

    def _s_While(self, n):
        top = len(self.proto.code)
        self._expr(n.test)
        j_exit = self.E('JUMP_FALSE_POP', 0)
        self._break_patches.append([])
        self.compile_block(n.body)
        self.E('JUMP', top)
        end = len(self.proto.code)
        self.proto.patch(j_exit, end)
        for bp in self._break_patches.pop(): self.proto.patch(bp, end)

    def _s_Repeat(self, n):
        top = len(self.proto.code)
        self._break_patches.append([])
        self.compile_block(n.body)
        self._expr(n.test); self.E('JUMP_FALSE_POP', top)
        end = len(self.proto.code)
        for bp in self._break_patches.pop(): self.proto.patch(bp, end)

    def _s_Fornumeric(self, n):
        self._expr(n.start); self._expr(n.stop)
        if n.step: self._expr(n.step)
        else: self._emit_const(1)
        base = len(self._local_stack)
        for nm in ('__step','__stop',n.target.id):
            self._local_stack.append(nm); self._locals[nm] = len(self._local_stack)-1
        loop_top = len(self.proto.code)
        self.E('LOAD_LOCAL', base+2); self._emit_const(0); self.E('GT')
        j_neg = self.E('JUMP_FALSE_POP', 0)
        self.E('LOAD_LOCAL', base+2); self.E('LOAD_LOCAL', base+1); self.E('LE')
        j_exit1 = self.E('JUMP_FALSE_POP', 0); j_body = self.E('JUMP', 0)
        neg_tgt = len(self.proto.code); self.proto.patch(j_neg, neg_tgt)
        self.E('LOAD_LOCAL', base+2); self.E('LOAD_LOCAL', base+1); self.E('GE')
        j_exit2 = self.E('JUMP_FALSE_POP', 0)
        self.proto.patch(j_body, len(self.proto.code))
        self._break_patches.append([]); self.compile_block(n.body)
        self.E('LOAD_LOCAL', base+2); self.E('LOAD_LOCAL', base); self.E('ADD')
        self.E('STORE_LOCAL', base+2); self.E('JUMP', loop_top)
        end = len(self.proto.code)
        self.proto.patch(j_exit1, end); self.proto.patch(j_exit2, end)
        for bp in self._break_patches.pop(): self.proto.patch(bp, end)
        for _ in range(3):
            if self._local_stack: nm=self._local_stack.pop(); self._locals.pop(nm,None); self.E('POP')

    def _s_Forin(self, n):
        for e in n.iter: self._expr(e)
        for _ in range(3-len(n.iter)): self.E('LOAD_NIL')
        base = len(self._local_stack)
        for nm in ('__iter','__state','__ctrl'):
            self._local_stack.append(nm); self._locals[nm]=len(self._local_stack)-1
        loop_top = len(self.proto.code)
        self.E('LOAD_LOCAL',base); self.E('LOAD_LOCAL',base+1); self.E('LOAD_LOCAL',base+2)
        self.E('CALL',2,len(n.targets))
        tgt_base = len(self._local_stack)
        for t in n.targets:
            self._local_stack.append(t.id); self._locals[t.id]=len(self._local_stack)-1
        self.E('LOAD_LOCAL',tgt_base); self._emit_const(None); self.E('EQ')
        j_exit = self.E('JUMP_TRUE_POP',0)
        self.E('LOAD_LOCAL',tgt_base); self.E('STORE_LOCAL',base+2)
        self._break_patches.append([]); self.compile_block(n.body); self.E('JUMP',loop_top)
        end = len(self.proto.code); self.proto.patch(j_exit,end)
        for bp in self._break_patches.pop(): self.proto.patch(bp,end)
        for _ in range(len(n.targets)+3):
            if self._local_stack: nm=self._local_stack.pop(); self._locals.pop(nm,None); self.E('POP')

    def _s_Function(self, n):
        p = self._compile_func(n.args, n.body)
        self.E('MAKE_CLOSURE', self.proto.add_proto(p))
        self._assign_target(n.name)

    def _s_LocalFunction(self, n):
        p = self._compile_func(n.args, n.body)
        slot = len(self._local_stack)
        self._local_stack.append(n.name.id); self._locals[n.name.id]=slot
        self.E('MAKE_CLOSURE', self.proto.add_proto(p))
        self.E('STORE_LOCAL', slot)

    def _s_Method(self, n):
        args = [N.Name('self')] + n.args
        p = self._compile_func(args, n.body)
        self.E('MAKE_CLOSURE', self.proto.add_proto(p))
        self._expr(n.source); self.E('SET_FIELD', self.proto.add_const(n.name.id))

    def _compile_func(self, args, body):
        p = Proto()
        ctx = _Ctx(p, self.op, self.rng, self.st, self)
        for a in args:
            if isinstance(a, N.Vararg): p.is_vararg = True
            else:
                sl = len(ctx._local_stack); ctx._local_stack.append(a.id)
                ctx._locals[a.id]=sl; p.nparams += 1
        ctx.compile_block(body); p.emit(self.op.get('RETURN'),0)
        _inject_junk(p, self.op, self.rng, 0.08)
        return p

    # ── Expressions ───────────────────────────────────────────────────────────
    def _expr(self, node):
        t = type(node).__name__
        m = getattr(self, f'_e_{t}', None)
        if m: m(node); return
        sm = getattr(self, f'_s_{t}', None)
        if sm: sm(node); return
        raise CompileError(f"Unsupported expr: {t}")

    def _e_EncryptedStringNode(self, n):
        enc_bytes, seed, step = self.st[n.idx]
        c = self.proto.add_const(('__enc_str', tuple(enc_bytes), seed, step))
        self.E('LOAD_CONST', c)

    def _e_Number(self, n):   self._emit_const(n.n)
    def _e_String(self, n):   self._emit_const(n.s)
    def _e_NilExpr(self, _):  self.E('LOAD_NIL')
    def _e_TrueExpr(self, _): self.E('LOAD_BOOL', 1)
    def _e_FalseExpr(self, _):self.E('LOAD_BOOL', 0)
    def _e_Vararg(self, _):   self.E('VARARG', 0)
    def _e_Name(self, n):     self._load_name(n.id)
    def _e_Field(self, n):
        self._expr(n.value); self.E('GET_FIELD', self.proto.add_const(n.key.id))
    def _e_Index(self, n):
        self._expr(n.value); self._expr(n.key); self.E('GET_TABLE')
    def _e_Call(self, n):
        self._expr(n.func)
        for a in n.args: self._expr(a)
        self.E('CALL', len(n.args), 1)
    def _e_Invoke(self, n):
        self._expr(n.source); self.E('SELF', self.proto.add_const(n.func.id))
        for a in n.args: self._expr(a)
        self.E('CALL', len(n.args)+1, 1)
    def _e_AnonymousFunction(self, n):
        p = self._compile_func(n.args, n.body); self.E('MAKE_CLOSURE', self.proto.add_proto(p))
    def _e_Table(self, n):
        self.E('NEW_TABLE')
        scratch = len(self._local_stack)
        self._local_stack.append('__tbl'); self._locals['__tbl'] = scratch
        self.E('STORE_LOCAL', scratch)
        for f in n.fields:
            self.E('LOAD_LOCAL', scratch)
            if isinstance(f, N.TableField):
                self._expr(f.value); self.E('SET_FIELD', self.proto.add_const(f.key.id))
            elif isinstance(f, N.TableIndex):
                self._expr(f.key); self._expr(f.value); self.E('SET_TABLE')
            else:
                self._expr(f)
                # sequential index: use length+1
                self.E('LEN'); self._emit_const(1); self.E('ADD')
                self.E('LOAD_LOCAL', scratch); self.E('SWAP'); self.E('SET_TABLE')
        self.E('LOAD_LOCAL', scratch)
        self._local_stack.pop(); self._locals.pop('__tbl', None)

    def _e_BinOp(self, n):
        OPS = {'+':'ADD','-':'SUB','*':'MUL','/':'DIV','%':'MOD','^':'POW',
               '..':'CONCAT','==':'EQ','~=':'NEQ','<':'LT','<=':'LE','>':'GT','>=':'GE'}
        if n.op == 'and':
            self._expr(n.left); j=self.E('JUMP_FALSE',0); self.E('POP')
            self._expr(n.right); self.proto.patch(j,len(self.proto.code))
        elif n.op == 'or':
            self._expr(n.left); j=self.E('JUMP_TRUE',0); self.E('POP')
            self._expr(n.right); self.proto.patch(j,len(self.proto.code))
        else:
            self._expr(n.left); self._expr(n.right)
            op = OPS.get(n.op)
            if op is None: raise CompileError(f"Unknown binop: {n.op}")
            self.E(op)
    def _e_UnOp(self, n):
        self._expr(n.operand)
        OPS = {'-':'UNM','not':'NOT','#':'LEN','~':'UNM'}
        self.E(OPS[n.op])


def _inject_junk(proto, op, rng, density=0.08):
    """Insert JUNK / FAKE no-ops at random positions (after all patches are done)."""
    n_junk = max(1, int(len(proto.code) * density))
    junk_ops = [op.get('JUNK'), op.get('FAKE_STACK'), op.get('FAKE_MATH')]
    for _ in range(n_junk):
        pos = rng.randint(0, len(proto.code))
        instr = Proto().emit.__func__  # just need pack_instr
        from ng_compiler.proto import pack_instr
        proto.code.insert(pos, pack_instr(rng.choice(junk_ops), 0, 0))
    for child in proto.protos:
        _inject_junk(child, op, rng, density)
