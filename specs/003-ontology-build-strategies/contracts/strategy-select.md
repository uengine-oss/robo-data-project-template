# Contract: 전략 추천 (FR-001 ~ FR-004)

**Owner**: ontology-studio · `modules/ontology/build_strategy.py`

## 순수 함수

```
recommend(has_documents, has_datasource, has_intent, timeseries_ready) -> StrategyRecommendation
```

I/O 가 없다. `timeseries_ready` 는 호출자가 전제 검사로 미리 계산해 넘긴다
([research.md R10](../research.md)) — 그래서 서비스 기동 없이 단위 테스트된다.

### 결정 표 (FR-001 — 같은 입력 → 항상 같은 추천)

| 문서 | 데이터소스 | 인텐트 | 시계열 | 추천 | 사유 |
|:---:|:---:|:---:|:---:|---|---|
| ✓ | ✓ | – / ✓ | – / ✓ | `doc_reverse_bind` | 문서가 도메인을, 데이터소스가 값을 갖는다 |
| – | ✓ | ✓ | ✓ | `causal_discovery` | 문서가 없다. 인텐트가 타겟을, 데이터가 구조를 준다 |
| – | ✓ | ✓ | – | `catalog_schema` | 인과 발견의 시계열 전제가 미충족 |
| – | ✓ | – | – / ✓ | `catalog_schema` | 목적도 문서도 없다. 카탈로그가 아는 것만 |
| ✓ | – | – / ✓ | – / ✓ | `document_only` | 바인딩할 데이터소스가 없다 (기존 경로) |
| – | – | – / ✓ | – / ✓ | `none` | 입력이 없다 |

### `unavailable` 사유 (FR-002, FR-003)

전제 미충족 전략은 **고를 수 없게** 하고 사유를 남긴다 — 고를 수 있게 두고 나중에
실패시키지 않는다.

| 전략 | 비활성 사유 |
|---|---|
| `doc_reverse_bind` | `"문서가 없습니다"` / `"데이터소스가 없습니다"` |
| `causal_discovery` | `"인텐트가 없습니다"` / `"시간축 컬럼이 없습니다"` / `"수치 변수가 2개 미만입니다"` / `"행이 N개로 최소 M개에 미달합니다"` / `"통계 서비스에 연결할 수 없습니다"` |
| `catalog_schema` | `"데이터소스가 없습니다"` / `"메타데이터가 추출되지 않았습니다"` |

마지막 사유(`통계 서비스에 연결할 수 없습니다`)를 데이터 부적합과 **구분**하는 이유:
사용자가 할 조치가 다르다 — 하나는 서비스 기동, 하나는 데이터 확보.

### 반환값

```json
{
  "inputs": {"has_documents": true, "has_datasource": true, "has_intent": false, "timeseries_ready": false},
  "recommended": "doc_reverse_bind",
  "reason": "문서와 데이터소스가 함께 있습니다. 문서가 정의한 엔티티에 데이터소스를 역으로 찾아 바인딩합니다.",
  "available": ["doc_reverse_bind", "catalog_schema"],
  "unavailable": [
    {"strategy": "causal_discovery", "reason": "인텐트가 없습니다"}
  ]
}
```

**추천은 강제가 아니다** (FR-003). `available` 에 있는 것은 무엇이든 고를 수 있고, 추천과 달라도
그대로 진행한다.

## HTTP

### `GET /api/build-strategy/recommend`

| 파라미터 | 타입 | 설명 |
|---|---|---|
| `has_documents` | bool | |
| `datasource` | str | 빈 문자열이면 데이터소스 없음 |
| `schema` | str | 시계열 전제 검사 대상 |
| `intent` | str | 빈 문자열이면 인텐트 없음 |
| `max_lag` | int | 기본 2. 최소 행 수 하한 계산에 쓰인다 |

라우트는 `datasource`/`schema` 가 있으면 카탈로그로 `timeseries_ready` 를 계산한 뒤(R5)
순수 함수를 호출한다. 카탈로그·통계 서비스가 응답하지 않으면 예외를 전파하지 않고
`timeseries_ready = false` + 구분된 사유로 접는다 (001 FR-003 과 같은 저하 패턴).

**응답에 접속 정보를 넣지 않는다** — `{datasource, schema}` 수준까지만 (원칙 V).
