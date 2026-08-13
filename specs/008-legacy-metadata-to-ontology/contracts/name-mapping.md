# 계약 — 이름 매핑 (정답지)

**파일**: `ontology-studio/desktop/resources/backend/seed/legacy-mapping.yaml`

난독화본 생성의 입력이자 채점의 기준. **이 파일이 없으면 SC-002~005 를 측정할 수 없다.**

## 형식

```yaml
version: 1
schema:
  source: manufacturing
  target: legacy

tables:
  - source: mfg_product
    target: TB01
    label: 제품 마스터
    columns:
      - { source: product_id,   target: C001, label: 제품 ID,   role: pk }
      - { source: product_name, target: C002, label: 제품명 }
      - { source: unit_price,   target: C004, label: 단가 }

foreign_keys:
  - from: { table: TB06, column: C002 }
    to:   { table: TB01, column: C001 }
    source_from: { table: mfg_daily_sales, column: product_id }
    source_to:   { table: mfg_product,     column: product_id }
```

## 필드

| 필드 | 필수 | 뜻 |
|---|---|---|
| `version` | ✅ | 형식 버전. 생성기와 채점기가 함께 확인한다 |
| `schema.source` / `schema.target` | ✅ | 원본/난독화 스키마명 |
| `tables[].source` / `.target` | ✅ | 원본/난독화 테이블명 |
| `tables[].label` | ✅ | **업무 의미 레이블** — 채점 기준 |
| `tables[].columns[].source` / `.target` | ✅ | 원본/난독화 컬럼명 |
| `tables[].columns[].label` | ✅ | 업무 의미 레이블 |
| `tables[].columns[].role` | | `pk` 등. 난독화에서 유지되는 구조 표시 |
| `foreign_keys[]` | ✅ | **제거된** FK. SC-004 의 분모 |

## 불변식 — 생성기가 검사한다

1. **`target` 은 전역 유일.** 겹치면 두 대상이 하나로 합쳐진다.
2. **원본 DDL 의 모든 테이블·컬럼이 매핑에 있다.** 빠진 이름은 원본 그대로 남아 **의미가 새어
   나간다** — 난독화의 구멍이다.
3. **`label` 은 비어 있을 수 없다.** 비면 그 항목은 채점에서 제외되고, 제외된 수가 보고된다.
4. **`target` 은 의미를 담지 않는다.** `TB01`·`C001` 같은 순번 코드만 허용한다.

## 생성 규칙 — 결정적

- 테이블: DDL 등장 순서대로 `TB01`, `TB02`, …
- 컬럼: **서로 다른 이름** 기준 첫 등장 순서대로 `C001`, `C002`, … (**전역 단일**)

> **컬럼 번호가 전역인 이유.** 치환은 파일 전체를 훑는 한 벌의 사전으로 한다. 프로시저의 컬럼
> 참조는 `p.product_id` 처럼 별칭으로 한정돼 있어, 어느 테이블의 컬럼인지 알려면 별칭을
> 해석해야 한다 — 진짜 SQL 파서의 일이고, 이 생성기는 PostgreSQL DDL 과 Oracle 방언 프로시저를
> 같은 도구로 다뤄야 해서 방언 파서를 쓰지 않는다.
>
> 사전이 전역이면 번호도 전역이어야 한다. 테이블별로 리셋해 놓고 전역 사전으로 치환하면
> **매핑과 생성물이 어긋난다.** 초기 구현이 실제로 이 버그를 냈다 — `created_date` 가 TB01 에서
> `C008` 을 받자 TB02 의 7번째 컬럼도 `C008` 이 되어 `C007` 이 비었다. 생성기의
> `check_mapping()` 이 이제 이 불일치를 막는다.
>
> 같은 이름이 여러 테이블에서 같은 코드가 되는 것은 부작용이 아니라 **현실에 가깝다.** 레거시
> DB 도 같은 개념에 같은 컬럼명을 쓴다. 조인 가능성이라는 *구조* 신호는 남지만, 그것은 이름이
> 주는 *의미* 신호가 아니다.

`target` 은 자동 생성하고 `label` 은 사람이 채운다. 손으로 지은 `target` 은 재현되지 않는다.

## 생성물이 지켜야 하는 것 — 생성기가 검사한다

| 검사 | 왜 |
|---|---|
| **코드와 주석 모두**에 원본 이름이 없다 | 처음엔 코드만 봤다가 프로시저 주석의 `-- 참조 테이블: manufacturing.mfg_product` 를 놓쳤다. 난독화를 무력화하는 가장 쉬운 길이 주석이다 |
| 문자열 리터럴은 손대지 않는다 | 값은 증강의 근거다 (FR-004) |
| 생성물 머리말에 원본 이름을 쓰지 않는다 | 생성물은 인제스천 입력이기도 하다 — 머리말에 원본 스키마명을 적으면 **생성기가 정답을 흘린다** |

## 변경 규칙

**매핑을 바꾸면 생성물을 다시 만들어야 한다.** 매핑과 생성물이 어긋나면 채점이 조용히
틀린 답을 낸다 — 채점기는 매핑을 정답으로 믿기 때문이다.

생성기는 생성물에 **매핑 파일의 해시**를 주석으로 남기고, 채점기는 그 해시가 현재 매핑과
일치하는지 먼저 확인한다.
