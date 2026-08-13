# API Gateway Constitution

<!--
  Principles the api-gateway codebase ALREADY embodies, derived 2026-06-15 by reverse-engineering
  the configuration. Every new spec/plan's "Constitution Check" must comply. Amending a principle
  requires bumping the version below with a rationale.
-->

## Core Principles

### I. Config-Driven Routing (코드 0, 설정으로)

All routes live in `application.yml` (and `application-docker.yml`); `ApiGatewayApplication` is a
bare `@SpringBootApplication` with **no programmatic routes**. Adding or changing a route MUST be
a YAML edit, never Java code.

**Rationale**: routing is operational config, not logic — keeping it declarative makes the route
table reviewable and avoids redeploying logic for a port change.

### II. Single Front Door (단일 진입점)

Every backend service is reachable through one endpoint (port 9000). Clients use one base URL and
never address service ports directly.

**Rationale**: one origin to configure, one place to manage CORS/observability, no client churn
when a backend moves.

### III. Centralized CORS (CORS 일원화)

The gateway owns CORS for all routed traffic; backends do not each implement it (routes carry
`RemoveRequestHeader=Origin` so backends don't double-handle it). CORS MUST be defined in exactly
one place.

**Rationale**: scattered CORS rules drift and cause hard-to-debug preflight failures.
⚠️ *Current debt*: CORS is defined twice (a `CorsWebFilter` bean in `CorsConfig.java` **and**
`spring.cloud.gateway.globalcors` in `application.yml`) with mismatched origins/methods — a new
plan touching CORS MUST consolidate to a single source (see spec 002).

### IV. Profile Separation, Kept Honest (프로파일 분리)

`application.yml` (local) and `application-docker.yml` (container) intentionally differ (frontend
target, route subset). Any route/CORS change MUST be evaluated against BOTH profiles, not just one.

**Rationale**: a route that works locally but is absent in the docker profile is a silent
production gap.

## Cross-Service Contracts

The gateway's **routing table IS its contract** with every other service: each `path-pattern →
service:port` mapping is a boundary. Changing a backend's port, path prefix, or adding a service
ripples here. The route list is the single registry of "what runs where" for the whole platform.

Downstream consumers: all robo services (antlr 8081, analyzer 5502, catalog 5503, architect 8001,
text2sql 8000, …) and all frontends (via the `/**` fallback). Keep ports in sync with each
service's own config.

## Governance

New features go through `/speckit-specify → /speckit-plan`; each `plan.md` MUST include a
Constitution Check verifying the principles above. A principle is amended only by editing this
file and bumping the version, with the rationale recorded.

**Version**: 1.0.0 | **Ratified**: 2026-06-15 | **Last Amended**: 2026-06-15
