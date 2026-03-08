import sys,os;sys.path.insert(0,os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
"""NightGuard V3 — Control Flow Flattening + State Machine + Noise
Two modes:
  1. Opaque guard wrapping (quick, lightweight)
  2. State machine flattening (Luraph-style: converts linear blocks into
     while(state~=exit) do ... dispatch on state ... end)
"""
import random
import ast_nodes as N

# ─── Opaque predicates (pure arithmetic, no function calls) ──────────────────
def _opaque_true(rng):
    k=rng.randint(0,11)
    if k==0:
        v=rng.randint(3,97)
        return N.BinOp('==',N.BinOp('%',N.BinOp('*',N.Number(v),N.Number(v+1)),N.Number(2)),N.Number(0))
    elif k==1:
        v=rng.randint(1,999)
        return N.BinOp('>=',N.BinOp('*',N.Number(v),N.Number(v)),N.Number(0))
    elif k==2:
        a,b=rng.randint(1,20),rng.randint(1,20)
        lhs=N.BinOp('*',N.BinOp('+',N.Number(a),N.Number(b)),N.BinOp('+',N.Number(a),N.Number(b)))
        return N.BinOp('==',lhs,N.Number(a*a+2*a*b+b*b))
    elif k==3:
        v=rng.randint(2,999)
        return N.BinOp('==',N.BinOp('%',N.Number(v),N.Number(1)),N.Number(0))
    elif k==4:
        a,b=rng.randint(1,50),rng.randint(1,50)
        d=N.BinOp('-',N.Number(a),N.Number(b))
        d2=N.BinOp('-',N.Number(a),N.Number(b))
        return N.BinOp('>=',N.BinOp('*',d,d2),N.Number(0))
    elif k==5:
        a,b=rng.randint(2,30),rng.randint(1,20)
        lhs=N.BinOp('-',N.BinOp('*',N.Number(a),N.Number(a)),N.BinOp('*',N.Number(b),N.Number(b)))
        rhs=N.BinOp('*',N.BinOp('-',N.Number(a),N.Number(b)),N.BinOp('+',N.Number(a),N.Number(b)))
        return N.BinOp('==',lhs,rhs)
    elif k==6:
        n=rng.randint(3,20); total=n*(n+1)//2
        return N.BinOp('==',N.BinOp('*',N.Number(n),N.Number(n+1)),N.Number(total*2))
    elif k==7:
        v=rng.randint(1,500)
        return N.BinOp('>=',N.BinOp('*',N.Number(v),N.Number(2)),N.Number(v))
    elif k==8:
        v=rng.randint(1,49)*2+1
        return N.BinOp('==',N.BinOp('%',N.BinOp('*',N.Number(v),N.Number(v)),N.Number(2)),N.Number(1))
    elif k==9:
        v=rng.randint(1,9999)
        return N.BinOp('==',N.BinOp('+',N.Number(v),N.Number(0)),N.Number(v))
    elif k==10:
        # (a XOR a) == 0  expressed as: (a - a) == 0
        v=rng.randint(1,9999)
        return N.BinOp('==',N.BinOp('-',N.Number(v),N.Number(v)),N.Number(0))
    else:
        # Fermat: a^2 + b^2 ~= (a+b)^2 → always true: (a+b)^2 == a^2+2ab+b^2
        a,b=rng.randint(1,10),rng.randint(1,10)
        return N.BinOp('==',N.Number(a*a+2*a*b+b*b),N.Number((a+b)*(a+b)))

def _opaque_false(rng):
    k=rng.randint(0,6)
    if k==0:
        v=rng.randint(1,49)*2+1
        return N.BinOp('==',N.BinOp('%',N.Number(v),N.Number(2)),N.Number(0))
    elif k==1:
        v=rng.randint(1,99)
        return N.BinOp('<',N.BinOp('*',N.Number(v),N.Number(v)),N.Number(0))
    elif k==2:
        a,b=rng.randint(10,50),rng.randint(1,9)
        return N.BinOp('<',N.BinOp('+',N.Number(a),N.Number(b)),N.Number(a))
    elif k==3:
        v=rng.randint(1,500)
        return N.BinOp('<',N.BinOp('*',N.Number(v),N.Number(2)),N.Number(v))
    elif k==4:
        v=rng.randint(2,50)
        return N.BinOp('==',N.BinOp('%',N.BinOp('*',N.Number(v),N.Number(v+1)),N.Number(2)),N.Number(1))
    elif k==5:
        v=rng.randint(1,99)
        return N.BinOp('<=',N.BinOp('+',N.BinOp('*',N.Number(v),N.Number(v)),N.Number(1)),N.Number(0))
    else:
        # a != a (always false)
        v=rng.randint(1,9999)
        return N.BinOp('~=',N.Number(v),N.Number(v))

def _iname(rng):
    chars='lI0O1'
    return '_'+''.join(rng.choice(chars) for _ in range(rng.randint(8,12)))

def _junk_stmt(rng):
    v=_iname(rng)
    choice=rng.randint(0,4)
    if choice==0: return N.LocalAssign([N.Name(v)],[N.Number(rng.randint(1,9999))])
    elif choice==1: return N.LocalAssign([N.Name(v)],[N.BinOp('*',N.Number(rng.randint(1,99)),N.Number(rng.randint(1,99)))])
    elif choice==2: return N.LocalAssign([N.Name(v)],[N.BinOp('+',N.Number(rng.randint(1,50)),N.Number(rng.randint(1,50)))])
    elif choice==3: return N.LocalAssign([N.Name(v)],[N.String('__ng')])
    else: return N.LocalAssign([N.Name(v)],[N.NilExpr()])

# ─── State machine flattening ─────────────────────────────────────────────────
def _flatten_block(stmts,rng):
    """Convert a list of statements into a state-machine while loop.
    State IDs are random large integers; transitions are obfuscated.
    Noise states are inserted between real states.
    """
    if len(stmts)<2: return stmts   # not worth flattening

    # Assign random state IDs to real statements + exit
    state_ids=[rng.randint(10000,99999) for _ in range(len(stmts)+1)]
    exit_id=state_ids[-1]

    # State var
    sv=_iname(rng)
    # Noise state IDs interleaved
    noise_states=[]
    for _ in range(len(stmts)):
        if rng.random()<0.4:
            noise_states.append(rng.randint(10000,99999))
        else:
            noise_states.append(None)

    # Build the dispatch if/elseif chain
    # while sv ~= exit_id do ... end
    # Each branch: if sv == state_id then <stmt>; sv = next_state end
    branches=[]
    for i,stmt in enumerate(stmts):
        sid=state_ids[i]
        nid=state_ids[i+1]
        # Add noise transition sometimes
        ns=noise_states[i]
        if ns is not None:
            # sv = noise_id; then noise branch just sets sv = real_next
            body_stmts=[
                stmt,
                N.Assign([N.Name(sv)],[N.Number(ns)]),
            ]
            noise_branch=N.If(
                N.BinOp('==',N.Name(sv),N.Number(ns)),
                N.Block([
                    _junk_stmt(rng),
                    N.Assign([N.Name(sv)],[N.Number(nid)])
                ]),[])
            real_branch=N.If(
                N.BinOp('==',N.Name(sv),N.Number(sid)),
                N.Block(body_stmts),[])
            branches.append(real_branch)
            branches.append(noise_branch)
        else:
            body_stmts=[stmt,N.Assign([N.Name(sv)],[N.Number(nid)])]
            branches.append(N.If(
                N.BinOp('==',N.Name(sv),N.Number(sid)),
                N.Block(body_stmts),[]))

    loop_body=N.Block(branches)
    init=N.LocalAssign([N.Name(sv)],[N.Number(state_ids[0])])
    loop=N.While(N.BinOp('~=',N.Name(sv),N.Number(exit_id)),loop_body)
    return [init,loop]

class ControlFlowPass:
    """
    Performs two kinds of obfuscation:
    1. Opaque guards: wrap stmts in if(always_true) / insert if(always_false) dead blocks
    2. State machine flattening: convert blocks into while+dispatch (Luraph style)
    """
    def __init__(self,rng,flatten_prob=0.30,guard_prob=0.18,dead_prob=0.14):
        self._rng=rng
        self._fp=flatten_prob   # probability a block gets state-machine flattened
        self._gp=guard_prob     # probability a stmt gets wrapped in opaque-true
        self._dp=dead_prob      # probability a dead block gets inserted

    def visit(self,node):
        m=getattr(self,f'_v_{type(node).__name__}',None)
        return m(node) if m else node

    def _v_Block(self,n):
        # First recurse into children
        stmts=[]
        for s in n.body:
            v=self.visit(s)
            if v is None: continue
            stmts.append(v)

        # Apply opaque guards + dead noise to individual statements
        new=[]
        for s in stmts:
            # Dead block before?
            if self._rng.random()<self._dp:
                new.append(N.If(_opaque_false(self._rng),N.Block([_junk_stmt(self._rng)]),[]))
            # Opaque true wrap?
            if self._rng.random()<self._gp:
                new.append(N.If(_opaque_true(self._rng),N.Block([s]),[]))
            else:
                new.append(s)
        # Dead block at end?
        if self._rng.random()<self._dp:
            new.append(N.If(_opaque_false(self._rng),N.Block([_junk_stmt(self._rng)]),[]))

        # State machine flattening on the whole block?
        if len(new)>=3 and self._rng.random()<self._fp:
            new=_flatten_block(new,self._rng)

        return N.Block(new)

    def _v_If(self,n):
        b=self._v_Block(n.body)
        orelse=[]
        for o in n.orelse:
            if isinstance(o,N.ElseIf): orelse.append(N.ElseIf(o.test,self._v_Block(o.body)))
            else: orelse.append(N.Else(self._v_Block(o.body)))
        return N.If(n.test,b,orelse)
    def _v_While(self,n):         return N.While(n.test,self._v_Block(n.body))
    def _v_Repeat(self,n):        return N.Repeat(self._v_Block(n.body),n.test)
    def _v_Do(self,n):            return N.Do(self._v_Block(n.body))
    def _v_Fornumeric(self,n):    return N.Fornumeric(n.target,n.start,n.stop,n.step,self._v_Block(n.body))
    def _v_Forin(self,n):         return N.Forin(n.targets,n.iter,self._v_Block(n.body))
    def _v_Function(self,n):      return N.Function(n.name,n.args,self._v_Block(n.body))
    def _v_LocalFunction(self,n): return N.LocalFunction(n.name,n.args,self._v_Block(n.body))
    def _v_Method(self,n):        return N.Method(n.source,n.name,n.args,self._v_Block(n.body))
    def _v_AnonymousFunction(self,n): return N.AnonymousFunction(n.args,self._v_Block(n.body))

def run(block,rng): return ControlFlowPass(rng).visit(block)
