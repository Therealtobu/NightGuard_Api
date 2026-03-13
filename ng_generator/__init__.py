"""NightGuard V4 - VM Generator Module"""
from .opcode_shuffler import generate_opcode_map, get_return_op, apply_mapping_to_bytecode
from .state_builder import generate_state_ids, generate_flow_seed, generate_junk_expressions
from .junk_builder import generate_vm_junk_blocks, generate_fake_constant_table
from .vm_assembler import assemble_vm, assemble_final_output
