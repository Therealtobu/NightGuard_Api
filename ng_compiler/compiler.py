import sys,os;sys.path.insert(0,os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
"""NightGuard V3 — Register VM Compiler
Each local variable occupies a fixed register for its lifetime.
Temporaries are allocated above locals and freed after use.
"""
import ast_nodes as N
from ng_transforms.string_encrypt import EncryptedStringNode
from ng_compiler.proto import Proto
from ng_compiler.opcodes import Opcodes,pack,pack_bx,unpack,unpack_bx,BX_BIAS,rk,is_rk,RK_BIT

class CompileError(Exception): pass

# ── Register allocator ────────────────────────────────────────────────────────
class _Regs:
    def __init__(self):
        self._top=0; self._max=0
    def alloc(self)->int:
        r=self._top; self._top+=1
        if self._top>self._max: self._max=self._top
        return r
    def free(self,r):
        if r==self._top-1: self._top-=1
    def free_to(self,top): self._top=top
    @property
    def top(self): return self._top
    @property
    def maxused(self): return self._max

# ── Function context ──────────────────────────────────────────────────────────
class _Ctx:
    def __init__(self,proto,op,rng,st,parent=None,cb=None):
        self.proto=proto; self.op=op; self.rng=rng; self.st=st
        self.parent=parent; self.cb=cb or (parent.cb if parent else None)
        self.regs=_Regs()
        self._scopes=[{}]   # stack of {name->reg}
        self._breaks=[[]]   # patch lists for break

    # ── Scope ─────────────────────────────────────────────────────────────────
    def push_scope(self): self._scopes.append({})
    def pop_scope(self):
        sc=self._scopes.pop()
        if sc:
            lowest=min(sc.values())
            self.regs.free_to(lowest)

    def def_local(self,name)->int:
        r=self.regs.alloc(); self._scopes[-1][name]=r; return r

    def resolve(self,name):
        for sc in reversed(self._scopes):
            if name in sc: return sc[name]
        return None

    # ── Emit ──────────────────────────────────────────────────────────────────
    def E(self,instr)->int:  return self.proto.emit(instr)
    def pc(self)->int:       return len(self.proto.code)

    def abc(self,nm,a,b=0,c=0): return self.E(self.op.mk(nm,a,b,c))
    def bx(self,nm,a,bx):       return self.E(self.op.mk_bx(nm,a,bx))
    def sbx(self,nm,a,s):       return self.E(self.op.mk_sbx(nm,a,s))

    def jmp(self,delta=0):       return self.sbx('JMP',0,delta)
    def patch(self,idx,target=None):
        t=target if target is not None else self.pc()
        self.proto.patch_sbx(idx,t)

    # ── RK helpers ────────────────────────────────────────────────────────────
    def _rk_literal(self,node):
        """Return RK-encoded const if node is a literal, else None."""
        if isinstance(node,N.Number):  k=self.proto.add_const(node.n);   return rk(k) if k<256 else None
        if isinstance(node,N.String):  k=self.proto.add_const(node.s);   return rk(k) if k<256 else None
        if isinstance(node,N.NilExpr): k=self.proto.add_const(None);     return rk(k) if k<256 else None
        if isinstance(node,N.TrueExpr): k=self.proto.add_const(True);    return rk(k) if k<256 else None
        if isinstance(node,N.FalseExpr):k=self.proto.add_const(False);   return rk(k) if k<256 else None
        return None

    def expr_rk(self,node):
        """Compile node as an RK operand (const slot or temp register)."""
        v=self._rk_literal(node)
        if v is not None: return v, None   # (rk_value, temp_reg_to_free)
        r=self.regs.alloc()
        self.expr(node,r)
        return r, r   # (reg_as_rk, reg_to_free)

    # ── Expression compiler ───────────────────────────────────────────────────
    def expr(self,node,dest=None)->int:
        """Compile expr into dest (alloc if None). Return dest register."""
        t=type(node).__name__
        m=getattr(self,f'_e_{t}',None)
        if m is None: raise CompileError(f'Unknown expr: {t}')
        return m(node,dest)

    def _alloc(self,dest): return dest if dest is not None else self.regs.alloc()

    def _e_Number(self,n,dest):
        r=self._alloc(dest); k=self.proto.add_const(n.n); self.bx('LOADK',r,k); return r
    def _e_String(self,n,dest):
        r=self._alloc(dest); k=self.proto.add_const(n.s); self.bx('LOADK',r,k); return r
    def _e_NilExpr(self,n,dest):
        r=self._alloc(dest); self.abc('LOADNIL',r,r); return r
    def _e_TrueExpr(self,n,dest):
        r=self._alloc(dest); self.abc('LOADBOOL',r,1,0); return r
    def _e_FalseExpr(self,n,dest):
        r=self._alloc(dest); self.abc('LOADBOOL',r,0,0); return r
    def _e_Vararg(self,n,dest):
        r=self._alloc(dest); self.abc('VARARG',r,2); return r

    def _e_EncryptedStringNode(self,n,dest):
        r=self._alloc(dest)
        entry=self.st.get(n.idx)
        if entry is None: k=self.proto.add_const(''); self.bx('LOADK',r,k); return r
        L=len(entry)
        if L>=7:   enc,seed,step,sk,chunks,noise,order=entry[:7]
        elif L>=6: enc,seed,step,sk,chunks,noise=entry[:6]; order=None
        elif L==4: enc,seed,step,sk=entry; chunks=None; noise=[]; order=None
        else:      enc,seed,step=entry[:3]; sk=0; chunks=None; noise=[]; order=None
        k=self.proto.add_const(('__enc_str',tuple(enc),seed,step,sk,chunks,noise,order))
        self.bx('LOADK',r,k); return r

    def _e_Name(self,n,dest):
        reg=self.resolve(n.id)
        if reg is not None:
            if dest is not None and dest!=reg: self.abc('MOVE',dest,reg); return dest
            return reg
        r=self._alloc(dest); k=self.proto.add_const(n.id); self.bx('GETGLOBAL',r,k); return r

    def _e_Field(self,n,dest):
        r=self._alloc(dest)
        obj=self.expr(n.value)
        k=self.proto.add_const(n.key.id)
        # GETTABLE R[r] = R[obj][RK(k)]
        self.abc('GETTABLE',r,obj,rk(k) if k<256 else (lambda t: (self.bx('LOADK',t,k),t)[1])(self.regs.alloc()))
        if obj!=r: self.regs.free(obj)
        return r

    def _e_Index(self,n,dest):
        r=self._alloc(dest)
        obj=self.expr(n.value)
        kv,ktmp=self.expr_rk(n.key)
        self.abc('GETTABLE',r,obj,kv)
        if ktmp is not None: self.regs.free(ktmp)
        if obj!=r: self.regs.free(obj)
        return r

    def _e_UnOp(self,n,dest):
        OPS={'-':'UNM','not':'NOT','#':'LEN'}
        r=self._alloc(dest)
        rb=self.expr(n.operand)
        self.abc(OPS[n.op],r,rb)
        if rb!=r: self.regs.free(rb)
        return r

    def _e_BinOp(self,n,dest):
        if n.op=='and': return self._e_and(n,dest)
        if n.op=='or':  return self._e_or(n,dest)
        if n.op=='..':  return self._e_concat(n,dest)
        CMP={'==':('EQ',0),'~=':('EQ',1),'<':('LT',0),'<=':('LE',0),'>':('LT',1),'>=':('LE',1)}
        ARITH={'+':'ADD','-':'SUB','*':'MUL','/':'DIV','%':'MOD','^':'POW'}
        if n.op in CMP:  return self._e_cmp(n,dest,CMP[n.op])
        if n.op in ARITH:
            r=self._alloc(dest)
            bv,btmp=self.expr_rk(n.left)
            cv,ctmp=self.expr_rk(n.right)
            self.abc(ARITH[n.op],r,bv,cv)
            if ctmp is not None: self.regs.free(ctmp)
            if btmp is not None: self.regs.free(btmp)
            return r
        raise CompileError(f'Unknown binop: {n.op}')

    def _e_cmp(self,n,dest,spec):
        op_nm,flip=spec
        r=self._alloc(dest)
        # swap operands for > and >=
        if n.op in('>','>='):
            bv,btmp=self.expr_rk(n.right); cv,ctmp=self.expr_rk(n.left)
        else:
            bv,btmp=self.expr_rk(n.left);  cv,ctmp=self.expr_rk(n.right)
        # EQ/LT/LE: if (B op C) ~= A then skip next
        # We want: if comparison is true → R[r]=true, else R[r]=false
        self.abc(op_nm,flip,bv,cv)   # if result~=flip: pc++  → skip jmp to false
        j=self.jmp(1)                # skip false LOADBOOL
        self.abc('LOADBOOL',r,0,1)   # false, then skip next (the true LOADBOOL)
        self.abc('LOADBOOL',r,1,0)   # true
        if ctmp is not None: self.regs.free(ctmp)
        if btmp is not None: self.regs.free(btmp)
        return r

    def _e_and(self,n,dest):
        r=self._alloc(dest)
        self.expr(n.left,r)
        self.abc('TEST',r,0,0)    # if not R[r]: skip jmp
        j=self.jmp(0)             # jump over right (result stays false in r)
        self.expr(n.right,r)
        self.patch(j)
        return r

    def _e_or(self,n,dest):
        r=self._alloc(dest)
        self.expr(n.left,r)
        self.abc('TEST',r,0,1)    # if R[r]: skip jmp
        j=self.jmp(0)
        self.expr(n.right,r)
        self.patch(j)
        return r

    def _e_concat(self,n,dest):
        # Collect all concat operands in a flat list
        parts=[]
        def collect(node):
            if isinstance(node,N.BinOp) and node.op=='..':
                collect(node.left); collect(node.right)
            else: parts.append(node)
        collect(n)
        base=self.regs.top
        part_regs=[]
        for p in parts:
            pr=self.regs.alloc(); self.expr(p,pr); part_regs.append(pr)
        r=self._alloc(dest)
        self.abc('CONCAT',r,base,base+len(parts)-1)
        for pr in reversed(part_regs): self.regs.free(pr)
        return r

    def _e_Call(self,n,dest):
        base=self.regs.top
        self.expr(n.func,base); self.regs._top=max(self.regs._top,base+1)
        for i,arg in enumerate(n.args):
            ar=self.regs.alloc(); self.expr(arg,ar)
        nargs=len(n.args)
        nret=1 if dest is not None else 0
        self.abc('CALL',base,nargs+1,nret+1)
        # results start at base
        self.regs.free_to(base+nret)
        if nret and dest is not None and dest!=base:
            self.abc('MOVE',dest,base); self.regs.free(base); return dest
        return base

    def _e_Invoke(self,n,dest):
        base=self.regs.top
        obj=self.expr(n.source,base); self.regs._top=max(self.regs._top,base+1)
        k=self.proto.add_const(n.func.id)
        ck=rk(k) if k<256 else 0   # SELF uses RK(C) for method name
        self.abc('SELF',base,obj,ck)
        self.regs._top=base+2
        for arg in n.args:
            ar=self.regs.alloc(); self.expr(arg,ar)
        nret=1 if dest is not None else 0
        self.abc('CALL',base,len(n.args)+2,nret+1)
        self.regs.free_to(base+nret)
        if nret and dest is not None and dest!=base:
            self.abc('MOVE',dest,base); self.regs.free(base); return dest
        return base

    def _e_Table(self,n,dest):
        r=self._alloc(dest); self.abc('NEWTABLE',r)
        arr=0
        for f in n.fields:
            if isinstance(f,N.TableField):
                kk=rk(self.proto.add_const(f.key.id))
                vr=self.regs.alloc(); self.expr(f.value,vr)
                self.abc('SETTABLE',r,kk,vr); self.regs.free(vr)
            elif isinstance(f,N.TableIndex):
                kv,ktmp=self.expr_rk(f.key)
                vr=self.regs.alloc(); self.expr(f.value,vr)
                self.abc('SETTABLE',r,kv,vr)
                self.regs.free(vr)
                if ktmp is not None: self.regs.free(ktmp)
            else:
                arr+=1; kk=rk(self.proto.add_const(arr))
                vr=self.regs.alloc(); self.expr(f,vr)
                self.abc('SETTABLE',r,kk,vr); self.regs.free(vr)
        return r

    def _e_AnonymousFunction(self,n,dest):
        r=self._alloc(dest)
        sub=self._fn(n.args,n.body,'anon')
        self.bx('CLOSURE',r,self.proto.add_proto(sub))
        return r

    # ── Statements ────────────────────────────────────────────────────────────
    def stmt(self,node):
        t=type(node).__name__
        m=getattr(self,f'_s_{t}',None)
        if m is None: raise CompileError(f'Unknown stmt: {t}')
        m(node)

    def compile_block(self,block):
        saved=self.regs.top
        self.push_scope()
        for s in block.body: self.stmt(s)
        self.pop_scope()
        self.regs.free_to(saved)

    def _s_LocalAssign(self,n):
        # Pre-allocate registers for all targets
        regs=[]
        for t in n.targets: regs.append(self.regs.alloc())
        for i,(t,r) in enumerate(zip(n.targets,regs)):
            if i<len(n.values): self.expr(n.values[i],r)
            else: self.abc('LOADNIL',r,r)
            self._scopes[-1][t.id]=r

    def _s_Assign(self,n):
        tmps=[]
        for i,tgt in enumerate(n.targets):
            v=n.values[i] if i<len(n.values) else N.NilExpr()
            r=self.regs.alloc(); self.expr(v,r); tmps.append(r)
        for i,tgt in enumerate(n.targets): self._store(tgt,tmps[i])
        for r in reversed(tmps): self.regs.free(r)

    def _store(self,tgt,src):
        if isinstance(tgt,N.Name):
            loc=self.resolve(tgt.id)
            if loc is not None:
                if loc!=src: self.abc('MOVE',loc,src)
            else:
                k=self.proto.add_const(tgt.id); self.bx('SETGLOBAL',src,k)
        elif isinstance(tgt,N.Field):
            obj=self.expr(tgt.value); k=rk(self.proto.add_const(tgt.key.id))
            self.abc('SETTABLE',obj,k,src); self.regs.free(obj)
        elif isinstance(tgt,N.Index):
            obj=self.expr(tgt.value); kv,ktmp=self.expr_rk(tgt.key)
            self.abc('SETTABLE',obj,kv,src)
            if ktmp: self.regs.free(ktmp)
            self.regs.free(obj)

    def _s_Return(self,n):
        if not n.values: self.abc('RETURN',0,1); return
        base=self.regs.top
        for v in n.values: r=self.regs.alloc(); self.expr(v,r)
        self.abc('RETURN',base,len(n.values)+1)
        self.regs.free_to(base)

    def _s_Call(self,n):
        base=self.regs.top
        self.expr(n.func,base); self.regs._top=max(self.regs._top,base+1)
        for arg in n.args: ar=self.regs.alloc(); self.expr(arg,ar)
        self.abc('CALL',base,len(n.args)+1,1)
        self.regs.free_to(base)

    def _s_Invoke(self,n):
        base=self.regs.top
        obj=self.expr(n.source,base); self.regs._top=max(self.regs._top,base+1)
        k=self.proto.add_const(n.func.id); ck=rk(k) if k<256 else 0
        self.abc('SELF',base,obj,ck); self.regs._top=base+2
        for arg in n.args: ar=self.regs.alloc(); self.expr(arg,ar)
        self.abc('CALL',base,len(n.args)+2,1); self.regs.free_to(base)

    def _s_Do(self,n):  self.compile_block(n.body)
    def _s_Block(self,n): self.compile_block(n)

    def _s_If(self,n):
        ends=[]
        cond=self.expr(n.test); self.abc('TEST',cond,0,0); self.regs.free(cond)
        j_skip=self.jmp(0)
        self.compile_block(n.body)
        for clause in n.orelse:
            j_end=self.jmp(0); ends.append(j_end); self.patch(j_skip)
            if isinstance(clause,N.ElseIf):
                cond=self.expr(clause.test); self.abc('TEST',cond,0,0); self.regs.free(cond)
                j_skip=self.jmp(0); self.compile_block(clause.body)
            else:
                j_skip=None; self.compile_block(clause.body)
        if j_skip is not None: self.patch(j_skip)
        for j in ends: self.patch(j)

    def _s_While(self,n):
        top=self.pc()
        cond=self.expr(n.test); self.abc('TEST',cond,0,0); self.regs.free(cond)
        j_exit=self.jmp(0); self._breaks.append([])
        self.compile_block(n.body)
        self.sbx('JMP',0,top-self.pc()-1)
        self.patch(j_exit)
        for bp in self._breaks.pop(): self.patch(bp)

    def _s_Repeat(self,n):
        top=self.pc(); self._breaks.append([])
        self.compile_block(n.body)
        cond=self.expr(n.test); self.abc('TEST',cond,0,0); self.regs.free(cond)
        self.sbx('JMP',0,top-self.pc()-1)
        for bp in self._breaks.pop(): self.patch(bp)

    def _s_Fornumeric(self,n):
        base=self.regs.top
        # R[base]=init, R[base+1]=limit, R[base+2]=step, R[base+3]=ctrl
        ri=self.regs.alloc(); self.expr(n.start,ri)
        rl=self.regs.alloc(); self.expr(n.stop,rl)
        rs=self.regs.alloc()
        if n.step: self.expr(n.step,rs)
        else: k=self.proto.add_const(1); self.bx('LOADK',rs,k)
        rc=self.regs.alloc()   # loop var
        fp=self.sbx('FORPREP',base,0)
        loop_top=self.pc()
        self.push_scope(); self._scopes[-1][n.target.id]=rc
        self._breaks.append([])
        self.compile_block(n.body)
        self.pop_scope()
        fl=self.sbx('FORLOOP',base,0)
        # Patch FORPREP: jump to FORLOOP+1 (end)
        self.proto.patch_sbx(fp,self.pc()-1)
        # Patch FORLOOP: jump back to loop_top
        self.proto.patch_sbx(fl,loop_top)
        end=self.pc()
        for bp in self._breaks.pop(): self.patch(bp)
        self.regs.free_to(base)

    def _s_Forin(self,n):
        base=self.regs.top
        # R[base]=iter, R[base+1]=state, R[base+2]=ctrl
        iters=n.iter
        for i in range(3):
            r=self.regs.alloc()
            if i<len(iters): self.expr(iters[i],r)
            else: self.abc('LOADNIL',r,r)
        self.push_scope()
        tbase=self.regs.top
        for t in n.targets:
            r=self.regs.alloc(); self._scopes[-1][t.id]=r
        loop_top=self.pc()
        self.abc('TFORLOOP',base,0,len(n.targets))
        j_exit=self.jmp(0)
        self.abc('MOVE',base+2,tbase)  # update control var
        self._breaks.append([])
        self.compile_block(n.body)
        self.sbx('JMP',0,loop_top-self.pc()-1)
        self.patch(j_exit)
        for bp in self._breaks.pop(): self.patch(bp)
        self.pop_scope()
        self.regs.free_to(base)

    def _s_Break(self,_):
        self._breaks[-1].append(self.jmp(0))

    def _s_Function(self,n):
        nm=_node_name(n.name)
        if self.cb: self.cb('compile',f'fn {nm}')
        sub=self._fn(n.args,n.body,nm)
        r=self.regs.alloc(); self.bx('CLOSURE',r,self.proto.add_proto(sub))
        self._store(n.name,r); self.regs.free(r)

    def _s_LocalFunction(self,n):
        if self.cb: self.cb('compile',f'local fn {n.name.id}')
        r=self.regs.alloc(); self._scopes[-1][n.name.id]=r
        sub=self._fn(n.args,n.body,n.name.id)
        self.bx('CLOSURE',r,self.proto.add_proto(sub))

    def _s_Method(self,n):
        if self.cb: self.cb('compile',f'method {n.name.id}')
        args=[N.Name('self')]+n.args
        sub=self._fn(args,n.body,n.name.id)
        r=self.regs.alloc(); self.bx('CLOSURE',r,self.proto.add_proto(sub))
        obj=self.expr(n.source); k=rk(self.proto.add_const(n.name.id))
        self.abc('SETTABLE',obj,k,r)
        self.regs.free(obj); self.regs.free(r)

    def _fn(self,args,body,name='?')->Proto:
        p=Proto(); p.name=name
        ctx=_Ctx(p,self.op,self.rng,self.st,self,self.cb)
        for a in args:
            if isinstance(a,N.Vararg): p.is_vararg=True
            else:
                r=ctx.regs.alloc(); ctx._scopes[-1][a.id]=r; p.nparams+=1
        ctx.compile_block(body)
        p.emit(self.op.mk('RETURN',0,1))
        p.maxreg=ctx.regs.maxused
        _inject_junk(p,self.op,self.rng)
        return p


# ── Top-level compiler ────────────────────────────────────────────────────────
class Compiler:
    def __init__(self,opcodes,rng,string_table,progress_cb=None):
        self.op=opcodes; self.rng=rng; self.st=string_table; self.cb=progress_cb

    def compile(self,block)->Proto:
        p=Proto(); p.name='main'; p.is_vararg=True
        ctx=_Ctx(p,self.op,self.rng,self.st,cb=self.cb)
        ctx.compile_block(block)
        p.emit(self.op.mk('RETURN',0,1))
        p.maxreg=ctx.regs.maxused
        _inject_junk(p,self.op,self.rng,density=0.10)
        return p


# ── Junk injection ────────────────────────────────────────────────────────────
_BOUNDARY_OPS={'RETURN','CALL','SETGLOBAL','SETTABLE','JMP','FORLOOP','FORPREP','TFORLOOP','SETLIST'}

def _inject_junk(proto,op,rng,density=0.08):
    """Insert junk instrs only at statement boundaries; re-patch all JMPs."""
    _JMP_OPS={'JMP','FORPREP','FORLOOP'}
    safe=[]
    for i,raw in enumerate(proto.code):
        nm=op.name(raw&0xFF)
        if nm in _BOUNDARY_OPS: safe.append(i+1)
    if not safe: safe=[0]

    n_junk=max(1,int(len(proto.code)*density))
    for _ in range(n_junk):
        pos=min(rng.choice(safe),len(proto.code))
        proto.code.insert(pos,op.junk(rng))
        # Re-patch sBx jumps
        for idx,raw in enumerate(proto.code):
            nm=op.name(raw&0xFF)
            if nm not in _JMP_OPS: continue
            _,a,bx=unpack_bx(raw)
            sbx=bx-BX_BIAS
            target=idx+1+sbx
            if idx<pos<=target: sbx+=1
            elif target<pos<=idx: sbx-=1
            else: continue
            proto.code[idx]=pack_bx(raw&0xFF,a,sbx+BX_BIAS)
        safe=[p+1 if p>=pos else p for p in safe]
        safe.append(pos+1)

    for child in proto.protos:
        _inject_junk(child,op,rng,density)

def _node_name(node):
    if node is None: return '?'
    t=type(node).__name__
    if t=='Name': return node.id
    if t=='Field': return f'{_node_name(node.value)}.{node.key.id}'
    return t
