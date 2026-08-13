# Feature Specification: Centralized CORS Management

**Feature Branch**: `002-cors-management`

**Created**: 2026-06-15

**Status**: Backfilled (reverse-engineered)

**Input**: User description: "게이트웨이가 모든 프론트엔드 출처(origin)에 대한 CORS를 중앙에서 관리하여, 개별 백엔드 서비스가 각자 CORS를 처리하지 않도록 한다. 허용 출처, 허용 메서드/헤더, 그리고 라우팅되는 모든 요청에 CORS가 어떻게 적용되는지를 정의한다."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - 프론트엔드에서 게이트웨이 API를 브라우저로 호출 (Priority: P1)

브라우저에서 동작하는 프론트엔드(Vite 5173~5175, 또는 3000번대)가 게이트웨이(`http://localhost:9000`)의 API를 `fetch`/`XHR`로 호출한다. 브라우저는 cross-origin 요청에 대해 CORS 검사를 수행하며, 게이트웨이는 허용된 출처에 대해 적절한 CORS 응답 헤더를 붙여 응답한다.

**Why this priority**: 이 동작이 없으면 모든 브라우저 기반 프론트엔드 호출이 차단되어 제품 전체가 사용 불가능해진다. CORS 중앙화의 핵심 가치(개별 백엔드가 CORS를 신경 쓰지 않아도 됨)가 여기서 실현된다.

**Independent Test**: 허용 출처(예: `http://localhost:5173`)를 `Origin` 헤더로 보내 게이트웨이의 임의 라우트(예: `/api/gateway/robo/...`)를 호출하고, 응답에 `Access-Control-Allow-Origin`이 해당 출처로 반환되는지 확인한다.

**Acceptance Scenarios**:

1. **Given** 출처가 `http://localhost:5173`인 브라우저 요청, **When** 게이트웨이의 라우팅 대상 API를 호출하면, **Then** 응답에 `Access-Control-Allow-Origin: http://localhost:5173`와 `Access-Control-Allow-Credentials: true`가 포함된다.
2. **Given** 임의의 라우트(`/**`), **When** 허용 출처에서 요청하면, **Then** 백엔드 서비스가 별도 CORS 설정을 갖지 않아도 게이트웨이가 CORS 헤더를 일괄 처리한다.

---

### User Story 2 - 브라우저 프리플라이트(OPTIONS) 처리 (Priority: P2)

비단순(non-simple) 요청(커스텀 헤더, PUT/DELETE/PATCH 등) 전에 브라우저가 보내는 프리플라이트 `OPTIONS` 요청을, 게이트웨이가 백엔드까지 전달하지 않고 직접 응답하여 허용 메서드/헤더/자격증명 정책을 알린다.

**Why this priority**: 프리플라이트가 실패하면 본 요청 자체가 전송되지 않는다. P1 동작을 실제로 성립시키는 전제 조건이지만, 단순 GET 요청만으로도 P1의 최소 가치는 확인 가능하므로 P2로 둔다.

**Independent Test**: `Origin`과 `Access-Control-Request-Method: PUT`를 담은 `OPTIONS` 요청을 보내, 게이트웨이가 `Access-Control-Allow-Methods`/`Access-Control-Allow-Headers`/`Access-Control-Max-Age`를 담아 응답하는지 확인한다.

**Acceptance Scenarios**:

1. **Given** 허용 출처의 `OPTIONS` 프리플라이트 요청, **When** 게이트웨이가 받으면, **Then** 백엔드로 전달하지 않고 허용 메서드/헤더와 `Access-Control-Max-Age: 3600`을 담아 응답한다.

---

### Edge Cases

- **프리플라이트 OPTIONS**: `OPTIONS` 메서드가 허용 메서드 목록에 포함되어 있어야 프리플라이트가 정상 응답된다. (CorsConfig에는 OPTIONS 포함, application.yml globalcors에는 OPTIONS 포함 — 아래 불일치 항목 참고)
- **허용되지 않은 출처**: 허용 목록에 없는 출처(예: `https://evil.example.com`)는 `Access-Control-Allow-Origin` 헤더가 부여되지 않아 브라우저가 응답을 차단한다.
- **자격증명(credentials)**: `allowCredentials=true`이므로 `Access-Control-Allow-Origin`은 와일드카드 `*`가 될 수 없고 반드시 구체적인 출처로 echo 되어야 한다. (CorsConfig는 명시적 출처 목록, application.yml은 `allowedOriginPatterns` 사용 — 둘 다 credentials와 호환됨)
- **라우트별 Origin 헤더 제거**: 모든 라우트 필터에 `RemoveRequestHeader=Origin`이 있어, 게이트웨이가 CORS를 처리한 뒤 백엔드로는 `Origin` 헤더를 전달하지 않는다(백엔드 측 CORS 중복/충돌 방지).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: 게이트웨이는 라우팅되는 모든 요청 경로(`/**`)에 대해 CORS 정책을 중앙에서 일괄 적용해야 한다(MUST).
- **FR-002**: 게이트웨이는 허용된 프론트엔드 출처에 대해서만 `Access-Control-Allow-Origin`을 응답해야 한다(MUST). CorsConfig.java 기준 허용 출처는 `http://localhost:3000/3001/3002/5173/5174/5175` 및 동일 포트의 `http://127.0.0.1:*`이다.
- **FR-003**: 게이트웨이는 `GET, POST, PUT, DELETE, PATCH, OPTIONS, HEAD` 메서드를 허용해야 한다(MUST, CorsConfig.java 기준).
- **FR-004**: 게이트웨이는 모든 요청 헤더(`*`)를 허용해야 한다(MUST).
- **FR-005**: 게이트웨이는 `Content-Disposition`, `Content-Type`, `X-Total-Count` 헤더를 브라우저에 노출(expose)해야 한다(MUST).
- **FR-006**: 게이트웨이는 자격증명(쿠키/인증헤더) 전송을 허용해야 한다(`allowCredentials=true`, MUST).
- **FR-007**: 게이트웨이는 프리플라이트 결과를 `3600`초 동안 캐시하도록 `Access-Control-Max-Age`를 응답해야 한다(MUST).
- **FR-008**: 게이트웨이는 CORS 처리 후 백엔드로 전달되는 요청에서 `Origin` 헤더를 제거해야 한다(MUST, 모든 라우트의 `RemoveRequestHeader=Origin` 필터).
- **FR-009**: 개별 백엔드 서비스는 자체 CORS 설정을 두지 않아도 동작해야 한다(SHOULD — CORS는 게이트웨이 단일 책임).
- **FR-010**: [NEEDS CLARIFICATION] CorsConfig.java의 `CorsWebFilter`(Java Bean)와 application.yml의 `spring.cloud.gateway.globalcors`(설정 기반) 두 CORS 정의가 공존한다. 운영 시 어느 쪽이 실효(effective)인지 단일화가 필요하다. 일반적으로 명시적 `CorsWebFilter` Bean이 globalcors보다 우선 적용되므로, CorsConfig.java의 출처 목록이 실제 계약일 가능성이 높다.

### Key Entities *(include if feature involves data)*

- **Allowed Origins (허용 출처 목록)**:
  - CorsConfig.java(명시적 목록): `http://localhost:3000`, `3001`, `3002`, `5173`, `5174`, `5175` + `http://127.0.0.1:` 동일 6개 포트 = 총 12개.
  - application.yml globalcors(패턴): `http://localhost:[*]`, `http://127.0.0.1:[*]`, `https://*.ngrok-free.app`.
- **Allowed Methods (허용 메서드)**: CorsConfig.java = `GET, POST, PUT, DELETE, PATCH, OPTIONS, HEAD`(7개). application.yml = `GET, POST, PUT, DELETE, PATCH, OPTIONS`(6개, **HEAD 없음**).
- **Allowed Headers (허용 헤더)**: 양쪽 모두 `*`(전체 허용).
- **Exposed Headers (노출 헤더)**: CorsConfig.java = `Content-Disposition, Content-Type, X-Total-Count`(3개). application.yml = `Content-Disposition, Content-Type`(2개, **X-Total-Count 없음**).
- **Credentials Flag (자격증명 허용)**: 양쪽 모두 `allowCredentials=true`.
- **Max Age**: 양쪽 모두 `3600`초.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 허용 출처 12개(또는 패턴 일치 출처) 전부에서 브라우저 API 호출이 CORS 오류 없이 성공한다.
- **SC-002**: 허용되지 않은 출처의 요청은 100% 브라우저에서 차단된다(`Access-Control-Allow-Origin` 미부여).
- **SC-003**: 프리플라이트 `OPTIONS` 요청은 백엔드로 전달되지 않고 게이트웨이에서 직접 응답된다.
- **SC-004**: 백엔드 서비스가 자체 CORS 코드를 갖지 않아도 프론트엔드 호출이 정상 동작한다(CORS 중복 설정으로 인한 헤더 충돌 0건).

## Assumptions

- 프론트엔드는 브라우저 기반이며 게이트웨이(`http://localhost:9000`, port 9000)를 통해 백엔드 API를 호출한다고 가정한다.
- 로컬/개발 환경 기준 출처(localhost·127.0.0.1)가 주 대상이며, ngrok 터널(`https://*.ngrok-free.app`)은 application.yml 패턴에만 존재한다(CorsConfig.java에는 없음).
- application-docker.yml에는 별도 CORS 설정 블록이 없으므로, Docker 프로파일에서도 CorsConfig.java Bean 또는 base application.yml의 globalcors가 그대로 적용된다고 가정한다.
- `RemoveRequestHeader=Origin`을 모든 라우트에 적용함으로써 백엔드가 CORS를 처리하지 않는다는 전제가 성립한다고 가정한다.

## ⚠️ README/설정 간 불일치 (Backfill 검증 결과)

1. **포트 범위**: 요청(및 README)은 "3000/5173/5174/5175"라 하나, **실제 CorsConfig.java는 3000·3001·3002·5173·5174·5175 + 127.0.0.1 동일 포트(총 12개)**로 더 넓다. application.yml은 `localhost:[*]`/`127.0.0.1:[*]` 와일드카드로 모든 포트를 허용한다.
2. **CorsConfig.java vs application.yml globalcors 중복 정의**: 두 곳에 서로 다른 CORS 정의가 존재. 메서드(HEAD 유무), 노출 헤더(X-Total-Count 유무), 출처 표현(명시 목록 vs 패턴+ngrok)이 불일치. 실효 정책 단일화 필요(FR-010).
3. **ngrok 출처**: application.yml에만 `https://*.ngrok-free.app` 존재, CorsConfig.java에는 없음.
