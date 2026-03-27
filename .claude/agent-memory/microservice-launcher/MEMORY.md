# Microservice Launcher Memory

## Project: robo-analyz
Working directory: /Users/uengine/robo-analyz

## Docker Environment
- Docker runtime: Colima (NOT Docker Desktop)
- Colima socket: /Users/uengine/.colima/default/docker.sock
- Start colima with: `colima start`
- Check status: `colima status`
- Colima auto-starts infrastructure containers on restart (robo-postgres, robo-mindsdb, robo-mysql-sample)

## Service Registry (Port -> Service -> Startup Command)

| Port | Service | Startup Command | Log |
|------|---------|-----------------|-----|
| 9000 | API Gateway | `cd /Users/uengine/robo-analyz/api-gateway && ./mvnw spring-boot:run` | /tmp/api-gateway.log |
| 8081 | ANTLR Parser | `cd /Users/uengine/robo-analyz/antlr-code-parser && ./mvnw spring-boot:run` | /tmp/antlr-parser.log |
| 5502 | ROBO Analyzer | `cd /Users/uengine/robo-analyz/robo-analyzer && source .venv/bin/activate && uvicorn main:app --host 0.0.0.0 --port 5502` | /tmp/robo-analyzer.log |
| 8000 | Neo4j Text2SQL | `cd /Users/uengine/robo-analyz/neo4j-text2sql && uv run python main.py` | /tmp/neo4j-text2sql.log |
| 8001 | PDF2BPMN API | `cd /Users/uengine/robo-analyz/process-gpt-bpmn-extractor && .venv/bin/python run.py api --port 8001` | /tmp/pdf2bpmn-api.log |
| 8002 | Domain Layer | `cd /Users/uengine/robo-analyz/domain-layer && venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8002` | /tmp/domain-layer.log |
| 8003 | Risk Calculator | `cd /Users/uengine/robo-analyz/risk-calculator && .venv/bin/python main.py` | /tmp/risk-calculator.log |
| 8004 | Data Fabric | `cd /Users/uengine/robo-analyz/data-fabric/backend && source .venv/bin/activate && uvicorn app.main:app --host 0.0.0.0 --port 8004` | /tmp/data-fabric.log |
| 8005 | What-If Simulator | `cd /Users/uengine/robo-analyz/what-if-simulator && .venv/bin/python run_api.py` | /tmp/what-if-simulator.log |
| 8006 | Data Secure Guard | `cd /Users/uengine/robo-analyz/data-secure-guard && source .venv/bin/activate && uvicorn api.main:app --host 0.0.0.0 --port 8006` | /tmp/data-secure-guard.log |
| 8089 | Agent Scheduler | `cd /Users/uengine/robo-analyz/agent-scheduler && source .venv/bin/activate && uvicorn app.main:app --host 0.0.0.0 --port 8089` | /tmp/agent-scheduler.log |
| 3000 | Frontend Vue3 | `cd /Users/uengine/robo-analyz/robo-analyzer-vue3 && npm run dev -- --port 3000` | /tmp/frontend-vue3.log |
| 9999 | A2A Server | `cd /Users/uengine/robo-analyz/process-gpt-bpmn-extractor && .venv/bin/python a2a_server.py` | /tmp/a2a-server.log |

## Health Check Endpoints
- API Gateway (9000): GET /actuator/health -> 200
- ANTLR Parser (8081): GET / -> 200 (NOT /actuator/health - returns 500, no actuator)
- ROBO Analyzer (5502): GET /health -> 200
- Neo4j Text2SQL (8000): GET /health -> 200
- PDF2BPMN API (8001): GET /docs -> 200 (no /health endpoint)
- Domain Layer (8002): GET /health -> 200
- Risk Calculator (8003): GET /health -> 200
- Data Fabric (8004): GET /health -> 200
- What-If Simulator (8005): GET /docs -> 200 (no /health endpoint)
- Data Secure Guard (8006): GET /health -> 200
- Agent Scheduler (8089): GET /health -> 200
- Frontend Vue3 (3000): GET / -> 200
- A2A Server (9999): GET /discover -> 200 (NOT / - returns 404)

## Critical Notes & Known Issues

### Neo4j Text2SQL (port 8000)
- Requires MindsDB (localhost:47335) to be up BEFORE startup
- On startup, runs sanity checks - fails if MindsDB not ready
- Solution: Start AFTER Colima/Docker is healthy. If it fails, wait and restart.

### pdf2bpmn-neo4j Docker container
- CONFLICTS with Neo4j Desktop running on ports 7687/7474 (always running on host)
- Do NOT start this container - it will exit with code 134
- PDF2BPMN and A2A run on HOST directly, using Neo4j Desktop at localhost:7687

### Risk Calculator (port 8003)
- `uv run python main.py` fails due to pyproject.toml missing hatch wheel build config
- Solution: Use `.venv/bin/python main.py` directly

### What-If Simulator (port 8005)
- Do NOT run `python api/main.py` directly (relative import error)
- Solution: Use `run_api.py` from the project root which adds sys.path correctly

### Data Secure Guard (port 8006)
- run_api.sh uses port 8001 by default (conflicts with PDF2BPMN)
- Always launch with explicit port via uvicorn command

### start-all-services.sh / stop-all-services.sh
- OUTDATED - references non-existent directories (data-platform-olap, robo-architect)
- stop-all-services.sh only kills ports 9000, 8081, 5502, 8000, 8001, 8002
- Use manual port-by-port kill for complete shutdown

## Service Dependency Order
1. Start Colima first -> waits for robo-postgres, robo-mindsdb to be healthy
2. Start Java services (API Gateway, ANTLR Parser) and Python services in parallel
3. Start Neo4j Text2SQL AFTER MindsDB is confirmed healthy (check port 47335)
4. PDF2BPMN API and A2A Server can start anytime (use Neo4j Desktop, always running)

## Docker Containers (Colima-managed)
- robo-postgres: port 5432
- robo-mindsdb: ports 47334-47335
- robo-mysql-sample: port 3307
- nkesa-mysql: port 3308
- data-fabric-postgres: port 5433
