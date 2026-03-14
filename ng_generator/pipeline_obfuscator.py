"""
NightGuard V4 - Pipeline Obfuscator
Applies Phase 3 obfuscation to assembled VM source.
Final output is stripped of all comments, blank lines, and
leading/trailing whitespace — no readability hints for attackers.
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from ng_transforms.cfo_vm_interp  import obfuscate_vm_source
from ng_antitamper.watermark      import inject_watermark
from ng_generator.lua_minifier    import minify, minify_and_fix
from ng_antitamper.linecheck      import inject_linechecks


def obfuscate_pipeline_output(vm_source: str,
                               script_source: str,
                               user_id: str = "anonymous",
                               passes: int = 2) -> str:
    """
    Apply full Phase 3 obfuscation to VM source.
    passes: 1-3  (more = stronger but larger output)
    Minifies after every pass so no comment/whitespace leaks through.
    """
    result = minify_and_fix(vm_source)

    # Pass 1: opaques + strings + numbers (no mangle yet)
    result = obfuscate_vm_source(
        result, script_source,
        mangle=False, opaques=True,
        strings=True, numbers=True
    )
    result = minify_and_fix(result)

    # Pass 2: extra opaques
    if passes >= 2:
        result = obfuscate_vm_source(
            result, script_source + "_p2",
            mangle=False, opaques=True,
            strings=False, numbers=False
        )
        result = minify_and_fix(result)

    # Pass 3: extra numbers
    if passes >= 3:
        result = obfuscate_vm_source(
            result, script_source + "_p3",
            mangle=False, opaques=False,
            strings=False, numbers=True
        )
        result = minify_and_fix(result)

    # Final: mangle names (always last)
    result = obfuscate_vm_source(
        result, script_source,
        mangle=True, opaques=False,
        strings=False, numbers=False
    )
    result = minify_and_fix(result)

    # Inject watermark then strip again (watermark adds numeric lines, safe)
    result = inject_watermark(result, script_source, user_id)
    result = minify_and_fix(result)

    # Line checks must be injected last so expected line numbers stay valid.
    result = inject_linechecks(result)

    return result


def full_v4_pipeline(script_source: str,
                      encrypted_blob: list,
                      user_id: str = "anonymous",
                      obf_passes: int = 2,
                      enc_key: list | None = None,
                      enc_seed: int | None = None) -> str:
    """
    Complete V4 pipeline (Phase 1+2+3):
    assemble VM → obfuscate VM source → inject watermark → append blob call
    Output is one continuous block: no comments, no blank lines.
    """
    from ng_generator.vm_assembler import assemble_vm
    from ng_crypto.key_schedule    import derive_key, derive_seed

    def _tbl(v): return "{" + ",".join(str(x) for x in v) + "}"

    # Phase 1+2: assemble (already minified inside assemble_vm)
    vm = assemble_vm(script_source)

    # Phase 3: obfuscate + watermark + final minify
    vm = obfuscate_pipeline_output(vm, script_source, user_id, obf_passes)

    # Encrypted blob call — compact, no spaces, no newlines between decls
    seg   = len(encrypted_blob) // 3
    bc1   = encrypted_blob[:seg]
    bc2   = encrypted_blob[seg:seg*2]
    bc3   = encrypted_blob[seg*2:]
    key   = list(enc_key) if enc_key is not None else list(derive_key(script_source, 32))
    seed  = int(enc_seed) if enc_seed is not None else derive_seed(script_source)

    call = (
        f"local _NG_bc1={_tbl(bc1)}"
        f" local _NG_bc2={_tbl(bc2)}"
        f" local _NG_bc3={_tbl(bc3)}"
        f" local _NG_blob={{}}"
        f" for i=1,#_NG_bc1 do _NG_blob[#_NG_blob+1]=_NG_bc1[i] end"
        f" for i=1,#_NG_bc2 do _NG_blob[#_NG_blob+1]=_NG_bc2[i] end"
        f" for i=1,#_NG_bc3 do _NG_blob[#_NG_blob+1]=_NG_bc3[i] end"
        f" local _NG_key={_tbl(key)}"
        f" local _NG_seed={seed}"
        f" _NG_L1(_NG_blob,_NG_key,_NG_seed,_NG_L2)"
    )

    bit32_shim = (
        "if not bit32 then bit32={}"
        " bit32.bxor=(bit and bit.bxor) or function(a,b) local r,m=0,1 while a>0 or b>0 do local x,y=a%2,b%2 if x~=y then r=r+m end a,b,m=math.floor(a/2),math.floor(b/2),m*2 end return r end"
        " end"
    )

    # Join shim + VM + call
    return bit32_shim + "\n" + vm + "\n" + call
