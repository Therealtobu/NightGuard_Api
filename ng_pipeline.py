import sys,os;sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
"""NightGuard V3 — Transform Pipeline"""
import random

from ng_transforms.rename_locals  import RenameLocalsPass
from ng_transforms.string_encrypt import StringEncryptPass
from ng_transforms.constant_split import ConstantSplitPass
from ng_transforms.mba_transform  import MBATransform
from ng_transforms.dead_code      import DeadCodePass
from ng_transforms.control_flow   import ControlFlowPass
from ng_transforms.watermark      import AntiTamperPass
from ng_transforms.string_scatter import scatter_string_table

class TransformPipeline:
    def __init__(self,rng,options=None):
        opts=options or {}
        self.rng=rng
        self.string_table={}
        self._enc_pass=None
        self._passes=[]

        # Pass order matters:
        # 1. Rename — before anything so renamed names used throughout
        if opts.get('rename',True):
            self._passes.append(RenameLocalsPass(rng))
        # 2. Anti-tamper — inject at top level before other transforms
        if opts.get('anti_tamper',True):
            self._passes.append(AntiTamperPass(rng))
        # 3. Constant split — before MBA so split values get MBA'd
        if opts.get('const_split',True):
            self._passes.append(ConstantSplitPass(rng))
        # 4. MBA — on split constants
        if opts.get('mba',True):
            self._passes.append(MBATransform(rng,prob=0.45))
        # 5. String encrypt — before CF so encrypted strings in state branches
        if opts.get('string_encrypt',True):
            enc=StringEncryptPass(rng)
            self._passes.append(enc)
            self._enc_pass=enc
        # 6. Dead code — before CF so dead branches get flattened too
        if opts.get('dead_code',True):
            self._passes.append(DeadCodePass(rng,insert_prob=0.20,wrap_prob=0.0,end_prob=0.12))
        # 7. Control flow flattening LAST — state machine on fully-transformed AST
        if opts.get('control_flow',True):
            # Keep control-flow enabled by default with moderate flattening.
            self._passes.append(ControlFlowPass(rng,flatten_prob=0.30,guard_prob=0.08,dead_prob=0.08))

    def run(self,block):
        node=block
        for p in self._passes:
            node=p.visit(node)
        if self._enc_pass:
            raw_st=self._enc_pass.string_table
            self.string_table=scatter_string_table(raw_st,self.rng)
        return node
