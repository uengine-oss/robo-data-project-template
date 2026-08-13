# Phase 0 Research: 입력 조합별 온톨로지 구축 전략

플랜의 미결 항목을 실제 코드에서 확인해 닫는다. 각 항목은 **결정 / 근거 / 검토한 대안** 순서.

---

## R1. 전략 2 의 통계 엔진을 어디에 둘 것인가

**결정**: domain-layer 에 **무상태 계산 엔드포인트** `POST /whatif/analyze-matrix` 를 추가하고
ontology-studio 가 행을 실어 호출한다. 통계 코드는 이식하지 않고, 온톨로지 쓰기는 전부
ontology-studio 가 갖는다.

**근거**:
- 통계 엔진이 domain-layer 에만 있다 — `causal_analysis.py`(575줄) +
  `whatif/correlation_engine.py`(471줄) + `model_validator.py`(521줄). `statsmodels>=0.14` ·
  `pandas>=2.0` · `scipy>=1.11` · `numpy<2.0` 도 domain-layer `pyproject.toml` 에만 있다.
  ontology-studio 의 의존성 목록에는 과학 스택이 **하나도 없다**.
- 하이브리드 라우팅이 미묘하다. VAR 피팅 실패를 오류가 아니라 **분류 신호**로 써서
  `_diagnose_collinearity()`(근사 상수열 / 상관 ≥0.999 / 로그-곱셈 적합 R²≥0.99) 를 돌리고
  분해형으로 보낸다. 이 판단 규칙이 두 벌로 갈라지면 어느 쪽이 맞는지 알 수 없다 —
  constitution 원칙 III 이 속성명 divergence 로 경고하는 실패 모드와 같다.
- `CorrelationEngine.analyze(df, node_columns, time_column)` 의 입력이 이미 **평범한
  DataFrame + 데이터클래스 리스트**다. `NodeColumn` 은 `(node_id, node_name, data_source,
  column_name, is_time_column)` 5필드 dataclass 이므로, 행렬을 받아 이 형태로 바꾸는 어댑터가
  얇다. 엔진을 수정할 필요가 없다.

**검토한 대안**:

| 대안 | 기각 이유 |
|---|---|
| **(a) 통계 코드를 ontology-studio 로 이식** (002 의 `schema_extractor.py` → `schema_ontology.py` 전례) | 002 때는 대상이 문자열 매핑 ~50줄이었고, 이식의 **목적이 의도적 divergence**였다 (FR-004: PK·`*_id` 를 제외하지 **않도록** 바꿈). 여기서는 반대로 통계적 **동일성**이 목적이다. 게다가 ontology-studio 에 ≈100MB 과학 스택을 새로 들여야 한다 |
| **(b) 기존 `POST /whatif/discover-edges` 호출** | `schema_id` 로 **domain-layer 자체 스키마 스토어**를 읽는다 (`whatif.py:481`). `ANALYSIS_TARGET_LABELS`(KPI/Measure/Driver)로 필터하고 `_auto_bind_datasources()` 로 바인딩까지 손댄다. 쓰려면 ontology-studio 의 클래스를 domain-layer 스토어로 복제해야 하고 → 공유 그래프에 **두 번째 writer** 가 생긴다. 게다가 domain-layer 온톨로지는 프로세스 메모리에만 있어 재시작 시 유실된다 (installation.md 이슈 #14) |
| **(c) numpy 만으로 Granger 직접 구현** | OLS F-검정 자체는 어렵지 않지만 VAR 의 AIC 기반 lag 선택, 부분상관, 시간적 안정성까지 다시 만들어야 한다. 검증된 구현을 버리고 미검증 사본을 만드는 거래 |

**대가와 완화**: 전략 2 가 domain-layer 기동을 요구한다. 001 FR-003(카탈로그 다운 시 저하
표시)과 같은 패턴으로 처리한다 — domain-layer 가 없으면 전략 2 를 **전제 미충족으로 비활성**
하고 사유를 표시한다(FR-003). 전략 1·3 은 영향받지 않는다.

이 경로는 domain-layer 가 그래프에 **아무것도 쓰지 않는** 순수 계산이므로 이슈 #14(메모리
온톨로지 유실)의 영향을 받지 않는다. `schema_id` 를 보내지 않는 것이 그 이유다.

---

## R2. 전략 1 의 문서 추출을 새로 만들 것인가

**결정**: 새로 만들지 않는다. 전략 1 = **기존 문서 기반 클래스 생성 경로** + **신규 역바인딩
단계**. 이 기능이 추가하는 것은 역바인딩뿐이다.

**근거**:
- 문서 파이프라인이 이미 있다 — `document_indexing/service.py`(85KB) + `ocr_service.py` 가
  OCR·청킹·인덱싱을 하고, `tools.py` 의 `hybrid_search_chunks()` 가 BM25 + 벡터 + RRF 하이브리드
  검색을 제공한다. 결과에 `document_id` · `chunk_ref` · `source_page` 가 실려 있다.
- 그 `chunk_ref` / `source_page` 가 곧 FR-029 가 요구하는 **문서 내 출처 위치**다. 새 필드를
  발명할 필요가 없다.
- 빌드 에이전트(`agent_session/service.py`)가 이미 문서에서 클래스를 만든다. 데이터소스를
  선택하지 않았을 때 그 경로는 카탈로그를 보지 않는다 — **FR-005("추출 단계는 카탈로그를 보지
  않는다")가 이미 성립**한다.

**따라서 전략 1 의 실제 작업 범위**: 생성된 클래스 목록을 받아 카탈로그 테이블 후보를 채점하고
(신규), 확정된 것에 기존 `upsert_class_binding()` 을 호출한다. 문서 파서는 손대지 않는다.

---

## R3. 엔티티 ↔ 테이블 매칭을 무엇으로 채점할 것인가

**결정**: 세 신호를 각각 계산해 가중 합산하고, **근거를 함께 반환**한다. 가중치는
`column 0.6 / type 0.2 / name 0.2`.

| 신호 | 계산 | 왜 이 비중 |
|---|---|---|
| `column_score` | 엔티티 속성명 ↔ 테이블 컬럼명 정규화 매칭. coverage(`matched/len(props)`)와 precision(`matched/len(cols)`)의 조화평균 | **판별력이 가장 큰 신호.** FR-006 이 든 `order` vs `order_log` 를 가르는 것이 이것이다. 조화평균을 쓰는 이유는 200컬럼 테이블이 coverage 만으로 모든 엔티티에 매칭되는 것을 막기 위해 |
| `type_score` | 매칭된 컬럼 중 온톨로지 타입이 일치하는 비율 (`map_sql_type()` 재사용) | 이름이 같아도 타입이 다르면 다른 개념이다. 값 형태 일치의 저비용 대리 지표 |
| `name_score` | 엔티티명·테이블명을 토큰화(snake/camel 분해, 소문자)한 뒤 토큰 집합 유사도 | **가장 약한 신호이므로 0.2.** 실제 케이스가 이유다 — FR-006 의 수락 시나리오는 엔티티 "설비일일점검" 과 테이블 `mfg_daily_equipment` 다. 한글↔영문이라 이름 유사도는 **0** 이고, 컬럼 겹침만이 둘을 잇는다. 이름에 큰 비중을 주면 이 정상 케이스가 탈락한다 |

**판정 규칙** (FR-009, FR-012):

| 상태 | 조건 |
|---|---|
| `auto` | 1위 ≥ 0.70 **이고** (1위 − 2위) ≥ 0.15 |
| `needs_review` | 1위 ≥ 0.40 이지만 위 조건 미달 (점수 부족 또는 동점 근접) |
| `no_match` | 1위 < 0.40 → 엔티티는 미바인딩으로 남는다 (FR-010) |
| `conflict` | 한 테이블이 둘 이상 엔티티의 1위이고 그중 `auto` 급이 2개 이상 |

**결정성**: 정렬 키는 `(-score, table_name)` — 동점에서도 순서가 고정된다. 점수 계산에 LLM 이
없으므로 같은 입력은 같은 순위를 낸다.

**대안**: 임베딩 유사도(`embedding.py` 가 이미 있다)로 한글↔영문 간극을 메우는 안을 검토했다.
**보류**: 채점이 비결정적이 되고(모델 버전에 따라 값이 바뀜) 단위 테스트로 고정할 수 없다.
컬럼 겹침이 이미 그 간극을 메우고 있고, 실패하는 경우는 `needs_review` 로 사람에게 간다 —
조용히 틀리는 것보다 낫다. 임베딩은 후보 **정렬 보조**로 나중에 얹을 수 있다.

---

## R4. 다중비교 보정을 무엇으로 할 것인가 (FR-020)

**결정**: **Benjamini–Hochberg FDR**, 기본 `q = 0.05`. domain-layer 가 보정을 수행해 원시
p-value 와 보정 p-value 를 **둘 다** 반환하고, 검정 횟수와 보정 방법을 함께 싣는다.

**근거**: 변수 20개면 쌍이 190개다. Bonferroni 는 α 를 `0.05/190 = 0.00026` 으로 떨어뜨려
행 수가 수백 규모인 이 도메인에서 **참인 관계까지 전부 죽인다**. BH 는 발견(screening) 목적의
표준이고, 산출물이 확정이 아니라 **사람이 검토하는 가설**(FR-021·FR-023)이라는 이 기능의 성격과
FDR 의 의미가 정확히 맞는다.

**배치**: 보정은 p-value 벡터에 대한 순수 함수이므로 통계 서비스(domain-layer)에 둔다. 문턱값
`q` 는 요청 파라미터로 받아 호출자가 정한다. 응답에 `tests_performed` ·
`correction: "benjamini-hochberg"` · 엣지별 `p_value_adjusted` · `significant` 를 싣는다.

**검토한 대안**: Bonferroni(위 이유로 기각) · 보정 없이 원시 p-value 만 노출(FR-020 위반이고
SC-006 의 셔플 검증을 통과할 수 없다) · ontology-studio 쪽에서 보정(p-value 벡터 전체가 필요한데
그건 통계 서비스가 이미 갖고 있다 — 굳이 옮길 이유가 없다).

---

## R5. 전략 2 의 전제조건을 어떻게 판정하는가 (FR-017)

**결정**: 카탈로그 메타데이터로 **먼저** 검사하고, 통과한 경우에만 행을 가져온다.

| 전제 | 판정 | 미충족 시 보고 |
|---|---|---|
| 시간축 존재 | 컬럼 중 `map_sql_type(...) == "date"` 가 1개 이상 | `"시간축 컬럼이 없습니다"` + 검사한 테이블·컬럼 수 |
| 수치 변수 ≥ 2 | `map_sql_type(...) in {"integer","float"}` 개수 | 발견한 수치 변수 수 |
| 최소 행 수 | 조회 후 실제 행 수 ≥ `max_lag × 2 + 10` | 필요 행 수와 실제 행 수를 **숫자로** |

**근거**: 하한 공식은 기존 구현에서 그대로 가져왔다 —
`causal_analysis.py:294` `min_required = max_lag * 2 + 10`. 다만 기존 코드는 미달 시
`warnings.warn()` 만 하고 **계속 진행한다**. FR-017 은 이를 **경고가 아니라 거부**로 바꾼다.
경고만 하고 엣지를 만들면 그 엣지가 결과에 남아 사실처럼 읽힌다.

행 상한에 걸려 잘렸으면 `truncated: true` 를 응답에 싣는다(FR-025) — 잘린 표본의 통계는
편향되므로 그 사실이 숨으면 안 된다.

---

## R6. 새 서비스 URL 을 어떻게 조립하는가 (constitution 원칙 VI)

**결정**: `DOMAIN_LAYER_URL` (별칭 `WHATIF_API_URL`) 을 루트 `.env` 에서 읽고, **origin 형과
접두사 포함형을 모두** 받는 정규화 함수를 `causal_client.py` **한 곳**에 둔다. 기본값
`http://127.0.0.1:8001`.

```
http://127.0.0.1:8001          → http://127.0.0.1:8001/whatif/analyze-matrix
http://127.0.0.1:8001/         → http://127.0.0.1:8001/whatif/analyze-matrix
http://127.0.0.1:8001/whatif   → http://127.0.0.1:8001/whatif/analyze-matrix
http://127.0.0.1:8001/whatif/  → http://127.0.0.1:8001/whatif/analyze-matrix
```

**근거**: 이 저장소에서 **이미 발생한 버그**다. `TEXT2SQL_BASE_URL` 이 접두사를 포함하는데
전체 경로를 직접 조립하는 코드가 그걸 모르고 붙여 `/text2sql/text2sql/...` 404 → 조용한 폴백 →
"카탈로그에 컬럼이 없다"는 **엉뚱한 증상**으로 나타났다 (constitution 원칙 VI). domain-layer 의
라우터 접두사가 `/whatif` 임을 `main.py:242` 에서 확인했으므로 같은 함정이 그대로 재현될 수 있다.

**포트 근거**: `.env.example:131` `WHATIF_API_PORT=8001`. 게이트웨이(9000)를 경유하지 않는다 —
30초 타임아웃이 이유다.

**가드**: 위 4형태를 고정하는 단위 테스트를 회귀 가드로 둔다. 목 트랜스포트는 우리가 만든 URL 을
그대로 받아주므로(원칙 VII), URL 조립은 **단위 테스트로 문자열을 직접 단언**해야 의미가 있다.

---

## R7. 출처(provenance)를 어디에 저장하는가 (FR-029)

**결정**: SQLite 신규 표 `element_provenance`. Neo4j 에 새 속성을 만들지 않는다.

**근거**: 온톨로지 상태(클래스·관계·바인딩·behavior)가 이미 전부 ontology-studio 의 SQLite 에
있다 — `ontology_schemas` / `schema_classes` / `schema_relationships` /
`class_datasource_bindings` / `class_behaviors`. 출처는 그 상태에 대한 메타데이터이므로 같은
곳에 둔다. 공유 Neo4j 에 새 속성을 쓰면 **새 writer 와 새 divergence** 를 만든다 —
constitution 원칙 III 이 금지하는 방향이다.

**마이그레이션 패턴**: 기존 코드가 쓰는 방식을 그대로 따른다 —
`_ensure_schema_tables()` 안에서 `CREATE TABLE IF NOT EXISTS`, 컬럼 추가는
`try: SELECT ... except: ALTER TABLE`(session_store.py:470~481 이 `binding_kind` 를 그렇게
추가했다). 기존 행의 기본값이 이전 동작을 유지해야 한다.

---

## R8. 인과 가설과 사람의 결정을 어떻게 보존하는가 (FR-023, SC-009)

**결정**: 신규 표 `causal_hypotheses` 에 엣지를 저장하고 `decision` 컬럼
(`pending`|`approved`|`rejected`|`reversed`)을 둔다. 재실행은 **upsert 하되 기존 `decision` 을
덮지 않는다.** 온톨로지 관계로 승격되는 것은 `approved`(및 `reversed`, 방향을 뒤집어) 뿐이다.

**근거**: SC-009("거부한 엣지는 되살아나지 않는다")가 통계 재실행과 정면으로 충돌한다 —
같은 데이터로 다시 돌리면 같은 엣지가 또 나온다(FR-022 가 그걸 요구한다). 그래서 **발견**과
**승인**을 분리해, 재실행이 통계 수치는 갱신하되 사람의 판정은 보존하게 한다.

`pending` 이 관계로 승격되지 않는 것은 FR-030(쓰기 전 계획만)과 FR-023(사람 판정이 최종)의
자연스러운 귀결이다. 발견 호출은 가설 표만 채우고, 별도 적용 호출이 승인분을 관계로 쓴다.

**키**: `(schema_id, source_class, source_field, target_class, target_field, lag)`. lag 를 키에
넣는 이유는 같은 변수 쌍이 서로 다른 시차에서 각각 유의할 수 있고, 그것들이 **다른 가설**이기
때문이다.

---

## R9. 가설 관계를 온톨로지에서 어떻게 구분하는가 (FR-021)

**결정**: 관계 유형명 `INFLUENCES_<TARGET_CLASS>`(UPPER_SNAKE, 002 의 명명 규약과 같은 층),
관계 properties 에 `method` · `lag` · `p_value` · `p_value_adjusted` · `strength` · `direction` ·
`hypothesis: true` 를 싣고, `element_provenance.evidence_kind = 'statistical'` 로 기록한다.

**근거**: domain-layer 에 **선례가 이미 있다.** 인과 링크를 `OntologyType` 간 직접 관계로 쓰지
않고 `OntologyBehavior:Model` 노드를 경유해 `READS_FIELD` / `PREDICTS_FIELD` 로 쓰며
`grangerPValue` · `lag` · `correlationScore` · `importance` 를 **관계 속성으로** 싣는다
(`schema_store.py:771-832`). 즉 "통계 유래 링크는 별도 층 + 수치를 관계에 싣는다" 가 이 플랫폼의
기존 방식이다. 그 형태를 ontology-studio 의 저장 구조(`schema_relationships.properties` JSON)로
옮긴다.

`REFERENCES_<TARGET>`(FK 유래, 002)와 `INFLUENCES_<TARGET>`(통계 유래)이 **이름 접두사로**
갈리므로 조회에서도 구분된다 — SC-008 이 요구하는 "구분해 조회" 가 문자열 접두사 하나로
성립한다.

---

## R10. 전략 추천을 어떻게 결정적으로 만드는가 (FR-001)

**결정**: 입력을 불리언 4개로 환원해 표를 조회하는 순수 함수. I/O 없음.

```
has_documents · has_datasource · has_intent · timeseries_ready
```

`timeseries_ready` 만 카탈로그 조회가 필요하므로, 호출자가 **미리 계산해 넘긴다**(R5 의 전제
검사 결과 재사용). 추천 함수 자체는 인자만 보고 판정하므로 서비스 기동 없이 테스트된다.

`domain-layer` 가 내려가 있으면 `timeseries_ready = False` 로 접히고, 사유가
`"통계 서비스에 연결할 수 없습니다"` 로 구분되어 표시된다 — 데이터가 부적합한 것과 서비스가
없는 것은 사용자가 할 조치가 다르다.

---

## 미해결로 남기는 것

- **임베딩 기반 후보 정렬 보조** (R3) — 결정성을 깨지 않는 형태로 얹을 방법이 정리되면 별도
  변경으로. 지금은 컬럼 겹침 + `needs_review` 로 충분하다.
- **엔티티 하나가 여러 테이블에 걸치는 경우의 자동 분할** — 001 의 바인딩이 테이블 1개
  기준이므로 이 기능에서는 대표 테이블 + `extra_tables`(조인 허용) 까지만 하고, 분할은 사람에게
  남긴다. spec Edge Cases 에 명시돼 있다.
- **전략 2 의 유의 엣지 실측** — 이 환경의 카탈로그(3행)로는 불가능하다. 합성 데이터로
  검증하고 그 한계를 완료 보고에 남긴다 (plan.md 원칙 VII 절).
