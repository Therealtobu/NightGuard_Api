import sys, os, random, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

"""NightGuard V3/V4 — Transform Pipeline"""

# ── V3 AST transform imports ──────────────────────────────────────────────────
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

    def __init__(self, rng, options=None):
        opts = options or {}
        self.rng          = rng
        self.string_table = {}
        self._enc_pass    = None
        self._passes      = []

        if opts.get('rename',         True):
            self._passes.append(RenameLocalsPass(rng))
        if opts.get('anti_tamper',    True):
            self._passes.append(AntiTamperPass(rng))
        if opts.get('const_split',    True):
            self._passes.append(ConstantSplitPass(rng))
        if opts.get('mba',            True):
            self._passes.append(MBATransform(rng, prob=0.45))
        if opts.get('string_encrypt', True):
            enc = StringEncryptPass(rng)
            self._passes.append(enc)
            self._enc_pass = enc
        if opts.get('dead_code',    True):
            self._passes.append(DeadCodePass(rng, insert_prob=0.20,
                                             wrap_prob=0.0, end_prob=0.12))
        if opts.get('control_flow', True):
            self._passes.append(ControlFlowPass(rng, flatten_prob=0.30,
                                                guard_prob=0.08, dead_prob=0.08))

    def run(self, block):
        node = block
        for p in self._passes:
            node = p.visit(node)
        if self._enc_pass:
            self.string_table = scatter_string_table(
                self._enc_pass.string_table, self.rng)
        return node


# ── V4 pipeline ───────────────────────────────────────────────────────────────

def obfuscate_v4(source: str,
                  seed=None,
                  options=None,
                  progress_cb=None,
                  user_id: str = 'anonymous',
                  obf_passes: int = 2) -> str:
    """
    NightGuard V4 full pipeline.

    Layer order:
      1  Parse              - source text -> AST
      2  V3 AST transforms  - rename / MBA / string-encrypt / dead-code / CFO
      3  Compile            - transformed AST -> register-based proto
      4  Serialize          - proto -> raw byte array
      5  Compress           - zlib deflate
      6  Whitebox-XOR       - per-script unique key encryption
      7  Bytecode CFO       - dead/NOP instruction injection into encrypted blob
      8  Double VM assembly - Layer1 (deserialise+validate) + Layer2 (execute)
      9  VM source obf      - Phase-3 AST CFO on VM Lua source
      10 Watermark          - hidden numeric watermark for user_id
    """
    def _cb(stage, detail=''):
        if progress_cb: progress_cb(stage, detail)

    if seed is None:
        seed = int(time.time() * 1000) & 0xFFFFFFFF

    opts = options or {}
    rng  = random.Random(seed)

    # ── 1. Parse ──────────────────────────────────────────────────────────────
    _cb('parse', f'{len(source):,} chars')
    from parser import parse
    ast = parse(source)

    # ── 2. V3 AST Transforms ─────────────────────────────────────────────────
    # Exact same passes as V3: rename -> anti-tamper -> const-split ->
    #                          MBA -> string-encrypt -> dead-code -> CFO
    for stage in ('rename_locals', 'anti_tamper', 'const_split',
                  'mba', 'string_encrypt', 'dead_code', 'control_flow'):
        _cb(stage, '')

    pipeline = TransformPipeline(rng, opts)
    ast2     = pipeline.run(ast)

    # ── 3. Compile transformed AST -> proto ───────────────────────────────────
    _cb('compile', 'AST -> register bytecode')
    from ng_compiler.opcodes    import Opcodes
    from ng_compiler.compiler   import Compiler
    from ng_compiler.serializer import serialize_proto

    opcodes  = Opcodes(seed=rng.randint(0, 2**31), shuffle=False)
    compiler = Compiler(opcodes, rng, pipeline.string_table)
    proto    = compiler.compile(ast2)

    # Remap compiled opcodes to match per-script V4 VM opcode shuffle.
    from ng_generator.opcode_shuffler import generate_opcode_map, apply_mapping_to_bytecode
    opmap = generate_opcode_map(source)

    def _remap_proto_ops(p):
        p.code = apply_mapping_to_bytecode(p.code, opmap)
        for child in p.protos:
            _remap_proto_ops(child)

    _remap_proto_ops(proto)

    # ── 4. Serialize proto -> raw bytes ───────────────────────────────────────
    _cb('serialize', 'proto -> byte array')
    raw = serialize_proto(proto)
    if not isinstance(raw, (bytes, bytearray)):
        raw = bytes(raw)

    # ── 5+6. Compress + whitebox-XOR encrypt ─────────────────────────────────
    _cb('v4_crypto',   'deriving per-script keys')
    _cb('v4_compress', f'compressing {len(raw):,} bytes')
    _cb('v4_encrypt',  'whitebox-XOR encrypt')

    from ng_crypto.compression  import compress
    from ng_compiler.serializer import encrypt_bytecode

    compressed = compress(raw)
    encrypted, enc_key, enc_seed = encrypt_bytecode(compressed, rng)

    # ── 7. Bytecode CFO — dead/NOP injection into encrypted blob ─────────────
    _cb('v4_cfo', 'bytecode CFO injection')
    from ng_transforms.cfo_bytecode import BytecodeCFO
    cfo      = BytecodeCFO(dead_op=0xFE, nop_op=0xFD, jmp_op=0xFC,
                           inject_rate=5, seed=enc_seed)
    enc_blob, _ = cfo.inject_dead_code(list(encrypted))

    # ── 8+9+10. Double VM + VM-source obfuscation + watermark ─────────────────
    _cb('v4_vm_assemble', 'assembling double VM (L1 + L2)')
    _cb('v4_vm_obf',      'VM source obfuscation (Phase 3 CFO)')
    _cb('v4_watermark',   f'watermark -> {user_id!r}')

    from ng_generator.pipeline_obfuscator import full_v4_pipeline
    output = full_v4_pipeline(
        source,
        enc_blob,
        user_id=user_id,
        obf_passes=obf_passes,
        enc_key=enc_key,
        enc_seed=enc_seed,
    )

    _cb('v4_done', f'{len(output):,} chars output')
    return output
