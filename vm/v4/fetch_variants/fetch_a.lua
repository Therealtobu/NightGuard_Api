-- Fetch Variant A: Standard sequential with random junk routing
if _ST == _S_FETCH then
    if _pc > #_CD then break end
    _ins = _CD[_pc]
    _pc  = _pc + 1
    _FL  = (_FL * 1103515245 + 12345) % 0x80000000
    _ST  = (_FL % 3 == 0) and _S_JUNK1 or _S_DECODE
