from __future__ import annotations

from dataclasses import dataclass

TOKEN_BUCKET_SCRIPT = """
local key = KEYS[1]
local capacity = tonumber(ARGV[1])
local refill_rate = tonumber(ARGV[2])
local now = tonumber(ARGV[3])
local requested = tonumber(ARGV[4])

local data = redis.call('HMGET', key, 'tokens', 'last_refill')
local tokens = tonumber(data[1])
local last_refill = tonumber(data[2])

if tokens == nil then
    tokens = capacity
    last_refill = now
end

local elapsed = math.max(0, now - last_refill)
tokens = math.min(capacity, tokens + elapsed * refill_rate)

if tokens < requested then
    local deficit = requested - tokens
    local retry_after = 1
    if refill_rate > 0 then
        retry_after = math.ceil(deficit / refill_rate)
    end
    redis.call('HMSET', key, 'tokens', tokens, 'last_refill', now)
    redis.call('EXPIRE', key, math.max(60, math.ceil(capacity / refill_rate) * 2))
    return {0, retry_after, tokens}
end

if requested < 0 then
    tokens = math.min(capacity, tokens - requested)
else
    tokens = tokens - requested
end
redis.call('HMSET', key, 'tokens', tokens, 'last_refill', now)
redis.call('EXPIRE', key, math.max(60, math.ceil(capacity / refill_rate) * 2))
return {1, 0, tokens}
"""

PRIORITY_REFILL_MULTIPLIER = {
    "low": 0.5,
    "normal": 1.0,
    "high": 2.0,
}

PRIORITY_CAPACITY_MULTIPLIER = {
    "low": 0.5,
    "normal": 1.0,
    "high": 2.0,
}


@dataclass(slots=True, frozen=True)
class RateLimitDecision:
    allowed: bool
    retry_after_seconds: int = 0
    remaining: float = 0.0
    limit_type: str = "requests"


def consume_tokens(
    cache,
    *,
    key: str,
    capacity: float,
    refill_per_second: float,
    amount: float = 1.0,
) -> RateLimitDecision:
    import time

    now = time.time()
    result = cache.eval_script(
        TOKEN_BUCKET_SCRIPT,
        [key],
        [str(capacity), str(refill_per_second), str(now), str(amount)],
    )
    if not isinstance(result, (list, tuple)) or len(result) < 3:
        raise RuntimeError("Unexpected token bucket response from cache.")

    allowed = int(result[0]) == 1
    retry_after = int(result[1])
    remaining = float(result[2])
    return RateLimitDecision(
        allowed=allowed,
        retry_after_seconds=retry_after,
        remaining=remaining,
    )
