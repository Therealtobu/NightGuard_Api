"""
TransformPipeline - standalone, no package needed
"""
import random, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ng_transforms.rename_locals  import RenameLocalsPass
from ng_transforms.string_encrypt import StringEncryptPass
from ng_transforms.constant_split import ConstantSplitPass
from ng_transforms.dead_code      import DeadCodePass
from ng_transforms.control_flow   import ControlFlowPass

class TransformPipeline:
    def __init__(self, rng, options=None):
        opts = options or {}
        self.rng = rng
        self.string_table = {}
        self._enc_pass = None
        self._passes = []
        if opts.get("rename", True):
            self._passes.append(RenameLocalsPass(rng))
        if opts.get("const_split", True):
            self._passes.append(ConstantSplitPass(rng))
        if opts.get("string_encrypt", True):
            enc = StringEncryptPass(rng)
            self._passes.append(enc)
            self._enc_pass = enc
        if opts.get("dead_code", True):
            self._passes.append(DeadCodePass(rng))
        if opts.get("control_flow", True):
            self._passes.append(ControlFlowPass(rng))

    def run(self, block):
        node = block
        for p in self._passes:
            node = p.visit(node)
        if self._enc_pass:
            self.string_table = self._enc_pass.string_table
        return node
