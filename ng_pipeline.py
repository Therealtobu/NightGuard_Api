import sys,os;sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
"""NightGuard V3/V4 — Transform Pipeline"""
import random,time

# ── V3 imports ────────────────────────────────────────────────────────────────
from ng_transforms.rename_locals  import RenameLocalsPass
from ng_transforms.string_encrypt import StringEncryptPass
from ng_transforms.constant_split import ConstantSplitPass
from ng_transforms.mba_transform  import MBATransform
from ng_transforms.dead_code      import DeadCodePass
from ng_transforms.control_flow   import ControlFlowPass
from ng_transforms.watermark      import AntiTamperPass
from ng_transforms.string_scatter import scatter_string_table

class TransformPipeline:
    """V3 AST transform pipeline — unchanged from original."""
    def __init__(self,rng,options=None):
        opts=options or {}
        self.rng=rng
        self.string_table={}
        self._enc_pass=None
        self._passes=[]

        if opts.get('rename',True):
            self._passes.append(RenameLocalsPass(rng))
        if opts.get('anti_tamper',True):
            self._passes.append(AntiTamperPass(rng))
        if opts.get('const_split',True):
            self._passes.append(ConstantSplitPass(rng))
        if opts.get('mba',True):
            self._passes.append(MBATransform(rng,prob=0.45))
        if opts.get('string_encrypt',True):
            enc=StringEncryptPass(rng)
            self._passes.append(enc)
            self._enc_pass=enc
        if opts.get('dead_code',True):
            self._passes.append(DeadCodePass(rng,insert_prob=0.20,wrap_prob=0.0,end_prob=0.12))
        if opts.get('control_flow',True):
            self._passes.append(ControlFlowPass(rng,flatten_prob=0.30,guard_prob=0.08,dead_prob=0.08))

    def run(self,block):
        node=block
        for p in self._passes:
            node=p.visit(node)
        if self._enc_pass:
            raw_st=self._enc_pass.string_table
            self.string_table=scatter_string_table(raw_st,self.rng)
        return node


# ── V4 pipeline ───────────────────────────────────────────────────────────────

def obfuscate_v4(source:str,
                  seed=None,
                  options=None,
                  progress_cb=None,
                  user_id:str='anonymous',
                  obf_passes:int=2) -> str:
    """NightGuard V4 full pipeline."""
    def _cb(stage,detail=''):
        if progress_cb: progress_cb(stage,detail)

    if seed is None: seed=int(time.time()*1000)&0xFFFFFFFF

    # ── Crypto ────────────────────────────────────────────────────────────────
    _cb('v4_crypto', 'deriving per-script keys')
    from ng_crypto.key_schedule import derive_key, derive_seed
    from ng_crypto.compression  import compress
    from ng_crypto.whitebox     import apply_whitebox   # function, not class

    enc_key  = bytes(derive_key(source, 32))
    enc_seed = derive_seed(source)

    # ── Compress ──────────────────────────────────────────────────────────────
    _cb('v4_compress', 'compressing bytecode')
    compressed = compress(source.encode('utf-8'))

    # ── Encrypt ───────────────────────────────────────────────────────────────
    _cb('v4_encrypt', 'encrypting with whitebox XOR')
    encrypted = bytes(apply_whitebox(compressed, enc_key))

    # ── CFO ───────────────────────────────────────────────────────────────────
    _cb('v4_cfo', 'injecting bytecode CFO')
    from ng_transforms.cfo_bytecode import BytecodeCFO
    cfo      = BytecodeCFO(dead_op=0xFE, nop_op=0xFD, jmp_op=0xFC,
                           inject_rate=5, seed=enc_seed)
    enc_blob = cfo.inject_dead_code(list(encrypted))

    # ── VM assemble + obfuscate + watermark ───────────────────────────────────
    _cb('v4_vm_assemble', 'assembling VM')
    _cb('v4_vm_obf',      'obfuscating VM source')
    _cb('v4_watermark',   f'injecting watermark for {user_id!r}')
    from ng_generator.pipeline_obfuscator import full_v4_pipeline
    output = full_v4_pipeline(
        source,
        enc_blob,
        user_id=user_id,
        obf_passes=obf_passes,
    )

    _cb('v4_done', f'{len(output):,} chars')
    return output
