# Contract — 스킬 레지스트리

두 백엔드가 스킬에 닿는 **유일한 경로**. 다른 경로가 생기면 이 스펙이 없애려는 divergence 가
되살아난다.

## 위치와 의존

`ontology-studio/backend/src/modules/agent_session/skill_registry.py`

**허용 import**: 표준 라이브러리, `PyYAML`
**금지 import**: `langchain*`, `langgraph`, `deepagents`, `.service`

이유는 두 가지다 — 004 FR-030(cliagents 경로의 langchain 비의존)을 규율이 아니라 구조로 만들고,
현재 `cliagents_backend.py:606` 의 `from .service import load_skill` 의존을 끊는다 (research R9).

## 표면

```python
SKILLS_ROOT: Path            # <ontology-studio>/skills

@dataclass(frozen=True)
class SkillPackage:
    name: str
    description: str
    version: str
    body: str                        # 프론트매터 제거된 지시문
    metadata: dict[str, str]         # 나머지 프론트매터 (allowed-tools, compatibility ...)
    path: Path                       # 스킬 폴더 절대 경로
    files: dict[str, str]            # 스킬 폴더 기준 상대경로 → 내용 (SKILL.md 포함)

class SkillLoadError(Exception): ...

def list_skills() -> list[SkillPackage]      # 폴더 스캔. 이름순
def load_skill(name: str) -> SkillPackage    # 없으면 SkillLoadError
```

### 계약

| # | 규칙 | 근거 |
|---|---|---|
| C1 | 스킬 목록은 **폴더 스캔**으로 결정된다. 이름을 코드에 하드코딩하지 않는다 | FR-013 |
| C2 | 형식 위반은 **예외**다. 건너뛰지 않는다 | FR-014 |
| C3 | `body` 는 프론트매터를 포함하지 않는다 | FR-011 |
| C4 | `files` 는 참조 자료를 포함한다. 배포·동기화가 이것을 쓴다 | FR-042 |
| C5 | `files` 는 `.claude-plugin/` 과 `.mcp.json` 을 **제외**한다 — 런타임 산출물이 아니다 | 관심사 분리 |
| C6 | 캐시해도 되지만 mtime 변화를 감지해야 한다 (개발 중 스킬 수정이 반영돼야 함) | 개발 편의 |

## 소비자

### 내장 경로 (deepagents)

```python
pkg = load_skill("ontology-build")
create_agent(..., system_prompt=pkg.body + environment_binding_block())
```

`SkillsMiddleware` 의 발견 기능은 쓰지 않는다. 이유는 research R2.

### cliagents 경로

```python
pkg = load_skill(self._skill_name)
# 1) 본문은 --append-system-prompt 로 (결정적 적용)
# 2) 폴더는 provider.emit 으로 (참조 자료를 디스크에)
```

### 동기화 (`skill_sync.py`)

```python
def sync_to_sandbox(pkg: SkillPackage, backend) -> str:
    """샌드박스의 <workdir>/.skills/<name>/ 로 복사하고 그 경로를 반환. 멱등."""
```

- `backend` 는 deepagents `BackendProtocol` (docker / local 공통)
- 세션당 1회. 이미 같은 내용이면 다시 쓰지 않는다
- **`uploads/` · `output/` 를 건드리지 않는다** (constitution 원칙 IV)
- 점 접두사 디렉터리를 쓴다 — 파일 패널에 섞이지 않게

## 환경 바인딩 블록

```python
def environment_binding_block(skill_dir: str, uploads: str, output: str) -> str
```

산출:

```
[환경]
스킬 폴더: {skill_dir}
업로드: {uploads}
출력: {output}
```

**값만 담는다.** 설명 문장을 넣으면 그 순간 두 번째 지시문 소스가 된다 (FR-015).
004 의 `_host_workspace_note()` 는 이 함수로 흡수되고 삭제된다.

## 테스트가 강제할 것

| # | 테스트 | 확인 |
|---|---|---|
| T1 | 폴더 추가 → 코드 변경 없이 `list_skills()` 에 나타난다 | SC-006 |
| T2 | 프론트매터 누락/이름 불일치/description 초과 → 각각 폴더를 지목한 예외 | FR-014 |
| T3 | `body` 에 `---` 프론트매터가 남아 있지 않다 | FR-011 |
| T4 | 서브프로세스에서 `skill_registry` 만 import → `sys.modules` 에 langchain 계열 0개 | SC-004 |
| T5 | 두 백엔드가 같은 `body` 문자열을 얻는다 | FR-010, US3-1 |
| T6 | 동기화 후 샌드박스에서 참조 자료를 읽을 수 있다 | FR-042, SC-009 |
