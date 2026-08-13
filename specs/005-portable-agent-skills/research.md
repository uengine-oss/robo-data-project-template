# Phase 0 — 조사와 결정

스펙의 미확정 항목은 `/speckit-specify` 단계에서 사용자 결정으로 모두 해소됐다(배포 형태 = 플러그인
+ 폴더 복사, 본문 분할 = 참조 자료). 이 문서는 그 결정을 **구현 가능한 형태로 만들기 위해 확인한
사실**과, 그 위에서 내린 설계 결정을 담는다.

각 항목은 추측이 아니라 소스 또는 공식 문서에서 확인했고 확인 경로를 적었다.

---

## R1 — deepagents 는 agentskills.io 규격을 이미 구현한다

**확인**: `ontology-studio/.venv/.../deepagents/middleware/skills.py`

- 폴더 + `SKILL.md` + YAML 프론트매터 구조를 그대로 요구한다
- 이름 제약이 스펙과 동일: 1~64자, 소문자·하이픈, `-` 로 시작/끝 금지, `--` 금지,
  **부모 디렉터리 이름과 일치**해야 함
- `description` 최대 1024자, `allowed_tools`·`license`·`compatibility`·`metadata` 를 인식
- 시스템 프롬프트에 목록을 주입할 때 각 스킬마다
  `-> Read `{path}` for full instructions` 를 붙인다 — **경로를 알려 주고 에이전트가 읽게 하는** 방식

**중요**: 그 `path` 는 백엔드 경로다. 에이전트가 그 경로를 읽을 도구를 갖고 있지 않으면 목록만 보고
내용을 못 읽는다. 이것이 R3 의 동기다.

**결정**: 규격을 새로 만들지 않는다. agentskills.io 를 그대로 따른다.

---

## R2 — 스튜디오는 `create_deep_agent` 가 아니라 `create_agent` 를 쓴다

**확인**: `backend/src/modules/agent_session/service.py:734, 765`

```python
create_agent(model=..., tools=..., system_prompt=ONTOLOGY_BUILD_SYSTEM_PROMPT,
             middleware=[HistoryCompressionMiddleware(), ToolCallParserMiddleware()])
```

`service.py:1653` 에 `if "SkillsMiddleware" in node_name` 이 있지만 **어디에서도 등록되지 않는다.**
죽은 분기다.

### 결정 — 내장 경로는 SkillsMiddleware 의 *발견*을 쓰지 않는다

`SkillsMiddleware` 는 "여러 스킬 중 에이전트가 고르는" 상황을 위한 것이다. 스튜디오는 그 상황이
아니다 — 모드가 엔드포인트로 이미 정해져 있고(build 탭 / 질의 탭), 해당 스킬은 **항상** 적용된다.

발견 방식으로 바꾸면:

- 에이전트가 스킬을 안 읽고 진행할 여지가 생긴다 (결정성 상실)
- 매 세션 읽기 턴이 하나 늘어난다 (SC-013 의 "턴 수가 지금과 같다" 와 충돌)

그래서 **`SKILL.md` 본문(프론트매터 제거)을 시스템 프롬프트로 주입**하고, 참조 자료만 필요할 때
읽게 한다. 이것도 FR-011 을 만족한다 — "폴더 내용을 통째 이식" 하지 않고 본문만 쓰며, 세부는 폴더에
남는다.

**단독 실행에서는 반대다.** 사용자가 "온톨로지 만들어줘" 라고 하면 Claude Code 가 `description` 을
보고 스킬을 고른다. 그래서 프론트매터의 `description` 은 장식이 아니라 **단독 실행의 유일한 발견
경로**다.

**대안 기각**: SkillsMiddleware 로 통일 — 위의 결정성·턴 수 손실. 다만 앞으로 선택적 스킬을 여러 개
노출하게 되면 그때 이 미들웨어가 정답이므로, 레지스트리의 메타데이터는 미들웨어가 요구하는 형태를
그대로 유지한다(전환 비용 0).

---

## R3 — 샌드박스 백엔드가 이미 deepagents `BackendProtocol` 이다

**확인**: `backend/src/shared/sandbox/docker_backend.py:16` —
`class DockerSandboxBackend(BaseSandbox)` (`deepagents.backends.sandbox` 에서 상속)

즉 파일 읽기/쓰기/실행 표면이 이미 표준이고, 스킬 폴더를 그 표면으로 넣을 수 있다.

### 문제 — 내장 경로의 파일 도구는 샌드박스 범위다

`sandbox_read` / `sandbox_ls` / `execute` 는 모두 샌드박스 안을 본다
(`backend/src/modules/agent_session/sandbox_tools.py`). 호스트의 `ontology-studio/skills/` 는 docker
모드에서 **컨테이너에 없다.** 참조 자료를 읽으라고 해도 읽을 수 없다.

### 결정 — 세션 준비 시 스킬 폴더를 샌드박스로 동기화한다

- 대상 경로: `<sandbox_workdir>/.skills/<skill-name>/`
- 수단: 샌드박스 백엔드의 write (docker / local 양쪽에서 같은 코드)
- 시점: 세션당 1회, 멱등. cliagents 의 `_prepare()` 와 같은 자리
- 점 접두사: `uploads/` · `output/` 만 노출하는 파일 패널에 섞이지 않게 한다

**부수 효과가 하나 좋다** — 이렇게 하면 두 백엔드가 **같은 모양**이 된다. cliagents 는 워크스페이스에
스킬 폴더를 emit 하고, deepagents 는 샌드박스에 emit 한다. 둘 다 "지시문은 프롬프트로, 참조 자료는
파일로".

**대안 기각**:
- 참조 자료를 프롬프트에 인라인 → 점진적 공개가 무의미. FR-042 를 한쪽만 만족
- 호스트 경로를 읽는 별도 도구 추가 → 샌드박스 경계에 구멍을 뚫는다. 원칙 V 와 충돌
- 이미지에 굽기 → 스킬을 고칠 때마다 이미지 재빌드. 개발 반복이 죽는다

---

## R4 — cliagents 의 스킬 배치가 지금은 파일 한 장이다

**확인**: `cliagents/src/cliagents/providers/claude_code.py`

```python
layout = ArtifactLayout(skill_path=".claude/skills/{name}.md", ...)
```

그리고 `artifacts.py` 의 `Artifact` 는 `content: str` **하나**만 갖는다. 보조 파일을 실을 자리가 없다.

**Claude Code 의 실제 규약은 `.claude/skills/<name>/SKILL.md` 폴더다**(R5). 즉 지금 emit 되는
`.claude/skills/ontology-build.md` 는 Claude Code 가 스킬로 인식하지 않는다.

그런데 004 는 동작했다. `cliagents_backend.py:223` 이 본문을 `--append-system-prompt` 로 **따로**
넘기기 때문이다. **emit 된 파일은 사실상 읽히지 않고 있었다.**

실측 근거: `ontology-studio/.cache/sandbox/.claude/skills/ontology-build.md` (플랫 파일) 이 남아 있고,
Codex 쪽만 `.agents/skills/ontology-build/SKILL.md` 로 폴더 규약을 지킨다.

### 결정

1. cliagents 의 `Artifact` 에 **보조 파일**을 추가한다 (`files: dict[상대경로, 내용]`)
2. Claude Code 프로바이더의 `skill_path` 를 `.claude/skills/{name}/SKILL.md` 로 고친다
3. 본문 주입은 `--append-system-prompt` 로 **계속 유지**한다 — 발견에 기대지 않고 결정적으로 적용.
   내장 경로와 같은 모양이 된다
4. 폴더 emit 은 참조 자료를 디스크에 놓기 위해 필요하다. 본문이 상대 경로로 참조 자료를 가리키므로
   폴더가 있어야 읽힌다

이 변경은 **cliagents 서브모듈(별도 저장소)** 을 건드린다. 그쪽 저장소의 변경 단위로 따로 관리한다.

---

## R5 — Claude Code 스킬 / 플러그인 / 마켓플레이스 규약

**확인**: `code.claude.com/docs/en/skills`, `/plugins-reference`, `/plugin-marketplaces`, `/mcp`
(2026-08-02 조회)

| 항목 | 사실 |
|---|---|
| 스킬 위치 | 개인 `~/.claude/skills/<name>/SKILL.md`, 프로젝트 `.claude/skills/<name>/SKILL.md` |
| 보조 파일 | `SKILL.md` 옆에 자유롭게 둘 수 있다 (`reference.md`, `scripts/` 등) |
| 표준 | "Claude Code skills follow the Agent Skills open standard" — R1 과 같은 규격 |
| 플러그인 매니페스트 | `.claude-plugin/plugin.json`. **선택 사항** — 없으면 기본 위치에서 자동 발견 |
| 플러그인 안의 스킬 | 플러그인 루트의 `skills/` 디렉터리, **또는 루트에 `SKILL.md` 한 장** |
| 스킬 폴더 = 플러그인 | `<skills-dir>/foo/.claude-plugin/plugin.json` 이 있으면 `foo@skills-dir` 플러그인으로 로드된다 |
| 컴포넌트 위치 | `.claude-plugin/` 안에는 매니페스트만. 나머지는 **플러그인 루트**에 (문서가 경고로 명시) |
| 마켓플레이스 | 저장소 루트의 `.claude-plugin/marketplace.json`. 필수 필드 `name` · `owner` · `plugins[]` |
| 플러그인 항목 | 최소 `name` + `source`. `source` 는 상대 경로 문자열 또는 `{"source":"github","repo":"..."}` |
| MCP | 플러그인 루트의 `.mcp.json`. `type: "http"` 지원 |
| MCP 변수 확장 | `${VAR}` 와 `${VAR:-default}` 지원. 미설정 + 기본값 없음이면 오류 |

### 결정 — 스킬 폴더 자체가 플러그인이 된다

```
ontology-studio/
├── .claude-plugin/marketplace.json          # 두 플러그인을 싣는다
└── skills/ontology-build/
    ├── SKILL.md                             # 플러그인 루트의 SKILL.md = 그 플러그인의 스킬
    ├── .claude-plugin/plugin.json
    ├── .mcp.json
    └── references/
```

`marketplace.json` 의 항목은 `"source": "./skills/ontology-build"`.

이 배치의 이점은 **한 폴더가 세 경로를 모두 만족**한다는 것이다:

1. 스튜디오 런타임이 읽는 원천
2. `~/.claude/skills/` 로 복사 → 스킬(플러그인 매니페스트가 있으므로 `.mcp.json` 까지 따라온다)
3. 마켓플레이스로 설치 → `/plugin install ontology-build@ontology-studio`

FR-025("두 배포 경로가 같은 폴더") 가 파일 복제 없이 성립한다.

### 결정 — 플러그인을 모드별로 둘로 나눈다

`.mcp.json` 은 세션에 서버를 등록한다. build 와 answer 를 한 플러그인에 담으면 질의만 하려는
사용자의 세션에도 **쓰기 도구가 올라간다.** 004 FR-012(모드별 권한 분리)와 스펙의 엣지 케이스
"두 스킬이 동시에 로드됨" 이 그대로 재발한다.

그래서 플러그인 두 개(`ontology-build`, `ontology-answer`)가 각자의 `.mcp.json` 으로 자기 모드
엔드포인트만 등록한다. 마켓플레이스 하나가 둘을 싣는다.

---

## R6 — 지시문의 나머지 절반: `_compose_build_prompt`

**확인**: `backend/src/modules/agent_session/service.py:342-400`

이 함수가 만드는 것:

| 블록 | 성격 |
|---|---|
| `[사용자 작업 요청]` | 값 |
| `[구축 의도]` | 값 |
| `[연결 데이터소스]` | 값 **+ 지시문** ("아래 데이터소스의 테이블과 조회조건에 근거하여 설계하세요", "카탈로그 탐색은 datasource_list / datasource_describe 를 사용하세요") |
| `[Golden Question]` | 값 **+ 지시문** ("아래 질문들에 답할 수 있는 스키마와 그래프를 구축하세요") |
| `[이전 결과 검토 피드백]` | 값 **+ 지시문** ("이를 해결하도록 온톨로지를 개선하세요") |
| `[완료 기준]` | **전부 지시문** |

지시문 문장이 값과 섞여 파이썬에 있다. 단독 실행자는 이 중 아무것도 받지 못한다.

### 결정 — 라벨은 유지하고, 지시문만 스킬로 옮긴다

- **스킬**: 어떤 라벨이 올 수 있는지, 각 라벨을 어떻게 다루는지, 없으면 어떻게 하는지, 완료 기준이
  무엇인지를 전부 본문에 쓴다
- **백엔드**: 값이 있는 라벨만 그대로 붙인다. 설명 문장을 붙이지 않는다. `[완료 기준]` 은 더 이상
  붙이지 않는다

라벨 형식을 그대로 두는 이유는 **회귀 위험이 가장 낮기** 때문이다. 기존 대화 이력과 체크포인트에
같은 형식이 남아 있고, JSON 블록 같은 새 형식으로 바꾸면 모델이 보는 입력 모양이 통째로 달라진다.
이 스펙은 방법론을 바꾸지 않기로 했다(Out of Scope).

**대안 기각**: 구조화된 JSON 입력 블록 — 더 깔끔하지만 재검증 범위가 커진다. 이 계획의 이득(단일
소스)과 무관한 위험이다.

---

## R7 — 초기 인터뷰를 어디에 구현하는가

**결정: 스킬 본문에만 둔다. 코드에 상태 기계를 만들지 않는다.**

근거:

- 인터뷰는 판단이다 — "이 요청에 골든 퀘스천이 사실상 들어 있는가" 는 문자열 검사로 판정할 수 없다
  (사용자가 문장으로 "설비별 가동률을 알고 싶다" 라고 쓰면 그것이 골든 퀘스천이다)
- 코드로 판정하면 그 판정 규칙이 **세 번째 지시문 소스**가 된다. 이 스펙이 없애려는 것과 같은 종류
- 단독 실행에는 우리 코드가 아예 없다. 코드에 넣으면 US1 에서 동작하지 않는다

### 헤드리스 제약을 어떻게 만족하는가

004 실측: Claude Code 헤드리스(`-p`)에 `AskUserQuestion` 이 제공되지 않고, Codex 도 같다. 그래서
인터뷰는 **산문 되묻기**로 성립해야 한다(FR-054).

스킬 본문의 규칙:

- 물을 것이 있으면 **질문만 하고 턴을 끝낸다.** 도구를 호출하며 답을 기다리지 않는다
- 사용자의 다음 메시지(또는 스티어링)가 답이다 — 004 가 만든 경로를 그대로 쓴다
- 되묻기는 최대 2회. 그 뒤에는 확보한 것으로 진행하되 가정한 내용을 명시한다(FR-055)

### 스튜디오에서 인터뷰가 발동하지 않게 하는 법

폼이 다 채워지면 라벨 블록이 모두 존재하므로 스킬의 점검이 "빠진 것 없음" 으로 끝난다. **별도
플래그를 두지 않는다** — 플래그를 두면 경로마다 동작이 갈라져 FR-053 이 깨진다. 차이는 값의 유무
뿐이어야 한다.

---

## R8 — 참조 자료 경로를 세 환경에서 성립시키는 법

세 환경의 스킬 폴더 위치가 전부 다르다:

| 환경 | 스킬 폴더 |
|---|---|
| 내장(docker/local 샌드박스) | `<workdir>/.skills/ontology-build/` |
| cliagents(호스트) | `<LOCAL_SANDBOX_ROOT>/.claude/skills/ontology-build/` |
| 단독 설치 | `~/.claude/skills/ontology-build/` 또는 플러그인 캐시 |

**결정**: 본문은 참조 자료를 **스킬 폴더 기준 상대 경로**로만 가리킨다 (`references/parser-rules.md`).
절대 경로를 본문에 쓰지 않는다(FR-005).

절대 위치는 **환경 바인딩 블록** 한 개로 런타임이 주입한다:

```
[환경]
스킬 폴더: <경로>
업로드: <경로>
출력: <경로>
```

이것은 지시문이 아니라 **값**이므로 FR-015 와 일관된다. 004 의 `_host_workspace_note()` 가 하던 일을
이 블록이 흡수하고, 그 함수는 사라진다 (이중 소스 제거).

---

## R9 — 레지스트리를 별도 모듈로 두면 004 FR-030 이 강해진다

**확인**: `cliagents_backend.py:606` 이 `from .service import load_skill` 를 한다. 즉 cliagents 경로가
`service.py` 를 import 한다.

`service.py` 는 langchain 을 함수 안에서 지연 import 하므로 지금은 SC-004(langchain 0개)가 통과하지만,
**의존 자체가 사고 위험**이다. `service.py` 상단에 langchain import 가 하나 추가되는 순간 깨진다.

**결정**: `skill_registry.py` 를 표준 라이브러리 + PyYAML 만으로 만들고, cliagents 경로는 그것만
import 한다. `service.py` 의존이 사라진다. 004 FR-030 이 규율에서 **구조**가 된다.

---

## 미해결로 남기는 것

| 항목 | 왜 지금 정하지 않는가 |
|---|---|
| 되묻기 상한의 정확한 값 | 스펙이 "상한이 존재한다" 만 요구한다. 실사용 관찰 후 조정 |
| 참조 자료 파일의 최종 분할 경계 | 내용 이동 중에 자연 경계가 드러난다. 계획에 적은 7개는 출발점 |
| 마켓플레이스 저장소를 ontology-studio 로 할지 별도로 낼지 | 첫 배포는 ontology-studio 저장소로 간다. 다른 서브모듈이 스킬을 내기 시작하면 그때 분리 |
