import sys,os;sys.path.insert(0,os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
"""NightGuard V3 — Dead Code Injection (deeper, Luraph-style)
Injects unreachable blocks guarded by opaque-false predicates.
Dead blocks can contain: assignments, nested dead ifs, fake loops.
"""
import random
import ast_nodes as N
from ng_transforms.control_flow import _opaque_false,_opaque_true,_iname

def _dead_assign(rng):
    v=_iname(rng)
    choice=rng.randint(0,4)
    if choice==0: return N.LocalAssign([N.Name(v)],[N.Number(rng.randint(1,9999))])
    elif choice==1: return N.LocalAssign([N.Name(v)],[N.BinOp('*',N.Number(rng.randint(1,99)),N.Number(rng.randint(1,99)))])
    elif choice==2: return N.LocalAssign([N.Name(v)],[N.String('__ng')])
    elif choice==3: return N.LocalAssign([N.Name(v)],[N.NilExpr()])
    else: return N.LocalAssign([N.Name(v)],[N.BinOp('+',N.Number(rng.randint(1,50)),N.Number(rng.randint(1,50)))])

def _dead_block(rng,depth=0):
    """Generate a dead code block with optional nesting."""
    stmts=[_dead_assign(rng)]
    if depth<2 and rng.random()<0.3:
        # Nested dead-if inside dead block
        stmts.append(N.If(_opaque_false(rng),N.Block([_dead_assign(rng)]),[]))
    if rng.random()<0.2:
        # Fake while(false) loop
        stmts.append(N.While(_opaque_false(rng),N.Block([_dead_assign(rng)])))
    return N.Block(stmts)

class DeadCodePass:
    def __init__(self,rng,insert_prob=0.22,wrap_prob=0.16,end_prob=0.14):
        self._rng=rng
        self._ip=insert_prob
        self._wp=wrap_prob
        self._ep=end_prob

    def visit(self,node):
        m=getattr(self,f'_v_{type(node).__name__}',None)
        return m(node) if m else node

    def _v_Block(self,n):
        new=[]
        for s in n.body:
            v=self.visit(s)
            if v is None: continue
            # Insert dead block before
            if self._rng.random()<self._ip:
                new.append(N.If(_opaque_false(self._rng),_dead_block(self._rng),[]))
            # Wrap in opaque true
            if self._rng.random()<self._wp:
                new.append(N.If(_opaque_true(self._rng),N.Block([v]),[]))
            else:
                new.append(v)
        # End dead block
        if self._rng.random()<self._ep:
            new.append(N.If(_opaque_false(self._rng),_dead_block(self._rng),[]))
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

def run(block,rng): return DeadCodePass(rng).visit(block)
