# Contract: `POST /whatif/analyze-matrix` (domain-layer)

**무상태 계산 엔드포인트.** 행렬을 받아 인과/상관 엣지를 돌려준다. `schema_id` 를 받지 않고,
Neo4j 에 **아무것도 쓰지 않으며**, domain-layer 의 스키마 스토어를 읽지 않는다.

왜 기존 `/whatif/discover-edges` 를 쓰지 않는지는 [research.md R1](../research.md) 참조.

**Owner**: domain-layer · **Caller**: ontology-studio `causal_client.py`

## Request

```json
{
  "columns": [
    {"name": "month",       "role": "time"},
    {"name": "yield_rate",  "role": "measure", "class": "MfgDailyEquipment", "field": "yield_rate"},
    {"name": "vibration",   "role": "measure", "class": "MfgSensor",         "field": "vibration"}
  ],
  "rows": [
    {"month": "2026-01", "yield_rate": 97.2, "vibration": 0.31},
    {"month": "2026-02", "yield_rate": 96.1, "vibration": 0.44}
  ],
  "max_lag": 2,
  "significance_level": 0.05,
  "fdr_q": 0.05,
  "min_correlation": 0.3,
  "target": "MfgDailyEquipment.yield_rate",
  "relation_hints": {"MfgSensor.vibration→MfgDailyEquipment.yield_rate": "dynamic"},
  "truncated": false
}
```

| 필드 | 필수 | 설명 |
|---|:---:|---|
| `columns` | ✓ | `role` ∈ `time`\|`measure`. `time` 은 0 또는 1개. `measure` 는 `class`·`field` 필수 |
| `rows` | ✓ | `columns[].name` 을 키로 하는 객체 배열. 결측은 `null` |
| `max_lag` | | 기본 2. 최소 행 수 하한 `max_lag×2+10` 을 결정 |
| `significance_level` | | 기본 0.05 |
| `fdr_q` | | 기본 0.05. Benjamini–Hochberg 문턱 (R4) |
| `target` | | 있으면 그 변수를 향하는 엣지만. 없으면 모든 쌍 |
| `relation_hints` | | `"src→dst": "dynamic"\|"deterministic"`. `deterministic` 은 Granger 대신 분해형으로 (FR-018) |
| `truncated` | | 호출자가 행 상한에 걸렸음을 알림. 응답에 그대로 되돌려 실린다 (FR-025) |

## Response 200 — 전제 충족

```json
{
  "ok": true,
  "rows_analyzed": 48,
  "variables": 2,
  "tests_performed": 1,
  "correction": "benjamini-hochberg",
  "fdr_q": 0.05,
  "truncated": false,
  "methods_used": ["granger"],
  "var_fit": "ok",
  "edges": [
    {
      "source_class": "MfgSensor",   "source_field": "vibration",
      "target_class": "MfgDailyEquipment", "target_field": "yield_rate",
      "method": "granger",
      "strength": 0.62,
      "p_value": 0.0031,
      "p_value_adjusted": 0.0031,
      "significant": true,
      "tested": true,
      "basis": "fdr",
      "lag": 3,
      "direction": "negative"
    }
  ]
}
```

| 필드 | 설명 |
|---|---|
| `tests_performed` | 실제 수행한 **가설검정** 수 (`tested: true` 엣지 수). 보정의 근거이므로 반드시 노출한다 (FR-020) |
| `correction` | 항상 `benjamini-hochberg` |
| `methods_used` | 실제로 반환된 방법 목록 |
| `var_fit` | `ok` \| `derived_routed_to_decomposition` \| `derived_correlation_only` \| `no_edges`. **파생 라벨이다** — 기존 엔진이 VAR 피팅 성공 여부를 노출하지 않으므로 반환된 방법 구성에서 **추론**한 값이고, 이름에 `derived_` 를 붙여 그 사실을 드러낸다 |
| `edges[].method` | `granger` \| `correlation` \| `decomposition` |
| `edges[].tested` | 실제 가설검정을 거쳤는가. `granger`·`correlation` 만 `true` |
| `edges[].p_value_adjusted` | BH 보정. `>= p_value` 보장. `tested: false` 면 원시값 그대로 (보정할 p-value 가 없다) |
| `edges[].significant` | 호출자는 **이 플래그만** 보고 승격 여부를 정한다 |
| `edges[].basis` | `significant` 의 산출 근거 — `fdr` \| `hinted_decomposition` \| `decomposition_unhinted` |

### `basis` 가 필요한 이유 (실측으로 발견한 함정)

기존 엔진은 `if not edges and try_var:` 로 **아무것도 찾지 못했을 때** 기여도 분해로
폴백한다 (`causal_analysis.py:433`). 그런데 "찾지 못했다" 는 무관한 변수들의 **정상적인**
결과다. 실측: 서로 독립인 난수 5개를 섞어 넣으면 granger·correlation 엣지는 0개이고
**decomposition 엣지가 20개** 나온다.

분해형에는 보정할 p-value 가 없으므로(엔진이 `p_value=0.0` 을 자리표시자로 넣는다) 기여도
강도를 유의성으로 쓰면 **잡음이 온톨로지 관계로 승격된다.** 그래서:

- `relation_hints` 로 **명시적으로 `deterministic` 이라고 선언한 쌍**만 강도로 판정한다
  (`basis: hinted_decomposition`).
- 그 외 분해형 엣지는 검토용으로 반환하되 `significant: false`
  (`basis: decomposition_unhinted`). 사람이 승인할 수는 있지만 자동 승격되지 않는다.

기존 통계 코드는 **수정하지 않는다** (다른 호출자가 의존한다). 이 판정은 어댑터에 있다.

`edges` 는 `strength` 내림차순, 동점은 `(source_class, source_field, target_class, target_field, lag)`
사전순 — **결정적 정렬** (FR-022).

## Response 200 — 전제 미충족 (오류가 아니다)

```json
{
  "ok": false,
  "reason": "insufficient_rows",
  "detail": "행이 12개입니다. max_lag=2 에서는 최소 14개가 필요합니다.",
  "required_rows": 14,
  "actual_rows": 12,
  "edges": [],
  "tests_performed": 0
}
```

| `reason` | 조건 |
|---|---|
| `no_time_column` | `columns` 에 `role: "time"` 이 없다 |
| `insufficient_variables` | `measure` 가 2개 미만 |
| `insufficient_rows` | 유효 행 < `max_lag×2+10` |

**`edges` 는 항상 `[]`** 다 — FR-017·SC-005 가 요구하는 "엣지를 하나도 만들지 않는다".
HTTP 200 을 쓰는 이유는 이것이 오류가 아니라 **정상적인 판정 결과**이기 때문이다. 호출자는
이 응답을 사용자에게 사유로 그대로 보여준다.

## Response 4xx / 5xx

| 코드 | 조건 |
|---|---|
| 422 | `columns`/`rows` 스키마 위반, `columns[].name` 이 `rows` 키와 불일치 |
| 500 | 통계 엔진의 예상 못한 예외. `var_fit` 실패는 500 이 **아니다** — 위 분류 신호로 처리 |

## 불변식

1. **Neo4j 쓰기 0회.** 이 경로는 순수 계산이다.
2. **domain-layer 스키마 스토어 읽기 0회.** `schema_id` 를 받지 않으므로 installation.md
   이슈 #14(메모리 온톨로지 유실)의 영향을 받지 않는다.
3. **LLM 호출 0회.** FR-022 의 재현성 근거.
4. 같은 요청 → 같은 응답. `rows` 순서가 같으면 엣지 집합과 순서까지 같다.
5. 기존 `causal_analysis.py` · `correlation_engine.py` 를 **수정하지 않는다.** 어댑터만 얹는다.
