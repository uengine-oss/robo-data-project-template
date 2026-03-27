#!/bin/bash

# ╔══════════════════════════════════════════════════════════════╗
# ║         전체 마이크로서비스 종료 스크립트                         ║
# ╚══════════════════════════════════════════════════════════════╝

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Robo Analyzer 마이크로서비스 종료"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# 저장된 PID 파일에서 종료
if [ -f /tmp/robo-services.pids ]; then
  PIDS=$(cat /tmp/robo-services.pids)
  for PID in $PIDS; do
    if ps -p $PID > /dev/null 2>&1; then
      echo "종료 중: PID $PID"
      kill $PID 2>/dev/null
    fi
  done
  rm -f /tmp/robo-services.pids
fi

# 포트별 프로세스 종료
echo ""
echo "포트별 프로세스 종료 중..."

# API Gateway (9000)
lsof -ti :9000 | xargs kill -9 2>/dev/null && echo "  [✓] 포트 9000 (API Gateway) 종료"

# ANTLR Parser (8081)
lsof -ti :8081 | xargs kill -9 2>/dev/null && echo "  [✓] 포트 8081 (ANTLR Parser) 종료"

# ROBO Analyzer (5502)
lsof -ti :5502 | xargs kill -9 2>/dev/null && echo "  [✓] 포트 5502 (ROBO Analyzer) 종료"

# Text2SQL (8000)
lsof -ti :8000 | xargs kill -9 2>/dev/null && echo "  [✓] 포트 8000 (Text2SQL) 종료"

# OLAP (8002)
lsof -ti :8002 | xargs kill -9 2>/dev/null && echo "  [✓] 포트 8002 (OLAP) 종료"

# Architect (8001)
lsof -ti :8001 | xargs kill -9 2>/dev/null && echo "  [✓] 포트 8001 (Architect) 종료"

echo ""
echo "✅ 모든 서비스가 종료되었습니다."
echo ""

