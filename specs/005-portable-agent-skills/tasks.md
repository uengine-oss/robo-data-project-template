# Tasks: 이식 가능한 에이전트 스킬 패키지

**Feature**: [spec.md](spec.md) | **Plan**: [plan.md](plan.md) | **Date**: 2026-08-02

**작업 루트**: `ontology-studio/` (서브모듈). 경로는 그 기준의 상대 경로다.

**테스트 포함**: 스펙의 SC 가 대부분 "무엇이 성립하는가" 를 요구하고, constitution 원칙 VII 이
실행 검증을 요구하므로 테스트 태스크를 포함한다.

---

## Phase 1: Setup

- [x] T001 `ontology-studio/skills/` 디렉터리를 만들고 `.gitignore` 가 이를 제외하지 않는지 확인
- [x] T002 기존 `ontology-studio/backend/skills/README.md`(빈 자리표시자)를 제거하고, 참조하는 코드가
      없는지 `grep -rn "backend/skills"` 로 확인

---

## Phase 2: Foundational (모든 스토리의 선행 조건)

레지스트리가 없으면 어느 스토리도 시작할 수 없다.

- [x] T003 `backend/src/modules/agent_session/skill_registry.py` 에 `SkillPackage` 데이터클래스와
      `SkillLoadError` 정의 — 필드는 [skill-registry.md](contracts/skill-registry.md) 표면 그대로
- [x] T004 `skill_registry.py` 에 프론트매터 파서 구현 — `---` 구분, PyYAML 로 파싱, 본문에서
      프론트매터 제거 (계약 C3)
- [x] T005 `skill_registry.py` 에 검증 규칙 V1~V7 구현 — 실패 시 **폴더를 지목하는**
      `SkillLoadError` ([skill-package.md](contracts/skill-package.md) 검증 규칙 표)
- [x] T006 `skill_registry.py` 에 `list_skills()` / `load_skill(name)` 구현 — 폴더 스캔, 이름
      하드코딩 금지 (C1), `files` 에서 `.claude-plugin/`·`.mcp.json` 제외 (C5)
- [x] T007 `skill_registry.py` 에 `environment_binding_block()` 구현 — 값만 담고 설명 문장 금지
- [x] T008 [P] `backend/tests/modules/agent_session/test_skill_registry.py` 작성 — T1~T5
      ([skill-registry.md](contracts/skill-registry.md) 테스트 표)
- [x] T009 [P] `test_skill_registry.py` 에 langchain 비의존 서브프로세스 테스트 추가 (T4 / SC-004)

---

## Phase 3: User Story 1 — 스튜디오 화면 없이 스킬만으로 쓴다 (P1)

**목표**: 스킬 폴더 하나만 복사해도 동작하는 자립 패키지를 만든다.

**독립 검증**: 스튜디오 프론트엔드를 띄우지 않고 스킬만 설치한 Claude Code 에서 질의·구축이 된다.

### 스킬 본문 재배치 (내용 이동, FR-043)

- [x] T010 [US1] `skills/ontology-build/SKILL.md` 생성 — 프론트매터(name/description/version/
      compatibility) + 본문 필수 7절. 현재
      `backend/src/modules/agent_session/skills/ontology_build.md` 의 역할·워크플로우 골격만 남긴다
- [x] T011 [P] [US1] `skills/ontology-build/references/ingestion-patterns.md` — 패턴 A~D, D-1 을
      **그대로 옮긴다**
- [x] T012 [P] [US1] `skills/ontology-build/references/strategies.md` — 전략 선택표,
      `build_strategy_recommend`, 역바인딩, 인과발견
- [x] T013 [P] [US1] `skills/ontology-build/references/datasource-binding.md` — 바인딩 절차,
      behavior 작성, SQL 템플릿 규칙, 파라미터 타입
- [x] T014 [P] [US1] `skills/ontology-build/references/parser-rules.md` — content 2-pass 수집,
      노드 속성 규칙, 구조 파싱, 파서 자체 검증
- [x] T015 [P] [US1] `skills/ontology-build/references/source-types.md` — PDF/Excel/Shapefile/
      Markdown/PPTX 파싱 가이드
- [x] T016 [P] [US1] `skills/ontology-build/references/validation.md` — Phase 3 검증, 검색 힌트
      파일, 최종 리포트 형식(`ontology_build_report`)
- [x] T017 [US1] `skills/ontology-answer/SKILL.md` + `references/search-strategy.md` 생성 —
      `ontology_answer.md` 를 같은 방식으로 분할
- [x] T018 [US1] 두 SKILL.md 에 **전제** 절 작성 — 필요한 도구와 출처(agent-bridge MCP), 없을 때
      멈추고 안내 (FR-004, SC-008)
- [x] T019 [US1] 두 SKILL.md 에 **권한 경계** 절 작성 — answer 는 읽기 전용임을 본문·
      `allowed-tools` 양쪽에 (FR-006, 불변식 4)
- [x] T020 [US1] 두 SKILL.md 에 **작업 경로** 절 작성 — 환경 무관 서술 + 환경 바인딩이 없을 때
      정하는 법 (FR-005, FR-003)
- [x] T021 [US1] 본문에서 각 참조 자료의 **읽을 시점**을 지목 (FR-041)

### 이동 검증

- [x] T022 [US1] `backend/tests/modules/agent_session/test_skill_content_migration.py` — 이동 전
      원본의 핵심 문장이 이동 후 어딘가에 **모두 존재**하는지 (SC-010, FR-043)
- [x] T023 [US1] 중복 사본 0건 확인 테스트 — 같은 지시문 문장이 저장소에 두 번 나타나지 않는다
      (SC-003)

---

## Phase 4: User Story 2 — 부족한 입력을 스킬이 스스로 묻는다 (P1)

**목표**: 폼이 없는 환경에서 스킬이 자기 입력을 확보한다. 폼이 있으면 확인만 한다.

**독립 검증**: 맥락 없는 요청은 묻고, 완비된 요청은 되묻기 0회로 진행한다.

- [x] T024 [US2] `skills/ontology-build/SKILL.md` 에 **입력** 절 작성 —
      [input-contract.md](contracts/input-contract.md) 의 라벨 표와 인터뷰 절차·금지 사항
- [x] T025 [US2] 같은 절에 **완료 기준** 이관 — `_compose_build_prompt` 의 `[완료 기준]` 블록 전문
- [x] T026 [US2] `service.py` 의 `_compose_build_prompt` 를 **값 전달로 축소** — 설명 문장과
      `[완료 기준]` 제거, `[골든 퀘스천]` 라벨로 통일
- [x] T027 [US2] `service.py` 의 `_build_continuation_prompt`(재개 프롬프트)에서도 같은 지시문
      문장을 제거 — 같은 위반이 두 함수에 있다
- [x] T028 [US2] `backend/tests/modules/agent_session/test_input_contract.py` — 값만 남았는지,
      지시문 문장이 사라졌는지 단언
- [x] T029 [US2] `test_prompt_composition.py` 갱신 — 기존 단언 중 제거된 문장을 기대하는 것 수정

---

## Phase 5: User Story 3 — 두 백엔드가 같은 스킬을 읽는다 (P1)

**목표**: 레지스트리를 유일한 진입점으로 만들고 두 경로를 거기에 붙인다.

**독립 검증**: 본문에 표식을 넣으면 양쪽 시스템 프롬프트에 모두 나타난다.

### 동기화 (참조 자료 도달성)

- [x] T030 [US3] `backend/src/modules/agent_session/skill_sync.py` — `sync_to_sandbox(pkg, backend)`
      구현. `<workdir>/.skills/<name>/` 에 멱등 복사, `uploads/`·`output/` 불가침
- [x] T031 [P] [US3] `backend/tests/modules/agent_session/test_skill_sync.py` — 멱등성,
      참조 자료 도달성(T6), 워크스페이스 불가침

### 내장 경로

- [x] T032 [US3] `service.py` 의 `load_skill` / `ONTOLOGY_*_SYSTEM_PROMPT` 를 레지스트리 기반으로
      교체 — `pkg.body` + `environment_binding_block()`
- [x] T033 [US3] `_create_build_agent` / `_create_answer_agent` 에서 스킬 동기화를 세션 준비
      시점에 호출하도록 배선
- [x] T034 [US3] `backend/src/modules/agent_session/skills/` 의 두 `.md` 삭제 (원천 이동 완료)

### cliagents 경로

- [x] T035 [US3] cliagents 서브모듈: `artifacts.py` 의 `Artifact` 에 보조 파일 필드 추가
      (`files: dict[str, str]`), `add_skill` 이 이를 받도록
- [x] T036 [US3] cliagents 서브모듈: `provider.py` 의 emit 이 보조 파일을 스킬 폴더 기준으로 배치
- [x] T037 [US3] cliagents 서브모듈: `providers/claude_code.py` 의 `skill_path` 를
      `.claude/skills/{name}/SKILL.md` 로 수정 (R4 — 현재 플랫 파일은 인식되지 않는다)
- [x] T038 [US3] `cliagents_backend.py` 가 `service.load_skill` 대신 `skill_registry` 를 쓰도록
      변경 — service 의존 제거 (R9)
- [x] T039 [US3] `cliagents_backend.py` 의 `_host_workspace_note()` 를 `environment_binding_block()`
      로 교체하고 삭제 (이중 소스 제거)
- [x] T040 [US3] `_prepare()` 가 폴더 전체(참조 자료 포함)를 emit 하도록 수정
- [x] T041 [US3] `test_cliagents_backend.py` 갱신 — 폴더 emit, 참조 자료 동봉, service 비의존

### 단일 소스 검증

- [x] T042 [US3] 두 백엔드가 같은 `body` 를 얻는지 확인하는 테스트 (T5, US3-1)

---

## Phase 6: User Story 4 — 스킬을 하나 더 추가한다 (P2)

**목표**: 폴더 추가만으로 스킬이 늘어난다.

- [x] T043 [US4] 임시 스킬 폴더를 만들고 `list_skills()` 에 나타나는지, 코드 변경이 0줄인지
      확인하는 테스트 (SC-006)
- [x] T044 [US4] 형식 위반 폴더(프론트매터 없음 / 이름 불일치 / description 초과)가 각각
      **폴더를 지목한** 오류를 내는지 테스트 (FR-014)

---

## Phase 7: User Story 5 — 설치본을 최신으로 갱신한다 (P3) + 배포

**목표**: Claude Code UI 설치 경로와 폴더 복사 경로를 모두 연다.

- [x] T045 [P] [US5] `skills/ontology-build/.claude-plugin/plugin.json` 작성
      ([distribution.md](contracts/distribution.md) 스키마)
- [x] T046 [P] [US5] `skills/ontology-answer/.claude-plugin/plugin.json` 작성
- [x] T047 [P] [US5] `skills/ontology-build/.mcp.json` — `agent-bridge/build/`,
      `${ONTOLOGY_STUDIO_URL:-http://127.0.0.1:8000}`
- [x] T048 [P] [US5] `skills/ontology-answer/.mcp.json` — `agent-bridge/answer/`
- [x] T049 [US5] `ontology-studio/.claude-plugin/marketplace.json` 작성 — 두 플러그인 등재
- [x] T050 [US5] `ontology-studio/skills/README.md` 작성 — 설치 절차, MCP 연결, 갱신·제거,
      백엔드 전제 명시 (FR-021, FR-022)
- [x] T051 [US5] `backend/tests/modules/agent_session/test_distribution.py` — D1~D5
      (버전 3곳 일치, source 실재, 모드별 엔드포인트, 자격증명 부재, 무가공)

---

## Phase 8: Polish & 실행 검증

constitution 원칙 VII — 단위 테스트 통과를 "동작한다" 로 보고하지 않는다.

- [x] T052 전체 백엔드 테스트 실행 — 회귀 0 (SC-004)
- [x] T053 스킬을 **서브에이전트로 직접 기동**해 구축 스킬을 검증 — 맥락 없는 요청에 인터뷰가
      발동하는지 (SC-012), 완비된 요청에 되묻기 0회인지 (SC-013)
- [x] T054 서브에이전트로 질의 스킬 검증 — 참조 자료를 실제로 읽는지 (SC-009), 도구 없을 때
      멈추는지 (SC-008)
- [x] T055 `installation.md` / `ontology-studio/CLAUDE.md` 에 스킬 위치 변경 반영
- [x] T056 실서비스 E2E — 백엔드(8000) · data-fabric(8004) · text2sql(8020) · Neo4j 기동 상태에서
      질의·구축을 실제 실행 (SC-001, SC-002)
- [x] T057 **히스토리 압축 결함 수정** — 실행 검증에서 발견. `compress_messages` 가 사용자 메시지를
      포함해 히스토리를 통째로 버려 인터뷰가 오작동했다. `history_compression.py` + 회귀 테스트
- [x] T058 **히스토리 예산 상향** — 참조 자료 분할이 지시문을 시스템 프롬프트(무과금)에서
      히스토리(과금·축출 대상)로 옮긴 결과, 12k 예산이 빌드를 망가뜨렸다. 48k 로 올리고
      `AGENT_HISTORY_MAX_TOKENS` 로 재정의 가능하게 했다

---

## 실행 검증 결과 (2026-08-02)

`/tmp/skilltest/.claude/skills/` 에 폴더를 복사해 설치한 상태에서 서브에이전트로 기동했다.

| 확인 | 결과 | 근거 |
|---|---|---|
| SC-008 도구 없이 멈춤 | ✅ | 질의 스킬이 수치를 지어내지 않고 백엔드·MCP 서버명·연결법을 안내하고 중단 |
| SC-012 맥락 없으면 인터뷰 | ✅ | 의도·골든 퀘스천·소스 3개만 묻고 턴 종료. 임의 생성 0건 |
| SC-013 완비되면 되묻기 0회 | ✅ | `asked_user_a_question: false`, 요약 후 바로 설계 |
| SC-009 참조 자료 실제 읽음 | ✅ | 5개 읽음. `parser-rules.md` 를 **파서 작성 전에** 읽음 |
| SC-015 골든 퀘스천 원문 유지 | ✅ | 리포트의 `question` 이 입력과 글자 그대로 일치 |
| 파서 규칙 준수 | ✅ | 실제 실행: 15노드/17관계, content 100%, dangling 0 (독립 재검증) |
| 리포트 형식 | ✅ | `ontology_build_report` 블록 산출 |

### 실서비스 검증 (T056)

Neo4j Desktop + data-fabric(8004) + text2sql(8020) 이 떠 있는 상태에서 ontology-studio 백엔드를
`SANDBOX_BACKEND=local` 로 8000 에 기동해 확인했다.

| 확인 | 결과 | 근거 |
|---|---|---|
| SC-001 단독 설치 질의 | ✅ | `~/.claude/skills` 에 폴더 복사 후 `claude -p` → **351일**, 데이터소스·테이블·행 수 제시 |
| SC-002 스튜디오 내장 경로 질의 | ✅ | 같은 질문에 **351일**. `behavior_invoke` → `설비가동.by_equipment` |
| 세 경로 값 일치 | ✅ | 004 내장 경로 / 단독 CLI / 새 내장 경로가 모두 351일 |
| 스킬 동기화 | ✅ | `.cache/sandbox/.skills/{ontology-build,ontology-answer}/` 에 참조 자료까지 배치 |
| SC-009 내장 경로 참조 읽기 | ✅ | 에이전트가 `/workspace/.skills/ontology-build/references/` 를 **5개 실제로 읽음** |
| SC-012 스튜디오 인터뷰 | ✅ | 폼이 빈 상태의 구축 요청 → 도구 호출 0회, 3항목만 묻고 턴 종료 |
| MCP 엔드포인트 | ✅ | `/mcp/agent-bridge/answer/` initialize + `behavior_list` 왕복 성공 |

### 실행에서만 드러난 결함 1건 (T057)

**증상**: 입력이 완비된 구축 요청인데도 에이전트가 의도·골든 퀘스천·소스를 다시 물었다
(SC-013 / FR-051 위반).

**원인**: 스킬이 아니라 `history_compression.py` 였다. 로그에 `History compressed: 13 → 0
messages`. 참조 자료 5개를 읽으면서 히스토리가 예산을 넘자 앞에서부터 버렸고, **사용자 메시지까지
사라졌다.** 에이전트는 다시 물은 것이 아니라 **받은 적이 없는 상태**가 된 것이다.

두 가지가 겹쳤다:

1. 루프 가드 `len(compressed) > 1` 이 pop **이후**의 고아 ToolMessage 정리를 막지 못해 0개까지 갔다.
   docstring 은 "Never drop the very last HumanMessage" 라고 적혀 있었지만 코드에 그 로직이 없었다.
2. HumanMessage 를 다른 메시지와 동등하게 취급했다. 사용자 메시지는 미션(의도·골든 퀘스천·대상
   파일)을 담고 도구 결과에 비해 작은데, 그것을 버려 자기 결과를 남기는 교환이 일어났다.

**수정**: HumanMessage 는 드롭 대상에서 제외하고, 머리에 남은 고아 ToolMessage 를 정리하며,
빈 리스트를 반환하지 않는다. 회귀 테스트 3개를 추가했다.

이 결함은 004 가 Out of Scope 로 남긴 "`_compress_history` 가 앞에서부터 버려 인텐트를 잊는 문제"
와 같은 뿌리다. 인터뷰가 대화에 남은 것을 근거로 판정하므로, 이 스펙에서는 더 이상 미룰 수 없었다.

### 이 기능이 만든 회귀 1건 (T058)

수정 후 다시 돌리자 되묻기는 사라졌지만 빌드가 **자기가 한 일을 잊고 반복**했다 — 4개 조문짜리
문서에 `sandbox_read` 122회, `schema_create_class` 39회, `schema_group_create` 9회, 압축 98회
(한 번은 17→1).

**원인은 이 기능이 만들었다.** 참조 자료 분할이 지시문 세부를 **시스템 프롬프트에서 히스토리로**
옮겼다. 전에는 본문 전체가 시스템 메시지에 실려 예산에 잡히지 않았는데, 이제는 에이전트가
`references/*.md` 를 읽어 그 내용이 대화 히스토리에 쌓이고 축출 대상이 된다. 12,000 토큰 예산은
32K 컨텍스트 모델 시절 값이고(현재 `gpt-4.1`, 1M), 그 압박을 견디지 못했다.

**수정**: 기본 예산을 48,000 토큰으로 올리고 `AGENT_HISTORY_MAX_TOKENS` 로 재정의 가능하게 했다.

같은 문서·같은 요청으로 전후 실측:

| | 수정 전 (12k) | 수정 후 (48k) |
|---|---|---|
| 압축 발생 | 98회 (한 번은 17→1) | **0회** |
| `schema_create_class` | 39 | **7** |
| `schema_group_create` | 9 | **1** |
| `sandbox_read` | 122 | **11** |
| 생성된 클래스 | 18개 (중복: EquipmentType/FacilityType, InspectionRule/PeriodicInspectionRule …) | **7개, 중복 없음** |
| 참조 자료 읽기 | 반복 | 5개 각 1회 (`validation.md` 만 3회) |

적재 결과를 그래프에서 독립 검증: RegulationArticle 4 · MaintenanceConcept 3 ·
EquipmentType 2 · InspectionRule 2 · Role 2 · ProcedureStep 2 · RegulationDocument 1 —
원문(조문 4개, 정의 3개, 설비유형 2종)과 정확히 대응한다. 구축 후 질의 모드로 골든 퀘스천을
물어 근거 노드와 함께 답이 나오는 것까지 확인했다.

검증 데이터는 **클래스를 먼저 지우고** 그룹을 지워 정리했고(constitution IV),
`scripts/inspect_catalog.py` 로 카탈로그 계약이 그대로임을 확인했다 (확인 13 · 어긋남 0).

**교훈**: 점진적 공개는 공짜가 아니다. 시스템 프롬프트에서 파일로 내리면 컨텍스트 비용이
"항상 있지만 안 세는 것" 에서 "필요할 때만 읽지만 세고 버려지는 것" 으로 바뀐다. 스펙의
FR-042(양쪽 경로가 참조 자료를 읽을 수 있어야 한다)는 읽기 **가능성**만 요구했지, 읽은 것이
**남아 있을 것**은 요구하지 않았다.

---

## 의존 그래프

```
Setup(T001-002)
   └─> Foundational(T003-009)  ← 레지스트리. 모든 스토리의 선행
          ├─> US1(T010-023)  스킬 폴더 — 이것이 없으면 나머지가 읽을 것이 없다
          │      ├─> US2(T024-029)  입력 계약 (SKILL.md 를 고침)
          │      ├─> US3(T030-042)  두 백엔드 배선 (레지스트리 + 폴더 필요)
          │      └─> US5(T045-051)  배포 포장 (폴더 필요)
          └─> US4(T043-044)  폴더 스캔 검증 (레지스트리만 필요)
                 └─> Polish(T052-056)
```

**US1 이 진짜 MVP다.** 스킬 폴더가 자립하면 US5(배포) 없이도 사용자가 `cp -r` 로 쓸 수 있다.

## 병렬 기회

| 묶음 | 태스크 | 이유 |
|---|---|---|
| 참조 자료 분할 | T011~T016 | 서로 다른 파일. 내용 이동이라 충돌 없음 |
| 테스트 작성 | T008, T009, T031 | 서로 다른 테스트 파일 |
| 배포 산출물 | T045~T048 | 서로 다른 JSON 파일 |

## 구현 전략

1. **Foundational + US1** 까지가 첫 증분 — 이 시점에 폴더 복사로 쓸 수 있다
2. **US3** 이 회귀 위험이 가장 크다. 두 백엔드를 옮기는 작업이므로 여기서 테스트를 조인다
3. **US2** 는 SKILL.md 문장 작업이 대부분이고 코드 변경은 `_compose_build_prompt` 축소뿐이다
4. **US5** 는 산출물 작성이라 마지막에 몰아도 된다
