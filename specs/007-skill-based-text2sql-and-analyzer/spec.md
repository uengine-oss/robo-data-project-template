# Feature Specification: 스킬 기반 text2sql 과 메타데이터 증강 분석기

**Feature Branch**: `007-skill-based-text2sql-and-analyzer`

**Created**: 2026-08-03

**Status**: Draft · **T1~T4 구현 완료 (2026-08-03)** — 구현 상태와 무엇이 미확인인지는
아래 §구현 상태 (2026-08-03) 절에 있다. 증거:
[`docs/business/evidence/12-embedding-indexing/`](../../docs/business/evidence/12-embedding-indexing/README.md)

**Status**: Draft — **2026-08-03 개정.** 사업 결정으로 임베딩의 지위가 바뀌었다
(선택 → **데이터소스 질의의 필수 선행 조건**) 그리고 색인의 자리가 바뀌었다
(text2sql 부팅 부수효과 → **메타데이터 증강 단계**). AD-4·AD-5 를 다시 썼고 AD-5b(재색인)을
신설했다. T 트랙이 5단계에서 9단계로 늘었다. 개정 이유와 뒤집힌 판단은 §개정 기록에 있다.

**Input**: 사업 결정 [`docs/business/agent-backend-and-llm-access.md`](../../docs/business/agent-backend-and-llm-access.md)
§*"`cliagents` 에서는 text2sql·ingestion 을 스킬로 돌린다"* — *"이것이 이 문서의 핵심 결정이다."*
그 문서의 「다음 작업」 2번이 이 스펙을 **spec 007 후보**로 지목했다.
참고 구현: [`uengine-oss/robo-skill-analyzer`](https://github.com/uengine-oss/robo-skill-analyzer)
(조사 시점 로컬 클론 `/tmp/robo-skill-analyzer`).

## 관계

[004](../004-pluggable-agent-backend/spec.md) 가 **누가 에이전트를 실행하는가**를 교체 가능하게
만들었고, [005](../005-portable-agent-skills/spec.md) 가 **그 지시문을 스튜디오 밖으로 꺼냈다.**
이 스펙은 그 교체 범위를 **ontology-studio 밖의 두 서비스**로 넓힌다.

004 가 남긴 경계가 정확히 문제의 자리다. 004 는 "외부 CLI 경로는 `OPENAI_API_KEY` 를 쓰지 않는다 —
CLI 가 자기 모델을 들고 온다"(constitution 원칙 VI)를 성립시켰는데, 그 문장은 **스튜디오 백엔드
안에서만** 참이다. `neo4j-text2sql` 과 `robo-data-analyzer` 는 에이전트 백엔드와 무관하게 자기
몫의 LLM·임베딩을 직접 부른다. 그래서 `AGENT_BACKEND=cliagents` 를 고른 사용자도 여전히 LLM 키를
넣어야 하고, 안 넣으면 스택이 절반만 선다.

루트에 두는 이유는 판단 기준 그대로다 — 되돌리면 계약이 깨지는 것이 넷 있다:

- **루트 `.env` 키의 의미가 바뀐다.** `OPENAI_API_KEY` 가 "필수"에서 "임베딩 제공자 중 하나의
  자격증명"으로 강등되고, `EMBEDDING_PROVIDER` 가 앱 전역 설정이 된다. 이 키를 읽는 서비스가 셋이다.
- **`data-fabric` 의 추출 파이프라인에 단계가 하나 늘어난다.** 지금 임베딩 코드가 **0건**인
  서비스가 색인 책임을 갖는다. 그리고 그 결과를 `neo4j-text2sql` 이 소비한다 — 두 저장소가 함께
  지켜야 하는 계약이고, 되돌리면 질의가 죽는다.
- **벡터 노드 속성 계약.** 벡터 옆에 모델·차원 **지문**이 붙는다. 쓰는 쪽(data-fabric)과 읽는 쪽
  (text2sql)이 같은 속성명을 봐야 한다 — constitution 원칙 III 이 경고하는 divergence 가
  새로 생길 수 있는 지점이다.
- **`POST /text2sql/react` 의 NDJSON 이벤트 계약.** ontology-studio 가 스트리밍으로 소비한다
  (`ontology-studio/backend/src/modules/ontology/datasource_exec.py:674`).
- **Neo4j 벡터 인덱스의 차원 계약.** 임베딩 제공자를 바꾸면 5개 인덱스를 다시 만들어야 한다.
  data-fabric 이 쓴 카탈로그와 같은 그래프에 있다.
- **`POST /robo/analyze` 의 NDJSON 계약과 분석기 Neo4j 스키마.** api-gateway·데스크톱 셸·
  robo-data-frontend·robo-data-catalog 가 함께 지킨다.

001~003 이 **무엇을 만드는가**, 004 가 **누가 만드는가**, 005 가 **지시문이 어디 있는가**였다면,
007 은 **그 셋을 ontology-studio 밖의 서비스에도 적용한다.**

---

## 배경 — 왜 지금인가

### 첫 실행이 깨진 자리가 그대로 있다

`agent-backend-and-llm-access.md` 는 2026-08-02 에 결정을 내리고 2026-08-03 에 구현 현황을
갱신했다. 그 갱신의 세 번째 항목:

> **text2sql 은 여전히 자기 몫의 LLM·임베딩을 직접 부른다.** 이 문서의 핵심 결정은 **미착수**다.
> 실제로 이번 실행에서도 text2sql 컨테이너는 키가 없어 기동에 실패했고, 임시 조치(비치명 강등)가
> 그대로 동작해 앱은 떴다. 즉 첫 실행 경험은 "선택 화면 → 앱 진입" 까지 깨지지 않지만,
> **데이터소스 자연어 질의는 여전히 비활성**이다.

같은 날 증거 11 이 분석 파이프라인에서 같은 종류의 실패를 기록했다 —
[`docs/business/evidence/11-analysis-pipeline/README.md`](../../docs/business/evidence/11-analysis-pipeline/README.md)
는 3단계 `scan_codebase` 에서 `openai.AuthenticationError: invalid_api_key` 로 멈췄고, 4~7단계와
임베딩·요약에 **도달하지 못했다**고 적었다.

두 서비스가 같은 이유로 같은 날 멈췄다. 이것이 이 스펙이 두 리팩터링을 한 스펙으로 묶는 이유다.

### 그런데 크기가 다르고, 그래서 방식이 다르다

| | text2sql | analyzer |
|---|---|---|
| 지금 코드 | `app/react/` **16,485줄 / 75 파일**, `controller.py` 1,865줄 | 파이썬 **13,317줄**, LangGraph 7~12단계 |
| 소비자 | `direct-sql` 을 domain-layer·ontology-studio·catalog 가 부름 — **바꾸면 안 되는 표면이 큼** | `POST /robo/analyze` **하나** |
| 참고 구현 | 없음 | **robo-skill-analyzer** 가 이미 있음 |
| 방식 | **제자리 리팩터링** (새 저장소 없음) | **새 마이크로서비스 추가 후 교체** |

↳ `app/react/` 규모는 `find app/react -name '*.py' | xargs wc -l` 실측. 분석기 규모는
`/Users/uengine/ontologic/robo-data-analyzer` 에서 `.venv` 제외 실측.

---

## 현재 코드 현실 — 조사 결과

**추측 없이 읽어서 확인한 것만 적었다.** 확인하지 못한 것은 §미결정 항목으로 내렸다.

### CR-1. ReAct 루프는 이미 두 곳으로 나뉘어 있다 — 소유권이 깨진 상태다

후보 생성·수리 루프는 컨트롤러에, `context_refresh` 루프는 **라우터**에 있다.

| 루프 | 위치 |
|---|---|
| 후보 생성 → 검증 → 채점 → 수리 → 탈출 | `neo4j-text2sql/app/react/controller.py:1426-1813` |
| 컨텍스트 보강 재시도(`context_refresh`) | `neo4j-text2sql/app/routers/react.py:1739` 이하 |
| 인프라 실패 감지 | `neo4j-text2sql/app/routers/react.py:1676` (`_is_infra_fail_reason`, 라우터 내부 클로저) |
| 최종 SQL 실행 | `neo4j-text2sql/app/routers/react.py:1987-2010` — 컨트롤러의 preview 와 **중복 실행 경로** |

스킬로 옮기기 전에 이 이중 소유권을 먼저 정리해야 한다. 지금 상태로는 "컨트롤러를 걷어낸다"가
루프의 절반만 걷어낸다는 뜻이 된다.

### CR-2. 도구는 사실상 두 개뿐이고, 결정론 부분이 이미 상당히 떨어져 있다

레지스트리에 등록된 도구는 둘이다 — `neo4j-text2sql/app/react/tools/__init__.py:18-21`
(`TOOL_HANDLERS = {"build_sql_context", "validate_sql"}`).

그런데 그 두 도구 **안쪽**에 이미 순수 함수로 분리된 결정론 모듈이 13개 있다:

| 기능 | 위치 | LLM |
|---|---|---|
| SQL 안전 검증 (sqlglot, SELECT-only, 깊이 제한) | `app/core/sql_guard.py:40` | 없음 |
| SQL 실행 / preview (행 상한은 cursor fetch) | `app/core/sql_exec.py:85,132` | 없음 |
| MindsDB dialect 변환 | `app/core/sql_transform.py:366,224,294` | 없음 |
| MindsDB passthrough 준비 | `app/core/sql_mindsdb_prepare.py:205` | 없음 |
| 규칙기반 SQL 자동수리 (stdlib 전용) | `app/react/utils/sql_autorepair.py:385` | 없음 |
| 카탈로그 FK·관계·중요도 Cypher | `app/react/tools/neo4j_utils.py:16,46,155,210,288` | 없음 |
| 벡터·키워드 테이블/컬럼 검색 Cypher | `app/react/tools/build_sql_context_parts/neo4j.py` (907줄) | 없음 |
| `validate_sql` 결과 파싱 | `app/react/controller.py:328` (`parse_validate_sql`, 라우터도 재사용) | 없음 |
| rubric 점수·수용 판정 | `app/react/rubric_judge.py:216` (`compute_score_and_accept`) | **없음** |
| 컨텍스트 통계 | `app/react/controller.py:248` | 없음 |
| EXPLAIN 플랜 수집 | `app/react/utils/db_query_builder/postgresql.py` | 없음 |
| 인메모리 질의 캐시 (LRU 200 / TTL 3600) | `app/core/query_cache.py` | 없음 |
| preview NULL 통계 | `app/react/controller.py:539` | 없음 |

**rubric 채점이 이미 결정론이라는 점이 이 설계의 핵심 근거다.** LLM 은 각 요구사항에
PASS/FAIL/UNKNOWN 만 답하고, 점수와 수용 여부는 파이썬이 계산한다. 즉 "판단은 지시문, 계산은
도구" 라는 경계가 이 저장소 안에 **이미 한 번 그어져 있다.** 이 스펙은 그 선을 나머지에
확장하는 것이지 새로 발명하는 것이 아니다.

### CR-3. LLM 호출 15곳은 전부 `generators/` 한 층에 캡슐화되어 있고, 프롬프트 입력은 전부 JSON 이다

`app/react/prompts/__init__.py:1-6` 의 `get_prompt_text()` 는 **변수 치환을 하지 않는다.**
모든 프롬프트는 `SystemMessage` 로 통째 주입되고, 입력은 `HumanMessage` 에 JSON 문자열로 들어간다
(예: `app/react/generators/controller_sql_candidates_generator.py:165-169`).

즉 **"system = 규칙, human = 값"** 구조가 이미 성립해 있다. constitution 의 *"지시문과 값을 섞지
않는다"* 를 프롬프트 층은 이미 지키고 있다. 유일한 예외가 레거시 `app/core/prompt.py:10-47`
(`ChatPromptTemplate` f-string 치환) 인데, 이것은 폐기 대상 `/ask` 경로 전용이다.

**따라서 프롬프트 → 스킬 이식의 마찰은 형식이 아니라 분량과 중복이다.**

### CR-4. 프롬프트 15개 중 3개는 호출자가 없다 (데드)

| 파일 | 상태 | 근거 |
|---|---|---|
| `app/react/prompts/vector_hyde_rank_table_profile_prompt.md` (69줄) | 데드 — `table_profile_prompt.md` 의 상수도 도메인 하드코딩 구버전 | 호출부 grep 0건 |
| `app/react/prompts/llm_xml_reprint_prompt.md` (9줄) | 데드 | 호출부 grep 0건 |
| `app/react/generators/hyde_schema_variant_generator.py` (203줄) | 데드 (프롬프트는 `hyde_schema_prompt.md` 재사용) | 호출부 grep 0건 |

컨트롤러 안에도 데드코드가 있다 — `score_sql`(`controller.py:655`)과 그것만이 참조하는 6개 함수
약 **300줄**. rubric judge 로 대체된 구 결정론 스코어러다. `compact_build_sql_context`
(`controller.py:858`)는 이름과 달리 **no-op** 이다.

합계 약 900줄이 지금 아무 일도 하지 않는다.

### CR-5. **색인 단계가 어디에도 없다** — 이것이 이 스펙의 가장 큰 발견이다

메타데이터 추출은 data-fabric 이 한다(constitution 원칙 I —
`POST /api/datasources/{name}/extract-metadata-sync`). 그런데:

> **`data-fabric/backend/app` 전체에 임베딩 코드가 0건이다.**
> ↳ `grep -rniE "embedding|embed_text|embed_batch" data-fabric/backend/app --include="*.py"` → **0**
> (`openai` 문자열 4건은 전부 `schemas/datasource.py` 의 데이터소스 **유형 이름**이다)

즉 **데이터소스를 등록하고 메타데이터를 추출해도 테이블·컬럼 벡터는 생기지 않는다.**
추출과 색인이 분리돼 있고, 색인 쪽이 비어 있다.

그러면 벡터는 어디서 오는가. 인덱스별로 실제 writer 를 전수 확인했다:

| 인덱스 | 벡터 속성 | **쓰는 곳** | 실질 상태 |
|---|---|---|---|
| `text_to_sql_table_vec_index` | `(:Table).text_to_sql_vector` | `app/core/text2sql_table_vectorizer.py:270` — **text2sql 기동 잡**(`ensure_text_to_sql_table_vectors`, `app/main.py:72`) | 질의 서비스를 **부팅해야** 채워진다 |
| `table_vec_index` | `(:Table).vector` | `app/routers/schema_edit.py:111` — **사람이 설명을 손으로 고칠 때만** | 사실상 **빈 채로 남는다** |
| `column_vec_index` | `(:Column).vector` | `app/routers/schema_edit.py:194` — 같음 | 사실상 **빈 채로 남는다** |
| `query_question_vec_index` / `query_intent_vec_index` | `(:Query).vector_*` | `app/core/cache_postprocess.py:1817` — 질의 후처리 | 질의를 해야 생긴다 |

**정확한 진단은 "채우는 코드가 없다"가 아니라 이것이다** — 색인이 **추출 파이프라인의 단계가
아니라 질의 서비스 부팅의 부수효과**로 존재한다. 그리고 레거시 두 인덱스는 그 부수효과조차
받지 못한다.

결과 셋:

1. **text2sql 기동이 임베딩(그리고 LLM)에 묶인다.** `ensure_text_to_sql_table_vectors` 는
   테이블마다 `table_profile` LLM 호출 + 임베딩을 도는 **블로킹** 작업이다
   (`app/main.py:72`, 동시성 30 / 배치 128). 키가 없으면 기동 자체가 실패한다.
2. **비어 있는 것이 정상 상태로 취급되고 있다.** `app/core/text2sql_runtime_repair.py:124-136`:

   ```python
   # Cold start heuristic:
   # - At least one table exists in graph
   # - Every table misses text_to_sql_vector
   # - Every table misses text_to_sql_embedding_text
   ```
   ↳ `table_missing_vector` · `table_missing_embedding_text` 를 세는 Cypher 가
   `text2sql_runtime_repair.py:58` 에 있다. **코드가 이 결핍을 이미 알고 있고, 감지 로직까지
   갖췄으면서, 채우는 책임은 아무 데도 없다.**
3. **질의 시점에는 임베딩이 반드시 필요하다.** 질문을 벡터로 만들어야 인덱스를 검색할 수 있다 —
   `app/routers/ask.py:115`, `app/routers/watch_agent.py:81`
   (`await embedding_client.embed_text(request.question)`), 그리고 ReAct 경로의
   `build_sql_context_parts/orchestrator.py:116-117`.

**따라서 임베딩은 "있으면 좋은 것"이 아니라 데이터소스 질의 경로의 선행 조건이다.**
필드 임베딩이 없으면 text2sql 은 그 필드를 찾을지 말지 판단할 단계에 **도달하지 못한다.**

### CR-5b. 임베딩은 OpenAI 공식 엔드포인트에 고정되어 있다 — 로컬 LLM 을 써도 이 키가 필요하다

```python
@lru_cache(maxsize=1)
def _get_openai_async_client() -> AsyncOpenAI:
    api_key = _require_api_key(provider="openai")
    return AsyncOpenAI(api_key=api_key)     # ← base_url 인자가 없다
```
↳ `neo4j-text2sql/app/core/llm_factory.py:116-118`

`EmbeddingClient.__init__` 은 `embedding_provider` 가 `openai` 가 아니면
`NotImplementedError` 를 던진다 — `app/core/embedding.py:13-17`.

**결과 세 가지.**

1. `LLM_PROVIDER=openai_compatible` 로 로컬 LLM 을 붙여도 **임베딩은 반드시 OpenAI 로 나간다.**
   `agent-backend-and-llm-access.md` 가 내세운 *"데이터가 이 PC 를 떠나지 않는다"* 는 임베딩
   경로에서 이미 깨져 있다. 이것은 이번 조사에서 처음 확인된 사실이다.
2. **"로컬 임베딩 모델" 선택지는 지금 구조에서 화면에만 존재할 수 있다.**
   `embedding.py:13-17` 이 `openai` 가 아닌 값을 **예외로 막는다.** 이 두 줄(제약 + `base_url`
   누락)을 고치지 않으면 어떤 설정 UI 를 만들어도 동작하지 않는다.
3. 기동 sanity check 가 `embedding_provider=="openai"` 이면 **무조건** 돈다
   (`app/sanity_checks/checks/check_openai.py:41-48`). 기본값이 `openai` 이므로
   `LLM_PROVIDER=google` 인 사용자도 `OPENAI_API_KEY` 가 필요하다. 하나라도 실패하면
   `RuntimeError` 로 **서버가 뜨지 않는다** (`app/sanity_checks/runner.py:14`).
   이것이 데스크톱 크래시 루프의 정확한 원인이다.

벡터는 별도 벡터 DB 없이 **Neo4j 인덱스 5개**에 있다. 전부 `cosine`, 차원은
`EMBEDDING_DIMENSION`(기본 1536):

| 인덱스 | 노드.속성 | 생성 | 조회 |
|---|---|---|---|
| `text_to_sql_table_vec_index` | `(:Table).text_to_sql_vector` | `app/core/neo4j_bootstrap.py:126` | `build_sql_context_parts/neo4j.py:86` — ReAct 정식 경로 |
| `table_vec_index` | `(:Table).vector` | `neo4j_bootstrap.py:113` | `app/core/graph_search.py:70` — 레거시 `/ask` |
| `column_vec_index` | `(:Column).vector` | `neo4j_bootstrap.py:139` | `neo4j.py:432,575` |
| `query_question_vec_index` | `(:Query).vector_question` | `app/models/neo4j_history.py:104` | `neo4j.py:656` |
| `query_intent_vec_index` | `(:Query).vector_intent` | `neo4j_history.py:115` | `neo4j.py:682` |

### CR-5c. 벡터에 **지문이 없다** — 무엇으로 만들어졌는지 알 방법이 없다

위 표의 어떤 속성 옆에도 *어떤 모델·어떤 차원으로 만들었는지*가 기록되지 않는다.
`text2sql_table_vectorizer.py:270-273` 이 함께 쓰는 것은
`text_to_sql_profile` · `text_to_sql_embedding_text` · `text_to_sql_updated_at` 뿐이고,
모델명도 차원도 없다.

`EMBEDDING_DIMENSION` 은 **설정값**이지 데이터에 붙은 사실이 아니다. 그래서:

- 모델을 바꾸면 기존 벡터가 무효가 되는데 **그 사실을 감지할 근거가 그래프에 없다.**
- 차원이 같고 모델만 다른 경우(예: `text-embedding-3-small` → 다른 1536차 모델)는
  **인덱스 차원 검사로도 잡히지 않는다.** 코사인 유사도가 조용히 무의미한 값을 낸다.
- 재색인이 도중에 죽으면 옛 벡터와 새 벡터가 섞이는데 **어느 것이 어느 것인지 구분할 수 없다.**

이것이 AD-5b(재색인)의 출발점이다. **감지 수단을 먼저 만들지 않으면 재색인 정책을 논할 수 없다.**

### CR-6. 검색은 다축(multi-axis)이고, 벡터축은 그중 둘이다

테이블 검색은 question / hyde / regex / intent / PRF 축의 합집합에 가중치와 패널티를 적용한다 —
`app/react/tools/build_sql_context_parts/table_search_flow.py:508줄`, 가중치는
`TABLE_AXIS_WEIGHT_{QUESTION,HYDE,REGEX,INTENT}`.

벡터축(question·hyde)이 빠져도 regex 축과 FK 확장·유사쿼리 부스트는 남는다. **그러나 이것을
"정상 저하 모드"로 삼지 않는다** — AD-4 참조.

두 가지가 그 판단을 뒷받침한다.

- **hyde 축 가중치가 가장 높다**(기본 `TABLE_AXIS_WEIGHT_HYDE=1.0`). 가장 강한 신호를 뺀
  나머지로 돌리는 것을 "약간 나쁨"이라고 부를 근거가 없다.
- **regex 축은 이름이 맞아떨어질 때만 작동한다.** constitution 이 이미 같은 사실을 다른 맥락에서
  기록했다 — *"문서가 한글 도메인 용어를 쓰고 컬럼은 영문 약어이면 이름 유사도가 **0** 이며,
  그것이 정상이다."* 국내 고객의 레거시 스키마가 정확히 그 모양이다. 벡터가 없으면
  **한글 질문 → 영문 약어 컬럼**을 이어 줄 신호가 남지 않는다.

즉 다축 구조는 **재색인 중의 일시적 열화**를 견디게 해 주지만, **색인이 아예 없는 상태**를
제품으로 팔 수 있게 해 주지는 않는다.

### CR-7. 두 에이전트 백엔드의 능력이 비대칭이다 — 셸이 갈린다

| 경로 | 모드 | 임의 셸/CLI | 근거 |
|---|---|---|---|
| cliagents (claude-code) | 전 모드 | **무제한** (`--permission-mode bypassPermissions`, 툴 allow-list 없음) | `cliagents_backend.py:225-229` |
| cliagents (codex) | 전 모드 | **무제한** (`--dangerously-bypass-approvals-and-sandbox`) | `cliagents_backend.py:378-382` |
| deepagents | **build** | 있음 — `execute(command)` 도구, **타임아웃 120초 고정**, 출력 3,000자 절단 | `agent_session/sandbox_tools.py:20-36`, `shared/sandbox/local_backend.py:165-198` |
| deepagents | answer / answer_nods / brief_draft | **없음** | `agent_session/service.py:181-201` |

그리고 Docker 배포에서 백엔드 컨테이너에는 `python:3.12-slim` + libreoffice + curl + `/app/.venv`
뿐이고, 볼륨 마운트는 `uploads/`·`output/` 둘뿐이다 (`ontology-studio/Dockerfile`,
`docker-compose.yml`). **`neo4j-text2sql` 체크아웃이나 임의 CLI 는 그 안에 존재하지 않는다.**

→ **"스킬이 `python .../cli.py` 를 부른다" 는 설계는 두 백엔드에서 같게 돌지 않는다.**
이것이 AD-3 의 근거다.

### CR-8. 스킬은 폴더 하나를 늘리면 되지만, **모드**를 늘리면 코드 6곳을 고쳐야 한다

`skills/README.md:175-176` 은 *"스킬을 추가하려면 이 폴더에 같은 구조의 폴더를 하나 만들면 된다.
코드 변경은 필요 없다"* 라고 적었고, 그것은 참이다 —
`agent_session/skill_registry.py:172-192` 가 폴더를 스캔하고
`backend/tests/modules/agent_session/test_distribution.py:23` 이 그 스캔 결과로 테스트를
파라미터화한다.

그러나 **모드**는 다르다. `AgentMode` 는 하드코딩이고 6곳에 흩어져 있다:

| 곳 | 위치 |
|---|---|
| 타입 선언 | `agent_session/service.py:82` |
| 도구 목록 | `agent_session/service.py:134-201` |
| `get_agent` 분기 | `agent_session/service.py:817-842` |
| cliagents 모드↔스킬 매핑 | `agent_session/cliagents_backend.py:610-617` |
| MCP 라우터 모드 목록 | `agent_bridge_mcp/router.py:15` |
| MCP 도구 선택 | `agent_bridge_mcp/server.py:32-42` |

### CR-9. ontology-studio 는 이미 text2sql 을 HTTP 로만 부른다 — 좋은 선례가 있다

| 호출 | 엔드포인트 | 위치 |
|---|---|---|
| 확정 SQL 실행 | `POST /text2sql/direct-sql` | `modules/ontology/datasource_exec.py:560` |
| 자연어 질의 위임 (스트리밍) | `POST /text2sql/react` | `datasource_exec.py:674` |
| 컬럼 카탈로그 | `GET /text2sql/meta/tables/{t}/columns` | `modules/ontology/datafabric_client.py:284` |

그리고 에이전트가 닿는 표면은 `datasource_nl_query(class_name, question)` 도구 하나다 —
`modules/ontology/tools.py:1811`, **answer 모드에만** 노출(`service.py:200`).
`ontology-answer` 스킬은 이를 *"최후 수단"* 으로 기술한다
(`skills/ontology-answer/references/search-strategy.md:19-29`).

**즉 "결정론 능력을 MCP 도구로 노출하고 스킬은 그 이름만 부른다" 는 패턴이 이 저장소에 이미
동작하는 형태로 존재한다.** 새 패턴을 발명할 필요가 없다.

### CR-10. `direct-sql` 은 건드리면 안 되는 표면이다

| 호출자 | 위치 |
|---|---|
| domain-layer | `app/routers/ontology.py:4655,4879,5575` · `app/services/instance_fetcher.py:88` · `data_source_linker.py:569` · `whatif/feature_view_builder.py:546` |
| ontology-studio | `datasource_exec.py:560` |
| robo-data-catalog | `TEXT2SQL_ENDPOINT = "/text2sql/direct-sql"` |

constitution 원칙 I 이 *"실데이터 조회는 neo4j-text2sql `POST /text2sql/direct-sql` 을 거친다"*
라고 못박은 계약이다. **이 스펙은 이 엔드포인트의 동작을 바꾸지 않는다.**

### CR-11. 피드백은 이미 아무 데도 연결돼 있지 않다

`(:Feedback)` 노드는 `app/routers/feedback.py:59-74` 에서 `CREATE` 되는데:

- 제약·인덱스가 없다 (`neo4j_bootstrap.py` 에 정의 전무)
- **다른 노드와 관계가 없다** — `(:Query)` 와도 연결되지 않는 고립 노드
- id 가 `f"fb_{ts}_{hash(snapshot_id)%10000}"` (`feedback.py:55`) — 파이썬 `hash()` 는 프로세스마다
  시드가 달라 **재현 불가**
- **피드백이 이후 SQL 생성·캐시·랭킹에 되먹여지는 코드가 존재하지 않는다.** `PromptImprover`
  (`app/core/prompt.py:98`)가 그 자리였을 것으로 보이나 인스턴스화하는 곳이 없다

즉 "피드백을 잃는다"는 리스크는 **이미 잃은 상태**다. 이 사실을 §무엇이 깨지는가에 정직하게 적는다.

### CR-12. 컨트롤러에는 테스트가 0개다

`app/tests/` 12파일 중 컨트롤러·rubric 점수·`parse_validate_sql`·MindsDB dialect·
`sql_autorepair`·`build_sql_context` 를 검증하는 것은 **하나도 없다.**
`app/tests/react/test_intent_keyword_json_parsing.py:2` 는 존재하지 않는 모듈을 import 해
**collection error** 로 죽는다. `Makefile:35` 의 `pytest tests/` 는 경로가 틀렸다(실제는 `app/tests/`).

**따라서 이 리팩터링의 첫 단계는 코드 삭제가 아니라 안전망 구축이다.**

### CR-13. robo-skill-analyzer 는 서비스가 아니라 CLI 이고, MCP 를 헌법으로 금지한다

- HTTP 프레임워크 import 0건 (`fastapi|flask|uvicorn|httpx|requests` grep, 데이터 파일 제외)
- `/tmp/robo-skill-analyzer/.specify/memory/constitution.md:54-56`:
  > **MCP 툴로 노출하지 않는다(MUST NOT)** — MCP 툴 정의가 캐시 프리픽스에 얹혀 캐시를 오염시킨다.
  > Bash 로 부르면 스크립트 코드는 컨텍스트에 오르지 않고 **stdout 만** 온다.
- LLM·임베딩 호출 **0건**. `skillkit/` 의존성은 `neo4j` 드라이버 + `sqlglot` + 표준 라이브러리뿐.
  이는 우연이 아니라 성공 기준이다 — `specs/003-scan-two-modes-linking/spec.md:154` (SC-005).
- 캐시 프리픽스 규율이 명문화되어 있다 —
  `.claude/skills/analyze-framework/SKILL.md:10-11`:
  > 이 문서(SKILL.md)는 **byte-stable 캐시 프리픽스**다 — 타임스탬프·실행ID·날짜·모드·사용자명
  > 같은 가변값을 절대 담지 않는다.
- Claude 가 토큰을 쓰는 지점이 **정확히 둘**로 못박혀 있다 — ③ scan(1회 발견), ⑥ analyze(노드 의미
  루프). 나머지 다섯 단계는 0 토큰 (`constitution.md:46-47`).

**금지의 근거가 기능이 아니라 캐시라는 점이 중요하다.** ontologic 은 별도 프로세스가 호출 주체가
되는 마이크로서비스이므로 이 전제가 다르다. AD-6 에서 이 경계를 재정의한다.

### CR-14. robo-skill-analyzer 는 그대로 쓸 수 없다

| 문제 | 근거 |
|---|---|
| 패키징 없음 | `pyproject.toml`/`setup.py`/`requirements.txt` 전부 없음 (`.gitignore:7-8` 이 의도적 제외) |
| 테스트 0개 | `test_*.py`/`conftest.py` 없음. 검증은 정답지 DB 대조뿐 |
| Windows 전제 | `.venv/Scripts/python.exe`, cp949 폴백, speckit 스크립트가 `powershell/` 만 |
| 데드코드 | `skillkit/scan_profile.py` 의 `save`/`validate`/`promotion_text` 는 호출자 없음 — 프로파일 저장·승격을 현재 **사람(메인 루프)이 손으로** 한다 |
| 계약 드리프트 | `contracts/cli-contract.md:38` 은 `usage --otel-log`, 실제 구현은 `--session-id/--usage-log` |
| 미소비 자산 | `schemas/semantic_output.json` 은 6필드인데 `cli.py:102-103` 은 `summary` 한 필드만 저장 |
| 스키마 불일치 | 라벨을 **antlr type 그대로** 씀. 기존 `robo-data-analyzer` 는 `MODULE`/`FUNCTION` 등 고정 라벨 + `sub_label` |
| 미커밋 | 전 코드가 단일 스쿼시 커밋 1개(`311837d`), 003 tasks 전부 미체크 |

동시에 **이식 가치가 매우 높은 설계 결정**들이 있다:

- **단일 엔진 원칙** — `skillkit/regex_link.py:1-6`: `scan-verify` 와 `link` 가 같은 `link()` 코어를
  공유해 *"검증한 정규식 == 적용되는 정규식"* 을 코드 한 곳으로 보장. *"drift 불가 = 환각 차단."*
- **throwaway 가드** — `skillkit/neo4j_store.py:19,47-53`: allowlist 밖 DB 면 드라이버 생성 **전에**
  거부. constitution 원칙 IV(전역 삭제 금지)와 정확히 같은 문제를 코드로 막는다.
- **판정 기준 선고정** — `specs/003.../spec.md:115` (FR-012): *"불일치가 난 뒤 사후에 설명을
  지어내는 것(고무줄 설명)을 금지"*.
- **개수 하드코딩 금지** — 같은 스펙 SC-003: *"'N개 뽑고 통과' 게임 차단"*.
- **"안 되는 게 발견"** — `specs/003.../tasks.md:27`: 두 방식 다 실패하면 조용히 밀지 말고
  표면화하고 범위를 재협의하라.

### CR-15. 기존 `robo-data-analyzer` 는 이미 프레임워크 스킬을 갖고 있다

`robo-data-analyzer/skills/` 에 6개 폴더(`_templates`, `ejb-cmp`, `jpa-standard`,
`mybatis-ibatis`, `ofbiz`, `proframe-c-pfm-dbio`), 합계 366줄. 다만 **agentskills.io 형식이 아니다**
— 프론트매터가 없고, Scan Agent 가 읽는 프롬프트 조각이다.

robo-skill-analyzer 의 `scan-structure` 2모드는 **정확히 이것을 일반화한 것**이다 —
`SKILL.md:46-53` 이 ProFrame(C) / MyBatis / JPA / OFBiz 네 프레임워크를 **대등한 예시 표**로 두고
*"★범용 — 프레임워크에 하드코딩 금지(FR-018)"* 라고 못박는다.

즉 두 저장소는 같은 문제의 두 세대다. 하드코딩된 스킬 6개 → 런타임 발견 프로파일 1개.

### CR-16. 분석기의 대외 표면은 엔드포인트 하나뿐이다

`robo-data-analyzer/api/analyze_router.py:32,47` — `GET /`(health) 와
`POST /robo/analyze`(NDJSON 스트림). 프론트가 부르는 `/robo/source`·`/robo/search`·
`/robo/analyze/control` 은 **현재 핀된 커밋에 없다**(증거 11 §3-3). 폴링·컨트롤은 주석으로 명시적
폐기(`analyze_router.py:6-9`).

파이썬/백엔드 서비스 중 분석기를 HTTP 로 부르는 것은 **없다.** 호출자는 api-gateway(프록시),
데스크톱 셸(프록시+기동), 기동 스크립트, 패키징 스크립트뿐.

**교체 난이도가 text2sql 보다 훨씬 낮다.** 지켜야 할 표면이 엔드포인트 하나와 NDJSON 이벤트
형식, 그리고 Neo4j 스키마다.

### CR-17. 메모리 실측 — text2sql 컨테이너를 없앤다고 큰 이득이 나지 않는다

| 측정 | 값 | 출처 |
|---|---|---|
| text2sql 호스트 프로세스 (유휴) | **214.8 MiB** | `memory-footprint-measurement.md` §3-2 |
| text2sql 호스트 프로세스 (부하 피크) | 215.8 MiB (**+1.0 MiB**) | §4-1 |
| text2sql 컨테이너 (Podman, 유휴) | **140.9 MB** | §9-5 |
| text2sql 컨테이너 (Podman, 라운드 3) | **201.3 MB** | §10-3 |
| core 소계 (컨테이너 5 + 호스트 4) | **3,261.8 MB ≈ 3.11 GiB** | §10-3 |
| robo-data-analyzer 호스트 프로세스 | **401.4~420.9 MiB** | §10-2, §10-3 |
| — 그중 원인 | `sentence-transformers==3.3.1` → torch, `.venv` **932 MB**, 비용은 **import 시점** | §10-2 (`:552-556`) |

**text2sql 이 core 에서 차지하는 비중은 201.3 / 3,261.8 = 6.2% 다.** 컨테이너를 통째로 없애도
8GB 판정을 뒤집지 못한다(§7-2 는 idle 3.957 GiB + OS 2~3 GiB 로 이미 경계). 반면 **분석기의
임베딩 스택 400 MB 는 core 의 12.3%** 로 훨씬 크다.

→ **메모리 최적화의 실제 지렛대는 text2sql 제거가 아니라 임베딩 모델을 몇 벌 두느냐다.** AD-5.

---

## 아키텍처 결정

### AD-1. ReAct 루프 자리에는 **스킬 본문의 산문**이 오고, 상태기계 변수는 에이전트 컨텍스트가 된다

경계는 constitution 의 *"지시문과 값을 섞지 않는다"* 가 정한다. 판정 규칙 한 줄:

> **값을 만들어 내는 것은 도구다. 무엇을 다음에 할지 정하는 것은 지시문이다.**

이 규칙을 컨트롤러가 하는 일에 적용하면 이렇게 갈린다.

| 컨트롤러가 지금 하는 일 | 어디로 | 근거 |
|---|---|---|
| `build_sql_context` 호출 | **도구** (5개로 분해, AD-2) | 카탈로그·벡터 조회 = 값 |
| `extract_requirements` (LLM) | **지시문** | 질문 해석 = 판단 |
| `draft_llm_candidates` (LLM) + 다양화 전략 3종 | **지시문** | 전략 3종이 `controller.py:1434-1438` 에 **문자열 리터럴로 하드코딩** — 전형적인 정책 |
| `sanitize_sql` (코드펜스 제거) | **도구** | 문자열 변환 = 값 |
| `validate_sql` 호출 | **도구** (3개로 분해, AD-2) | 실행·EXPLAIN = 값 |
| `parse_validate_sql` | **도구** | 파싱 = 값 |
| `_hard_preview_reject` / `_preview_non_null_stats` | **도구** | row_count==0, 전부 NULL = 계산 |
| `evaluate_candidate` (LLM) | **지시문** | 요구사항 충족 판정 = 판단 |
| `compute_score_and_accept` | **도구 (그대로)** | 이미 결정론 (CR-2) |
| 수리 루프 / stall 감지 / 2순위 전환 | **지시문** | `max_repairs_per_candidate=4`, `stall_rounds=2` 는 정책 |
| `triage_no_acceptable_sql` (LLM) + 정책 강제(`controller.py:1086-1140`) | **지시문** | 포기 판단 = 판단 |
| `context_refresh` 루프 (라우터) | **지시문** | 재시도 정책 |
| 최종 SQL 실행 | **도구** | 실행 = 값 |
| 인메모리 캐시 조회/저장 | **도구 (라우터, 에이전트 진입 전)** | AD-7 |

**수치 파라미터는 스킬 본문에 쓰지 않는다.** `n_candidates`·`score_threshold` 같은 것은
`ControllerConfig`(`controller.py:872`)에서 **값 블록**으로 주입한다 — constitution 의
*"경로 매핑도 값이다 … 값 블록 한 개로 주입하고 설명 문장을 붙이지 않는다"* 와 같은 취급.
스킬 본문은 "예산이 주어지면 그 안에서 돈다"만 말하고 숫자를 담지 않는다.

**대가 (숨기지 않는다)**: 컨트롤러의 명시적 상태기계(`active_*` 7개 + `fallback_*` 7개 +
`best_*`/`second_*` 10개, `controller.py:1656-1813`)가 에이전트 컨텍스트로 바뀐다. 재현성이
떨어지고 `_repro_log.py`(prompt sha256 + input/response sha256)의 의미가 약해진다. §무엇이
깨지는가에 적었다.

### AD-2. 두 도구를 **8개의 좁은 도구**로 분해한다

지금 `build_sql_context`(3,000줄 13모듈)와 `validate_sql`(468줄 단일 함수)은 LLM 호출과 결정론
계산이 한 몸이다. 스킬이 루프를 돌려면 도구가 **한 번에 한 가지 값**을 줘야 한다.

| 새 도구 | 무엇을 하는가 | 어디서 왔는가 | LLM |
|---|---|---|---|
| `search_tables(keywords, vectors?, top_k)` | 다축 테이블 후보 + 점수 | `table_search_flow.py` 에서 rerank LLM 제거 | 없음 |
| `search_columns(tables, keywords, vectors?)` | 테이블별 컬럼 후보 | `column_search_flow.py` | 없음 |
| `catalog_context(tables)` | FK·관계·중요도·enum 값 힌트 | `neo4j_utils.py` + `column_value_hints_flow.py` | 없음 |
| `similar_queries(question, vectors?)` | `:Query` 캐시 + ValueMapping | `similar_flow.py` 에서 intent LLM 제거 | 없음 |
| `embed(texts) -> vectors` | 임베딩 (제공자 심, AD-4) | `app/core/embedding.py` | 없음 |
| `guard_sql(sql)` | SELECT-only·깊이·금지패턴 판정 + dialect 변환 결과 | `sql_guard.py` + `sql_transform.py` + `sql_mindsdb_prepare.py` | 없음 |
| `run_sql_preview(sql, row_limit)` | 실행 + preview + NULL 통계 + 규칙 자동수리 시도 | `sql_exec.py` + `sql_autorepair.py` + `_preview_non_null_stats` | 없음 |
| `explain_sql(sql)` | EXPLAIN 플랜 원문 (PostgreSQL) | `db_query_builder/postgresql.py` | 없음 |

**여덟 개 전부 LLM 을 부르지 않는다.** 이것이 검증 가능한 형태의 경계다 — SC-005 가 grep 으로
강제한다. robo-skill-analyzer 의 SC-005(`skillkit/` grep 0건)를 그대로 빌린다.

`compute_score_and_accept` 는 도구로 노출하지 않는다 — 스킬이 PASS/FAIL 을 세는 규칙을 본문에
갖는 편이 왕복 한 번을 아낀다. 다만 **임계값은 값 블록으로 주입한다.**

### AD-3. 스킬은 **셸에 의존하지 않는다.** 능력은 전부 MCP 도구로 노출한다

CR-7 이 근거다. deepagents 의 `execute` 는 build 모드에만 있고 120초에 잘리며 Docker 배포에서는
실행할 소스가 컨테이너에 없다. 스킬이 `python .../cli.py` 를 부르는 순간 두 백엔드가 **구조적으로**
갈린다.

**결정**: text2sql 스킬이 쓰는 능력은 전부 `agent_bridge_mcp` 의 새 모드에 도구로 올린다.
선례는 이미 있다 — `datasource_nl_query`(`ontology-studio/backend/src/modules/ontology/tools.py:1811`)
가 정확히 text2sql 을 HTTP 로 부르는 파이썬 도구다.

**이 결정이 `agent-backend-and-llm-access.md` 의 "산출물 품질이 구조적으로 갈린다" 를 해결하는가 —
부분적으로만 그렇다. 정직하게 적는다.**

- **해결되는 것**: *능력* 차이. 두 백엔드가 같은 MCP 엔드포인트에서 같은 8개 도구를 받는다.
  004 FR-011 의 "같은 함수 객체" 강제(`tests/modules/agent_bridge_mcp/test_agent_bridge_mcp.py:39-40`)가
  그대로 적용된다.
- **해결되지 않는 것**: *모델* 차이. spec 004 가 이미 Out of Scope 로 선언했다 —
  *"관측된 차이는 대부분 모델 차이이지 아키텍처 차이가 아니다."* 이 스펙도 같은 선을 지킨다.
- **남는 비대칭 하나**: cliagents 는 answer 계열 모드에서도 로컬 Bash 가 열려 있다
  (`cliagents_backend.py:634-640` 이 모드별로 MCP URL 만 바꾼다). MCP 상 읽기 전용이어도 CLI 자체
  도구는 살아 있다. 이 사실을 스킬 본문에 적지 않는다 — 적으면 한쪽만 쓰는 지시문이 된다.
  대신 §Assumptions 에 기록한다.

**분석기는 예외다.** AD-6 참조.

### AD-4. 임베딩은 **도구로 남고, 데이터소스 질의의 선행 조건이다.** `none` 은 저하 모드가 아니다

**사업 결정 (2026-08-03).** 임베딩은 선택이 아니라 데이터소스 경로의 **필수 선행 조건**이다.
근거는 CR-5·CR-6 이다 — 필드 임베딩이 없으면 text2sql 은 그 필드를 찾을지 말지 판단할 단계에
**도달하지 못한다.**

**두 부분으로 나눠 결정한다.**

#### (a) 임베딩은 스킬로 옮겨지지 않는다 — 도구로 남는다

CLI 에이전트는 벡터를 만들 수 없다. Claude Code 도 Codex 도 임베딩 도구를 노출하지 않는다.
프롬프트로 우회할 수 없는 종류의 한계다. **이 스펙의 가장 확실한 결론이고, 사업 결정이
바뀌어도 바뀌지 않는다.**

#### (b) `none` 은 **"데이터소스 질의 불가"** 상태다 — "조금 나쁜 검색"이 아니다

앞선 판(2026-08-03 이전)은 `none` 을 *정상 동작하는 저하 모드*로 두었다. **폐기한다.**

| 상태 | 정의 | 무엇이 되는가 | 무엇이 안 되는가 |
|---|---|---|---|
| `indexed` | 대상 데이터소스의 테이블·컬럼 벡터가 현재 지문과 일치 | 전부 | — |
| `indexing` | 색인 진행 중 | 온톨로지 설계·그래프 조회. **질의는 진행률과 함께 대기 또는 부분 결과 고지** | 완전한 데이터소스 질의 |
| `stale` | 벡터는 있으나 지문이 현재 설정과 불일치 (CR-5c) | 온톨로지 설계·그래프 조회 | **데이터소스 질의 — 거부한다.** 조용히 낡은 벡터로 검색하지 않는다 |
| `unindexed` | 벡터 없음 (임베딩 미설정 포함) | 온톨로지 설계·그래프 조회 | **데이터소스 질의 — 거부하고 무엇을 해야 하는지 안내한다** |

**규칙 넷.**

1. **`unindexed`·`stale` 에서 데이터소스 질의는 "나쁜 답"이 아니라 "명시적 거부"다.**
   나쁜 답은 사용자가 검증할 수 없다. 거부는 검증할 필요가 없다. constitution 원칙 VII 의
   *"단위 테스트만 통과한 것을 동작한다고 보고하지 않는다"* 와 같은 정신이다.
2. **거부는 진단과 다음 행동을 함께 준다.** 데스크톱이 이미 같은 일을 하고 있다 —
   *"데이터소스 자연어 질의 비활성 — 온톨로지 설계와 그래프 조회는 사용 가능"*
   (`agent-backend-and-llm-access.md` §임시 조치, `desktop/src/main/index.js`).
   그 문구를 **임시 조치에서 정식 상태 표시로 승격**한다. 다만 이제는 "왜 비활성인지"와
   "무엇을 하면 켜지는지"(= 메타데이터 증강 실행)를 함께 말한다.
3. **기동은 색인 상태와 무관하다.** text2sql 은 벡터가 없어도 뜬다. 뜨는 것과 질의가 되는 것은
   다른 문제이고, 지금은 그 둘이 묶여 있어 앱 전체가 죽는다(CR-5b 결과 3).
4. **다축 폴백은 `indexing` 중의 일시적 열화에만 쓴다.** `unindexed` 를 가리는 데 쓰지 않는다.

**감수하는 대가 (숨기지 않는다)**: "키 없이 설치하면 바로 질문할 수 있다"는 카피를
**쓸 수 없게 된다.** 정확한 카피는 §사업 문서에 적었다. 앞선 판보다 약속이 줄었지만, 줄어든
약속이 참이다.

### AD-5. 색인은 **메타데이터 증강 단계**로 옮긴다. 추출이 곧 색인이다

**사업 결정 (2026-08-03).** 임베딩 생성을 데이터소스 메타데이터 추출(「메타데이터 증강」)
단계로 옮긴다.

#### 왜 거기인가

CR-5 가 진단한 결함이 정확히 이것이다 — 색인이 **추출의 단계가 아니라 질의 서비스 부팅의
부수효과**로 존재한다. 그 배치가 낳은 것:

| 증상 | 원인 |
|---|---|
| text2sql 이 키 없이 못 뜬다 | 부팅 잡이 LLM + 임베딩을 요구 |
| 콜드스타트가 길다 | 테이블 전수 프로파일링이 **블로킹** (`app/main.py:72`) |
| 데이터소스를 새로 등록해도 벡터가 안 생긴다 | 추출 파이프라인에 색인 단계가 없다 |
| 레거시 두 인덱스는 영원히 빈다 | 부수효과조차 못 받는다 |

**추출이 곧 색인이 되면 넷이 동시에 사라진다.** 벡터는 데이터소스의 메타데이터이지 질의
엔진의 캐시가 아니다 — constitution 원칙 I(*"카탈로그는 인제스천 이후 Neo4j 가 단일 진실
원천"*)이 이미 그렇게 말하고 있었고, 벡터만 그 규칙 밖에 있었다.

#### 소유권

| 일 | 누가 | 근거 |
|---|---|---|
| 색인 **단계**를 파이프라인에 갖는 것 | **메타데이터 증강 경로** (data-fabric 추출 + 신규 분석기) | 추출이 곧 색인 (원칙 I) |
| 임베딩 **벡터를 만드는 것** | **임베딩 엔드포인트 한 곳** | 아래 |
| 질의 시점 질문 임베딩 | text2sql 이 같은 엔드포인트를 호출 | CR-5 결과 3 |

#### 임베딩 제공자 셋 — 사용자가 고른다

| 선택지 | 무엇인가 | 우리 스택 비용 |
|---|---|---|
| **제공 LLM 엔드포인트 재사용** | 이미 설정한 OpenAI 호환 엔드포인트가 임베딩도 서빙하면 그것을 쓴다 | **0** |
| **OpenAI** | 공식 엔드포인트 + 키 | 0 (데이터가 나간다) |
| **로컬 번들 모델** | 우리가 모델을 들고 돈다 | **~400 MB RSS** (§10-2 실측) |

**1순위는 첫 번째다.** `base_url` 누락(CR-5b)만 고치면, 사용자가 이미 돌리는 로컬 서버
(Ollama·LM Studio·vLLM 등이 `/v1/embeddings` 를 제공하는 경우)를 임베딩에도 쓸 수 있다 —
**우리 스택 메모리 증가 0 으로 "데이터가 PC 를 떠나지 않는다"가 성립한다.**
앞선 판이 400 MB 를 기정사실로 둔 것은 이 경로를 놓친 것이다.
*(미확인: 실제 로컬 서버로 임베딩 왕복을 검증하지 않았다 — §미결정 11번)*

번들 로컬 모델은 **사용자가 아무 엔드포인트도 갖고 있지 않을 때만** 필요하다. 그때만 400 MB 를
지불하고, 호스트는 이미 그 스택을 가진 신규 분석기로 둔다 (실측 근거 §10-2).

#### 한 벌만 두는 진짜 이유는 메모리가 아니라 **차원·모델 일치**다

앞선 판은 이것을 메모리 논거로만 세웠다. 더 강한 논거가 있다:

> **추출이 모델 A 로 색인하고 질의가 모델 B 로 임베딩하면, 아무 오류 없이 코사인 유사도가
> 무의미한 값을 낸다.** 차원까지 같으면 인덱스 검사로도 안 잡힌다 (CR-5c).

임베딩 엔드포인트를 **하나로 두면 이 불일치가 구조적으로 불가능해진다.** 그래서 설정도
**앱 전역 한 벌**이다 — 데이터소스마다 다르게 두지 않는다 (사업 결정 4).

**감수하는 대가**: 임베딩 엔드포인트가 죽으면 색인과 질의가 함께 멈춘다.
→ 그 경우 상태는 `indexing` 또는 `stale` 로 표시되고 데이터소스 질의는 거부된다(AD-4).
**조용히 낡은 벡터로 답하지 않는다.**

### AD-5b. 재색인 — 감지는 자동, 실행은 확인, 삭제는 좁게 (권고안)

**이것은 결정이 아니라 권고안이다.** 아직 정해지지 않았으므로 근거와 함께 제안하고
§미결정 항목에도 남긴다.

#### 문제

모델을 바꾸면 기존 벡터가 무효가 된다. 그런데 CR-5c 대로 **무효인지 알 방법이 그래프에 없다.**
그리고 재색인은 본질적으로 파괴적 작업이다 — constitution 원칙 IV 가 다루는 종류의 일이고,
그 문서는 실제 사고 두 건(전역 삭제로 카탈로그 소실, 스키마 그룹 삭제 후 엔티티 누적)을 근거로
갖고 있다.

#### 권고 1 — 감지 수단을 **먼저** 만든다 (지문)

재색인 정책보다 앞선다. 벡터를 쓸 때 **노드마다** 무엇으로 만들었는지 함께 기록한다:

```
t.text_to_sql_vector          (지금 있음)
t.embedding_model             ← 신규
t.embedding_dimension         ← 신규
t.embedding_indexed_at        ← 신규 (text_to_sql_updated_at 로 대체 가능)
```

전역 설정과 대조할 **현재 지문**은 별도로 한 곳에 둔다. 지문이 없으면 다음 셋을 전부 못 한다 —
불일치 감지 / 부분 실패 복구 / 재개.

**노드별로** 기록하는 것이 핵심이다. 전역에만 두면 재색인이 중간에 죽었을 때 "전부 다시" 밖에
할 수 없고, 수천 테이블에서 그것은 사실상 복구 불가다.

#### 권고 2 — 자동 재색인은 **지울 것이 없을 때만**

| 상황 | 처리 | 근거 |
|---|---|---|
| 벡터가 **하나도 없다** (콜드 스타트) | **자동으로 색인한다** | 지울 것이 없으므로 파괴적이지 않다. 판정 로직이 이미 있다 — `text2sql_runtime_repair.py:124-136` 의 `cold_start_detected` 를 재사용 |
| 일부만 없다 (신규 테이블 추가 등) | **없는 것만 자동으로 채운다** | 기존 벡터를 건드리지 않는다 |
| 지문 불일치 (모델·차원 변경) | **거부 + 사용자 확인 요구** | 기존 벡터를 **버리는** 일이다 |
| 인덱스 차원 ≠ 설정 차원 | **거부.** 추측해서 진행하지 않는다 | 조용히 섞이면 코사인이 무의미해진다 |

#### 권고 3 — 확인받을 때 **무엇을 잃는지 숫자로** 보인다

*"모델을 바꾸면 다시 색인합니다"* 로는 판단할 수 없다. 보여야 하는 것:

- 다시 색인할 테이블 수 · 컬럼 수
- 예상 소요 시간, 그리고 **유료 제공자면 예상 비용**
- 재색인 중 데이터소스 질의가 어떤 상태가 되는지 (AD-4 의 `indexing`/`stale`)
- **되돌릴 수 없다는 사실** — 옛 벡터는 재생성 외에 복구 경로가 없다

#### 권고 4 — 삭제 범위를 좁힌다 (constitution IV)

- `MATCH (n) DETACH DELETE n` 류 **절대 금지.** 원칙 IV 가 실제 사고로 명시한 것이다.
- **벡터 속성만** 지운다 — `REMOVE t.text_to_sql_vector, t.embedding_model, ...`.
  `(:Table)` / `(:Column)` 노드 자체는 **data-fabric 이 쓴 카탈로그**이므로 건드리지 않는다
  (원칙 I).
- 인덱스는 drop → create 로 다시 만든다. 차원이 바뀌면 이것 말고 방법이 없다.
- 범위는 **데이터소스 단위**로 좁힌다. 원칙 II 대로 `(t.datasource = $ds OR t.db = $ds)` 를
  항상 함께 쓴다 — 그러지 않으면 한 데이터소스의 재색인이 **다른 데이터소스의 벡터를 지운다.**

#### 권고 5 — 재색인 중에는 거짓말하지 않는다

부분 재색인 상태에서 검색하면 옛 벡터와 새 벡터가 한 인덱스에 섞인다. 셋 중 하나를 골라야 한다:

| 안 | 동작 | 평가 |
|---|---|---|
| A. 완료까지 질의 거부 | 가장 단순, 가장 정직 | 수천 테이블이면 오래 막힌다 |
| B. 지문이 맞는 노드만 검색 대상 | 결과가 항상 유효 | Cypher 에 지문 필터가 붙는다 |
| C. 섞인 채로 검색 | 아무것도 안 막힘 | **무의미한 유사도. 채택하지 않는다** |

**권고는 B 다.** 지문(권고 1)이 있으면 필터 한 줄이고, 진행률에 따라 결과가 점점 좋아진다.
B 의 비용은 재색인 중 재현율이 낮다는 것인데, 그 사실은 AD-4 의 `indexing` 상태로 **사용자에게
표시된다.** C 는 같은 열화를 **숨긴다** — 그것이 차이다.

**미결정으로 남기는 것**: 확인 UI 를 어디에 둘지(부팅 화면 / 앱 안 설정 / 추출 화면),
대규모에서 B 의 성능, 재색인을 데이터소스 단위로 나눠 돌릴지 전부 한 번에 돌릴지.

### AD-6. 분석기는 **새 마이크로서비스**로 만들되, skillkit 은 이식하고 헌법 II 는 재해석한다

`robo-skill-analyzer` 를 그대로 쓰지 않는다 (CR-14). **설계를 이식하고 코드는 이 제품의 계약 위에
다시 쓴다.**

이식하는 것 / 이식하지 않는 것:

| 이식한다 | 이식하지 않는다 |
|---|---|
| 단일 엔진 원칙 (`regex_link.link()` 를 verify 와 apply 가 공유) | Windows 전용 경로·cp949 폴백 |
| throwaway DB 가드 (allowlist 밖이면 드라이버 생성 전 거부) | antlr type 을 라벨로 직결하는 스키마 |
| 5순위 결정론 호출 분류 (internal→wrapper→stdlib→framework→external) | 패키징 없음 / 테스트 0개 |
| scan 2모드 (structure / domain) 와 byte-stable 프로파일 | 데드코드 (`scan_profile.save/validate/promotion_text`) |
| NDJSON 이벤트 계약 + `stream_end` 센티넬 | `usage` 서브커맨드의 세션 JSONL 조인 (Claude Code 전용) |
| "판정 기준 선고정"·"개수 하드코딩 금지"·"안 되는 게 발견" 규율 | 001 의 MCP 서버 방식 (이미 폐기됨) |

**Neo4j 스키마는 기존 `robo-data-analyzer` 것을 따른다.** 라벨 `SCHEMA·TABLE·COLUMN·PACKAGE·
MODULE·FUNCTION·VARIABLE·CONSTANT·DATA_TYPE·RULE·EXAMPLE·QUESTION` + `sub_label`
(`robo-data-analyzer/shared/neo4j/schema_constraints.py:15-46`), 관계 19종
(`shared/neo4j/rel_types.py:12-36`). 이유: robo-data-catalog 와 robo-data-frontend 가 이미 이것을
읽는다. 스키마를 바꾸면 이 스펙 범위가 두 서비스 더 늘어난다.

**헌법 II(MCP 금지) 재해석.** robo-skill-analyzer 가 MCP 를 금지한 근거는 기능이 아니라
*"MCP 툴 정의가 캐시 프리픽스에 얹혀 캐시를 오염시킨다"* 이다 (CR-13). 그 전제는 **Claude Code
메인 루프가 곧 오케스트레이터일 때**만 성립한다. ontologic 에서는 호출 주체가 다르므로 이렇게
가른다:

| 소비자 | 접근 방식 | 근거 |
|---|---|---|
| 데스크톱 셸 / api-gateway / robo-data-frontend | `POST /robo/analyze` (NDJSON) — **기존 계약 그대로** | CR-16. 이들은 에이전트가 아니다 |
| cliagents 경로의 의미 루프 | **Bash 로 `skillkit` CLI** — 캐시 프리픽스 보존 | 헌법 II 의 원래 근거가 그대로 성립 |
| deepagents 경로의 의미 루프 | **MCP 도구** (`agent_bridge_mcp` 신규 모드) | 셸이 build 모드에만 있고 120초에 잘림 (CR-7) |

**같은 결정론 함수를 세 진입점이 공유한다.** 004 FR-010("도구 동작을 다시 구현해서는 안 된다")과
같은 규칙이고, 같은 방식(객체 동일성 테스트)으로 강제한다.

### AD-7. 캐시·direct-sql·NDJSON 계약은 **에이전트 밖에** 둔다

리팩터링이 건드리지 않아야 하는 것을 명시적으로 고정한다.

| 대상 | 결정 |
|---|---|
| `POST /text2sql/direct-sql` | **변경 없음.** CR-10 의 8개 호출부가 그대로 동작 |
| `GET /text2sql/meta/*` | **변경 없음** |
| 인메모리 LRU 캐시 (`query_cache.py`) | **라우터에 그대로.** 에이전트 진입 **전**에 조회하고, HIT 면 에이전트를 띄우지 않는다 (지금과 같음, `routers/react.py:787-855`) |
| Neo4j `:Query` 지식캐시 + 품질 게이트 | **백그라운드 워커 그대로.** 단 payload 형태가 컨트롤러 구조체에서 에이전트 턴 요약으로 바뀐다 — **이것이 조용히 깨지기 쉬운 지점** (§무엇이 깨지는가 2번) |
| `POST /text2sql/react` NDJSON 이벤트 이름 | **유지.** 에이전트 이벤트를 기존 이름으로 매핑한다. 선례: `cliagents_backend.py:691-735` 이 CLI 이벤트를 LangGraph 풍 이벤트로 매핑 |
| `conversation_state` 필드 | **필드는 유지**, 내용이 base64 캡슐에서 에이전트 스레드 참조로 바뀐다 |

### AD-8. 두 엔진을 **동시에 두는 기간**을 만든다 — text2sql 도, 분석기도

되돌릴 수 없는 단계를 만들지 않는다.

- text2sql: `TEXT2SQL_ENGINE=controller|skill` (기본 `controller`). 같은 골든셋에서 두 엔진을
  비교할 수 있어야 스킬 엔진을 기본으로 올릴 근거가 생긴다.
- 분석기: **새 서비스를 새 포트에 띄우고** `ANALYZER_IMPL=legacy|skill` 로 게이트웨이/셸이 고른다.
  기존 `robo-data-analyzer` 는 그대로 둔다.

두 경우 모두 **되돌리기는 환경변수 한 줄**이다.

---

## 프롬프트 15개를 어떻게 일반화하는가

그대로 옮기면 스킬이 아니라 프롬프트 창고가 된다. 처분은 넷 중 하나다 —
**스킬 본문 / 참조 자료 / 배치 잡 유지 / 삭제**.

| # | 프롬프트 (줄) | 지금 호출부 | 처분 | 근거 |
|---|---|---|---|---|
| 1 | `controller_sql_candidates_prompt.md` (44) | `controller.py:842` | **스킬 본문** §후보 생성 | 다양화 전략 3종이 `controller.py:1434-1438` 에 하드코딩 = 정책 |
| 2 | `controller_repair_prompt.md` (34) | `controller.py:1680` | **스킬 본문** §수리 — #10 을 흡수 | "실패 이유 보고 최소 수정" 이 #10 과 같은 지시 |
| 3 | `controller_triage_prompt.md` (49) | `controller.py:1081` | **스킬 본문** §포기 판단 + `controller.py:1086-1140` 의 정책 강제도 함께 | 비기술 사용자에게 DB 용어 묻기 금지 = 순수 정책 |
| 4 | `rubric_extract_requirements_prompt.md` (15) | `rubric_judge.py:186` | **스킬 본문** §요구사항 체크리스트 | 15줄, 별도 왕복 불필요 |
| 5 | `rubric_evaluate_candidate_prompt.md` (13) | `rubric_judge.py:204` | **스킬 본문** §후보 판정 (점수 계산은 유지) | `compute_score_and_accept` 는 결정론 (CR-2) |
| 6 | `hyde_schema_prompt.md` (38) | `hyde_flow.py:58` | **스킬 본문** §검색어 확장 + `embed` 도구 | 가상 스키마 텍스트 작성 = 판단, 벡터화 = 도구 (AD-4) |
| 7 | `table_rerank_prompt.md` (33) | `table_search_flow.py:417` | **스킬 본문** §테이블 선별 | 후보 목록은 `search_tables` 가 준다 |
| 8 | `intent_extract_prompt.md` (13) | `similar_flow.py:246` | **#6 에 흡수** | 한 줄 정규화. 별도 LLM 왕복이 아깝다 |
| 9 | `light_disambiguation_queries_prompt.md` (48) | `light_queries_flow.py:217` | **참조 자료** `references/disambiguation.md` + `run_sql_preview` | 본문에 두기엔 길고, 모호할 때만 읽으면 된다 |
| 10 | `validate_sql_repair_prompt.md` (19) | `validate_sql.py:117` | **#2 에 병합** | 중복 |
| 11 | `query_quality_gate_prompt.md` (32) | `routers/react.py:587`, `cache_postprocess.py:835` | **배치 잡 유지** | 요청 경로 밖. fail-closed 게이트는 결정론적으로 유지해야 한다 |
| 12 | `table_profile_prompt.md` (74) | `text2sql_table_vectorizer.py:240` | **배치 잡 유지 → 분석기 이관 후보** | 테이블 N개 배치(동시성 30, 배치 128). 에이전트 루프로 옮기면 콜드스타트가 폭발 |
| 13 | `vector_hyde_rank_table_profile_prompt.md` (69) | **없음** | **삭제** | #12 의 상수도 도메인 하드코딩 구버전 |
| 14 | `llm_xml_reprint_prompt.md` (9) | **없음** | **삭제** | 데드 |
| 15 | `explain_analysis_prompt.xml` (70) | `validate_sql.py:303` | **참조 자료** `references/execution-plan.md` + `explain_sql` 도구 | PostgreSQL 전용. MindsDB 경로는 안 탄다 |
| — | `hyde_schema_variant_generator.py` (203) | **없음** | **삭제** | 데드 |

**합계**: 스킬 본문 7개 · 참조 자료 2개 · 배치 잡 유지 2개 · 삭제 3개(+제너레이터 1) · 병합 흡수 2개.

**본문에 들어가는 7개의 총 원문은 206줄이다.** 005 가 정한 분량 규율(본문 < 10,000자, 참조 자료
총합 > 본문 — `ontology-studio/backend/tests/modules/agent_session/test_skill_content_migration.py:96-104`)
안에 들어간다. 다만 **원문을 이어붙이면 안 된다** — 7개가 같은 컨텍스트를 각자 다시 설명하고 있기
때문이다(예: #1·#2·#3 이 모두 `context_xml` 의 의미를 각자 설명). 본문은 컨텍스트 설명을 **한 번**
하고, 각 단계는 그 위에서 무엇을 결정하는지만 적는다.

**#12 를 분석기로 이관하는 것이 두 리팩터링을 잇는 다리다.** `table_profile` 은 테이블 메타데이터를
LLM 으로 증강해 임베딩 텍스트를 만드는 일 — 즉 **메타데이터 증강**이고, 그것이 정확히 분석기의
정의다. 이 스펙에서는 **이관 후보로만 지목하고 실행하지 않는다** (§Out of Scope).

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - LLM 키 없이 앱이 서고, 무엇이 안 되는지 알 수 있다 (Priority: P1)

Claude Code 구독만 있는 사용자가 데스크톱 앱을 처음 켠다. 첫 실행 화면에서 `cliagents` 를 고르고,
LLM 접속 정보를 **한 번도 입력하지 않는다.** 예제 데이터에 "EQ-CNC-001 설비의 가동 일수를
알려줘" 라고 묻는다.

**Why this priority**: `agent-backend-and-llm-access.md` 가 결정한 것이 이것 하나다.
다만 **결과는 "답이 나온다"가 아니다** — 색인이 없으면 답이 나오면 안 된다(AD-4).
이 스토리가 요구하는 것은 **앱이 서는 것**과 **왜 안 되는지 알 수 있는 것**이다.

**Independent Test**: 루트 `.env` 에서 `OPENAI_API_KEY`·`GOOGLE_API_KEY` 를 비우고 스택을 기동.

**Acceptance Scenarios**:

1. **Given** 두 키가 모두 비어 있다, **When** text2sql 서비스를 기동한다, **Then** `/health` 가
   200 을 반환한다. (지금은 `RuntimeError` 로 뜨지 않는다 — `sanity_checks/runner.py:14`)
2. **Given** 같은 상태, **When** 데이터소스 색인 상태를 조회한다, **Then** `unindexed` 가 반환되고
   그 이유(임베딩 미설정)가 함께 온다.
3. **Given** 같은 상태, **When** 위 질문을 한다, **Then** **답을 지어내지 않고 거부**하며,
   온톨로지 설계와 그래프 조회는 계속 쓸 수 있다는 사실을 함께 알린다.
4. **Given** 같은 상태, **When** 온톨로지 설계·그래프 조회를 쓴다, **Then** 정상 동작한다.

> 이 스토리가 "답이 나온다"로 닫히는 것은 US4 를 지난 뒤다. 순서를 바꾸지 않는다.

### User Story 1b - 메타데이터 증강이 색인까지 끝낸다 (Priority: P1)

같은 사용자가 「메타데이터 증강」을 실행한다. 시작하는 순간 임베딩을 어떻게 만들지 묻는다.
고르고 나면 추출과 색인이 함께 끝나고, US1 의 질문에 **답이 나온다.**

**Why this priority**: 이것이 사업 결정 2·3 의 본체다. 그리고 CR-5 가 진단한 결함
(색인 단계 부재)이 닫히는 지점이다.

**Acceptance Scenarios**:

1. **Given** 임베딩 설정이 없다, **When** 메타데이터 추출을 시작한다, **Then** 선택 화면이 뜨고
   세 선택지(제공 LLM 엔드포인트 / OpenAI / 로컬 번들 모델)와 **각각의 대가**가 보인다.
2. **Given** 선택을 마쳤다, **When** 추출이 끝난다, **Then** 그 데이터소스의 **테이블·컬럼 벡터가
   생성되어 있고** 상태가 `indexed` 다. (지금은 `data-fabric` 에 임베딩 코드가 0건이라 생기지 않는다)
3. **Given** 색인이 끝났다, **When** US1 의 질문을 다시 한다, **Then** 답이 나오고 근거로
   데이터소스·테이블·행 수를 제시한다.
4. **Given** 이미 설정돼 있다, **When** 다른 데이터소스를 추출한다, **Then** **묻지 않고**
   기존 설정으로 진행한다.
5. **Given** 새 데이터소스를 등록하고 추출한다, **When** 아무 추가 조작도 하지 않는다,
   **Then** 그 데이터소스의 벡터가 생겨 있다.
6. **Given** 색인이 진행 중이다, **When** 상태를 조회한다, **Then** 대상 수·완료 수·실패 수가 온다.

### User Story 2 - `direct-sql` 을 쓰는 서비스들이 아무것도 눈치채지 못한다 (Priority: P1)

domain-layer 와 ontology-studio 는 이 리팩터링을 모른다.

**Why this priority**: 회귀는 새 기능보다 비싸다. 그리고 CR-10 의 8개 호출부는 constitution 원칙 I
이 못박은 계약이다.

**Acceptance Scenarios**:

1. **Given** 스킬 엔진이 기본으로 켜져 있다, **When** `POST /text2sql/direct-sql` 을 호출한다,
   **Then** 요청·응답 스키마와 행 상한 동작이 리팩터링 전과 동일하다.
2. **Given** 같은 상태, **When** ontology-studio 의 가상 클래스 behavior 를 호출한다,
   **Then** 리팩터링 전과 같은 행이 같은 순서로 나온다.
3. **Given** 같은 상태, **When** `GET /text2sql/meta/tables/{t}/columns` 를 호출한다,
   **Then** 응답이 동일하다.

### User Story 3 - 두 백엔드가 같은 스킬로 같은 답에 도달한다 (Priority: P1)

**Why this priority**: 004 FR-020 과 constitution 의 *"에이전트 백엔드는 도구와 프롬프트를
공유한다"* 를 이 스펙이 지키는지가 여기서 갈린다.

**Acceptance Scenarios**:

1. **Given** `skills/text2sql-query/SKILL.md` 하나, **When** 두 백엔드로 각각 골든셋을 돌린다,
   **Then** 두 경로가 읽은 지시문 본문이 **byte 단위로 같다**.
2. **Given** 같은 스킬, **When** 두 경로가 노출받는 도구 목록을 비교한다, **Then** 이름과
   **함수 객체**가 같다 (004 FR-011 과 같은 방식으로 강제).
3. **Given** 골든 질문 20개, **When** 두 백엔드로 돌린다, **Then** 정답 SQL 이 같은 테이블 집합을
   참조하고 실행 결과 행 수가 일치한다.

### User Story 4 - 임베딩 모델을 바꿨을 때 조용히 망가지지 않는다 (Priority: P1)

사용자가 OpenAI 에서 로컬 모델로 바꾼다. 기존 벡터는 무효가 된다.

**Why this priority**: 이것이 재색인 문제이고, **파괴적 작업**이다.
constitution 원칙 IV 가 실제 사고 두 건을 근거로 갖고 있는 영역이다.
조용히 진행하면 사용자는 답이 나빠진 것을 **알 방법이 없다.**

**Acceptance Scenarios**:

1. **Given** 임베딩 제공자를 바꿨다, **When** 시스템이 상태를 판정한다, **Then** 기존 벡터의
   **지문**과 새 설정이 다르다는 것을 감지해 `stale` 로 표시한다.
   (지금은 지문이 없어 감지 자체가 불가능하다 — CR-5c)
2. **Given** `stale` 이다, **When** 데이터소스 질의를 한다, **Then** **낡은 벡터로 답하지 않고
   거부**한다.
3. **Given** `stale` 이다, **When** 재색인이 필요하다, **Then** **묻지 않고 시작하지 않는다.**
   확인 화면에 대상 테이블·컬럼 수, 예상 시간, 유료면 예상 비용, **되돌릴 수 없다는 사실**이 있다.
4. **Given** 사용자가 확인했다, **When** 재색인이 돈다, **Then** 지워지는 것은 **벡터·지문
   속성뿐**이고 `(:Table)`/`(:Column)` 노드는 그대로다.
5. **Given** 데이터소스가 둘이고 하나만 재색인한다, **When** 끝난다, **Then** 다른 데이터소스의
   벡터가 **그대로 남아 있다.**
6. **Given** 재색인이 절반쯤 돌았다, **When** 질의한다, **Then** 지문이 맞는 노드만 검색 대상이
   되고, 상태가 `indexing` 으로 표시된다. **옛 벡터와 새 벡터가 섞여 검색되지 않는다.**
7. **Given** 재색인이 도중에 죽었다, **When** 다시 시작한다, **Then** 이미 끝난 노드를 건너뛰고
   **재개**한다. (노드별 지문이 이것을 가능하게 한다 — FR-050)
8. **Given** 인덱스 차원과 설정 차원이 다르다, **When** 기동한다, **Then** 추측해서 진행하지 않고
   **거부**한다.

### User Story 5 - 분석기가 키 없이 결정론 단계를 완주한다 (Priority: P1)

증거 11 이 멈춘 자리 — `scan_codebase` 3단계 — 를 지난다.

**Why this priority**: 증거 11 의 표에서 ❌ 가 시작되는 정확한 지점이다.

**Acceptance Scenarios**:

1. **Given** LLM 키가 없다, **When** 로컬 폴더로 분석을 시작한다, **Then** DDL 파싱·AST 적재·
   결정론 링킹(CALLS·READS/WRITES)까지 완주하고 NDJSON 이 `stream_end` 로 끝난다.
2. **Given** 같은 실행, **When** Neo4j 를 본다, **Then** 노드·관계가 기존 `robo-data-analyzer` 와
   **같은 라벨·같은 관계 타입**으로 들어가 있다.
3. **Given** 의미 분석 단계, **When** `AGENT_BACKEND=cliagents` 다, **Then** CLI 에이전트가
   스킬로 노드 의미 루프를 돌고 LLM 키를 요구하지 않는다.
4. **Given** 실패한 단계가 있다, **When** 스트림이 끝난다, **Then** 실패 원인이 **사용자에게 보이는
   메시지**로 전달된다 — 증거 11 §3-2 의 `emit_after_close` 로 드롭되지 않는다.

### User Story 6 - 신·구 분석기를 나란히 두고 결과를 대조한다 (Priority: P2)

**Acceptance Scenarios**:

1. **Given** 두 서비스가 각각 다른 포트에 떠 있다, **When** 같은 코드베이스를 두 번 분석한다,
   **Then** 노드·관계의 **양방향 차집합**이 리포트로 나온다.
2. **Given** 차이가 있다, **When** 리포트를 본다, **Then** 각 차이가 규칙으로 설명되거나
   **결함으로 분류**된다. 원인 불명 0건이어야 신 서비스를 기본으로 올릴 수 있다.

### User Story 7 - 5,009줄이 사라져도 되돌릴 수 있다 (Priority: P2)

**Acceptance Scenarios**:

1. **Given** 스킬 엔진이 기본이다, **When** `TEXT2SQL_ENGINE=controller` 로 되돌린다,
   **Then** 재기동만으로 이전 동작이 돌아온다.
2. **Given** 컨트롤러 삭제 단계가 끝났다, **When** 골든셋을 돌린다, **Then** 삭제 직전 실행과
   같은 결과를 낸다.

### Edge Cases

- **임베딩 엔드포인트가 도중에 죽는다**: 색인은 실패로 기록하고 재개 가능하게 둔다.
  질의 경로는 질문을 임베딩할 수 없으므로 **거부**한다 — 벡터축 없이 답을 지어내지 않는다(AD-4).
- **인덱스 차원 불일치**: 조용히 섞지 않고 거부한다 (US4-8).
- **차원은 같은데 모델이 다르다**: 인덱스 검사로는 안 잡힌다. **지문**만이 잡는다 (CR-5c).
  지문이 없는 기존 벡터(리팩터링 이전에 만들어진 것)는 **`stale` 로 간주**한다 —
  모르는 것을 안다고 하지 않는다.
- **색인은 됐는데 데이터소스에 테이블이 추가됐다**: 없는 것만 자동으로 채운다(FR-052).
  기존 벡터를 건드리지 않으므로 확인을 받지 않는다.
- **한 데이터소스만 재색인하는데 다른 데이터소스 테이블이 같은 `schema.table` 이름을 갖는다**:
  constitution 원칙 II 의 노드 합쳐짐 문제가 그대로 재현된다.
  `(t.datasource = $ds OR t.db = $ds)` 를 반드시 함께 쓴다 (FR-055).
- **에이전트가 도구 없이 SQL 을 지어낸다**: `guard_sql` 을 통과하지 않은 SQL 은 실행 경로에
  도달할 수 없다. 스킬이 부탁하는 것이 아니라 **도구 표면이 강제**한다.
- **에이전트가 무한 루프에 든다**: 예산(도구 호출 수·벽시계 시간)이 값 블록으로 주입되고,
  소진 시 라우터가 턴을 끊는다. 지금 `remaining_tool_calls`(`app/react/state.py`)가 하던 일이다.
- **cliagents 인데 CLI 가 없다**: 004 Edge Case 그대로 — 조용히 대체하지 않고 설치 힌트를 담은
  오류를 낸다.
- **Codex 는 실행 중 스티어링을 못 받는다**: 004 실측 그대로. 긴 분석 실행에서 이 제약이 더
  아프다. 거부를 반환한다(FR-053).
- **분석기 NDJSON 이 `stream_end` 없이 끊긴다**: consumer 가 hang 한다
  (`/tmp/robo-skill-analyzer/specs/002-.../contracts/ndjson-contract.md` 불변식). 새 서비스는
  예외 경로에서도 센티넬을 보낸다.

---

## Requirements *(mandatory)*

### Functional Requirements — 안전망이 먼저다

- **FR-001**: 컨트롤러의 어떤 코드도 삭제하기 **전에**, 현재 동작을 고정하는 골든 질의 세트와
  기록된 실행 결과가 있어야 한다. 최소 20질의, 실제 데이터소스 대상.
- **FR-002**: `parse_validate_sql` · `compute_score_and_accept` · `sql_transform` ·
  `sql_mindsdb_prepare` · `sql_autorepair` 에 단위 테스트가 있어야 한다. 이 다섯은 도구로 승격되며
  지금 테스트가 0개다 (CR-12).
- **FR-003**: 깨진 테스트 수집 오류(`app/tests/react/test_intent_keyword_json_parsing.py`)와
  틀린 테스트 경로(`Makefile:35`)를 고쳐야 한다. 테스트 스위트가 실제로 돌아야 안전망이 된다.
- **FR-004**: 데드코드를 **명시적 목록으로** 삭제해야 한다 — `score_sql` 및 그것만 참조하는 6개
  함수(약 300줄), `compact_build_sql_context`(no-op), 제너레이터 3개, 프롬프트 2개. 삭제 후에도
  FR-001 골든셋이 같은 결과를 내야 한다.

### Functional Requirements — 도구 계층

- **FR-010**: AD-2 의 8개 도구는 **LLM 을 호출하지 않아야 한다.**
- **FR-011**: 8개 도구는 스킬 엔진과 컨트롤러 엔진이 **같은 구현**을 써야 한다. 두 벌을 만들면 안
  된다.
- **FR-012**: 도구는 `agent_bridge_mcp` 를 통해 노출되며, 내장 경로가 쓰는 **같은 함수 객체**여야
  한다 (004 FR-011 과 동일 규칙, 같은 방식으로 테스트).
- **FR-013**: `guard_sql` 을 통과하지 않은 SQL 은 실행 도구에 도달할 수 없어야 한다.
- **FR-014**: 도구 응답에는 접속 정보와 내부 SQL 원문이 포함되지 않아야 한다
  (constitution 원칙 V). 데이터소스는 **이름으로만** 지칭한다.

### Functional Requirements — 임베딩 제공자 (능력 확보)

- **FR-020**: `EMBEDDING_PROVIDER` 는 **`llm_endpoint`**(제공 LLM 엔드포인트 재사용) /
  **`openai`** / **`local`**(번들 모델) 셋을 받아야 한다.
- **FR-021**: 임베딩 클라이언트는 **`base_url` 을 받아야 한다.** 지금은 받지 않는다 —
  `app/core/llm_factory.py:116-118` 의 `AsyncOpenAI(api_key=api_key)`.
  **이것을 고치지 않으면 "로컬 모델" 선택지가 화면에만 존재하고 실제로는 OpenAI 로 나간다.**
- **FR-022**: `EmbeddingClient` 의 **openai 전용 제약을 제거해야 한다** —
  `app/core/embedding.py:13-17` 이 `provider != "openai"` 를 `NotImplementedError` 로 막는다.
  FR-021 과 이 둘이 함께 고쳐져야 FR-020 이 성립한다.
- **FR-023**: 임베딩 벡터를 만드는 지점은 **앱 전역에서 한 곳**이어야 한다. 추출 경로와 질의
  경로가 같은 엔드포인트를 호출해야 한다 (AD-5 — 불일치를 구조적으로 불가능하게 만든다).
- **FR-024**: 임베딩 설정은 **앱 전역 한 벌**이어야 한다. 데이터소스별로 다르게 둘 수 없다.

### Functional Requirements — 색인은 메타데이터 증강의 단계다

- **FR-025**: 데이터소스 메타데이터 추출은 **테이블·컬럼 임베딩 생성을 자기 단계로 포함**해야
  한다. 지금은 `data-fabric/backend/app` 에 임베딩 코드가 **0건**이다.
- **FR-026**: text2sql 기동은 **색인 여부와 무관**해야 한다. 지금은
  `ensure_text_to_sql_table_vectors`(`app/main.py:72`)가 블로킹으로 돌고 키가 없으면 기동이
  실패한다. 이 잡은 기동 경로에서 빠지거나 비블로킹이 되어야 한다.
- **FR-027**: 새 데이터소스를 등록하고 추출하면 **추가 조작 없이** 그 데이터소스의 테이블·컬럼
  벡터가 생겨야 한다.
- **FR-028**: 색인 진행 상황이 관측 가능해야 한다 — 대상 수 / 완료 수 / 실패 수.

### Functional Requirements — 색인 상태와 거부

- **FR-030**: 시스템은 데이터소스별 색인 상태를 **`indexed` / `indexing` / `stale` /
  `unindexed`** 로 판정할 수 있어야 한다 (AD-4 표).
- **FR-031**: `unindexed` 또는 `stale` 상태에서 **데이터소스 자연어 질의는 거부되어야 한다.**
  벡터축을 뺀 채 답을 내지 않는다. **나쁜 답 대신 명시적 거부다.**
- **FR-032**: 거부는 **무엇이 안 되는지와 무엇을 하면 되는지**를 함께 전달해야 한다.
  온톨로지 설계·그래프 조회가 계속 가능하다는 사실을 포함한다.
- **FR-033**: 이 상태는 UI 가 표시할 수 있도록 **API 로 노출**되어야 한다. 로그에만 남기면
  사용자는 이유를 모른 채 "안 된다"만 본다.
- **FR-034**: `indexing` 중의 다축 폴백은 **일시적 열화로 표시**되어야 한다.
  `unindexed` 를 가리는 데 쓰지 않는다.

### Functional Requirements — 임베딩 설정 수집

- **FR-040**: 임베딩 설정이 없는 상태에서 **메타데이터 추출을 시작하는 순간** 사용자에게
  물어야 한다. 설정 파일을 손으로 열게 하지 않는다.
- **FR-041**: 선택지는 FR-020 의 셋이어야 하고, 각각의 **대가가 화면에 보여야** 한다 —
  데이터 외부 전송 여부, 메모리 비용, 키 필요 여부.
- **FR-042**: **이미 설정돼 있으면 묻지 않고 그대로 쓴다.** 선례와 같은 원칙이다 —
  첫 실행 에이전트 선택 화면이 `stack.json` 의 `agentConfigured` 로 재질문을 막는다
  (`agent-backend-and-llm-access.md` §구현됨).
- **FR-043**: 선택 결과는 **줄 단위 갱신으로 기록**되어야 한다 (주석·다른 키 보존).
  선례: `settings.updateEnv`.
- **FR-044**: 나중에 **다시 고를 수 있어야** 한다. 선례: 메뉴 「런타임 → 에이전트 백엔드 변경…」.
- **FR-045**: 설정 변경이 지문 불일치를 낳으면 FR-053 의 확인 절차로 이어져야 한다.
  묻지 않고 재색인을 시작하지 않는다.

### Functional Requirements — 지문과 재색인

- **FR-050**: 벡터를 쓸 때 **어떤 모델·어떤 차원으로 만들었는지를 노드마다 함께 기록**해야
  한다. 지금은 아무 데도 기록되지 않는다 (CR-5c). **노드별**이어야 부분 실패에서 재개할 수 있다.
- **FR-051**: 인덱스 차원과 설정 차원이 다르면 **거부**해야 한다. 추측해서 진행하지 않는다.
- **FR-052**: 벡터가 **하나도 없는** 상태(콜드 스타트)와 **일부만 없는** 상태에서는 자동으로
  채워야 한다. 지울 것이 없으므로 파괴적이지 않다. 판정에는 기존
  `text2sql_runtime_repair.py:124-136` 의 `cold_start_detected` 를 재사용한다.
- **FR-053**: 지문 **불일치**(모델·차원 변경)로 인한 재색인은 **사용자 확인 없이 시작하면
  안 된다.** 확인 화면에는 대상 테이블·컬럼 수, 예상 시간, 유료 제공자면 예상 비용,
  재색인 중 질의 상태, **되돌릴 수 없다는 사실**이 있어야 한다.
- **FR-054**: 재색인의 삭제 범위는 **벡터 및 지문 속성으로 한정**되어야 한다.
  `(:Table)` / `(:Column)` 노드 자체를 지우면 안 된다 (constitution 원칙 I·IV).
  전역 삭제(`MATCH (n) DETACH DELETE n`)는 금지다.
- **FR-055**: 재색인 범위는 **데이터소스 단위로 좁혀져야** 한다.
  `(t.datasource = $ds OR t.db = $ds)` 를 항상 함께 쓴다 (constitution 원칙 II).
  그러지 않으면 한 데이터소스의 재색인이 다른 데이터소스의 벡터를 지운다.
- **FR-056**: 재색인 중 검색은 **지문이 현재 설정과 일치하는 노드만** 대상으로 해야 한다
  (AD-5b 권고 5 의 안 B). 옛 벡터와 새 벡터를 섞어 검색하면 안 된다.

### Functional Requirements — 스킬

- **FR-060**: text2sql 지시문은 `skills/text2sql-query/SKILL.md` 하나가 원천이어야 한다.
  두 백엔드가 그 파일을 읽는다 (constitution — *"지시문은 `skills/<name>/SKILL.md` 하나가 원천"*).
- **FR-061**: 스킬은 agentskills.io 규격을 따라야 한다 — 폴더 하나 = 스킬 하나, 프론트매터,
  폴더 이름과 `name` 일치. 005 가 정한 것과 같다.
- **FR-062**: 스킬 본문에 **수치 파라미터를 쓰지 않아야 한다.** 후보 수·임계값·재시도 상한은
  값 블록으로 주입한다.
- **FR-063**: 스킬은 **셸 명령을 지시하지 않아야 한다** (AD-3). 능력은 도구 이름으로 지목한다.
- **FR-064**: 스킬은 자기가 받을 값과 **빠졌을 때 무엇을 할지**를 본문에 가져야 한다
  (constitution). `ontology-build/SKILL.md:52-88` 의 「표 + 절차 + 금지」 3단 관례를 따른다.
- **FR-065**: 본문이 길면 참조 자료로 나누되, 본문이 **각 참조 자료를 언제 읽는지 지목**해야 한다.
  005 의 분량 테스트(`test_skill_content_migration.py:96-125`)를 그대로 통과해야 한다.
- **FR-066**: 두 백엔드가 참조 자료를 **실제로 읽을 수 있어야** 한다. deepagents 는
  `skill_sync.sync_to_sandbox()`, cliagents 는 `provider.emit()` 경로다.

### Functional Requirements — 대외 계약 보존

- **FR-070**: `POST /text2sql/direct-sql` 의 요청·응답 스키마와 동작이 변하지 않아야 한다.
- **FR-071**: `GET /text2sql/meta/*` 가 변하지 않아야 한다.
- **FR-072**: `POST /text2sql/react` 의 NDJSON 이벤트 이름 집합이 유지되어야 한다.
- **FR-073**: 인메모리 캐시 HIT 경로는 에이전트를 띄우지 않고 지금과 같이 동작해야 한다.
- **FR-074**: Neo4j `:Query` 지식캐시 저장이 계속 동작해야 하며, **저장 건수 0** 은 회귀로 간주한다.
  fail-closed 게이트(judge 2라운드 전부 confidence ≥ 0.90)는 그대로다.
- **FR-075**: `conversation_state` 필드는 유지되어야 한다. 내용 형식은 바뀔 수 있다.

### Functional Requirements — 엔진 전환

- **FR-080**: `TEXT2SQL_ENGINE=controller|skill` 로 엔진을 고를 수 있어야 하고, 기본값은 전환
  완료 전까지 `controller` 여야 한다.
- **FR-081**: 분기는 **한 곳**에서만 일어나야 한다 (004 FR-002 와 같은 규칙).
- **FR-082**: 컨트롤러 삭제는 스킬 엔진이 골든셋에서 동등 이상을 낸 **이후에만** 한다.

### Functional Requirements — 분석기 (신규 마이크로서비스)

- **FR-090**: 새 서비스는 `POST /robo/analyze` 를 **기존과 같은 NDJSON 계약**으로 제공해야 한다
  (CR-16). 프론트·게이트웨이·데스크톱 셸이 바뀌지 않아야 한다.
- **FR-091**: 스트림은 **어떤 실패 경로에서도** 종료 센티넬로 끝나야 한다. 증거 11 §3-2 의
  `emit_after_close` 드롭이 재발하면 안 된다.
- **FR-092**: 결정론 엔진(`skillkit` 상당)은 **LLM·임베딩·HTTP 클라이언트를 import 하지 않아야**
  한다. grep 으로 재증명한다.
- **FR-093**: 결정론 엔진은 `verify` 와 `apply` 가 **같은 코어 함수**를 공유해야 한다
  (단일 엔진 원칙 — `/tmp/robo-skill-analyzer/skillkit/regex_link.py:1-6`).
- **FR-094**: Neo4j 쓰기는 **allowlist 밖 데이터베이스에 대해 드라이버 생성 전에 거부**해야 한다.
  constitution 원칙 IV 를 코드로 강제한다.
- **FR-095**: 노드 라벨·관계 타입은 기존 `robo-data-analyzer` 스키마를 따라야 한다 (AD-6).
- **FR-096**: 의미 분석 루프는 `AGENT_BACKEND` 를 따라야 한다. `cliagents` 면 CLI 에이전트가
  스킬로 돌고 LLM 키를 요구하지 않는다.
- **FR-097**: cliagents 경로의 스킬 지시문은 **byte-stable** 이어야 한다 — 타임스탬프·실행 ID·
  날짜·모드·사용자명 같은 가변값을 담지 않는다 (CR-13).
- **FR-098**: 프레임워크 패턴은 **코드에 하드코딩하지 않아야** 한다. 런타임 발견(scan) 결과를
  프로파일로 고정한다. 기존 `robo-data-analyzer/skills/` 의 6개 하드코딩 스킬이 대체 대상이다.
- **FR-099**: 판정 기준은 **선고정**되어야 한다. 결과 대조에서 불일치가 난 뒤 사후에 설명을
  만들어 붙이는 것을 금지한다.
- **FR-100**: 번들 로컬 임베딩 모델을 쓰는 경우, 그 모델은 **분석기 서비스가 호스트**하고
  `POST /robo/embed` 로 노출해야 한다 (AD-5). data-fabric 의 색인 단계와 text2sql 의 질의 시점이
  **같은 엔드포인트**를 호출해야 한다 — 모델 불일치를 구조적으로 불가능하게 만드는 것이 목적이다.
  스택에 임베딩 모델이 두 벌 로드되면 안 된다.
- **FR-101**: `ANALYZER_IMPL=legacy|skill` 로 신·구를 고를 수 있어야 하며, 기본값은 대조가
  끝나기 전까지 `legacy` 여야 한다.

### Functional Requirements — 증거

- **FR-110**: 구현 작업은 **영상 증거 없이 완료로 치지 않는다.** 전략 문서 §6 「완료 판정 규칙」이
  요구하는 형식 그대로다:

  > | 항목 | 요구 |
  > |---|---|
  > | 실행 증거 | **실제 UI 를 띄운 화면 녹화(mp4/webm)** 또는 단계별 스크린샷 |
  > | 생성 경로 | `ontology-studio/demo/` 의 기존 Playwright 파이프라인 재사용 |
  > | 보관 위치 | `docs/business/evidence/<작업번호>-<이름>/` — 영상 + 캡처 + `README.md` |
  > | 실패 시 | 되지 않는 부분은 숨기지 말고 **그대로 녹화하고** 무엇이 안 되는지 적는다 |

  ↳ `docs/business/ontology-studio-strategy.md:290-306`

- **FR-111**: 증거 디렉터리는 `docs/business/evidence/12-skill-based-text2sql/` 과
  `docs/business/evidence/13-skill-based-analyzer/` 로 하고, 기존 README 관례(결론 먼저 → 파일 →
  안 되는 것 → 재현 절차 → 함께 고친 것 → 사람이 판단할 것)를 따른다.
- **FR-112**: 증거에는 다음 세 화면이 반드시 포함되어야 한다. 로그로는 증명되지 않는다.
  1. **임베딩 미설정 상태에서 앱이 뜨고**, 데이터소스 질의가 **이유와 함께 거부**되며,
     온톨로지 설계·그래프 조회는 되는 화면
  2. **메타데이터 증강을 시작하는 순간 임베딩 설정을 묻는 화면**, 그리고 두 번째 실행에서
     **묻지 않는** 화면
  3. 색인 완료 후 **같은 질문에 답이 나오는** 화면
- **FR-113**: 재색인 확인 화면이 **대상 수·예상 시간·되돌릴 수 없음**을 보여 주는 캡처가
  포함되어야 한다 (FR-053). 파괴적 작업의 동의 절차는 화면으로만 증명된다.

### Key Entities

| 개념 | 설명 |
|---|---|
| `text2sql-query` 스킬 | text2sql 질의 절차의 단일 지시문 원천. 두 백엔드가 읽는다 |
| 결정론 도구 8종 | AD-2 의 도구 표면. LLM 0 |
| 임베딩 제공자 심 | `openai` / `local` / `none` 을 가르는 한 곳 |
| 값 블록 | 예산·임계값·경로를 스킬에 넘기는 라벨+값 묶음. 설명 문장 없음 |
| `TEXT2SQL_ENGINE` | 컨트롤러 / 스킬 엔진 선택 |
| 골든 질의 세트 | 리팩터링 전후를 비교하는 기준. FR-001 |
| skillkit(신) | 분석기의 결정론 엔진. LLM 0, verify==apply |
| scan 프로파일 | 런타임 발견 결과. byte-stable, 프레임워크 하드코딩 대체 |
| `ANALYZER_IMPL` | 신·구 분석기 선택 |
| 대조 리포트 | 신·구 분석기 결과의 양방향 차집합 |

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: `OPENAI_API_KEY` 와 `GOOGLE_API_KEY` 가 **둘 다 빈 상태**에서 text2sql `/health` 가
  200 을 반환한다. (지금은 `RuntimeError`) 그리고 그 상태에서 데이터소스 질의는
  **거부되지만 온톨로지 설계·그래프 조회는 동작한다.**
- **SC-002**: 같은 상태에서 `AGENT_BACKEND=cliagents` 로 골든 질의 20개 중 **정답 도달률이
  현재 컨트롤러 대비 하락하지 않는다.** 하락하면 전환하지 않는다.
- **SC-003**: 두 백엔드가 읽은 지시문 본문이 **byte 단위로 같다** (`sha256` 비교).
- **SC-004**: 두 백엔드에 노출된 도구 목록이 **이름과 함수 객체 모두** 같다.
- **SC-005**: 도구 8종 구현 모듈에서 `openai|anthropic|langchain|litellm|api_key` grep 결과가
  **0건**이다. (robo-skill-analyzer SC-005 를 빌린 형태)
- **SC-006**: 임베딩 미설정 상태에서 데이터소스 질의를 하면 **답이 아니라 거부가 온다.**
  거부 메시지에 이유와 다음 행동이 있다. (앞선 판의 "저하 모드로 답한다"를 대체한다)
- **SC-006b**: 데이터소스를 등록하고 메타데이터 추출을 실행하면, **추가 조작 없이**
  그 데이터소스의 `(:Table).text_to_sql_vector` 와 `(:Column)` 벡터가 **0건이 아니다.**
  (지금은 추출만으로는 0건이다 — `data-fabric` 임베딩 코드 0건)
- **SC-006c**: 임베딩 설정을 한 번 하고 나면 두 번째 데이터소스 추출에서 **묻지 않는다.**
- **SC-006d**: 모든 벡터에 **모델·차원 지문이 붙어 있다.** 지문 없는 벡터가 0건이다.
- **SC-006e**: 임베딩 제공자를 바꾸면 상태가 `stale` 로 바뀌고 데이터소스 질의가 거부되며,
  **사용자 확인 전에는 재색인이 시작되지 않는다.**
- **SC-006f**: 데이터소스 A 를 재색인해도 데이터소스 B 의 벡터 수가 **변하지 않는다.**
- **SC-006g**: 재색인을 중간에 죽였다가 다시 시작하면 **이미 끝난 노드를 다시 임베딩하지 않는다.**
- **SC-006h**: `EMBEDDING_PROVIDER` 를 OpenAI 가 아닌 값으로 두고 임베딩을 요청하면
  `NotImplementedError` 가 **나지 않는다.** (지금은 `embedding.py:13-17` 이 던진다 —
  이 하나가 "로컬 모델" 선택지 전체를 막고 있다)
- **SC-007**: `POST /text2sql/direct-sql` 의 응답이 리팩터링 전후로 **바이트 동일**하다
  (같은 입력·같은 데이터).
- **SC-008**: Neo4j `:Query` 지식캐시 저장 건수가 리팩터링 전후로 **0 이 아니다.**
- **SC-009**: `TEXT2SQL_ENGINE=controller` 로 되돌리면 재기동만으로 이전 동작이 복원된다.
- **SC-010**: 컨트롤러 삭제 후 `app/react/` 의 줄 수가 **16,485 → 6,000 미만**이 된다.
  (이 숫자는 목표이지 합격선이 아니다 — 합격선은 SC-002 다)
- **SC-011**: 분석기 결정론 엔진 모듈에서 LLM/API/HTTP grep 결과가 **0건**이다.
- **SC-012**: LLM 키 없이 분석기가 결정론 단계를 완주하고 NDJSON 이 종료 센티넬로 끝난다.
  증거 11 의 표에서 ❌ 였던 항목 중 결정론에 해당하는 것이 ✅ 로 바뀐다.
- **SC-013**: 신·구 분석기의 양방향 차집합에서 **원인 불명 차이가 0건**이다.
- **SC-014**: 새 분석기가 allowlist 밖 Neo4j DB 에 대해 **연결 자체를 거부**한다 (테스트로 강제).
- **SC-015**: 증거 디렉터리 두 개가 존재하고 각각 **영상 또는 단계별 스크린샷**과 README 를 갖는다.
  키 없이 답이 나오는 화면이 포함된다.
- **SC-016**: 데스크톱 core 팩의 유휴 메모리를 **리팩터링 전후로 같은 방법으로 재측정**해
  `memory-footprint-measurement.md` 에 라운드를 추가한다. (증가/감소 방향을 미리 약속하지 않는다 —
  CR-17 근거로 큰 변화를 기대하지 않는다)

---

## 단계 계획

**5,009줄을 한 번에 걷어내는 계획은 실행 불가능하다.** 각 단계는 되돌릴 수 있고, 끝났을 때
무엇이 동작하는지가 정해져 있다.

두 트랙(T = text2sql, A = analyzer)은 **병렬로 갈 수 있다.** 유일한 결합점은 AD-5(임베딩 소유권)
이고, 그것은 T2 와 A2 사이에 있다.

### T0 — 안전망 (동작 변화 0)

- 골든 질의 20개 + 기록된 실행 결과 (FR-001)
- 다섯 모듈 단위 테스트 (FR-002), 깨진 테스트·경로 수정 (FR-003)
- 데드코드 약 900줄 삭제 (FR-004)

**끝나면 동작하는 것**: 지금과 완전히 동일. 다만 삭제된 900줄이 없고, 테스트 스위트가 실제로 돌며,
"바뀌었는지"를 판정할 기준이 생긴다.

> **개정 (2026-08-03)**: 사업 결정으로 임베딩 트랙이 커졌다. 앞선 판의 T1 하나가 **T1~T5 다섯**이
> 된다. 색인 단계 신설(data-fabric)이 포함되기 때문이다. 여전히 각 단계는 되돌릴 수 있고,
> **T1~T3 은 컨트롤러를 한 줄도 건드리지 않는다.**

### T1 — 임베딩 제공자 심 (능력 확보, 동작 변화 0)

- `EmbeddingClient` 의 openai 전용 제약 제거 (FR-022) — `embedding.py:13-17`
- `base_url` 지원 (FR-021) — `llm_factory.py:116-118`
- `EMBEDDING_PROVIDER` 3값: `llm_endpoint` / `openai` / `local` (FR-020)
- 벡터 생성 지점을 한 곳으로 모음 (FR-023)

**끝나면 동작하는 것**: 겉으로는 변화 없다. **그러나 "로컬 임베딩"이 처음으로 실제 가능해진다** —
사용자가 이미 돌리는 OpenAI 호환 서버를 임베딩에 쓸 수 있다. 이것 없이는 뒤 단계의 설정 화면이
화면에만 존재하게 된다.

### T2 — 지문 (감지 수단, 아직 재색인 없음)

- 벡터 옆에 모델·차원·시각 기록 (FR-050), **노드별**
- 지문 대조로 `indexed`/`indexing`/`stale`/`unindexed` 판정 (FR-030)
- 차원 불일치 거부 (FR-051)
- 지문 없는 기존 벡터는 `stale` 로 간주

**끝나면 동작하는 것**: **무엇이 낡았는지 처음으로 알 수 있다.** 아직 아무것도 지우지 않고
아무것도 다시 만들지 않는다. 진단만 한다. AD-5b 권고 1 — 감지 수단이 정책보다 앞선다.

### T3 — 색인을 메타데이터 증강으로 (가장 큰 단계)

- data-fabric 추출 파이프라인에 임베딩 단계 신설 (FR-025) — 지금 임베딩 코드 **0건**
- 진행 상황 관측 (FR-028), 데이터소스 단위 범위 (FR-055)
- text2sql 기동에서 블로킹 벡터화 잡 분리 (FR-026) — `app/main.py:72`
- 콜드 스타트·부분 결손 자동 채움 (FR-052)

**끝나면 동작하는 것**: **데이터소스를 등록하고 추출하면 벡터가 생긴다** (SC-006b).
text2sql 기동이 색인과 분리되어 크래시 루프가 사라진다. 레거시 두 인덱스도 처음으로 채워진다.

> 이 단계가 CR-5 가 진단한 결함을 닫는다. 앞선 판이 "text2sql 내부 문제"로 다뤘던 것이
> 실은 **여기**였다.

### T4 — 설정 수집 화면 + 상태 표면화

- 추출 시작 시점의 임베딩 선택 화면 (FR-040~041), 각 선택지의 대가 표시
- 이미 있으면 묻지 않음 (FR-042), 줄 단위 기록 (FR-043), 다시 고르기 (FR-044)
- `unindexed`/`stale` 에서 데이터소스 질의 거부 + 안내 (FR-031~033)
- 상태 API 노출 (FR-033)

**끝나면 동작하는 것**: **US1 과 US1b 가 닫힌다.** 설정 파일을 손으로 여는 일이 없어지고,
안 되는 것이 왜 안 되는지 화면에서 보인다. `agent-backend-and-llm-access.md` 의 임시 조치
문구가 정식 상태 표시로 승격된다.

### T5 — 재색인 (확인형)

- 지문 불일치 시 확인 화면 (FR-053) — 대상 수·시간·비용·**되돌릴 수 없음**
- 삭제 범위 한정 (FR-054), 데이터소스 단위 (FR-055)
- 재색인 중 지문 필터 검색 (FR-056), 부분 실패 재개 (FR-050 의 노드별 지문)

**끝나면 동작하는 것**: **US4 가 닫힌다.** 모델을 바꿔도 조용히 망가지지 않고, 파괴적 작업에
동의 절차가 붙는다. 증거 12 의 재색인 확인 캡처(FR-113)를 여기서 찍는다.

> T1~T5 가 끝나면 **컨트롤러를 한 줄도 건드리지 않은 채** 사업 결정 1~4 가 전부 구현된다.
> 아래 T6 부터가 원래의 스킬 리팩터링이다.

### T6 — 도구 계층 추출 (루프 변화 0)

- `build_sql_context` → `search_tables`/`search_columns`/`catalog_context`/`similar_queries`
- `validate_sql` → `guard_sql`/`run_sql_preview`/`explain_sql`
- `embed` 도구화 (T1 의 심을 그대로 쓴다). 컨트롤러가 새 도구를 호출하도록 배선

**끝나면 동작하는 것**: 동작은 T5 와 동일. 도구 8종이 문서화되고 테스트되며 LLM 0 이 grep 으로
증명된다(SC-005). **컨트롤러는 아직 그대로다.**

### T7 — 스킬 초안 + MCP 노출 + 두 번째 엔진

- `skills/text2sql-query/` 작성 (FR-060~066), 프롬프트 일반화 표대로
- `agent_bridge_mcp` 에 모드 추가 (CR-8 의 6곳)
- `TEXT2SQL_ENGINE=skill` 추가, **기본은 `controller`**

**끝나면 동작하는 것**: 두 엔진이 같은 골든셋에서 **나란히 비교 가능**하다. 기본 경로는 아직
컨트롤러이므로 사용자에게는 아무 변화가 없다.

### T8 — 엔진 전환

- 골든셋에서 스킬 엔진이 동등 이상임을 확인 (SC-002)
- 기본값을 `skill` 로. 컨트롤러는 남는다
- 증거 12 마무리 촬영 (FR-110~113)

**끝나면 동작하는 것**: 기본 경로가 스킬. **되돌리기는 환경변수 한 줄** (SC-009).

### T9 — 컨트롤러 제거

- `controller.py`·`conversation_capsule.py`·`generators/` 정리, 프롬프트 3개 삭제
- `routers/react.py` 의 `context_refresh` 루프 정리 (CR-1 의 이중 소유권 해소)
- 배치 잡 2개(`query_quality_gate`, `table_profile`)만 남긴다

**끝나면 동작하는 것**: SC-010. 되돌리기는 이제 git revert 다 — 그래서 T8 을 충분히 오래 둔다.

### 두 트랙의 유일한 결합점

**T3(색인)은 A 트랙에 의존하지 않는다.** `llm_endpoint` 또는 `openai` 제공자만으로 완주할 수
있다 — AD-5 의 1순위가 "사용자가 이미 돌리는 엔드포인트 재사용" 이기 때문이다.

**번들 로컬 모델(`local` 제공자)만이 A 트랙에 걸린다.** 400 MB 스택을 새로 들이지 않고
분석기가 이미 가진 것을 쓰므로, `local` 제공자의 실제 구현은 **A2 이후**로 미룬다.
그때까지 설정 화면의 세 번째 선택지는 "준비 중" 으로 둔다 — **화면에 있는데 안 되는 것보다
낫다** (CR-5b 결과 2 가 경고하는 바로 그 함정이다).

### A1 — 결정론 엔진 이식

- skillkit 설계 이식 (AD-6 표), 기존 Neo4j 스키마 위에 (FR-095)
- throwaway 가드 (FR-094), 단일 엔진 원칙 (FR-093), LLM 0 (FR-092)
- 정답지 대조 도구

**끝나면 동작하는 것**: CLI 로 코드베이스를 분석해 결정론 그래프가 나온다. 서비스는 아직 없다.

### A2 — 새 서비스 골격

- `POST /robo/analyze` NDJSON 동일 계약 (FR-090), 종료 센티넬 보장 (FR-091)
- `POST /robo/embed` (FR-100), `ANALYZER_IMPL` 게이트 (FR-101)
- 새 포트에 기동. **기존 서비스는 그대로 둔다**

**끝나면 동작하는 것**: 키 없이 결정론 단계 완주 (SC-012). 증거 11 의 ❌ 중 결정론 항목이 ✅ 로.
프론트는 `ANALYZER_IMPL` 로 골라 붙는다.

### A3 — 의미 루프 (스킬)

- `analyze-framework` 상당 스킬, byte-stable (FR-097)
- scan 2모드 → 프로파일 (FR-098), 하드코딩 스킬 6개 대체
- `AGENT_BACKEND` 두 경로 (FR-096): cliagents=Bash CLI, deepagents=MCP

**끝나면 동작하는 것**: 키 없이(cliagents) 의미 분석까지 완주.

### A4 — 병행 대조 → 교체

- 실제 코드베이스 2개 이상에서 양방향 차집합, 원인 불명 0건 (SC-013)
- 판정 기준 선고정 (FR-099) — 대조 **전에** 무엇을 합격으로 볼지 적어 둔다
- 기본값을 `skill` 로. 증거 13 촬영

**끝나면 동작하는 것**: 기본 경로가 새 분석기. 되돌리기는 환경변수 한 줄.

### A5 — 레거시 제거

- `robo-data-analyzer` 서브모듈 링크 해제
- 메모리 재측정 (SC-016) — 임베딩 스택이 한 벌인지 확인

**끝나면 동작하는 것**: 스택에서 LangGraph 7단계 파이프라인이 사라진다.

---

## 무엇이 깨지는가 — 정직한 목록

이 변경으로 **잃는 것**이다. 되찾을 계획이 있는 것과 없는 것을 구분했다.

| # | 잃는 것 | 되찾는가 | 근거 |
|---|---|---|---|
| 1 | **재현성.** `_repro_log.py` 의 prompt sha256 + input/response sha256 이 고정된 프롬프트를 전제한다. 에이전트 루프는 턴 구성이 매번 다르다 | **아니오.** 대신 골든셋 회귀로 대체 | `app/react/generators/_repro_log.py` |
| 2 | **`:Query` 지식캐시 payload 형태.** `steps_tail`·`metadata` 가 컨트롤러 구조체에서 온다. 조용히 저장 0건이 될 수 있다 | **예** — FR-074 가 저장 건수 0 을 회귀로 규정 | `routers/react.py:2103,2117-2120` |
| 3 | **`conversation_capsule` (784줄).** base64url 캡슐이 에이전트 스레드 참조로 대체된다 | **필드는 유지**, 내부 형식은 아니다 | FR-075 |
| 4 | **컨트롤러의 명시적 예산 회계.** `remaining_tool_calls`·`iteration` 이 상태로 관리되던 것이 값 블록 + 라우터 절단으로 바뀐다 | **부분적으로.** 정밀도가 떨어진다 | `app/react/state.py` |
| 5 | **피드백 경로** | **잃을 것이 없다** — 이미 고립 노드이고 되먹임 코드가 존재하지 않는다 (CR-11) | `app/routers/feedback.py:55,59-74` |
| 6 | **`explain_analysis` 의 XML 구조화 출력** | **아니오.** PostgreSQL 전용이고 MindsDB 경로는 안 탄다 | `tools/validate_sql.py:303` |
| 7 | **레거시 `/ask` 경로와 `app/core/prompt.py`** | **아니오. 의도적으로 버린다** — 매뉴얼이 이미 "쓰지 말 것"으로 명시 | `app/routers/ask.py` |
| 8 | **`table_vec_index`(레거시 `(:Table).vector`)** | **아니오** — `/ask` 와 함께 정리 | `neo4j_bootstrap.py:113` |
| 9 | **`robo-data-analyzer` 의 프레임워크 스킬 6개** | **일반화로 대체** (FR-098). 다만 하드코딩된 도메인 지식(예: ProFrame SQL_KEY 두 변종)이 scan 으로 재발견되지 않으면 **품질이 떨어진다** — A4 대조가 잡아야 한다 | `robo-data-analyzer/skills/proframe-c-pfm-dbio/SKILL.md` |
| 10 | **분석기의 `enrich_*_from_catalog` 단계** (robo-data-catalog HTTP 연동) | **A3 에서 유지해야 한다.** robo-skill-analyzer 에는 이 단계가 없다 — 이식 시 빠지기 쉽다 | `robo-data-analyzer/shared/catalog_http.py` |
| 11 | **`direct_sql` 의 AI 요약** (`format_with_ai`) | **선택 기능으로 강등.** LLM 없으면 원시 결과만 | `app/routers/direct_sql.py:384,395,423` |
| 12 | **"임베딩 없이도 데이터소스 질의가 된다"는 가능성** | **의도적으로 버린다.** 앞선 판이 이것을 저하 모드로 두려 했으나 사업 결정으로 폐기됐다. 대신 **왜 안 되는지 알려 준다** | AD-4 |
| 13 | **재색인 전의 옛 벡터** | **되찾을 수 없다.** 재생성 외에 복구 경로가 없다 — 그래서 확인을 받는다 (FR-053) | AD-5b 권고 3 |
| 14 | **지문 없는 기존 벡터** (리팩터링 이전 생성분) | **`stale` 로 간주해 한 번 다시 만든다.** 무엇으로 만들었는지 알 수 없으므로 신뢰할 근거가 없다 | CR-5c |

**가장 조용히 깨질 것은 2번이다.** 지식캐시는 백그라운드 워커라 실패해도 요청이 성공한다.
저장 건수를 세지 않으면 몇 주 뒤에 "유사 쿼리가 왜 안 뜨지"로 발견된다.

---

## Assumptions

- **모델 품질 차이는 이 스펙의 범위가 아니다.** 004 가 이미 Out of Scope 로 선언했다.
  이 스펙은 *능력* 차이만 없앤다 (AD-3).
- **cliagents 는 answer 계열 모드에서도 로컬 Bash 가 열려 있다** — 모드는 MCP URL 만 바꾼다
  (`cliagents_backend.py:634-640`). 이 비대칭은 이 스펙이 없애지 않는다. 스킬 본문이 셸을
  지목하지 않으므로 **결과에는 영향이 없어야 한다**는 것이 가정이고, 대조로 확인한다.
- **골든셋은 예제 데이터(manufacturing/insurance/sales) 위에서 만든다.** 실고객 데이터가 없다.
- **분석기의 Neo4j 스키마를 바꾸지 않는다**는 전제 위에서만 robo-data-catalog·
  robo-data-frontend 가 범위 밖이다.
- **`skills/` 폴더는 ontology-studio 저장소에 있다.** text2sql 스킬을 거기에 두면
  `neo4j-text2sql` 서브모듈만 클론한 사람은 스킬을 못 얻는다. §미결정 항목 4번.
- **임베딩 설정을 묻는 화면은 첫 실행 에이전트 선택 화면과 같은 기법으로 만들 수 있다.**
  선례가 동작하는 형태로 존재한다 — `desktop/src/renderer/boot.html` 의 `#agent-select`,
  `settings.updateEnv`(줄 단위 갱신), `stack.json` 의 `agentConfigured`(재질문 차단),
  메뉴 「런타임 → …변경」(다시 고르기). **다만 묻는 시점이 다르다** — 에이전트 선택은 부팅 전,
  임베딩 설정은 **메타데이터 추출을 시작할 때**다. 부팅 전으로 당기면 데이터소스를 아직 등록하지
  않은 사용자에게 무의미한 질문을 하게 된다.

---

## 개정 기록

### 2026-08-03 — 임베딩의 지위와 색인의 자리

**무엇이 뒤집혔는가.** 초판은 임베딩을 *text2sql 내부 문제*로 다뤘고, `none` 을 *정상 동작하는
저하 모드*로 설계했다. 둘 다 틀렸다.

| | 초판 | 개정 |
|---|---|---|
| 임베딩의 지위 | 선택. 없으면 검색 품질만 떨어짐 | **데이터소스 질의의 필수 선행 조건** |
| `none` | 정상 저하 모드 (벡터축 빼고 답함) | **질의 불가 상태.** 답이 아니라 거부 |
| 결함의 위치 | text2sql 이 임베딩을 OpenAI 에 고정 | **메타데이터 추출에 색인 단계가 통째로 없다** |
| 색인 소유 | text2sql 기동 잡 | **메타데이터 증강 단계** |
| 로컬 임베딩 비용 | 400 MB 기정사실 | **1순위는 0 MB** (기존 엔드포인트 재사용) |
| 재색인 | "차원 다르면 거부" 한 줄 | **AD-5b — 지문·확인·좁은 삭제·필터 검색** |
| T 트랙 | 5단계 | **9단계** (색인 신설 때문) |

**왜 초판이 틀렸는가.** 초판은 `EMBEDDING_PROVIDER` 가 text2sql 설정이라는 사실에서 출발해
"text2sql 이 임베딩을 잘못 다룬다"로 진단했다. 그러나 실제로 확인해야 했던 것은 **누가 벡터를
채우는가**였고, 그 답이 "아무도" 였다 (CR-5). 진단이 한 단계 얕았다.

**초판에서 살아남은 것.** AD-4(a) — *임베딩은 스킬로 옮겨지지 않고 도구로 남는다*.
CLI 에이전트가 벡터를 만들 수 없다는 사실은 사업 결정과 무관하게 참이고, 이 스펙의 가장 확실한
결론이다.

---

## 구현 상태 (2026-08-03)

**T1~T4 만 구현했다.** T5(재색인)·T6~T9(스킬화)·A 트랙 전체는 미착수다.
`app/react/controller.py` 는 한 줄도 바뀌지 않았다.

증거: [`docs/business/evidence/12-embedding-indexing/README.md`](../../docs/business/evidence/12-embedding-indexing/README.md)

### 끝난 FR

| FR | 상태 | 어디에 |
|---|---|---|
| FR-003 (깨진 테스트 경로) | ✅ | `neo4j-text2sql/Makefile` — `pytest tests/` → `app/tests` + PYTHONPATH |
| FR-020 (제공자 3값) | ✅ | `llm_factory.normalize_embedding_provider`. `local` 은 "준비 중" 으로 명시 거부 |
| FR-021 (`base_url`) | ✅ | `llm_factory.resolve_embedding_endpoint` + `_get_embedding_async_client_cached` |
| FR-022 (openai 전용 제약 제거) | ✅ | `core/embedding.py` — 생성자의 `NotImplementedError` 삭제 |
| FR-023 (벡터 생성 지점 한 곳) | ✅ | `create_embedding_client()` 단일 진입점. data-fabric 은 임베딩을 만들지 않고 text2sql 을 부른다 |
| FR-024 (앱 전역 한 벌) | ✅ | 데스크톱 설정이 전역 env 한 벌. 데이터소스별 설정을 만들지 않았다 |
| FR-025 (추출이 색인을 포함) | ✅ | `data-fabric/.../vector_indexing.py` + `schema_introspection.extract_and_store` 의 `indexing` 단계 |
| FR-026 (기동 ≠ 색인) | ✅ | `main.py` — 기동 잡 기본 꺼짐 + 켜도 비블로킹. sanity check 의 LLM/임베딩 항목을 경고로 강등 |
| FR-027 (추가 조작 없이 벡터 생성) | ✅ | 실측: `sales` 추출 → 컬럼 벡터 32건 |
| FR-028 (진행 관측) | ✅ | `index_status` 의 작업 등록부 + 추출 응답 메시지의 색인 건수 |
| FR-030 (4상태 판정) | ✅ | `core/index_status.py` |
| FR-031 (거부) | ✅ | `routers/react.py` 의 색인 게이트 (컨트롤러 **진입 전**) |
| FR-032 (이유 + 다음 행동) | ✅ | `index_status.rejection_payload` — 온톨로지 설계·그래프 조회 가능 사실 포함 |
| FR-033 (상태 API) | ✅ | `GET /text2sql/index/status`, `GET /text2sql/index/embedding-config` |
| FR-034 (indexing 은 일시적 열화 표시) | ⚠️ 부분 | 상태 응답에 `degraded` 플래그만. 다축 폴백 자체는 손대지 않았다 |
| FR-040 (추출 시작 시 질문) | ✅ | 데스크톱 `#embedding-select` + `embedding:ensure-configured` IPC. **트리거(「메타데이터 증강」 버튼)도 새로 만들었다** — 이 제품에 추출을 시작하는 UI 가 없었다 |
| FR-041 (대가 표시) | ✅ | 화면에 세 선택지의 대가. `05-embedding-select.png` |
| FR-042 (이미 있으면 안 묻기) | ✅ 코드 / ⚠️ 화면 미촬영 | `stack.json` 의 `embeddingConfigured` |
| FR-043 (줄 단위 기록) | ✅ | `settings.updateEnv` 재사용 |
| FR-044 (다시 고르기) | ✅ | 메뉴 「런타임 → 임베딩 설정 변경…」 |
| FR-050 (노드별 지문) | ✅ | `core/embedding_fingerprint.py` — `embedding_provider/model/dimension/indexed_at` |
| FR-051 (차원 불일치 거부) | ✅ | `check_index_dimensions`. 실측: 4096 모델을 1536 인덱스에 붙이면 거부 |
| FR-052 (없는 것만 자동 채움) | ✅ | 기본 경로가 `text_to_sql_vector IS NULL` 만 대상 |
| FR-053 (지문 불일치는 확인 필요) | ✅ 경계만 | `include_stale=true` 를 명시해야만 덮어쓴다. **확인 화면 자체는 T5** |

### 남은 것

- **FR-001·FR-002·FR-004 (T0)** — 골든 질의 20개, 다섯 모듈 단위 테스트, 데드코드 900줄 삭제는
  **하지 않았다.** 대신 T1~T4 가 바꾼 것에 대한 회귀 테스트 19개를 붙였다
  (`app/tests/test_spec007_embedding_indexing.py`). 111 passed → 130 passed, 회귀 0.
- **FR-054~FR-056 (T5 재색인)** — 미착수. 지금 `stale` 인 데이터소스는 확인 절차가 생기기
  전까지 다시 만들어지지 않는다.
- **FR-010~FR-014, FR-060~FR-066, FR-080~FR-082 (T6~T9)** — 미착수.
- **FR-090~FR-101 (A 트랙)** — 미착수.
- **FR-112 ③ (색인 후 답이 나오는 화면)** — **미충족.** 게이트 통과까지만 확인했다.
  SQL 생성 LLM 키가 이 환경에 없다(401).

### 미결정 항목의 갱신

- **11번 (로컬 서버가 `/v1/embeddings` 를 서빙하는가) → 확인됨(참).** Ollama 로 실왕복.
  AD-5 의 1순위가 성립하므로 400 MB 번들 모델을 앞당길 필요가 없다.
  다만 **차원이 다르다**(qwen3-embedding 4096 vs 인덱스 1536). MRL `dimensions` 파라미터로
  절단 가능함을 확인했고 `EMBEDDING_SEND_DIMENSIONS` 로 열었다.
- **12번 (색인이 `table_profile` LLM 에 묶인 것) → 풀었다.** 임베딩 텍스트를 카탈로그
  메타데이터만으로 결정론적으로 만든다. LLM 프로필은 선택으로 강등. **품질은 미측정.**
- **14번 (레거시 인덱스)** — 컬럼 벡터는 살렸고 테이블 레거시 `t.vector` 도 같은 벡터로 채웠다.
  버리는 결정은 여전히 열려 있다.

### 이 구현이 새로 만든 미결정

- data-fabric 이 `MERGE (t:Table {name, schema})` 로만 병합해 **같은 스키마 이름을 쓰는 두
  데이터소스가 서로의 카탈로그를 덮어쓴다** (검증 중 실제로 재현). T5 가 데이터소스 단위로
  동작하려면 이 경계가 먼저 신뢰할 수 있어야 한다.
- 색인이 `text_to_sql_is_valid` 를 무시하도록 했다 — 거르면 그 데이터소스가 영원히
  `unindexed` 에 머무는 고리가 생기기 때문이다. 유료 제공자에서 이 판단이 옳은지 미검토.

---

## 미결정 항목

확인하지 못했거나, 확인은 했지만 판단을 미룬 것이다. **추측을 사실로 적지 않았다.**

1. **재색인 정책은 권고안이지 결정이 아니다 (AD-5b).** 확인 UI 를 어디에 둘지(부팅 화면 /
   앱 안 설정 / 추출 화면), 대규모(수천 테이블)에서 지문 필터 검색(권고 5 안 B)의 성능,
   데이터소스 단위로 나눠 돌릴지 한 번에 돌릴지 — 셋 다 미결정이다.
   **권고의 근거는 적었으니 반대 결정을 하려면 그 근거를 반박하면 된다.**
2. **에이전트 루프의 지연·비용이 컨트롤러 대비 어떤지 — 미확인.** 지금 컨트롤러는 요청당 LLM
   호출이 5~10회로 예측 가능하다. 에이전트 루프는 턴 수가 열려 있다. 004 실측(질문 응답 20.3초)이
   참고값이지만 text2sql 은 도구 왕복이 더 많다.
3. **`table_profile` 배치를 분석기로 이관할지 — 미결정.** 이관이 개념적으로 맞지만(둘 다
   메타데이터 증강) 콜드스타트 소유권이 옮겨간다. 이 스펙은 후보로만 지목한다.
4. **text2sql 스킬을 어느 저장소에 둘지 — 미결정.** `ontology-studio/skills/` 는 배포·플러그인·
   마켓플레이스 배선이 이미 있지만(005), text2sql 만 쓰는 사람이 스튜디오를 클론해야 한다.
   대안은 `neo4j-text2sql/skills/` 인데 그러면 스캔 루트가 둘이 되고 005 의 "저장소 전체에
   `<name>/SKILL.md` 는 정확히 1개" 테스트(`test_distribution.py:103-120`)와 부딪힌다.
5. **새 분석기의 저장소 위치 — 미결정.** 새 서브모듈인지 `robo-data-analyzer` 안의 새 패키지인지.
   "제자리 수정이 아니라 추가 후 교체" 만 정해졌다.
6. **`robo-skill-analyzer` 의 상위 근거 문서를 못 봤다.** 헌법이 단일 진실로 지목한
   `docs/HANDOFF-순수skill-analyzer-2026-07-02.md` 가 그 저장소에 **없다**. 왜 레거시 분석기를
   버리기로 했는지의 원 근거를 확인하지 못했다.
7. **캐시 프리픽스 경제성이 이 제품에서도 성립하는지 — 미확인.** robo-skill-analyzer 는 노드 318개
   전부 `cache_read>0` 을 실측했지만, 그것은 Claude Code 메인 루프가 오케스트레이터일 때다.
   ontology-studio 의 cliagents 경로는 턴마다 `--append-system-prompt` 로 프롬프트를 넣고
   `--resume` 로 이어간다(`cliagents_backend.py:214-243`). 프리픽스가 같은 방식으로 유지되는지
   **측정하지 않았다.** A3 의 선행 조사 대상이다.
8. **deepagents 경로에서 분석기 의미 루프가 현실적인지 — 미확인.** `execute` 타임아웃 120초,
   출력 3,000자 절단(CR-7). 노드 수백 개 루프를 MCP 도구 왕복으로 도는 비용을 재보지 않았다.
   측정 결과가 나쁘면 **"deepagents 경로는 결정론 단계까지만"** 이 정직한 결론일 수 있다 —
   robo-skill-analyzer 의 *"안 되는 게 발견"* 규율을 그대로 적용한다.
9. **메모리 순변화 — 미측정.** CR-17 근거로 text2sql 컨테이너는 남고 크게 줄지 않을 것으로
   본다. AD-5 로 임베딩 스택이 한 벌이면 최대 +400 MB 를 막는다. **약속하지 않고 SC-016 으로
   재측정한다.**
10. **`infra/docker-compose.robo-stack.yml` 의 text2sql 환경변수가 현재 코드와 불일치한다.**
    `REACT_LLM_PROVIDER`·`OPENAI_LLM_MODEL` 등은 `app/config.py` 에 없는 키다
    (`infra/docker-compose.robo-stack.yml:182-186`). 이 스펙 범위인지 별도 수정인지 미결정.
11. **로컬 OpenAI 호환 서버가 임베딩을 실제로 서빙하는지 — 미확인.** AD-5 의 1순위
    (`llm_endpoint` 제공자)는 Ollama·LM Studio·vLLM 류가 `/v1/embeddings` 를 제공한다는 전제 위에
    있다. **이 환경에서 왕복을 검증하지 않았다.** 이 전제가 틀리면 "메모리 증가 0 으로 로컬
    임베딩" 이 성립하지 않고, 400 MB 번들 모델이 1순위로 올라온다. **T1 의 첫 확인 항목이다.**
12. **`table_profile` LLM 단계를 색인이 흡수해야 하는가 — 미결정.** 지금 색인은 LLM(테이블 프로필
    생성)과 임베딩 **둘 다** 필요하다(`text2sql_table_vectorizer.py:240-256`). 색인을 추출로
    옮기면 이 LLM 의존도 함께 옮겨간다. 프로필 없이 컬럼명·설명만으로 임베딩하면 LLM 없이
    색인할 수 있지만 **품질은 미측정**이다. 미결정 3번(분석기 이관)과 얽혀 있다.
13. **`indexing` 중 질의를 대기시킬지 부분 결과로 답할지 — 미결정.** AD-4 표는 둘 다 열어 두었다.
    수천 테이블 규모에서 어느 쪽이 견딜 만한지 재보지 않았다.
14. **레거시 두 인덱스(`table_vec_index`·`column_vec_index`)를 살릴지 버릴지 — 미결정.**
    `/ask` 경로 전용이고 그 경로는 폐기 대상이다(§무엇이 깨지는가 7·8번). 그러나 컬럼 벡터는
    ReAct 경로도 쓴다(`neo4j.py:432,575`). **컬럼 색인은 살리고 테이블 레거시 인덱스만 버리는
    것**이 자연스러워 보이나, 확인하지 않았다.

---

## Out of Scope

- **두 백엔드의 산출물 품질 비교.** 004 와 같은 이유로 뺀다.
- **`table_profile` 의 분석기 이관** (미결정 3번).
- **robo-data-catalog·robo-data-frontend 변경.** 분석기 스키마·NDJSON 계약을 유지하므로 범위 밖.
- **api-gateway 경유 경로 개선.** constitution 원칙 VI 가 이미 "경유하지 않는다"로 정리했다.
- **레거시 `/ask` 경로 유지.** 정리 대상이다 (§무엇이 깨지는가 7번).
- **분석기의 후처리 단계(군집·health)** — robo-skill-analyzer 도 미착수다.
- **`AskUserQuestion` 구조화 질문.** 004 실측대로 어느 CLI 도 헤드리스에서 발화하지 않는다.
- **데스크톱 첫 실행 선택 화면 변경.** 이미 구현됐고
  (`agent-backend-and-llm-access.md` §구현된 것), 이 스펙은 그 뒤를 채운다.
