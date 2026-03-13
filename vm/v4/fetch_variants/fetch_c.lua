-- Fetch Variant C: PC hash + double-step flow mutation
if _ST == _S_FETCH then
    if _pc > #_CD then break end
    _ins = _CD[_pc]
    _pc  = _pc + 1
    -- Double mutation
    _FL  = (_FL * 69069 + 1) % 0x80000000
    _FL  = (_FL + _pc * 1013904223) % 0x80000000
    local _r = _FL % 5
    if     _r == 0 then _ST = _S_JUNK1
    elseif _r == 1 then _ST = _S_JUNK2
    else                _ST = _S_DECODE
    end
