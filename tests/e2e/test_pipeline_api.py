"""
Ontologic 플랫폼 API 레벨 E2E 회귀 테스트

설치 후 핵심 파이프라인이 살아있는지 검증한다:
  인프라(Neo4j/PostgreSQL/MySQL/MindsDB) → data-fabric(데이터소스/메타데이터)
  → text2sql(자연어 → SQL → MindsDB 실행)

실행:
    cd tests/e2e
    uv run --with pytest --with requests --with python-dotenv \
        pytest test_pipeline_api.py -v

포트/접속 정보는 레포 루트 .env 를 따른다 (installation.md 참조).
"""
import json
import os
import time
from pathlib import Path

import pytest
import requests
from dotenv import load_dotenv

# 레포 루트 .env 로드 (서비스들과 동일한 단일 설정 소스)
REPO_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(REPO_ROOT / ".env")

DATA_FABRIC = os.getenv("DATA_FABRIC_URL", "http://127.0.0.1:8004")
TEXT2SQL = os.getenv("TEXT2SQL_BASE_URL", "http://127.0.0.1:8020/text2sql").rsplit("/text2sql", 1)[0]
MINDSDB = os.getenv("MINDSDB_URL", "http://127.0.0.1:47334")
NEO4J_HTTP = os.getenv("NEO4J_HTTP_URL", "http://127.0.0.1:7475")

TIMEOUT = 30


# ──────────────────────────────────────────────────────────────
# 1. 인프라 헬스체크
# ──────────────────────────────────────────────────────────────

class TestInfra:
    def test_mindsdb_status(self):
        r = requests.get(f"{MINDSDB}/api/status", timeout=TIMEOUT)
        assert r.status_code == 200

    def test_neo4j_http(self):
        r = requests.get(NEO4J_HTTP, timeout=TIMEOUT)
        assert r.status_code == 200

    def test_data_fabric_health(self):
        r = requests.get(f"{DATA_FABRIC}/health", timeout=TIMEOUT)
        assert r.status_code == 200
        assert r.json().get("status") == "healthy"

    def test_text2sql_health(self):
        r = requests.get(f"{TEXT2SQL}/health", timeout=TIMEOUT)
        assert r.status_code == 200


# ──────────────────────────────────────────────────────────────
# 2. 데이터패브릭: 데이터소스 등록 상태
# ──────────────────────────────────────────────────────────────

EXPECTED_DATASOURCES = {"manufacturing", "insurance", "sales"}


class TestDataFabric:
    def test_datasources_registered(self):
        r = requests.get(f"{DATA_FABRIC}/api/datasources", timeout=TIMEOUT)
        assert r.status_code == 200
        names = {ds["name"] for ds in r.json()["datasources"]}
        missing = EXPECTED_DATASOURCES - names
        assert not missing, f"등록 안 된 데이터소스: {missing}"

    def test_manufacturing_tables_visible(self):
        r = requests.get(
            f"{DATA_FABRIC}/api/datasources/manufacturing/tables",
            params={"schema": "manufacturing", "source": "neo4j"},
            timeout=TIMEOUT,
        )
        assert r.status_code == 200


# ──────────────────────────────────────────────────────────────
# 3. MindsDB 경유 실 데이터 질의 (federated query)
# ──────────────────────────────────────────────────────────────

def _mindsdb_sql(query: str) -> dict:
    r = requests.post(
        f"{MINDSDB}/api/sql/query",
        json={"query": query},
        timeout=120,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["type"] != "error", body.get("error_message")
    return body


class TestMindsDBFederation:
    def test_postgres_manufacturing_query(self):
        body = _mindsdb_sql(
            "SELECT COUNT(*) AS cnt FROM manufacturing.manufacturing.mfg_product;"
        )
        cnt = int(body["data"][0][0])
        assert cnt >= 1, "manufacturing.mfg_product 데이터 없음"

    def test_mysql_insurance_query(self):
        body = _mindsdb_sql("SELECT COUNT(*) AS cnt FROM insurance.customers;")
        cnt = int(body["data"][0][0])
        assert cnt >= 1, "insurance.customers 데이터 없음"

    def test_mysql_sales_query(self):
        body = _mindsdb_sql("SELECT COUNT(*) AS cnt FROM sales.orders;")
        cnt = int(body["data"][0][0])
        assert cnt >= 1, "sales.orders 데이터 없음"


# ──────────────────────────────────────────────────────────────
# 4. Text2SQL 스키마 인식 + ReAct 자연어 질의
# ──────────────────────────────────────────────────────────────

class TestText2SQL:
    def test_meta_datasources(self):
        r = requests.get(f"{TEXT2SQL}/text2sql/meta/datasources", timeout=TIMEOUT)
        assert r.status_code == 200
        assert EXPECTED_DATASOURCES <= set(r.json())

    @pytest.mark.slow
    def test_react_nl_query_manufacturing(self):
        """자연어 → SQL → MindsDB 실행 전체 파이프라인 (LLM 호출, 수 분 소요 가능)"""
        payload = {
            "question": "등록된 제품이 모두 몇 개인지 알려줘",
            "datasource": "manufacturing",
            "schema_filter": ["manufacturing"],  # 멀티 데이터소스 환경 필수 (installation.md 이슈 #10)
            "max_iterations": 5,
        }
        completed = None
        with requests.post(
            f"{TEXT2SQL}/text2sql/react",
            json=payload,
            stream=True,
            timeout=600,
        ) as resp:
            assert resp.status_code == 200
            deadline = time.time() + 570
            for line in resp.iter_lines(decode_unicode=True):
                if time.time() > deadline:
                    pytest.fail("ReAct 응답 타임아웃")
                if not line or not line.strip().startswith("{"):
                    continue
                try:
                    evt = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if evt.get("event") == "completed":
                    completed = evt["response"]
                    break
                if evt.get("event") == "error":
                    pytest.fail(f"ReAct 오류: {json.dumps(evt, ensure_ascii=False)[:500]}")

        assert completed, "completed 이벤트를 받지 못함"
        assert completed["status"] == "completed"
        assert completed["final_sql"], "최종 SQL 없음"
        result = completed["execution_result"]
        assert result and result["row_count"] >= 1, "실행 결과 없음"


if __name__ == "__main__":
    import sys
    sys.exit(pytest.main([__file__, "-v", *sys.argv[1:]]))
