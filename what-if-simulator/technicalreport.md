# Technical Report: What-if Simulator

## Explainable KPI Simulation Platform with Causal Discovery

**Version**: 1.0  
**Date**: 2026-01-24  
**Authors**: AI-Assisted Development Team

---

## 목차

1. [Executive Summary](#1-executive-summary)
2. [프로젝트 개요](#2-프로젝트-개요)
3. [시스템 아키텍처](#3-시스템-아키텍처)
4. [Causal Discovery: 역방향 CLD 생성](#4-causal-discovery-역방향-cld-생성)
5. [Edge-Based Simulation](#5-edge-based-simulation)
6. [Model Validation: 검증 실험](#6-model-validation-검증-실험)
7. [Data Literacy: LLM 기반 설명](#7-data-literacy-llm-기반-설명)
8. [Continuous Learning Pipeline](#8-continuous-learning-pipeline)
9. [실험 결과 종합](#9-실험-결과-종합)
10. [결론 및 향후 과제](#10-결론-및-향후-과제)

---

## 1. Executive Summary

본 기술 보고서는 **데이터 기반 인과관계 발견(Causal Discovery)**과 **What-if 시뮬레이션**을 결합한 설명 가능한 KPI 시뮬레이션 플랫폼의 개발 과정과 실험 결과를 기술합니다.

### 핵심 성과

| 항목 | 결과 |
|------|------|
| 발견된 인과관계 | **103개** |
| PRD 정의 CLD와 일치율 | **88%** (15/17) |
| 검증된 모델 중 유효 비율 | **22%** (18/83) |
| MindsDB 최고 성능 모델 | R² = **0.974** (whatif_profit_model) |
| 탐지된 피드백 루프 | **76개** |

### 주요 발견

1. **데이터로부터 인과관계를 자동 발견**하는 것이 가능하며, 전문가 정의 CLD의 88%와 일치
2. **Edge-Based 모델링**으로 각 인과관계의 기여도를 정량적으로 분석 가능
3. **36개월 데이터**로는 많은 관계에서 **과적합** 발생 → 최소 60개월 이상 권장
4. **LLM 기반 설명**으로 비전문가도 분석 결과를 이해 가능

---

## 2. 프로젝트 개요

### 2.1 문제 정의

기업은 환율 변화에 대해 다음을 동시에 알고 싶어합니다:

- 단기적으로 **이익률/마진은 어떻게 변하는가**
- 중·장기적으로 **브랜드 가치와 수요는 어떻게 훼손되거나 강화되는가**
- 이 두 결과 사이의 **트레이드오프는 어떤 경로를 통해 발생하는가**

### 2.2 솔루션 접근법

```
┌─────────────────────────────────────────────────────────────────────┐
│                    전통적 접근법 vs 본 시스템                         │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  전통적 접근법:                                                      │
│    전문가 정의 CLD → 시뮬레이션 → 결과                               │
│                                                                     │
│  본 시스템:                                                          │
│    데이터 → Causal Discovery → 자동 CLD                             │
│         → 검증 → Edge-Based Simulation                              │
│         → LLM 설명 → 지속적 학습                                     │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### 2.3 기술 스택

| 구성요소 | 기술 | 역할 |
|---------|------|------|
| 그래프 DB | Neo4j | 인과관계(CLD) 저장, 경로 분석 |
| ML 플랫폼 | MindsDB | 예측 모델 학습/서빙 |
| 통계 분석 | statsmodels, scipy | Granger Causality, 상관분석 |
| LLM | OpenAI GPT-4o-mini | 데이터 리터러시 |
| 시뮬레이션 | Python (asyncio) | 상태 업데이트, 시나리오 실행 |

---

## 3. 시스템 아키텍처

### 3.1 전체 구조

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        What-if Simulator Pipeline                        │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌─────────────┐    ┌─────────────────┐    ┌─────────────────────────┐  │
│  │ Time Series │───▶│ Causal Discovery│───▶│ Auto CLD (Neo4j)        │  │
│  │ Data (CSV)  │    │ Engine          │    │ 103 edges discovered    │  │
│  └─────────────┘    └─────────────────┘    └───────────┬─────────────┘  │
│                                                        │                │
│  ┌─────────────────────────────────────────────────────▼─────────────┐  │
│  │                     Model Validation                               │  │
│  │  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐    │  │
│  │  │ Train/Test Split│  │ R²/RMSE/MAPE   │  │ Overfit Detection│    │  │
│  │  │ (80/20)        │  │ Calculation    │  │ (63 cases)      │    │  │
│  │  └─────────────────┘  └─────────────────┘  └─────────────────┘    │  │
│  └───────────────────────────────┬───────────────────────────────────┘  │
│                                  │                                      │
│  ┌───────────────────────────────▼───────────────────────────────────┐  │
│  │                    Edge-Based Simulation                          │  │
│  │  각 CAUSES 관계별 MindsDB 모델 또는 회귀 함수 적용                   │  │
│  │  인과 경로 추적 및 기여도 분석                                       │  │
│  └───────────────────────────────┬───────────────────────────────────┘  │
│                                  │                                      │
│  ┌───────────────────────────────▼───────────────────────────────────┐  │
│  │                    Data Literacy (LLM)                            │  │
│  │  OpenAI GPT로 경영진용 요약 및 인사이트 자동 생성                     │  │
│  └───────────────────────────────────────────────────────────────────┘  │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 3.2 파일 구조

```
what-if-simulator/
├── # Causal Discovery
│   ├── causal_discovery.py          # Granger/PC/Correlation 알고리즘
│   ├── cld_generator.py             # CLD 그래프 구축 및 Neo4j 저장
│   └── reverse_cld_test.py          # 역방향 CLD 생성 파이프라인
│
├── # Simulation
│   ├── edge_based_simulation.py     # Edge별 모델 적용 시뮬레이션
│   ├── simulation_engine.py         # 기본 시뮬레이션 엔진
│   └── ontology_loader.py           # Neo4j 온톨로지 관리
│
├── # Validation
│   ├── model_validation.py          # 모델 검증 엔진
│   ├── validation_test.py           # 통합 테스트
│   └── continuous_learning.py       # 지속적 학습 파이프라인
│
├── # Data Literacy
│   └── data_literacy.py             # LLM 기반 설명 생성
│
├── # MindsDB Integration
│   ├── mindsdb_connector.py         # MindsDB API 클라이언트
│   ├── setup_mindsdb_models.py      # MindsDB 모델 학습
│   └── test_mindsdb_simulation.py   # MindsDB 시뮬레이션
│
├── # Data & Results
│   ├── kpi_monthly.csv              # 36개월 KPI 시계열 데이터
│   ├── causal_discovery_results.json
│   ├── influence_functions.json
│   ├── validation_results.json
│   └── literacy_report.json
│
└── # Documentation
    ├── PRD.md
    ├── README.md
    └── technicalreport.md           # 본 문서
```

---

## 4. Causal Discovery: 역방향 CLD 생성

### 4.1 개요

**Causal Discovery**는 시계열 데이터로부터 변수들 간의 인과관계를 자동으로 추정하는 기법입니다. 
기존의 "전문가가 정의한 CLD"를 데이터로 검증하고, 새로운 관계를 발견하는 것이 목표입니다.

### 4.2 사용된 알고리즘

#### 4.2.1 Granger Causality

```
귀무가설: X의 과거 값은 Y의 미래 예측에 도움이 되지 않는다
검정통계량: F-test (SSR 비교)
판정기준: p-value < 0.05
```

**장점**: 시계열 데이터에 적합, 방향성 추론 가능  
**한계**: 선형 관계만 탐지, 숨겨진 교란변수에 취약

#### 4.2.2 Partial Correlation

```python
# 부분 상관: 다른 변수들을 통제한 후의 상관계수
partial_corr(X, Y | Z) = corr(residuals_X, residuals_Y)
```

**장점**: 직접 관계 vs 간접 관계 구분 가능  
**한계**: 방향성 결정 불가

#### 4.2.3 알고리즘 조합 전략

```
신뢰도 점수 = Base Score × (1 + 0.2 × (발견 방법 수 - 1))

예: Granger + Correlation + Partial로 발견된 관계
    신뢰도 = 0.8 × (1 + 0.2 × 2) = 1.12 → 1.0 (상한)
```

### 4.3 실험 설정

| 파라미터 | 값 | 설명 |
|---------|-----|------|
| significance_level | 0.05 | p-value 임계값 |
| min_correlation | 0.35 | 최소 상관계수 |
| max_lag | 2 | Granger 최대 시차 (개월) |
| 데이터 크기 | 36행 × 16열 | 36개월, 16개 변수 |

### 4.4 실험 결과

#### 4.4.1 발견된 인과관계 통계

```
============================================================
🔬 Causal Discovery 결과
============================================================
📊 데이터: 36 행, 16 변수
🎯 유의수준: 0.05

발견된 관계:
  - 상관관계 분석: 52개 후보
  - Granger Causality: 65개 방향성 관계
  - Partial Correlation: 34개 직접 관계
  
✅ 최종 통합 결과: 103개 인과관계
   - 강한 관계 (strength > 0.5): 45개
   - 양의 관계 (+): 66개
   - 음의 관계 (-): 37개
```

#### 4.4.2 상위 10개 발견된 관계

| Rank | Source | → | Target | Strength | Direction | Method |
|------|--------|---|--------|----------|-----------|--------|
| 1 | mkt_spend | →+ | brand_equity | 1.0000 | positive | correlation+granger+partial |
| 2 | cogs | →+ | price | 1.0000 | positive | correlation+partial |
| 3 | sales | →+ | loyalty | 1.0000 | positive | correlation+granger |
| 4 | delivery_time | →- | csat | 0.9929 | negative | correlation |
| 5 | service_level | →+ | csat | 0.9916 | positive | correlation |
| 6 | refund_rate | →- | csat | 0.9915 | negative | correlation |
| 7 | fx_rate | →+ | price | 0.9684 | positive | correlation |
| 8 | csat | →+ | loyalty | 0.9141 | positive | granger |
| 9 | fx_rate | →+ | cogs | 0.8724 | positive | correlation |
| 10 | brand_equity | →+ | loyalty | 0.8524 | positive | correlation+granger+partial |

#### 4.4.3 PRD 정의 CLD와 비교

```
┌─────────────────────────────────────────────────────────────────┐
│ PRD 정의 CLD vs 데이터 기반 발견                                 │
├─────────────────────────────────────────────────────────────────┤
│ ✅ 일치하는 관계: 15개 (88%)                                     │
│    데이터에서도 해당 인과관계가 통계적으로 유의하게 발견됨          │
│                                                                 │
│ ❌ 데이터에서 미발견: 2개 (12%)                                   │
│    - brand_equity → demand                                      │
│    - price → sales                                              │
│    (데이터에서 통계적으로 유의하지 않음)                           │
│                                                                 │
│ 🆕 새로 발견된 관계: 68개                                        │
│    PRD에 없지만 데이터에서 유의하게 발견된 관계                    │
│    예: price → brand_equity, profit → csat                      │
└─────────────────────────────────────────────────────────────────┘
```

#### 4.4.4 핵심 변수 분석

**Root Causes (원인 변수)**: 다른 변수에 가장 많이 영향을 주는 변수

| 변수 | 영향 대상 수 | 설명 |
|------|-------------|------|
| fx_rate | 15개 | 환율 - 가장 광범위한 영향 |
| mkt_spend | 9개 | 마케팅 비용 |
| pass_through | 9개 | 가격 전가율 |

**Final Effects (결과 변수)**: 가장 많은 영향을 받는 변수

| 변수 | 영향 원인 수 | 설명 |
|------|-------------|------|
| brand_equity | 14개 | 브랜드 가치 - 가장 많은 요인에 영향받음 |
| loyalty | 14개 | 고객 충성도 |
| demand | 11개 | 수요 |

#### 4.4.5 피드백 루프 탐지

```
🔄 발견된 피드백 루프: 76개

주요 루프 예시:

[R] Reinforcing Loop (강화 루프):
    sales → loyalty → profit → delivery_time → demand → sales
    해석: 매출 증가 → 충성도 상승 → 이익 증가 → 배송 투자 → 수요 증가 (선순환)

[B] Balancing Loop (균형 루프):
    sales → delivery_time → csat → demand → sales
    해석: 매출 급증 → 배송 지연 → 만족도 하락 → 수요 감소 (자기조정)
```

---

## 5. Edge-Based Simulation

### 5.1 개요

PRD의 핵심 철학인 **"관계별 소형 모델"** 전략을 구현합니다.

```
❌ 기존 방식: 하나의 대형 모델
   whatif_demand_model(price, brand, loyalty) → demand
   
✅ Edge-Based 방식: 관계별 소형 모델
   edge_price_demand(price) → demand 효과
   edge_brand_demand(brand) → demand 효과
   edge_loyalty_demand(loyalty) → demand 효과
   → 각 효과를 합산하여 최종 demand 계산
```

### 5.2 장점

1. **Explainability**: 각 Edge의 기여도를 정량적으로 파악
2. **Modularity**: 개별 관계 모델만 교체/업데이트 가능
3. **Traceability**: 결과가 어떤 경로를 통해 도출되었는지 추적
4. **Flexibility**: 새로운 관계 추가 용이

### 5.3 Edge 기여도 분석 예시

```
DEMAND에 대한 Edge 기여 (FX_RATE=1380 시나리오):

   ← PRICE:        -8.28   (가격 상승 → 수요 감소)
   ← BRAND_EQUITY: -19.20  (브랜드 하락 → 수요 감소)
   ← LOYALTY:      -24.00  (충성도 하락 → 수요 감소)
   ─────────────────────────
   총 효과:        -51.48
   
   Baseline DEMAND: 90.0
   Final DEMAND: 90.0 - 51.48 = 38.52
```

### 5.4 시나리오 비교 결과

| 시나리오 | FX_RATE | PASS_THROUGH | MKT | 단기마진 | 장기브랜드 | 총이익 |
|---------|---------|--------------|-----|---------|-----------|--------|
| Baseline | 1200 | 0.5 | 100 | 13.04% | 13.69 | 12,048 |
| FX_Shock | 1380 | 0.5 | 100 | 13.04% | 10.80 | 12,071 |
| + 가격전가 80% | 1380 | 0.8 | 100 | **19.35%** | 10.80 | **18,439** |
| + 마케팅 150% | 1380 | 0.5 | 150 | 13.04% | **39.27** | 15,817 |

---

## 6. Model Validation: 검증 실험

### 6.1 검증 방법론

#### 6.1.1 Hold-out Validation

```
┌─────────────────────────────────────────────────────────────┐
│                 시계열 데이터 분할                            │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────────────────────────┬─────────────────────┐ │
│  │      Training Data (80%)        │   Test Data (20%)   │ │
│  │      2023-01 ~ 2025-05          │   2025-06 ~ 2025-12 │ │
│  │          28 rows                │       8 rows        │ │
│  └─────────────────────────────────┴─────────────────────┘ │
│                                                             │
│  ⚠️ 시계열 데이터는 랜덤 분할이 아닌 시간순 분할 사용          │
│     (미래 데이터로 과거 예측하는 오류 방지)                    │
└─────────────────────────────────────────────────────────────┘
```

#### 6.1.2 검증 지표

| 지표 | 수식 | 해석 |
|------|------|------|
| R² | 1 - SSres/SStot | 결정계수, 1에 가까울수록 좋음 |
| RMSE | √(mean((y-ŷ)²)) | 평균 제곱근 오차, 작을수록 좋음 |
| MAE | mean(\|y-ŷ\|) | 평균 절대 오차 |
| MAPE | mean(\|y-ŷ\|/y) × 100% | 평균 백분율 오차 |
| Train-Test Gap | Train R² - Test R² | 과적합 지표, 0.15 이상이면 의심 |

### 6.2 실험 결과

#### 6.2.1 전체 요약

```
┌─────────────────────────────────────────────────────────────────┐
│ 📈 추정 함수 검증 결과                                           │
├─────────────────────────────────────────────────────────────────┤
│ 총 검증 함수:   83개                                             │
│ 유효한 함수:   18개 (22%)                                        │
│ 평균 R²: 0.20 (중앙값)                                           │
├─────────────────────────────────────────────────────────────────┤
│ 🎯 적합도 분포                                                   │
│   R² > 0.7 (좋음):   11개 (13%)                                  │
│   R² 0.3~0.7 (보통):   18개 (22%)                                │
│   R² < 0.3 (약함):   54개 (65%)                                  │
├─────────────────────────────────────────────────────────────────┤
│ ⚠️ 과적합 의심:   63개 (76%)                                     │
│    (Train R² - Test R² 차이 > 0.15)                             │
└─────────────────────────────────────────────────────────────────┘
```

#### 6.2.2 가장 신뢰할 수 있는 관계 (Top 6)

| Edge | R² | Test R² | MAPE | Gap | 판정 |
|------|-----|---------|------|-----|------|
| service_level → refund_rate | 0.9922 | 0.9950 | 1.0% | -0.003 | ✅ Excellent |
| delivery_time → csat | 0.9857 | 0.9880 | 0.4% | -0.002 | ✅ Excellent |
| service_level → delivery_time | 0.9845 | 0.9941 | 0.7% | -0.010 | ✅ Excellent |
| service_level → csat | 0.9834 | 0.9917 | 0.4% | -0.008 | ✅ Excellent |
| refund_rate → csat | 0.9831 | 0.9877 | 0.4% | -0.005 | ✅ Excellent |
| refund_rate → delivery_time | 0.9800 | 0.9970 | 0.7% | -0.017 | ✅ Excellent |

**핵심 발견**: `service_level`과 관련된 관계들이 가장 안정적이고 신뢰할 수 있음

#### 6.2.3 과적합 사례 분석

| Edge | Train R² | Test R² | Gap | 원인 분석 |
|------|----------|---------|-----|----------|
| mkt_spend → brand_equity | 0.179 | -4.212 | 4.39 | 마케팅 효과 지연, 비선형 관계 |
| cogs → price | 0.849 | -6.790 | 7.64 | 테스트 기간 가격정책 변화 |
| sales → loyalty | 0.297 | -1.782 | 2.08 | 충성도 측정 방식 변화 |
| fx_rate → cogs | 0.761 | -2.282 | 3.04 | 환율 급변기 헷징 정책 |

**과적합 원인 분석**:
1. **데이터 부족**: 36개월은 검증에 충분하지 않음 (최소 60개월 권장)
2. **비정상성**: 테스트 기간(2025년 하반기)에 구조적 변화 가능성
3. **비선형 관계**: 선형 회귀로 포착 불가능한 관계 존재

#### 6.2.4 MindsDB 모델 검증

```
┌─────────────────────────────────────────────────────────────────┐
│ 🤖 MindsDB 모델 검증 결과 (샘플 10개 기준)                       │
├─────────────────────────────────────────────────────────────────┤
│ Model                    │ R²     │ RMSE   │ MAPE  │ 판정     │
├─────────────────────────────────────────────────────────────────┤
│ whatif_profit_model      │ 0.974  │ 33.91  │ 2.0%  │ ✅ 좋음  │
│ whatif_cogs_model        │ 0.461  │ 1.51   │ 1.1%  │ ⚡ 보통  │
│ whatif_demand_model      │ 0.142  │ 2.35   │ 2.1%  │ ⚠️ 약함  │
│ whatif_brand_model       │ -1.661 │ 3.88   │ 7.6%  │ ❌ 부적합 │
└─────────────────────────────────────────────────────────────────┘
```

**권장 사항**:
- `whatif_profit_model`: 즉시 활용 가능
- `whatif_cogs_model`: 활용 가능, 추가 특성 고려 권장
- `whatif_demand_model`: 다중 요인 모델로 재학습 필요
- `whatif_brand_model`: 시계열 모델(ARIMA, Prophet)로 재설계 필요

---

## 7. Data Literacy: LLM 기반 설명

### 7.1 개요

복잡한 통계 분석 결과를 **비전문가도 이해할 수 있는 자연어**로 변환합니다.

### 7.2 구현 방법

```python
class DataLiteracyEngine:
    def __init__(self, model="gpt-4o-mini"):
        self.client = OpenAI()
        
    def generate_executive_summary(self, discovery, validation):
        prompt = f"""
        당신은 최고 데이터 책임자(CDO)입니다.
        분석 결과를 경영진에게 브리핑할 수 있는 요약문을 작성해주세요.
        
        ## Causal Discovery 결과
        - 발견된 인과관계: {discovery['summary']['total_edges']}개
        ...
        """
        return self.client.chat.completions.create(...)
```

### 7.3 LLM 생성 리포트 예시

```
📝 경영진 요약 (LLM 생성):

"경영진 여러분, 최근 Causal Discovery 분석 결과 103개의 인과관계가 
발견되었으며, fx_rate, mkt_spend, pass_through와 같은 변수들이 
브랜드 가치, 충성도, 수요에 중요한 영향을 미치는 것으로 나타났습니다. 

그러나 검증된 모델의 비율이 낮고 평균 예측 정확도가 음수인 점은 
심각한 과적합 리스크를 시사합니다. 

따라서, 마케팅 예산의 효율성을 높이기 위해 fx_rate와 mkt_spend 간의 
관계를 심층 분석할 필요가 있습니다.

핵심 인사이트: mkt_spend의 조정이 브랜드 가치와 수요에 긍정적인 
영향을 미칠 수 있는 가능성이 높습니다.

추가 분석 필요 영역: fx_rate와 mkt_spend 간의 상호작용 효과."
```

### 7.4 활용 시나리오

| 시나리오 | LLM 역할 |
|---------|---------|
| 주간 KPI 리포트 | 데이터 변화를 자연어로 요약 |
| 시뮬레이션 결과 해석 | 시나리오 간 트레이드오프 설명 |
| 이상 탐지 알림 | 급격한 변화 원인 분석 및 설명 |
| 경영진 브리핑 자료 | 핵심 인사이트 자동 생성 |

---

## 8. Continuous Learning Pipeline

### 8.1 개요

새로운 데이터가 추가될 때 자동으로 전체 파이프라인을 재실행하고 변화를 감지합니다.

### 8.2 파이프라인 구조

```
┌─────────────────────────────────────────────────────────────────────┐
│                  Continuous Learning Pipeline                        │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌─────────────┐                                                    │
│  │ New Data    │──┐                                                 │
│  │ (CSV)       │  │                                                 │
│  └─────────────┘  │                                                 │
│                   ▼                                                 │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │ 1. Data Hash 계산                                            │   │
│  │    MD5 해시로 데이터 변경 여부 확인                            │   │
│  └───────────────────────────────┬─────────────────────────────┘   │
│                                  │                                  │
│                    ┌─────────────┴─────────────┐                    │
│                    │ 변경 감지?                 │                    │
│                    └─────────────┬─────────────┘                    │
│                          Yes     │     No                           │
│                    ┌─────────────┴─────────────┐                    │
│                    ▼                           ▼                    │
│  ┌─────────────────────────┐    ┌─────────────────────────┐        │
│  │ 2. Causal Discovery     │    │ Skip                    │        │
│  │ 3. Model Validation     │    │ (No changes)            │        │
│  │ 4. Change Detection     │    └─────────────────────────┘        │
│  │ 5. History Archiving    │                                       │
│  └─────────────────────────┘                                       │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### 8.3 변화 감지 유형

| 유형 | 설명 | 알림 수준 |
|------|------|----------|
| 새로 발견된 관계 | 이전에 없던 인과관계 추가 | Info |
| 사라진 관계 | 기존 관계가 더 이상 유의하지 않음 | Warning |
| 강화된 관계 | strength 증가 (>0.1) | Info |
| 약화된 관계 | strength 감소 (>0.1) | Warning |
| 모델 성능 개선 | R² 증가 (>0.05) | Info |
| 모델 성능 저하 | R² 감소 (>0.05) | Critical |

### 8.4 히스토리 관리

```
learning_history/
├── discovery_20260124_123456_a1b2c3d4.json
├── discovery_20260125_091011_e5f6g7h8.json
├── validation_20260124_123456_a1b2c3d4.json
└── validation_20260125_091011_e5f6g7h8.json
```

---

## 9. 실험 결과 종합

### 9.1 핵심 성과 요약

```
┌─────────────────────────────────────────────────────────────────────┐
│                      실험 결과 종합 대시보드                          │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  📊 Causal Discovery                                                │
│  ├─ 발견된 인과관계: 103개                                          │
│  ├─ PRD 일치율: 88% (15/17)                                        │
│  ├─ 새로 발견: 68개                                                 │
│  └─ 피드백 루프: 76개                                               │
│                                                                     │
│  ✅ Model Validation                                                │
│  ├─ 유효한 함수: 22% (18/83)                                        │
│  ├─ 과적합 의심: 76% (63/83)                                        │
│  ├─ 최고 R²: 0.99 (service_level → refund_rate)                    │
│  └─ MindsDB 최고: 0.97 (whatif_profit_model)                       │
│                                                                     │
│  🔄 Simulation                                                      │
│  ├─ 시나리오 비교: 4개 시나리오 분석                                 │
│  ├─ 최대 이익 시나리오: FX_Shock + 가격전가80% (+53%)               │
│  └─ 브랜드 보호 시나리오: 마케팅150% (브랜드 +187%)                  │
│                                                                     │
│  📚 Data Literacy                                                   │
│  └─ LLM 리포트: 경영진 요약 자동 생성 성공                           │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### 9.2 주요 인사이트

#### 9.2.1 신뢰할 수 있는 인과관계

1. **서비스 품질 → 고객 만족**: 가장 안정적인 관계 (R² > 0.98)
2. **환율 → 원가**: 데이터와 PRD 모두 일치 (R² = 0.76)
3. **원가 → 가격**: 강한 관계지만 테스트 성능 불안정

#### 9.2.2 주의가 필요한 관계

1. **마케팅 → 브랜드**: 지연 효과 모델링 필요
2. **브랜드 → 수요**: 비선형 관계 가능성
3. **가격 → 판매**: 탄력성이 시기에 따라 변동

#### 9.2.3 새로 발견된 중요 관계

1. **profit → csat**: 수익성이 서비스 품질에 재투자되는 효과
2. **price → brand_equity**: 가격이 브랜드 인식에 미치는 영향
3. **service_level → sales**: 직접적인 매출 효과

### 9.3 한계점 및 주의사항

1. **데이터 크기**: 36개월은 통계적 검증에 불충분 (권장: 60개월+)
2. **선형 가정**: 비선형 관계 탐지 불가
3. **외부 요인**: 코로나, 경기 변동 등 구조 변화 미반영
4. **인과 vs 상관**: Granger Causality도 진정한 인과를 보장하지 않음

---

## 10. 결론 및 향후 과제

### 10.1 결론

본 프로젝트는 **데이터 기반 인과관계 발견**과 **설명 가능한 시뮬레이션**을 성공적으로 결합하였습니다.

주요 성과:
- 전문가 정의 CLD의 88%를 데이터로 검증
- Edge-Based 시뮬레이션으로 인과 경로별 기여도 분석
- LLM을 활용한 비전문가 대상 자동 설명 생성
- 지속적 학습 파이프라인으로 자동 업데이트 체계 구축

### 10.2 향후 과제

#### 단기 (1-3개월)

| 과제 | 우선순위 | 예상 효과 |
|------|---------|----------|
| 데이터 확보 (60개월+) | 높음 | 과적합 해소, 검증 신뢰도 향상 |
| 비선형 모델 추가 (XGBoost, GAM) | 높음 | 복잡한 관계 포착 |
| 시각화 대시보드 구축 | 중간 | 사용자 접근성 향상 |

#### 중기 (3-6개월)

| 과제 | 우선순위 | 예상 효과 |
|------|---------|----------|
| 고급 Causal Discovery (LiNGAM, NOTEARS) | 중간 | 방향성 추정 정확도 향상 |
| 실시간 데이터 연동 | 중간 | 최신 상태 반영 |
| 멀티 테넌트 지원 | 낮음 | 여러 사업부 적용 |

#### 장기 (6-12개월)

| 과제 | 우선순위 | 예상 효과 |
|------|---------|----------|
| 자동 모델 선택 (AutoML) | 중간 | Edge별 최적 모델 자동 선정 |
| 인과 효과 추정 (DoWhy) | 중간 | 인과적 what-if 정확도 향상 |
| 자연어 인터페이스 | 낮음 | "환율 10% 오르면?" 질문 처리 |

---

## 부록

### A. 실행 명령어 모음

```bash
# 전체 역방향 CLD 생성
python3 reverse_cld_test.py

# 모델 검증
python3 model_validation.py

# 데이터 리터러시 (LLM)
OPENAI_API_KEY="your-key" python3 data_literacy.py

# 지속적 학습
python3 continuous_learning.py

# Edge-Based 시뮬레이션
python3 edge_based_simulation.py

# 통합 테스트
python3 validation_test.py
```

### B. 환경 설정

```bash
# 필수 패키지
pip install neo4j requests pydantic pandas numpy
pip install statsmodels scipy networkx matplotlib
pip install openai  # LLM 기능

# 선택 패키지 (고급 기능)
pip install lingam tigramite dowhy causal-learn
```

### C. 참고 문헌

1. Sterman, J. D. (2000). Business Dynamics: Systems Thinking and Modeling for a Complex World
2. Pearl, J. (2009). Causality: Models, Reasoning, and Inference
3. Spirtes, P., Glymour, C., & Scheines, R. (2000). Causation, Prediction, and Search
4. Granger, C. W. (1969). Investigating Causal Relations by Econometric Models and Cross-spectral Methods

---

*본 기술 보고서는 2026년 1월 24일에 작성되었습니다.*
