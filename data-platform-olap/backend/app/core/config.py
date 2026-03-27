"""Configuration settings for AI Pivot Studio."""
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings."""
    
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")
    
    # API Settings
    app_name: str = "AI Pivot Studio"
    debug: bool = True
    
    # OpenAI Settings
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    
    # Database Settings
    database_url: str = "postgresql://postgres:postgres@localhost:5432/pivot_studio"
    
    # Query Settings
    query_timeout: int = 30
    max_rows: int = 1000
    
    # Neo4j Settings (for catalog exploration and lineage)
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = ""
    neo4j_database: str = "neo4j"
    
    # DW Schema Settings
    dw_schema: str = "dw"


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()

