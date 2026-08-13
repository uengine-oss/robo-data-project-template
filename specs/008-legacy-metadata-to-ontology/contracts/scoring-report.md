# 계약 — 채점 하네스 출력

**스크립트**: `scripts/score_scenario.py` · **출력**: JSON (stdout) + 사람이 읽는 요약 (stderr)

SC-001~005 를 **사람 눈이 아니라 스크립트로** 판정한다. 증강이 LLM 의존이라 결과가 결정적이지
않으므로, 반복 실행의 분포로 보고한다.

---

## 실행

```bash
uv run --with neo4j --with httpx --with pyyaml python scripts/score_scenario.py \
  --mapping ontology-studio/desktop/resources/backend/seed/legacy-mapping.yaml \
  --datasource <이름> --schema legacy \
  --phase before|after \
  --runs 3
```

`--phase before` 는 증강 전 기준선(SC-001), `after` 는 증강 후(SC-002~005).

---

## 출력

```json
{
  "mapping_hash": "sha256:...",
  "phase": "after",
  "runs": 3,
  "sc_001_auto_bindings_before": 0,
  "sc_002_correct_bindings": { "n": 8, "of": 10, "per_run": [8, 7, 8] },
  "sc_003_description_fill": {
    "tables": { "filled": 13, "of": 13 },
    "columns": { "filled": 141, "of": 158 },
    "without_evidence": 0
  },
  "sc_004_inferred_relations": { "found": 9, "matching_removed_fk": 7, "of_removed_fk": 12 },
  "sc_005_wrong_bindings": 0,
  "excluded": { "no_label": 0, "prefiltered_out": 2 },
  "verdict": "PASS|FAIL",
  "failures": []
}
```

---

## 판정 규칙

| 기준 | 통과 조건 | 성격 |
|---|---|---|
| **SC-001** | `sc_001_auto_bindings_before == 0` | **엄격.** 현재 채점식상 산술적으로 보장되므로, 0이 아니면 **난독화가 불완전한 것** |
| **SC-002** | 목표 개념의 정답 바인딩 비율이 기준선보다 **유의하게** 높다 | 절대 임계는 T3 측정 후 정한다 |
| **SC-003** | `without_evidence == 0` | **엄격.** 근거 없는 설명은 추측이다 (FR-014) |
| **SC-004** | `found > 0` 이고 `matching_removed_fk` 를 보고 | 절대 임계 없음 — 관측값 |
| **SC-005** | `wrong_bindings == 0` | **엄격.** 못 찾는 것보다 틀리게 찾는 것이 나쁘다 |

**엄격 기준 셋(SC-001·003·005)은 하나라도 어긋나면 `FAIL`** 이다. 나머지는 관측값으로
보고하되, SC-002 는 T3 기준선과 비교해 판정한다.

### SC-002 의 절대 임계를 지금 정하지 않는 이유

증강 품질이 LLM 에 의존하므로, 임계를 미리 박으면 **채점기 문제인지 증강 품질 문제인지**
구분하지 못한 채 숫자만 좇게 된다. T3 에서 기준선을 재고, T4 에서 개선 폭을 보고, 그때
"이 정도면 시나리오가 성립한다"를 정한다.

---

## 이름 비교는 대소문자를 무시한다

매핑의 `target` 은 `TB01` 이지만 **PostgreSQL 은 따옴표 없는 식별자를 소문자로 접는다** —
실제 테이블은 `tb01` 이고, 카탈로그에도 그렇게 들어온다 (2026-08-05 실측).

채점기는 테이블·컬럼 이름을 **소문자로 정규화한 뒤** 비교한다. 이 한 줄이 없으면 SC-002 가
항상 0이 나오고, 원인은 "증강이 실패했다"로 오독되기 쉽다.

## 선행 검사 — 실패하면 채점하지 않는다

1. **매핑 해시 일치.** 생성물의 해시 주석과 현재 매핑이 다르면 중단한다. 어긋난 채로 채점하면
   **조용히 틀린 답**이 나온다 — 채점기는 매핑을 정답으로 믿는다.
2. **난독화 완전성.** `legacy` 스키마에 원본 이름이 하나라도 남아 있으면 중단한다. 남은
   이름은 의미가 새는 구멍이고, SC-001 이 0이 아닌 이유가 된다.
3. **데이터 보존.** 채점 전후로 `:DataSource` 수가 같아야 한다 (FR-032·SC-007). 줄었으면
   **채점 결과를 신뢰하지 않고** 중단한다.

> 3번은 분석기 전역 삭제 수정(2026-08-05)에 의존한다. 그 수정이 실증되기 전에는 이 검사가
> 곧 실증 수단이다.

---

## 제외 항목을 반드시 보고한다

| 필드 | 뜻 |
|---|---|
| `excluded.no_label` | 매핑에 `label` 이 없어 채점 못 한 항목 |
| `excluded.prefiltered_out` | 후보 축소로 탈락한 수 (research R2) |

**축소가 정답을 떨어뜨렸는지 추적하기 위해서다.** 후보 축소는 성능 최적화이지 판정이 아니므로,
축소 때문에 SC-002 가 낮아졌다면 그것은 채점기가 아니라 축소 임계의 문제다. 이 수를 보고하지
않으면 두 원인을 구분할 수 없다.
