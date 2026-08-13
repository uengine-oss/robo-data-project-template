# Implementation Plan: 레거시 메타데이터에서 온톨로지까지

**Branch**: `008-legacy-metadata-to-ontology` | **Date**: 2026-08-05 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/008-legacy-metadata-to-ontology/spec.md`

---

## Summary

예제를 **이름이 의미를 말해주지 않는 레거시**로 바꿔, 증강 없이는 테이블 선택이 **산술적으로**
실패하게 만든다. 그 조건 위에서 (a) 프로시저·데이터 샘플로 메타데이터를 증강하고, (b) 증강 결과를
테이블 선택이 **처음으로 소비**하게 만들고, (c) 질의 결과를 온톨로지 객체로 만든다.

핵심 기술 접근은 셋이다.

1. **난독화는 생성물이다.** 이름 매핑에서 결정적으로 생성하고, 매핑 파일을 **정답지**로 커밋한다.
   이로써 SC-001~005 를 사람 눈이 아니라 스크립트로 채점한다.
2. **채점기는 결정적으로 유지한다.** `entity_matcher` 의 "LLM 을 부르지 않는다"는 성질을 깨지
   않는다. 증강 신호는 **텍스트 토큰과 값 형태**로 넣고, 임베딩은 채점이 아니라 **후보 축소**
   단계로 분리한다. (§research R2)
3. **domain-layer 편입은 격리 우선.** 포트·DB·동시성을 먼저 고정하고, 그 다음에 기능을 연결한다.

---

## Technical Context

**Language/Version**: Python 3.11 (domain-layer) · Python 3.12 (ontology-studio, data-fabric,
text2sql, robo-data-analyzer) · Node 20 / Electron 33 (desktop) · Vue 3 (frontend) · SQL
(PostgreSQL 16) · Cypher (Neo4j 5.26)

**Primary Dependencies**: FastAPI · Neo4j Python driver · asyncpg · MindsDB · podman compose ·
ANTLR (code parsing)

**Storage**: 공유 Neo4j 그래프(카탈로그 + 온톨로지) · PostgreSQL(샘플 데이터, ObjectType 물리
테이블) · SQLite(ontology-studio 바인딩·behavior) · MySQL(샘플 데이터)

**Testing**: pytest(백엔드 단위) · `tests/integration_verify.py`(실서비스 통합) · Playwright(E2E) ·
**신규**: 채점 하네스(`scripts/score_scenario.py`)

**Target Platform**: macOS/Windows 데스크톱 설치본 (Electron + podman)

**Project Type**: 다중 서비스 플랫폼 (서브모듈 조합) + 데스크톱 셸

**Performance Goals**: 시나리오 전체(등록 → 증강 → 구축 → 질의 → 객체화)를 사용자가 중간에
막히지 않고 완주. 증강 단계는 기존 인제스천 소요를 크게 넘지 않는다.

**Constraints**:
- **메모리** — 유휴 실측 7.3 GiB (podman VM 6.02 + Electron 0.56 + 호스트 파이썬 0.73,
  2026-08-05). domain-layer 편입이 이 위에 얹힌다. VM 정원 6 GiB 는 **설정값**이고 컨테이너
  실수요는 2.80 GiB 이므로 축소 여지가 있다.
- **결정성** — 전략3(카탈로그 → 온톨로지)은 LLM 을 부르지 않는다(헌법). `entity_matcher` 도
  같은 성질을 갖는다. 이 계획은 그 성질을 **유지**한다.
- **비파괴** — 헌법 원칙 IV. 시나리오 실행이 기존 데이터를 지우지 않는다.

**Scale/Scope**: 예제 13테이블 · 158컬럼 · FK 12 · 프로시저 5 · DML 4.9 MB. 서브모듈 4개
(ontology-studio, domain-layer, robo-data-analyzer, desktop 리소스) + 헌법 + 매뉴얼.

---

## Constitution Check

*GATE: Phase 0 이전에 통과해야 하고, Phase 1 이후 재확인한다.*

### 통과

| 원칙 | 판정 | 근거 |
|---|---|---|
| I. 카탈로그가 단일 진실 원천 | ✅ | 증강 결과도 Neo4j 카탈로그에 쓴다. 소스 DB 재조회 없음 |
| II. Table 은 데이터소스와 함께 필터 | ✅ | 두 예제가 같은 데이터소스의 **다른 스키마**이므로 `schema` 필터가 이미 필수 |
| V. 자격증명 비노출 | ✅ | 새 외부 표면 없음. domain-layer 응답도 sanitize 대상에 포함 |
| VII. 통합 경로 실제 실행 검증 | ✅ | 채점 하네스가 실서비스 대상. 단위 테스트만으로 완료 보고하지 않음 |

### 위반 — 정당화 필요

| # | 원칙 | 위반 내용 | 처리 |
|---|---|---|---|
| **V-1** | **"온톨로지 쓰기는 ontology-studio 가 단독으로 갖는다"** | Q1-B 로 domain-layer 가 온톨로지에 쓴다 | **헌법 개정이 산출물** (T8). 경계를 명문화하고 **코드로 강제**한다 — 문서만 고치면 다음 사람이 같은 자리에서 충돌한다 |
| **V-2** | ontology-studio 절 — *"domain-layer 의 `value.replace("'", "''")` 후 문자열 연결 방식은 복사하지 않는다"* | **복사가 아니라 편입이므로 그 패턴이 제품에 실려 나간다.** 헌법은 "복사 금지"만 규정했지 "번들 금지"는 규정하지 않았다 — 이 스펙이 그 빈틈을 처음 밟는다 | T5 에서 **편입 전에 해당 경로를 점검**한다. 사용자 입력이 닿는 경로면 파라미터 렌더링으로 교체하거나 노출을 막는다. §research R5 |
| **V-3** | 원칙 III — divergence 는 한 곳에서 흡수하고 표에 기록 | domain-layer 는 `OntologyType`/`OntologyNode` 이중 라벨, 관계는 전부 `EFFECTS`(오탈자로 보이나 실제 값), FK 는 `FK_TO_TABLE` 표기를 쓴다 | 편입은 **새 divergence 를 그래프에 들인다.** T5 에서 `docs/catalog-schema.md` 표에 추가한다 |
| **V-4** | 원칙 VI — 포트/URL 정규화 | domain-layer 포트가 코드 8002 / 규약 8001 / Dockerfile 8002 로 셋이 어긋남 | T5 에서 한 값으로 고정 (FR-035) |
| **V-5** | 원칙 IV — 파괴적 삭제 | domain-layer 스키마 저장이 **전체 재작성**(스키마 노드 DETACH DELETE 후 재생성) | 전역은 아니므로 원칙 IV 직접 위반은 아니나, 동시 실행 시 서로를 지운다. T5 에서 보호 (FR-037) |

> **V-2 가 이 계획에서 가장 조용한 위험이다.** 나머지는 눈에 보이는 설정·문서 문제지만, 이것은
> "복사하지 말라"고 이미 판정된 패턴이 **번들이라는 다른 문에 실려 제품에 들어가는** 경우다.
> 편입 자체를 막을 이유는 아니지만, 편입 전에 반드시 확인해야 한다.

### 재확인 (Phase 1 이후 — 2026-08-05)

| # | 상태 | Phase 1 설계가 어떻게 다루는가 |
|---|---|---|
| **V-1** | ✅ 해소 방법 확정 | **라벨 소유권 레지스트리**로 강제한다 (아래) |
| **V-2** | ✅ 격리 확정 | 확인 전까지 해당 엔드포인트를 게이트웨이에 **노출하지 않는다**. research R5 |
| **V-3** | ✅ 기록 위치 확정 | `data-model.md §6` 표 → `docs/catalog-schema.md` 이관 (T5) |
| **V-4** | ✅ 해소 방법 확정 | 컨테이너 내부 `8002` 유지 + 호스트 노출만 새 값. **충돌은 4중**이었다 (research R4) |
| **V-5** | ✅ | 전역 삭제가 아니라 스키마 범위 재작성. 동시성 보호는 FR-037 |

#### V-1 을 코드로 강제하는 방법 — 라벨 소유권 레지스트리

문서만 고치면 다음 사람이 같은 자리에서 충돌한다. 쓰기 주체 경계(`data-model.md §6`)를
**검사 가능한 형태**로 만든다.

각 writer 가 **자기가 소유하는 라벨 집합을 선언**하고, `scripts/inspect_catalog.py` 가 다음을
검사한다.

1. **선언 집합끼리 교집합이 없다.** 겹치면 두 서비스가 같은 노드를 덮어쓸 수 있다.
2. **그래프에 실재하는 모든 라벨이 정확히 한 주체에 속한다.** 어디에도 속하지 않는 라벨은
   "누가 썼는지 모르는 노드"이므로 보고한다.
3. **선언과 구현이 어긋나지 않는다.** 분석기는 이미 이 형태를 갖췄다 — `_owned_labels()` 가
   `CONSTRAINTS` 에서 라벨을 **유도**하므로 별도 목록이 드리프트할 수 없다
   (`robo-data-analyzer/shared/neo4j/schema_constraints.py`, 2026-08-05). 같은 패턴을 쓴다.

경계가 성립하는 근거는 **Neo4j 라벨이 대소문자를 구분**한다는 것이다 — 분석기 `:TABLE` 과
카탈로그 `:Table`, domain-layer `:OntologyType` 과 studio `:_Entity` 는 서로 다른 라벨이다.

**주의해야 할 한 곳**: domain-layer 의 `:Table:ObjectType` 은 **카탈로그와 같은 `:Table` 라벨**을
쓰고 `db:'ontology'` 로만 구분한다. 라벨 소유권만으로는 갈리지 않으므로, 이 하나는
**라벨 + `db` 속성** 조합으로 소유를 판정한다. 헌법 원칙 II 가 요구하는 데이터소스 필터가
여기서도 방어선이다.

> 게이트 통과. Phase 2(`/speckit-tasks`)로 진행한다.

---

## Project Structure

### Documentation (this feature)

```text
specs/008-legacy-metadata-to-ontology/
├── spec.md              # 완료
├── plan.md              # 이 파일
├── research.md          # Phase 0
├── data-model.md        # Phase 1
├── quickstart.md        # Phase 1
├── contracts/
│   ├── name-mapping.md      # 정답지 파일 형식
│   ├── augmented-metadata.md # 증강 결과의 그래프 속성 계약
│   └── scoring-report.md     # 채점 하네스 출력 형식
├── checklists/
│   └── requirements.md  # 완료
└── tasks.md             # /speckit-tasks 산출물
```

### Source Code (repository root)

```text
scripts/
├── obfuscate_example.py        # 신규 — 매핑에서 난독화본 생성 (T1)
└── score_scenario.py           # 신규 — SC-001~005 자동 채점 (T3)

ontology-studio/
├── backend/src/modules/ontology/
│   ├── entity_matcher.py       # 수정 — 증강 신호·샘플값 형태 (T4)
│   ├── schema_ontology.py      # 수정 — 증강 속성 읽기 확장 (T4)
│   └── datafabric_client.py    # 수정 — 샘플 행 전달 (T4)
└── desktop/
    ├── resources/
    │   ├── backend/seed/postgres/       # 수정 — legacy 스키마 추가 (T2)
    │   ├── backend/compose.yml          # 수정 — domain-layer 추가 (T5)
    │   └── tutorial/
    │       ├── manufacturing/           # 유지 — 깨끗한 예제 (Q2-C)
    │       └── legacy/                  # 신규 — 난독화 예제 (T2)
    └── src/main/                        # 수정 — 예제 선택·게이트웨이 (T2/T5)

domain-layer/
├── app/services/data_source_linker.py   # 수정 — 이름 유사도 → 증강 신호 (T6)
├── app/services/schema_extractor.py     # 수정 — LAYER_PATTERNS 대체 (T6)
├── app/config.py / Dockerfile           # 수정 — 포트·DB 정리 (T5)
└── app/routers/ontology.py              # 점검 — SQL 렌더링(V-2), 객체화(T7)

.specify/memory/constitution.md          # 개정 — 쓰기 주체 경계 (T8)
docs/catalog-schema.md                   # 갱신 — domain-layer divergence (T5)
docs/manual/Ontologic-사용자-매뉴얼.md    # 개정 — 예제 선택·6/7/9장 (T9)
```

**Structure Decision**: 기존 서브모듈 구조를 그대로 쓴다. 새 서비스를 만들지 않는다 —
난독화 생성기와 채점 하네스만 루트 `scripts/` 에 추가한다. 두 스크립트가 루트에 있는 이유는
**여러 서브모듈에 걸쳐 있고 어느 하나에 속하지 않기** 때문이다(`scripts/inspect_catalog.py` 와
같은 위치·같은 성격).

---

## 단계 (독립 검증 가능 · 역순 되돌리기 가능)

각 단계는 **앞 단계 없이도 되돌릴 수 있다.** 되돌림이 어려운 것(샘플 DB 교체, 헌법 개정)은
뒤로 미뤘다.

| # | 단계 | 산출 | 독립 검증 | 되돌리기 |
|---|---|---|---|---|
| **T0** | 착수 전 실증 | 증거 문서 | 인제스천 후 `:DataSource` 보존 확인 | — (검증만) |
| **T1** | 난독화 생성 파이프라인 | `scripts/obfuscate_example.py` + 매핑 파일 + 생성물 | 생성된 DDL 로 DB 가 서고 행 수가 원본과 일치 | 생성물 삭제 |
| **T2** | 예제 번들 + 선택 UI | legacy 스키마·튜토리얼·기본 선택 | 설치본에서 두 예제가 모두 선택되고 서로 침범하지 않음 | 기본값을 manufacturing 으로 되돌림 |
| **T3** | 채점 하네스 + 기준선 | `scripts/score_scenario.py`, SC-001 실측 | 증강 전 자동 바인딩 **0건** 확인 | 스크립트 삭제 |
| **T4** | 증강 신호를 채점에 반영 | `entity_matcher` 확장 | SC-002 상승, SC-005 오바인딩 0건 | 가중치 원복(설정) |
| **T5** | domain-layer 편입 | compose·포트·DB·동시성·divergence 문서·메모리 실측 | 기존 7서비스 회귀 없음 + 메모리 증가분 기록 | compose 에서 제거 |
| **T6** | domain-layer 이름 매칭 교체 | linker·extractor 수정 | 난독화 예제에서 매뉴얼 9장 동작 | 원복 |
| **T7** | 객체화 경로 | 질의 → 객체 | US4 수용 시나리오 4개 | 엔드포인트 비노출 |
| **T8** | 헌법 개정 + 경계 강제 | 헌법 절 + 강제 수단 | 경계 위반 시 실패하는 검사 | 문서 되돌림 |
| **T9** | 매뉴얼 개정 + E2E 증거 | 매뉴얼·증거 디렉터리 | 시나리오 완주 영상/캡처 | — |

**T0 는 차단(blocking)이다.** FR-032·SC-007 이 분석기 수정에 의존하는데 그 수정이 아직
실증되지 않았다. 실증 없이 T1 로 넘어가면, 나중에 시나리오가 데이터를 지우는 것을 발견했을 때
T1~T4 의 채점 결과를 전부 신뢰할 수 없게 된다.

---

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|---|---|---|
| 온톨로지 쓰기 주체가 둘 (V-1) | 사용자 결정 Q1-B. 매뉴얼 6·7·9장 기능을 실제로 갖기 위함 | 대안 A(ontology-studio 확장)는 헌법을 지키지만 domain-layer 의 ObjectType·온톨로지 구성·데이터소스 매핑을 다시 만들어야 한다 — 그것이야말로 원칙 III 이 경고하는 두 벌 만들기다 |
| 예제가 둘 (Q2-C) | 매뉴얼 3·4·5장을 재현 가능하게 유지 | 전면 전환은 매뉴얼과 기존 증거를 한 번에 무효화한다. 별도 스키마만 추가하면 첫 실행에서 레거시를 만나지 못해 스펙 목적이 약해진다 |
| 난독화본을 생성물로 관리 | 매핑이 정답지가 되어야 자동 채점이 가능 | 난독화본 직접 커밋은 정답 대응이 사라져 SC-002~005 를 사람 눈으로만 볼 수 있다 |
| 채점 하네스 신설 | SC-001~005 가 "측정 가능"해야 스펙이 성립 | 수동 확인은 재현되지 않고, 증강이 LLM 의존이라 반복 실행 통계가 필요하다 |
