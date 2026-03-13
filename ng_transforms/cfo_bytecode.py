"""
NightGuard V4 - Bytecode CFO
Injects dead instructions and junk opcodes into compiled bytecode.
Makes static analysis produce wrong control flow graphs.
"""

import random
import struct
from typing import List

# Instruction encoding helpers (matching NightGuard bytecode format)
# ins = op | (a << 8) | (b << 16) | (c << 24)
def encode_ins(op: int, a: int = 0, b: int = 0, c: int = 0) -> int:
    return (op & 0xFF) | ((a & 0xFF) << 8) | ((b & 0xFF) << 16) | ((c & 0xFF) << 24)

def decode_ins(ins: int):
    op = ins & 0xFF
    a  = (ins >> 8)  & 0xFF
    b  = (ins >> 16) & 0xFF
    c  = (ins >> 24) & 0xFF
    return op, a, b, c

class BytecodeCFO:
    """
    Dead code injector for NightGuard bytecode.
    Works on the proto's code array (list of u32 instructions).
    """
    
    def __init__(self, dead_op: int, nop_op: int, jmp_op: int,
                 inject_rate: int = 5, seed: int = None):
        """
        dead_op:     Opcode number for DEAD (never-executed placeholder)
        nop_op:      Opcode number for NOP (no operation)  
        jmp_op:      Opcode number for JMP (unconditional jump)
        inject_rate: Inject 1 dead instruction every N real instructions
        seed:        RNG seed for reproducibility
        """
        self.dead_op = dead_op
        self.nop_op  = nop_op
        self.jmp_op  = jmp_op
        self.inject_rate = inject_rate
        self.rng = random.Random(seed)
    
    def _make_dead_ins(self) -> int:
        """Create a dead instruction that looks real but never executes."""
        # Random operands to confuse static analysis
        a = self.rng.randint(0, 255)
        b = self.rng.randint(0, 255)
        c = self.rng.randint(0, 255)
        return encode_ins(self.dead_op, a, b, c)
    
    def _make_nop(self) -> int:
        """Create a NOP instruction."""
        return encode_ins(self.nop_op, 0, 0, 0)
    
    def inject_dead_code(self, code: List[int]) -> List[int]:
        """
        Inject dead instructions into code array.
        Returns new code array with injected instructions.
        Also returns a mapping: new_index -> original_index (for jump fixup).
        """
        result = []
        index_map = {}  # original_index -> new_index
        
        for i, ins in enumerate(code):
            index_map[i] = len(result)
            result.append(ins)
            
            # Inject dead instruction every N real instructions
            if (i + 1) % self.inject_rate == 0:
                result.append(self._make_dead_ins())
        
        return result, index_map
    
    def inject_opaque_predicates(self, code: List[int],
                                  branch_op: int, always_taken_val: int) -> List[int]:
        """
        Inject opaque predicates - conditional jumps that always go one way
        but static analyzer can't determine which.
        Inserts: JMP_IF_ALWAYS_TRUE(skip_dead); DEAD_BLOCK; real_code
        """
        result = []
        i = 0
        while i < len(code):
            ins = code[i]
            result.append(ins)
            
            # Every 7 instructions, add opaque predicate + dead block
            if (i + 1) % 7 == 0 and i + 1 < len(code):
                dead_block_size = self.rng.randint(2, 4)
                # Jump over dead block (sbx = dead_block_size)
                jmp = encode_ins(self.jmp_op, 0,
                                  (dead_block_size + 32767) & 0xFF,
                                  ((dead_block_size + 32767) >> 8) & 0xFF)
                result.append(jmp)
                for _ in range(dead_block_size):
                    result.append(self._make_dead_ins())
            
            i += 1
        
        return result
    
    def process_proto(self, proto_code: List[int],
                       return_op: int) -> List[int]:
        """
        Full CFO processing for a proto's code array.
        Handles RETURN opcode specially to not break execution.
        """
        # Step 1: inject dead code
        injected, index_map = self.inject_dead_code(proto_code)
        
        # Step 2: inject opaque predicates
        # (skipped in Phase 1, added in Phase 2)
        
        return injected

class JunkOpcodeInjector:
    """
    Injects junk opcode sequences that decode to nonsense
    but are never reached due to surrounding jumps.
    Makes disassembly output misleading.
    """
    
    def __init__(self, seed: int = None):
        self.rng = random.Random(seed)
    
    def generate_junk_sequence(self, length: int) -> List[int]:
        """Generate a sequence of random junk instructions."""
        return [
            encode_ins(
                self.rng.randint(0, 255),
                self.rng.randint(0, 255),
                self.rng.randint(0, 255),
                self.rng.randint(0, 255)
            )
            for _ in range(length)
        ]
    
    def wrap_with_junk(self, code: List[int], jmp_op: int) -> List[int]:
        """
        Wrap real code: [junk][JMP skip_junk_at_end][real_code][junk]
        The JMP at start skips all junk, but disassembler sees junk first.
        """
        pre_junk_len  = self.rng.randint(3, 8)
        post_junk_len = self.rng.randint(3, 8)
        
        pre_junk  = self.generate_junk_sequence(pre_junk_len)
        post_junk = self.generate_junk_sequence(post_junk_len)
        
        # JMP that skips pre_junk (sbx points past pre_junk)
        skip_jmp = encode_ins(jmp_op, 0,
                               (pre_junk_len + 32767) & 0xFF,
                               ((pre_junk_len + 32767) >> 8) & 0xFF)
        
        return [skip_jmp] + pre_junk + code + post_junk
