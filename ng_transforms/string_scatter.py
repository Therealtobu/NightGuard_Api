import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
"""NightGuard V2 - String Scatter Pass

Splits each encrypted string's byte array into 2-4 chunks.
At runtime the VM re-joins them → static analysis sees no contiguous byte array.
Also injects fake/noise chunks that are never used.

Works as a post-process on the string_table after StringEncryptPass.
"""
import random

def scatter_string_table(string_table: dict, rng) -> dict:
    """
    Returns a new string_table where each entry is:
      (enc_bytes, seed, step, sub_key, chunks)
    chunks: list of (start, length) slice descriptors → VM reassembles in order
    """
    new_table = {}
    for idx, entry in string_table.items():
        if len(entry) == 4:
            enc_bytes, seed, step, sub_key = entry
        else:
            enc_bytes, seed, step = entry; sub_key = 0

        n = len(enc_bytes)
        if n < 4:
            new_table[idx] = (enc_bytes, seed, step, sub_key, None)
            continue

        # Split into 2-4 chunks
        n_chunks = rng.randint(2, min(4, n))
        cuts = sorted(rng.sample(range(1, n), n_chunks - 1))
        starts = [0] + cuts
        ends   = cuts + [n]
        chunks = [(s, e-s) for s, e in zip(starts, ends)]

        # Inject 1-2 noise chunks (wrong offsets, never referenced)
        noise_count = rng.randint(1, 2)
        noise = [(rng.randint(0, n-1), rng.randint(1, max(1, n//4))) for _ in range(noise_count)]

        new_table[idx] = (enc_bytes, seed, step, sub_key, chunks, noise)
    return new_table
