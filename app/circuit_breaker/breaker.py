from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class CircuitState(str, Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass(slots=True, frozen=True)
class CircuitDecision:
    allowed: bool
    state: CircuitState


CIRCUIT_BREAKER_SCRIPT = """
local key = KEYS[1]
local threshold = tonumber(ARGV[1])
local recovery_timeout = tonumber(ARGV[2])
local half_open_max = tonumber(ARGV[3])
local now = tonumber(ARGV[4])
local action = ARGV[5]

local state = redis.call('HGET', key, 'state') or 'closed'
local failures = tonumber(redis.call('HGET', key, 'failures') or '0')
local opened_at = tonumber(redis.call('HGET', key, 'opened_at') or '0')
local half_open_calls = tonumber(redis.call('HGET', key, 'half_open_calls') or '0')

if action == 'check' then
    if state == 'open' then
        if now - opened_at >= recovery_timeout then
            redis.call('HSET', key, 'state', 'half_open', 'half_open_calls', '0')
            state = 'half_open'
        else
            return {0, state}
        end
    end
    if state == 'half_open' then
        if half_open_calls >= half_open_max then
            return {0, state}
        end
        redis.call('HINCRBY', key, 'half_open_calls', 1)
    end
    redis.call('EXPIRE', key, recovery_timeout * 4)
    return {1, state}
end

if action == 'success' then
    redis.call('HSET', key, 'state', 'closed', 'failures', '0', 'half_open_calls', '0')
    redis.call('EXPIRE', key, recovery_timeout * 4)
    return {1, 'closed'}
end

if action == 'failure' then
    failures = failures + 1
    redis.call('HSET', key, 'failures', failures)
    if state == 'half_open' or failures >= threshold then
        redis.call('HSET', key, 'state', 'open', 'opened_at', now, 'failures', '0', 'half_open_calls', '0')
        redis.call('EXPIRE', key, recovery_timeout * 4)
        return {0, 'open'}
    end
    redis.call('EXPIRE', key, recovery_timeout * 4)
    return {1, state}
end

return {0, state}
"""


def run_circuit_action(
    cache,
    *,
    key: str,
    threshold: int,
    recovery_timeout: int,
    half_open_max: int,
    action: str,
) -> CircuitDecision:
    import time

    now = time.time()
    result = cache.eval_script(
        CIRCUIT_BREAKER_SCRIPT,
        [key],
        [
            str(threshold),
            str(recovery_timeout),
            str(half_open_max),
            str(now),
            action,
        ],
    )
    if not isinstance(result, (list, tuple)) or len(result) < 2:
        raise RuntimeError("Unexpected circuit breaker response from cache.")

    allowed = int(result[0]) == 1
    state = CircuitState(str(result[1]))
    return CircuitDecision(allowed=allowed, state=state)
