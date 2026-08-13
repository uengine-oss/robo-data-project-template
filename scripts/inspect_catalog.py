#!/usr/bin/env python3
"""Re-verify the data catalog contract recorded in the constitution.

The constitution (`.specify/memory/constitution.md`) states what the catalog
graph looks like, and `docs/catalog-schema.md` records the measurements behind
it. Those were true when written; this script checks they are still true, so a
drifted contract is caught deliberately instead of by a confusing bug three
services away.

    python3 scripts/inspect_catalog.py
    python3 scripts/inspect_catalog.py --datasource itest_pg --schema manufacturing

The contract spans every service on the shared graph, so this reads the root
`.env` directly rather than importing any one submodule's settings — it must
keep working if a submodule is missing or its dependencies are not installed.

Exit code 0 = the contract holds. Non-zero = at least one expectation drifted.
"""

from __future__ import annotations

import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

CHECKS: list[tuple[str, bool, str]] = []


def read_env(*names: str, default: str = "") -> str:
    """First value found for `names` — os.environ wins, then the root `.env`.

    Deliberately not python-dotenv: this script is a contract check that has to
    run from a bare checkout, so it takes no third-party dependency beyond the
    neo4j driver it cannot avoid.
    """
    import os

    for name in names:
        if os.environ.get(name):
            return os.environ[name]

    env_file = ROOT / ".env"
    if env_file.exists():
        for raw in env_file.read_text(encoding="utf-8", errors="replace").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            if key.strip() in names:
                return value.strip().strip("\"'")
    return default


def record(name: str, ok: bool, detail: str = "") -> None:
    CHECKS.append((name, ok, detail))
    print(f"[{'OK ' if ok else 'DRIFT'}] {name}" + (f" — {detail}" if detail else ""))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--datasource", default="", help="검사할 데이터소스 (기본: 첫 번째)")
    parser.add_argument("--schema", default="", help="검사할 스키마 (기본: 첫 번째)")
    args = parser.parse_args()

    from neo4j import READ_ACCESS, GraphDatabase

    uri = read_env("NEO4J_URI", default="bolt://localhost:7687")
    user = read_env("NEO4J_USER", "NEO4J_USERNAME", default="neo4j")
    password = read_env("NEO4J_PASSWORD", default="neo4j")
    print(f"Neo4j: {uri}\n")
    driver = GraphDatabase.driver(uri, auth=(user, password), connection_timeout=30)

    def rows(cypher: str, **params):
        with driver.session(default_access_mode=READ_ACCESS) as session:
            return [record_.data() for record_ in session.run(cypher, params)]

    try:
        # ── II. 노드가 존재하고 정체성 속성을 갖는가 ─────────────────────
        labels = {row["label"] for row in rows("CALL db.labels() YIELD label RETURN label")}
        for label in ("DataSource", "Schema", "Table", "Column"):
            record(f"II. :{label} 라벨 존재", label in labels)

        rel_types = {
            row["t"] for row in
            rows("CALL db.relationshipTypes() YIELD relationshipType AS t RETURN t")
        }
        for rel in ("HAS_SCHEMA", "HAS_TABLE", "HAS_COLUMN"):
            record(f"II. [:{rel}] 관계 존재", rel in rel_types)

        # ── 검사 대상 고르기 ─────────────────────────────────────────────
        datasource = args.datasource
        schema = args.schema
        if not datasource or not schema:
            picked = rows(
                "MATCH (t:Table) WHERE t.datasource IS NOT NULL OR t.db IS NOT NULL "
                "RETURN coalesce(t.datasource, t.db) AS ds, t.schema AS sc LIMIT 1"
            )
            if not picked:
                record("카탈로그에 테이블 존재", False, "메타데이터 추출을 먼저 실행하세요")
                return summarize()
            datasource = datasource or picked[0]["ds"]
            schema = schema or picked[0]["sc"]
        print(f"\n검사 대상: {datasource} / {schema}\n")

        params = {"ds": datasource, "sc": schema}

        # ── III. 컬럼 타입과 PK 를 어느 표기로 읽을 수 있는가 ────────────
        column_rows = rows(
            "MATCH (t:Table)-[:HAS_COLUMN]->(c:Column) "
            "WHERE (t.datasource = $ds OR t.db = $ds) AND t.schema = $sc "
            "RETURN c.type AS type, c.dtype AS dtype, "
            "c.primary_key AS pk, c.is_primary_key AS pk_alt LIMIT 200",
            **params,
        )
        record("III. 컬럼을 읽을 수 있다", bool(column_rows), f"{len(column_rows)}개")
        if column_rows:
            has_type = sum(1 for r in column_rows if r["type"])
            has_dtype = sum(1 for r in column_rows if r["dtype"])
            record(
                "III. 타입은 두 표기 중 하나에 있다",
                bool(has_type or has_dtype),
                f"type={has_type} dtype={has_dtype} → coalesce 필수",
            )
            has_pk = sum(1 for r in column_rows if r["pk"] is not None)
            has_pk_alt = sum(1 for r in column_rows if r["pk_alt"] is not None)
            record(
                "III. PK 도 두 표기 중 하나에 있다",
                bool(has_pk or has_pk_alt),
                f"primary_key={has_pk} is_primary_key={has_pk_alt}",
            )

        # ── III. 외래키를 어느 형태로 읽을 수 있는가 ─────────────────────
        fk_shapes = {
            "REFERENCES (column→column)":
                "MATCH (t:Table)-[:HAS_COLUMN]->(:Column)-[r:REFERENCES]->(:Column) "
                "WHERE (t.datasource = $ds OR t.db = $ds) AND t.schema = $sc RETURN count(r) AS c",
            "FK_TO (column→column)":
                "MATCH (t:Table)-[:HAS_COLUMN]->(:Column)-[r:FK_TO]->(:Column) "
                "WHERE (t.datasource = $ds OR t.db = $ds) AND t.schema = $sc RETURN count(r) AS c",
            "FK_TO_TABLE (table→table)":
                "MATCH (t:Table)-[r:FK_TO_TABLE]->(:Table) "
                "WHERE (t.datasource = $ds OR t.db = $ds) AND t.schema = $sc RETURN count(r) AS c",
        }
        found_any = False
        for name, cypher in fk_shapes.items():
            try:
                count = rows(cypher, **params)[0]["c"]
            except Exception:
                count = 0
            if count:
                found_any = True
            print(f"        {name}: {count}")
        record("III. 외래키를 최소 한 형태로 읽을 수 있다", found_any)

        # ── II. Table MERGE 키가 db 를 포함하지 않는 위험 ────────────────
        collisions = rows(
            "MATCH (t:Table) WITH t.schema AS sc, t.name AS n, count(*) AS c, "
            "collect(DISTINCT t.db) AS dbs WHERE size(dbs) > 1 "
            "RETURN sc, n, dbs LIMIT 5"
        )
        record(
            "II. schema.table 이 여러 DB 에 걸쳐 합쳐지지 않았다",
            not collisions,
            "" if not collisions else f"충돌 {len(collisions)}건: {collisions[:2]}",
        )

        # ── V. 자격증명이 카탈로그에 평문으로 있다 (사실 확인) ───────────
        secret_rows = rows(
            "MATCH (d:DataSource) RETURN d.name AS name, "
            "d.password IS NOT NULL AS has_password LIMIT 20"
        )
        exposed = [r["name"] for r in secret_rows if r["has_password"]]
        record(
            "V. :DataSource 가 평문 자격증명을 보유한다 (노출 금지 대상)",
            True,
            f"{len(exposed)}/{len(secret_rows)}개 데이터소스에 password 속성 존재",
        )

        # ── VII. 가상 클래스는 인스턴스를 만들지 않는다 ──────────────────
        entity_count = rows("MATCH (n:`_Entity`) RETURN count(n) AS c")[0]["c"]
        print(f"\n        참고: (:_Entity) 인스턴스 {entity_count}개 "
              f"(문서 기반 클래스의 것. 가상 클래스는 0이어야 한다)")

        return summarize()
    finally:
        driver.close()


def summarize() -> int:
    drift = [(name, detail) for name, ok, detail in CHECKS if not ok]
    print("\n" + "=" * 68)
    print(f"확인 {len(CHECKS) - len(drift)} · 어긋남 {len(drift)}")
    if drift:
        print("\n계약과 어긋난 항목 — constitution 을 갱신하거나 원인을 고치세요:")
        for name, detail in drift:
            print(f"  - {name}: {detail}")
    else:
        print("constitution 의 카탈로그 계약이 현재 그래프와 일치합니다.")
    print("=" * 68)
    return 0 if not drift else 1


if __name__ == "__main__":
    raise SystemExit(main())
