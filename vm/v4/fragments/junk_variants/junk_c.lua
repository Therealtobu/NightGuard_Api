-- Junk Variant C: pcall junk + fake table ops
elseif _ST == _S_JUNK1 then
    local _ok = pcall(function()
        _junk1 = (_pc * 6364136223846793005) % 65536
    end)
    _ST = _S_JUNK2
elseif _ST == _S_JUNK2 then
    -- Fake table op (never stored anywhere useful)
    local _tmp = {_junk1, _junk2, _pc % 256}
    _junk2 = (_tmp[1] + _tmp[2]) % 65536
    _tmp = nil
    _ST = _S_DECODE
