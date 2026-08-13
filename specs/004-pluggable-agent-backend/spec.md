# Feature Specification: 교체 가능한 에이전트 백엔드 (내장 / 외부 CLI)

**Feature Branch**: `004-pluggable-agent-backend`

**Created**: 2026-08-01

**Status**: Implemented — 스티어링·문서 빌드까지 두 CLI(claude-code, codex)로 실서비스 검증 완료.
AskUserQuestion 은 배선만 존재하고 현재 어느 CLI 도 헤드리스에서 발화하지 않음.

**Input**: User description: "cliagents 를 submodule 로 등록하고, 이걸 기반으로 현재의 langchain
deepagents 를 이용하여 동작하는 구조를 skill file + 외부 에이전트 호출 방식으로 전환한다. 기존의
langchain deepagent 를 그대로 사용하던 방식도 유지하면서 strategy pattern 으로 동작하도록 한다.
외부 에이전트가 ontology studio 의 기능을 호출하도록 하는방법은 mcp 를 제공하는 방식을 사용해야
한다." + 후속: "가능한 기존 tool 들을 그대로 MCP 호출하도록 하여야 한다. 로직을 중복해서 구현해서는
안된다. 기존 langchain deepagents 에 적용된 프롬프트들은 스킬로 다 이동해야 한다. 외부 에이전트
만으로도 할 수 있어야 하므로, 독립적으로 완전히 동작할 수 있어야 한다." + 후속: "cliagent 를
사용할때는 sandbox 는 신경쓰지 않아도 돼. 호스트의 filesystem 을 사용할것이니까." + 후속: "HITL 가
벌어지는 상황에서 UI를 통한 인터랙션, 실행 도중 steering, 완료 후 피드백 등을 주었을때 해당 claude
code 세션에 이어서 요청이 가능한지?"

## 관계

이 스펙은 **온톨로지를 누가 만드는가**를 갈라 놓는다. 무엇을 만드는지는 바뀌지 않는다 —
[001](../001-datasource-backed-virtual-classes/spec.md) 의 가상 클래스,
[002](../002-catalog-driven-ontology/spec.md) 의 결정적 생성,
[003](../003-ontology-build-strategies/spec.md) 의 전략 선택은 그대로이고, 그 도구들을 **누가
호출하느냐**만 교체 가능해진다.

루트에 두는 이유는 판단 기준 그대로다 — 되돌리면 계약이 깨지는 것이 셋 있다:

- 루트 `.env` 의 새 키 `AGENT_BACKEND` / `EXTERNAL_AGENT_ID`
- ontology-studio 백엔드가 새로 노출하는 MCP 엔드포인트 `/mcp/agent-bridge/{mode}`
- 새 서브모듈 `ontology-studio/cliagents` (별도 저장소)

## 배경 — 왜 교체 가능해야 하는가

지금 에이전트는 백엔드 프로세스 안의 LangChain 그래프다. 모델 호출 비용이 `OPENAI_API_KEY` 로
나가고, 컨텍스트 관리는 `HistoryCompressionMiddleware` 가 한다.

사용자는 이미 Claude Code / Codex 구독을 갖고 있다. 그 CLI 들은 자기 모델·자기 컨텍스트 관리·자기
파일 도구를 들고 온다. 이들을 스튜디오의 에이전트로 쓸 수 있으면 API 키 없이도 스튜디오가 돈다.

바꾸지 말아야 할 것도 분명하다. 기존 경로는 **그대로 남는다**. 두 경로가 같은 도구·같은 프롬프트를
쓰지 않으면 갈라져서, 한쪽에서 고친 것이 다른 쪽에 반영되지 않는다.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - API 키 없이 스튜디오를 쓴다 (Priority: P1)

Claude Code 구독은 있지만 OpenAI API 키가 없는 사용자가, 환경변수 하나만 바꿔 스튜디오의 온톨로지
구축·질의를 그대로 쓴다.

**Why this priority**: 이 스펙의 존재 이유. 이것이 안 되면 나머지는 의미가 없다.

**Acceptance Scenarios**:

1. **Given** `AGENT_BACKEND=cliagents`, `EXTERNAL_AGENT_ID=claude-code`, **When** 질문 응답 모드에서
   "EQ-CNC-001 설비의 가동 일수를 알려줘" 를 묻는다, **Then** 내장 에이전트와 **같은 답(351일)** 이
   나오고, 근거로 데이터소스·테이블·행 수를 제시한다.
2. **Given** 같은 설정, **When** 도로교통법 PDF + 인텐트 + 골든 퀘스천 3개로 구축을 시작한다,
   **Then** 에이전트가 스키마를 설계하고 파서를 작성·실행해 그래프에 적재하고, 골든 퀘스천을 실제
   Cypher 로 검증한 리포트를 낸다.
3. **Given** `EXTERNAL_AGENT_ID=codex`, **When** 같은 두 시나리오를 돌린다, **Then** 같은 결과에
   도달한다 (도구 선택 순서는 다를 수 있다).

### User Story 2 - 기존 방식이 그대로 남는다 (Priority: P1)

`AGENT_BACKEND` 를 건드리지 않은 사용자는 아무것도 달라지지 않는다.

**Why this priority**: 회귀는 새 기능보다 비싸다.

**Acceptance Scenarios**:

1. **Given** `AGENT_BACKEND` 미설정, **When** 기존 백엔드 테스트 전체를 돌린다, **Then** 전부
   통과한다.
2. **Given** 미설정 상태, **When** 채팅·구축·MCP 검색을 쓴다, **Then** 이전과 동일하게 동작한다.

### User Story 3 - 작업 중에 방향을 바꾼다 (Priority: P1)

에이전트가 엉뚱한 방향으로 가고 있을 때, 중단하고 처음부터 다시 시키는 것 말고 **지금 하는 일을
고쳐 잡을** 방법이 있어야 한다.

**Why this priority**: 긴 구축 작업에서 중단은 그때까지의 작업을 버린다는 뜻이다.

**Acceptance Scenarios**:

1. **Given** 에이전트가 작업 중, **When** 입력창에 지시를 쓴다, **Then** 입력창이 잠겨 있지 않고
   보내기 버튼이 조타 버튼으로 바뀌어 있다.
2. **Given** 작업 중 지시를 보낸다, **When** 전달된다, **Then** "작업 중 지시" 표시가 붙은 사용자
   메시지가 대화에 남고, 에이전트가 **몇 초 안에** 방향을 바꾼다 (새 턴이 아니라 같은 턴).
3. **Given** `EXTERNAL_AGENT_ID=codex`, **When** 작업 중 지시를 보낸다, **Then** 조용히 삼키지 않고
   **거부**한다 (`delivered: false`).

### User Story 4 - 완료 후 피드백이 이어진다 (Priority: P2)

구축이 끝난 뒤 "이 부분이 틀렸다" 고 하면, 에이전트가 앞선 작업을 기억한 채로 답한다.

**Acceptance Scenarios**:

1. **Given** 한 세션에서 구축을 마쳤다, **When** 후속 메시지를 보낸다, **Then** 같은 CLI 세션이
   재개되어(`--resume`) 이전 맥락 위에서 답한다.
2. **Given** 세션을 초기화했다, **When** 다시 요청한다, **Then** CLI 대화도 함께 초기화되어 "이미
   완료된 요청" 이라고 답하지 않는다.

### Edge Cases

- **CLI 미설치**: 조용히 다른 에이전트로 대체하지 않는다. 설치 힌트를 담은 오류를 낸다.
- **헤드리스로 구동할 수 없는 에이전트**(예: Cursor): `EXTERNAL_AGENT_ID` 로 지정하면 기동 시
  거부한다.
- **백엔드 재시작 후 후속 턴**: 우리가 정한 세션 ID 를 재사용하면 CLI 가 거부하므로, 세션 ID 는
  턴마다 CLI 가 보고한 것을 저장해 쓴다.
- **`BACKEND_HOST=0.0.0.0`**: 바인드 주소이지 접속 주소가 아니므로 MCP URL 에는 `127.0.0.1` 을 쓴다.

## Requirements *(mandatory)*

### Functional Requirements — 전략 선택

- **FR-001**: 시스템은 `AGENT_BACKEND` 로 `deepagents`(기본) / `cliagents` 중 하나를 고를 수 있어야
  한다.
- **FR-002**: 분기는 `get_agent(mode)` **한 곳**에서만 일어나야 한다. 스트리밍·MCP 어댑터 등 호출부는
  어느 백엔드인지 몰라야 한다.
- **FR-003**: 두 백엔드는 `.stream()` / `.invoke()` / `.get_state()` 세 메서드만 만족하면 된다.
- **FR-004**: `EXTERNAL_AGENT_ID` 로 `claude-code` / `codex` 를 고를 수 있어야 한다.

### Functional Requirements — 도구는 재구현하지 않는다

- **FR-010**: 외부 에이전트는 스튜디오의 도구를 **MCP 로** 호출해야 한다. 도구 동작을 다시 구현해서는
  안 된다.
- **FR-011**: MCP 로 노출하는 도구는 내장 에이전트가 쓰는 **같은 함수 객체**여야 한다
  (`_BUILD_MODE_TOOLS` / `_ANSWER_MODE_TOOLS`).
- **FR-012**: 모드별로 엔드포인트가 분리되어야 한다. `answer` 모드에는 쓰기 도구가 올라가면 안 된다 —
  지금 내장 에이전트가 가진 권한과 정확히 같아야 한다.
- **FR-013**: 이 서버는 기존 읽기 전용 검색 서버(`ontology_mcp`)와 **별개**여야 한다. 그 서버의 보안
  경계를 넓히면 안 된다.

### Functional Requirements — 프롬프트는 단일 소스

- **FR-020**: 시스템 프롬프트는 마크다운 파일 하나로 존재해야 하고, 두 백엔드가 그 파일을 읽어야 한다.
  내용을 복사해 두 벌로 두면 안 된다.
- **FR-021**: cliagents 경로는 그 파일을 에이전트 관례에 맞는 위치로 내보내야 한다
  (Claude Code `.claude/skills/{name}.md`, Codex `.agents/skills/{name}/SKILL.md`).

### Functional Requirements — 독립 동작

- **FR-030**: cliagents 백엔드 모듈은 `langchain` / `langgraph` / `deepagents` 를 import 하지 않아야
  한다. 그 패키지들이 없어도 이 경로는 동작해야 한다.

### Functional Requirements — 실행 환경

- **FR-040**: 외부 CLI 는 호스트에서 직접 돌므로 샌드박스의 `/workspace` 간접층을 거치지 않는다.
  작업 디렉터리는 스튜디오가 실제로 파일을 서빙하는 `uploads/`·`output/` 루트여야 한다.
- **FR-041**: 스킬 본문은 `/workspace` 를 말하므로, 실제 호스트 경로 매핑을 시스템 프롬프트에
  명시해야 한다.
- **FR-042**: 파일 읽기·쓰기·실행은 CLI 자신의 도구를 쓰고, 그래프 조작은 MCP 도구를 써야 한다.

### Functional Requirements — Human in the loop

- **FR-050**: 에이전트가 작업 중일 때도 사용자가 메시지를 보낼 수 있어야 한다.
- **FR-051**: 그 메시지는 새 턴이 아니라 **실행 중인 턴**에 전달되어야 한다.
- **FR-052**: 전달 전에 **인터럽트를 먼저 보내야** 한다. 그러지 않으면 에이전트는 방금 취소당한
  작업을 끝까지 마친 뒤에야 새 지시를 읽는다.
- **FR-053**: 헤드리스에서 입력을 받을 수 없는 에이전트는 요청을 **거부**해야 한다. 큐에 넣고 버리면
  안 된다.
- **FR-054**: 세션 초기화는 CLI 대화도 함께 초기화해야 한다.
- **FR-055**: 에이전트가 구조화된 질문(AskUserQuestion)을 보내면 선택지를 UI 로 렌더링하고, 답은
  같은 실행 중인 턴으로 돌려보내야 한다.

### Key Entities

| 개념 | 설명 |
|---|---|
| `AgentBackend` | `.stream()`/`.invoke()`/`.get_state()` 를 만족하는 무엇. 두 구현이 있다 |
| `CliAgentAdapter` | 외부 CLI 프로세스를 위 인터페이스로 감싼 것 |
| `TurnEvent` | CLI 출력에서 뽑아낸 에이전트 중립 이벤트 (token/tool_start/tool_result/steered/ask_user/error) |
| agent-bridge MCP | 모드별로 스튜디오 도구를 노출하는 in-process MCP 서버 |
| skill 파일 | 시스템 프롬프트의 단일 소스. 두 백엔드가 공유 |
| 스티어링 채널 | 실행 중인 턴에 메시지를 밀어넣는 경로 (인터럽트 + stdin) |

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: `AGENT_BACKEND` 미설정 시 기존 백엔드 테스트가 100% 통과한다.
- **SC-002**: `cliagents` 경로에서 질문 응답이 내장 경로와 **같은 값**을 낸다.
- **SC-003**: `cliagents` 경로에서 문서 빌드가 클래스 생성 → 파서 작성 → 적재 → Cypher 검증까지
  완주한다.
- **SC-004**: cliagents 백엔드 모듈 import 시 langchain 계열 모듈이 **0개** 적재된다.
- **SC-005**: 작업 중 스티어링이 **10초 안에** 반영된다.
- **SC-006**: 두 CLI(claude-code, codex) 모두에서 SC-002·SC-003 이 성립한다.

### 실제 검증 상태 (2026-08-01)

| 항목 | claude-code | codex | 비고 |
|---|---|---|---|
| 질문 응답 (SC-002) | ✅ 351일 / 20.3초 | ✅ 351일 / 21.0초 | 내장 경로와 동일 값 |
| 문서 빌드 (SC-003) | ✅ 2,493 노드 / 991초 | ✅ 1,559 노드 / 361초 | 도로교통법 PDF 403KB |
| 골든 퀘스천 검증 | ✅ 3/3 PASS | ✅ | 실제 Cypher 실행 |
| langchain 비의존 (SC-004) | ✅ 0개 | ✅ | 서브프로세스 테스트로 강제 |
| 실행 중 스티어링 (SC-005) | ✅ 약 4초 | ❌ 거부 반환 | codex 는 헤드리스 입력 불가 |
| 완료 후 세션 이어가기 | ✅ | ✅ | `--resume` |
| AskUserQuestion | ❌ 도구 미제공 | ❌ | 배선만 존재 (아래) |
| 기존 경로 회귀 (SC-001) | ✅ 417 tests | — | |

### 스티어링 — 인터럽트의 효과 (실측)

같은 지시("취소하고 클래스 이름만 한 줄로 나열해줘")를 작업 20초 시점에 보냈을 때:

| | 인터럽트 없음 | 인터럽트 있음 |
|---|---|---|
| 턴 총 소요 | 68.1초 | **24.8초** |
| 결과 | 스티어링 무시, 원래 상세 보고서 완주 | **지시대로 클래스 목록만** |

메시지를 stdin 에 밀어넣는 것만으로는 부족하다. Claude Code 는 현재 턴을 끝낸 **뒤에야** 다음 입력을
읽으므로, `control_request`/`interrupt` 를 먼저 보내야 실제 개입이 된다.

### AskUserQuestion 이 발화하지 않는다 (실측)

Claude Code 헤드리스(`-p`)에는 AskUserQuestion 도구가 **제공되지 않는다.** 명시적으로 "반드시
AskUserQuestion 으로 물어봐" 라고 지시해도 산문으로 되묻는다. Codex 도 같다.

따라서 FR-055 의 배선(이벤트·SSE·UI 버튼)은 존재하지만 현재 어느 경로로도 실행되지 않는다.
실질적인 HITL 루프는 **에이전트가 산문으로 묻고 사용자가 스티어링으로 답하는** 형태다.
배선을 남겨 둔 이유는 비용이 거의 없고, 어느 에이전트든 이 도구를 노출하는 순간 구조화된 선택지가
산문보다 나은 UI 이기 때문이다.

### 구현 중 발견한 결함

문서와 영상 제작 과정에서 드러난 것들. 모두 수정 후 테스트로 고정했다.

| # | 증상 | 원인 |
|---|---|---|
| 1 | 스티어링 응답이 UI 에서 사라짐 | SSE 핸들러가 마지막 메시지를 스트리밍 대상으로 삼는데, 스티어링 사용자 메시지를 뒤에 붙여 토큰이 사용자 버블로 들어감 |
| 2 | Codex 가 10분 넘게 멈춤 | `stdin=PIPE` 를 열어 두면 Codex 는 입력이 더 올 것으로 보고 닫힐 때까지 대기 |
| 3 | Codex 의 MCP 도구 호출이 전부 취소 | `approval_policy="never"` 로도 MCP 도구는 승인 대기에 걸림 (`user cancelled MCP tool call`) |
| 4 | Codex 진행 이벤트가 UI 에 안 보임 | 이벤트 스키마가 `item.started`/`item.completed` 래퍼로 바뀜 |
| 5 | 세션 초기화 후에도 "이미 완료된 요청" | `clear_session()` 이 CLI 세션 매핑을 지우지 않음 |
| 6 | 문서 빌드 노드 수가 실행마다 누적 | 스키마 그룹 삭제는 Neo4j 엔티티를 남김 |

1번은 **거짓 통과**로 숨어 있었다. 처음 단언이 "응답 길이 < 1500자" 였는데, 스티어링 **이전** 메시지도
짧아서 통과했다. 단언을 "응답에 실제 클래스 목록이 있어야 한다" 로 바꾸고서야 드러났다.

## Out of Scope

- 내장 경로의 컨텍스트 관리 개선. `_compress_history` 가 앞에서부터 버려 긴 빌드에서 인텐트를 잊는
  문제가 관측됐지만, 이 스펙은 그것을 고치지 않는다.
- Cursor 등 헤드리스 CLI 가 없는 에이전트 지원.
- 두 백엔드의 품질 비교. 관측된 차이는 대부분 **모델 차이**이지 아키텍처 차이가 아니다.
