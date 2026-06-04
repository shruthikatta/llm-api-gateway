from __future__ import annotations

BUDGET_CHECK_SCRIPT = """
local key = KEYS[1]
local limit = tonumber(ARGV[1])
local amount = tonumber(ARGV[2])
local ttl = tonumber(ARGV[3])

local current = tonumber(redis.call('GET', key) or '0')
if amount > 0 and current + amount > limit then
    return {0, current}
end

local updated = redis.call('INCRBYFLOAT', key, amount)
redis.call('EXPIRE', key, ttl)
return {1, updated}
"""


def check_and_increment(
    cache,
    *,
    key: str,
    limit: float,
    amount: float,
    ttl_seconds: int,
) -> tuple[bool, float]:
    result = cache.eval_script(
        BUDGET_CHECK_SCRIPT,
        [key],
        [str(limit), str(amount), str(ttl_seconds)],
    )
    if not isinstance(result, (list, tuple)) or len(result) < 2:
        raise RuntimeError("Unexpected budget check response from cache.")
    allowed = int(result[0]) == 1
    current = float(result[1])
    return allowed, current
