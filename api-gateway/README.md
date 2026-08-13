# API Gateway

Spring Cloud Gateway를 사용한 중앙 API 게이트웨이입니다.

## 개요

여러 마이크로서비스들을 하나의 엔드포인트(포트 9000)에서 접근할 수 있도록 라우팅하며, CORS 이슈를 통합 관리합니다.

## 아키텍처

```
                     ┌─────────────────────────────────────────────────────────────┐
                     │                     API Gateway (9000)                       │
                     │                                                               │
   Frontend Apps     │    ┌──────────────────────────────────────────────────────┐  │
   ─────────────────────▶│                   CORS Handler                         │  │
   (3000, 5173, 5175)    │    ┌───────────────────────────────────────────────┐  │  │
                         │    │              Route Configuration              │  │  │
                         │    └───────────────────────────────────────────────┘  │  │
                         └──────────────────────────────────────────────────────┘  │
                     └─────────────────────────────────────────────────────────────┘
                                                   │
       ┌───────────────────────────────────────────┼───────────────────────────────────────────┐
       │                      │                    │                    │                      │
       ▼                      ▼                    ▼                    ▼                      ▼
 ┌──────────┐         ┌──────────┐         ┌──────────┐         ┌──────────┐         ┌──────────┐
 │  ANTLR   │         │   ROBO   │         │ Text2SQL │         │   OLAP   │         │Architect │
 │  Parser  │         │ Analyzer │         │          │         │          │         │          │
 │  (8081)  │         │  (5502)  │         │  (8000)  │         │  (8007)  │         │  (8001)  │
 └──────────┘         └──────────┘         └──────────┘         └──────────┘         └──────────┘
   Java/Spring          Python/FastAPI      Python/FastAPI      Python/FastAPI      Python/FastAPI
```

## 라우팅 설정

`application.yml`에 선언된 순서대로 **first-match** 라우팅합니다(위에서부터 먼저 매칭되는 라우트로).

### 직접 경로

| 경로 패턴 | 대상 서비스 | 포트 | 비고 |
|-----------|-------------|------|------|
| `/antlr/**` | ANTLR Parser | 8081 | |
| `/robo/analyze/**`, `/robo/pipeline/**` | ROBO Analyzer | 5502 | |
| `/robo/glossary/**`, `/robo/business-calendar/**` | ROBO Data Catalog | 5503 | |
| `/robo/**` (catch-all) | ROBO Glossary | 5504 | |
| `/text2sql/**` | Text2SQL | 8000 | |
| `/olap/**` | Data Platform OLAP | **8007** | prefix 제거 |
| `/architect/**` | ROBO Architect | 8001 | prefix 제거 |
| `/langchain/**` | LangChain | 8001 | prefix 제거 |
| `/ontology/**`, `/api/ontology/**` | Domain Layer / Ontology | 8002 | |
| `/risk-calculator/**` | Risk Calculator | 8003 | |
| `/data-fabric/**` | Data Fabric | 8004 | |
| `/whatif/**` | What-If Simulator | 8005 | `/whatif/`→`/api/` |
| `/api/security/**` | Data Secure Guard | 8006 | |
| `/agent-scheduler/**` | Agent Scheduler | 8089 | |
| `/node-agent-scheduler/**` | Node Agent Scheduler | 8091 | |
| `/**` (fallback) | robo-data-frontend | 3000 | 미매치는 프론트로 |

### `/api/gateway/<svc>/**` prefix 라우트군

프론트가 `/api/gateway/` prefix를 붙여 보내면 RewritePath로 prefix를 떼고 위와 **동일 서비스**로 전달합니다(antlr·robo·text2sql·olap·architect·langchain·ontology·domain-whatif·data-fabric·whatif·security·risk-calculator 등).

## 시작 방법

### 사전 요구사항

- Java 8 이상 (Spring Boot 2.7.18 / Spring Cloud 2021.0.9)
- Maven 3.9 이상 (또는 mvnw 사용)

### 1. Maven 사용

```bash
cd api-gateway
mvn spring-boot:run
```

### 2. 스크립트 사용

```bash
chmod +x run-gateway.sh
./run-gateway.sh
```

### 3. JAR 빌드 후 실행

```bash
mvn clean package -DskipTests
java -jar target/api-gateway-1.0.0-SNAPSHOT.jar
```

## 헬스 체크

```bash
# 게이트웨이 상태 확인
curl http://localhost:9000/actuator/health

# 라우팅 정보 확인
curl http://localhost:9000/actuator/gateway/routes
```

## CORS 설정

CORS는 **두 곳**에 정의되어 있습니다:

1. **`application.yml` globalcors** — origin을 **패턴**으로 허용: 모든 `http://localhost:[*]` · `http://127.0.0.1:[*]` 포트 + `https://*.ngrok-free.app`. 메서드 GET/POST/PUT/DELETE/PATCH/OPTIONS (HEAD 없음), allowCredentials.
2. **`CorsConfig.java`** — 명시 origin 목록(localhost/127.0.0.1 × 3000~3002, 5173~5175)에 **HEAD** 메서드와 `X-Total-Count` 노출 헤더 추가.

## 프론트엔드 연결

프론트엔드에서는 게이트웨이 주소 하나만 사용하면 됩니다:

### robo-data-frontend

환경 변수 `VITE_API_GATEWAY_URL`을 설정하거나, 기본값 `http://localhost:9000` 사용.

```typescript
// 자동으로 게이트웨이 URL 사용
import { antlrApi, roboApi, text2sqlApi } from '@/services/api'
```

### data-platform-olap/frontend

```javascript
// 자동으로 게이트웨이 URL 사용
import * as api from './services/api'
```

### robo-architect/frontend

`main.js`에서 fetch를 래핑하여 `/api/*` 경로를 자동으로 게이트웨이로 라우팅합니다.

## 환경 변수

### 게이트웨이 서버

| 변수 | 기본값 | 설명 |
|------|--------|------|
| `SERVER_PORT` | 9000 | 게이트웨이 포트 |

### 프론트엔드

| 변수 | 기본값 | 설명 |
|------|--------|------|
| `VITE_API_GATEWAY_URL` | http://localhost:9000 | API 게이트웨이 URL |

## 문제 해결

### CORS 오류

1. 게이트웨이가 실행 중인지 확인
2. 프론트엔드 origin이 `application.yml`의 `allowedOrigins`에 포함되어 있는지 확인
3. 브라우저 캐시 삭제 후 재시도

### 라우팅 실패

1. 대상 백엔드 서비스가 실행 중인지 확인
2. 포트 번호가 올바른지 확인
3. 로그 확인: `curl http://localhost:9000/actuator/health`

### 디버그 로깅

`application.yml`에서 로깅 레벨을 조정할 수 있습니다:

```yaml
logging:
  level:
    org.springframework.cloud.gateway: DEBUG
    reactor.netty: DEBUG
```
