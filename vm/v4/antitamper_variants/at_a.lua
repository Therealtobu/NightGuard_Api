-- Anti-Tamper Variant A: Periodic anti-debug check
elseif _ST == _S_ADVANCE then
    if _pc % 31 == 0 then
        if type(math.floor) ~= "function" then
            local _t = {}
            repeat _t[#_t+1] = 0 until #_t > 50000
        end
    end
    _ST = _S_FETCH
