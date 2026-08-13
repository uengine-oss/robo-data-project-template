# Implementation Plan: 이식 가능한 에이전트 스킬 패키지

**Branch**: `main` (별도 브랜치 미생성) | **Date**: 2026-08-02 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/005-portable-agent-skills/spec.md`

## Summary

지시문을 스튜디오 코드 밖으로 꺼내 **agentskills.io 표준 스킬 폴더**로 만든다. 폴더 하나가 세 역할을
동시에 한다 — (1) 스튜디오가 런타임에 읽는 지시문 원천, (2) 사용자가 `~/.claude/skills/` 로 복사하는
스킬, (3) Claude Code UI 로 설치되는 플러그인.

확인한 사실 두 가지가 설계를 결정했다:

1. **deepagents 는 이미 이 규격을 안다.** `deepagents.middleware.skills` 가 agentskills.io 스펙을
   그대로 구현하고 있고, 스튜디오의 샌드박스 백엔드는 **이미 deepagents `BackendProtocol` 을 구현**
   한다(`DockerSandboxBackend(BaseSandbox)`). 규격을 새로 만들 필요가 없다.
2. **지시문이 두 곳으로 갈라져 있다.** 스킬 파일 말고도 `_compose_build_prompt` 가 `[구축 의도]` ·
   `[연결 데이터소스]` · `[Golden Question]` · `[완료 기준]` 을 파이썬 문자열로 조립한다. 스킬 파일만
   옮기면 이 절반은 그대로 남아 단독 실행자에게 전달되지 않는다.

그래서 이 계획은 **두 가지를 함께** 옮긴다: 스킬 본문의 형식·위치와, 입력 계약(무엇을 받아 어떤
기준으로 끝내는가). 후자가 초기 인터뷰(FR-050~058)의 근거이기도 하다.

## Technical Context

**Language/Version**: Python ≥3.12 (백엔드). 프론트엔드 변경 없음

**Primary Dependencies**: `langchain.agents.create_agent`(내장 경로) · `deepagents.backends`(샌드박스
프로토콜) · `cliagents`(서브모듈, 외부 CLI 프로바이더) · `PyYAML`(프론트매터 파싱, 기존 의존성)

**Storage**: 스킬 폴더는 파일시스템. 런타임 상태 없음. 샌드박스 동기화 결과는 휘발성
(`<sandbox>/.skills/`)

**Testing**: pytest (`ontology-studio/backend/tests/`), 서브프로세스 격리 테스트(langchain 비의존
강제), Playwright E2E(기존 스위트)

**Target Platform**: macOS/Linux 호스트. 샌드박스는 `docker`(기본) 또는 `local`

**Project Type**: 웹 서비스(backend + frontend) + 서브모듈 라이브러리(cliagents)

**Performance Goals**: 스킬 동기화가 세션당 1회, 첫 턴 지연에 체감 영향 없을 것(파일 10개 미만, 합계
100KB 미만). 입력이 완비된 요청의 되묻기 0회(SC-013)

**Constraints**: cliagents 경로는 langchain 계열 import 0개(004 FR-030 / SC-004 유지) · `answer` 모드에
쓰기 도구 금지 · 스킬 본문에 환경별 절대 경로 금지(FR-005)

**Scale/Scope**: 스킬 2개(`ontology-build`, `ontology-answer`) + 참조 자료 7개. 백엔드 신규 모듈 2개,
수정 3곳(`service.py`, `cliagents_backend.py`, cliagents 서브모듈 프로바이더)

## Constitution Check

*GATE: Phase 0 이전 통과 필수. Phase 1 이후 재확인.*

| 원칙 | 관련성 | 판정 |
|---|---|---|
| I~III (카탈로그 계약) | 스킬은 카탈로그를 읽지 않는다. 도구가 읽는다 | 해당 없음 |
| IV. 전역 삭제 금지 | 동기화가 샌드박스에 쓴다. `uploads/`·`output/` 를 건드리지 않고 `.skills/` 만 쓴다 | **통과** |
| V. 자격증명 비노출 | 스킬 본문·참조 자료에 접속 정보를 넣지 않는다. 배포 MCP 설정은 URL 만 담는다 | **통과** |
| VI. 루트 `.env` 단일 원천 | 배포본의 MCP URL 이 새 설정 항목이 된다. 바인드 주소를 접속 주소로 쓰지 않는다 | **통과** (아래 주의) |
| VII. 실행 검증 | 단위 테스트만으로 "동작한다" 고 보고하지 않는다 | **통과** |
| ontology-studio: 에이전트 백엔드는 도구와 프롬프트를 공유한다 | **정면으로 관련** | **개정 완료 — 통과** |

### constitution 개정 (2.1.0 → 2.2.0, 2026-08-02 완료)

Governance 규칙이 "위반이 필요하다면 **먼저 이 문서를 고치고** 근거를 남긴다" 이므로, 구현 착수
전에 개정했다. 이 계획은 개정된 2.2.0 을 기준으로 판정된다.

바뀐 것 셋:

1. **프롬프트 원천 위치** — `agent_session/skills/*.md` → `skills/<name>/SKILL.md`
2. **"스킬은 배포 가능한 표준 패키지다" 절 신설** — agentskills.io 규격, 폴더 스캔, 참조 자료
   분할과 양쪽 경로의 읽기 보장, 배포본 무가공
3. **"지시문과 값을 섞지 않는다" 절 신설** — 백엔드가 넘기는 것은 값이고, "이 질문들에 답할 수
   있도록 구축하세요" 같은 문장은 스킬에 있어야 한다

원칙 자체("두 백엔드가 갈라지면 안 된다")는 약화되지 않았다. 오히려 **강화됐다** — 2.1.0 은
"프롬프트 파일이 하나" 라고만 요구해서 `_compose_build_prompt` 가 지시문을 파이썬에서 조립하는
것을 잡지 못했다. 파일을 세는 규칙으로는 보이지 않는 위반이었다. 2.2.0 은 그것을 "지시문은
스킬에, 값은 코드에" 로 다시 적는다.

### 원칙 VI 주의사항

배포본의 MCP URL 기본값은 `http://127.0.0.1:8000` 이다. `BACKEND_HOST=0.0.0.0` 을 그대로 쓰면 안 되고
(004 에서 이미 겪은 함정), 사용자가 포트를 바꿨을 때 덮어쓸 수 있어야 한다. `.mcp.json` 의
`${VAR:-default}` 확장으로 처리한다 — 문서화된 기능임을 확인했다([research.md](research.md) R5).

## Project Structure

### Documentation (this feature)

```text
specs/005-portable-agent-skills/
├── plan.md              # 이 파일
├── research.md          # Phase 0 — 확인한 사실과 결정
├── data-model.md        # Phase 1 — 스킬 패키지·입력 계약의 구조
├── quickstart.md        # Phase 1 — 검증 시나리오
├── contracts/
│   ├── skill-package.md     # 스킬 폴더 형식 계약
│   ├── input-contract.md    # 스튜디오→스킬 입력 블록과 인터뷰 규칙
│   ├── skill-registry.md    # 두 백엔드가 공유하는 로더 표면
│   └── distribution.md      # 플러그인 / 마켓플레이스 / MCP 설정 계약
└── tasks.md             # /speckit-tasks 산출물 (이 명령이 만들지 않음)
```

### Source Code (repository root)

```text
ontology-studio/                          # 서브모듈
├── .claude-plugin/
│   └── marketplace.json                  # [신규] 두 플러그인을 싣는 마켓플레이스
├── skills/                               # [신규] 스킬 패키지의 정식 위치
│   ├── ontology-build/
│   │   ├── SKILL.md                      # 프론트매터 + 개요 + 워크플로우 + 입력 계약
│   │   ├── .claude-plugin/plugin.json    # 이 폴더를 플러그인으로도 만든다
│   │   ├── .mcp.json                     # agent-bridge(build) 등록
│   │   └── references/
│   │       ├── ingestion-patterns.md     # 패턴 A~D, D-1
│   │       ├── parser-rules.md           # content 수집·노드 속성·자체 검증
│   │       ├── source-types.md           # PDF/Excel/Shapefile/DOCX 파싱
│   │       ├── datasource-binding.md     # 바인딩·behavior·SQL 템플릿 규칙
│   │       ├── strategies.md             # 003 전략 선택·역바인딩·인과발견
│   │       └── validation.md             # Phase 3 검증·검색 힌트·리포트 형식
│   └── ontology-answer/
│       ├── SKILL.md
│       ├── .claude-plugin/plugin.json
│       ├── .mcp.json
│       └── references/
│           └── search-strategy.md        # 단계별 검색 전략·가상 클래스 발견
├── backend/src/modules/agent_session/
│   ├── skill_registry.py                 # [신규] 폴더 스캔·프론트매터 파싱·검증
│   ├── skill_sync.py                     # [신규] 샌드박스로 스킬 폴더 동기화
│   ├── service.py                        # [수정] 시스템 프롬프트·입력 조립 축소
│   ├── cliagents_backend.py              # [수정] 폴더 통째 emit, service 의존 제거
│   └── skills/                           # [제거] ontology_build.md / ontology_answer.md
├── backend/tests/modules/agent_session/
│   ├── test_skill_registry.py            # [신규]
│   ├── test_skill_sync.py                # [신규]
│   ├── test_input_contract.py            # [신규] 인터뷰 유발 / 미유발 판정
│   ├── test_prompt_composition.py        # [수정] 지시문 문장이 사라졌는지 확인
│   └── test_cliagents_backend.py         # [수정] 폴더 emit 검증
└── cliagents/                            # 서브모듈 (별도 저장소)
    └── src/cliagents/
        ├── artifacts.py                  # [수정] Artifact 에 보조 파일 지원
        ├── provider.py                   # [수정] 스킬을 폴더로 배치
        └── providers/claude_code.py      # [수정] skill_path 를 폴더 규약으로
```

**Structure Decision**: 스킬 폴더는 **ontology-studio 서브모듈 루트의 `skills/`** 에 둔다. 세 가지가
동시에 성립해야 하기 때문이다 — 스튜디오 백엔드가 읽고, 사용자가 폴더째 복사하고, 마켓플레이스가
`"source": "./skills/ontology-build"` 로 가리킨다. 파이썬 패키지 내부(`backend/src/.../skills/`)는 셋 중
첫 번째만 만족한다.

플랫폼 루트(`ontologic/`)에 두지 않는 이유는 이 스킬이 **스튜디오의 도구**를 전제하기 때문이다.
도구와 지시문이 다른 저장소에 있으면 004 가 막으려던 divergence 가 저장소 경계로 되살아난다.

`ontology-studio/.claude/skills/` 는 이 저장소를 **개발할 때** 쓰는 openspec 스킬들이 이미 차지하고
있다. 제품 스킬을 거기에 섞지 않는다.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|---|---|---|
| cliagents 서브모듈 API 변경 (보조 파일) | `Artifact` 가 단일 문자열만 담아 참조 자료를 실을 수 없다 | 단일 본문 유지 → 사용자가 분할을 명시적으로 선택했고, 본문이 수백 줄이라 "본문은 간결하게" 라는 스킬 규약에 어긋난다 |
| 스킬 폴더를 샌드박스로 동기화 | 내장 경로의 파일 도구는 샌드박스 범위다. 호스트의 스킬 폴더를 읽지 못한다 | 참조 자료를 프롬프트에 인라인 → 점진적 공개가 무의미해지고 FR-042 가 한쪽만 성립 |

## 구현 순서

의존 관계상 아래 순서가 강제된다. 상세 분해는 `/speckit-tasks` 에서 한다.

1. ~~**constitution 개정**~~ — 2.2.0 으로 완료 (2026-08-02)
2. **스킬 폴더 구축** — 기존 두 본문을 SKILL.md + references 로 재배치(내용 무변경, FR-043).
   입력 계약·도구 요구사항·권한 경계·경로 규약 절을 새로 쓴다
3. **레지스트리** — 스캔·파싱·검증. langchain 비의존. 두 백엔드의 유일한 진입점
4. **동기화** — 샌드박스 백엔드 프로토콜로 `.skills/` 에 복사 (docker / local 공통 경로)
5. **내장 경로 배선** — `SKILL.md` 본문을 시스템 프롬프트로, 환경 바인딩을 한 블록으로 주입
6. **입력 계약 이관** — `_compose_build_prompt` 를 값 전달로 축소, 지시문 문장은 스킬로
7. **cliagents 경로** — 폴더 통째 emit, `service.load_skill` 의존 제거
8. **배포 포장** — plugin.json · .mcp.json · marketplace.json · 설치 문서
9. **검증** — 004 시나리오 재현 + 신규 SC 확인 (원칙 VII: 실제 실행)

## Post-Design Constitution Re-check

개정된 **2.2.0** 을 기준으로 Phase 1 산출물을 재확인했다. 위반 없음.

- **원칙 V**: `.mcp.json` 은 URL 만 담고 자격증명을 담지 않는다 → [distribution.md](contracts/distribution.md)
- **원칙 VI**: MCP URL 은 `${VAR:-default}` 로 덮어쓸 수 있고 기본값은 `127.0.0.1` 이다
- **에이전트 백엔드 공유 원칙**: 레지스트리가 유일한 진입점이므로 두 경로의 divergence 가
  구조적으로 불가능해진다. 004 시점보다 **강해진다** (그때는 규칙이었고 지금은 단일 함수다)
- **스킬은 배포 가능한 표준 패키지다** (2.2.0 신설): [skill-package.md](contracts/skill-package.md)
  가 규격·폴더 스캔·거부 규칙을, [skill-registry.md](contracts/skill-registry.md) C1·C2 가 그
  강제 지점을 고정한다
- **지시문과 값을 섞지 않는다** (2.2.0 신설): [input-contract.md](contracts/input-contract.md) 의
  "백엔드가 하면 안 되는 것" 표가 옮겨야 할 문장을 하나씩 지목한다. 환경 바인딩은
  `environment_binding_block()` 값 블록 하나로 좁혀지고 `_host_workspace_note()` 는 삭제된다
