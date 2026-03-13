-- NightGuard V4 - Coroutine Pool Dispatch
-- Each opcode handler runs in its own coroutine
-- Makes stack traces and execution tracing extremely difficult
-- Lua 5.1 / Luau compatible

local _NG_make_dispatch
do
    _NG_make_dispatch = function(handlers)
        -- ── Build coroutine pool ─────────────────────────────────────────
        local _pool    = {}
        local _mailbox = {}

        for op, fn in pairs(handlers) do
            local _co = coroutine.create(function()
                while true do
                    -- Wait for dispatch
                    local ctx = coroutine.yield()
                    if ctx == nil then break end
                    -- Execute handler
                    fn(ctx.a, ctx.b, ctx.c, ctx.bx, ctx.sbx)
                    -- Signal done
                    coroutine.yield(true)
                end
            end)
            -- Advance to first yield
            coroutine.resume(_co)
            _pool[op] = _co
        end

        -- ── Dispatch function ────────────────────────────────────────────
        local function _dispatch(op, a, b, c, bx, sbx)
            local co = _pool[op]
            if co == nil then return end

            -- Check coroutine is still alive
            if coroutine.status(co) ~= "suspended" then
                -- Recreate if dead (shouldn't happen normally)
                local fn = handlers[op]
                if fn then fn(a, b, c, bx, sbx) end
                return
            end

            local ctx = {
                a   = a,
                b   = b,
                c   = c,
                bx  = bx,
                sbx = sbx
            }

            -- Wake coroutine with context
            local ok, result = coroutine.resume(co, ctx)
            if not ok then
                -- Error in handler - propagate
                error(result, 2)
            end

            -- Advance back to yield point (ready for next dispatch)
            -- Coroutine yields true after fn() completes
        end

        -- ── Cleanup function ────────────────────────────────────────────
        local function _cleanup()
            for op, co in pairs(_pool) do
                if coroutine.status(co) == "suspended" then
                    -- Send nil to signal shutdown
                    coroutine.resume(co, nil)
                end
                _pool[op] = nil
            end
        end

        return _dispatch, _cleanup
    end
end
