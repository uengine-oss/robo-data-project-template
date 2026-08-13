# Quickstart: 입력 조합별 온톨로지 구축 전략 검증

이 기능이 실제로 동작하는지 확인하는 실행 절차. **단위 테스트만 통과한 것을 "동작한다"고
보고하지 않는다** (constitution 원칙 VII).

## 전제

루트 `.env` 하나만 쓴다. **서브모듈 안에 `.env` 를 만들면 루트를 가린다** (원칙 VI).

```bash
cd /Users/uengine/ontologic
grep -E 'NEO4J_URI|TEXT2SQL_BASE_URL|DOMAIN_LAYER_URL' .env
```

이 머신은 포트가 재매핑되어 있다 — Neo4j `7688`, text2sql `8020`, domain-layer `8001`.
`localhost` 대신 `127.0.0.1` 을 쓴다. **api-gateway(9000)를 경유하지 않는다** (30초 타임아웃).

새 변수:

```bash
DOMAIN_LAYER_URL=http://127.0.0.1:8001      # 접두사 포함형(/whatif)도 허용
```

## 1단계 — 단위 테스트 (서비스 기동 불필요)

순수 로직(전략 추천·매칭 점수기·URL 정규화·출처)은 여기서 전부 검증된다.

```bash
cd /Users/uengine/ontologic/ontology-studio
uv run --with pytest --with httpx pytest -q backend/tests
```

```bash
cd /Users/uengine/ontologic/domain-layer
uv run --with pytest --with httpx pytest -q tests/test_analyze_matrix.py
```

**반드시 확인할 항목**:

| 확인 | 왜 |
|---|---|
| `test_causal_client.py` 의 URL 4형태 | 목 트랜스포트는 우리가 만든 URL 을 그대로 받는다. 문자열을 **직접 단언**해야 의미가 있다 (원칙 VI, 실제 발생한 404 버그) |
| `test_entity_matcher.py` 의 한글↔영문 케이스 | 이름 유사도 0 인데 컬럼 겹침으로 매칭되는가. 이름 비중을 올리면 이 정상 케이스가 깨진다 |
| `needs_review`/`conflict` 자동 바인딩 0건 | SC-003 |
| 전제 미충족 시 `edges == []` | SC-005. 경고만 하고 진행하면 엉터리 엣지가 사실처럼 남는다 |

## 2단계 — 카탈로그 계약 재확인

전략 1 의 역검색이 카탈로그를 읽으므로 계약이 유효한지 먼저 본다.

```bash
cd /Users/uengine/ontologic
uv run --with neo4j python scripts/inspect_catalog.py
```

기대: **어긋남 0** (SC-013). 어긋나면 추측으로 고치지 않고 원인을 찾는다.

## 3단계 — 서비스 기동

```bash
# 인프라 + data-fabric(8004) + text2sql(8020) 은 기존 절차
./start-all-services.sh

# domain-layer (전략 2 의 통계 계산)
cd domain-layer && nohup uv run uvicorn app.main:app --host 0.0.0.0 --port 8001 > /tmp/domain-layer.log 2>&1 &
curl -s http://127.0.0.1:8001/health

# ontology-studio backend
cd ontology-studio && uv run uvicorn backend.src.host.main:app --port 8010 &
```

## 4단계 — 전략 추천 (FR-001, SC-010)

```bash
# 데이터소스만 → catalog_schema, causal_discovery 는 인텐트 없음으로 비활성
curl -s 'http://127.0.0.1:8010/api/build-strategy/recommend?datasource=itest_pg&schema=manufacturing' | jq

# 인텐트 추가 → 시계열 전제에 따라 갈린다
curl -s 'http://127.0.0.1:8010/api/build-strategy/recommend?datasource=itest_pg&schema=manufacturing&intent=수율%20하락%20원인' | jq
```

기대: 같은 질의를 두 번 하면 **완전히 같은 응답** (SC-010). 비활성 전략에 사유가 붙어 있고,
`host`/`port`/`password` 가 **없다** (원칙 V).

## 5단계 — 전략 1 역바인딩 (SC-001 ~ SC-004)

문서 기반으로 클래스가 만들어진 스키마가 있어야 한다.

```bash
SCHEMA_ID=<문서로 만든 스키마 id>

# 미리보기 — 아무것도 저장하지 않는다 (FR-030)
curl -s -X POST http://127.0.0.1:8010/api/schema/$SCHEMA_ID/reverse-bind/preview \
  -H 'Content-Type: application/json' \
  -d '{"datasource":"itest_pg","source_schema":"manufacturing"}' | jq

# 확정
curl -s -X POST http://127.0.0.1:8010/api/schema/$SCHEMA_ID/reverse-bind/apply \
  -H 'Content-Type: application/json' \
  -d '{"datasource":"itest_pg","source_schema":"manufacturing","bindings":[],"include_auto":true}' | jq
```

확인:

| 기대 | 근거 |
|---|---|
| 후보에 `evidence.matched_columns` 가 실려 있다 | FR-008 — 점수만으로는 검토 불가 |
| `needs_review`/`conflict` 는 `bindings` 없이 바인딩되지 않았다 | SC-003 |
| `unbound_entities` 의 엔티티가 온톨로지에 **여전히 존재**한다 | SC-002 — 데이터 없다고 지우지 않는다 |
| `uncovered_tables` 가 보고된다 | FR-011 |
| 미리보기만으로는 저장이 없다 | FR-030 |

바인딩된 엔티티로 실제 행이 나오는지 (SC-001):

```bash
curl -s -X POST http://127.0.0.1:8010/api/schema/classes/설비일일점검/fetch \
  -H 'Content-Type: application/json' -d '{"limit":5}' | jq '.row_count'
```

기대: **1 이상**. 그리고 그 클래스의 저장된 인스턴스 수는 **0** (SC-012).

## 6단계 — 전략 2 인과 발견

```bash
curl -s -X POST http://127.0.0.1:8010/api/schema/$SCHEMA_ID/causal/discover \
  -H 'Content-Type: application/json' \
  -d '{"datasource":"itest_pg","source_schema":"manufacturing","intent":"수율 하락 원인","max_lag":2}' | jq
```

**이 환경에서의 기대**: `itest_pg`/`manufacturing` 은 실측 3행이므로 최소 행 수(14)에 미달한다.
따라서 정상 결과는

```json
{"ok": false, "reason": "insufficient_rows", "required_rows": 14, "actual_rows": 3, "edges": []}
```

이것이 **성공적인 검증**이다 (FR-017, SC-005). 엣지가 나오면 오히려 버그다.

### 유의 엣지 경로 (합성 데이터)

실데이터로는 확인할 수 없으므로 계산 엔드포인트를 직접 친다:

```bash
curl -s -X POST http://127.0.0.1:8001/whatif/analyze-matrix \
  -H 'Content-Type: application/json' \
  -d @specs/003-ontology-build-strategies/contracts/sample-matrix.json | jq '.edges, .tests_performed, .correction'
```

확인: `tests_performed` 가 노출되고 `correction == "benjamini-hochberg"`, 각 엣지에
`p_value_adjusted >= p_value` (FR-020).

**셔플 검증** (SC-006) — 우연을 인과로 승격하지 않는지:

```bash
uv run --with pytest pytest -q domain-layer/tests/test_analyze_matrix.py -k shuffle
```

### 결정 보존 (SC-009)

```bash
# 거부
curl -s -X POST http://127.0.0.1:8010/api/schema/$SCHEMA_ID/causal/decide \
  -H 'Content-Type: application/json' \
  -d '{"decisions":[{"source_class":"MfgSensor","source_field":"vibration","target_class":"MfgDailyEquipment","target_field":"yield_rate","lag":3,"decision":"rejected"}]}'

# 재실행 후에도 rejected 인가
curl -s -X POST http://127.0.0.1:8010/api/schema/$SCHEMA_ID/causal/discover -H 'Content-Type: application/json' -d '{...}' \
  | jq '.preserved_decisions, (.hypotheses[] | select(.lag==3) | .decision)'
```

기대: `"rejected"` 유지, `preserved_decisions >= 1`.

## 7단계 — 관계 구분 확인 (SC-008)

```bash
curl -s http://127.0.0.1:8010/api/schema | jq '[.relationships[].name] | map(select(startswith("INFLUENCES_") or startswith("REFERENCES_")))'
```

기대: FK 유래는 `REFERENCES_*`, 통계 유래는 `INFLUENCES_*` — 접두사로 갈린다.

## 8단계 — 마지막 계약 재확인

```bash
cd /Users/uengine/ontologic && uv run --with neo4j python scripts/inspect_catalog.py
```

전략을 돌린 뒤에도 **어긋남 0** 이어야 한다 (SC-013). 전역 삭제를 하지 않았으므로 카탈로그가
살아 있어야 한다 (원칙 IV) — `POST /api/neo4j/clear-all` 을 테스트에서 쓰면 카탈로그가 지워져
이 단계가 실패한다.

## 알려진 한계

- **전략 2 의 유의 엣지는 실데이터로 검증되지 않는다.** 이 환경의 카탈로그가 3행이다. 합성
  데이터로만 확인 가능하며, 완료 보고에서 이 구분을 유지한다.
- 프론트엔드 패널(`BindingCandidatePanel` · `CausalEdgeReviewPanel`)은 백엔드 계약이 고정된
  뒤에 붙는다. 위 절차는 전부 HTTP 로 검증 가능하다.
