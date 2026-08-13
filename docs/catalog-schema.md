# 데이터 카탈로그 그래프 — 실측 스냅샷

[`.specify/memory/constitution.md`](../.specify/memory/constitution.md) 가 규칙을 정하고,
이 문서는 그 규칙의 **근거가 되는 실제 그래프 모양**을 기록한다. 규칙만 보면 왜 그렇게
정했는지 알 수 없어서 분리했다.

그래프는 플랫폼 전체가 공유한다 — data-fabric 이 쓰고 text2sql·domain-layer·ontology-studio
가 읽는다. 그래서 이 문서는 특정 서브모듈이 아니라 ontologic 루트에 있다. 서브모듈에서
이 계약을 참조할 때는 자기 저장소 안에 표를 복사하지 말고 이 문서를 링크한다.

재확인 (ontologic 루트에서):

```bash
uv run --with neo4j python scripts/inspect_catalog.py
uv run --with neo4j python scripts/inspect_catalog.py --datasource <ds> --schema <schema>
```

## 그래프 모양

```
(:DataSource {name, engine, display_name, host, port, database, user, password})
  └─[:HAS_SCHEMA]→ (:Schema {name, db, description})
       └─[:HAS_TABLE]→ (:Table {name, schema, db, datasource, table_type, description})
            └─[:HAS_COLUMN]→ (:Column {fqn, name, table, schema, datasource,
                                       type, nullable, primary_key,
                                       ordinal_position, description})

(:Column)-[:REFERENCES {constraint_name}]→(:Column)      ← 외래키
```

text2sql 이 나중에 `:Table` 에 `text_to_sql_*` 속성(벡터, 임베딩 텍스트, 프로파일,
유효성 플래그)을 덧붙이고, `:Column` 에도 검증 플래그를 붙인다. 카탈로그 구조를 읽는
코드는 이것들을 무시하면 된다.

## 누가 쓰고 누가 읽는가

경로는 ontologic 루트 기준이다.

| | 역할 | 위치 |
|---|---|---|
| **data-fabric** | 유일한 writer. 소스 DB introspect → Neo4j 적재 | `data-fabric/app/services/schema_introspection.py::_store_to_neo4j` |
| **neo4j-text2sql** | reader. 제약·인덱스 생성, SQL 컨텍스트 구성 | `neo4j-text2sql/app/core/neo4j_bootstrap.py`, `.../app/react/tools/build_sql_context_parts/neo4j.py` |
| **domain-layer** | reader. 테이블 구조 → 온톨로지 (결정적) | `domain-layer/app/services/schema_extractor.py` |
| **ontology-studio** | reader. 카탈로그 탐색, 가상 클래스 바인딩, 결정적 생성 | `ontology-studio/backend/src/modules/ontology/` |

## 정체성과 제약

text2sql 이 부팅 시 생성한다 (`neo4j_bootstrap.py:85-93`):

| 제약/인덱스 | 대상 |
|---|---|
| `table_key` NODE KEY | `(t.db, t.schema, t.name)` |
| `column_fqn` UNIQUE | `c.fqn` |
| `table_name_idx` | `t.name` |
| `column_name_idx` | `c.name` |
| `table_vec_index` (vector) | `t.vector` |
| `text_to_sql_table_vec_index` (vector) | `t.text_to_sql_vector` |
| `column_vec_index` (vector) | `c.vector` |

`fqn` 규칙: `f"{schema}.{table}.{column}".lower()` — 소문자다. robo-analyzer 와 일관성을
맞추기 위한 것이라고 writer 코드에 주석이 있다.

### 알려진 위험: Table MERGE 키가 제약보다 좁다

제약은 `(db, schema, name)` 3-튜플인데 writer 의 MERGE 는 `(name, schema)` 2-튜플이다.

```cypher
MERGE (t:Table {name: $table_name, schema: $schema_name})
SET t.table_type = ..., t.db = $database, t.datasource = $datasource_name
```

서로 다른 DB 에 같은 `schema.table` 이 있으면 **같은 노드로 합쳐진다.** 그래서 테이블을
조회할 때는 항상 데이터소스로 함께 필터링해야 한다. `inspect_catalog.py` 가 이 충돌을
검사한다.

## 속성명 divergence (가장 자주 사고 나는 지점)

| 개념 | data-fabric 이 쓰는 이름 | text2sql / domain-layer 가 읽는 이름 |
|---|---|---|
| 컬럼 타입 | `Column.type` | `Column.dtype` |
| 기본키 | `Column.primary_key` | `Column.is_primary_key` |
| 외래키 | `(:Column)-[:REFERENCES]->(:Column)` | `(:Column)-[:FK_TO]->(:Column)`,<br>`(:Table)-[:FK_TO_TABLE]->(:Table)` |
| 데이터소스 | `Table.datasource` | `Table.db`, `COALESCE(t.datasource, t.db)` |

실측 (`itest_pg` / `manufacturing`, 컬럼 158개):

```
type=158  dtype=0            → data-fabric 표기만 채워져 있다
primary_key=158  is_primary_key=0
REFERENCES=12  FK_TO=0  FK_TO_TABLE=0
```

**결과적으로 나타나는 증상**: text2sql 의 `GET /text2sql/meta/tables/{t}/columns` 는
`dtype` 을 읽으므로 data-fabric 이 추출한 메타데이터에 대해 `dtype: "unknown"` 을
반환한다. 값이 없는 게 아니라 **다른 키에 있다.** `installation.md` 의 이슈 #9 / #10 도
같은 뿌리다.

그래서 카탈로그를 읽는 Cypher 는 항상 이렇게 쓴다:

```cypher
coalesce(c.type, c.dtype, '')                      AS sql_type
coalesce(c.primary_key, c.is_primary_key, false)   AS primary_key
WHERE (t.datasource = $ds OR t.db = $ds)
```

외래키는 세 형태를 모두 시도하고 중복을 제거한다. 어느 서비스가 먼저 부팅했는지에 따라
어떤 형태가 존재하는지 달라진다.

## 자격증명

`:DataSource` 노드가 `user` / `password` 를 **평문으로** 보유하고, data-fabric 의
`GET /api/datasources/{name}/connection` 은 비밀번호를 그대로 반환한다. 실측에서 2개
데이터소스 모두 `password` 속성을 갖고 있었다.

Ontology Studio 는 이 값을 읽지도, 노출하지도 않는다. 데이터소스는 이름으로만 지칭하고
접속은 text2sql / MindsDB 가 담당한다. 온톨로지 스키마 응답과 MCP 표면에는
`{datasource, schema, table}` 만 나간다.

## 카탈로그를 지우는 사고

`POST /api/neo4j/clear-all` (`ontology/api.py`) 은 이렇게 한다:

```cypher
MATCH ()-[r]->() DELETE r
MATCH (n) DETACH DELETE n
```

로컬 구성에서 Ontology Studio 가 플랫폼 Neo4j 를 공유하므로 **데이터 패브릭 카탈로그도
함께 사라진다.** 실제로 전체 E2E 스위트를 돌린 뒤 카탈로그가 비어 데이터소스 등록과
메타데이터 추출을 다시 해야 했다.

Docker compose 구성에서는 Ontology Studio 가 자체 Neo4j(`ontology-neo4j`)를 쓰므로 이
문제가 없다. 그래도 테스트는 만든 것만 지우는 편이 안전하다.

## 인제스천 절차

```bash
# 1. 데이터소스 등록 (Neo4j 노드 + MindsDB 데이터베이스)
curl -X POST 'http://127.0.0.1:8004/api/datasources?register_to=both' \
  -H 'Content-Type: application/json' \
  -d '{"name":"<ds>","engine":"postgres","parameters":{...}}'

# 2. 메타데이터 추출 (소스 DB introspect → Neo4j 적재)
curl -X POST 'http://127.0.0.1:8004/api/datasources/<ds>/extract-metadata-sync' \
  -H 'Content-Type: application/json' -d '{"schemas":["<schema>"]}'

# 3. 계약 확인
uv run --with neo4j python scripts/inspect_catalog.py --datasource <ds> --schema <schema>
```

2번을 하지 않으면 데이터소스는 등록만 된 상태이고 스키마·테이블·컬럼이 하나도 없다.
E2E 픽스처가 이런 데이터소스를 건너뛰어야 하는 이유다 — 무조건 첫 번째를 고르면 모든
스펙이 조용히 skip 되어 초록불로 보이지만 아무것도 검증하지 못한다.

카탈로그가 갱신되면 Ontology Studio 의 TTL 캐시(기본 300초)를 비운다:

```bash
curl 'http://127.0.0.1:8000/api/datasources?refresh=true'
```
