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
 │  (8081)  │         │  (5502)  │         │  (8000)  │         │  (8002)  │         │  (8001)  │
 └──────────┘         └──────────┘         └──────────┘         └──────────┘         └──────────┘
   Java/Spring          Python/FastAPI      Python/FastAPI      Python/FastAPI      Python/FastAPI
```

## 라우팅 설정

| 경로 패턴 | 대상 서비스 | 포트 | 설명 |
|-----------|-------------|------|------|
| `/antlr/**` | ANTLR Parser | 8081 | 소스코드 파싱 (Java/Spring Boot) |
| `/robo/**` | ROBO Analyzer | 5502 | 레거시 코드 분석 |
| `/text2sql/**` | Text2SQL | 8000 | 자연어 → SQL 변환 |
| `/olap/**` | Data Platform OLAP | 8002 | ETL/OLAP 서비스 |
| `/architect/**` | ROBO Architect | 8001 | 아키텍처 분석 |
| `/langchain/**` | LangChain | 8001 | LangChain ReAct 에이전트 |

## 시작 방법

### 사전 요구사항

- Java 17 이상
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

모든 프론트엔드 포트(3000, 5173, 5174, 5175)에서 접근 가능하도록 설정되어 있습니다.

지원되는 메서드:
- GET, POST, PUT, DELETE, PATCH, OPTIONS, HEAD

## 프론트엔드 연결

프론트엔드에서는 게이트웨이 주소 하나만 사용하면 됩니다:

### robo-analyzer-vue3

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
