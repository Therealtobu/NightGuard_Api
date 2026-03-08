import sys,os;sys.path.insert(0,os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
"""NightGuard V3 — Mixed Boolean Arithmetic (MBA) Transform
Replaces integer constants with equivalent arithmetic expressions.
All rules are proven correct for any integer in range.
"""
import random
import ast_nodes as N

def _mba_rules(val,rng):
    """Return a list of AST expressions all equal to val. All rules guaranteed correct."""
    rules=[]
    v=int(val)

    # Rule 1: (val + r) - r   [always correct]
    r=rng.randint(1,200)
    rules.append(N.BinOp('-',N.BinOp('+',N.Number(v),N.Number(r)),N.Number(r)))

    # Rule 2: val * (2 - 1)   [always correct]
    rules.append(N.BinOp('*',N.Number(v),N.BinOp('-',N.Number(2),N.Number(1))))

    # Rule 3: (val + 0) * 1   [always correct]
    rules.append(N.BinOp('*',N.BinOp('+',N.Number(v),N.Number(0)),N.Number(1)))

    # Rule 4: val^2 - (val-1)*(val+1) = 1, so val = (val*val - (val-1)*(val+1)) + val - 1
    # = 1 + val - 1 = val  [correct for all integers]
    rules.append(
        N.BinOp('+',
            N.BinOp('-',
                N.BinOp('*',N.Number(v),N.Number(v)),
                N.BinOp('*',N.BinOp('-',N.Number(v),N.Number(1)),
                             N.BinOp('+',N.Number(v),N.Number(1)))),
            N.BinOp('-',N.Number(v),N.Number(1))))

    # Rule 5: a*q + c = val, pick integer factor
    if abs(v) > 1:
        for _ in range(8):
            f=rng.randint(2,min(10,abs(v)))
            if v % f == 0:
                q=v//f
                # q*f + 0 = val
                rules.append(N.BinOp('+',N.BinOp('*',N.Number(q),N.Number(f)),N.Number(0)))
                break
        else:
            # Not divisible: val = (val-1) + 1
            rules.append(N.BinOp('+',N.Number(v-1),N.Number(1)))

    # Rule 6: ((val - r) + r)  different from rule 1
    r2=rng.randint(1,150)
    rules.append(N.BinOp('+',N.BinOp('-',N.Number(v),N.Number(r2)),N.Number(r2)))

    # Rule 7: val * 2 - val   [always correct, no division]
    rules.append(N.BinOp('-',N.BinOp('*',N.Number(v),N.Number(2)),N.Number(v)))

    return rules

class MBATransform:
    """Replace numeric literals with MBA-style arithmetic expressions."""
    def __init__(self,rng,prob=0.5,max_depth=2):
        self._rng=rng
        self._prob=prob
        self._depth=0
        self._max_depth=max_depth

    def visit(self,node):
        m=getattr(self,f'_v_{type(node).__name__}',None)
        return m(node) if m else node

    def _v_Number(self,n):
        if self._depth>=self._max_depth: return n
        if not isinstance(n.n,int) or abs(n.n)>10000 or n.n==0: return n
        if self._rng.random()>self._prob: return n
        rules=_mba_rules(int(n.n),self._rng)
        if not rules: return n
        self._depth+=1
        result=self._rng.choice(rules)
        self._depth-=1
        return result

    def _v_Block(self,n): return N.Block([self.visit(s) for s in n.body])
    def _v_LocalAssign(self,n): return N.LocalAssign(n.targets,[self.visit(v) for v in n.values])
    def _v_Assign(self,n):      return N.Assign(n.targets,[self.visit(v) for v in n.values])
    def _v_Return(self,n):      return N.Return([self.visit(v) for v in n.values])
    def _v_BinOp(self,n):       return N.BinOp(n.op,self.visit(n.left),self.visit(n.right))
    def _v_UnOp(self,n):        return N.UnOp(n.op,self.visit(n.operand))
    def _v_Call(self,n):        return N.Call(self.visit(n.func),[self.visit(a) for a in n.args])
    def _v_Invoke(self,n):      return N.Invoke(self.visit(n.source),n.func,[self.visit(a) for a in n.args])
    def _v_Field(self,n):       return N.Field(self.visit(n.value),n.key)
    def _v_Index(self,n):       return N.Index(self.visit(n.value),self.visit(n.key))
    def _v_If(self,n):
        orelse=[]
        for o in n.orelse:
            if isinstance(o,N.ElseIf): orelse.append(N.ElseIf(self.visit(o.test),self._v_Block(o.body)))
            else: orelse.append(N.Else(self._v_Block(o.body)))
        return N.If(self.visit(n.test),self._v_Block(n.body),orelse)
    def _v_While(self,n):         return N.While(self.visit(n.test),self._v_Block(n.body))
    def _v_Repeat(self,n):        return N.Repeat(self._v_Block(n.body),self.visit(n.test))
    def _v_Do(self,n):            return N.Do(self._v_Block(n.body))
    def _v_Fornumeric(self,n):    return N.Fornumeric(n.target,self.visit(n.start),self.visit(n.stop),self.visit(n.step) if n.step else None,self._v_Block(n.body))
    def _v_Forin(self,n):         return N.Forin(n.targets,[self.visit(e) for e in n.iter],self._v_Block(n.body))
    def _v_Function(self,n):      return N.Function(n.name,n.args,self._v_Block(n.body))
    def _v_LocalFunction(self,n): return N.LocalFunction(n.name,n.args,self._v_Block(n.body))
    def _v_Method(self,n):        return N.Method(n.source,n.name,n.args,self._v_Block(n.body))
    def _v_AnonymousFunction(self,n): return N.AnonymousFunction(n.args,self._v_Block(n.body))
    def _v_Table(self,n):
        flds=[]
        for f in n.fields:
            if isinstance(f,N.TableField):   flds.append(N.TableField(f.key,self.visit(f.value)))
            elif isinstance(f,N.TableIndex): flds.append(N.TableIndex(self.visit(f.key),self.visit(f.value)))
            else: flds.append(self.visit(f))
        return N.Table(flds)
    def _v_Name(self,n):       return n
    def _v_String(self,n):     return n
    def _v_NilExpr(self,n):    return n
    def _v_TrueExpr(self,n):   return n
    def _v_FalseExpr(self,n):  return n
    def _v_Vararg(self,n):     return n
    def _v_Break(self,n):      return n

def run(block,rng): return MBATransform(rng).visit(block)
