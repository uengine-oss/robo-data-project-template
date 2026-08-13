---

description: "Task list for 003-ontology-build-strategies"
---

# Tasks: 입력 조합별 온톨로지 구축 전략

**Input**: Design documents from `/specs/003-ontology-build-strategies/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md),
[data-model.md](./data-model.md), [contracts/](./contracts/)

**Tests**: 포함한다. spec 의 SC-003·SC-005·SC-006·SC-007·SC-009·SC-010 이 단위 테스트로만
확인 가능하고, constitution 원칙 VI 의 URL 조립 버그는 **문자열 단언 없이는 잡히지 않는다**
(목 트랜스포트는 우리가 만든 URL 을 그대로 받는다).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: 병렬 가능 (다른 파일, 의존 없음)
- **[Story]**: US1(전략 1) · US2(전략 2) · US3(전략 추천) · US4(순차 적용)

## Path Conventions

`ontology-studio/backend/src/modules/...` · `ontology-studio/backend/tests/modules/...` ·
`domain-layer/app/...` — plan.md 의 Project Structure 를 따른다.

---

## Phase 1: Foundational (Blocking Prerequisites)

**Purpose**: 저장 계층과 출처 기록. 어느 스토리도 이것 없이는 진행할 수 없다.

**⚠️ 이 단계가 끝나기 전에는 스토리 작업을 시작하지 않는다**

- [x] T001 `session_store.py` 의 `_ensure_schema_tables()` 에 `element_provenance` 표 추가
      (data-model.md 표 1). `CREATE TABLE IF NOT EXISTS` — 기존 마이그레이션 패턴을 따른다
- [x] T002 `session_store.py` 에 `causal_hypotheses` 표 추가 (data-model.md 표 2).
      PK 에 `lag` 포함 — 같은 쌍의 다른 시차는 **다른 가설**이다
- [x] T003 `session_store.py` 에 접근 함수 추가: `upsert_provenance`, `list_provenance`,
      `upsert_causal_hypothesis`(기존 `decision` 을 **덮지 않음**), `list_causal_hypotheses`,
      `set_causal_decision`
- [x] T004 [P] `modules/ontology/provenance.py` — 출처 기록/조회 래퍼 + 열거값 검증 (FR-029)
- [x] T005 [P] `tests/modules/ontology/test_provenance.py` — 열거값 거부, 먼저 만든 출처 유지
      (SC-011)
- [x] T006 `tests/.../test_session_store_causal.py` — 재실행 upsert 가 `decision`·`decided_at`
      을 보존하는지 (**SC-009 의 핵심 가드**)

**Checkpoint**: 표와 접근 함수가 있고, 결정 보존이 테스트로 고정됐다.

---

## Phase 2: User Story 3 — 전략 추천 (P2, 먼저 구현)

**Goal**: 입력 조합에서 전략을 결정적으로 추천하고 비활성 사유를 보인다.

**왜 P2 를 먼저**: 순수 함수이고 US1·US2 의 진입점이다. 다른 스토리가 이 판정에 붙는다.

**Independent Test**: 입력 조합 4가지로 추천과 비활성 사유가 contracts/strategy-select.md 의
표와 일치.

- [x] T007 [P] [US3] `modules/ontology/build_strategy.py` — `recommend()` 순수 함수.
      I/O 없음. contracts/strategy-select.md 의 결정 표 그대로 (FR-001~003)
- [x] T008 [P] [US3] `build_strategy.py` — `check_timeseries_ready(catalog, max_lag)`:
      시간축 존재 · 수치 변수 ≥2 · 최소 행 수 `max_lag×2+10` (FR-017, research.md R5).
      **미충족 사유를 숫자와 함께** 반환
- [x] T009 [US3] `tests/.../test_build_strategy.py` — 결정 표 전 행, 반복 호출 동일성
      (SC-010), 비활성 사유가 "서비스 없음" 과 "데이터 부적합" 을 **구분**하는지
- [x] T010 [US3] `datasource_api.py` — `GET /api/build-strategy/recommend`. 카탈로그·통계
      서비스 부재 시 예외 전파 금지, `timeseries_ready=false` + 구분된 사유로 접는다.
      응답에 접속 정보 금지 (원칙 V)

**Checkpoint**: 추천이 HTTP 로 확인되고 결정적이다.

---

## Phase 3: User Story 1 — 전략 1 역바인딩 (P1) 🎯 MVP

**Goal**: 문서가 정의한 엔티티에 카탈로그 테이블을 역으로 찾아 바인딩한다.

**Independent Test**: 문서 1건 + 메타데이터 추출된 데이터소스 1개 → 문서 용어로 조회 시 실제 행.

- [x] T011 [P] [US1] `modules/ontology/entity_matcher.py` — 토큰화(`_tokenize`: snake/camel
      분해, 소문자) + 3신호 점수 (`column 0.6 / type 0.2 / name 0.2`).
      `column_score` 는 coverage·precision 의 **조화평균** (research.md R3)
- [x] T012 [US1] `entity_matcher.py` — `score_entity()` 가 `evidence` 를 **반드시** 포함해
      반환 (FR-008). 정렬 `(-score, table_name)` 으로 결정적
- [x] T013 [US1] `entity_matcher.py` — `match_all()`: `auto`/`needs_review`/`no_match` 판정 +
      `conflict` 교차 판정 + `unbound_entities` + `uncovered_tables` (FR-009~012)
- [x] T014 [US1] `tests/.../test_entity_matcher.py`:
      - 한글 엔티티 ↔ 영문 테이블 (name_score=0 인데 컬럼 겹침으로 매칭) — **정상 케이스 가드**
      - `order` vs `order_log` 구분 (FR-006)
      - 200컬럼 테이블이 조화평균 때문에 모든 엔티티에 매칭되지 **않음**
      - 동점 근접 → `needs_review` (SC-003)
      - 한 테이블이 2엔티티 1위 → `conflict` (FR-012)
      - 다른 도메인 → `auto` 0건 (SC-004)
- [x] T015 [US1] `modules/ontology/doc_ontology.py` — `preview()`: `schema_id` 의 클래스 목록 +
      `schema_ontology.read_catalog()`(재사용, 원칙 II·III) → `MatchReport`. **저장 없음**
- [x] T016 [US1] `doc_ontology.py` — `apply()`: `auto` + 명시 `bindings` 만
      `upsert_class_binding()` 호출 (기존 001 경로 재사용, FR-015). `column_map` 에 문서 속성명과
      컬럼명 **둘 다** 보존 (FR-013). `element_provenance` 기록
- [x] T017 [US1] `doc_ontology.py` — `needs_review`/`conflict` 는 명시 확정 없이 **절대**
      바인딩하지 않는다. 건너뛴 항목을 `skipped` 로 반환 (SC-003)
- [x] T018 [US1] `tests/.../test_doc_ontology.py` — apply 가 `needs_review` 를 건너뛰는지,
      미바인딩 엔티티가 **지워지지 않는지** (SC-002), preview 가 저장하지 않는지 (FR-030)
- [x] T019 [US1] `datasource_api.py` — `POST /api/schema/{schema_id}/reverse-bind/preview`
      · `.../apply` (contracts/strategy1-reverse-bind.md)

**Checkpoint**: US1 단독으로 배포 가능. 문서 용어로 운영 데이터에 도달한다 (SC-001).

---

## Phase 4: User Story 2 — 전략 2 인과 발견 (P1)

**Goal**: 인텐트 + 데이터에서 인과 후보를 찾아 **가설로** 저장하고, 승인분만 관계로 승격한다.

**Independent Test**: 문서 없이 인텐트 + 시계열 데이터소스 → 방법·강도·p-value·시차가 실린
가설. 전제 미충족이면 엣지 0개 + 사유.

### domain-layer (통계 서비스)

- [x] T020 [P] [US2] `domain-layer/app/services/whatif/matrix_adapter.py` — `rows` + `columns`
      → `DataFrame` + `NodeColumn` 리스트. **기존 통계 코드를 수정하지 않는다**
- [x] T021 [US2] `matrix_adapter.py` — Benjamini–Hochberg 보정 (research.md R4). 원시·보정
      p-value 를 **둘 다** 반환, `p_value_adjusted >= p_value` 보장
- [x] T022 [US2] `matrix_adapter.py` — 전제 검사: `no_time_column` / `insufficient_variables`
      / `insufficient_rows`. **`edges` 는 항상 `[]`** (FR-017, SC-005). 기존 코드의
      `warnings.warn()` + 진행을 **거부로 바꾼다**
- [x] T023 [US2] `domain-layer/app/routers/whatif.py` — `POST /whatif/analyze-matrix`.
      `schema_id` 없음, Neo4j 쓰기 없음, 스키마 스토어 읽기 없음
      (contracts/domain-layer-analyze-matrix.md)
- [x] T024 [US2] `domain-layer/tests/test_analyze_matrix.py`:
      - 전제 미충족 3종 → `edges == []`, `ok == false`, HTTP 200
      - `tests_performed` 노출, `correction == "benjamini-hochberg"`
      - **셔플 검증** (SC-006): 무작위 섞은 데이터에서 보정 후 유의 엣지가 기대 오류율 이내
      - 같은 요청 2회 → 같은 엣지 집합·순서 (SC-007)
      - VAR 실패 → `var_fit` 분류 신호, 500 이 아님 (FR-024)

### ontology-studio (오케스트레이션)

- [x] T025 [P] [US2] `modules/ontology/causal_client.py` — **URL 정규화 한 곳**.
      origin / 접두사 / 트레일링 슬래시 4형태 모두 수용 (원칙 VI). `127.0.0.1` 기본,
      게이트웨이 경유 금지
- [x] T026 [US2] `causal_client.py` — 서비스 부재 시 예외 전파 금지 →
      `{"ok": false, "reason": "stats_service_unavailable"}`
- [x] T027 [US2] `tests/.../test_causal_client.py` — **URL 4형태를 문자열로 직접 단언**
      (원칙 VI 회귀 가드. 목 트랜스포트는 잘못된 URL 도 받아준다), 서비스 부재 시 저하
- [x] T028 [US2] `modules/ontology/causal_ontology.py` — 인텐트 → 타겟·변수 도출.
      결과를 응답에 싣고 기록 (FR-016). LLM 은 **여기까지만**
- [x] T029 [US2] `causal_ontology.py` — 행 조회는 기존 `datasource_exec` 경로 (studio-3 게이트).
      행 상한 적용, 잘렸으면 `truncated: true` (FR-025)
- [x] T030 [US2] `causal_ontology.py` — `discover()`: 전제 검사 → 계산 위임 → 가설 upsert
      (`decision` 보존). `preserved_decisions` 반환. `dry_run` 지원 (FR-030)
- [x] T031 [US2] `causal_ontology.py` — `decide()` / `apply()`. `approved`·`reversed` 만
      `INFLUENCES_<TARGET>` 관계로 승격, properties 에 method·lag·p_value·p_value_adjusted·
      strength·direction·`hypothesis: true`. `element_provenance` 에 `statistical` 기록
      (FR-021, R9)
- [x] T032 [US2] `tests/.../test_causal_ontology.py` — 전제 미충족 → 가설 0건,
      재실행이 `rejected` 를 보존 (SC-009), `pending` 이 승격되지 **않음**,
      `INFLUENCES_` 접두사로 FK 유래와 구분 (SC-008)
- [x] T033 [US2] `datasource_api.py` — `POST .../causal/discover` · `.../causal/decide` ·
      `.../causal/apply` (contracts/strategy2-causal.md)
- [x] T034 [US2] 루트 `.env.example` 에 `DOMAIN_LAYER_URL` 추가. **서브모듈에 `.env` 를 만들지
      않는다** (원칙 VI)

**Checkpoint**: US2 단독으로 배포 가능. 전제 미충족 경로가 실데이터로 검증된다.

---

## Phase 5: User Story 4 — 순차 적용 (P3)

**Goal**: 전략 3/1 이 만든 구조 위에 전략 2 로 인과 관계만 덧붙인다.

- [x] T035 [US4] `doc_ontology.py` · `causal_ontology.py` — 기존 클래스 중복 생성 금지.
      두 번째 전략은 관계만 추가 (FR-004)
- [x] T036 [US4] `tests/.../test_strategy_compose.py` — 전략 3 → 전략 2 순차 적용 시 클래스
      중복 0개, 모든 요소에 출처 100% (SC-011)
- [x] T037 [US4] `schema_ontology.py` 호출부에 출처 기록 추가 (`catalog_schema` /
      `foreign_key`). **매핑 규칙은 손대지 않는다** (FR-027, 002 확정)
- [x] T038 [US4] `schema_ontology.py` 결과에 FK 부재 보고 추가 — 관계 0개면 전략 1·2 보완 안내
      (FR-028)

---

## Phase 6: 에이전트 도구 등록

- [x] T039 [P] `modules/ontology/tools.py` — `build_strategy_recommend`,
      `reverse_bind_preview`, `reverse_bind_apply`, `causal_discover` 도구 등록
- [x] T040 `tools.py` — **자연어 폴백처럼, 인과 `apply` 는 빌드 시 검증 도구 목록에 넣지
      않는다.** 승격은 사람 판정을 거쳐야 한다 (FR-023)
- [x] T041 `agent_session/service.py` 프롬프트 — 입력 조합별 전략 선택 안내 추가
- [x] T042 `tests/.../test_ontology_mcp.py` — 외부(MCP) 표면 도구 목록이 **넓어지지 않았는지**
      회귀 가드 (001 SC-006 과 같은 성질)

---

## Phase 7: 프론트엔드 (백엔드 계약 고정 후)

- [x] T043 [P] `OntologyBuildBriefPanel.vue` — 전략 추천 표시 + 선택. 비활성 전략은 사유와
      함께 비활성 (FR-002, FR-003)
- [x] T044 [P] `BindingCandidatePanel.vue` — 후보 검토/확정. `evidence` 를 보여야 한다 —
      점수만 보여주면 검토가 불가능하다 (FR-008)
- [x] T045 [P] `CausalEdgeReviewPanel.vue` — 엣지 승인/거부/방향 반전. **가설**임을 명시
      (FR-021)
- [x] T046 그래프 UI — `INFLUENCES_*` 를 `REFERENCES_*` 와 시각적으로 구분 (FR-021)

---

## Phase 8: 검증 (constitution 원칙 VII)

- [x] T047 단위 테스트 전량 통과 — ontology-studio + domain-layer
- [x] T048 `scripts/inspect_catalog.py` 어긋남 0 (SC-013)
- [x] T049 실서비스 통합 검증 — quickstart.md 4~7단계. **단위 테스트만 통과한 것을
      "동작한다"고 보고하지 않는다**
- [x] T050 완료 보고에 **검증된 것과 미검증인 것을 구분**해 적는다. 이 환경의 카탈로그는 3행
      이므로 전략 2 의 유의 엣지 경로는 합성 데이터로만 확인된다 (plan.md 원칙 VII 절)

---

## Dependencies

```
Phase 1 (T001-T006)  ─── 모든 스토리의 선행 조건
        │
        ├──▶ Phase 2 US3 (T007-T010)  ─── 순수 함수, 진입점
        │
        ├──▶ Phase 3 US1 (T011-T019)  ─── MVP. US3 와 병렬 가능
        │
        ├──▶ Phase 4 US2 (T020-T034)  ─── domain-layer(T020-T024) 와
        │                                  ontology-studio(T025-T033) 병렬 가능
        │
        └──▶ Phase 5 US4 (T035-T038)  ─── US1 또는 US2 중 하나 완료 후
                  │
                  ▼
        Phase 6 (T039-T042) → Phase 7 (T043-T046) → Phase 8 (T047-T050)
```

**병렬 실행 가능**: T004+T005 · T007+T008 · T011 · T020+T025 · T043+T044+T045

## Implementation Strategy

**MVP = Phase 1 + Phase 2 + Phase 3** (T001-T019). 전략 추천과 전략 1 만으로 사용자 질문의
첫 문장이 해결되고, 문서 용어로 운영 데이터에 도달한다.

전략 2(Phase 4)는 domain-layer 기동을 요구하므로 독립 증분으로 붙인다. 전략 2 가 없어도
전략 1·3 은 그대로 동작한다.

**우선순위 근거**: 순수 로직(T007-T014)이 먼저다. 서비스 기동 없이 테스트되고, 이 기능의
판단 규칙(점수·판정·추천)이 전부 거기 있다. 오케스트레이션과 HTTP 는 그 위에 얇게 얹는다.

---

## 진행 상태 (2026-07-30)

### 완료 (T001–T050 전체)

백엔드 전량 + 에이전트 도구 등록 + 프론트엔드 4개 + 단위 테스트 + 신규 서비스 간 계약의
실환경 검증.

| 검증 | 결과 |
|---|---|
| ontology-studio 단위 테스트 | **367 passed** (기존 355 → 신규 49 추가, 회귀 0) |
| domain-layer 단위 테스트 | **27 passed** (기존 7 + 신규 20) |
| 카탈로그 계약 재확인 | **13 확인 / 0 어긋남** (`scripts/inspect_catalog.py`) |
| 라우트 등록 | 신규 7개 경로 전부 확인 |
| 에이전트 도구 | 4개 등록 확인, `causal_apply` 는 **부재** 확인 (승격은 사람 판정) |
| 프론트엔드 빌드 | 통과 (33 modules) — 신규 패널 2개 + 브리프 전략 표시 + 그래프 가설 구분 |
| 프론트엔드 E2E | **5 passed** (`tests/e2e_build_strategy.spec.js`) — 스크린샷으로 렌더 확인 |
| `POST /whatif/analyze-matrix` 실HTTP | **동작 확인** — 120행 합성 데이터에서 주입한 lag=2 를 Granger 가 회수, `tests_performed=2`, `correction=benjamini-hochberg` |
| 전제 미충족 실HTTP | `insufficient_rows`(3행→14행 필요) · `no_time_column` 모두 HTTP 200 + `edges: []` |
| URL 정규화 실환경 (원칙 VI) | origin·`/whatif`·트레일링 슬래시 3형태가 **모두 실제 핸들러에 도달** — 404 폴백이 아님을 `reason=insufficient_rows` 로 확인 |

### 구현 중 발견해 고친 결함 (3건)

기존 엔진은 `if not edges and try_var:` 로 **아무것도 찾지 못했을 때** 기여도 분해로 폴백한다
(`causal_analysis.py:433`). "찾지 못했다" 는 무관한 변수들의 정상 결과이므로, 독립 난수 5개를
섞어 넣으면 **decomposition 엣지 20개가 전부 유의로** 나왔다 — 잡음에서 인과를 제조하는,
SC-006 이 잡으려던 바로 그 실패였다.

기존 통계 코드는 수정하지 않고(다른 호출자가 의존한다) 어댑터에서 막았다: `deterministic`
힌트가 있는 쌍만 강도로 판정하고, 나머지 분해형은 `basis: decomposition_unhinted` +
`significant: false` 로 검토용으로만 반환한다.

이 결함을 처음 놓친 이유도 기록해 둔다 — 셔플 테스트가 `tested` 엣지만 필터링해서
**공허하게 통과**(`tests_performed: 0`)했다. 지금은 전체 엣지에 대해 단언하고,
"가설검정이 실제로 수행됐는지" 확인하는 별도 테스트를 두었다.

**2. 매칭 점수 오보정 — 실데이터로만 드러났다 (원칙 VII)**

`column_score` 를 coverage·precision 의 조화평균으로 두었더니, 규정서가 7속성을 기술한
`설비일일점검` 이 13컬럼 테이블에 대해 coverage 0.86 · precision 0.46 → **0.56** 으로 떨어져
`needs_review` 가 됐다. 2위가 **0.0** 인 명백한 정답인데도 사람 확인을 요구한 것이다.

문서는 테이블의 **부분집합**을 기술하는 것이 정상이므로 precision 을 coverage 와 동등하게
가중하면 정상 케이스가 벌을 받는다. precision 을 하한(`PRECISION_FLOOR = 0.30`) 방식으로
바꿨다 — 하한 이상이면 감점 없음, 미만이면 선형 감소. 200컬럼 가드(precision 0.01)는 그대로
작동한다. 실측 재확인: 0.7143 → `auto`.

단위 테스트가 못 잡은 이유: 픽스처가 엔티티 속성과 테이블 컬럼을 **정확히 일치**시켜
precision 이 항상 1.0 이었다. 실제 비율(7 vs 13)을 쓰는 테스트를 추가했다.

**3. 한글 클래스명이 관계명에서 사라졌다**

`_relationship_name()` 의 정규식이 non-ASCII 를 제거해 `설비일일점검` → **`INFLUENCES_`**
(접미사 없음)가 됐다. 전략 1 은 문서의 도메인 용어로 클래스를 만들므로 한글 클래스명이
예외가 아니라 **표준**이고, 모든 인과 관계가 같은 이름을 갖게 된다. `가-힣` 를 보존하도록
고쳤다 (`entity_matcher.tokenize` 와 동일 문자클래스). 실측: `INFLUENCES_설비일일점검`.

세 결함 모두 **단위 테스트가 전부 통과한 상태**에서 실행으로만 드러났다 — constitution
원칙 VII 이 요구하는 바로 그 이유다.

### 실서비스 종단 검증 (T049) — 실행함

스키마 픽스처를 API 로 직접 만들어(한글 클래스명 + 실제 컬럼명 속성) 전략 1·2 를 실데이터로
끝까지 돌렸다.

| 확인 | 실측 결과 |
|---|---|
| 전략 추천 (SC-010) | 데이터소스만 → `catalog_schema`, 인텐트 추가 → `causal_discovery`. 접속정보 미노출 |
| 역바인딩 (SC-001) | `설비일일점검` → `mfg_daily_equipment` (score 0.7143, auto). **한글 도메인 용어로 조회 시 실제 3행** 반환 |
| 미바인딩 보존 (SC-002) | `작업지시서` 가 `materialized` 로 온톨로지에 **남음** |
| 억지 매칭 금지 (SC-004) | DB 에 대응 없는 엔티티는 `no_match`, 자동 바인딩 0건 |
| 인스턴스 0 (SC-012) | 바인딩 클래스 조회 후에도 저장 인스턴스 **0** |
| 인과 발견 | **500행** 분석, granger·correlation 엣지 6건 (lag 1·2), BH 보정 적용, `truncated: true` |
| 결정 보존 (SC-009) | 거부 1 + 승인 1 → 재실행 후에도 유지, `preserved_decisions: 2` |
| 승격 | 승인분만 `INFLUENCES_설비일일점검` 로 승격, `pending` 4 · `rejected` 1 **미승격** |
| 카탈로그 계약 (SC-013) | 전 과정 후에도 **13 확인 / 0 어긋남** |

**앞선 보고의 정정**: "이 환경의 카탈로그는 3행이라 전략 2 의 유의 엣지를 실데이터로 검증할 수
없다" 고 적었는데 **틀렸다.** `mfg_daily_equipment` 는 500행 이상이고(행 상한에 걸려 잘림),
실데이터에서 유의 엣지가 정상적으로 나왔다. 3행은 특정 클래스 조회에 걸린 limit 결과를
테이블 크기로 잘못 읽은 것이다.
