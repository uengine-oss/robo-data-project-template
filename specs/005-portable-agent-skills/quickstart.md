# Quickstart — 검증 가이드

이 문서는 구현이 끝난 뒤 **무엇을 실행해 무엇을 확인하면 되는가**를 담는다. 구현 코드는 담지 않는다.

constitution 원칙 VII: 단위 테스트만 통과한 것을 "동작한다" 고 보고하지 않는다. 아래 4·5·6절은
**실제 실행**이다.

## 전제

```bash
cd /Users/uengine/ontologic
cat .env | grep -E "BACKEND_(HOST|PORT)|SANDBOX_BACKEND|AGENT_BACKEND|NEO4J"
```

이 머신의 포트 재매핑(5433 / 7475 / 7688 / 8020)과 `SANDBOX_BACKEND` 설정을 먼저 확인한다.
`ontology-studio` 는 `SANDBOX_BACKEND=local` 이 필요하다.

---

## 1. 레지스트리 — 폴더가 곧 목록인가

```bash
cd ontology-studio
uv run pytest backend/tests/modules/agent_session/test_skill_registry.py -v
```

| 기대 | 근거 |
|---|---|
| 두 스킬이 폴더 스캔으로 나온다 | FR-013 |
| 빈 폴더를 하나 추가하면 **폴더를 지목한 오류**가 난다 | FR-014 |
| `body` 에 프론트매터가 없다 | FR-011 |

수동 확인 (SC-006 — 코드 변경 0줄):

```bash
mkdir -p skills/probe-skill && cat > skills/probe-skill/SKILL.md <<'EOF'
---
name: probe-skill
description: 레지스트리가 폴더 추가만으로 스킬을 인식하는지 확인하는 임시 스킬.
version: 0.0.1
---
확인용.
EOF
uv run python -c "from backend.src.modules.agent_session.skill_registry import list_skills; print([s.name for s in list_skills()])"
rm -rf skills/probe-skill
```

`probe-skill` 이 목록에 나와야 한다.

---

## 2. langchain 비의존 — 구조로 강제되는가

```bash
uv run pytest backend/tests/modules/agent_session/ -k "langchain or isolation" -v
```

서브프로세스에서 `skill_registry` 만 import 했을 때 `sys.modules` 에 langchain 계열이 **0개** 여야
한다 (SC-004, research R9).

---

## 3. 단일 소스 — 두 경로가 같은 본문을 읽는가

```bash
# 스킬 본문에 표식 한 줄을 넣는다
echo "<!-- PROBE-7f3a -->" >> skills/ontology-build/SKILL.md

AGENT_BACKEND= uv run python -c "..."            # 내장 경로의 시스템 프롬프트 출력
AGENT_BACKEND=cliagents uv run python -c "..."   # cliagents 경로의 시스템 프롬프트 출력

git checkout skills/ontology-build/SKILL.md
```

양쪽 출력 모두에 `PROBE-7f3a` 가 있어야 한다 (US3-1, SC-003).

중복 사본 확인:

```bash
grep -rn "골든 퀘스천이 모든 것을 결정" --include="*.md" --include="*.py" . | grep -v ".venv"
```

**한 줄만** 나와야 한다. 두 줄이면 FR-010 위반이다.

---

## 4. 스튜디오 경로 회귀 — 004 가 유지되는가

```bash
uv run pytest backend/tests -q                    # SC-004 (417 tests 기준선)
./start-all-services.sh
```

UI 에서:

| 시나리오 | 기대 | 근거 |
|---|---|---|
| 폼을 모두 채우고 구축 시작 | **되묻기 없이** 요약 후 진행. 턴 수가 이전과 같다 | SC-013 |
| 구축 의도를 비우고 시작 | 의도를 묻고 턴이 끝난다 | SC-014 |
| 질의 응답: "EQ-CNC-001 설비의 가동 일수" | 351일. 근거로 데이터소스·테이블·행 수 | 004 SC-002 |
| 파서 작성 단계 | 에이전트가 `references/parser-rules.md` 를 **실제로 읽는다** | SC-009 |

마지막 항목은 도구 호출 로그에서 참조 자료 읽기가 보이는지로 확인한다. 안 읽고 파서를 쓰면
FR-041 이 실패한 것이다.

```bash
AGENT_BACKEND=cliagents EXTERNAL_AGENT_ID=claude-code ./start-all-services.sh
```

같은 네 항목을 cliagents 경로에서 반복한다 (SC-005). 004 의 문서 빌드 시나리오(도로교통법 PDF)도
완주해야 한다.

---

## 5. 단독 실행 — 스튜디오 화면 없이 되는가

프론트엔드를 띄우지 않고 백엔드만 기동한다.

```bash
cp -r ontology-studio/skills/ontology-answer ~/.claude/skills/
cd ~/some-empty-dir && claude
```

| 확인 | 기대 | 근거 |
|---|---|---|
| `/plugin` 또는 스킬 목록 | `ontology-answer` 가 보인다 | FR-002 |
| MCP 연결 | `ontology-studio-answer` 가 연결됨 | FR-022 |
| "EQ-CNC-001 설비의 가동 일수 알려줘" | 스튜디오와 **같은 답** | SC-001 |
| 백엔드를 끄고 같은 질문 | 도구가 없다고 **명시하고 멈춘다.** 추측 답변 없음 | SC-008 |

구축 스킬로 반복 (SC-002, SC-012):

```bash
cp -r ontology-studio/skills/ontology-build ~/.claude/skills/
```

| 입력 | 기대 |
|---|---|
| "온톨로지 만들어줘" (맥락 없음) | 의도·골든 퀘스천·소스를 묻고 턴 종료 |
| 의도 + 골든 퀘스천 + 문서 경로를 모두 준 요청 | 되묻기 없이 요약 후 설계 시작 |
| 의도만 준 요청 | 나머지 둘만 묻는다. 의도를 다시 묻지 않는다 |

마지막으로 완주 확인: 클래스 생성 → 파서 작성 → 적재 → Cypher 검증 리포트. 리포트의 골든 퀘스천이
**입력한 문장 그대로**여야 한다 (SC-015).

---

## 6. 마켓플레이스 설치 — UI 경로가 되는가

```
/plugin marketplace add uengine-oss/ontology-studio
/plugin install ontology-build@ontology-studio
```

5절의 구축 시나리오를 반복한다. 폴더 복사 경로와 **같은 결과**여야 한다 (SC-011).

정합성 검사:

```bash
uv run pytest backend/tests -k distribution -v
```

`version` 3곳 일치, `source` 경로 실재, 모드별 엔드포인트 일치, 자격증명 부재를 확인한다
([distribution.md](contracts/distribution.md) D1~D5).

---

## 7. 뒷정리

```bash
rm -rf ~/.claude/skills/ontology-build ~/.claude/skills/ontology-answer
```

빌드 검증으로 만든 노드는 **클래스 단위로** 지운다. 전역 삭제(`MATCH (n) DETACH DELETE n`)는
데이터 패브릭 카탈로그까지 지운다 (constitution 원칙 IV).

```bash
uv run --with neo4j python ../scripts/inspect_catalog.py
```

카탈로그 계약이 여전히 유효한지 확인하고 끝낸다.
