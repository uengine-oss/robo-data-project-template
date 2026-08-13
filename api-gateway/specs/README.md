# Specifications — API Gateway

> **Backfilled** on 2026-06-15 by reverse-engineering the existing configuration using the
> [GitHub Spec Kit](https://github.com/github/spec-kit) format. Each `spec.md` was derived from
> the actual `application.yml` / `application-docker.yml` / `CorsConfig.java` — **not** from a
> prior design doc. The README routing/CORS tables were found to be substantially stale; specs
> follow the **config** (see "Discrepancies" below).

## What this is

api-gateway (Spring Cloud Gateway, Java 17) is the single front door (port 9000) that routes path
patterns to all robo microservices and centralizes CORS. It is **entirely config-driven** —
`ApiGatewayApplication` is a bare main class.

## How to use these specs

- **Change planning**: edit the relevant `spec.md` first, then `application.yml`. Evaluate every
  change against **both** the local and docker profiles.
- **New features**: `/speckit-specify → /speckit-plan → /speckit-tasks → /speckit-implement`.
  The constitution at [`.specify/memory/constitution.md`](../.specify/memory/constitution.md)
  states the 4 principles every new plan's Constitution Check must satisfy.

## Feature index

| # | Spec | One-liner |
|---|------|-----------|
| 001 | [Service Routing](001-service-routing/spec.md) | path-pattern → service:port route table; `/api/gateway/**` rewrite set; actuator introspection |
| 002 | [Centralized CORS Management](002-cors-management/spec.md) | allowed origins/methods for all frontends; backends strip `Origin` |

## Cross-service contract

The **routing table IS the contract** with every other service — each `path-pattern → service:port`
mapping is a boundary. Changing a backend's port or path prefix ripples here. The route list is
the platform's single registry of "what runs where".

## Discrepancies corrected against config (notable — README was stale)

Specs follow the **config**, not the README:

- **001** — README says `/olap/**` → **8002**, but config routes it to **8007** (8002 is ontology).
  README's routing table is **missing many live routes**: risk-calculator (8003), data-fabric
  (8004), whatif (8005), security (8006), agent-scheduler (8089), node-agent-scheduler (8091),
  ontology (8002), and the entire parallel **`/api/gateway/**`** (RewritePath-stripped) set.
  `application-docker.yml` collapses all `/robo/**` to the analyzer (5502) and targets
  `robo-frontend:80` instead of `localhost:3000`.
- **002** — README claims 4 origins (`3000/5173/5174/5175`); `CorsConfig.java` actually allows
  **12** (`localhost` + `127.0.0.1` × ports `3000-3002, 5173-5175`), while `application.yml`
  `globalcors` allows **any port** via `[*]` plus `*.ngrok-free.app`. CORS is **defined twice**
  (Java bean vs globalcors) with mismatched method sets (HEAD) and exposed headers
  (`X-Total-Count`) — flagged as debt to consolidate.

Specs are intentionally short (~120-150 lines each) — they describe the contract, not the config.
