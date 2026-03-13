"""
NightGuard — Stage Definitions
Single source of truth for V3 + V4 stages.
Imported by cli.py, bot.py, ng_pipeline.py.
"""

# ── V3 stages ─────────────────────────────────────────────────────────────────
V3_STAGES = [
    ("parse",          "Parsing source"),
    ("rename_locals",  "Renaming locals"),
    ("anti_tamper",    "Injecting anti-tamper"),
    ("const_split",    "Splitting constants"),
    ("mba",            "MBA transforms"),
    ("string_encrypt", "Encrypting strings"),
    ("dead_code",      "Injecting dead code"),
    ("control_flow",   "Flattening control flow"),
    ("compile",        "Compiling AST → bytecode"),
    ("serialize",      "Serializing proto"),
    ("vm_gen",         "Generating VM"),
    ("finalize",       "Encoding output"),
]

# ── V4 stages ─────────────────────────────────────────────────────────────────
V4_STAGES = [
    ("v4_crypto",      "Deriving per-script keys"),
    ("v4_compress",    "Compressing bytecode"),
    ("v4_encrypt",     "Encrypting (whitebox XOR)"),
    ("v4_cfo",         "Injecting bytecode CFO"),
    ("v4_vm_assemble", "Assembling double VM"),
    ("v4_vm_obf",      "Obfuscating VM source"),
    ("v4_watermark",   "Injecting watermark"),
    ("v4_done",        "Finalizing output"),
]

# ── Helpers ───────────────────────────────────────────────────────────────────
def get_stages(version: int) -> list:
    """Return stages list for given version (3 or 4)."""
    return V3_STAGES if version == 3 else V4_STAGES

def stage_map(version: int) -> dict:
    """Return {stage_id: label} for given version."""
    return dict(get_stages(version))

def stage_order(version: int) -> list:
    """Return ordered list of stage IDs for given version."""
    return [s for s, _ in get_stages(version)]

# Legacy alias so old bot.py `from cli import STAGES` still works
STAGES = V3_STAGES
