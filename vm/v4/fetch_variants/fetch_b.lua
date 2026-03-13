-- Fetch Variant B: PC bounds check + XOR decode
if _ST == _S_FETCH then
    if _pc < 1 or _pc > #_CD then break end
    local _raw = _CD[_pc]
    _ins = _raw
    _pc  = _pc + 1
    -- Flow mutation depends on instruction content
    _FL  = (_FL + (_ins % 256) * 6364136223846793005) % 0x80000000
    _ST  = (_FL % 4 == 0) and _S_JUNK2
        or (_FL % 4 == 1) and _S_JUNK1
        or _S_DECODE
