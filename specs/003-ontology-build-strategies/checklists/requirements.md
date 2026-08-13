# Specification Quality Checklist: 입력 조합별 온톨로지 구축 전략

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-07-30
**Feature**: [spec.md](../spec.md)

## Content Quality

- [x] No implementation details (languages, frameworks, APIs)
- [x] Focused on user value and business needs
- [x] Written for non-technical stakeholders
- [x] All mandatory sections completed

## Requirement Completeness

- [x] No [NEEDS CLARIFICATION] markers remain
- [x] Requirements are testable and unambiguous
- [x] Success criteria are measurable
- [x] Success criteria are technology-agnostic (no implementation details)
- [x] All acceptance scenarios are defined
- [x] Edge cases are identified
- [x] Scope is clearly bounded
- [x] Dependencies and assumptions identified

## Feature Readiness

- [x] All functional requirements have clear acceptance criteria
- [x] User scenarios cover primary flows
- [x] Feature meets measurable outcomes defined in Success Criteria
- [x] No implementation details leak into specification

## Notes

### 검증 반복 1 — 발견된 문제와 조치

1. **"구현 세부사항 없음" 항목이 처음에 실패했다.** FR-017·FR-018·FR-019·FR-021·FR-024,
   Assumptions, 그리고 "??계수" 절이 파일 경로·클래스명·Cypher 관계명(`READS_FIELD`)·
   가중치 수치를 인용한다.
   **판단: 의도적으로 유지한다.** 이 저장소의 스펙 규약(001·002)이 `↳` 줄로 근거 위치를
   남기도록 요구하고, constitution 이 "추측이 아니라 소스와 실측에서 확인한 사실" 을 규범으로
   정한다. 또한 사용자가 "기존 what-if simulator 참고" 를 명시적으로 요구했으므로 어떤 자산을
   재사용하는지가 요구사항의 일부다.
   **완화 조치**: 요구사항 문장 자체는 기술 중립으로 쓰고(무엇을 해야 하는가), 코드 인용은
   `↳` 근거 줄과 Assumptions 로 분리했다. 요구사항을 지우고 근거만 남기지 않았다.

2. **Success Criteria 의 기술 중립성** — SC 전체를 재검토해 SQL·Neo4j·Granger 같은 구현 용어를
   빼고 관찰 가능한 결과(행 수, 0건, 동일 여부, 보고 여부)로 표현했다. SC-013 만 검증
   스크립트를 인용하는데, 이는 플랫폼 계약 검사 도구이므로 남겼다.

3. **범위 경계** — 초안에 "무엇을 하지 않는가" 가 없어 인과 발견이 예측 모델 학습·배포까지
   번질 여지가 있었다. **"범위 밖" 절을 추가**했다.

### 검증 반복 2 — 결과

전 항목 통과. 다음 단계 진행 가능.

### 사용자 확인이 남은 항목 (차단 아님)

스펙은 합리적 기본값으로 채워져 있으나, 아래 두 가지는 되돌리기 비용이 큰 범위 결정이라
사용자에게 별도로 제시했다. 답에 따라 스펙을 갱신한다.

- **전략 선택(User Story 3)이 런타임 기능인가, 문서 가이드인가** — 현재 스펙은 런타임 기능
  (FR-001~004)으로 썼다.
- **전략 2 의 산출 범위** — 현재 스펙은 온톨로지 관계 생성까지로 끊고, what-if 시뮬레이션
  연결은 "범위 밖" 으로 두었다.
