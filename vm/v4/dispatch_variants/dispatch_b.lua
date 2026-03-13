-- Dispatch Variant B: pcall-wrapped dispatch
elseif _ST == _S_DISPATCH then
    if _op == _RET_OP then
        local _n = _b - 1
        if _n < 0 then _n = 0 end
        if _b == 1 then return end
        local _rv = {}
        for _i = 0, _n-1 do _rv[_i+1] = _R[_a+_i] end
        return (table.unpack or unpack)(_rv, 1, _n)
    end
    local _h = _H[_op]
    if _h then
        local _ok, _err = pcall(_h, _a, _b, _c, _bx, _sbx)
        if not _ok then error(_err, 0) end
    end
    _ST = _S_ADVANCE
