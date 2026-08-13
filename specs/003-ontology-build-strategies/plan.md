# Implementation Plan: 입력 조합별 온톨로지 구축 전략

**Branch**: `main` (feature dir `003-ontology-build-strategies`) | **Date**: 2026-07-30 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/003-ontology-build-strategies/spec.md`

## Summary

세 가지 온톨로지 구축 전략을 **입력 조합**으로 분기시킨다. 전략 3(FK 매핑)은
[002](../002-catalog-driven-ontology/spec.md) 로 이미 있으므로 감싸기만 하고, 전략 1(문서 →
카탈로그 역바인딩)과 전략 2(인텐트 + 데이터 → 인과 발견)를 새로 만든다.

기술적 핵심은 두 가지다.

1. **전략 1 은 순수 로직으로 만든다.** 문서 추출은 기존 `document_indexing` 이 하고, 새로
   만드는 것은 *엔티티 ↔ 카탈로그 테이블 매칭 점수기*다. 이름 유사도 + 컬럼 겹침 + 값 형태
   일치를 각각 계산해 근거와 함께 순위를 낸다. 채점 자체는 결정적이라 단위 테스트가 가능하고,
   애매한 경우는 사람에게 넘긴다(FR-009).
2. **전략 2 의 통계는 이식하지 않고 domain-layer 에 무상태 계산 엔드포인트를 만들어 호출한다.**
   `causal_analysis.py` + `correlation_engine.py` 는 1,000줄 넘는 통계 코드이고, VAR 실패를
   분류 신호로 쓰는 하이브리드 라우팅이 미묘하다. 복사하면 두 벌이 갈라진다 — constitution
   원칙 III 이 경고하는 바로 그 실패 모드다. 대신 `schema_id` 없이 **행렬만 받아 엣지를
   돌려주는** 엔드포인트를 domain-layer 에 추가하고, ontology-studio 가 행을 가져와 넘긴다.
   온톨로지 쓰기는 전부 ontology-studio 가 갖는다.

근거와 대안 검토는 [research.md](./research.md) 에 있다.

## Technical Context

**Language/Version**: Python 3.12 (ontology-studio backend) · Python 3.11–3.12 (domain-layer) ·
Vue 3 + Vite (ontology-studio frontend)

**Primary Dependencies**:
- ontology-studio: FastAPI, `neo4j`, `httpx`, deepagents/langchain-core, pdfplumber
  — **새 의존성 없음** (statsmodels/pandas 를 들이지 않는 것이 설계 목표)
- domain-layer: 기존 `statsmodels>=0.14`, `pandas>=2.0`, `scipy>=1.11`, `numpy<2.0`
  — **새 의존성 없음** (이미 전부 있음)

**Storage**:
- SQLite (ontology-studio) — `ontology_schemas` · `schema_classes` · `schema_relationships` ·
  `class_datasource_bindings` · `class_behaviors`. 이 기능이 표 2개를 추가한다
  ([data-model.md](./data-model.md)).
- Neo4j (공유) — 카탈로그는 **읽기만** 한다. 새 divergence 를 만들지 않는다.

**Testing**: `pytest` (`ontology-studio/backend/tests`, `domain-layer/tests`) ·
`tests/integration_verify.py` (실서비스) · Playwright E2E · `scripts/inspect_catalog.py` (계약)

**Target Platform**: 로컬/온프렘 리눅스·macOS 다중 서비스. 이 머신은 포트가 재매핑되어 있다
(Neo4j 7688, text2sql 8020).

**Project Type**: 다중 서비스 (git 서브모듈) + 웹 프론트엔드

**Performance Goals**: 인과 발견 1회가 행 상한(기본 500) 안에서 끝난다. 전략 1 의 역검색은
카탈로그 1회 읽기 + 순수 계산이므로 테이블 수에 선형.

**Constraints**:
- api-gateway(9000) 경유 금지 — 30초 타임아웃이 MindsDB view 질의(10~25초)를 끊는다.
- `localhost` 대신 `127.0.0.1`.
- 행 상한 500 — MindsDB 가 `LIMIT 1000` 근처에서 연결을 끊는다.
- 새 서비스 URL 환경변수는 **접두사 포함형과 origin 형을 모두** 받아야 한다
  (`TEXT2SQL_BASE_URL` 이 실제로 낸 `/text2sql/text2sql/...` 404 버그).

**Scale/Scope**: 실측 카탈로그 기준 13 테이블 / 12 FK / 158 속성 (itest_pg / manufacturing).
전략 2 의 변수 쌍은 n(n−1)/2 로 늘어나므로 다중비교 보정이 필수(FR-020).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| # | 원칙 | 이 기능에 대한 게이트 | Phase 0 | Phase 1 |
|---|---|---|:---:|:---:|
| I | 인제스천 이후 Neo4j 가 단일 진실 원천 | 역검색은 Neo4j 카탈로그만 읽는다. `information_schema` 재조회 금지. 전략 2 의 실데이터는 text2sql 경유 | PASS | PASS |
| II | Table 은 항상 데이터소스로 함께 필터링 | 매칭용 카탈로그 읽기는 전부 `(t.datasource = $ds OR t.db = $ds)` 를 포함 | PASS | PASS |
| III | 읽을 때 두 표기 모두 받기 (COALESCE) | 새 Cypher 를 쓰지 않고 기존 `schema_ontology.read_catalog()` 를 재사용해 divergence 흡수를 한 곳에 유지 | PASS | PASS |
| IV | 전역 삭제 금지 | 어떤 전략도 전역 삭제를 하지 않는다. 정리는 `schema_id` 범위 | PASS | PASS |
| V | `:DataSource` 자격증명 미유출 | 역검색 결과·후보 응답에 `{datasource, schema, table}` 만. host/port/user/password 금지 | PASS | PASS |
| VI | 루트 `.env` 단일 원천 | 새 변수 `DOMAIN_LAYER_URL` 은 루트 `.env` 에만. **origin/접두사 양형 수용 필수**. 서브모듈에 `.env` 생성 금지. gateway 경유 금지 | PASS | PASS |
| VII | 통합 경로는 실제로 실행해 검증 | 단위 테스트만으로 완료 보고 금지. 새 서비스 간 호출은 실제 기동해 확인 | PASS | 부분 — 아래 참조 |
| studio-1 | 테이블 구조 → 온톨로지는 LLM 금지 | **전략 3 에만 적용된다.** 전략 3 은 손대지 않으므로 유지. 전략 2 의 **통계 판정 단계**에도 LLM 금지(FR-022) | PASS | PASS |
| studio-2 | 가상 클래스는 인스턴스 0건 | 전략 1·2 가 만드는 바인딩 클래스도 동일. 문서 기반 미바인딩 클래스는 예외(SC-012) | PASS | PASS |
| studio-3 | SQL 파라미터는 이스케이프 대신 타입 렌더 | 전략 2 의 데이터 조회도 기존 `datasource_exec` 경로를 쓴다. 새 SQL 조립 경로를 만들지 않는다 | PASS | PASS |

**게이트 결론**: 차단 위반 없음. 원칙 VI 가 이 기능에서 가장 위험하다 — 새 서비스 URL 이
하나 늘어나고, 그 URL 을 잘못 조립한 전례가 이미 있다. 그래서 URL 정규화를 **한 곳**에 두고
단위 테스트로 양형을 모두 고정한다.

**원칙 VII 관련 정직한 한계**: 전략 2 의 종단 검증은 domain-layer 와 text2sql 이 모두 기동하고
**시계열 데이터가 실제로 있는** 데이터소스를 요구한다. 실측 카탈로그
(`itest_pg`/`manufacturing`, 3행)는 최소 행 수 요건에 미달한다 — 즉 이 환경에서 전략 2 는
"엣지 0개 + 부족 사유 보고"(FR-017, SC-005)까지만 실증할 수 있고, 유의한 엣지가 나오는 경로는
합성 데이터로만 검증된다. 완료 보고 시 이 구분을 유지한다.

## Project Structure

### Documentation (this feature)

```text
specs/003-ontology-build-strategies/
├── spec.md              # 입력
├── plan.md              # 이 파일
├── research.md          # Phase 0 — 결정과 대안
├── data-model.md        # Phase 1 — SQLite 표·상태 전이
├── quickstart.md        # Phase 1 — 검증 실행 절차
├── contracts/           # Phase 1 — HTTP·도구 계약
│   ├── strategy-select.md
│   ├── strategy1-reverse-bind.md
│   ├── strategy2-causal.md
│   └── domain-layer-analyze-matrix.md
├── checklists/
│   └── requirements.md
└── tasks.md             # Phase 2 (/speckit-tasks)
```

### Source Code (repository root)

```text
ontology-studio/backend/src/modules/ontology/
├── schema_ontology.py           # 전략 3 — 기존, 손대지 않음 (read_catalog 재사용)
├── build_strategy.py            # 신규 — 전략 추천 (FR-001~004), 순수 로직
├── entity_matcher.py            # 신규 — 엔티티↔테이블 역검색 점수기 (FR-006~012), 순수 로직
├── doc_ontology.py              # 신규 — 전략 1 오케스트레이션: 추출→역검색→바인딩 적용
├── causal_ontology.py           # 신규 — 전략 2 오케스트레이션: 행 조회→계산 위임→관계 적용
├── causal_client.py             # 신규 — domain-layer 무상태 계산 클라이언트 + URL 정규화
├── provenance.py                # 신규 — 출처 기록/조회 (FR-029)
├── datafabric_client.py         # 기존 — 정규화는 여기 한 곳
├── datasource_exec.py           # 기존 — SQL 렌더·행 상한·실행
├── datasource_api.py            # 확장 — 새 라우트 추가
└── tools.py                     # 확장 — 빌드 에이전트 도구 등록

ontology-studio/backend/src/modules/agent_session/
└── session_store.py             # 확장 — 표 2개 추가 (출처 · 인과 가설)

ontology-studio/backend/tests/modules/ontology/
├── test_build_strategy.py       # 신규
├── test_entity_matcher.py       # 신규
├── test_causal_client.py        # 신규 — URL 양형 고정 (원칙 VI 회귀 가드)
├── test_causal_ontology.py      # 신규
└── test_provenance.py           # 신규

domain-layer/app/
├── routers/whatif.py            # 확장 — POST /whatif/analyze-matrix (무상태)
└── services/whatif/
    └── matrix_adapter.py        # 신규 — rows+spec → DataFrame/NodeColumn 어댑터

domain-layer/tests/
└── test_analyze_matrix.py       # 신규

ontology-studio/frontend/src/features/ontology/
├── OntologyBuildBriefPanel.vue  # 확장 — 전략 추천 표시·선택
├── BindingCandidatePanel.vue    # 신규 — 역검색 후보 검토/확정
└── CausalEdgeReviewPanel.vue    # 신규 — 인과 엣지 승인/거부/반전
```

**Structure Decision**: 기존 다중 서브모듈 배치를 그대로 따른다. 새 디렉터리를 만들지 않고
`modules/ontology/` 안에 전략별 모듈을 하나씩 둔다 — 002 가 `schema_ontology.py` 를 그 자리에
둔 것과 같은 층이다. 순수 로직(`build_strategy`, `entity_matcher`, `provenance`)을 I/O 를 하는
오케스트레이션(`doc_ontology`, `causal_ontology`)과 파일 단위로 분리해, 점수기와 전략 추천이
서비스 기동 없이 단위 테스트되게 만든다. domain-layer 변경은 **엔드포인트 1개 + 어댑터 1개**로
최소화하고 기존 통계 코드는 수정하지 않는다.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| ontology-studio → domain-layer 서비스 간 새 의존성 (전략 2 가 domain-layer 기동을 요구) | 통계 엔진(`causal_analysis.py` + `correlation_engine.py`, 1,000줄+)이 domain-layer 에만 있고 statsmodels/scipy/pandas 도 거기에만 있다. 하이브리드 VAR-실패 라우팅은 미묘해서 두 벌이 갈라지면 어느 쪽이 맞는지 알 수 없다 — constitution III 이 경고하는 실패 모드 | **(a) 통계 코드를 ontology-studio 로 이식**: 002 가 `schema_extractor.py` 를 이식한 전례가 있으나, 그때는 문자열 매핑 50줄이었고 **의도적 divergence**(FR-004)가 목표였다. 여기서는 통계적 **동일성**이 목표다. 게다가 ontology-studio 에 과학 스택(≈100MB)을 새로 들여야 한다. **(b) 기존 `POST /whatif/discover-edges` 호출**: `schema_id` 로 domain-layer 자체 스키마 스토어를 읽고 `ANALYSIS_TARGET_LABELS` 로 필터하며 자동 바인딩까지 한다. 쓰려면 ontology-studio 의 클래스를 domain-layer 스키마 스토어로 복제해야 하고, 그러면 두 번째 writer 가 공유 그래프에 생긴다. 게다가 domain-layer 온톨로지는 프로세스 메모리에만 있어 재시작 시 유실된다 (installation.md 이슈 #14) |
| 전략 1·2 가 LLM 을 쓴다 (studio-1 게이트와 표면상 상충) | 문서에서 엔티티를 뽑고 인텐트를 해석하는 일은 결정적 규칙으로 환원되지 않는다 | studio-1 은 **"테이블 구조 → 온톨로지" 경로**에 걸린 규칙이고 그 경로가 전략 3 이다. 전략 3 은 이 기능에서 수정하지 않으므로 규칙은 그대로 지켜진다. 전략 2 는 LLM 을 **인텐트 해석에만** 두고 통계 판정에서 배제해(FR-022) 재현성을 확보한다 — 게이트의 취지(같은 입력 → 같은 결과)를 판정 단계에서 유지 |
