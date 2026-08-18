# Natural Language Music Editing Acceptance Benchmark V1

- **Date**: 2026-08-18T07:39:36.006640+00:00
- **Provider**: synthetic / deterministic (ground truth)
- **Total cases**: 22

## Summary

| Status | Count |
|--------|-------|
| PASS | 13 |
| NEEDS_CLARIFICATION | 3 |
| UNSUPPORTED | 2 |
| INVALID_TARGET | 4 |

**Overall pass rate**: 13/22 (59.1%)

## Results by Category

| Category | PASS | NEEDS_CLARIFICATION | UNSUPPORTED | INVALID_TARGET | FAIL |
|----------|------|---------------------|-------------|----------------|------|
| ambiguity | 0 | 3 | 0 | 0 | 0 |
| hallucination | 0 | 0 | 0 | 3 | 0 |
| instrument_transposition | 2 | 0 | 0 | 1 | 0 |
| key_target | 0 | 0 | 2 | 0 | 0 |
| measure_range | 3 | 0 | 0 | 0 | 0 |
| part_measure_range | 2 | 0 | 0 | 0 | 0 |
| part_specific | 3 | 0 | 0 | 0 | 0 |
| whole_score_interval | 3 | 0 | 0 | 0 | 0 |

## Failure Stage Distribution

| Stage | Count |
|-------|-------|
| resolver | 9 |

## Detailed Results

| Case | Category | Input | Expected | Actual | Resolver | Target Part | Measures | Interval/Basis | Export | Reimport | Latency (ms) | Failure Stage | Error |
|------|----------|-------|----------|--------|----------|-------------|----------|----------------|--------|----------|--------------|---------------|-------|
| WS-01 | whole_score_interval | 把整首升大二度 | PASS | PASS | ready | P1, P2, P3, P4 | 1-50 | +M2 | ✅ | ✅ | 74.8 |  |  |
| WS-02 | whole_score_interval | 整首降小三度 | PASS | PASS | ready | P1, P2, P3, P4 | 1-50 | -m3 | ✅ | ✅ | 85.1 |  |  |
| WS-03 | whole_score_interval | 全曲升高一个八度 | PASS | PASS | ready | P1, P2, P3, P4 | 1-50 | +P8 | ✅ | ✅ | 74.4 |  |  |
| PS-01 | part_specific | 把长号升高一个八度 | PASS | PASS | ready | P3 | 1-50 | +P8 | ✅ | ✅ | 73.1 |  |  |
| PS-02 | part_specific | 把第一小号升大二度 | PASS | PASS | ready | P1 | 1-50 | +M2 | ✅ | ✅ | 74.1 |  |  |
| PS-03 | part_specific | 把第二小号降半音 | PASS | PASS | ready | P2 | 1-50 | -m2 | ✅ | ✅ | 73.5 |  |  |
| MR-01 | measure_range | 把第12到24小节升大二度 | PASS | PASS | ready | P1, P2, P3, P4 | 12-24 | +M2 | ✅ | ✅ | 78.8 |  |  |
| MR-02 | measure_range | 第32小节到最后降一个全音 | PASS | PASS | ready | P1, P2, P3, P4 | 32-50 | -M2 | ✅ | ✅ | 78.6 |  |  |
| MR-03 | measure_range | 前8小节升半音 | PASS | PASS | ready | P1, P2, P3, P4 | 1-8 | +m2 | ✅ | ✅ | 75.5 |  |  |
| PM-01 | part_measure_range | 把长号第12到24小节升大二度 | PASS | PASS | ready | P3 | 12-24 | +M2 | ✅ | ✅ | 72.2 |  |  |
| PM-02 | part_measure_range | 第二小号第5到10小节降半音 | PASS | PASS | ready | P2 | 5-10 | -m2 | ✅ | ✅ | 86.4 |  |  |
| IT-01 | instrument_transposition | 把Bb小号改成实际音高 | PASS | PASS | ready | P1 | 1-50 | written_to_sounding | ✅ | ✅ | 59.0 |  |  |
| IT-02 | instrument_transposition | 把实际音高改成Bb小号记谱 | PASS | PASS | ready | P1 | 1-50 | sounding_to_written | ✅ | ✅ | 66.6 |  |  |
| IT-03 | instrument_transposition | 把F圆号改成实际音高 | INVALID_TARGET | INVALID_TARGET | invalid |  |  |  | ❌ | ❌ | 0.3 | resolver | Could not find a part matching '圆号'. |
| KY-01 | key_target | 把整首移到降E大调 | UNSUPPORTED | UNSUPPORTED | unsupported |  |  |  | ❌ | ❌ | 0.0 | resolver | Target-key transposition is not supported in V1. |
| KY-02 | key_target | 把这段移成D大调 | UNSUPPORTED | UNSUPPORTED | unsupported |  |  |  | ❌ | ❌ | 0.0 | resolver | Target-key transposition is not supported in V1. |
| AM-01 | ambiguity | 后面一点降一点 | NEEDS_CLARIFICATION | NEEDS_CLARIFICATION | needs_clarification |  |  |  | ❌ | ❌ | 0.0 | resolver | 请说明具体音程。 |
| AM-02 | ambiguity | 把小号调高一点 | NEEDS_CLARIFICATION | NEEDS_CLARIFICATION | needs_clarification |  |  |  | ❌ | ❌ | 0.0 | resolver | Which trumpet? |
| AM-03 | ambiguity | 第二段降一点 | NEEDS_CLARIFICATION | NEEDS_CLARIFICATION | needs_clarification |  |  |  | ❌ | ❌ | 0.0 | resolver | 请说明具体音程与小节范围。 |
| HL-01 | hallucination | 把不存在的圆号升八度 | INVALID_TARGET | INVALID_TARGET | invalid |  |  |  | ❌ | ❌ | 0.1 | resolver | Could not find a part matching '圆号'. |
| HL-02 | hallucination | 把第999小节升大二度 | INVALID_TARGET | INVALID_TARGET | invalid |  |  |  | ❌ | ❌ | 0.1 | resolver | Invalid measure range: measure_not_found:999 |
| HL-03 | hallucination | 把第三小号第10小节升半音 | INVALID_TARGET | INVALID_TARGET | needs_clarification |  |  |  | ❌ | ❌ | 0.1 | resolver | '第三小号' matches multiple parts: P1 Trumpet 1, P2 Trumpet 2. Please specify which one. |

## Classification Notes

- **PASS**: pipeline produced `ready` and engine/export/reimport/semantic checks succeeded.
- **NEEDS_CLARIFICATION**: resolver returned `needs_clarification` for ambiguous input.
- **UNSUPPORTED**: model or system correctly reported unsupported operation (e.g., target-key transposition).
- **INVALID_TARGET**: resolver refused a non-existent part or measure.
- **FAIL**: actual outcome did not match expected outcome.
- **PROVIDER_ERROR**: reserved for real-provider HTTP/JSON failures (not present in synthetic run).
