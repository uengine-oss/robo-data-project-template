# 계약 — 증강된 메타데이터의 그래프 속성

**쓰는 쪽**: 메타데이터 증강(robo-data-analyzer) · **읽는 쪽**: ontology-studio 테이블 선택,
domain-layer 노드 매핑

헌법 원칙 III 이 경고하는 divergence 가 **새로 생길 수 있는 지점**이다. 쓰는 쪽과 읽는 쪽이
같은 속성명을 봐야 한다.

---

## 노드 속성

| 노드 | 속성 | 타입 | 필수 | 뜻 |
|---|---|---|---|---|
| `:Table` | `description` | string | | 업무 의미 설명 |
| `:Table` | `description_source` | string | 설명이 있으면 ✅ | 근거 |
| `:Column` | `description` | string | | 업무 의미 설명 |
| `:Column` | `description_source` | string | 설명이 있으면 ✅ | 근거 |
| `:Column` | `value_shape` | string(JSON) | | 값 **형태** 요약 |

**`description` 은 기존 속성이다.** 새로 만들지 않는다 — `schema_ontology.read_catalog` 가 이미
읽고 있고(`coalesce(c.description, '')`), data-fabric HTTP 경로는 `description or comment` 로
흡수한다. 증강은 **같은 자리를 채운다.**

### `description_source` — **기존 열거형이다. 자유 텍스트를 넣지 않는다**

허용값은 넷뿐이다. 프론트엔드 계약 검증이 그 밖의 값을 **거부**한다.

| 값 | 화면 표기 |
|---|---|
| `ddl` | DDL 정의 |
| `code` / `procedure` | **코드 분석** |
| `user` | 사용자 입력 |

↳ `robo-data-frontend/src/domains/catalog/api/schemaContracts.ts:150`

> **여기서 한 번 틀렸다 (2026-08-05).** 이 문서 초안이 `procedure:PRC_X#L42-58` 처럼
> *접두사 + 상세* 형식을 설계했는데, 실제 시스템은 그것을 받지 않는다. 그대로 넣자
> `Catalog schema tables[0].description_source가 지원하는 설명 출처가 아닙니다` 로
> **테이블 목록 전체가 실패**했다. 62건을 정정해야 했다.
>
> 교훈은 형식이 아니라 순서다 — **계약을 설계하기 전에 소비자를 먼저 확인한다.** 이 그래프에는
> 이미 규약이 있었고, 새로 만든 것은 divergence 였다(헌법 원칙 III).

### 근거는 별도 필드에 둔다

| 속성 | 내용 |
|---|---|
| `description_evidence` | `PRC_CALC_DAILY_PRODUCTION.sql 머리말 — '일별 공정 지표 테이블(TB09)'` |

FR-013(근거 남기기)·FR-014(근거 없으면 채우지 않기)는 **이 필드**로 검증한다.
`description` 이 있는데 `description_evidence` 가 없으면 "근거 없이 추측했다"는 뜻이다.

### `value_shape` 형식

```json
{
  "kind": "categorical",
  "cardinality": "low",
  "null_ratio": "none",
  "pattern": "AAAA-999",
  "sampled_rows": 500
}
```

| 필드 | 값 |
|---|---|
| `kind` | `date` / `code` / `categorical` / `numeric` / `text` / `boolean` |
| `cardinality` | `unique` / `low` / `medium` / `high` |
| `null_ratio` | `none` / `some` / `mostly` |
| `pattern` | 코드꼴일 때만. `A`=영문, `9`=숫자 |
| `sampled_rows` | 표본 크기 |

> **값 자체를 넣지 않는다.** 헌법 원칙 V — 그래프에 업무 데이터를 눕히지 않는다. 003 FR-006 의
> "샘플 값 형태 일치" 신호는 **형태만으로 성립한다.**

등급을 쓰고 원시 수치를 쓰지 않는 이유: 원시 수치는 표본 크기에 따라 흔들려 **결정성을 해친다**
(research R2). 등급은 경계 근처가 아니면 안정적이다.

---

## 관계 — **기존 형태로 쓰고, 추론임은 속성으로 구별한다**

| 관계 | 방향 | 속성 |
|---|---|---|
| `FK_TO_TABLE` | `:Table` → `:Table` | `sourceColumn`, `targetColumn`, **`source='procedure'`**, `inferred=true`, `evidence`, `confidence` |

`source` 가 화면의 출처 분류를 정한다 — `'code'` / `'procedure'` 면 **「코드 분석」(점선·하늘색)**
으로 그려진다.
↳ `robo-data-frontend/src/workflows/schema-modeling/model/relationshipEdgeProjection.ts:225-228`

> **여기서도 틀렸다 (2026-08-05).** 초안은 `(:Column)-[:INFERRED_REFERENCES]->(:Column)` 이라는
> **새 타입**을 만들었다. 결과는 둘 다 실패였다.
>
> 1. 카탈로그 API 는 `(:Table)-[r]->(:Table)` 을 읽고 타입 화이트리스트가
>    `FK_TO_TABLE` 외 4종뿐이다 — **레벨도 타입도 안 맞아 화면에 하나도 안 나왔다.**
>    ↳ `robo-data-catalog/service/schema_manage_service.py:350-362`
> 2. `r.source` 를 넣지 않아 출처 분류도 되지 않았다.
>
> "추론과 단언을 섞지 않는다"(FR-012)는 여전히 옳지만, **별도 타입은 그 값을 아무도 읽지
> 않는다.** 기록되지 않은 구별은 구별이 아니다. 속성으로 구별하면 기존 소비자가 그대로 읽고
> 구별도 유지된다.

### 읽는 쪽 규칙

- 단언만 필요하면 `WHERE coalesce(r.inferred, false) = false` 로 거른다.
- 온톨로지 관계로 승격할 때 `inferred=true` 유래는 **가설 표시**를 유지한다 — 헌법이 통계 유래
  관계를 `INFLUENCES_*` 로 분리한 것과 같은 취지다.
- 컬럼 수준의 정밀한 기록이 필요하면 `(:Column)-[:INFERRED_REFERENCES]->(:Column)` 을 함께
  둘 수 있다. 다만 그것은 **보조 기록이지 표시 경로가 아니다.**

---

## 재실행 규칙 (FR-015)

증강을 다시 실행해도 **이전 결과가 훼손되지 않아야** 한다.

- 같은 근거에서 나온 설명은 **덮어쓴다** (갱신).
- 근거가 사라진 항목은 **지우지 않고** 그대로 둔다. 이번 실행이 그 프로시저를 안 봤을 수도 있다.
- 사람이 손으로 넣은 설명은 **덮어쓰지 않는다** — `description_source` 가 `manual:` 이면 건너뛴다.

> 마지막 규칙이 없으면 사용자가 고쳐 놓은 설명이 다음 증강에서 조용히 사라진다.

---

## 계약 검사

`scripts/inspect_catalog.py` 에 항목을 추가한다:

1. `description` 이 있는데 `description_source` 가 없는 노드 수 → **0이어야 한다**
2. `value_shape` 가 JSON 으로 파싱되는가
3. `INFERRED_REFERENCES` 가 카탈로그 FK 와 섞이지 않았는가

**검사를 헌법 검사 스크립트에 넣는 이유**: 이 계약은 두 저장소(분석기·studio)가 함께 지킨다.
어느 한쪽만 고치면 조용히 어긋나고, 증상은 "증강했는데 테이블을 못 찾는다"로 나타나 원인을
찾기 어렵다.
