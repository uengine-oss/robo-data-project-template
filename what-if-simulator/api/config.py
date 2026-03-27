"""
API Configuration
==================

환경변수 및 설정 관리
"""

import os
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """API 설정"""
    
    # API Server
    api_host: str = "0.0.0.0"
    api_port: int = 8005  # 8001은 robo-architect에서 사용 중
    
    # MySQL (MindsDB 연결용 물리 계층)
    mysql_host: str = "localhost"
    mysql_port: int = 3307
    mysql_database: str = "sample_db"
    mysql_user: str = "sampleuser"
    mysql_password: str = "samplepass123"
    
    # Neo4j
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "12345analyzer"
    neo4j_database: str = "neo4j"
    
    # MindsDB
    mindsdb_url: str = "http://127.0.0.1:47334"
    
    # Text2SQL Service
    text2sql_url: str = "http://localhost:8000"
    
    # OpenAI
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    
    # Validation
    test_ratio: float = 0.2
    significance_level: float = 0.05
    min_correlation: float = 0.35
    
    class Config:
        env_file = ".env"
        env_prefix = "WHATIF_"
        case_sensitive = False


settings = Settings()

# 환경변수에서 OpenAI 키 로드 (메모리에서 참조)
if not settings.openai_api_key:
    settings.openai_api_key = os.getenv(
        "OPENAI_API_KEY", 
        ""
    )
