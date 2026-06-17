# Phase 6 — Production Readiness, Scale Testing & Documentation

Final phase: integration tests, load/stress tooling, performance benchmarks, and project documentation.

## Testing

| Asset | Purpose |
|-------|---------|
| `tests/test_integration.py` | HTTP integration tests (auth, chat, streaming, metrics, recovery) |
| `tests/conftest.py` | Shared fixtures with dependency overrides |
| `locustfile.py` | Locust UI + distributed load testing |
| `scripts/load_test_phase6.py` | 5000+ async concurrent requests |
| `scripts/stream_stress_phase6.py` | Concurrent SSE streaming stress |
| `scripts/fault_injection_phase6.py` | Provider failure + recovery validation |
| `scripts/chaos_test_phase4.py` | Circuit breaker / failover smoke test |

### Run integration tests

```bash
pytest tests/test_integration.py -q
```

### Run load tests (gateway must be running)

```bash
export GATEWAY_API_KEY=<seeded-key>

# 5000 requests, 200 concurrent
python scripts/load_test_phase6.py --requests 5000 --concurrency 200

# Streaming stress (200 concurrent streams)
python scripts/stream_stress_phase6.py --streams 200 --concurrency 50

# Locust (web UI on :8089)
pip install -r requirements-dev.txt
locust -f locustfile.py --host http://localhost:8000
```

### Fault injection

```bash
python scripts/fault_injection_phase6.py
python scripts/chaos_test_phase4.py
```

## Performance

```bash
# Latency benchmark (p50/p95/p99)
python scripts/benchmark_phase6.py --requests 500 --concurrency 50
python scripts/benchmark_phase6.py --requests 200 --concurrency 25 --stream

# CPU + memory profiling
python scripts/profile_phase6.py --requests 200 --cpu --memory
```

### Reference results (local, mock provider)

On a typical dev machine with mock provider and local Postgres/Redis:

| Scenario | Throughput | p95 latency |
|----------|------------|-------------|
| 500 req / 50 concurrent | ~150–400 req/s | < 100 ms |
| 5000 req / 200 concurrent | ~200–600 req/s | < 250 ms |
| 200 concurrent streams | ~50–150 streams/s | < 500 ms |

Actual numbers depend on hardware, Docker overhead, and DB/Redis latency.

## Repository deliverables

| Document | Location |
|----------|----------|
| Architecture overview | [docs/architecture.md](architecture.md) |
| API reference | [docs/api.md](api.md) |
| Portfolio case study | [docs/case-study.md](case-study.md) |
| ADRs | [docs/adr/](adr/) |
| Example configs | [config/examples/](../config/examples/) |
| Example alerts | [observability/examples/](../observability/examples/) |
| Demo script | [scripts/demo.sh](../scripts/demo.sh) |

## Demo

```bash
chmod +x scripts/demo.sh
export GATEWAY_API_KEY=<seeded-key>
./scripts/demo.sh
```

## Design decisions

- **Locust + asyncio scripts** — Locust for interactive/distributed load; asyncio script for reproducible CI-friendly 5000+ concurrency without JVM.
- **Integration tests with dependency overrides** — fast, portable tests without requiring a live DB for every HTTP assertion.
- **Mock provider for scale tests** — isolates gateway performance from external LLM latency and cost.
- **Separate benchmark vs load test** — benchmark reports percentiles; load test reports saturation behavior (429/402).

## Tests

```bash
pytest -q
```

All tests including integration should pass before considering Phase 6 complete.
