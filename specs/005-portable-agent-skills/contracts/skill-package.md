# Contract — 스킬 패키지 형식

이 계약을 어기는 폴더는 **로드되지 않는다.** 조용히 건너뛰지 않고 오류로 지목한다 (FR-014).

## 폴더 구조

```
skills/<name>/
├── SKILL.md                    # 필수
├── .claude-plugin/
│   └── plugin.json             # 배포용 (런타임은 읽지 않음)
├── .mcp.json                   # 배포용 (런타임은 읽지 않음)
└── references/                 # 선택. 있으면 본문이 가리켜야 한다
    └── *.md
```

`<name>` 규칙 (agentskills.io):

- 1~64자, 소문자 알파벳·숫자·하이픈만
- `-` 로 시작하거나 끝날 수 없다
- `--` 를 포함할 수 없다
- **프론트매터 `name` 과 반드시 일치**

## SKILL.md

```markdown
---
name: ontology-build
description: 문서와 데이터소스에서 온톨로지·지식그래프를 설계하고 구축한다. 사용자가 온톨로지
  구축, 지식그래프 생성, 골든 퀘스천에 답할 스키마 설계를 요청할 때 사용한다.
version: 1.0.0
compatibility: Ontology Studio 백엔드와 agent-bridge MCP 연결이 필요하다.
allowed-tools: ...
---

## 언제 쓰는가
...
```

### 프론트매터

| 필드 | 필수 | 검증 |
|---|---|---|
| `name` | ✓ | 위 규칙 + 폴더명 일치 |
| `description` | ✓ | 1~1024자. **무엇을 + 언제** 를 모두 담는다 |
| `version` | ✓ | semver |
| `compatibility` | 권장 | ≤500자 |
| `allowed-tools` | 권장 | 공백 구분 |
| `license`, `metadata` | – | agentskills.io 를 따른다 |

`description` 이 부실하면 **단독 실행에서 스킬이 선택되지 않는다.** 이것이 유일한 발견 경로다.

### 본문 필수 절

아래 일곱 절이 모두 있어야 한다. 순서는 자유지만 누락은 계약 위반이다.

| 절 | 반드시 답해야 하는 것 |
|---|---|
| 언제 쓰는가 | 이 스킬이 맡는 것과 맡지 않는 것 |
| 전제 | 어떤 도구가 필요한가, 어디서 오는가, **없으면 어떻게 하는가** |
| 권한 경계 | 읽기 전용인가 쓰기 가능한가 |
| 입력 | [input-contract.md](input-contract.md) 의 라벨과 인터뷰 규칙 |
| 작업 경로 | 입력·출력이 어디인가. **환경 바인딩이 없을 때 어떻게 정하는가** |
| 워크플로우 | 단계 순서 + 각 참조 자료를 **언제** 읽는가 |
| 완료 기준 | 무엇이 되면 끝인가 |

### 본문에 쓰면 안 되는 것

| 금지 | 이유 |
|---|---|
| 환경별 절대 경로 (`/workspace/uploads`, `/Users/...`) | FR-005. 세 환경에서 다 다르다 |
| 런타임이 덧붙여야 뜻이 통하는 문장 | FR-003. 파일만 복사한 사용자에게 깨진다 |
| 접속 정보·자격증명 | constitution 원칙 V |
| 참조 자료의 내용 사본 | FR-010. 두 곳에 있으면 갈라진다 |

## 참조 자료

- 위치: `references/*.md` (스킬 폴더 기준 상대 경로)
- 본문이 **읽을 시점을 지목**해야 한다. 목록만 나열하면 읽히지 않는다 (FR-041)
- 내용은 기존 본문에서 **옮겨온 것**이다. 재작성 금지 (FR-043)
- 참조 자료가 없거나 읽히지 않으면 본문만으로 진행하지 말고 **보고**한다 (FR-044)

## 검증 규칙 (레지스트리가 강제)

| # | 규칙 | 실패 시 |
|---|---|---|
| V1 | `SKILL.md` 가 존재한다 | `SkillLoadError: <folder>: SKILL.md 없음` |
| V2 | 프론트매터가 유효한 YAML 이다 | `SkillLoadError: <folder>: 프론트매터 파싱 실패 — <원인>` |
| V3 | `name` 이 규칙을 만족한다 | `SkillLoadError: <folder>: name '<v>' 이 규격 위반 — <사유>` |
| V4 | `name` == 폴더 이름 | `SkillLoadError: <folder>: name '<v>' 이 폴더 이름과 다름` |
| V5 | `description` 이 1~1024자 | `SkillLoadError: <folder>: description <사유>` |
| V6 | `version` 이 존재한다 | `SkillLoadError: <folder>: version 누락` |
| V7 | 본문이 비어 있지 않다 | `SkillLoadError: <folder>: 본문 없음` |

오류 메시지는 **폴더를 지목**한다. "스킬 로드 실패" 만으로는 어느 폴더인지 알 수 없다.
