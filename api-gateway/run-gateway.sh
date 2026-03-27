#!/bin/bash

# API Gateway 실행 스크립트

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║              API Gateway 시작                                 ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""
echo "Gateway URL: http://localhost:9000"
echo ""
echo "라우팅 정보:"
echo "  /antlr/**     -> http://127.0.0.1:8081 (ANTLR Parser)"
echo "  /robo/**      -> http://127.0.0.1:5502 (ROBO Analyzer)"
echo "  /text2sql/**  -> http://127.0.0.1:8000 (Text2SQL)"
echo "  /olap/**      -> http://127.0.0.1:8002 (Data Platform OLAP)"
echo "  /architect/** -> http://127.0.0.1:8001 (ROBO Architect)"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Maven이 설치되어 있으면 사용, 아니면 mvnw 사용
if command -v mvn &> /dev/null; then
    mvn spring-boot:run
else
    ./mvnw spring-boot:run
fi

