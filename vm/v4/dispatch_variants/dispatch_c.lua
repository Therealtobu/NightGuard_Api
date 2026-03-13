-- Dispatch Variant C: XOR-obfuscated handler lookup
elseif _ST == _S_DISPATCH then
    if _op == _RET_OP then
        local _n = _b - 1
        if _n < 0 then _n = 0 end
        if _b == 1 then return end
        local _rv = {}
        for _i = 0, _n-1 do _rv[_i+1] = _R[_a+_i] end
        return (table.unpack or unpack)(_rv, 1, _n)
    end
    -- Lookup via XOR key (unique per script, filled by generator)
    local _key = _NG_DK  -- dispatch key constant
    local _idx = _op ~ _key
    local _h   = _H[_idx]
    if not _h then _h = _H[_op] end  -- fallback
    if _h then _h(_a, _b, _c, _bx, _sbx) end
    _ST = _S_ADVANCE
