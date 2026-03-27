#!/bin/bash

# ╔══════════════════════════════════════════════════════════════╗
# ║         전체 마이크로서비스 시작 스크립트                         ║
# ╚══════════════════════════════════════════════════════════════╝

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Robo Analyzer 마이크로서비스 시작"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# 색상 정의
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_status() {
  echo -e "${GREEN}[✓]${NC} $1"
}

print_info() {
  echo -e "${BLUE}[i]${NC} $1"
}

print_warn() {
  echo -e "${YELLOW}[!]${NC} $1"
}

# 1. API Gateway (Spring Cloud Gateway)
echo ""
print_info "1. API Gateway 시작 (포트 9000)..."
cd "$SCRIPT_DIR/api-gateway"
if command -v mvn &> /dev/null; then
  mvn spring-boot:run > /tmp/api-gateway.log 2>&1 &
else
  ./mvnw spring-boot:run > /tmp/api-gateway.log 2>&1 &
fi
GATEWAY_PID=$!
print_status "API Gateway 시작됨 (PID: $GATEWAY_PID)"

sleep 3

# 2. ANTLR Parser (Spring Boot)
echo ""
print_info "2. ANTLR Parser 시작 (포트 8081)..."
cd "$SCRIPT_DIR/antlr-code-parser"
if command -v mvn &> /dev/null; then
  mvn spring-boot:run > /tmp/antlr-parser.log 2>&1 &
else
  ./mvnw spring-boot:run > /tmp/antlr-parser.log 2>&1 &
fi
ANTLR_PID=$!
print_status "ANTLR Parser 시작됨 (PID: $ANTLR_PID)"

# 3. ROBO Analyzer (FastAPI)
echo ""
print_info "3. ROBO Analyzer 시작 (포트 5502)..."
cd "$SCRIPT_DIR/robo-analyzer"
if [ -d ".venv" ]; then
  source .venv/bin/activate
fi
uvicorn main:app --host 0.0.0.0 --port 5502 > /tmp/robo-analyzer.log 2>&1 &
ROBO_PID=$!
print_status "ROBO Analyzer 시작됨 (PID: $ROBO_PID)"

# 4. Text2SQL (FastAPI)
echo ""
print_info "4. Text2SQL 시작 (포트 8000)..."
cd "$SCRIPT_DIR/neo4j-text2sql"
if [ -f ".venv/bin/activate" ]; then
  source .venv/bin/activate
fi
uv run python main.py > /tmp/text2sql.log 2>&1 &
T2SQL_PID=$!
print_status "Text2SQL 시작됨 (PID: $T2SQL_PID)"

# 5. Data Platform OLAP (FastAPI)
echo ""
print_info "5. Data Platform OLAP 시작 (포트 8002)..."
cd "$SCRIPT_DIR/data-platform-olap/backend"
if [ -d ".venv" ]; then
  source .venv/bin/activate
fi
uvicorn app.main:app --host 0.0.0.0 --port 8002 > /tmp/olap.log 2>&1 &
OLAP_PID=$!
print_status "Data Platform OLAP 시작됨 (PID: $OLAP_PID)"

# 6. ROBO Architect (FastAPI)
echo ""
print_info "6. ROBO Architect 시작 (포트 8001)..."
cd "$SCRIPT_DIR/robo-architect"
if [ -d ".venv" ]; then
  source .venv/bin/activate
fi
uvicorn api.main:app --host 0.0.0.0 --port 8001 > /tmp/architect.log 2>&1 &
ARCH_PID=$!
print_status "ROBO Architect 시작됨 (PID: $ARCH_PID)"

sleep 2

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "🚀 모든 서비스가 시작되었습니다!"
echo ""
echo "  API Gateway:      http://localhost:9000"
echo "  ANTLR Parser:     http://localhost:8081 (via /antlr/*)"
echo "  ROBO Analyzer:    http://localhost:5502 (via /robo/*)"
echo "  Text2SQL:         http://localhost:8000 (via /text2sql/*)"
echo "  OLAP:             http://localhost:8002 (via /olap/*)"
echo "  Architect:        http://localhost:8001 (via /architect/*)"
echo ""
echo "📝 로그 파일:"
echo "  /tmp/api-gateway.log"
echo "  /tmp/antlr-parser.log"
echo "  /tmp/robo-analyzer.log"
echo "  /tmp/text2sql.log"
echo "  /tmp/olap.log"
echo "  /tmp/architect.log"
echo ""
echo "🔧 헬스 체크: curl http://localhost:9000/actuator/health"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# PID 저장
echo "$GATEWAY_PID $ANTLR_PID $ROBO_PID $T2SQL_PID $OLAP_PID $ARCH_PID" > /tmp/robo-services.pids
print_info "PID 저장됨: /tmp/robo-services.pids"
echo ""

