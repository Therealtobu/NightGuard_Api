-- Junk Variant B: Register peek + flow hash
elseif _ST == _S_JUNK1 then
    local _rv = _R[0] or 0
    _junk1 = (_FL + _rv * 7 + _pc) % 65536
    _ST = _S_JUNK2
elseif _ST == _S_JUNK2 then
    _junk2 = (_junk1 * 1103515245 + 12345) % 0x80000000
    local _ = _junk2 % 256
    _ST = _S_DECODE
