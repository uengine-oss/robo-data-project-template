---
name: ontologic-install
description: >
  Ontologic 플랫폼을 처음부터 설치·검증하는 가이드형 자동화 스킬. 사용자가
  "온톨로직 설치", "ontologic install", "/ontologic-install", "플랫폼 설치해줘",
  "설치 다시 해줘", "기본 데이터 적재", "데이터패브릭 구성해줘" 등을 말하면
  트리거. 서브모듈 클론 → 루트 .env 구성 → 인프라(docker) 기동 → 예제 데이터
  적재 → data-fabric 데이터소스 등록/메타데이터 추출 → text2sql 기동 →
  E2E 검증까지 수행한다. 설치 초보자도 이 스킬만으로 완주 가능.
---

# Ontologic 플랫폼 설치 스킬

이 스킬은 Ontologic(서브모듈 기반 마이크로서비스 플랫폼)의 전체 설치를
자동화한다. 각 단계는 **검증 후 다음 단계로** 진행하고, 실패 시 아래
트러블슈팅 절을 참조한다. 전 과정의 상세 배경은 레포 루트 `installation.md`.

## 사전 요구사항 (없으면 먼저 사용자에게 안내)

- Docker Desktop 실행 중 (`docker ps` 동작)
- `uv` 설치됨 (`uv --version`)
- OpenAI API 키 (사용자에게 요청 — .env에 넣을 것)

## 0단계 — 포트 충돌 사전 점검 (중요)

기본 포트가 다른 프로젝트에 점유될 수 있다. 반드시 두 가지 모두 확인:

```bash
lsof -nP -iTCP -sTCP:LISTEN | awk '{print $9}' | grep -oE "[0-9]+$" | sort -un
docker ps --format "{{.Ports}}" | grep -oE "0.0.0.0:[0-9]+" | sort -u
```

필요 포트: Neo4j 7474/7687, PostgreSQL 5432, MySQL 3307, MindsDB 47334/47335,
data-fabric 8004, text2sql 8000. **점유된 포트는 대체 포트로 재매핑**한다:

- docker 서비스 → `infra/docker-compose.override.local.yml` 작성 (ports에
  `!override` 태그 필수 — 없으면 목록이 병합되어 충돌 지속):

```yaml
services:
  neo4j:
    ports: !override ["7475:7474", "7688:7687"]
  postgres:
    ports: !override ["5433:5432"]
```

- 로컬 서비스(text2sql 등) → 루트 `.env`의 `API_PORT`, `TEXT2SQL_BASE_URL` 변경.
- 재매핑했으면 `.env`의 `NEO4J_URI`, `POSTGRES_PORT`도 함께 변경.

## 1단계 — 서브모듈 클론

```bash
git submodule update --init --recursive
```

주의: `.gitmodules`에 stale 엔트리(antlr-code-parser, data-platform-olap)가
있어도 무시된다(정상). api-gateway가 아직 서브모듈이면 일반 폴더로 전환:

```bash
git submodule deinit -f api-gateway && git rm --cached api-gateway
rm -rf .git/modules/api-gateway api-gateway
git clone --depth 1 https://github.com/uengine-oss/robo-api-gateway.git api-gateway
rm -rf api-gateway/.git
```

## 2단계 — 루트 .env 구성

**루트에 .env 하나만** 만든다 (각 서비스가 `load_dotenv()`로 상위 디렉토리를
탐색해 읽음 — 서브모듈 안에 .env를 만들면 루트 설정을 가리므로 금지).

각 서비스의 env example(`data-fabric/env.example`, `agent-scheduler/env.example`,
`infra/.env.example`, `robo-data-analyzer/.env.example`, `data-secure-guard/env.example`,
`neo4j-text2sql/env.test.example`, `process-gpt-bpmn-extractor/*.example`,
`what-if-simulator/api/env_example.txt`)의 **합집합**으로 만들되, 다음을 강제:

- `NEO4J_PASSWORD=12345strategy` (infra docker-compose 기준으로 통일 —
  example마다 값이 다르니 주의)
- `TARGET_DB_*`는 **MindsDB 기준**: TYPE=mysql, HOST=localhost, PORT=47335,
  NAME=mindsdb, USER=mindsdb, PASSWORD 빈값, SCHEMA(S)=mindsdb
- OpenAI 키만 있으면: `LLM_PROVIDER=openai`, `LLM_MODEL=gpt-4.1`,
  `LIGHT_LLM_PROVIDER=openai`, `LIGHT_LLM_MODEL=gpt-4.1-mini`,
  `GOOGLE_API_KEY=` (빈값 — 플레이스홀더 문자열 금지)
- `MINDSDB_REPLACE_LOCALHOST=host.docker.internal`
- `OPENAI_API_KEY=<사용자 제공 키>`

기존 설치의 루트 `.env`가 있으면 그것을 템플릿으로 재사용.

## 3단계 — 인프라 기동

```bash
cd infra
docker compose -f docker-compose.robo-stack.yml \
  [-f docker-compose.override.local.yml] \
  up -d neo4j postgres postgres-init mysql-sample mindsdb
```

- 이전 설치의 동명 컨테이너가 있으면 `docker rm <이름>` 후 재시도.
- MindsDB 최초 기동은 수 분 + 시스템 부하 폭증 가능. 4개 컨테이너가 모두
  `healthy` 될 때까지 대기: `docker ps --filter name=robo-`

## 4단계 — 예제 데이터 적재 확인

```bash
# PostgreSQL manufacturing 예제 (postgres-init가 멱등 적재)
docker exec robo-postgres psql -U postgres -d meetingroom \
  -c "SELECT count(*) FROM manufacturing.mfg_product;"   # 10 기대

# MySQL insurance/sales 예제
docker exec robo-mysql-sample mysql -uroot -prootpass123 -N \
  -e "SELECT COUNT(*) FROM insurance.customers;"          # 5 기대
```

**주의**: MySQL init 스크립트는 볼륨이 비어 있을 때만 자동 실행된다.
기존 볼륨 재사용 시 데이터가 없으면 수동 적재:

```bash
docker exec -i robo-mysql-sample mysql -uroot -prootpass123 sample_db \
  < init-scripts/mysql/01_create_sample_tables.sql
```

## 5단계 — data-fabric 기동 + 데이터소스 등록

```bash
cd data-fabric/backend
uv venv .venv --python 3.12
uv pip install -r requirements.txt --python .venv/bin/python
nohup .venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8004 \
  > /tmp/data-fabric.log 2>&1 &
# /health가 healthy 될 때까지 대기 (부하 시 startup이 느릴 수 있음)
```

데이터소스 3개 등록 (포트는 재매핑 반영):

```bash
curl -X POST http://127.0.0.1:8004/api/datasources -H "Content-Type: application/json" \
  -d '{"name":"manufacturing","engine":"postgres","parameters":{"host":"localhost","port":5433,"user":"postgres","password":"postgres123","database":"meetingroom","schema":"manufacturing"}}'
curl -X POST http://127.0.0.1:8004/api/datasources -H "Content-Type: application/json" \
  -d '{"name":"insurance","engine":"mysql","parameters":{"host":"localhost","port":3307,"user":"root","password":"rootpass123","database":"insurance"}}'
curl -X POST http://127.0.0.1:8004/api/datasources -H "Content-Type: application/json" \
  -d '{"name":"sales","engine":"mysql","parameters":{"host":"localhost","port":3307,"user":"root","password":"rootpass123","database":"sales"}}'
```

메타데이터 추출 (Neo4j 적재 — text2sql RAG의 소스):

```bash
for pair in "manufacturing manufacturing" "insurance insurance" "sales sales"; do
  set -- $pair
  curl -X POST "http://127.0.0.1:8004/api/datasources/$1/extract-metadata-sync" \
    -H "Content-Type: application/json" -d "{\"schemas\":[\"$2\"]}"
done
```

## 6단계 — text2sql 기동

```bash
cd neo4j-text2sql && uv sync
nohup uv run uvicorn app.main:app --host 0.0.0.0 --port 8020 \
  > /tmp/text2sql.log 2>&1 &
```

- 기동 시 sanity check(Neo4j 10s/MindsDB 30s 타임아웃, fail-fast)가 있어
  시스템 부하 중엔 실패할 수 있다 → 부하가 가라앉은 뒤 재시도.
- 첫 기동은 테이블 벡터화(OpenAI 임베딩) 때문에 수 분 소요.
- 로그에서 `Text-to-SQL table vectors ensured` 확인.

## 7단계 — E2E 검증

```bash
cd tests/e2e
uv run --with pytest --with requests --with python-dotenv \
  pytest test_pipeline_api.py -v -m "not slow"   # 빠른 검증 (10개)
# LLM 포함 전체 검증은 -m 옵션 제거
```

자연어 질의 수동 확인 (정식 경로는 `/text2sql/react` — `/ask`는 레거시로
data-fabric 메타데이터와 비호환):

```bash
curl -N -X POST http://127.0.0.1:8020/text2sql/react \
  -H "Content-Type: application/json" \
  -d '{"question":"등록된 제품이 모두 몇 개인지 알려줘","datasource":"manufacturing","schema_filter":["manufacturing"]}'
```

**주의**: 멀티 데이터소스 환경에서는 `schema_filter`를 반드시 지정
(생략 시 다른 데이터소스 테이블이 검색되어 실패).

## 트러블슈팅

| 증상 | 원인/해결 |
|---|---|
| `container name already in use` | 이전 설치 잔재 → `docker rm <이름>` |
| MySQL에 예제 데이터 없음 | 기존 볼륨이라 init 미실행 → 4단계 수동 적재 |
| MindsDB `failed to resolve host.docker.internal` | 부하 중 일시 DNS 오류 → 재시도 |
| text2sql `Startup sanity checks failed` | 부하 스파이크 → 포트 응답 안정화 후 재기동 |
| `/text2sql/ask`가 "No relevant tables found" | 레거시 경로 → `/react` 사용 |
| ReAct가 needs_user_input으로 끝남 | `schema_filter` 누락 → 지정 후 재시도 |
| docker/curl이 전반적으로 타임아웃 | Docker VM 과부하 → `uptime`으로 load 확인 후 대기 |
