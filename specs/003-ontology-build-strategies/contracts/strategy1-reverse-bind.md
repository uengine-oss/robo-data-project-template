# Contract: 전략 1 — 문서 엔티티 → 데이터소스 역바인딩 (FR-005 ~ FR-015)

**Owner**: ontology-studio · `entity_matcher.py` (순수 채점) + `doc_ontology.py` (오케스트레이션)

문서 파서는 **새로 만들지 않는다.** 기존 문서 기반 클래스 생성 경로가 만든 클래스를 입력으로
받아 역바인딩만 한다 ([research.md R2](../research.md)).

## 순수 함수 — 채점

```
score_entity(entity, tables) -> list[BindingCandidate]     # 한 엔티티에 대한 후보 순위
match_all(entities, tables)  -> MatchReport                # 충돌 판정 포함 전체
```

`tables` 는 기존 `schema_ontology.read_catalog()` 의 반환값을 그대로 쓴다 — 새 Cypher 를 쓰지
않아 divergence 흡수(원칙 III)와 데이터소스 필터(원칙 II)가 한 곳에 유지된다.

### 점수 (research.md R3)

```
score = 0.6 × column_score + 0.2 × type_score + 0.2 × name_score

column_score = harmonic_mean(coverage, precision)
  coverage  = matched / len(entity.properties)
  precision = matched / len(table.columns)
type_score = (매칭된 컬럼 중 온톨로지 타입 일치) / matched      # matched=0 이면 0
name_score = |shared tokens| / |union tokens|                  # snake/camel 분해, 소문자
```

조화평균을 쓰는 이유: coverage 만 보면 200컬럼 테이블이 모든 엔티티에 매칭된다.
`name_score` 가 0.2 인 이유: FR-006 의 실제 케이스가 엔티티 "설비일일점검" ↔ 테이블
`mfg_daily_equipment` 로 **한글↔영문이라 이름 유사도가 0** 이다. 이름에 큰 비중을 주면 정상
케이스가 탈락한다.

### 판정 (FR-009, FR-012)

| verdict | 조건 | 결과 |
|---|---|---|
| `auto` | 1위 ≥ 0.70 **이고** (1위 − 2위) ≥ 0.15 | 바인딩 적용 대상 |
| `needs_review` | 1위 ≥ 0.40, 위 조건 미달 | **사람 확인 필수** — 자동 바인딩 금지 |
| `no_match` | 1위 < 0.40 | 엔티티는 미바인딩 클래스로 남는다 (FR-010) |
| `conflict` | 한 테이블이 2개 이상 엔티티의 `auto` 급 1위 | 양쪽 모두 `conflict`, 자동 바인딩 금지 |

정렬은 `(-score, table_name)` — 동점에서도 순서가 고정된다.

### `MatchReport`

```json
{
  "matches": [
    {
      "entity": "설비일일점검",
      "verdict": "auto",
      "candidates": [
        {
          "table": "mfg_daily_equipment", "datasource": "itest_pg", "source_schema": "manufacturing",
          "score": 0.82,
          "evidence": {
            "matched_columns": [{"property": "가동시간", "column": "run_hours", "type_match": true}],
            "unmatched_properties": ["점검자"],
            "name_tokens_shared": [],
            "column_coverage": 0.86, "column_precision": 0.75
          }
        }
      ]
    }
  ],
  "unbound_entities": ["작업지시서"],
  "uncovered_tables": [{"datasource": "itest_pg", "schema": "manufacturing", "table": "mfg_scrap"}],
  "conflicts": [{"table": "mfg_product", "entities": ["제품", "품목"]}]
}
```

- `unbound_entities` — FR-010. 데이터가 없다고 엔티티를 지우지 않는다.
- `uncovered_tables` — FR-011. 문서가 덮지 못한 데이터가 다음 작업 목록이다.
- `conflicts` — FR-012.
- **`evidence` 없는 후보를 반환하지 않는다** (FR-008). 점수만 주면 검토가 불가능하다.
- 응답에 `host`/`port`/`user`/`password` **없음** (원칙 V).

## HTTP

### `POST /api/schema/{schema_id}/reverse-bind/preview`

```json
{"datasource": "itest_pg", "source_schema": "manufacturing"}
```

→ `MatchReport`. **아무것도 저장하지 않는다** (FR-030).

### `POST /api/schema/{schema_id}/reverse-bind/apply`

```json
{
  "datasource": "itest_pg", "source_schema": "manufacturing",
  "bindings": [{"entity": "설비일일점검", "table": "mfg_daily_equipment"}],
  "include_auto": true
}
```

| 필드 | 설명 |
|---|---|
| `bindings` | 사람이 확정한 것. `needs_review`/`conflict` 를 통과시키는 **유일한 경로** |
| `include_auto` | `auto` 판정을 함께 적용할지. 기본 `true` |

동작:
1. 대상 클래스에 `upsert_class_binding()` — 기존 001 경로를 그대로 쓴다 (FR-015).
2. `column_map` 은 **문서 속성명과 컬럼명을 모두** 보존 (FR-013):
   `{"property": "가동시간", "column": "run_hours", "type": "float"}`.
3. `element_provenance` 에 `strategy=doc_reverse_bind`, `evidence_kind=document`,
   `evidence_ref=<document_id>#<chunk_ref>@<page>` 기록 (FR-029).
4. `needs_review`/`conflict` 인데 `bindings` 에 없는 항목은 **건너뛰고** 결과에 남긴다.

응답:

```json
{
  "bound": ["설비일일점검"],
  "skipped": [{"entity": "제품", "reason": "conflict"}],
  "unbound_entities": ["작업지시서"],
  "counts": {"bound": 1, "skipped": 1, "unbound": 1}
}
```

## 불변식

1. 채점에 **LLM 호출 0회** — 같은 입력은 같은 순위.
2. `needs_review`/`conflict` 는 명시적 `bindings` 없이 **절대** 바인딩되지 않는다 (SC-003).
3. 서로 다른 도메인이면 `auto` 가 0건이고 두 결과가 분리 보고된다 (SC-004).
4. 문서 유래 관계와 FK 유래 관계는 `element_provenance.evidence_kind` 로 갈린다 (FR-014).
5. 바인딩된 클래스의 저장 인스턴스 수는 0 (studio-2 게이트, SC-012).
