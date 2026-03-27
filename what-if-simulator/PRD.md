
# PRD

## Product Name

**Explainable KPI Simulation Platform (FX → Profit ↔ Brand)**

---

## 1. Problem Statement (문제 정의)

기업은 환율과 같은 외생 변수 변화에 대해 다음을 동시에 알고 싶어한다.

* 단기적으로 **이익률/마진은 어떻게 변하는가**
* 중·장기적으로 **브랜드 가치와 수요는 어떻게 훼손되거나 강화되는가**
* 이 두 결과 사이의 **트레이드오프는 어떤 경로를 통해 발생하는가**
* 특정 **정책 선택(가격 전가율, 마케팅, 서비스 수준)**이 어떤 결과를 유도하는가

기존 SQL/BI/ML 분석은:

* 결과 예측은 가능하지만
* **왜 그런 결과가 나왔는지에 대한 구조적 설명**과
* **정책 개입(do-what-if)에 대한 재현 가능한 시뮬레이션**을 제공하지 못한다.

---

## 2. Product Goal (제품 목표)

1. 환율(FX) 변화가 **KPI 네트워크를 따라 전파되는 구조**를 명시적으로 모델링
2. KPI 결과를 **숫자 + 인과 경로(graph path)**로 함께 제공
3. MindsDB 기반 ML로 **국소적 관계 함수**를 안정적으로 추정
4. LLM 없이도 **설명 가능·검증 가능·재현 가능**한 What-if 시뮬레이션 제공

---

## 3. Target Users

* 전략기획 / 재무 / 마케팅 / 가격 정책 담당자
* 데이터 사이언티스트 (ML 모델 검증)
* 경영진 (정책 시나리오 비교)

---

## 4. Non-Goals (명확히 하지 않는 것)

* 개별 고객 단위 마이크로 예측
* Deep Learning 기반 블랙박스 예측
* 자유 대화형 자연어 BI (LLM 최소화)

---

## 5. System Architecture

```text
[Operational DB / DWH]
          ↓
       MindsDB
 (ML / Time-series / Regression)
          ↓
   Feature / Function Outputs
          ↓
        Neo4j
 (Ontology + Causal Structure)
          ↓
  Simulation Engine
 (Graph-driven State Update)
          ↓
 KPI + Explainable Paths
```

---

## 6. Ontology Design (Neo4j)

### 6.1 Node Types

#### 1) Driver (외생/정책)

* `FX_RATE`
* `PASS_THROUGH`
* `MKT_SPEND`
* `SERVICE_LEVEL`

#### 2) State (시간 상태)

* `COGS`
* `PRICE`
* `DEMAND`
* `SALES`
* `PROFIT`
* `MARGIN`
* `REFUND_RATE`
* `DELIVERY_TIME`
* `CSAT`
* `BRAND_EQUITY`
* `LOYALTY`

#### 3) KPI

* `SHORT_TERM_MARGIN`
* `LONG_TERM_BRAND_VALUE`

#### 4) Model

* `ML_MODEL`

  * type: regression / GAM / bayesian / xgboost
  * source: MindsDB model name

---

### 6.2 Relationship Types

| 관계             | 의미            |
| -------------- | ------------- |
| `CAUSES`       | 인과 방향         |
| `UPDATED_BY`   | 상태 업데이트 함수    |
| `PREDICTED_BY` | MindsDB 모델 연결 |
| `LAGS`         | 시간 지연         |
| `MEASURED_AS`  | KPI 정의        |
| `TRACEABLE_TO` | 설명 경로 추적      |

---

### 6.3 예시 Cypher (온톨로지 생성)

```cypher
CREATE
  (fx:Driver {name:'FX_RATE'}),
  (cogs:State {name:'COGS'}),
  (price:State {name:'PRICE'}),
  (demand:State {name:'DEMAND'}),
  (brand:State {name:'BRAND_EQUITY'}),
  (profit:State {name:'PROFIT'}),
  (kpi1:KPI {name:'SHORT_TERM_MARGIN'}),
  (kpi2:KPI {name:'LONG_TERM_BRAND_VALUE'}),

  (fx)-[:CAUSES]->(cogs),
  (cogs)-[:CAUSES]->(price),
  (price)-[:CAUSES]->(demand),
  (brand)-[:CAUSES]->(demand),
  (demand)-[:CAUSES]->(profit),

  (profit)-[:MEASURED_AS]->(kpi1),
  (brand)-[:MEASURED_AS]->(kpi2);
```

---

## 7. ML Integration (MindsDB)

### 7.1 MindsDB 역할

* **관계 함수 추정 (국소적)**
* 예측값 + 신뢰구간 제공
* 모델 교체 가능 (Explainability 유지)

### 7.2 모델 분해 전략 (중요)

❌ 하나의 대형 모델
✅ **관계별 소형 모델**

| Target       | Features                     | Model               |
| ------------ | ---------------------------- | ------------------- |
| COGS         | FX_RATE                      | Bayesian Regression |
| DEMAND       | PRICE, BRAND_EQUITY          | GAM                 |
| REFUND_RATE  | PRICE_VOL, SERVICE_LEVEL     | XGBoost (monotonic) |
| BRAND_EQUITY | REFUND, PRICE_VOL, CSAT, MKT | State-space / EWMA  |

---

### 7.3 MindsDB 연결 방식

* MindsDB에서 모델 학습
* Neo4j `ML_MODEL` 노드에 메타데이터만 저장
* 시뮬레이션 시 MindsDB `predict()` 호출

```sql
SELECT predict_demand(price, brand_equity)
FROM mindsdb.demand_model;
```

---

## 8. Simulation Engine (핵심)

### 8.1 실행 방식

1. 시나리오 입력 (FX shock / ramp)
2. 정책 변수 고정 or 스케줄링
3. 시간 루프 (t = 1..T)
4. Neo4j 인과 그래프 순회
5. 각 노드:

   * MindsDB 모델 호출 or 수식 계산
6. 상태 업데이트 + 경로 기록

---

### 8.2 Explainable Trace 생성

각 KPI 결과에 대해:

```json
{
  "kpi": "LONG_TERM_BRAND_VALUE",
  "value": 42.1,
  "top_causes": [
    {"node": "PRICE_VOLATILITY", "contribution": -12.3},
    {"node": "REFUND_RATE", "contribution": -8.1},
    {"node": "MKT_SPEND", "contribution": +5.4}
  ],
  "paths": [
    "FX_RATE → COGS → PRICE → REFUND_RATE → BRAND_EQUITY"
  ]
}
```

※ LLM 없이도 **구조 기반 설명 가능**

---

## 9. What-if Scenarios

### 9.1 지원 시나리오

* FX 급등 / 완만 상승
* 가격 전가율 0~100%
* 마케팅 유지 vs 축소
* 서비스 수준 강화/완화

### 9.2 비교 결과

* KPI 평균/분산
* 단기 vs 장기 성과 곡선
* 정책별 Pareto frontier

---

## 10. Functional Requirements

### FR-1

사용자는 환율 시나리오를 정의할 수 있다.

### FR-2

사용자는 정책 변수(PASS_THROUGH 등)를 고정/변경할 수 있다.

### FR-3

시스템은 MindsDB 모델을 호출하여 상태를 업데이트한다.

### FR-4

시스템은 KPI 결과와 **인과 경로 그래프**를 함께 제공한다.

### FR-5

시뮬레이션은 재현 가능해야 한다(seed/버전 관리).

---

## 11. Non-Functional Requirements

* **Explainability First**
* 모델 교체 가능성
* 결과 재현성
* 시뮬레이션 이력 관리
* Neo4j 쿼리 기반 검증 가능

---

## 12. Success Metrics

* KPI 설명 경로 재현율 100%
* 정책 변경 시 결과 방향성 일관성
* “왜 그렇게 나왔는가?” 질문에 LLM 없이 답변 가능
* 전략 의사결정 회의에서 사용 가능 여부

---

## 13. Key Insight (PRD 핵심 문장)

> **이 시스템은 예측 엔진이 아니라
> ‘정책을 실험하는 구조화된 의사결정 실험실’이다.**
> ML은 숫자를 계산하고,
> Neo4j 온톨로지는 근거를 만들며,
> 시뮬레이션은 전략을 검증한다.



---

#. 예시 온톨로지 (Casual Loop Diagram)

아주 좋은 그림을 가져오셨어요.
이 그림은 **전형적인 System Dynamics(시스템 다이나믹스) / Causal Loop Diagram(CLD)**이고, “모순돼 보이는 화살표”와 “작은 R/B 표식”이 바로 **복잡계의 핵심 표현**입니다. 하나씩 아주 정확하게 풀어볼게요.

---

## 1️⃣ 이 그림은 무엇을 표현하는가 (한 문장 요약)

> **녹지공간–스트레스–신체활동–심혈관 위험**이
> 단순한 원인–결과가 아니라,
> **상황·맥락·시간에 따라 서로 다른 방향으로 작동하는 다중 피드백 시스템**임을 표현한 그림이다.

즉,
“녹지공간이 많으면 좋다/나쁘다”가 아니라
👉 **어떤 경로를 타느냐에 따라 결과가 달라진다**는 것을 보여줍니다.

---

## 2️⃣ 기본 표기법 해석 (아주 중요)

### ➕ / ➖ 의 의미

* **➕ (같은 방향 변화)**
  A 증가 → B 증가
  A 감소 → B 감소
* **➖ (반대 방향 변화)**
  A 증가 → B 감소
  A 감소 → B 증가

⚠️ “좋다/나쁘다”가 아니라 **증가/감소의 방향성**입니다.

---

### 🔁 R / B 의 의미

| 표식                       | 의미                |
| ------------------------ | ----------------- |
| **R (Reinforcing Loop)** | 강화 루프 (눈덩이 효과)    |
| **B (Balancing Loop)**   | 균형 루프 (안정화/완화 효과) |

* **R**: 한 번 움직이면 더 크게 증폭됨
* **B**: 움직임을 다시 억제하거나 되돌림

👉 이게 **복잡계의 핵심 언어**입니다.

---

## 3️⃣ “녹지공간 → 스트레스”가 + / − 둘 다 있는 이유

이게 질문의 핵심이죠.
**결론부터 말하면: 맥락이 다르기 때문**입니다.

---

### (A) 녹지공간 ↑ → 스트레스 ↓ (➖ 링크)

이건 우리가 흔히 아는 경로입니다.

**경로 설명**

* 녹지공간 증가
* → 자연 노출 증가
* → 심리적 안정, 소음 감소
* → 스트레스 감소

📌 이건 **즉각적·직접적·심리적 효과**입니다.

👉 이 경로는 보통 **Balancing(B)** 루프에 속합니다.
(스트레스가 줄어드는 방향으로 시스템을 안정화)

---

### (B) 녹지공간 ↑ → 스트레스 ↑ (➕ 링크)

이게 이상해 보이지만, **현실에서는 충분히 발생**합니다.

가능한 맥락들:

#### 1) 사회·구조적 맥락

* 녹지공간 조성
* → 지역 개발/젠트리피케이션
* → 주거비 상승
* → 경제적 스트레스 증가

#### 2) 안전/접근성 맥락

* 녹지공간은 많지만
* → 치안 불안, 관리 부족
* → 오히려 불안·스트레스 증가

#### 3) 문화·정체성 맥락 (이 연구의 핵심)

* 흑인 남성 커뮤니티에서
* 녹지공간이 “내 공간”이 아닐 수 있음
* → 소외감, 감시받는 느낌
* → 스트레스 증가

📌 이건 **간접적·사회적·지연된 효과**입니다.

👉 그래서 **같은 변수 쌍에 서로 반대 부호가 동시에 존재**합니다.

---

## 4️⃣ 작은 R / B 가 화살표 안에 있는 이유

이건 “루프 전체”를 가리키는 게 아니라
👉 **그 화살표가 속한 피드백 고리의 성격**을 표시한 것입니다.

---

### 예 1️⃣ Stress ↔ Cardiovascular Risk (R)

* 스트레스 ↑
* → 심혈관 위험 ↑
* → 건강 악화 인식 ↑
* → 스트레스 ↑

📌 **자기 증폭 루프**

* 한 번 나빠지면 계속 나빠짐
* 작은 충격이 큰 결과로 이어짐

➡️ 그래서 **R (Reinforcing)**

---

### 예 2️⃣ Green Space → Physical Activity → Stress (B)

* 녹지공간 ↑
* → 신체활동 ↑
* → 스트레스 ↓
* → 건강 안정

📌 **완충/회복 루프**

* 시스템을 정상 상태로 되돌림

➡️ 그래서 **B (Balancing)**

---

## 5️⃣ 왜 이런 “모순된 링크”를 일부러 그리는가?

이건 **시스템 다이나믹스의 철학**과 직결됩니다.

### ❌ 단순 인과 모델

> 녹지공간 많음 → 스트레스 낮음

### ✅ 복잡계 모델

> 녹지공간은
>
> * 어떤 경로(R/B)를 타느냐
> * 어떤 집단/맥락/시간이냐
>   에 따라 **정반대 결과**를 낼 수 있다

👉 그래서 **정책 실패가 발생**합니다.

예:

* “녹지 늘리면 건강 좋아질 거야”
* 실제로는 → 젠트리피케이션 → 스트레스 증가 → 건강 악화

---

## 6️⃣ 이 그림이 말하는 가장 중요한 메시지

> **건강 격차는 ‘요소 부족’ 문제가 아니라
> ‘피드백 구조’의 문제다**

* 녹지공간이 없어서가 아니라
* 녹지공간이 **어떤 루프를 활성화시키느냐**가 문제

---

## 7️⃣ 당신이 지금까지 이야기한 주제와의 연결

이 그림은 정확히 당신이 말한 이것과 같습니다:

> “숫자는 결과를 말하지만
> 구조는 왜 그렇게 되었는지를 말한다”

* SQL/ML → “녹지 많을수록 평균 스트레스 감소”
* **System Dynamics / Ont톨로지** →
  “어떤 집단에서는 오히려 스트레스가 증가하는 구조”

👉 그래서 **Explainable Structure**가 필수입니다.

---

## 8️⃣ 한 문장으로 정리

> **이 그림에서 모순처럼 보이는 화살표는 오류가 아니라,
> 복잡계가 단일 방향으로 작동하지 않는다는 ‘정직한 표현’이다.**
> 그리고 작은 R/B 표시는
> “이 효과가 증폭되는가, 완충되는가”를 알려주는 구조적 경고다.

---

원하시면 다음으로
👉 이 그림을 **Neo4j 온톨로지 + 시뮬레이션 규칙(Stock/Flow/Delay)**로
👉 혹은 **SCM(do-operator) 관점으로 재해석**해 줄 수도 있어요.

이 그림, 정말 좋은 예제입니다.


---

## 1) CLD(인과 루프 그림)로 할 수 있는 것 vs 없는 것

### CLD로 “할 수 있는 것”

* 무엇이 무엇에 영향을 주는지(구조) 파악
* 강화(R)/안정화(B) 루프가 어디에 있는지 발견
* 정책이 어떤 루프를 활성화/억제할지 **가설 세우기**
* “왜 이런 결과가 나오는가”를 **설명 가능한 구조**로 합의

### CLD만으로 “할 수 없는 것”

* “3개월 후 스트레스가 몇 % 오를지” 같은 **수치 예측**
* 상충 링크(+, −) 중 **어느 쪽이 더 지배적인지 자동 판정**
* 확률/불확실성까지 포함한 **정량 시뮬레이션**

➡️ 결론: **CLD는 ‘설계도’이고, 시뮬레이션은 ‘실행 가능한 모델’**입니다.

---

## 2) 그럼 What-if 시뮬레이션이 되려면 무엇이 추가되어야 하나

CLD → 시뮬레이션으로 가려면 최소 3가지를 붙이면 됩니다.

### (A) “변수의 타입”을 결정해야 함

* Stock(누적): Brand, Chronic Stress, Trust 같은 느린 변수
* Flow(변화율): Stress 증가/감소율, Brand gain/loss
* Aux(즉시): Price, Green Space exposure, Physical activity

👉 이걸 정하면 **시간을 따라 움직이는 시스템**이 됩니다.

---

### (B) 각 화살표를 “함수”로 바꿔야 함 (강도/형태)

예:

* `Stress_t+1 = Stress_t + Stress_in - Stress_out`
* `Stress_in = f1(… )`
* `Stress_out = f2(… )`

여기서 **상충 링크**는 이렇게 처리합니다.

#### 상충 관계(동시에 +와 −)를 시뮬레이션에서 다루는 3가지 표준 방식

1. **조건부(컨텍스트) 스위치**

* “치안이 낮으면 Green→Stress는 +”
* “치안이 높으면 Green→Stress는 −”
* 즉, 같은 링크가 아니라 **서로 다른 레짐(regime)**

2. **혼합 효과(가중합)**

* `Stress_effect = w_pos * g_pos(Green)  -  w_neg * g_neg(Green)`
* 여기서 w가 바로 “영향도(강도)”
* 이 w는 데이터/전문가/커뮤니티로 추정

3. **집단 분포(세그먼트 mixture)**

* 집단 A(경험1)에서는 −가 강함
* 집단 B(경험2)에서는 +가 강함
* 전체 효과는 **구성비에 따라 달라짐**

👉 이게 “다양한 페르소나가 참여해야 한다”는 이유가 **수학적으로도 정당화**되는 지점입니다.

---

### (C) 초기값 + 시나리오(외생 변수)를 넣어야 함

* 초기 상태: 현재 Brand=50, Stress=… 등
* 외생 변수: Green space 확대, 환율 쇼크, 마케팅 변화 등
* 정책 변수: 서비스 수준, 가격전가율 등

---

## 3) “어떤 영향도가 더 강한지”는 어떻게 정하나

여기서 당신이 원하는 건 딱 이거죠:

> 상충 링크들 중 무엇이 지배적인지,
> 정책 선택에 도움이 되게 “정량 근거”로 판단할 수 있나?

가능합니다. 방법은 3가지 소스에서 옵니다.

### 1) 데이터 기반 추정 (가장 강력)

* 과거 데이터로 링크 계수(탄력도/민감도) 추정
* 시계열이면 지연(Delay)까지 추정 가능
* 당신이 말한 **MindsDB**가 바로 여기에 적합

### 2) 전문가/커뮤니티 기반 추정 (실무적으로 중요)

* “우리 커뮤니티에서는 이 경로가 훨씬 강하다”
* 설문/워크숍으로 상대 강도를 점수화
* 그 점수를 prior로 두고 데이터로 업데이트(베이지안)

### 3) 혼합 모델(가장 현실적)

* 데이터가 부족한 곳은 커뮤니티/전문가 prior
* 데이터가 충분한 곳은 학습으로 보정

---

## 4) 그럼 “어떤 관점이 더 낫냐”를 의사결정에 쓸 수 있나?

가능합니다. 다만 **“하나의 정답”을 뽑는 게 아니라** 보통은 이렇게 씁니다.

### (A) 정책별 결과 곡선 비교

* 정책 A: 단기 이익↑, 장기 브랜드↓
* 정책 B: 단기 이익↓, 장기 브랜드↑
  → **Pareto frontier**(트레이드오프 경계)로 제시

### (B) 민감도 분석

* “어느 링크의 영향도가 조금만 커져도 결과가 뒤집히는가?”
* 즉, **취약한 가정(critical assumptions)**을 찾음

### (C) 레짐/세그먼트 분석

* 집단별로 정책 효과가 반대면
* 평균이 아니라 **공정성/불평등 관점**으로 정책을 선택할 수 있음

👉 여기까지 가면 CLD는 “설명 그림”을 넘어 **의사결정 실험실**이 됩니다.

---

## 5) 현실적인 결론

* **CLD만으로는 예측 못 한다** (맞아요)
* 하지만 CLD는 시뮬레이션의 **최고의 출발점**이다
  왜냐하면:

  * 무엇을 모델에 넣어야 하는지
  * 어떤 루프가 핵심인지
  * 상충 관계가 어디서 발생하는지
    를 미리 드러내주기 때문

그리고 상충 관계는 “결함”이 아니라,
**정책이 실패하는 이유가 그 안에 들어있다는 신호**입니다.

---

## 6) 당신의 FX–이익–브랜드 모델에 그대로 적용하면

* CLD(온톨로지)로 구조를 합의하고
* 상충 링크를 “레짐/세그먼트/가중합”으로 운영화하고
* MindsDB로 각 로컬 함수 강도를 학습해서
* Neo4j에서 경로 기반 설명과 함께 What-if를 실행

➡️ 이건 충분히 제품/플랫폼으로 만들 수 있는 구조입니다.

---

원하면, 다음 중 하나를 바로 만들어 드릴게요(질문 없이 제가 결정해도 됨).

1. **CLD → Stock/Flow 모델로 변환한 정식 수식 세트** (브랜드/스트레스형)
2. **상충 링크를 레짐/혼합/세그먼트로 처리하는 템플릿** (Neo4j 표현 포함)
3. **What-if 시뮬레이션 결과 리포트 포맷** (경영진용: Pareto + 민감도)

어느 걸로 갈까요?



-- 

좋아요. **“CLD/온톨로지(Neo4j) + MindsDB(데이터 기반 계수 추정) + 시뮬레이션 엔진”**에서,
말씀하신 **데이터 기반 추정(링크 계수/탄력도/지연)**이 **어떻게 ‘실제로’ 돌아가게 만들지**를 구현 관점으로 구체화해볼게요.

아래는 **바로 개발 티켓으로 쪼갤 수 있는 수준**으로 씁니다.

---

# 0) 핵심 아이디어 (한 줄)

CLD의 각 화살표(링크)를 **“학습 가능한 Edge(=Link Model)”**로 만들고,
그 Edge가 **MindsDB 모델을 참조**하여 시뮬레이션 시점마다 `predict()`로 값을 계산하게 만든다.

---

# 1) Neo4j에서 “링크(화살표)”를 학습 단위로 만드는 스키마

## 1.1 노드/관계 타입

* `(:Variable)` : Stress, GreenSpace, Brand, Demand, Profit 등
* `(:Link)` : “A -> B” 를 하나의 객체로 표현 (학습/버전/메타를 담기 위해)
* `(:Model)` : MindsDB에 생성된 실제 ML 모델 메타
* `(:Dataset)` : 학습 데이터 정의(쿼리/뷰/윈도우/라벨 등)

## 1.2 관계

* `(A:Variable)-[:FROM]->(L:Link)-[:TO]->(B:Variable)`
* `(L)-[:TRAINED_BY]->(D:Dataset)`
* `(L)-[:PREDICTED_BY]->(M:Model)`

## 1.3 Link 노드에 들어갈 핵심 속성

* `polarity`: +1 / -1  (CLD의 +/−)
* `type`: linear / GAM / xgboost / bayesian / state_space
* `lag_max`: 최대 지연(예: 12개월)
* `regime_key`: 안전/젠트리/커뮤니티 등 조건부 스위치 키(있으면)
* `feature_spec`: 어떤 변수/파생변수를 쓸지 JSON
* `model_name`: MindsDB 모델 이름(배포된 모델)
* `version`, `trained_at`, `metrics`

---

# 2) “학습 데이터(Training Set)”를 어떻게 만들까

## 2.1 기본 원칙

각 링크 `A -> B`마다 “지도학습” 형태로 학습셋을 만듭니다.

* **Target (y)**: B(t)
* **Features (X)**: A(t), A(t-1..t-k), control 변수들

즉,

> B(t) = f( A(t), A(t-1), …, A(t-k), Controls(t) )

여기서 k가 바로 **지연(Delay)** 후보입니다.

---

## 2.2 Feature Engineering (필수 파생변수)

탄력도/민감도를 위해 아래 파생변수를 기본으로 만듭니다.

* `delta_A = A(t) - A(t-1)`
* `pct_A = (A(t) - A(t-1)) / A(t-1)` (or log-diff)
* `rolling_mean_A_3`, `rolling_mean_A_6`
* `A_lag_1..A_lag_k`
* `shock_A = abs(pct_A)` (변동성/충격)

**지연 추정**을 하려면 `A_lag_i`가 핵심이에요.

---

## 2.3 학습셋 생성 SQL 예시 (Postgres 기준)

예를 들어 `GreenSpace -> Stress` 링크를 학습한다고 치면:

```sql
WITH base AS (
  SELECT
    month,
    green_space_index AS green,
    stress_index      AS stress,
    safety_index,
    rent_index
  FROM kpi_monthly
),
lags AS (
  SELECT
    month,
    stress AS y_stress,

    green AS x_green_0,
    lag(green,1) OVER (ORDER BY month) AS x_green_1,
    lag(green,2) OVER (ORDER BY month) AS x_green_2,
    lag(green,3) OVER (ORDER BY month) AS x_green_3,

    (green - lag(green,1) OVER (ORDER BY month)) AS delta_green,
    (green / NULLIF(lag(green,1) OVER (ORDER BY month),0) - 1) AS pct_green,

    safety_index,
    rent_index
  FROM base
)
SELECT * FROM lags
WHERE x_green_3 IS NOT NULL;
```

이 쿼리 자체를 Neo4j의 `Dataset.query_sql`로 저장해두고 재생성 가능하게 합니다.

---

# 3) MindsDB에서 링크별 모델을 어떻게 학습시키나

## 3.1 MindsDB 모델 생성 개념

MindsDB에서 “predictor”를 만들 때, 학습셋(테이블/뷰)을 지정하고 target을 지정합니다.

### (A) 지연 포함 모델

* Target: `y_stress`
* Features: `x_green_0..x_green_k`, `controls`

### (B) 정책/레짐 포함 모델

* 조건부 상충 관계를 반영하려면 **regime 변수**를 feature로 넣습니다.

  * `safety_index`, `rent_index` 같은 것
  * 또는 `community_type` 같은 범주

---

## 3.2 MindsDB 학습 SQL (개념 예시)

(MindsDB 문법은 배포/버전에 따라 조금 다를 수 있어서, 아래는 “형태”를 보여주는 구현 템플릿입니다.)

```sql
CREATE MODEL mindsdb.green_to_stress_model
FROM mydb
  (SELECT * FROM training_green_to_stress)
PREDICT y_stress
USING
  engine = 'lightgbm',
  time_column = 'month',
  window = 12;
```

또는 단순 회귀라면:

```sql
CREATE MODEL mindsdb.green_to_stress_model
FROM mydb (SELECT * FROM training_green_to_stress)
PREDICT y_stress;
```

핵심은:

* 모델 이름을 **Link.model_name**에 박아 넣고
* 시뮬레이터가 이 모델을 호출하도록 합니다.

---

# 4) “탄력도/민감도”를 모델에서 어떻게 뽑아내나 (진짜 구현 포인트)

여기서 많이들 막힙니다. “계수”를 어떻게 뽑느냐.

## 4.1 선형/베이지안 회귀라면 (가장 깔끔)

* 계수(β)가 곧 민감도
* `lag별 β`를 보면 delay가 보임

예:

* β_green_lag2가 가장 크면
  → “2개월 지연 효과가 최대”

## 4.2 트리/GBM 모델이라면 (현실적으로 많이 씀)

* “계수” 대신 **부분효과(Partial Dependence) / ICE / SHAP**로 민감도를 정의합니다.

실전 정의(추천):

* **Local elasticity at baseline**

  * 기준 상태 x에서 A를 +1% 바꿨을 때 B의 변화량을 계산
* 이것을 수치 미분으로 구합니다.

### 수치 미분 방식 (시뮬레이터 내부에서 구현 가능)

* `y0 = predict(x)`
* `y1 = predict(x with A*=1.01)`
* `elasticity ≈ (y1 - y0) / y0 / 0.01`

이렇게 하면 “모델이 어떤 종류든” 탄력도를 통일된 방식으로 얻습니다.

> 즉, “계수”는 꼭 회귀계수여야 하는 게 아니라
> **정책 시뮬레이션에 필요한 ‘국소 민감도’**면 됩니다.

---

# 5) “지연(Delay)”을 어떻게 데이터로 추정하나 (구체 루틴)

## 5.1 가장 단순하고 강력한 방식: Lag Scan

링크마다 `k=0..K`에 대해 모델을 여러 번 학습해보고,

* 성능(AIC/BIC/RMSE) 또는
* 설명력
  이 가장 좋은 lag 조합을 선택합니다.

### 구현 플로우

1. Dataset generator가 `A_lag_0..A_lag_k`를 만들어 줌
2. MindsDB 모델을 k별로 생성 (자동화)
3. 성능을 비교해 best k를 선택
4. Link.lag_selected = best k 저장

> 이건 완전히 자동화 가능합니다.

## 5.2 더 고급: Distributed Lag Model

* `A_lag_0..K`를 한 번에 넣고
* 중요도가 큰 lag를 선택
* 트리 모델/선형 모델 모두 가능

---

# 6) 시뮬레이션 엔진에서 MindsDB 모델이 “진짜로” 어떻게 쓰이나

## 6.1 런타임 상태 업데이트

시뮬레이터는 시간 t에서 각 Variable을 업데이트할 때:

1. Neo4j에서 해당 Variable로 들어오는 Link들을 찾음
2. 각 Link는 MindsDB model_name을 가지고 있음
3. 현 상태에서 Feature vector를 구성
4. MindsDB `predict()` 호출
5. 결과를 Variable(t+1)에 반영
6. 동시에 “trace”(근거)를 저장

---

## 6.2 상충 링크(+와 −)는 어떻게 반영되나

실전에서는 같은 A->B에 대해 Link가 2개 있을 수 있습니다.

* Link#1: “녹지 증가가 스트레스를 낮춤” (−)
* Link#2: “녹지 증가가 스트레스를 높임” (+)

이 두 개를 “레짐”으로 분기합니다.

### 레짐 분기 규칙 예

* safety_index < threshold → Link#2 활성
* rent_index 상승률 > threshold → Link#2 활성
* otherwise → Link#1 활성

이 분기 규칙도 Neo4j에 `Link.regime_rule`로 저장하고,
시뮬레이터가 실행 시 평가합니다.

---

# 7) 구현 티켓 단위로 쪼개기 (바로 개발 가능)

### EPIC A: Ontology & Link Registry

* A1. Variable/Link/Model/Dataset 스키마 설계
* A2. CLD 업로드 → Link 객체 자동 생성

### EPIC B: Dataset Generator

* B1. KPI time-series 표준 스키마 정의(월 단위)
* B2. lag/pct/delta 파생변수 자동 생성 SQL 템플릿
* B3. Dataset.query_sql 저장 & 실행

### EPIC C: MindsDB Trainer

* C1. Link별 모델 생성 자동화
* C2. lag scan 자동화 + best lag 선택
* C3. 성능/버전 Neo4j 기록

### EPIC D: Simulation Runtime

* D1. Neo4j에서 그래프 순회하여 업데이트 순서 생성
* D2. MindsDB predict 호출 어댑터
* D3. trace 저장(어떤 링크/어떤 입력이 결과에 기여했나)
* D4. what-if UI/API

---

# 8) 현실적인 체크포인트(중요)

* 데이터가 충분한 링크만 먼저 자동 추정
* 부족한 링크는 “prior/default 함수(선형/휴리스틱)”로 시작
* 시간이 지나면서 점점 ML로 대체

이렇게 해야 제품이 “처음부터 완벽한 데이터”를 요구하지 않고 굴러갑니다.

---
