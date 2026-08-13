# Contract — 배포 (플러그인 · 마켓플레이스 · MCP)

사실 근거: `code.claude.com/docs/en/{skills,plugins-reference,plugin-marketplaces,mcp}` (2026-08-02 조회).
상세는 [research.md](../research.md) R5.

두 경로를 지원한다 (FR-024). **같은 폴더**를 쓴다 (FR-025).

## 경로 A — 폴더 복사

```bash
cp -r ontology-studio/skills/ontology-build ~/.claude/skills/
```

`~/.claude/skills/<name>/SKILL.md` 가 개인 스킬의 표준 위치다. 폴더 안에
`.claude-plugin/plugin.json` 이 있으므로 Claude Code 는 이것을 `<name>@skills-dir` 플러그인으로
로드하고, **`.mcp.json` 도 함께 따라온다.** 즉 복사 한 번으로 도구 연결까지 온다.

프로젝트 범위로 쓰려면 `.claude/skills/` 에 두고 워크스페이스 신뢰를 수락한다.

## 경로 B — 마켓플레이스 설치

```
/plugin marketplace add uengine-oss/ontology-studio
/plugin install ontology-build@ontology-studio
```

### `ontology-studio/.claude-plugin/marketplace.json`

```json
{
  "name": "ontology-studio",
  "owner": { "name": "uEngine", "url": "https://github.com/uengine-oss" },
  "description": "Ontology Studio 온톨로지 구축·질의 스킬",
  "plugins": [
    {
      "name": "ontology-build",
      "source": "./skills/ontology-build",
      "description": "문서·데이터소스에서 온톨로지와 지식그래프를 구축한다",
      "version": "1.0.0"
    },
    {
      "name": "ontology-answer",
      "source": "./skills/ontology-answer",
      "description": "구축된 온톨로지를 조회해 질문에 답한다 (읽기 전용)",
      "version": "1.0.0"
    }
  ]
}
```

필수 필드는 `name` · `owner` · `plugins[]` 이고, 각 항목은 최소 `name` + `source` 다.

**이름 주의**: 마켓플레이스 `name` 은 공개된 식별자이며 사용자당 하나만 등록된다. 예약어 목록
(`agent-skills`, `anthropic-*` 등)을 피한다.

### `skills/<name>/.claude-plugin/plugin.json`

```json
{
  "name": "ontology-build",
  "version": "1.0.0",
  "description": "문서·데이터소스에서 온톨로지와 지식그래프를 구축한다",
  "author": { "name": "uEngine" },
  "repository": "https://github.com/uengine-oss/ontology-studio",
  "license": "Apache-2.0"
}
```

`skills` 필드를 쓰지 않는다 — **플러그인 루트의 `SKILL.md` 한 장**이 그 플러그인의 스킬이 되는 것이
문서화된 동작이다. 컴포넌트를 `.claude-plugin/` 안에 두지 않는다 (문서가 경고로 명시).

## MCP 연결

### `skills/<name>/.mcp.json`

```json
{
  "mcpServers": {
    "ontology-studio-build": {
      "type": "http",
      "url": "${ONTOLOGY_STUDIO_URL:-http://127.0.0.1:8000}/mcp/agent-bridge/build/"
    }
  }
}
```

질의 스킬은 `.../agent-bridge/answer/` 를 쓴다.

| 규칙 | 근거 |
|---|---|
| `${VAR:-default}` 확장을 쓴다 | 포트·호스트가 사용자마다 다르다. 문서화된 기능 |
| 기본값은 `127.0.0.1` | constitution 원칙 VI — 바인드 주소를 접속 주소로 쓰지 않는다. `localhost` 는 `::1` 로 먼저 풀린다 |
| 자격증명을 담지 않는다 | constitution 원칙 V |
| 모드마다 **플러그인을 나눈다** | 한 플러그인에 둘을 담으면 질의 세션에도 쓰기 도구가 올라간다. 004 FR-012 위반 |

## 갱신과 제거

| 요구 | 방법 |
|---|---|
| 버전 확인 (FR-007) | `SKILL.md` 프론트매터 `version` · `plugin.json` `version` · 마켓플레이스 항목 `version` **셋이 같아야 한다** |
| 재설치가 완전 대체 (FR-023) | 마켓플레이스 경로는 플러그인 캐시를 교체한다. 폴더 복사 경로는 `rm -rf` 후 복사를 문서에 명시한다 |
| 이름 변경/제거 | 마켓플레이스의 `renames` 필드 |

## 설치 문서가 반드시 담아야 하는 것 (FR-021, FR-022)

1. **스튜디오 백엔드가 떠 있어야 한다** — 도구가 거기서 온다. 이 전제를 숨기지 않는다
2. 두 설치 경로와 각각의 갱신·제거 방법
3. MCP URL 을 바꾸는 법 (`ONTOLOGY_STUDIO_URL`)
4. 연결 확인 방법과, 연결이 안 됐을 때 스킬이 무엇을 하는지 (멈추고 안내한다)
5. build 와 answer 를 **함께 설치했을 때의 권한 의미**

## 테스트가 강제할 것

| # | 확인 | 근거 |
|---|---|---|
| D1 | 세 곳의 `version` 이 일치한다 | FR-007 |
| D2 | `marketplace.json` 의 모든 `source` 경로가 실재한다 | 설치 실패 방지 |
| D3 | `.mcp.json` 의 엔드포인트가 모드와 일치한다 (build 스킬이 answer 를 가리키지 않는다) | 004 FR-012 |
| D4 | `.mcp.json` 에 자격증명 형태의 키가 없다 | 원칙 V |
| D5 | 배포 폴더와 저장소 `skills/<name>/` 이 동일하다 (가공 사본 없음) | FR-025, SC-011 |
