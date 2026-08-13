# Implementation Plan: 교체 가능한 에이전트 백엔드

**Spec**: [spec.md](./spec.md) · **Status**: Implemented (2026-08-01)

## 설계의 중심 — 좁은 이음매 하나

`get_agent(mode)` 가 반환하는 객체를 코드베이스가 실제로 어떻게 쓰는지 세어 보면 세 가지뿐이다:

| 메서드 | 호출부 |
|---|---|
| `.stream(input, config, stream_mode)` | `agent_session/service.py` `_run_agent_in_thread` |
| `.invoke(input, config)` | `ontology_mcp/adapters.py` |
| `.get_state(config)` | 위 두 곳의 마무리 처리 |

즉 LangGraph `CompiledGraph` 전체가 아니라 이 셋만 만족하면 대체 가능하다. 그래서 분기를
`get_agent()` 안에 넣으면 **호출부는 한 줄도 바뀌지 않는다.** 기존에 있던
`shared/sandbox/get_sandbox_backend()` 팩토리와 정확히 같은 모양이다.

```
AGENT_BACKEND=deepagents (기본) → _create_build_agent() / _create_answer_agent()   ← 무수정
AGENT_BACKEND=cliagents        → CliAgentAdapter(mode)
```

## 세 가지 원칙이 코드에 박히는 자리

### 1. 도구 재구현 금지 → 같은 함수 객체를 MCP 에 등록

`agent_bridge_mcp/server.py` 는 `_BUILD_MODE_TOOLS` / `_ANSWER_MODE_TOOLS` 를 import 해서
`mcp.add_tool(fn)` 로 그대로 올린다. 새 도구 구현이 없다.

테스트가 이것을 강제한다 — `tools_for("build") == list(_BUILD_MODE_TOOLS)` 는 객체 동일성을 본다.
누가 여기에 도구를 새로 구현하면 실패한다.

모드마다 엔드포인트를 나눈 이유는 권한이다. 하나로 합치면 `answer` 모드가 쓰기 도구를 갖게 되는데,
그건 지금 내장 에이전트에 없는 권한이다.

```
/mcp/agent-bridge/build        31개 도구 (쓰기 포함)
/mcp/agent-bridge/answer       10개 (읽기 전용)
/mcp/agent-bridge/answer_nods   7개 (데이터소스 제외)
```

기존 `ontology_mcp` 은 건드리지 않는다. 그 서버는 `TOOL_NAMES` 를 보안 경계로 명시한 읽기 전용
검색 서버이고, 여기에 mutation 을 얹으면 그 불변식이 깨진다.

### 2. 프롬프트 단일 소스 → 파일로 빼고 둘이 읽는다

`service.py` 에 인라인 문자열로 있던 두 프롬프트를 파일로 옮겼다:

```
backend/src/modules/agent_session/skills/ontology_build.md    22.0K
backend/src/modules/agent_session/skills/ontology_answer.md    3.4K
```

- deepagents: `load_skill()` → `system_prompt=` (호출부 무수정)
- cliagents: 같은 함수로 읽어 `ArtifactBundle().add_skill()` 로 emit

배치 위치는 cliagents 라이브러리가 에이전트별로 정한다:

| | Claude Code | Codex |
|---|---|---|
| 경로 | `.claude/skills/{name}.md` | `.agents/skills/{name}/SKILL.md` |
| 프론트매터 | 불필요 | `name`/`description` 자동 삽입 |

옮길 때 build 프롬프트 첫 글자의 잔여 백슬래시 하나를 걷어냈다. `r"""\` 는 raw string 이라
줄이음이 적용되지 않아 리터럴 `\` 가 값에 남아 있었다(answer 프롬프트는 raw 가 아니라 정상).

### 3. 독립 동작 → import 금지를 테스트로 고정

`cliagents_backend.py` 는 표준 라이브러리 + `cliagents` 만 쓴다. 서브프로세스에서 이 모듈만
import 하고 `sys.modules` 를 검사하는 테스트로 강제한다.

이 제약 때문에 LangGraph 의 `updates` 페이로드를 만들 수 없다(그 안의 메시지는 LangChain 클래스로
타입 판별된다). 그래서 어댑터는 **`"cli"` 라는 별도 이벤트 모드**로 평범한 dict 를 흘리고,
`generate_sse` 에 그 분기를 하나 추가했다.

반환값도 마찬가지다. `ontology_mcp` 의 소비자들이 `.type`/`.content`/`.tool_call_id` 로 덕타이핑하는
것을 확인하고, LangChain 없이 그 속성만 가진 `_Message` 프로즌 데이터클래스를 돌려준다.

## 왜 cliagents 의 PtySession 을 쓰지 않는가

cliagents 는 세 surface(TERMINAL/ARTIFACTS/BRIDGE)를 제공한다. `PtySession` 은 "호스트가 이벤트
루프를 소유하는 대화형 터미널" 용이고, 헤드리스로 한 턴 돌리고 구조화된 스트림을 받는 네 번째
surface 는 없다.

스튜디오는 HTTP 요청당 한 턴(SSE)이므로 헤드리스 실행이 맞다. 그래서 역할을 나눴다:

| cliagents 가 하는 것 | 여기서 하는 것 |
|---|---|
| CLI 탐지 · 설치 힌트 | 헤드리스 argv 조립 |
| 스킬 파일 배치 경로 | CLI 출력 파싱 |
| 에이전트별 관례 차이 | 스티어링 · 인터럽트 |

에이전트별 헤드리스 실행은 `_RUNNERS` 딕셔너리로 갈린다. cliagents 에 헤드리스 surface 가 생기면
자연스럽게 이관할 수 있는 자리다.

## 실행 환경 — 호스트 파일시스템 직접 사용

외부 CLI 는 호스트에서 돈다. 샌드박스의 `/workspace` 간접층을 거칠 이유가 없다.

- 작업 디렉터리 = `LOCAL_SANDBOX_ROOT` (스튜디오가 `uploads/`·`output/` 을 서빙하는 그곳)
- 도구 allow-list 없음 — CLI 의 Read/Write/Bash 를 그대로 쓴다
- 스킬 본문의 `/workspace` → 실제 경로 매핑을 시스템 프롬프트 끝에 명시

이 전환 전에는 에이전트가 `/workspace/uploads/...` 로 파서를 짜서 **7번 실패**했다. 전환 후 0번.

UI 에 보고하는 도구는 "내부 기록"만 숨긴다(`ToolSearch`, `TodoWrite`). 에이전트가 `Write` 로 파서를
쓰고 `Bash` 로 돌리는 것은 실제 작업이므로 그대로 보여준다.

## Human in the loop

### 스티어링 — 스트리밍 입력 + 인터럽트

`-p <프롬프트>` 단발에서 `--input-format stream-json` 으로 바꿨다. stdin 이 열려 있으므로 실행 중인
턴에 사용자 메시지를 밀어넣을 수 있다.

```
POST /api/agent/steer?session_id&mode  {"text": "..."}  → {"delivered": bool}
```

**메시지만 밀어넣는 것으로는 부족하다.** Claude Code 는 현재 턴을 끝낸 뒤에야 다음 입력을 읽는다.
그래서 전달 전에 인터럽트를 먼저 보낸다:

```json
{"type":"control_request","request_id":"...","request":{"subtype":"interrupt"}}
```

인터럽트가 만든 error result 는 실패가 아니라 우리가 요청한 중단이므로 삼킨다.
밀어넣은 메시지 수만큼 result 를 기다린 뒤에 stdin 을 닫는다(`outstanding` 카운터). 첫 result 에서
닫으면 방금 보낸 스티어링이 잘린다.

Codex 는 헤드리스 입력이 없다. `_STEERABLE` 로 걸러 `delivered: false` 를 돌려준다 — 큐에 넣고
버리면 사용자는 전달됐다고 믿는다.

### 세션 연속성

| | 세션 ID 주체 |
|---|---|
| Claude Code | 우리가 첫 턴에 uuid4 생성 → `--session-id`, 이후 `--resume` |
| Codex | Codex 가 발급 → 이벤트에서 캡처해 저장, 이후 `resume <id>` |

스레드 기반 결정적 UUID 를 쓰면 백엔드 재시작 후 이미 존재하는 ID 가 되어 CLI 가 거부한다.
Codex 의 `--last` 는 머신 전체에서 최신 세션을 고르므로 동시 세션에서 남의 대화를 집는다.

`clear_session()` 은 어댑터의 `forget_session()` 도 호출한다. 이게 없으면 초기화한 세션인데도
"이미 완료된 요청" 이라고 답한다.

## 변경 대상

| 파일 | 성격 |
|---|---|
| `ontology-studio/cliagents` | 새 서브모듈 |
| `pyproject.toml` | `cliagents` editable 의존성 + skills 패키지 데이터 |
| `shared/kernel/settings.py` | `agent_backend`, `external_agent_id` |
| `agent_session/skills/*.md` | 프롬프트 단일 소스 (신규) |
| `agent_session/service.py` | `get_agent` 분기, `load_skill`, `cli` SSE 분기, steer/running 헬퍼 |
| `agent_session/cliagents_backend.py` | 어댑터 (신규) |
| `agent_bridge_mcp/` | MCP 서버 + 라우터 (신규) |
| `agent_session/api.py` | `/api/agent/steer`, `/api/agent/running` |
| `host/app.py` | 마운트 + lifespan 체이닝 |
| `frontend/.../useOntologyStudio.js` | steer, ask_user, steered 처리 |
| `frontend/.../ChatPanel.vue` | 실행 중 입력창, 조타 버튼, 질문 UI |

FastAPI 는 마운트된 서브앱의 lifespan 을 전파하지 않는다. 세션 매니저가 시작되지 않으면 MCP 요청이
전부 거부되므로 `host/app.py` 의 lifespan 에서 직접 진입한다.

## 검증 방법

```bash
# 회귀 (기본 경로)
cd ontology-studio && uv run --with pytest --with httpx pytest -q backend/tests

# 두 CLI 로 문서 빌드 비교
DEMO_APP=... DEMO_API=... BUILD_LABEL=claude-code npx playwright test tests/e2e_doc_build_compare.spec.js
DEMO_APP=... DEMO_API=... BUILD_LABEL=codex       npx playwright test tests/e2e_doc_build_compare.spec.js

# 실행 중 스티어링 (UI 경로)
DEMO_APP=... DEMO_API=... npx playwright test tests/e2e_hitl_steering.spec.js
```

E2E 스펙은 `/api/neo4j/clear-all` 을 쓰지 않는다 — 그것은 데이터 패브릭 카탈로그까지 지운다
(constitution IV). 자기가 만든 스키마 그룹의 **클래스를 먼저** 지우고 그룹을 지운다. 그룹만 지우면
Neo4j 엔티티가 남아 다음 실행의 노드 수에 누적된다.

## 데모 영상

```
demo/out/document-build-cliagents.mp4   문서 빌드 (Claude Code) · say/Yuna
demo/out/document-build-codex.mp4       문서 빌드 (Codex) · OpenAI TTS nova
demo/out/hitl-steering-cliagents.mp4    실행 중 개입 · OpenAI TTS nova
```

빌드 데모는 중간이 에이전트가 몇 분간 스스로 일하는 구간이라, 장면을 나레이션 길이에 고정할 수 없다.
마일스톤(도구 등장·파일 생성·타이핑 종료)에 반응해 넘어가되 최소 나레이션 길이는 지키고, 남는 화면은
`build_video.py --trim-to-narration` 으로 잘라낸다.
