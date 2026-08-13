# Ontologic 플랫폼 설치 가이드 (Installation)

이 문서는 Ontologic 플랫폼을 처음 설치하는 과정을 순서대로 기록한 것입니다.

## 아키텍처 개요

이 레포지토리(`ontologic`)는 **메인 레포**이며, 여러 개의 git 서브모듈로 구성된
**마이크로서비스 아키텍처**입니다. 각 서비스는 독립된 서브모듈 레포로 관리되고,
메인 레포가 이들을 묶어서 전체 플랫폼으로 동작합니다.

## 1. 서브모듈 클론

메인 레포를 클론한 직후에는 서브모듈 디렉토리가 비어 있으므로,
먼저 모든 서브모듈을 초기화/클론해야 합니다.

```bash
git submodule update --init --recursive
```

> **주의**: `.gitmodules`에는 `antlr-code-parser`, `data-platform-olap` 엔트리가
> 남아 있지만 실제 git 인덱스에는 서브모듈로 등록되어 있지 않습니다(stale 엔트리).
> `data-platform-olap`은 이미 메인 레포에 일반 폴더로 포함되어 있고,
> `antlr-code-parser`는 클론되지 않습니다. 위 명령이 이 둘을 건너뛰는 것은 정상입니다.

서브모듈 목록 (`.gitmodules` 기준):

| 경로 | 레포 |
|---|---|
| agent-scheduler | uengine-oss/robo-data-agent-scheduler |
| antlr-code-parser | uengine-oss/antlr-code-parser |
| api-gateway | uengine-oss/robo-api-gateway |
| data-fabric | jinyoung/robo-data-fabric |
| data-platform-olap | uengine-oss/data-platform-olap |
| data-secure-guard | uengine-oss/robo-data-security-guard |
| domain-layer | uengine-oss/robo-insight-domain-layer |
| infra | uengine-oss/robo-data-platform |
| neo4j-text2sql | uengine-oss/neo4j-text2sql |
| node-local-agent-scheduler | uengine-oss/robo-node-local-agent-scheduler |
| process-gpt-bpmn-extractor | uengine-oss/process-gpt-bpmn-extractor |
| robo-data-analyzer | uengine-oss/robo-data-analyzer (branch: refactor) |
| robo-data-catalog | uengine-oss/robo-data-catalog |
| robo-data-frontend | uengine-oss/robo-data-frontend |
| robo-data-glossary | uengine-oss/robo-data-glossary |

## 2. api-gateway 서브모듈 → 일반 폴더로 전환

`api-gateway`는 현재 서브모듈로 되어 있지만, **서브모듈을 받은 뒤 일반 폴더로
전환**합니다. (향후 메인 레포 자체가 api-gateway 코드를 직접 포함하는 구조로
바뀔 예정이므로, 다음 설치부터는 이 단계가 필요 없어질 것입니다.)

```bash
# 1) 서브모듈 등록 해제 (이 명령은 api-gateway 작업 디렉토리를 비웁니다)
git submodule deinit -f api-gateway
git rm --cached api-gateway
rm -rf .git/modules/api-gateway
git config -f .gitmodules --remove-section submodule.api-gateway

# 2) deinit이 폴더를 비우므로, 레포를 직접 클론한 뒤 .git을 제거해 일반 폴더화
rm -rf api-gateway
git clone --depth 1 https://github.com/uengine-oss/robo-api-gateway.git api-gateway
rm -rf api-gateway/.git
```

이 시점에서 git 상태는 `api-gateway` 서브모듈 삭제(`D api-gateway`) +
`.gitmodules` 수정 상태가 되며, `api-gateway/` 폴더 자체는 untracked 일반 폴더가
됩니다. (메인 레포에 직접 커밋할지는 별도 결정 사항)

## 3. 루트 `.env` 파일 생성

각 서비스는 `.env` 파일이 필요하지만, **메인 루트에 `.env` 파일 하나만 있으면**
각 서비스가 루트의 `.env`를 읽어들이도록 되어 있습니다.

루트 `.env`는 각 서비스 내부에 들어 있는 env example 파일들의
**합집합(union)** 으로 만듭니다. 수집된 example 파일:

| 서비스 | 파일 |
|---|---|
| data-fabric | `env.example` |
| agent-scheduler | `env.example` |
| infra | `.env.example` |
| robo-data-analyzer | `.env.example` (ROBO_* 네임스페이스) |
| data-secure-guard | `env.example` |
| neo4j-text2sql | `env.test.example` |
| process-gpt-bpmn-extractor | `agent.env.example`, `api.env copy.example` |
| what-if-simulator | `api/env_example.txt` (WHATIF_* 네임스페이스) |

`api-gateway`, `domain-layer`, `robo-data-catalog`, `robo-data-glossary`,
`robo-data-frontend`, `data-platform-olap`, `node-local-agent-scheduler`에는
env example 파일이 없습니다.

### 병합 시 주의사항 (키 충돌)

1. **`NEO4J_PASSWORD`** — 서비스마다 example 값이 다름
   (`12345strategy` / `12345analyzer` / `1234567bpmn`).
   실제 인프라 기준값은 `infra/docker-compose.robo-stack.yml`의
   `NEO4J_AUTH: neo4j/12345strategy` 이므로 **`12345strategy`로 통일**했습니다.
   (`ROBO_NEO4J_PASSWORD`, `WHATIF_NEO4J_PASSWORD`도 동일하게 통일)
2. **`TARGET_DB_*`** — agent-scheduler는 postgres(`localhost:5432/rwis`)를,
   neo4j-text2sql(테스트)은 mysql(`localhost:47335/mindsdb`)을 같은 키로 사용.
   기본값은 agent-scheduler 기준(postgres)으로 넣고, text2sql용 대안은
   주석으로 남겨두었습니다.
3. API 키(`OPENAI_API_KEY`, `GOOGLE_API_KEY`)와 Supabase 시크릿
   (`SUPABASE_ANON_KEY`, `SERVICE_ROLE_KEY`, `USER_JWT`)은 플레이스홀더 상태이므로
   **실제 값으로 채워야 합니다.**

루트 `.env`는 `.gitignore`에 의해 커밋에서 제외됩니다.

### 서비스가 루트 `.env`를 읽는 원리

각 Python 서비스는 `load_dotenv()`(python-dotenv)를 인자 없이 호출하는데,
이 함수는 호출한 파일의 디렉토리부터 **상위 디렉토리로 올라가며** `.env`를
탐색합니다. 서브모듈 내부에 `.env`가 없으면 메인 루트의 `.env`를 찾아 읽게
됩니다. 따라서 **서브모듈 안에 별도의 `.env`를 만들지 않는 것**이 중요합니다
(만들면 루트 설정을 가려버림).

## 4. 인프라 기동 (Neo4j / PostgreSQL / MySQL / MindsDB)

```bash
cd infra
docker compose -f docker-compose.robo-stack.yml -f docker-compose.override.local.yml \
  up -d neo4j postgres postgres-init mysql-sample mindsdb
```

앱 서비스(text2sql, data-fabric 등)는 컨테이너 대신 **서브모듈 소스에서 직접
실행**합니다 (루트 `.env` 하나로 설정을 통일하기 위함).

### 이슈 #1 — 호스트 포트 충돌

이 머신에서 다른 프로젝트(process-gpt)가 다음 포트를 이미 점유:

| 포트 | 점유 프로세스 | 해결 |
|---|---|---|
| 5432 | process-gpt-litellm-db | postgres를 **5433**으로 재매핑 |
| 7474/7687 | process-gpt neo4j | neo4j를 **7475/7688**로 재매핑 |
| 8000 | ontology-studio-backend (로컬 프로세스) | text2sql 포트 변경 필요 |
| 8010 | 다른 docker 컨테이너 포트포워딩 | text2sql을 **8020**으로 실행 |

재매핑은 `infra/docker-compose.override.local.yml`(untracked)로 처리하고,
루트 `.env`의 `NEO4J_URI`(bolt://localhost:7688), `POSTGRES_PORT`(5433),
`API_PORT`/`TEXT2SQL_BASE_URL`(8020)을 함께 변경했습니다.

> 포트 선정 시 `lsof -nP -iTCP -sTCP:LISTEN`과
> `docker ps --format "{{.Ports}}"`를 함께 확인할 것 — docker 포트포워딩은
> 프로세스명이 `com.docke`로만 보여서 놓치기 쉽습니다.

> compose override에서 포트 매핑을 교체하려면 `ports:` 목록에 `!override`
> 태그가 필요합니다 (없으면 목록이 병합되어 충돌 지속).

### 이슈 #2 — 이전 설치의 잔재 컨테이너 이름 충돌

`robo-neo4j` 등 이름이 같은 (수개월 전 중단된) 컨테이너가 남아 있어
`Conflict. The container name "/robo-neo4j" is already in use` 에러 발생.
→ 중단된 잔재 컨테이너 제거 후 재기동:

```bash
docker rm robo-neo4j robo-postgres robo-mysql-sample robo-mindsdb robo-postgres-init
```

기존 데이터 볼륨(`infra_postgres_data` 등)은 유지한 채 진행 (아래 이슈 #3 참조).

### 이슈 #3 — 기존 볼륨 때문에 MySQL init 스크립트 미실행

`docker-entrypoint-initdb.d`의 init SQL은 **볼륨이 비어 있을 때(최초 1회)만**
실행됩니다. 기존 볼륨을 재사용하면 새 init 스크립트가 실행되지 않으므로 수동
적재가 필요합니다:

```bash
docker exec -i robo-mysql-sample mysql -uroot -prootpass123 sample_db \
  < init-scripts/mysql/01_create_sample_tables.sql
```

반면 PostgreSQL 쪽은 `postgres-init` 컨테이너(python)가 별도로 돌면서
`manufacturing.mfg_product` 존재 여부를 확인하고 멱등하게 적재하므로 기존
볼륨과 무관하게 정상 동작합니다.

### 이슈 #4 — LLM provider 기본값이 google(Gemini)

`neo4j-text2sql`의 기본 `LLM_PROVIDER`는 `google`인데 OpenAI 키만 제공되므로
루트 `.env`에서 `LLM_PROVIDER=openai`, `LLM_MODEL=gpt-4.1`,
`LIGHT_LLM_PROVIDER=openai`, `LIGHT_LLM_MODEL=gpt-4.1-mini`로 변경.

### 이슈 #5 — `TARGET_DB_*`의 올바른 값은 MindsDB

infra docker-compose를 보면 text2sql과 agent-scheduler 모두 타겟 DB로
**MindsDB(MySQL 프로토콜, 47335)**를 사용합니다. 실제 postgres/mysql 데이터는
data-fabric을 통해 MindsDB에 데이터소스로 등록되고, 질의는 MindsDB를 경유
합니다. 루트 `.env`의 `TARGET_DB_*`를 MindsDB 기준으로 수정했습니다.

### 적재된 기본 데이터

**PostgreSQL (localhost:5433, postgres/postgres123, DB=meetingroom)**
- `manufacturing` 스키마: 13개 테이블 (제조 예제 — mfg_product 등)
- (이전 설치 잔재: RWIS, steel_safety, ins, hwaseong 스키마도 존재)

**MySQL (localhost:3307, root/rootpass123)**
- `insurance` DB: customers(5), products(5), contracts(5), claims(2) (보험 예제)
- `sales` DB: categories(8), products(6), customers(3), orders(3), order_items(4) (판매 예제)
- 주의: `sampleuser`는 `sample_db`에만 권한이 있음 — insurance/sales 등록 시
  root 계정 또는 권한 부여 필요

## 5. 로컬 서비스 실행 준비 (Python)

앱 서비스는 서브모듈 소스에서 직접 실행합니다. `uv`로 의존성 설치:

```bash
# data-fabric (requirements.txt 기반)
cd data-fabric/backend
uv venv .venv --python 3.12
uv pip install -r requirements.txt --python .venv/bin/python

# neo4j-text2sql (uv 프로젝트)
cd ../../neo4j-text2sql
uv sync
```

## 6. Data Fabric 구성 (데이터소스 등록 + 메타데이터 추출)

### 기동

```bash
cd data-fabric/backend
nohup .venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8004 > /tmp/data-fabric.log 2>&1 &
curl http://127.0.0.1:8004/health   # {"status":"healthy"}
```

### 데이터소스 등록

등록하면 ① Neo4j에 DataSource 노드 생성, ② MindsDB에 database 생성이 동시에
수행됩니다. data-fabric이 `localhost`를 `MINDSDB_REPLACE_LOCALHOST`
(host.docker.internal)로 자동 치환하므로 MindsDB 컨테이너가 호스트 매핑 포트로
접근할 수 있습니다.

```bash
# PostgreSQL manufacturing 예제
curl -X POST http://127.0.0.1:8004/api/datasources -H "Content-Type: application/json" \
  -d '{"name":"manufacturing","engine":"postgres","parameters":{"host":"localhost","port":5433,"user":"postgres","password":"postgres123","database":"meetingroom","schema":"manufacturing"}}'

# MySQL insurance / sales 예제
curl -X POST http://127.0.0.1:8004/api/datasources -H "Content-Type: application/json" \
  -d '{"name":"insurance","engine":"mysql","parameters":{"host":"localhost","port":3307,"user":"root","password":"rootpass123","database":"insurance"}}'
curl -X POST http://127.0.0.1:8004/api/datasources -H "Content-Type: application/json" \
  -d '{"name":"sales","engine":"mysql","parameters":{"host":"localhost","port":3307,"user":"root","password":"rootpass123","database":"sales"}}'
```

### 스키마 메타데이터 추출 (Neo4j 적재 — text2sql의 RAG 소스)

```bash
curl -X POST http://127.0.0.1:8004/api/datasources/manufacturing/extract-metadata-sync \
  -H "Content-Type: application/json" -d '{"schemas":["manufacturing"]}'
# → {"success":true,"schemas":1,"tables":13}
curl -X POST http://127.0.0.1:8004/api/datasources/insurance/extract-metadata-sync \
  -H "Content-Type: application/json" -d '{"schemas":["insurance"]}'
# → {"success":true,"schemas":1,"tables":4}
curl -X POST http://127.0.0.1:8004/api/datasources/sales/extract-metadata-sync \
  -H "Content-Type: application/json" -d '{"schemas":["sales"]}'
# → {"success":true,"schemas":1,"tables":5}
```

## 7. Text2SQL 실행 및 스모크 테스트

### 기동

```bash
cd neo4j-text2sql
nohup uv run uvicorn app.main:app --host 0.0.0.0 --port 8020 > /tmp/text2sql.log 2>&1 &
# 기동 시 자동 수행: Neo4j 인덱스 부트스트랩 → 테이블 text_to_sql 벡터화(OpenAI 임베딩)
#                  → enum 캐시/유효성 부트스트랩
curl http://127.0.0.1:8020/health
```

기동 완료 로그 확인 포인트:
- `Connected to Neo4j at bolt://localhost:7688`
- `Target database: mysql://localhost:47335/mindsdb`
- `Using LLM: openai:gpt-4.1`
- `Text-to-SQL table vectors ensured`

### 데이터소스 인식 확인

```bash
curl http://127.0.0.1:8020/text2sql/meta/datasources
# → ["insurance","manufacturing","sales"]  (+ 이전 설치 잔재가 있으면 함께 표시)
```

### 자연어 질의 (ReAct 에이전트 — 정식 경로)

`POST /text2sql/react`는 NDJSON 스트리밍으로 진행 과정을 흘려보내며,
파이프라인은 임베딩 → 스키마 검색(RAG) → SQL 후보 생성 → 검증(validate_sql)
→ MindsDB 실행 순으로 진행됩니다.

```bash
curl -N -X POST http://127.0.0.1:8020/text2sql/react \
  -H "Content-Type: application/json" \
  -d '{"question":"등록된 제품이 모두 몇 개인지 알려줘","datasource":"manufacturing"}'
```

첫 질의는 컨텍스트 구축(build_sql_context) 때문에 수 분이 걸릴 수 있고,
이후에는 캐시로 빨라집니다. (curl 사용 시 `-m` 타임아웃을 넉넉히 줄 것)

### 이슈 #10 — 멀티 데이터소스 환경에서는 `schema_filter` 지정 필요

ReAct의 스키마 검색(RAG)은 요청의 `datasource`로 검색 범위를 좁히지 않고
Neo4j 전체 스키마를 대상으로 벡터 검색합니다. 여러 데이터소스가 등록된 상태
에서 `datasource`만 지정하면 다른 데이터소스의 테이블이 검색되어 SQL 후보가
전부 실패(→ `needs_user_input`)할 수 있습니다.
→ 요청에 `"schema_filter": ["<스키마명>"]`을 함께 지정할 것.
(datasource가 자동으로 검색 필터로 이어지지 않는 점은 개선 후보)

**스모크 테스트 결과 (manufacturing/PostgreSQL):**

- 질문: "등록된 제품이 모두 몇 개인지 알려줘"
- 생성 SQL: `SELECT COUNT(DISTINCT t."product_id") AS "product_count"
  FROM "manufacturing"."mfg_product" t`
- 실행 결과: `product_count = 10` (psql 직접 조회값과 일치 ✓,
  MindsDB 경유 실행 48ms)

**스모크 테스트 결과 (insurance/MySQL, schema_filter 지정):**

```bash
curl -N -X POST http://127.0.0.1:8020/text2sql/react \
  -H "Content-Type: application/json" \
  -d '{"question":"보험 고객이 모두 몇 명인지 알려줘","datasource":"insurance","schema_filter":["insurance"]}'
```

- 생성 SQL: `SELECT COUNT(DISTINCT c.customer_id) AS customer_count
  FROM insurance.contracts c`
- 실행 결과: `customer_count = 4` (계약 보유 고객 기준; customers 테이블 전체는
  5명 — LLM이 "보험 고객"을 계약 보유자로 해석한 의미론적 선택)

### 이슈 #16 — 게이트웨이 30초 응답 타임아웃으로 온톨로지 데이터 탭 실패

온톨로지 노드 데이터 조회(`/ontology/ontology-nodes/{id}/data`)는 MindsDB 뷰
질의를 수반해 10~25초(부하 시 그 이상)가 걸릴 수 있는데, Spring Cloud
Gateway 기본 응답 타임아웃(30초)에 걸리면 UI 데이터 탭이 "no-data"로 표시됨.
→ 게이트웨이 기동 시 응답 타임아웃 연장:

```bash
SPRING_CLOUD_GATEWAY_HTTPCLIENT_RESPONSE_TIMEOUT=120s \
ROBO_TEXT2SQL_URL=http://127.0.0.1:8020 sh ./mvnw spring-boot:run
```

추가 주의: 온톨로지 저장(`POST /ontology/schema`) 시 노드의
`dataSourceSchema.columns`가 유실되어 "0개 컬럼"이 되는 경우가 있음 →
`POST /ontology/confirm-datasource`로 재연결하면 복구됨.

### 이슈 #15 — 코드 인제스천 후 Neo4j의 DataSource 노드 유실 가능

코드 인제스천(robo-data-analyzer 파이프라인) 실행 후 Neo4j의 `:DataSource`
노드가 사라져 데이터소스 목록(`GET /api/datasources`)이 빈 배열이 되는 현상이
관찰됨 (MindsDB 쪽 등록은 유지됨). 프론트 데이터소스 화면이 비어 보이면:

```bash
# Neo4j에만 재등록 (MindsDB는 건드리지 않음)
curl -X POST "http://127.0.0.1:8004/api/datasources?register_to=neo4j" \
  -H "Content-Type: application/json" \
  -d '{"name":"manufacturing","engine":"postgres","parameters":{...}}'
```

원인(인제스천의 그래프 정리 로직이 DataSource 노드까지 삭제하는지)은
분석 필요 — 개선 후보.

### 이슈 #14 — 온톨로지가 domain-layer 메모리에만 존재 (영속화 안 됨)

문서/스키마에서 생성한 온톨로지(활성 스키마)는 **domain-layer 프로세스 메모리에만**
있고 Neo4j에는 저장되지 않은 상태로 남을 수 있습니다 (`GET /ontology/schemas`가
빈 배열). 이 상태에서는:
- 노드 데이터 API(`/ontology/ontology-nodes/{id}/data`)가 404
- 원인 분석(인접 네트워크를 Neo4j에서 조회)이 빈 네트워크로 실패
- BPMN 노드 단위 저장(`PATCH /ontology/nodes/{id}/bpmn-xml`)이 404
- **domain-layer 재시작 시 온톨로지 유실**

→ 온톨로지 생성 후 상단 **저장** 버튼으로 반드시 Neo4j에 영속화할 것.
(저장은 전체 스키마 재작성(DETACH DELETE 후 재생성) 방식이므로 다른 작업과
동시에 수행하지 말 것.) 관련: Neo4j가 2개(7687 process-gpt / 7688 ontologic)
공존하는 환경에서는 domain-layer가 루트 .env의 7688을 바라보는지도 확인.

### 이슈 #13 — ObjectType 마법사 관련 버그/제약 (개선 후보)

1. **직접 SQL 경로에서 한글 View 이름 생성 실패**: 마법사의 "SELECT 직접 입력"
   경로에는 View 이름 입력란이 없어 백엔드가 ObjectType 이름으로
   `mv_제조_일일_판매_현황` 같은 한글 뷰명을 만들려다 MindsDB
   `Illegal character` 오류로 실패. (프론트 CreateObjectTypeDialog.vue가
   LLM 경로에서만 viewName을 전송, domain-layer ontology.py:2209 부근)
   → 우회: viewName을 영문으로 지정하는 API 호출 또는 자연어 경로 사용.
2. **스트림 error 이벤트가 파싱 오류로 은폐됨**: 실제 원인("Lost connection")이
   "결과 컬럼을 파싱할 수 없습니다"로 표시됨 (CreateObjectTypeDialog.vue:289).
3. **MindsDB 조인 미리보기는 LIMIT 필수**: LIMIT 없는 조인 쿼리는 부하 시
   `Lost connection to MySQL server`. View 생성 시 후행 LIMIT은 자동 제거되므로
   미리보기 SQL에 `LIMIT 100`을 붙이는 것이 안전.
4. **2-part 테이블 표기는 데이터소스 자동 감지 안 됨**: `스키마.테이블` 대신
   `데이터소스.스키마.테이블` 3-part 표기 권장.
5. **제조3(기존 저장 온톨로지)의 노드 연결 경로가 깨져 있었음**:
   `postgres.manufacturing.*` 경로가 MindsDB에서 조회 불가(500) — ObjectType
   재연결로 정상화 가능.

### 이슈 #12 — ANTLR 파서: QEMU 이미지 대신 네이티브 실행 권장

인제스천(코드 분석)에는 ANTLR 파서(8081)가 필요한데, `antlr-code-parser`는
`.gitmodules`에 stale 엔트리만 있고 서브모듈로 클론되지 않습니다.
ghcr 이미지(`robo-antlr-parser`)는 amd64 전용이라 Apple Silicon에서 QEMU
에뮬레이션으로 돌며 **시스템 전체를 마비시킬 정도의 CPU를 소모**했습니다.
→ 소스를 직접 클론해 네이티브로 실행하는 것을 권장:

```bash
git clone --depth 1 https://github.com/uengine-oss/antlr-code-parser.git
cd antlr-code-parser
sh ./mvnw spring-boot:run -q -Dspring-boot.run.arguments=--server.port=8081 &
# 기본 포트가 8080(점유됨)이므로 8081 명시 필요
```

### 이슈 #11 — api-gateway의 text2sql 라우트 포트 하드코딩

`api-gateway/src/main/resources/application.yml`의 text2sql 라우트 2곳이
`http://127.0.0.1:8000` 하드코딩이라 이 머신(8000 점유, text2sql은 8020)에서
라우팅이 깨짐 → `${ROBO_TEXT2SQL_URL:http://127.0.0.1:8000}` 패턴으로 수정
(기존 `ROBO_ANTLR_URL` 등과 동일한 방식). 게이트웨이 기동 시:

```bash
cd api-gateway && ROBO_TEXT2SQL_URL=http://127.0.0.1:8020 ./mvnw spring-boot:run
```

## 7-b. 온톨로지 구축 전략 (선택) — domain-layer 통계 서비스

[003 입력 조합별 온톨로지 구축 전략](specs/003-ontology-build-strategies/spec.md) 의
**전략 2(인과 발견)만** domain-layer 를 요구한다. 전략 1(문서 역바인딩)과 전략 3(카탈로그
구조 매핑)은 이 서비스 없이 동작하고, 없으면 전략 선택 화면에 "통계 서비스에 연결할 수
없습니다" 로 표시되며 나머지 전략은 영향받지 않는다.

```bash
cd domain-layer
nohup uv run uvicorn app.main:app --host 127.0.0.1 --port 8001 > /tmp/domain-layer.log 2>&1 &
curl -s http://127.0.0.1:8001/health   # {"status":"healthy",...,"neo4j":"connected"}
```

루트 `.env` (origin 형과 접두사 포함형 `/whatif` 를 모두 받는다):

```bash
DOMAIN_LAYER_URL=http://127.0.0.1:8001
DOMAIN_LAYER_TIMEOUT_SECONDS=120
```

**게이트웨이(9000)를 경유하지 않는다** — 30초 응답 타임아웃이 분석을 끊는다 (이슈 #16 과 동일).

### 이슈 #17 — ontology-studio 백엔드가 sandbox 컨테이너 없이는 기동 실패

`SANDBOX_BACKEND` 기본값이 `docker` 여서, `deepagents-sandbox` 컨테이너가 없으면
기동 시점에 sanity check 로 죽는다:

```
Sandbox container 'deepagents-sandbox'가 실행 중이 아닙니다.
ERROR: Application startup failed. Exiting.
```

→ 컨테이너를 띄우거나, 에이전트 샌드박스가 필요 없는 검증(HTTP API·전략 경로)만 할 때는
로컬 백엔드로 우회한다:

```bash
cd ontology-studio
SANDBOX_BACKEND=local uv run uvicorn backend.src.host.main:app --host 127.0.0.1 --port 8010
```

이 머신은 8000 이 점유되어 있어 **8010** 을 쓴다.

## 8. 설치 완료 상태 요약

| 구성요소 | 위치/포트 | 실행 방식 |
|---|---|---|
| Neo4j | localhost:7475(HTTP)/7688(Bolt), neo4j/12345strategy | docker (robo-neo4j) |
| PostgreSQL | localhost:5433, postgres/postgres123, DB meetingroom | docker (robo-postgres) |
| MySQL 샘플 | localhost:3307, root/rootpass123 | docker (robo-mysql-sample) |
| MindsDB | localhost:47334(HTTP)/47335(MySQL) | docker (robo-mindsdb) |
| data-fabric | localhost:8004 | 로컬 소스 (`data-fabric/backend`, .venv) |
| text2sql | localhost:8020 | 로컬 소스 (`neo4j-text2sql`, uv) |
| domain-layer | localhost:8001 | 로컬 소스 (`domain-layer`, uv) — **전략 2 인과 발견에만 필요** |
| ontology-studio | localhost:8010 | 로컬 소스 (`ontology-studio`, uv) — sandbox 없으면 `SANDBOX_BACKEND=local` |

등록된 데이터소스(MindsDB + Neo4j): `manufacturing`(postgres),
`insurance`(mysql), `sales`(mysql)

### 설치 검증 (E2E 회귀 테스트)

```bash
cd tests/e2e
uv run --with pytest --with requests --with python-dotenv \
  pytest test_pipeline_api.py -v -m "not slow"
```

상세: [tests/e2e/README.md](tests/e2e/README.md).
설치 자동화는 agent skill `ontologic-install`(.claude/skills/)로도 수행 가능.

### 서비스 재기동 방법

```bash
# 인프라
cd infra && docker compose -f docker-compose.robo-stack.yml \
  -f docker-compose.override.local.yml up -d neo4j postgres mysql-sample mindsdb

# data-fabric
cd data-fabric/backend && nohup .venv/bin/uvicorn app.main:app \
  --host 0.0.0.0 --port 8004 > /tmp/data-fabric.log 2>&1 &

# text2sql (인프라가 안정된 후에 기동할 것 — 이슈 #8 참조)
cd neo4j-text2sql && nohup uv run uvicorn app.main:app \
  --host 0.0.0.0 --port 8020 > /tmp/text2sql.log 2>&1 &
```

### 이슈 #6 — 시스템 과부하로 인한 일시적 실패

MindsDB 최초 기동 시 Docker VM CPU가 폭증(load average 275)하면서
`docker exec`/`curl` 타임아웃과 MindsDB의 postgres 연결에서
`failed to resolve host 'host.docker.internal': Temporary failure in name
resolution` 오류가 발생했습니다. **일시적 현상**으로, 기동 완료 후 재시도하면
정상 동작합니다. (동일 머신에서 다른 무거운 스택이 돌고 있으면 MindsDB 최초
기동에 수 분이 걸릴 수 있음)

### 이슈 #8 — text2sql startup sanity check가 부하 스파이크에 취약

`neo4j-text2sql`은 기동 시 Neo4j(10초)·타겟 DB(30초) 연결 sanity check를
수행하고 실패하면 즉시 종료합니다(fail-fast). 이 머신처럼 Docker VM이 주기적
으로 CPU 폭주하는 환경에서는 일시적 타임아웃으로 기동이 실패할 수 있습니다.
→ bolt 포트(7688)가 3초 내 연결되는 안정 상태를 확인한 뒤 기동하는 래퍼
스크립트로 우회. (타임아웃 값은 소스에 하드코딩되어 있어 env로 조정 불가 —
개선 후보)

### 이슈 #9 — `/text2sql/ask`(레거시)는 data-fabric 추출 메타데이터와 호환 안 됨

`/text2sql/ask`는 `Table.vector` 속성 기반의 레거시 벡터 인덱스
(`table_vec_index`)를 조회하는데, 이 속성은 schema-edit(설명 수정) 경로로만
채워집니다. data-fabric 추출 + 스타트업 벡터화는 `Table.text_to_sql_vector`
(인덱스 `text_to_sql_table_vec_index`)를 채우므로 `/ask`는
"No relevant tables found"를 반환합니다. 또한 `/ask`의 datasource 필터는
`Table.db`(물리 DB명, 예: meetingroom)를 키로 비교해 MindsDB 데이터소스명
(manufacturing)과 불일치합니다.

→ **정식 질의 경로는 `/text2sql/react`** (ReAct 에이전트, SSE 스트리밍)이며,
이 경로가 `text_to_sql_vector` 인덱스를 사용합니다.

### 이슈 #7 — MindsDB 경유 MySQL 조회 시 한글 인코딩 깨짐

`SELECT * FROM insurance.customers`를 MindsDB HTTP API로 실행하면 한글이
`ê¹€`처럼 깨져 보입니다(mojibake). MySQL 핸들러의 기본 charset 문제로 추정.
설치 진행에는 지장이 없으나 한글 데이터 표시 품질 이슈로 기록해둡니다.
