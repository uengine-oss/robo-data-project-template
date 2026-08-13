# Ontologic E2E 회귀 테스트

설치 후 또는 변경 후 플랫폼 핵심 파이프라인이 살아있는지 검증한다.
포트/접속 정보는 레포 루트 `.env`를 따른다 (재매핑 내역은 `installation.md`).

## 구성

| 스위트 | 파일 | 검증 범위 | 소요 |
|---|---|---|---|
| API | `test_pipeline_api.py` | 인프라 헬스 → data-fabric 데이터소스 → MindsDB federated 질의 → text2sql 메타 (+ `slow`: ReAct 자연어 질의 전체) | ~10초 (slow 포함 시 수 분) |
| UI | `test_ui_smoke.py` | 프론트(3000) 렌더링, 로고, 데이터소스 카드, 스키마 트리, 자연어 질의/온톨로지/What-if/감시에이전트 화면 | ~1분 |

## 실행

```bash
cd tests/e2e

# API 스위트 (빠른 회귀 — CI 기본)
uv run --with pytest --with requests --with python-dotenv \
  pytest test_pipeline_api.py -v -m "not slow"

# API 전체 (LLM 자연어 질의 포함)
uv run --with pytest --with requests --with python-dotenv \
  pytest test_pipeline_api.py -v

# UI 스모크 (frontend + gateway + 백엔드 서비스 필요)
python3 -m pytest test_ui_smoke.py -v      # playwright + chromium 설치 전제
```

## 사전 조건

- 인프라 + 서비스 기동 상태 (installation.md의 "서비스 재기동 방법" 참조,
  UI 스위트는 api-gateway(9000)와 frontend(3000)까지 필요)
- 시스템 과부하 시 게이트웨이 경유 API가 타임아웃되어 간헐 실패할 수 있음 —
  UI 테스트는 폴링/재진입 재시도가 들어 있으나, 무거운 병렬 작업(영상 인코딩
  등)과 동시 실행은 피할 것.
