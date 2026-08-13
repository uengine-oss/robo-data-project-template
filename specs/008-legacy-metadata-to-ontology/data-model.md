# Phase 1 — 데이터 모델

spec 008 이 다루는 개체와 그 저장 위치. **새 저장소를 만들지 않는다** — 기존 Neo4j 카탈로그와
파일에 얹는다.

---

## 1. 이름 매핑 (정답지) — 파일

난독화본 생성의 **입력**이자 채점의 **기준**. 저장 위치는 예제 데이터 곁이다.

```
ontology-studio/desktop/resources/backend/seed/legacy-mapping.yaml
```

| 필드 | 뜻 | 예 |
|---|---|---|
| `schema.source` | 원본 스키마명 | `manufacturing` |
| `schema.target` | 난독화 스키마명 | `legacy` |
| `tables[].source` | 원본 테이블명 | `mfg_daily_sales` |
| `tables[].target` | 난독화 테이블명 | `TB06` |
| `tables[].label` | **업무 의미 레이블** (채점 기준) | `일별 매출 실적` |
| `tables[].columns[].source` | 원본 컬럼명 | `net_sales_amount` |
| `tables[].columns[].target` | 난독화 컬럼명 | `C005` |
| `tables[].columns[].label` | 업무 의미 레이블 | `순매출액` |
| `foreign_keys[]` | **제거된** FK 목록 (원본 기준) | `TB06.C002 → TB01.C001` |

**설계 판단**

- **`label` 이 없으면 채점이 성립하지 않는다.** 증강은 `net_sales_amount` 라는 문자열을 되살릴
  이유가 없다 — "순매출액"이면 충분하다 (FR-007).
- **제거된 FK 를 기록한다.** SC-004("추론된 관계 중 원래 FK 와 일치하는 비율")의 분모다.
  난독화가 FK 를 지우므로, 지운 것이 무엇인지 남기지 않으면 복원 여부를 판정할 수 없다.
- **매핑은 생성기가 만들고 사람이 `label` 을 채운다.** `target` 이름은 결정적 규칙(테이블 순서
  `TB01`.., 컬럼 순서 `C001`..)으로 자동 생성한다. 손으로 지으면 재현되지 않는다.

**불변식**

- `source` 와 `target` 은 각각 전역 유일. `target` 이 겹치면 두 컬럼이 한 컬럼으로 합쳐진다.
- 원본 DDL 의 모든 테이블·컬럼이 매핑에 있어야 한다. 빠지면 그 이름이 원본 그대로 남아
  **의미가 새어 나간다** — 난독화의 구멍이다. 생성기가 이를 검사한다.

---

## 2. 난독화 예제 데이터 — 생성물

| 산출물 | 위치 | 용도 |
|---|---|---|
| 스키마 DDL | `seed/postgres/05_ddl_legacy.sql` | 샘플 DB 에 `legacy` 스키마 생성 |
| 데이터 DML | `seed/postgres/06_dml_legacy.sql` | 원본 값 그대로, 컬럼 목록만 난독화 |
| 인제스천용 DDL | `tutorial/legacy/ddl/legacy_ddl.sql` | 코드 분석 입력 |
| 프로시저 | `tutorial/legacy/procedures/*.sql` | 의미의 원천 (5종) |

**난독화 규칙**

| 대상 | 처리 | 이유 |
|---|---|---|
| 테이블·컬럼 이름 | 코드로 치환 | FR-001 |
| `FOREIGN KEY` 절 | **제거** | FR-002 |
| 주석 | **제거** | FR-003 |
| 데이터 값 | **그대로** | FR-004 — 증강의 근거 |
| `PRIMARY KEY` | **유지** | 난독화 대상이 아니다. 실제 레거시에도 PK 는 대개 있고, 없으면 데이터가 적재되지 않는다 |
| 프로시저 이름·주석·지역변수 | **그대로** | FR-005 — 의미가 남아 있는 자리 |
| 프로시저의 테이블·컬럼 참조 | 코드로 치환 | 실행 가능해야 한다 |
| 타입·제약(NOT NULL, DEFAULT) | **그대로** | 타입은 채점의 약한 신호로 남는다 |

---

## 3. 증강된 메타데이터 — Neo4j 카탈로그 (기존 노드에 속성 추가)

**새 라벨을 만들지 않는다.** 기존 `:Table` / `:Column` 에 속성을 얹는다.

| 노드 | 속성 | 성격 |
|---|---|---|
| `:Table` | `description` | 기존 — 증강이 채운다 |
| `:Table` | `description_source` | **신규** — 근거 (`procedure:PRC_X` / `sampling` / `ddl`) |
| `:Column` | `description` | 기존 — 증강이 채운다 |
| `:Column` | `description_source` | **신규** — 근거 |
| `:Column` | `value_shape` | **신규** — 값 형태 요약 (R2 의 샘플값 신호용) |

**`value_shape` 가 담는 것** (값이 아니라 **형태**):

- 형(`date` / `code` / `categorical` / `numeric` / `text`)
- 카디널리티 등급, 널 비율 등급
- 수치면 범위 등급, 코드면 패턴(예: `AAAA-999`)

> **값 자체를 넣지 않는다.** 헌법 원칙 V 가 자격증명 비노출을 요구하고, 값은 업무 데이터다.
> 형태만으로 003 FR-006 의 "샘플 값 형태 일치" 신호가 성립한다.

**관계**

| 관계 | 방향 | 성격 |
|---|---|---|
| `REFERENCES` | `:Column` → `:Column` | 기존 — **선언된** FK (난독화본에는 없다) |
| `INFERRED_REFERENCES` | `:Column` → `:Column` | **신규** — 프로시저 조인에서 **추론된** 관계 |

**왜 별도 관계 타입인가** — FR-012 가 "추론된 관계는 선언된 외래키와 구별되어야 한다"를
요구한다. 같은 타입에 속성 플래그로 두면 기존 FK 조회 Cypher 3형태
(`REFERENCES`/`FK_TO`/`FK_TO_TABLE`)가 **추론까지 함께 집어온다.** 헌법이 통계 유래 관계를
`INFLUENCES_*` 로 분리한 것과 같은 판단이다 — *"통계로 발견한 관계는 단언이 아니라 가설이다."*

속성: `source_procedure`, `join_expression`, `confidence`.

---

## 4. 바인딩 판정 — 기존 구조 확장

`entity_matcher` 가 내는 판정 객체에 **근거 필드를 추가**한다 (FR-018).

| 필드 | 기존/신규 | 내용 |
|---|---|---|
| `verdict` | 기존 | `auto` / `needs_review` / `conflict` / `no_match` |
| `score` | 기존 | 총점 |
| `signals.column_overlap` | 기존 | 컬럼명 완전일치 |
| `signals.type_agreement` | 기존 | 타입 합의 |
| `signals.name_similarity` | 기존 | 이름 토큰 자카드 |
| `signals.description_overlap` | **신규** | 증강 설명 토큰 겹침 |
| `signals.value_shape_match` | **신규** | 샘플 값 형태 일치 (003 FR-006) |
| `evidence[]` | **신규** | 사람이 읽는 근거 문장 |
| `prefiltered_out` | **신규** | 후보 축소로 탈락한 수 (R2 — 축소가 정답을 떨어뜨렸는지 추적) |

**가중치는 설정으로 뺀다.** T4 에서 측정하며 조정해야 하고, 원복이 가능해야 한다(계획 T4 의
되돌리기 조건).

---

## 5. 온톨로지 객체 — domain-layer 소유

Q1-B 결정에 따라 **domain-layer 가 쓴다.**

| 라벨/관계 | 표기 | 비고 |
|---|---|---|
| `:OntologyInstance` | PascalCase | 객체화 결과 |
| `:OntologyNode` -`[:HAS_INSTANCE]`→ `:OntologyInstance` | | |
| `:OntologyType` / `:OntologyNode` | | **이중 표기** — 현행/레거시. 원칙 III 의 divergence 로 `docs/catalog-schema.md` 에 기록해야 한다 |
| `[:EFFECTS]` | | 클래스 간 **모든** 관계. 세부 타입은 `relationType` 속성 (오탈자로 보이나 실제 값) |

**추가 속성** (FR-024·FR-025):

| 속성 | 용도 |
|---|---|
| `sourceQuestion` | 원 자연어 질문 |
| `sourceQuery` | 실행된 SQL |
| `instanceId` | 머지 키 — 중복 방지 |

**`instanceId` 가 중복 방지의 전부다** (FR-025). 같은 질의를 다시 객체화해도 같은 키가 나오려면
키가 **행의 내용**에서 결정돼야 한다. 실행 시각이나 순번을 섞으면 매번 새 객체가 쌓인다.

---

## 6. 쓰기 주체 경계 — 헌법 개정 대상

| 그래프 영역 | 쓰는 주체 | 근거 |
|---|---|---|
| 카탈로그 `:Table` / `:Column` / `:DataSource` | **data-fabric** | 헌법 원칙 III — writer 는 하나 |
| 증강 속성 (`description`, `value_shape`, `INFERRED_REFERENCES`) | **분석기(robo-data-analyzer)** | 이 스펙이 새로 정한다 |
| 온톨로지 클래스·바인딩 (`_Entity`, 스키마 그룹) | **ontology-studio** | 헌법 현행 |
| 온톨로지 스키마·객체 (`OntologySchema`, `OntologyType`, `OntologyInstance`) | **domain-layer** | **이 스펙이 도입** — 개정 대상 |
| 분석기 산출 (`:TABLE`, `:FUNCTION` 등 UPPER_SNAKE) | **robo-data-analyzer** | 2026-08-05 wipe 수정으로 범위 확정 |

**경계가 성립하는 이유**: Neo4j 라벨은 대소문자를 구분한다. 분석기의 `:TABLE` 과 카탈로그의
`:Table` 은 다른 라벨이고, domain-layer 의 `:OntologyType` 과 ontology-studio 의 `:_Entity` 도
겹치지 않는다.

**경계가 위험한 지점**: domain-layer 의 `:Table:ObjectType` 은 **카탈로그와 같은 `:Table` 라벨을
쓴다**(`db:'ontology', schema:'ObjectType'` 로 구분). 카탈로그를 읽는 코드가 `db`/`schema` 로
거르지 않으면 ObjectType 을 실제 테이블로 착각한다. 헌법 원칙 II 가 요구하는 데이터소스 필터가
여기서도 방어선이다.

**T8 은 이 표를 헌법에 옮기고, 표가 지켜지는지 검사하는 수단을 함께 만든다.** 문서만 고치면
다음 사람이 같은 자리에서 충돌한다.
