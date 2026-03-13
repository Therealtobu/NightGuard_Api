"""
NightGuard V4 - Compression
Compress bytecode before encryption.
Pipeline: source → compile → compress → encrypt → VM
"""

import zlib
import struct

def compress(data: bytes) -> bytes:
    """
    Compress bytecode with zlib level 9.
    Prepend original length for decompressor.
    """
    original_len = len(data)
    compressed = zlib.compress(data, level=9)
    # Header: [4 bytes original length][compressed data]
    return struct.pack(">I", original_len) + compressed

def decompress(data: bytes) -> bytes:
    """Decompress data compressed with compress()."""
    original_len = struct.unpack(">I", data[:4])[0]
    compressed = data[4:]
    result = zlib.decompress(compressed)
    assert len(result) == original_len, "Decompression length mismatch"
    return result

def compress_bytelist(data: bytes) -> list:
    """Compress and return as list of ints for embedding in Lua."""
    return list(compress(data))

# ── Lua 5.1 compatible decompressor ──────────────────────────────────────────
# Injected into Layer1 VM template
# Pure Lua implementation of zlib inflate (deflate decompression)
# This is a minimal implementation sufficient for our compressed bytecode

LUA_DECOMPRESSOR = r"""
-- NightGuard V4: Pure Lua zlib decompressor (Lua 5.1 compatible)
local _NG_decompress
do
    -- Lookup tables for deflate
    local _lens   = {3,4,5,6,7,8,9,10,11,13,15,17,19,23,27,31,35,43,51,59,67,83,99,115,131,163,195,227,258}
    local _lext   = {0,0,0,0,0,0,0,0,1,1,1,1,2,2,2,2,3,3,3,3,4,4,4,4,5,5,5,5,0}
    local _dists  = {1,2,3,4,5,7,9,13,17,25,33,49,65,97,129,193,257,385,513,769,1025,1537,2049,3073,4097,6145,8193,12289,16385,24577}
    local _dext   = {0,0,0,0,1,1,2,2,3,3,4,4,5,5,6,6,7,7,8,8,9,9,10,10,11,11,12,12,13,13}

    local function _build_tree(lengths)
        local counts = {}
        for i = 1, #lengths do
            local l = lengths[i]
            if l > 0 then counts[l] = (counts[l] or 0) + 1 end
        end
        local next_code = {}
        local code = 0
        for bits = 1, 15 do
            code = (code + (counts[bits-1] or 0)) * 2
            next_code[bits] = code
        end
        local tree = {}
        for i = 1, #lengths do
            local l = lengths[i]
            if l > 0 then
                local c = next_code[l]
                next_code[l] = c + 1
                tree[c * 16 + l] = i - 1
            end
        end
        return tree
    end

    local function _read_bits(state, n)
        while state.bits < n do
            state.byte = state.data[state.pos]
            state.pos  = state.pos + 1
            state.buf  = state.buf + state.byte * (2 ^ state.bits)
            state.bits = state.bits + 8
        end
        local v = state.buf % (2 ^ n)
        state.buf  = math.floor(state.buf / (2 ^ n))
        state.bits = state.bits - n
        return v
    end

    local function _read_tree_sym(state, tree, max_bits)
        local code = 0
        for bits = 1, max_bits do
            local b = _read_bits(state, 1)
            code = code * 2 + b
            local sym = tree[code * 16 + bits]
            if sym ~= nil then return sym end
        end
        error("invalid tree symbol")
    end

    local function _inflate_block(state, out, lit_tree, dist_tree)
        while true do
            local sym = _read_tree_sym(state, lit_tree, 15)
            if sym < 256 then
                out[#out + 1] = sym
            elseif sym == 256 then
                break
            else
                local li   = sym - 257
                local len  = _lens[li + 1] + _read_bits(state, _lext[li + 1])
                local di   = _read_tree_sym(state, dist_tree, 15)
                local dist = _dists[di + 1] + _read_bits(state, _dext[di + 1])
                local base = #out - dist
                for i = 1, len do
                    out[#out + 1] = out[base + i]
                end
            end
        end
    end

    local _fixed_lit, _fixed_dist
    do
        local fl = {}
        for i = 0,   143 do fl[i+1] = 8 end
        for i = 144, 255 do fl[i+1] = 9 end
        for i = 256, 279 do fl[i+1] = 7 end
        for i = 280, 287 do fl[i+1] = 8 end
        _fixed_lit  = _build_tree(fl)
        local fd = {}
        for i = 0, 29 do fd[i+1] = 5 end
        _fixed_dist = _build_tree(fd)
    end

    _NG_decompress = function(data)
        -- Skip 2-byte zlib header + 4-byte original length prefix
        local state = {
            data = data,
            pos  = 7,   -- skip: 4 (orig_len) + 2 (zlib hdr) + 1-indexed
            buf  = 0,
            bits = 0,
            byte = 0
        }
        local out = {}
        local done = false
        while not done do
            local bfinal = _read_bits(state, 1)
            local btype  = _read_bits(state, 2)
            if btype == 0 then
                -- Stored block
                state.buf  = 0
                state.bits = 0
                local len  = data[state.pos] + data[state.pos+1] * 256
                state.pos  = state.pos + 4
                for _ = 1, len do
                    out[#out+1] = data[state.pos]
                    state.pos   = state.pos + 1
                end
            elseif btype == 1 then
                _inflate_block(state, out, _fixed_lit, _fixed_dist)
            elseif btype == 2 then
                local hlit  = _read_bits(state, 5) + 257
                local hdist = _read_bits(state, 5) + 1
                local hclen = _read_bits(state, 4) + 4
                local cl_order = {16,17,18,0,8,7,9,6,10,5,11,4,12,3,13,2,14,1,15}
                local cl_lens  = {}
                for i = 1, 19 do cl_lens[i] = 0 end
                for i = 1, hclen do
                    cl_lens[cl_order[i] + 1] = _read_bits(state, 3)
                end
                local cl_tree = _build_tree(cl_lens)
                local all_lens = {}
                local ai = 1
                while ai <= hlit + hdist do
                    local sym = _read_tree_sym(state, cl_tree, 7)
                    if sym < 16 then
                        all_lens[ai] = sym; ai = ai + 1
                    elseif sym == 16 then
                        local rep = _read_bits(state, 2) + 3
                        local prev = all_lens[ai-1]
                        for _ = 1, rep do all_lens[ai] = prev; ai = ai + 1 end
                    elseif sym == 17 then
                        local rep = _read_bits(state, 3) + 3
                        for _ = 1, rep do all_lens[ai] = 0; ai = ai + 1 end
                    else
                        local rep = _read_bits(state, 7) + 11
                        for _ = 1, rep do all_lens[ai] = 0; ai = ai + 1 end
                    end
                end
                local ll = {}
                for i = 1, hlit  do ll[i] = all_lens[i] end
                local dl = {}
                for i = 1, hdist do dl[i] = all_lens[hlit + i] end
                _inflate_block(state, out, _build_tree(ll), _build_tree(dl))
            else
                error("reserved block type")
            end
            if bfinal == 1 then done = true end
        end
        return out
    end
end
"""
