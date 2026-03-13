"""
NightGuard V4 - Pipeline Obfuscator
Applies Phase 3 obfuscation to assembled VM source.
The VM generator obfuscates its own output.
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from ng_transforms.cfo_vm_interp import obfuscate_vm_source
from ng_antitamper.watermark import inject_watermark

def obfuscate_pipeline_output(vm_source: str,
                               script_source: str,
                               user_id: str = "anonymous",
                               passes: int = 2) -> str:
    """
    Apply full Phase 3 obfuscation to VM source.
    passes: 1-3 (more = stronger but larger output)
    """
    result = vm_source

    # Pass 1: opaques + strings + numbers (no mangle yet)
    result = obfuscate_vm_source(
        result, script_source,
        mangle=False, opaques=True,
        strings=True, numbers=True
    )

    # Pass 2: extra opaques
    if passes >= 2:
        result = obfuscate_vm_source(
            result, script_source + "_p2",
            mangle=False, opaques=True,
            strings=False, numbers=False
        )

    # Pass 3: extra numbers
    if passes >= 3:
        result = obfuscate_vm_source(
            result, script_source + "_p3",
            mangle=False, opaques=False,
            strings=False, numbers=True
        )

    # Final: mangle names (always last)
    result = obfuscate_vm_source(
        result, script_source,
        mangle=True, opaques=False,
        strings=False, numbers=False
    )

    # Inject watermark
    result = inject_watermark(result, script_source, user_id)

    return result

def full_v4_pipeline(script_source: str,
                      encrypted_blob: list,
                      user_id: str = "anonymous",
                      obf_passes: int = 2) -> str:
    """
    Complete V4 pipeline (Phase 1+2+3):
    assemble VM → obfuscate VM source → inject watermark → combine blob
    """
    from ng_generator.vm_assembler import assemble_vm
    from ng_crypto.key_schedule import derive_key, derive_seed

    def _tbl(v): return "{" + ",".join(str(x) for x in v) + "}"

    # Phase 1+2: assemble
    vm = assemble_vm(script_source)

    # Phase 3: obfuscate + watermark
    vm = obfuscate_pipeline_output(vm, script_source, user_id, obf_passes)

    # Combine with encrypted blob
    seg  = len(encrypted_blob) // 3
    bc1  = encrypted_blob[:seg]
    bc2  = encrypted_blob[seg:seg*2]
    bc3  = encrypted_blob[seg*2:]
    key  = list(derive_key(script_source, 32))
    seed = derive_seed(script_source)

    call = (
        f"\nlocal _NG_bc1={_tbl(bc1)}"
        f"\nlocal _NG_bc2={_tbl(bc2)}"
        f"\nlocal _NG_bc3={_tbl(bc3)}"
        f"\nlocal _NG_key={_tbl(key)}"
        f"\nlocal _NG_seed={seed}"
        f"\n_NG_L1(_NG_bc1,_NG_bc2,_NG_bc3,_NG_key,_NG_seed,_NG_L2)\n"
    )

    return vm + "\n" + call
