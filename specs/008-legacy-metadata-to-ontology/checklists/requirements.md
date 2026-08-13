# Specification Quality Checklist: 레거시 메타데이터에서 온톨로지까지

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-08-05
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

### 요구사항 본문에 코드 경로가 들어간 것에 대하여

FR-016·FR-022 와 §배경에 `entity_matcher.py:27-29` 같은 파일·줄 인용이 있다. 이는 구현 지시가
아니라 **"현재 이렇게 되어 있다"는 실측 근거**다. 이 저장소의 spec 001~003 이 역공학 스펙이라
같은 관례를 쓰고, `specs/README.md` 가 각 요구사항에 근거(`↳`)를 붙이도록 정하고 있다.

요구사항 자체("증강된 메타데이터를 근거로 사용해야 한다")는 기술 중립적이며, 근거 인용은
*현재 상태* 절에 분리해 두었다.

### 갈림길 2건 — 해소됨 (2026-08-05)

[NEEDS CLARIFICATION] 마커 대신 선택지·함의·권고를 갖춘 표로 제시했고, 사용자가 결정했다.

- **Q1** 온톨로지 객체화 주체 → **B. domain-layer 번들 편입** (제 권고 A 와 다름)
- **Q2** 기존 예제 처리 → **C. 난독화본 기본 + 깨끗한 예제 선택 유지** (권고와 일치)

Q1-B 의 결과로 요구사항이 7개 늘었다 (FR-034~040) 그리고 **헌법 개정이 이 스펙의 산출물**이 되었다
(FR-028a). 이 점이 계획 단계에서 누락되기 쉬우므로 여기 적어 둔다 — 헌법은 리뷰 기준 문서이고,
개정 없이 구현하면 코드가 계속 위반 상태로 남는다.

### 계획 전 확인해야 할 것

1. **분석기 전역 삭제 수정의 실증** — FR-032·SC-007 이 여기 의존한다. 수정은 했으나 실제
   인제스천으로 데이터소스가 보존되는지 확인하지 않았다.
2. **domain-layer 서브모듈 상태** — 조사 시점에 커밋되지 않은 변경이 있었다. 번들에 넣기 전에
   확정해야 한다.
3. **메모리 격차** — 유휴 7.3 GiB 로 "최소 8 GB" 가 이미 성립하지 않는다. domain-layer 편입은
   이를 더 벌린다. FR-039 가 증가분 기록을 요구하지만, **목표 자체를 조정할지는 사업 결정**이다.

### 착수 전 실증이 필요한 전제

`robo-data-analyzer` 의 전역 삭제 수정(2026-08-05)이 **아직 실제 인제스천으로 검증되지 않았다.**
FR-032·SC-007("기존 데이터가 보존된다")이 그 수정에 의존하므로, 이 스펙 착수 전에 실증해야 한다.
