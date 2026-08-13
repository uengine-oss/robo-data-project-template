# Tasks: 교체 가능한 에이전트 백엔드

**Spec**: [spec.md](./spec.md) · **Plan**: [plan.md](./plan.md)

전부 완료. 순서는 실제 구현 순서이고, 검증 칸은 그 작업이 무엇으로 고정됐는지를 가리킨다.

## Phase 1 — 기반

- [x] **T001** `cliagents` 서브모듈 등록 (`ontology-studio/cliagents`)
      · 검증: `uv sync` 로 editable 설치 확인
- [x] **T002** `pyproject.toml` — `cliagents>=0.1.0` + `[tool.uv.sources]` editable
- [x] **T003** `pyproject.toml` — `[tool.setuptools.package-data]` 에 `skills/*.md`
      · 콘솔 스크립트로 설치되는 패키지라 마크다운이 휠에 포함돼야 한다
- [x] **T004** `settings.py` — `agent_backend`(기본 `deepagents`), `external_agent_id`(기본
      `claude-code`) · `.env.example` 문서화

## Phase 2 — 프롬프트 단일 소스 (FR-020, FR-021)

- [x] **T010** `service.py` 인라인 프롬프트 2개를 `skills/ontology_build.md`,
      `skills/ontology_answer.md` 로 이관 (내용 그대로)
- [x] **T011** `load_skill()` 로더 추가, 상수는 그 결과를 담도록 변경 (호출부 무수정)
- [x] **T012** build 프롬프트 선두의 잔여 백슬래시 제거
      · raw string `r"""\` 이라 줄이음이 적용되지 않아 리터럴로 남아 있었다
      · 검증: 이관 전후 문자열 길이·선두·말미 대조

## Phase 3 — MCP 브리지 (FR-010 ~ FR-013)

- [x] **T020** `agent_bridge_mcp/server.py` — `_BUILD_MODE_TOOLS`/`_ANSWER_MODE_TOOLS` 를
      `mcp.add_tool()` 로 등록. 모드별 서버
- [x] **T021** `agent_bridge_mcp/router.py` — `/mcp/agent-bridge/{mode}` 마운트 + lifespan
      · FastAPI 는 마운트 서브앱의 lifespan 을 전파하지 않는다
- [x] **T022** `host/app.py` — `mount()` 호출 + lifespan 체이닝
- [x] **T023** 테스트: 도구 **객체 동일성**, answer 모드에 쓰기 도구 부재, 서버 등록 도구 일치
      · `tests/modules/agent_bridge_mcp/test_agent_bridge_mcp.py`

## Phase 4 — 어댑터 (FR-001 ~ FR-004, FR-030)

- [x] **T030** `cliagents_backend.py` — `CliAgentAdapter` (`stream`/`invoke`/`get_state`)
- [x] **T031** `_RUNNERS` — claude-code / codex 헤드리스 실행
- [x] **T032** LangChain 없는 반환 타입 (`_Message`, `_State`) — 소비자 덕타이핑에 맞춤
- [x] **T033** `service.py` — `get_agent()` 분기 (`_create_*` 는 무수정)
- [x] **T034** `generate_sse` — `"cli"` 이벤트 분기 추가
- [x] **T035** 테스트: 서브프로세스에서 langchain 계열 **0개** 적재 강제
- [x] **T036** 네 가지 argv 형태를 **실제 CLI 파서로** 검증
      · 이 과정에서 `codex exec` 가 `--ask-for-approval` 을 거부, `resume` 는 `--cd`/`--sandbox`
        를 안 받는 것을 발견 → `-c` 오버라이드로 통일

## Phase 5 — 호스트 파일시스템 (FR-040 ~ FR-042)

- [x] **T040** 작업 디렉터리를 스크래치에서 `LOCAL_SANDBOX_ROOT` 로 변경
- [x] **T041** 도구 allow-list 제거 — CLI 자체 Read/Write/Bash 허용
- [x] **T042** `_host_workspace_note()` — `/workspace` → 실제 경로 매핑을 프롬프트에 명시
- [x] **T043** UI 보고 필터를 "내부 기록만 숨김"으로 변경 (`ToolSearch`, `TodoWrite`)
      · 검증: `/workspace` 실패 7회 → 0회

## Phase 6 — Human in the loop (FR-050 ~ FR-055)

- [x] **T050** `--input-format stream-json` 으로 전환, stdin 을 열어 둔 채 프롬프트를 스트리밍
- [x] **T051** 스티어링 큐 + `steer()` / `is_running()` / `forget_session()`
- [x] **T052** `POST /api/agent/steer`, `GET /api/agent/running`
- [x] **T053** **인터럽트 제어 메시지**를 스티어링 직전에 전송
      · 이것 없이는 에이전트가 취소당한 작업을 완주한 뒤에야 새 지시를 읽는다 (68.1초 → 24.8초)
- [x] **T054** `outstanding` 카운터 — 밀어넣은 수만큼 result 를 기다린 뒤 stdin 종료
- [x] **T055** `_STEERABLE` 게이트 — Codex 는 조용히 삼키지 않고 거부
- [x] **T056** `clear_session()` → `forget_session()` 연결
- [x] **T057** `ask_user` 이벤트 배선 (AskUserQuestion)
      · 실측: 두 CLI 모두 헤드리스에서 이 도구를 제공하지 않아 현재 발화하지 않음
- [x] **T058** 프론트엔드 — 실행 중 입력창 활성, 조타 버튼, "작업 중 지시" 표시, 질문 선택지 UI

## Phase 7 — 검증

- [x] **T060** 기존 백엔드 테스트 회귀 없음 (417 passed)
- [x] **T061** 질문 응답 동치 — claude-code / codex / deepagents 모두 **351일**
- [x] **T062** 문서 빌드 완주 — claude-code 2,493 노드 · codex 1,559 노드
- [x] **T063** UI 경로 스티어링 E2E (`tests/e2e_hitl_steering.spec.js`)
- [x] **T064** 문서 빌드 비교 스펙 (`tests/e2e_doc_build_compare.spec.js`)
      · `/api/neo4j/clear-all` 미사용 (constitution IV)

## Phase 8 — 데모 영상

- [x] **T070** 문서 빌드 데모 (Claude Code) — `document-build-cliagents.mp4`
- [x] **T071** 실행 중 개입 데모 — `hitl-steering-cliagents.mp4` (OpenAI TTS nova)
- [x] **T072** 문서 빌드 데모 (Codex) — `document-build-codex.mp4` (OpenAI TTS nova)
- [x] **T073** 좁은 초기화 스크립트 `demo/prep_state_narrow.py`
      · 문서화된 `prep_state.py` 는 데모 외 스키마 그룹을 전부 지운다

## 영상 제작 중 발견해 고친 결함

영상이 아니었으면 못 잡았을 것들. 수치만 봤다면 전부 정상으로 보였다.

- [x] **D001** 스티어링 응답이 UI 에서 소실
      · SSE 핸들러가 `messages[length-1]` 을 스트리밍 대상으로 삼는데 사용자 메시지를 뒤에 붙임
      · **처음엔 테스트가 거짓 통과했다** — 단언이 "길이 < 1500자" 여서 스티어링 이전 메시지도 통과
      · 단언을 "실제 클래스 목록 포함" 으로 강화 후 드러남
- [x] **D002** Codex 10분 이상 멈춤 — `stdin=PIPE` 를 열어 두면 입력 대기
- [x] **D003** Codex MCP 도구 전부 취소 — `approval_policy="never"` 로도 승인 대기
      · `--dangerously-bypass-approvals-and-sandbox` 필요
- [x] **D004** Codex 이벤트 스키마 구버전 — 현행은 `item.started`/`item.completed`
- [x] **D005** 세션 초기화 후에도 "이미 완료된 요청" — `forget_session()` 누락
- [x] **D006** 문서 빌드 노드 수 누적 — 그룹 삭제가 엔티티를 남김 (클래스 먼저 삭제로 수정)

## 하지 않은 것

- 내장 경로의 `_compress_history` 개선. 앞에서부터 버려 긴 빌드에서 인텐트를 잊는 현상이
  관측됐지만 이 스펙의 범위가 아니다.
- 두 백엔드의 품질 비교. 관측된 차이는 대부분 모델 차이다.
- Codex 의 실행 중 스티어링. 헤드리스 입력 경로가 없다.
