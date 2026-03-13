-- Anti-Tamper Variant B: Upvalue sentinel + timing
elseif _ST == _S_ADVANCE then
    if _pc % 23 == 0 then
        -- Check upvalue sentinel
        if _NG_UP_check then _NG_UP_check() end
        -- Check timing (every 23 instructions)
        if _pc % 253 == 0 then
            if _NG_TC_check then _NG_TC_check() end
        end
    end
    _ST = _S_FETCH
