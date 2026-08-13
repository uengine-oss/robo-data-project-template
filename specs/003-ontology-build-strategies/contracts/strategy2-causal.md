# Contract: 전략 2 — 인텐트 + 데이터에서 인과 발견 (FR-016 ~ FR-026)

**Owner**: ontology-studio · `causal_ontology.py` (오케스트레이션) + `causal_client.py` (계산 위임)

통계는 domain-layer 의 [`POST /whatif/analyze-matrix`](./domain-layer-analyze-matrix.md) 가
한다. ontology-studio 는 행을 모으고, 결과를 가설로 저장하고, 승인분을 관계로 쓴다.

## 파이프라인

```
인텐트 → 타겟·후보 변수 선정(기록)  →  전제 검사  →  행 조회  →  계산 위임  →  가설 저장
   (FR-016)                          (FR-017)     (text2sql)   (domain-layer)   (pending)
                                                                                    │
                                                              사람 승인/거부/반전 ───┘
                                                                     │
                                                              관계 승격 (INFLUENCES_*)
```

## `causal_client.py` — URL 정규화 (constitution 원칙 VI)

`DOMAIN_LAYER_URL` (별칭 `WHATIF_API_URL`) 을 루트 `.env` 에서 읽는다. 기본
`http://127.0.0.1:8001`. **origin 형과 접두사 포함형을 모두** 받는다:

| 입력 | 조립 결과 |
|---|---|
| `http://127.0.0.1:8001` | `http://127.0.0.1:8001/whatif/analyze-matrix` |
| `http://127.0.0.1:8001/` | 동일 |
| `http://127.0.0.1:8001/whatif` | 동일 |
| `http://127.0.0.1:8001/whatif/` | 동일 |

이미 이 저장소에서 발생한 버그다 — `TEXT2SQL_BASE_URL` 이 접두사를 포함하는데 전체 경로를
조립하는 코드가 그걸 몰라 `/text2sql/text2sql/...` 404 → 조용한 폴백 → **"카탈로그에 컬럼이
없다"는 엉뚱한 증상**이 됐다. 정규화는 **한 함수**에만 두고 위 4형태를 단위 테스트로 고정한다.

`localhost` 대신 `127.0.0.1`. api-gateway(9000) 경유 금지.

**서비스 부재 시**: 예외를 전파하지 않고 `{"ok": false, "reason": "stats_service_unavailable"}`
로 접는다 → 전략 추천에서 `"통계 서비스에 연결할 수 없습니다"` 로 표시된다.

## HTTP

### `POST /api/schema/{schema_id}/causal/discover`

```json
{
  "datasource": "itest_pg", "source_schema": "manufacturing",
  "intent": "수율 하락의 원인을 알고 싶다",
  "target": {"class": "MfgDailyEquipment", "field": "yield_rate"},
  "max_lag": 2, "fdr_q": 0.05,
  "dry_run": false
}
```

| 필드 | 설명 |
|---|---|
| `target` | 없으면 인텐트에서 도출. **응답에 도출 결과가 실려 기록된다** (FR-016) |
| `dry_run` | `true` 면 가설 표에 쓰지 않고 결과만 반환 (FR-030) |

후보 변수는 바인딩된 클래스의 수치 속성 전체다. 시간축이 있는 **한 테이블**로 범위를 좁힌다 —
바인딩을 넘는 조인은 이 기능이 소유하지 않는 조인 계획을 요구한다.

**전제 미충족 응답** (FR-017 · SC-005) — 오류가 아니라 판정 결과:

```json
{
  "ok": false, "reason": "insufficient_rows",
  "detail": "행이 3개입니다. max_lag=2 에서는 최소 14개가 필요합니다.",
  "required_rows": 14, "actual_rows": 3,
  "edges": [], "hypotheses_written": 0
}
```

**성공 응답**:

```json
{
  "ok": true,
  "target": "MfgDailyEquipment.yield_rate",
  "target_source": "intent",
  "table": "mfg_daily_equipment",
  "rows_analyzed": 48, "variables": 6,
  "tests_performed": 15, "correction": "benjamini-hochberg", "fdr_q": 0.05,
  "methods_used": ["granger"], "var_fit": "ok", "truncated": false,
  "hypotheses": [
    {
      "source_class": "MfgSensor", "source_field": "vibration",
      "target_class": "MfgDailyEquipment", "target_field": "yield_rate",
      "method": "granger", "strength": 0.62,
      "p_value": 0.0031, "p_value_adjusted": 0.0078, "significant": true,
      "lag": 3, "direction": "negative",
      "decision": "pending"
    }
  ],
  "preserved_decisions": 2,
  "hypotheses_written": 15
}
```

`preserved_decisions` — 재실행에서 사람의 기존 판정을 몇 건 보존했는지. 이것이 SC-009 의
가시적 증거다.

### `POST /api/schema/{schema_id}/causal/decide`

```json
{
  "decisions": [
    {"source_class": "MfgSensor", "source_field": "vibration",
     "target_class": "MfgDailyEquipment", "target_field": "yield_rate",
     "lag": 3, "decision": "approved"}
  ]
}
```

`decision` ∈ `approved` | `rejected` | `reversed`. `reversed` 는 승격 시 source↔target 을
바꾼다.

### `POST /api/schema/{schema_id}/causal/apply`

승인분(`approved`·`reversed`)만 관계로 승격한다.

- 관계명 `INFLUENCES_<TARGET_CLASS>` (UPPER_SNAKE) — FK 유래 `REFERENCES_*` 와 **접두사로
  구분**된다 (FR-021, SC-008).
- 관계 properties: `method` · `lag` · `p_value` · `p_value_adjusted` · `strength` ·
  `direction` · `hypothesis: true`.
- `element_provenance`: `strategy=causal_discovery`, `evidence_kind=statistical`,
  `evidence_ref=<method>/lag=<lag>/p_adj=<p>`.
- **`pending`·`rejected` 는 승격되지 않는다.**
- 기존 클래스를 중복 생성하지 않는다 (FR-004, SC-011) — 관계만 추가한다.

```json
{"promoted": ["INFLUENCES_MFG_DAILY_EQUIPMENT"], "skipped_pending": 13, "skipped_rejected": 1}
```

## 불변식

1. **통계 판정 단계에 LLM 호출 0회** (FR-022). LLM 은 인텐트 → 타겟 도출에만, 그 결과는 기록된다.
2. 같은 데이터·파라미터 재실행 → **같은 엣지 집합** (FR-022, SC-007).
3. 재실행이 `decision`·`decided_at` 을 **덮지 않는다** (SC-009).
4. 전제 미충족이면 `edges` 가 정확히 `[]` (SC-005).
5. 표본이 잘렸으면 `truncated: true` 가 응답과 가설 행에 남는다 (FR-025).
6. 실데이터 조회는 기존 `datasource_exec` 경로 — 새 SQL 조립 경로를 만들지 않는다
   (studio-3 게이트). 행 상한은 호출자가 정하지 못한다.
7. 응답에 접속 정보 없음 (원칙 V).
