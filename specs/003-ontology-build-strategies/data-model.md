# Phase 1 Data Model: 입력 조합별 온톨로지 구축 전략

저장소는 **ontology-studio 의 SQLite** 다. 공유 Neo4j 에는 아무것도 새로 쓰지 않는다 —
카탈로그는 읽기 전용이고, 새 속성을 쓰면 새 writer 와 새 divergence 가 생긴다
(constitution 원칙 III, [research.md R7](./research.md)).

## 기존 표 (변경 없음)

| 표 | 역할 |
|---|---|
| `ontology_schemas` | 스키마 그룹. `intent`, `golden_questions` 보유 |
| `schema_classes` | 클래스. `properties` JSON, `binding_kind`(`materialized`\|`virtual`) |
| `schema_relationships` | 관계. PK `(schema_id, name, from_class, to_class)`, `properties` JSON |
| `class_datasource_bindings` | 가상 클래스 바인딩. `column_map`, `key_columns`, `base_conditions`, `extra_tables` |
| `class_behaviors` | 파라미터화된 조회 |

전략 1·2 는 **이 표들에 그대로 쓴다.** 새 클래스 표를 만들지 않는다 — 세 전략의 산출물이
동일해야 001 의 조회·안전성 요구사항이 자동으로 적용된다(spec 관계 절).

## 신규 표 1 — `element_provenance` (FR-029)

모든 클래스·속성·관계가 **어느 전략, 어느 근거**에서 왔는지.

| 컬럼 | 타입 | 설명 |
|---|---|---|
| `schema_id` | TEXT | FK → `ontology_schemas(id)` ON DELETE CASCADE |
| `element_kind` | TEXT | `class` \| `property` \| `relationship` |
| `element_key` | TEXT | `class` → 클래스명 · `property` → `클래스명.속성명` · `relationship` → `관계명:from:to` |
| `strategy` | TEXT | `doc_reverse_bind` \| `causal_discovery` \| `catalog_schema` \| `manual` |
| `evidence_kind` | TEXT | `document` \| `foreign_key` \| `statistical` \| `human` |
| `evidence_ref` | TEXT | 근거 위치. 문서면 `document_id#chunk_ref@page`, FK 면 `from.col→to.col`, 통계면 `method/lag/p_adj` |
| `created_at` | REAL | |

**PK** `(schema_id, element_kind, element_key)` — 요소당 출처 하나. 순차 전략 적용 시 나중
전략이 같은 요소를 다시 만들면 덮어쓰지 않고 **먼저 만든 출처를 유지**한다(FR-004: 중복 생성
금지, SC-011).

## 신규 표 2 — `causal_hypotheses` (FR-021, FR-023)

통계로 발견된 엣지와 **사람의 결정**. 관계로 승격되기 전 단계.

| 컬럼 | 타입 | 설명 |
|---|---|---|
| `schema_id` | TEXT | FK → `ontology_schemas(id)` ON DELETE CASCADE |
| `source_class` / `source_field` | TEXT | 원인 변수 |
| `target_class` / `target_field` | TEXT | 결과 변수 |
| `lag` | INTEGER | 시차. **PK 의 일부** |
| `method` | TEXT | `granger` \| `correlation` \| `decomposition` |
| `strength` | REAL | 0~1 |
| `p_value` | REAL | 원시 |
| `p_value_adjusted` | REAL | BH 보정 후 |
| `tests_performed` | INTEGER | 이 실행에서 수행한 총 검정 수 |
| `correction` | TEXT | `benjamini-hochberg` |
| `direction` | TEXT | `positive` \| `negative` |
| `truncated` | INTEGER | 표본이 행 상한에 걸렸는가 (FR-025) |
| `decision` | TEXT | `pending` \| `approved` \| `rejected` \| `reversed` |
| `decided_at` | REAL | NULL 이면 미결 |
| `created_at` / `updated_at` | REAL | |

**PK** `(schema_id, source_class, source_field, target_class, target_field, lag)`

`lag` 가 키에 든 이유: 같은 변수 쌍이 서로 다른 시차에서 각각 유의할 수 있고 그것들은 **다른
가설**이다.

### 상태 전이

```
                   (발견 실행)
                        │
                        ▼
                    pending ──── 사람 승인 ────▶ approved ──▶ 관계로 승격
                        │                                      (INFLUENCES_*)
                        ├──── 사람 거부 ──────▶ rejected  ──▶ 승격 안 함
                        │
                        └──── 방향 반전 ──────▶ reversed  ──▶ source↔target 바꿔 승격
```

**재실행 규칙 (FR-022 + SC-009 의 충돌 해소)**: 재실행은 통계 수치
(`strength`·`p_value`·`p_value_adjusted`·`tests_performed`·`truncated`)를 **갱신**하고
`decision`·`decided_at` 은 **절대 덮지 않는다.** 같은 데이터면 같은 엣지가 다시 나오는 것이
정상(FR-022)이므로, 사람의 판정을 보존하는 것만이 "거부한 엣지가 되살아나지 않는다"(SC-009)를
성립시킨다.

`pending` 은 관계로 승격되지 않는다 — 발견과 적용을 분리한 결과이고 FR-030(쓰기 전 계획만)과
같은 성질이다.

## 인메모리 구조 (저장하지 않음)

### 전략 추천 — `StrategyRecommendation`

```
inputs:        {has_documents, has_datasource, has_intent, timeseries_ready}
recommended:   'doc_reverse_bind' | 'causal_discovery' | 'catalog_schema' | 'document_only'
reason:        문자열
unavailable:   [{strategy, reason}]
```

순수 함수의 반환값. `timeseries_ready` 는 호출자가 전제 검사(R5)로 미리 계산해 넘긴다.

### 역검색 후보 — `BindingCandidate`

```
entity:      클래스명
table:       테이블명
datasource:  데이터소스명            ← host/port/user/password 금지 (원칙 V)
source_schema: 스키마명
score:       0~1 (column 0.6 + type 0.2 + name 0.2)
verdict:     'auto' | 'needs_review' | 'no_match' | 'conflict'
evidence:
  matched_columns:    [{property, column, type_match: bool}]
  unmatched_properties: [속성명]
  name_tokens_shared: [토큰]
  column_coverage:    0~1
  column_precision:   0~1
```

`evidence` 가 없으면 사람이 검토할 수 없다(FR-008). 점수만 반환하는 것은 금지.

### 인과 분석 요청/응답 — [contracts/domain-layer-analyze-matrix.md](./contracts/domain-layer-analyze-matrix.md)

## 검증 규칙

| 규칙 | 근거 |
|---|---|
| `element_provenance.strategy` / `evidence_kind` 는 열거값만 | FR-029 |
| `causal_hypotheses.decision` 은 열거값만, 기본 `pending` | FR-023 |
| `p_value_adjusted >= p_value` (BH 는 단조 증가) | R4 |
| `lag >= 0` | |
| 승격되는 관계명은 `INFLUENCES_` 접두사 · UPPER_SNAKE | FR-021, R9 |
| FK 유래 관계명은 `REFERENCES_` 접두사 (002 그대로) | 002 FR-001 |
| 바인딩 응답에 `host`/`port`/`user`/`password` 부재 | 원칙 V |
| 마이그레이션은 `CREATE TABLE IF NOT EXISTS` + `try SELECT / except ALTER` | R7, session_store 기존 패턴 |
