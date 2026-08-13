# Feature Specification: Service Routing

**Feature Branch**: `001-service-routing`

**Created**: 2026-06-15

**Status**: Backfilled (reverse-engineered)

**Input**: 기존 api-gateway(Spring Cloud Gateway, Java 17, 포트 9000)의 라우트 테이블을 실제 코드/설정(`application.yml`, `application-docker.yml`, `ApiGatewayApplication.java`)에서 역공학하여 작성한 명세. 경로 패턴을 백엔드 마이크로서비스로 매핑하고, actuator를 통해 라우트를 조회한다.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - 단일 엔드포인트로 모든 백엔드 호출 (Priority: P1)

프론트엔드(robo-data-frontend 등)는 백엔드 서비스의 개별 포트를 알 필요 없이, 게이트웨이 주소(`http://localhost:9000`) 하나만 사용한다. 경로 접두사(`/antlr/**`, `/robo/**`, `/text2sql/**` 등)에 따라 게이트웨이가 알맞은 백엔드로 프록시한다.

**Why this priority**: 게이트웨이의 존재 이유 그 자체. 이 매핑이 없으면 어떤 마이크로서비스도 통합 진입점을 통해 호출할 수 없다.

**Independent Test**: 게이트웨이만 띄우고 각 경로 접두사로 요청을 보내, 해당 백엔드 포트로 프록시되는지(또는 백엔드 미기동 시 502) 확인하면 검증 가능하다.

**Acceptance Scenarios**:

1. **Given** 게이트웨이가 9000에서 기동, **When** `GET /antlr/health` 요청, **Then** `127.0.0.1:8081`(antlr-service)로 경로 변형 없이 프록시된다.
2. **Given** 게이트웨이 기동, **When** `POST /robo/analyze/run` 요청, **Then** `127.0.0.1:5502`(robo-analyzer-service)로 프록시된다.
3. **Given** 게이트웨이 기동, **When** `GET /text2sql/ask` 요청, **Then** `127.0.0.1:8000`(text2sql-service)로 프록시된다.

### User Story 2 - 미일치 요청의 프론트엔드 폴백 (Priority: P2)

백엔드 접두사에 해당하지 않는 모든 경로(UI 라우트, 정적 자산 등)는 프론트엔드 개발 서버로 폴백 라우팅된다.

**Why this priority**: 사용자가 게이트웨이 한 주소로 SPA와 API를 동시에 쓸 수 있게 한다. 단, 백엔드 라우팅(P1)이 먼저 성립해야 의미가 있다.

**Independent Test**: 정의된 접두사가 아닌 임의 경로(`/`, `/dashboard`)를 요청해 프론트엔드(`localhost:3000`)로 가는지 확인한다.

**Acceptance Scenarios**:

1. **Given** 게이트웨이 기동, **When** `GET /dashboard` 요청, **Then** `/**` 폴백 라우트가 매칭되어 `localhost:3000`(frontend)으로 프록시된다.

### User Story 3 - 라우트 조회/헬스 점검 (Priority: P3)

운영자/개발자는 actuator 엔드포인트로 현재 활성 라우트 테이블과 게이트웨이 상태를 조회한다.

**Why this priority**: 라우팅 자체에는 필수가 아니지만, 장애 진단과 라우트 검증에 필요한 운영 기능.

**Independent Test**: `/actuator/gateway/routes`와 `/actuator/health`를 호출해 라우트 목록·상태가 반환되는지 확인한다.

**Acceptance Scenarios**:

1. **Given** 게이트웨이 기동, **When** `GET /actuator/gateway/routes` 요청, **Then** 정의된 모든 라우트의 id·predicate·uri가 JSON으로 반환된다.
2. **Given** 게이트웨이 기동, **When** `GET /actuator/health` 요청, **Then** `show-details: always` 설정에 따라 상세 상태가 반환된다.

### Edge Cases

- **경로 중첩/순서**: `/robo/analyze/**`·`/robo/pipeline/**`(5502), `/robo/glossary/**`·`/robo/business-calendar/**`(5503), `/robo/**`(5504 catch-all)이 겹친다. 구체적 경로 라우트가 catch-all보다 **먼저 선언**되어야 의도대로 매칭된다(Spring Cloud Gateway는 선언 순서대로 평가).
- **폴백 위치**: `/**`(frontend)는 모든 경로를 잡으므로 반드시 **맨 마지막**에 선언되어야 한다. 그렇지 않으면 모든 요청을 가로챈다.
- **포트 충돌**: `8001`이 `architect`·`langchain` 두 서비스에 공유된다(접두사로만 구분). `8002`도 `ontology`/`domain-whatif`가 공유.
- **백엔드 다운**: 대상 백엔드 미기동 시 connect-timeout(5000ms) 후 502/503. ontology·domain-whatif는 response-timeout 600000ms로 장시간 작업 허용.
- **대용량 요청**: PDF 온톨로지 base64 본문을 위해 `max-in-memory-size: 1024MB` 설정.
- **프론트엔드 바인딩**: Vite가 IPv6(::1)로 바인딩하므로 frontend 라우트 uri는 `127.0.0.1`이 아닌 `localhost`를 사용.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: 게이트웨이는 포트 **9000**에서 수신해야 한다.
- **FR-002**: 게이트웨이는 요청 경로 접두사를 `application.yml`에 정의된 백엔드 서비스로 프록시해야 한다(아래 Key Entities 라우트 표가 계약).
- **FR-003**: 라우트는 **선언 순서대로** 평가되며, 구체적 경로가 catch-all보다 앞서고, `/**` 프론트엔드 폴백이 마지막이어야 한다.
- **FR-004**: `/api/gateway/**` 접두사 라우트는 `RewritePath`로 게이트웨이 접두사를 제거한 뒤 백엔드 경로로 변환해야 한다.
- **FR-005**: 모든 라우트는 `RemoveRequestHeader=Origin` 필터를 적용해야 한다(백엔드 CORS 충돌 방지).
- **FR-006**: 게이트웨이는 글로벌 CORS를 적용해야 한다(localhost/127.0.0.1 임의 포트 및 ngrok 패턴 허용, credentials 허용).
- **FR-007**: 게이트웨이는 actuator로 `health`·`info`·`gateway` 엔드포인트를 노출하고, `/actuator/gateway/routes`로 라우트 조회를 제공해야 한다.
- **FR-008**: 미일치 요청은 `/**` 폴백 라우트를 통해 프론트엔드로 라우팅해야 한다.
- **FR-009**: connect-timeout 5000ms, 기본 response-timeout 30s를 적용하되, 장시간 라우트(ontology/domain-whatif)는 메타데이터로 600000ms를 적용해야 한다.

### Key Entities *(include if feature involves data)*

- **Route**: 하나의 라우팅 규칙. 속성 = `{ id, path predicate(들), target uri/port, filters(RewritePath/RemoveRequestHeader), [metadata timeout] }`.
- **Route Table (실제, `application.yml` 로컬 프로파일 — 계약의 원천)**:

  Direct 라우트 (경로 변형 없음 또는 단순):

  | 경로 패턴 | 라우트 id | 대상 |
  |-----------|-----------|------|
  | `/antlr/**` | antlr-service | 127.0.0.1:8081 |
  | `/robo/analyze/**`, `/robo/pipeline/**` | robo-analyzer-service | 127.0.0.1:5502 |
  | `/robo/glossary/**`, `/robo/business-calendar/**` | robo-catalog-service | 127.0.0.1:5503 |
  | `/robo/**` (catch-all) | robo-glossary-service | 127.0.0.1:5504 |
  | `/text2sql/**` | text2sql-service | 127.0.0.1:8000 |
  | `/olap/**` → `/$\{seg}` | olap-service | 127.0.0.1:8007 |
  | `/architect/**` → `/$\{seg}` | architect-service | 127.0.0.1:8001 |
  | `/langchain/**` → `/$\{seg}` | langchain-service | 127.0.0.1:8001 |
  | `/agent-scheduler/**` → `/$\{seg}` | agent-scheduler-service | 127.0.0.1:8089 |
  | `/node-agent-scheduler/**` → `/$\{seg}` | node-agent-scheduler-service | 127.0.0.1:8091 |
  | `/ontology/**` | ontology-service | 127.0.0.1:8002 |
  | `/risk-calculator/**` → `/$\{seg}` | risk-calculator-service | 127.0.0.1:8003 |
  | `/data-fabric/**` → `/$\{seg}` | data-fabric-service | 127.0.0.1:8004 |
  | `/whatif/**` → `/api/$\{seg}` | whatif-service | 127.0.0.1:8005 |
  | `/api/ontology/**` → `/ontology/$\{seg}` | ontology-api-direct | 127.0.0.1:8002 |
  | `/api/security/**` | security-api-direct | 127.0.0.1:8006 |
  | `/**` (fallback, **마지막**) | frontend | localhost:3000 |

  `/api/gateway/**` 접두사 라우트 (RewritePath로 접두사 제거):

  | 경로 패턴 | 라우트 id | 대상 |
  |-----------|-----------|------|
  | `/api/gateway/antlr/**` → `/antlr/..` | api-gateway-antlr | 127.0.0.1:8081 |
  | `/api/gateway/robo/analyze/**`,`/pipeline/**` → `/robo/..` | api-gateway-robo-analyze | 127.0.0.1:5502 |
  | `/api/gateway/robo/**` → `/robo/..` | api-gateway-robo-catalog | 127.0.0.1:5503 |
  | `/api/gateway/text2sql/**` | api-gateway-text2sql | 127.0.0.1:8000 |
  | `/api/gateway/olap/**` | api-gateway-olap | 127.0.0.1:8007 |
  | `/api/gateway/architect/**` | api-gateway-architect | 127.0.0.1:8001 |
  | `/api/gateway/langchain/**` | api-gateway-langchain | 127.0.0.1:8001 |
  | `/api/gateway/agent-scheduler/**` | api-gateway-agent-scheduler | 127.0.0.1:8089 |
  | `/api/gateway/node-agent-scheduler/**` | api-gateway-node-agent-scheduler | 127.0.0.1:8091 |
  | `/api/gateway/ontology/**` → `/ontology/..` | api-gateway-ontology | 127.0.0.1:8002 |
  | `/api/gateway/domain-whatif/**` → `/whatif/..` | api-gateway-domain-whatif | 127.0.0.1:8002 |
  | `/api/gateway/data-fabric/**` | api-gateway-data-fabric | 127.0.0.1:8004 |
  | `/api/gateway/whatif/**` → `/api/..` | api-gateway-whatif | 127.0.0.1:8005 |
  | `/api/gateway/security/**` → `/api/security/..` | api-gateway-security | 127.0.0.1:8006 |
  | `/api/gateway/risk-calculator/**` | api-gateway-risk-calculator | 127.0.0.1:8003 |

- **Actuator 엔드포인트**: `/actuator/health`(show-details: always), `/actuator/info`, `/actuator/gateway/routes`(라우트 introspection).
- **Docker 프로파일 차이(`application-docker.yml`)**: uri가 `127.0.0.1:port` 대신 컨테이너 이름(예: `robo-antlr-parser:8081`, `robo-analyzer:5502`, `robo-frontend:80`)을 사용하고, 라우트 집합이 더 적다(아래 불일치 참조).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 정의된 모든 경로 접두사 요청 중 100%가 의도한 백엔드 포트로 프록시된다(catch-all/폴백 오매칭 0건).
- **SC-002**: 백엔드 미일치 요청은 100% 프론트엔드(`/**`)로 폴백된다.
- **SC-003**: `/actuator/gateway/routes`가 위 표의 모든 라우트 id를 반환한다.
- **SC-004**: 백엔드 다운 시, 게이트웨이는 connect-timeout(5s) 내에 오류를 반환하며 무한 대기하지 않는다.
- **SC-005**: 허용된 origin의 CORS 프리플라이트(OPTIONS)가 모두 통과한다.

## Assumptions

- 본 명세는 **로컬 `application.yml`을 계약의 원천**으로 삼는다. README 라우팅 표와 docker 프로파일은 부분집합/구버전일 수 있다(아래 불일치 참조).
- 각 백엔드는 명세된 포트에서 별도로 기동되어 있다고 가정한다(게이트웨이는 헬스 체크 후 라우팅하지 않으며 단순 프록시).
- Spring Cloud Gateway가 라우트를 **선언 순서**대로 평가한다는 전제에 의존한다.
- 인증/인가는 본 라우팅 기능의 범위 밖이다(게이트웨이는 라우팅·CORS·헤더 정리만 담당).
- frontend 폴백 대상(`localhost:3000`)은 로컬에서 Vite 개발 서버, docker에서는 Nginx(`robo-frontend:80`)임을 가정한다.

## README ↔ application.yml 불일치 (역공학 시 발견)

- **OLAP 포트 불일치**: README는 `/olap/**` → **8002**라고 기재하나, `application.yml`의 olap-service는 **8007**이다(8002는 ontology/domain-layer). README가 stale.
- **README에 누락된 라우트 다수**: `application.yml`에만 존재하고 README 표에 없는 서비스 — risk-calculator(8003), data-fabric(8004), whatif(8005), security(8006), agent-scheduler(8089), node-agent-scheduler(8091), ontology(8002), 및 전체 `/api/gateway/**` 접두사 라우트군, `/api/ontology/**`·`/api/security/**` direct 라우트.
- **docker 프로파일 불일치**: `application-docker.yml`에는 `/robo/**`가 단일 라우트로 **전부 robo-analyzer(5502)** 로 가며, 로컬의 5502/5503/5504 3분할(analyze·pipeline / glossary·business-calendar / catch-all)이 없다. 또한 olap·architect·langchain·whatif·risk-calculator·node-agent-scheduler·domain-whatif 라우트가 docker에는 부재. 반대로 docker에만 있는 라우트: `/api/datasources/**` → data-fabric(8004)(로컬엔 없음). frontend 대상도 다름(local `localhost:3000` vs docker `robo-frontend:80`).
- **CORS 정의 이원화**: `application.yml`의 globalcors(allowedOriginPatterns: localhost/127.0.0.1 임의 포트 + ngrok)와 `CorsConfig.java`의 CorsWebFilter(allowedOrigins: 3000–3002·5173–5175 고정 목록 + HEAD 메서드)가 **동시에 존재**하며 origin 목록·메서드 집합이 일치하지 않는다.
