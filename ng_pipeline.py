"""TransformPipeline - orchestrates all AST passes in correct order."""
import random, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ng_transforms.rename_locals  import RenameLocalsPass
from ng_transforms.string_encrypt import StringEncryptPass
from ng_transforms.constant_split import ConstantSplitPass
from ng_transforms.dead_code      import DeadCodePass
from ng_transforms.control_flow   import ControlFlowPass
from ng_transforms.string_scatter  import scatter_string_table

class TransformPipeline:
    def __init__(self, rng, options=None):
        opts = options or {}
        self.rng = rng
        self.string_table = {}
        self._enc_pass = None
        self._passes = []

        # Order matters:
        # 1. Rename first (before CF so renamed names are used in state machines)
        if opts.get('rename', True):
            self._passes.append(RenameLocalsPass(rng))
        # 2. Constant split (before CF so split constants appear in state branches)
        if opts.get('const_split', True):
            self._passes.append(ConstantSplitPass(rng))
        # 3. String encrypt (before CF so encrypted strings propagate into states)
        if opts.get('string_encrypt', True):
            enc = StringEncryptPass(rng)
            self._passes.append(enc)
            self._enc_pass = enc
        # 4. Dead code injection (before CF — dead branches get flattened too)
        if opts.get('dead_code', True):
            self._passes.append(DeadCodePass(rng))
        # 5. Control flow flattening LAST (operates on fully-transformed AST)
        if opts.get('control_flow', True):
            self._passes.append(ControlFlowPass(rng))

    def run(self, block):
        node = block
        for p in self._passes:
            node = p.visit(node)
        if self._enc_pass:
            raw_st = self._enc_pass.string_table
            self.string_table = scatter_string_table(raw_st, self.rng)
        return node
