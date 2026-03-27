---
name: domain-layer
description: "Use this agent when working on domain layer microservice architecture, ontology management, domain modeling, or when you need expertise in designing and implementing domain-driven design patterns within microservice boundaries. This includes ontology definition, domain entity relationships, bounded context design, and domain event management.\\n\\nExamples:\\n\\n<example>\\nContext: The user is designing a new domain entity and needs ontology expertise.\\nuser: \"새로운 Product 도메인 엔티티를 설계해야 합니다. 관련 온톨로지를 정의해주세요.\"\\nassistant: \"도메인 레이어 전문 에이전트를 사용하여 Product 엔티티의 온톨로지를 설계하겠습니다.\"\\n<commentary>\\nSince the user needs domain entity ontology design, use the Agent tool to launch the domain-layer agent to provide expert guidance on ontology definition and domain modeling.\\n</commentary>\\n</example>\\n\\n<example>\\nContext: The user is refactoring microservice boundaries and needs domain layer expertise.\\nuser: \"주문 서비스와 결제 서비스 간의 바운디드 컨텍스트를 재설계해야 합니다.\"\\nassistant: \"도메인 레이어 에이전트를 활용하여 바운디드 컨텍스트 경계를 분석하고 재설계하겠습니다.\"\\n<commentary>\\nSince the user is working on bounded context redesign between microservices, use the Agent tool to launch the domain-layer agent to analyze domain boundaries and provide expert recommendations.\\n</commentary>\\n</example>\\n\\n<example>\\nContext: The user is implementing domain events and needs ontology-aware event design.\\nuser: \"도메인 이벤트를 설계할 때 온톨로지 관계를 어떻게 반영해야 할까요?\"\\nassistant: \"도메인 레이어 에이전트를 통해 온톨로지 기반 도메인 이벤트 설계를 진행하겠습니다.\"\\n<commentary>\\nSince the user needs ontology-aware domain event design, use the Agent tool to launch the domain-layer agent to provide expertise on ontology-driven event modeling.\\n</commentary>\\n</example>\\n\\n<example>\\nContext: The user has written new domain layer code and needs it reviewed for DDD compliance.\\nuser: \"이 Aggregate Root 구현을 리뷰해주세요.\"\\nassistant: \"도메인 레이어 에이전트를 사용하여 Aggregate Root 구현이 DDD 원칙과 온톨로지 정합성에 부합하는지 검토하겠습니다.\"\\n<commentary>\\nSince the user wants a domain layer code review, use the Agent tool to launch the domain-layer agent to review the implementation against DDD principles and ontology consistency.\\n</commentary>\\n</example>"
model: opus
color: yellow
memory: project
---

# Domain Layer — Agent Overview

## 프로젝트 개요

이 시스템은 **도메인 레이어(Domain Layer) 기반 온톨로지 관리 플랫폼**입니다.
비즈니스 도메인의 KPI·프로세스·자원 개념을 계층적 온톨로지로 모델링하고, 실제 데이터 소스와 연결하여 인과 분석까지 수행하는 풀스택 애플리케이션입니다.

---

## 아키텍처 개요

```
[Vue 3 프론트엔드]
       │
       ▼
[API Gateway]  /api/gateway/*
       ├── /ontology/*   → Ontology 마이크로서비스
       └── /text2sql/*   → Text2SQL 마이크로서비스
```

모든 API 통신은 `/api/gateway/` 프리픽스를 통해 단일 게이트웨이로 라우팅됩니다.

---

## 백엔드 마이크로서비스

### 1. Ontology 서비스 (`/api/gateway/ontology/`)

온톨로지 스키마의 생성·저장·조회·분석을 담당합니다.

| 엔드포인트 | 메서드 | 설명 |
|---|---|---|
| `/ontology/generate-multi-layer` | POST (Streaming) | 문서/PDF/URL로부터 멀티레이어 온톨로지 자동 생성 (NDJSON 스트리밍) |
| `/ontology/schemas` | GET | 저장된 온톨로지 스키마 목록 조회 |
| `/ontology/schemas` | POST | 온톨로지 스키마 저장 (Neo4j) |
| `/ontology/schemas/{id}` | GET | 특정 스키마 조회 |
| `/ontology/schemas/{id}` | DELETE | 스키마 삭제 |
| `/ontology/schemas/{id}/activate` | POST | 스키마 활성화 |
| `/ontology/schemas/{id}/nodes/{nodeId}/incoming-network` | POST | 노드의 인과 상위 네트워크 조회 (최대 depth 지원) |
| `/ontology/schemas/{id}/nodes/{nodeId}/causal-analysis/stream` | POST (Streaming) | 특정 노드 시간 구간의 원인 분석 실행 (NDJSON 스트리밍) |
| `/ontology/schemas/{id}/nodes/{nodeId}/causal-analysis` | POST | 원인 분석 (비스트리밍 폴백) |
| `/ontology/ontology-nodes/{nodeId}/data` | GET | 노드에 연결된 데이터 소스의 실제 데이터 조회 |
| `/ontology/ontology-nodes/{nodeId}/create-objecttype` | POST | Measure 노드용 ObjectType 생성 |
| `/ontology/auto-link-datasource/stream` | POST (Streaming) | 전체 노드에 대한 데이터 소스 자동 연결 (Text2SQL 에이전트, 스트리밍) |
| `/ontology/auto-link-datasource` | POST | 데이터 소스 자동 연결 (비스트리밍 폴백) |
| `/ontology/confirm-datasource` | POST | 데이터 소스 매핑 확정 |
| `/ontology/node/{nodeId}/sample-data` | GET | 노드 데이터 소스 샘플 데이터 조회 |
| `/ontology/schema` | POST | 스키마 저장 (구형 엔드포인트) |

**스트리밍 응답 포맷 (NDJSON):**
- 온톨로지 생성 이벤트: `start`, `layer_progress`, `layer_complete`, `needs_info`, `web_search`, `web_search_complete`, `complete`
- 원인 분석 이벤트: `progress` (step: `report_chunk` 등), `result`

### 2. Text2SQL 서비스 (`/api/gateway/text2sql/`)

자연어 질의를 SQL로 변환하고 데이터 메타 정보를 제공합니다.

| 엔드포인트 | 메서드 | 설명 |
|---|---|---|
| `/text2sql/ask` | POST (Streaming) | 자연어 질의 → SQL 변환 및 실행 (스트리밍 대화) |
| `/text2sql/direct-sql` | POST | SQL 직접 실행 |
| `/text2sql/meta/datasources` | GET | 연결된 데이터소스 목록 |
| `/text2sql/meta/datasources/{ds}/schemas` | GET | 특정 데이터소스의 스키마 목록 |
| `/text2sql/meta/datasources/{ds}/schemas/{schema}/tables` | GET | 테이블 목록 (최대 500개) |
| `/text2sql/meta/tables/{table}/columns` | GET | 테이블 컬럼 정보 |
| `/text2sql/meta/objecttypes` | GET | ObjectType 목록 |

---

## 프론트엔드 구조

### 기술 스택

- **Vue 3** (Composition API, TypeScript)
- **Cytoscape.js** — 온톨로지 그래프 시각화 (edgehandles 플러그인 포함)
- **Apache ECharts** — 시계열·막대 차트
- **NDJSON 스트리밍** — `ReadableStream` + `TextDecoder`로 실시간 처리

### 주요 컴포넌트

| 컴포넌트 | 경로 | 역할 |
|---|---|---|
| `MultiLayerOntologyViewer.vue` | `@/components/` | 메인 온톨로지 편집기 (핵심 컴포넌트) |
| `CausalAnalysisPanel.vue` | `@/components/domain/` | 원인 분석 결과 패널 |
| `SchemaBasedGenerator.vue` | `@/components/ontology/` | DB 스키마 기반 온톨로지 생성 UI |
| `LineChart.vue` | `@/components/charts/` | 시계열 라인 차트 |

### 데이터 모델

```typescript
interface OntologyNode {
  id: string
  name: string
  label: string           // 레이어 ID (KPI, Measure, Process, Driver, Resource)
  layer?: string
  description?: string
  unit?: string
  formula?: string
  targetValue?: number
  dataSource?: string     // 연결된 DB 테이블 or ObjectType
  filterFields?: FilterField[]
  position?: { x: number; y: number }
}

interface OntologyRelationship {
  id: string
  source: string
  target: string
  type: string            // CAUSES, MEASURED_AS, PRODUCES, INFLUENCES, EXECUTES, ...
  weight?: number
  lag?: number
}
```

---

## 도메인 레이어 구조 (5계층)

온톨로지는 다음 5개 레이어로 구성되며, 상위 레이어가 비즈니스 목표, 하위 레이어가 자원을 나타냅니다.

| 레이어 | 아이콘 | 색상 | 설명 |
|---|---|---|---|
| **KPI** | 📊 | Red (#ef4444) | 핵심 성과 지표 (최상위) |
| **Measure** | 📏 | Orange (#f97316) | KPI를 구성하는 측정치 |
| **Process** | ⚙️ | Green (#22c55e) | Measure를 생산하는 프로세스 |
| **Driver** | 🔧 | Yellow (#eab308) | Process에 영향을 주는 드라이버 |
| **Resource** | 💾 | Blue (#3b82f6) | 최하위 자원 (데이터, 시스템 등) |

### 관계 타입 (Relationship Types)

`CAUSES`, `MEASURED_AS`, `PRODUCES`, `INFLUENCES`, `EXECUTES`, `USED_WHEN`, `NEXT`, `TRIGGERS`, `EFFECTS`, `AFFECTS`, `FOLLOWS`, `PRECEDES` 및 역방향 타입 전부 지원.

---

## 주요 기능 목록

### 온톨로지 편집
- **노드 추가**: 상단 툴바 버튼 또는 캔버스 우클릭 컨텍스트 메뉴로 스테레오타입(레이어) 선택 후 생성
- **관계 추가**: 노드 드래그 핸들(edgehandles)을 이용한 엣지 연결, 관계 타입 선택 다이얼로그
- **노드/관계 삭제**: 컨텍스트 메뉴 또는 상세 패널에서 삭제
- **Undo/Redo**: 최대 50단계 히스토리 지원 (Ctrl+Z / Ctrl+Y)
- **레이아웃 전환**: Hierarchical, Cose(물리 기반), Circle, Grid
- **이미지 내보내기**: 그래프 스냅샷 PNG 저장

### 온톨로지 자동 생성
- **문서 기반**: 텍스트 입력 / PDF 업로드 / URL 입력 → LLM 에이전트가 레이어별 노드 자동 추출
- **DB 스키마 기반**: 연결된 데이터베이스 스키마 분석 → 온톨로지 자동 생성
- **Human-in-the-Loop**: 추출 중 정보 부족 시 사용자에게 질문, 건너뛰기 또는 Tavily 웹 검색으로 보완
- **병렬 추출**: 레이어별 병렬 처리 옵션
- 생성 완료 후 Neo4j에 자동 저장

### 온톨로지 관리
- 저장된 온톨로지 목록 드롭다운에서 로드/삭제/이름 편집
- 스키마 이름 자동 생성 (도메인 힌트 + 노드 구성 기반)

### 데이터 소스 연결
- **자동 연결**: Text2SQL 에이전트가 전체 노드를 순서대로 스캔하며 후보 테이블 추천 (스트리밍 진행 표시)
- **개별 연결**: 노드 선택 → 상세 패널에서 AI 검색 또는 수동 테이블 선택
- **ObjectType 연결**: Palantir 스타일의 ObjectType(Materialized View) 지원
- 연결 확정 후 데이터 소스 정보 저장 및 즉시 미리보기 가능

### 데이터 조회 및 시각화 (노드 상세 패널 - 데이터 탭)
- 연결된 데이터 소스의 실제 데이터를 최대 50행 테이블로 표시
- 시계열 컬럼 감지 시 ECharts 라인/막대 차트 자동 렌더링
- 필터 바: 날짜 범위, 카테고리, 숫자 범위, 텍스트 검색 필터 지원

### 원인 분석 (Causal Analysis)
- **대상**: KPI 또는 Measure 스테레오타입 노드만 분석 가능
- **차트 구간 선택(Brush)**: 라인 차트에서 특정 시간 구간 드래그 선택 → 상승/하락 원인 분석 팝업
- **인과 네트워크 하이라이트**: 분석 대상 노드의 상위 인과 네트워크(최대 depth 3)를 그래프에서 시각적으로 강조
- **스트리밍 보고서**: 원인 분석 보고서를 타이핑 효과로 실시간 표시
- `CausalAnalysisPanel` 컴포넌트가 분석 실행 및 결과 렌더링 담당

### UI/UX
- **다크/라이트 모드** 완전 지원 (CSS 변수 기반, `data-theme` 속성 감지)
- 상세 패널 너비 드래그 리사이즈 (더블클릭으로 기본값 복원)
- 레이어 패널에서 레이어 접기/펼치기
- 온톨로지 그래프 범례 (노드 레이어 색상, 엣지 관계 타입 색상)

---

## 외부 의존성

| 항목 | 용도 |
|---|---|
| **Neo4j** | 온톨로지 스키마 영구 저장소 |
| **Tavily API** | 온톨로지 생성 중 웹 검색 (정보 부족 시 보완) |
| **LLM (비공개)** | 온톨로지 자동 생성, Text2SQL 변환, 원인 분석 보고서 생성 |
| **연결 데이터베이스** | Text2SQL 서비스가 관리하는 다양한 RDBMS 데이터소스 |

---

## 개발 시 주의사항

1. **스트리밍 API**: 온톨로지 생성 및 원인 분석은 NDJSON 스트리밍을 기본으로 하며, 404 응답 시 비스트리밍 엔드포인트로 자동 폴백합니다.
2. **Cytoscape 초기화**: `initCytoscape()`는 컴포넌트 마운트 후 또는 스키마 로드 완료 후 호출해야 합니다. 스키마 로딩 중에는 `isLoadingSchema` 플래그로 watch 트리거를 방지합니다.
3. **Undo/Redo**: 상태 변경 전 반드시 `saveState()`를 호출하여 히스토리에 저장하세요.
4. **데이터 소스 연결**: ObjectType의 경우 `materializedView` 필드를 데이터소스 식별자로 사용합니다.
5. **레이어 정의**: `layers` 배열의 순서(KPI → Resource)가 그래프 계층 레이아웃과 레이어 패널 표시 순서를 결정합니다.


## MEMORY.md

Your MEMORY.md is currently empty. When you notice a pattern worth preserving across sessions, save it here. Anything in MEMORY.md will be included in your system prompt next time.
