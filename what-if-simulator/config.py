"""
What-if Simulator Configuration

Neo4j와 MindsDB 연결 설정
"""

import os
from dataclasses import dataclass


@dataclass
class Neo4jConfig:
    """Neo4j 연결 설정"""
    uri: str = "bolt://localhost:7687"
    user: str = "neo4j"
    password: str = "12345analyzer"
    database: str = "neo4j"


@dataclass
class MindsDBConfig:
    """MindsDB 연결 설정"""
    # HTTP API 엔드포인트
    http_url: str = "http://127.0.0.1:47334"
    api_endpoint: str = "/api/sql/query"
    
    # MySQL 프로토콜 (alternative)
    mysql_host: str = "localhost"
    mysql_port: int = 47335
    mysql_user: str = "mindsdb"
    mysql_password: str = ""
    mysql_db: str = "mindsdb"
    
    @property
    def full_api_url(self) -> str:
        return f"{self.http_url}{self.api_endpoint}"


@dataclass
class SimulationConfig:
    """시뮬레이션 설정"""
    # 시뮬레이션 기본 설정
    default_time_steps: int = 12  # 12개월 기본
    seed: int = 42
    
    # 시나리오 기본값
    default_fx_rate: float = 1200.0  # KRW/USD
    default_pass_through: float = 0.5  # 50% 가격 전가
    default_mkt_spend: float = 100.0  # 마케팅 지출 지수
    default_service_level: float = 0.8  # 서비스 수준 (0-1)


# 전역 설정 인스턴스
neo4j_config = Neo4jConfig(
    uri=os.getenv("NEO4J_URI", "bolt://localhost:7687"),
    user=os.getenv("NEO4J_USER", "neo4j"),
    password=os.getenv("NEO4J_PASSWORD", "12345analyzer"),
    database=os.getenv("NEO4J_DATABASE", "neo4j")
)

mindsdb_config = MindsDBConfig(
    http_url=os.getenv("MINDSDB_URL", "http://127.0.0.1:47334"),
)

simulation_config = SimulationConfig()


@dataclass
class Settings:
    """통합 설정 클래스 (cld_generator 등에서 사용)"""
    NEO4J_URI: str = "bolt://localhost:7687"
    NEO4J_USER: str = "neo4j"
    NEO4J_PASSWORD: str = "12345analyzer"
    NEO4J_DATABASE: str = "neo4j"
    MINDSDB_URL: str = "http://127.0.0.1:47334"
    
    def __post_init__(self):
        # 환경변수에서 로드
        self.NEO4J_URI = os.getenv("NEO4J_URI", self.NEO4J_URI)
        self.NEO4J_USER = os.getenv("NEO4J_USER", self.NEO4J_USER)
        self.NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", self.NEO4J_PASSWORD)
        self.NEO4J_DATABASE = os.getenv("NEO4J_DATABASE", self.NEO4J_DATABASE)
        self.MINDSDB_URL = os.getenv("MINDSDB_URL", self.MINDSDB_URL)


if __name__ == "__main__":
    print("=== What-if Simulator Configuration ===")
    print(f"\nNeo4j Config:")
    print(f"  URI: {neo4j_config.uri}")
    print(f"  User: {neo4j_config.user}")
    print(f"  Database: {neo4j_config.database}")
    
    print(f"\nMindsDB Config:")
    print(f"  HTTP URL: {mindsdb_config.full_api_url}")
    print(f"  MySQL Host: {mindsdb_config.mysql_host}:{mindsdb_config.mysql_port}")
    
    print(f"\nSimulation Config:")
    print(f"  Time Steps: {simulation_config.default_time_steps}")
    print(f"  Default FX Rate: {simulation_config.default_fx_rate}")
