-- NightGuard V4 - Buffer-based Register File
-- Luau specific: uses buffer library for register storage
-- Falls back to plain table for standard Lua 5.1

local _NG_make_regs
do
    local _has_buffer = type(buffer) == "table" and
                        type(buffer.create) == "function"

    if _has_buffer then
        -- ── Luau buffer-based registers ────────────────────────────────────
        -- Much harder to inspect/dump than plain table
        -- Layout per register (16 bytes):
        --   [0..7]  f64 value
        --   [8]     type tag (0=nil, 1=number, 2=boolean_true,
        --                     3=boolean_false, 4=string/table/function)
        --   [9..15] padding

        local _REG_SIZE   = 16
        local _TYPE_NIL   = 0
        local _TYPE_NUM   = 1
        local _TYPE_TRUE  = 2
        local _TYPE_FALSE = 3
        local _TYPE_OBJ   = 4

        _NG_make_regs = function(max_regs)
            local _buf   = buffer.create((max_regs + 16) * _REG_SIZE)
            local _objs  = {}  -- string/table/function refs (not in buffer)
            local _obj_n = 0

            local regs = {}

            function regs.get(i)
                local base = i * _REG_SIZE
                local t    = buffer.readu8(_buf, base + 8)
                if t == _TYPE_NIL  then return nil
                elseif t == _TYPE_NUM  then return buffer.readf64(_buf, base)
                elseif t == _TYPE_TRUE then return true
                elseif t == _TYPE_FALSE then return false
                else
                    -- Object type: index into _objs
                    local idx = buffer.readu32(_buf, base)
                    return _objs[idx]
                end
            end

            function regs.set(i, v)
                local base = i * _REG_SIZE
                local t    = type(v)
                if v == nil then
                    buffer.writeu8(_buf, base + 8, _TYPE_NIL)
                elseif t == "number" then
                    buffer.writef64(_buf, base, v)
                    buffer.writeu8(_buf, base + 8, _TYPE_NUM)
                elseif t == "boolean" then
                    buffer.writeu8(_buf, base + 8,
                        v and _TYPE_TRUE or _TYPE_FALSE)
                else
                    -- Store object reference
                    _obj_n = _obj_n + 1
                    _objs[_obj_n] = v
                    buffer.writeu32(_buf, base, _obj_n)
                    buffer.writeu8(_buf, base + 8, _TYPE_OBJ)
                end
            end

            function regs.wipe()
                -- Overwrite buffer with zeros (anti-dump)
                for i = 0, (max_regs + 16) * _REG_SIZE - 1 do
                    buffer.writeu8(_buf, i, 0)
                end
                _objs = {}
                _obj_n = 0
            end

            return regs
        end
    else
        -- ── Lua 5.1 fallback: plain table ──────────────────────────────────
        _NG_make_regs = function(max_regs)
            local _R = {}
            for i = 0, max_regs + 8 do _R[i] = nil end

            local regs = {}
            function regs.get(i)   return _R[i] end
            function regs.set(i,v) _R[i] = v    end
            function regs.wipe()
                for i = 0, max_regs + 8 do _R[i] = nil end
            end
            return regs
        end
    end
end
