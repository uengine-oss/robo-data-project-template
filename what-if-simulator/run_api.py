#!/usr/bin/env python3
"""
What-If Simulator API Server
============================

Causal Discovery 기반 시뮬레이션 API 서버를 실행합니다.

Usage:
    python run_api.py
    # 또는
    uvicorn api.main:app --host 0.0.0.0 --port 8001 --reload
"""

import uvicorn
import sys
import os

# 프로젝트 루트를 Python 경로에 추가
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from api.config import settings


def main():
    """API 서버 시작"""
    print(f"""
╔══════════════════════════════════════════════════════════════╗
║       What-If Simulator API Server                           ║
║       Causal Discovery 기반 시뮬레이션 플랫폼                ║
╠══════════════════════════════════════════════════════════════╣
║  Direct:  http://{settings.api_host}:{settings.api_port}                  ║
║  Gateway: http://localhost:9000/api/gateway/whatif           ║
║  Docs:    http://{settings.api_host}:{settings.api_port}/docs             ║
║  MySQL:   {settings.mysql_host}:{settings.mysql_port}                            ║
║  MindsDB: {settings.mindsdb_url}                   ║
╚══════════════════════════════════════════════════════════════╝
    """)
    
    uvicorn.run(
        "api.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=True,
        log_level="info"
    )


if __name__ == "__main__":
    main()
