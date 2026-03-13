-- Junk Variant A: Simple math accumulator
elseif _ST == _S_JUNK1 then
    _junk1 = (_junk1 + _pc * 31) % 65536
    _ST = _S_JUNK2
elseif _ST == _S_JUNK2 then
    _junk2 = (_junk2 ~ _junk1 + (_ins % 256)) % 65536
    _ST = _S_DECODE
