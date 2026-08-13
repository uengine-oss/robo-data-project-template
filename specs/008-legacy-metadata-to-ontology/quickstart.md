# Quickstart — 시나리오 검증

spec 008 이 실제로 성립하는지 확인하는 절차. **각 단계는 앞 단계 없이도 되돌릴 수 있다**
(plan.md 의 T 단계와 대응).

---

## 사전 조건

```bash
# 설치본이 떠 있어야 한다 (앱 origin 확인)
grep -a "앱 origin" "$HOME/Library/Application Support/Ontology Studio/logs/desktop.log" | tail -1

# 컨테이너가 healthy 인지
CONTAINER_CONNECTION=ontology-studio podman ps --format "{{.Names}}\t{{.Status}}"
```

앱을 띄울 때는 **셸에서 분리**해야 한다. `npm start` 를 백그라운드로 두면 툴 셸이 정리될 때
앱이 함께 내려간다(`scripts/start.js` 가 `stdio: 'inherit'`). 새 세션으로 띄운다.

---

## T0 — 착수 전 실증 (차단)

**FR-032·SC-007 이 여기에 의존한다.** 분석기의 전역 삭제 수정(2026-08-05)이 실제로 데이터를
보존하는지 확인한다.

```bash
# 인제스천 전
CONTAINER_CONNECTION=ontology-studio podman exec ontology-studio-desktop-neo4j-1 \
  cypher-shell -u neo4j -p "$PW" --format plain \
  "MATCH (n) UNWIND labels(n) AS l RETURN l, count(*) ORDER BY l"

# 앱에서 「메타데이터 증강」 → 「분석 시작」

# 인제스천 후 — :DataSource 가 보존되어야 한다
curl -s "http://127.0.0.1:17900/api/gateway/data-fabric/api/datasources?source=neo4j"
```

**기대**: `:DataSource` 수가 인제스천 전후로 **같다.** 0이 되면 수정이 통하지 않은 것이고,
그 상태로는 T1 이후의 채점 결과를 신뢰할 수 없다.

**이 단계가 실패하면 진행하지 않는다.**

---

## T1 — 난독화 생성

```bash
uv run --with pyyaml python scripts/obfuscate_example.py \
  --mapping ontology-studio/desktop/resources/backend/seed/legacy-mapping.yaml \
  --out ontology-studio/desktop/resources
```

**검증**

```bash
# 1. 난독화 완전성 — 원본 이름이 남아 있으면 안 된다
grep -oE "mfg_[a-z_]+" ontology-studio/desktop/resources/backend/seed/postgres/0[56]_*legacy*.sql | sort -u
# → 아무것도 나오지 않아야 한다

# 2. 구조 보존 — INSERT 문 수가 원본과 같다
grep -c "^INSERT INTO" .../02_dml_master_data.sql .../06_dml_legacy.sql
```

**최종 관문**: 실제로 DB 를 세워 **테이블별 행 수가 원본과 일치**하는지 확인한다. 값이
깨졌으면 적재가 실패하거나 수가 달라진다.

---

## T2 — 예제 번들

앱을 다시 띄우고 확인:

- 「메타데이터 증강」을 열면 **난독화 예제**가 기본 선택돼 있다 (FR-030·FR-033a)
- 깨끗한 예제도 **선택 가능**하다
- 데이터소스 스키마 목록에 `legacy` 와 `manufacturing` 이 **모두** 보인다

---

## T3 — 기준선 (SC-001)

**증강하지 않은 상태**에서 채점한다.

```bash
uv run --with neo4j --with httpx --with pyyaml python scripts/score_scenario.py \
  --mapping .../legacy-mapping.yaml --datasource <이름> --schema legacy \
  --phase before
```

**기대**: `sc_001_auto_bindings_before == 0`.

0이 아니면 **난독화가 불완전한 것이다** — 현재 채점식(컬럼명 0.6 + 타입 0.2 + 이름 0.2,
`no_match` 임계 0.40)상 이름 신호가 0이면 총점이 0.2를 넘을 수 없다. T1 의 완전성 검사로
돌아간다.

---

## T4 — 증강 후 (SC-002~005)

앱에서 「분석 시작」으로 증강을 돌린 뒤:

```bash
uv run ... scripts/score_scenario.py ... --phase after --runs 3
```

**기대**: `sc_002_correct_bindings` 가 기준선(0)보다 유의하게 높고, `sc_005_wrong_bindings == 0`,
`sc_003.without_evidence == 0`.

SC-002 가 낮으면 `sc_003` 채움률로 원인을 가른다 — **채움률이 낮으면 증강 품질 문제**,
채움률은 높은데 바인딩이 안 되면 **채점기 문제**다.

---

## T5 — domain-layer 편입

```bash
# 편입 전 메모리 (기준선: 7.31 GiB, 2026-08-05)
bash scripts/measure_memory.sh

# 편입 후
bash scripts/measure_memory.sh
```

**주의**: podman/vfkit 에서 게스트 메모리는 **vfkit 프로세스에 잡히지 않는다**
(phys_footprint 16 MB). `com.apple.Virtualization.VirtualMachine` 헬퍼를 봐야 한다. 같은
머신에 VM 이 여럿이면 vfkit 과 **같은 초에 뜬** 것이 우리 것이다.

**회귀 확인**: 기존 7개 서비스가 모두 healthy 이고 시나리오 T3·T4 가 그대로 통과한다 (FR-038).

**노출 금지**: research R5 의 확인이 끝날 때까지 `GET /ontology/ontology-nodes/{id}/data` 를
데스크톱 게이트웨이에 노출하지 않는다.

---

## T7 — 객체화 (US4)

앱에서:

1. 자연어 질의 → 결과 확인
2. 결과를 온톨로지 객체로 등록
3. 온톨로지에서 그 객체 조회 → **원 질문과 SQL 이 보인다**
4. 같은 질의를 다시 객체화 → **중복이 쌓이지 않는다**
5. **가상 클래스에 객체화 시도 → 거부된다** (FR-026, spec 001 SC-001)

5번을 빠뜨리지 않는다. 가상 클래스의 인스턴스는 **정확히 0건**이어야 하고, 이 스펙이 그 계약을
깨는 가장 그럴듯한 자리다.

---

## 전체 통과 조건

```bash
# 계약 검사 (증강 속성 계약 포함)
uv run --with neo4j python scripts/inspect_catalog.py

# 채점
uv run ... scripts/score_scenario.py ... --phase after --runs 3
```

`verdict: PASS` 이고 `inspect_catalog.py` 가 계약 위반을 보고하지 않으면 통과다.

**단위 테스트만 통과한 것을 "동작한다"고 보고하지 않는다** (헌법 원칙 VII). 이 시나리오는
실서비스에서 끝까지 돌려야 검증된다.
