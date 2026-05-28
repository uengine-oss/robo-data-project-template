# OpenSpec

이 디렉토리는 `robo-data-project-template`에 포함된 서비스들의 **OpenSpec 사양**을 통합 관리합니다.

## 목적

대표님 방침에 따라 본 프로젝트는 **OpenSpec 기반 개발**을 진행하며,
모든 OpenSpec 관련 사양은 본 디렉토리에서 통합적으로 관리됩니다.

## 디렉토리 구조 (예정)

```text
openspec/
├── README.md             # 본 문서
├── ontologic/            # 카탈로그 · 글로서리 · ANTLR · Analyzer · Frontend 영역
│   ├── catalog/
│   ├── glossary/
│   ├── antlr-parser/
│   ├── analyzer/
│   └── frontend/
└── (그 외 영역별 폴더 추가 예정)
```

## 영역 매핑

| 영역 | 담당 | 관련 submodule |
| --- | --- | --- |
| catalog | ontologic | `robo-data-catalog` |
| glossary | ontologic | `robo-data-glossary` |
| antlr-parser | ontologic | `antlr-code-parser` |
| analyzer | ontologic | `robo-data-analyzer` (`robo-data-analyzer.git` @ `refactor`) |
| frontend | ontologic | `robo-data-frontend` |

## 작성 규칙

OpenSpec 초안은 `code-to-spec` 등 도구로 생성할 수 있으나, **바로 사용할 수 있는 품질은 보장되지 않으므로** 담당자가 검토·보완 후 본 디렉토리에 커밋합니다.

## 진행 상태

- [x] 기반 디렉토리 세팅 (본 문서)
- [ ] ontologic 영역 OpenSpec 초안 작성
- [ ] 기타 영역 OpenSpec 작성
