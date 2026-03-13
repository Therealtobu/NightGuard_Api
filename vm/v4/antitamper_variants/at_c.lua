-- Anti-Tamper Variant C: Stack depth + line check combo
elseif _ST == _S_ADVANCE then
    if _pc % 41 == 0 then
        -- Stack depth check
        if _NG_SC_check_fn then _NG_SC_check_fn() end
    end
    if _pc % 97 == 0 then
        -- Type integrity check
        if type(math.floor) ~= "function" or
           type(pcall)       ~= "function" or
           type(tostring)    ~= "function" then
            local _t = {}
            repeat _t[#_t+1] = 0 until #_t > 50000
        end
    end
    _ST = _S_FETCH
