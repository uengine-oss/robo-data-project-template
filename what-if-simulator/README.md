# What-if Simulator

**Explainable KPI Simulation Platform**

환율(FX) 변화가 이익률과 브랜드 가치에 미치는 영향을 시뮬레이션하고, 인과 경로를 통해 설명 가능한 결과를 제공하는 플랫폼입니다.

---

## 📋 목차

1. [개요](#개요)
2. [시스템 아키텍처](#시스템-아키텍처)
3. [핵심 개념](#핵심-개념)
4. [컴포넌트 상세](#컴포넌트-상세)
5. [데이터 흐름](#데이터-흐름)
6. [설치 및 실행](#설치-및-실행)
7. [사용 방법](#사용-방법)
8. [파일 구조](#파일-구조)
9. [확장 가이드](#확장-가이드)

---

## 개요

### 문제 정의

기업은 환율 변화에 대해 다음을 동시에 알고 싶어합니다:

- 단기적으로 **이익률/마진은 어떻게 변하는가**
- 중·장기적으로 **브랜드 가치와 수요는 어떻게 훼손되거나 강화되는가**
- 이 두 결과 사이의 **트레이드오프는 어떤 경로를 통해 발생하는가**

### 솔루션

```
이 시스템은 예측 엔진이 아니라
'정책을 실험하는 구조화된 의사결정 실험실'입니다.

ML은 숫자를 계산하고,
Neo4j 온톨로지는 근거를 만들며,
시뮬레이션은 전략을 검증합니다.
```

---

## 시스템 아키텍처

### 전체 구조

```
┌─────────────────────────────────────────────────────────────────┐
│                        What-if Simulator                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────────────┐ │
│  │   Neo4j     │    │   MindsDB   │    │  Simulation Engine  │ │
│  │  (Ontology) │◄──▶│ (ML Models) │◄──▶│   (Python Core)     │ │
│  └──────┬──────┘    └──────┬──────┘    └──────────┬──────────┘ │
│         │                  │                      │             │
│         ▼                  ▼                      ▼             │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────────────┐ │
│  │ CLD Graph   │    │ Predictions │    │  Scenario Results   │ │
│  │ (인과관계)   │    │ (예측값)     │    │  (KPI + 경로)        │ │
│  └─────────────┘    └─────────────┘    └─────────────────────┘ │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 기술 스택

| 구성요소 | 기술 | 역할 |
|---------|------|------|
| **그래프 DB** | Neo4j | 인과관계(CLD) 저장, 경로 분석 |
| **ML 플랫폼** | MindsDB | 예측 모델 학습/서빙 |
| **시뮬레이션** | Python | 상태 업데이트, 시나리오 실행 |
| **데이터** | CSV/MySQL | KPI 시계열 데이터 |

---

## 핵심 개념

### 1. Causal Loop Diagram (CLD)

인과관계 그래프로, 변수들 사이의 영향 관계를 표현합니다.

```
           ┌──────────┐
     (+)   │ FX_RATE  │
    ┌──────┤ (환율)    ├──────┐
    │      └──────────┘      │
    ▼                        │
┌──────────┐          ┌──────────┐
│  COGS    │──(+)────▶│  PRICE   │
│ (원가)    │          │ (가격)    │
└──────────┘          └────┬─────┘
                           │(-)
                           ▼
┌──────────┐          ┌──────────┐
│  BRAND   │◀──(-)────│ DEMAND   │
│ (브랜드)  │──(+)────▶│ (수요)    │
└──────────┘          └────┬─────┘
                           │(+)
                           ▼
                     ┌──────────┐
                     │  PROFIT  │
                     │ (이익)    │
                     └──────────┘
```

**극성(Polarity)**:
- `(+)`: 같은 방향 변화 (A↑ → B↑)
- `(-)`: 반대 방향 변화 (A↑ → B↓)

### 2. 노드 타입

| 타입 | 설명 | 예시 |
|------|------|------|
| **Driver** | 외생/정책 변수 | FX_RATE, PASS_THROUGH, MKT_SPEND |
| **State** | 시간에 따라 변하는 상태 | COGS, PRICE, DEMAND, BRAND_EQUITY |
| **KPI** | 최종 성과 지표 | SHORT_TERM_MARGIN, LONG_TERM_BRAND_VALUE |
| **Link** | 학습 가능한 관계 | fx_to_cogs_model |

### 3. Stock vs Flow

```python
# Flow 변수: 즉시 계산
COGS = 100 + 0.05 * (FX_RATE - 1200)
PRICE = COGS * (1 + PASS_THROUGH * 0.3)

# Stock 변수: 누적/감가상각 (시간 지연)
BRAND_t+1 = BRAND_t * 0.98  # 2% 자연 감소
           + 0.1 * CSAT     # 고객만족 기여
           - 10 * REFUND    # 환불율 손상
           + 0.02 * MKT     # 마케팅 기여
```

---

## 컴포넌트 상세

### 1. `config.py` - 설정 관리

```python
@dataclass
class Neo4jConfig:
    uri: str = "bolt://localhost:7687"
    user: str = "neo4j"
    password: str = "12345analyzer"
    database: str = "neo4j"

@dataclass
class MindsDBConfig:
    http_url: str = "http://127.0.0.1:47334"
    api_endpoint: str = "/api/sql/query"
```

**역할**: 
- Neo4j, MindsDB 연결 정보 관리
- 시뮬레이션 기본값 설정

---

### 2. `ontology_loader.py` - Neo4j 온톨로지 관리

```python
class OntologyLoader:
    def create_driver_nodes(self):
        """Driver 노드 생성 (외생/정책 변수)"""
        drivers = [
            {"name": "FX_RATE", "type": "exogenous", ...},
            {"name": "PASS_THROUGH", "type": "policy", ...},
            ...
        ]
    
    def create_causal_relationships(self):
        """CAUSES 관계 생성"""
        # (source, target, polarity, lag, description)
        causal_links = [
            ("FX_RATE", "COGS", "+", 0, "환율 상승 → 매출원가 증가"),
            ("COGS", "PRICE", "+", 0, "원가 상승 → 가격 조정 압력"),
            ("PRICE", "DEMAND", "-", 0, "가격 상승 → 수요 감소"),
            ...
        ]
```

**Neo4j에 생성되는 그래프**:

```cypher
// 노드
(:SimDriver {name: "FX_RATE", type: "exogenous"})
(:SimState {name: "COGS", is_stock: false})
(:SimState {name: "BRAND_EQUITY", is_stock: true})
(:SimKPI {name: "SHORT_TERM_MARGIN"})

// 관계
(fx:SimDriver)-[:CAUSES {polarity: "+", lag: 0}]->(cogs:SimState)
(brand:SimState)-[:MEASURED_AS]->(kpi:SimKPI)
```

---

### 3. `mindsdb_connector.py` - MindsDB 연동

```python
class MindsDBConnector:
    def execute_query(self, query: str) -> Dict[str, Any]:
        """SQL 쿼리 실행"""
        response = requests.post(
            self.api_url,
            json={"query": query}
        )
        return response.json()
    
    def predict(self, model_name: str, input_data: Dict) -> Dict:
        """모델 예측 실행"""
        query = f"SELECT * FROM mindsdb.{model_name} WHERE ..."
        return self.execute_query(query)


class SimulationModelAdapter:
    """MindsDB 모델 또는 기본 수식 사용"""
    
    def predict(self, model_name: str, inputs: Dict) -> Dict:
        # MindsDB 연결 시 먼저 시도
        if self.use_mindsdb:
            result = self.mindsdb.predict(model_name, inputs)
            if result:
                return result
        
        # 기본 수식 폴백
        return self.default_formulas[model_name](inputs)
```

**MindsDB 모델 생성**:

```sql
-- 환율 → 매출원가 모델
CREATE MODEL mindsdb.whatif_cogs_model
FROM files (SELECT fx_rate, cogs FROM kpi_monthly)
PREDICT cogs;

-- 다요인 → 수요 모델
CREATE MODEL mindsdb.whatif_demand_model
FROM files (SELECT price, brand_equity, loyalty, demand FROM kpi_monthly)
PREDICT demand;
```

---

### 4. `simulation_engine.py` - 시뮬레이션 코어

```python
class CausalGraph:
    """Neo4j에서 로드한 인과 그래프"""
    
    def load_from_neo4j(self):
        """그래프 로드"""
        # 노드 로드
        self.nodes = session.run("MATCH (n:SimDriver|SimState|SimKPI) ...")
        
        # 관계 로드
        self.edges = session.run("MATCH (a)-[r:CAUSES]->(b) ...")
    
    def get_update_order(self) -> List[str]:
        """위상 정렬로 업데이트 순서 결정"""
        # BFS 기반 위상 정렬
        # Driver → 의존성 없는 노드 → 의존성 있는 노드 순서


class SimulationEngine:
    def run_simulation(self, scenario: SimulationScenario):
        """시뮬레이션 실행"""
        
        for t in range(scenario.time_steps):
            # 1. Driver 값 설정 (외생 변수)
            current_drivers = {
                "FX_RATE": scenario.fx_rate_schedule[t],
                "PASS_THROUGH": scenario.pass_through,
                ...
            }
            
            # 2. 그래프 순회하며 각 노드 업데이트
            for node in self.graph.get_update_order():
                new_value = self._update_node(node, current_drivers, t)
                self.states[node] = new_value
            
            # 3. 히스토리 저장
            for state, value in self.states.items():
                self.state_history[state].append(value)
        
        # 4. KPI 계산
        return self._calculate_kpis()
```

**상태 업데이트 로직**:

```python
def _apply_update_formula(self, node: str, drivers: Dict, t: int):
    if node == "COGS":
        # COGS = 100 + 0.05 * (FX - 1200)
        fx = drivers.get("FX_RATE", 1200)
        return 100 + 0.05 * (fx - 1200)
    
    elif node == "BRAND_EQUITY":
        # Stock 변수: 누적/감가상각
        prev = self.states.get("BRAND_EQUITY", 50)
        csat = self.states.get("CSAT", 0.75)
        refund = self.states.get("REFUND_RATE", 0.05)
        mkt = drivers.get("MKT_SPEND", 100)
        
        new_val = prev * (1 - 0.02)  # 감가상각
        new_val += 0.1 * (csat - 0.5)  # CSAT 기여
        new_val += 0.02 * (mkt - 100) / 100 * 10  # 마케팅
        new_val -= 10 * refund  # 환불율 손상
        
        return max(0, min(100, new_val))
```

---

### 5. `test_mindsdb_simulation.py` - MindsDB 기반 시뮬레이션

```python
class MindsDBPredictor:
    """MindsDB 모델을 통한 예측"""
    
    def predict_cogs(self, fx_rate: float) -> float:
        result = run_query(
            f"SELECT cogs FROM mindsdb.whatif_cogs_model WHERE fx_rate = {fx_rate}"
        )
        return float(result["data"][0][0])
    
    def predict_demand(self, price, brand_equity, loyalty) -> float:
        result = run_query(
            f"""SELECT demand FROM mindsdb.whatif_demand_model 
                WHERE price = {price} 
                AND brand_equity = {brand_equity} 
                AND loyalty = {loyalty}"""
        )
        return float(result["data"][0][0])


class MindsDBSimulator:
    def run_scenario(self, config: ScenarioConfig):
        for t in range(config.time_steps):
            # MindsDB 모델로 예측
            state.cogs = self.predictor.predict_cogs(fx)
            state.demand = self.predictor.predict_demand(
                state.price, state.brand_equity, state.loyalty
            )
            ...
```

---

## 데이터 흐름

### 1. 온톨로지 로드 흐름

```
┌─────────────────┐
│ ontology_loader │
│     .py         │
└────────┬────────┘
         │ Cypher 쿼리
         ▼
┌─────────────────┐     ┌─────────────────────────────────┐
│     Neo4j       │────▶│ 노드: SimDriver, SimState, SimKPI │
│   (localhost    │     │ 관계: CAUSES, MEASURED_AS        │
│    :7687)       │     └─────────────────────────────────┘
└─────────────────┘
```

### 2. 모델 학습 흐름

```
┌─────────────────┐
│ kpi_monthly.csv │
│  (36개월 데이터)  │
└────────┬────────┘
         │ HTTP PUT
         ▼
┌─────────────────┐
│    MindsDB      │
│  files 스토리지  │
└────────┬────────┘
         │ CREATE MODEL
         ▼
┌─────────────────────────────────────────────┐
│ ML 모델들                                    │
│ • whatif_cogs_model    (FX → COGS)         │
│ • whatif_demand_model  (Price/Brand → Demand) │
│ • whatif_brand_model   (다요인 → Brand)      │
│ • whatif_profit_model  (Price/Demand → Profit) │
└─────────────────────────────────────────────┘
```

### 3. 시뮬레이션 실행 흐름

```
┌──────────────────┐
│ ScenarioConfig   │
│ • fx_schedule    │
│ • pass_through   │
│ • mkt_spend      │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐    ┌─────────────────┐
│ SimulationEngine │◄──▶│     Neo4j       │
│                  │    │ (그래프 순회)     │
└────────┬─────────┘    └─────────────────┘
         │
         │ predict()
         ▼
┌──────────────────┐
│    MindsDB       │
│  (ML 예측)        │
└────────┬─────────┘
         │
         ▼
┌──────────────────────────────────────────┐
│ SimulationResult                          │
│ • state_history: {COGS: [...], ...}      │
│ • kpi_values: {SHORT_TERM_MARGIN: 0.15}  │
│ • top_causal_paths: [FX→COGS→PRICE→...]  │
└──────────────────────────────────────────┘
```

### 4. 시간 루프 상세

```
t=1:
  FX_RATE=1270 (외생)
       │
       ▼ predict_cogs()
  COGS=107.6
       │
       ▼ 수식
  PRICE=123.8
       │
       ▼ predict_demand()
  DEMAND=91.1
       │
       ▼ predict_profit()
  PROFIT=1502
       │
       ▼ Stock 업데이트
  BRAND_EQUITY=49.5

t=2:
  FX_RATE=1270
       │
       ▼
  (이전 상태 기반 계산)
       ...
```

---

## 설치 및 실행

### 사전 요구사항

- **Python 3.9+**
- **Neo4j Desktop** (bolt://localhost:7687)
- **MindsDB** (http://localhost:47334)

### 1. 의존성 설치

```bash
cd what-if-simulator
pip install -r requirements.txt
```

### 2. Neo4j 연결 확인

```bash
# Neo4j Desktop에서 데이터베이스 시작
# 비밀번호: 12345analyzer
```

### 3. 온톨로지 로드

```bash
python ontology_loader.py
```

**출력**:
```
✓ 4개 Driver 노드 생성 완료
✓ 12개 State 노드 생성 완료
✓ 2개 KPI 노드 생성 완료
✓ 21개 CAUSES 관계 생성 완료
```

### 4. MindsDB 모델 설정

```bash
python setup_mindsdb_models.py
```

**출력**:
```
✅ CSV 파일 업로드 성공!
✅ 모델 생성: whatif_cogs_model
✅ 모델 생성: whatif_demand_model
⏳ 학습 진행 중...
```

### 5. 시뮬레이션 실행

```bash
# 기본 수식 기반 시뮬레이션
python test_simulation.py

# MindsDB 모델 기반 시뮬레이션
python test_mindsdb_simulation.py
```

---

## 사용 방법

### 시나리오 정의

```python
from simulation_engine import SimulationScenario

# 환율 급등 시나리오
fx_shock = [1270.0] * 3 + [1380.0] * 9  # 4개월차부터 급등

scenario = SimulationScenario(
    name="FX_Shock_MarketingBoost",
    description="환율 급등 + 마케팅 130%",
    time_steps=12,
    fx_rate_schedule=fx_shock,
    pass_through=0.5,      # 가격 전가율 50%
    mkt_spend=130.0,       # 마케팅 130%
    service_level=0.8      # 서비스 수준 80%
)
```

### 시뮬레이션 실행

```python
from simulation_engine import SimulationEngine

engine = SimulationEngine()
engine.initialize()

result = engine.run_simulation(scenario)

print(f"단기 마진: {result.kpi_values['SHORT_TERM_MARGIN']:.2%}")
print(f"장기 브랜드: {result.kpi_values['LONG_TERM_BRAND_VALUE']:.2f}")
```

### 시나리오 비교

```python
scenarios = create_default_scenarios()
comparison = engine.compare_scenarios(scenarios)

for scenario_name, data in comparison.items():
    print(f"{scenario_name}: {data['kpis']}")
```

### 인과 경로 분석

```python
loader = OntologyLoader()
paths = loader.get_causal_paths("FX_RATE", "BRAND_EQUITY")

for path in paths:
    print(f"경로: {' → '.join(path['nodes'])}")
    # FX_RATE → COGS → PRICE → PRICE_VOLATILITY → BRAND_EQUITY
```

---

## 파일 구조

```
what-if-simulator/
│
├── PRD.md                         # 제품 요구사항 문서
├── README.md                      # 이 문서
├── requirements.txt               # Python 의존성
│
├── # 설정
├── config.py                      # Neo4j/MindsDB 연결 설정
│
├── # 온톨로지
├── ontology_loader.py             # Neo4j CLD 그래프 생성
│
├── # MindsDB 연동
├── kpi_monthly.csv                # 36개월 KPI 샘플 데이터
├── setup_sample_data.py           # MySQL 데이터 설정 (대안)
├── setup_mindsdb_models.py        # MindsDB 모델 학습
├── mindsdb_connector.py           # MindsDB API 클라이언트
│
├── # 시뮬레이션 엔진
├── simulation_engine.py           # 기본 시뮬레이션 로직
├── edge_based_simulation.py       # ⭐ Edge 기반 시뮬레이션 (PRD 핵심)
├── test_simulation.py             # 기본 시뮬레이션 테스트
├── test_mindsdb_simulation.py     # MindsDB 기반 시뮬레이션
│
└── # 결과
    ├── simulation_results.json           # 기본 시뮬레이션 결과
    ├── mindsdb_simulation_results.json   # MindsDB 시뮬레이션 결과
    └── edge_simulation_results.json      # Edge 기반 시뮬레이션 결과
```

---

## 확장 가이드

### 1. 새로운 변수 추가

**1) Neo4j에 노드 추가**:

```python
# ontology_loader.py에 추가
states = [
    ...
    {"name": "NEW_VARIABLE", "description": "새 변수", "unit": "index", "is_stock": False},
]
```

**2) 인과관계 추가**:

```python
causal_links = [
    ...
    ("EXISTING_VAR", "NEW_VARIABLE", "+", 0, "기존 변수 → 새 변수"),
]
```

**3) 업데이트 수식 추가**:

```python
# simulation_engine.py의 _apply_update_formula에 추가
elif node == "NEW_VARIABLE":
    return some_calculation(...)
```

### 2. 새로운 MindsDB 모델 추가

**1) 학습 데이터 준비**:

```csv
# kpi_monthly.csv에 컬럼 추가
...,new_feature,new_target
```

**2) 모델 생성**:

```sql
CREATE MODEL mindsdb.whatif_new_model
FROM files (SELECT new_feature, new_target FROM kpi_monthly)
PREDICT new_target;
```

**3) 예측 함수 추가**:

```python
# mindsdb_connector.py에 추가
def predict_new_target(self, new_feature: float) -> float:
    result = run_query(
        f"SELECT new_target FROM mindsdb.whatif_new_model WHERE new_feature = {new_feature}"
    )
    return float(result["data"][0][0])
```

### 3. 레짐(Regime) 분기 추가

상충 관계가 있는 경우 조건부 로직 구현:

```python
def _apply_update_formula(self, node: str, drivers: Dict, t: int):
    if node == "STRESS":
        safety = self.states.get("SAFETY_INDEX", 0.5)
        green = self.states.get("GREEN_SPACE", 50)
        
        # 레짐 분기: 안전도에 따라 다른 효과
        if safety < 0.3:
            # 안전하지 않으면 녹지공간이 오히려 스트레스 증가
            return base_stress + 0.1 * green
        else:
            # 안전하면 녹지공간이 스트레스 감소
            return base_stress - 0.1 * green
```

### 4. 시각화 추가

```python
import matplotlib.pyplot as plt

def plot_scenario_comparison(results: Dict):
    fig, axes = plt.subplots(2, 2, figsize=(12, 10))
    
    for name, result in results.items():
        # PROFIT 추이
        axes[0, 0].plot(result["history"]["profit"], label=name)
        # BRAND_EQUITY 추이
        axes[0, 1].plot(result["history"]["brand_equity"], label=name)
    
    axes[0, 0].set_title("Profit Over Time")
    axes[0, 1].set_title("Brand Equity Over Time")
    plt.legend()
    plt.savefig("scenario_comparison.png")
```

---

---

## Edge-Based Simulation (PRD 핵심 원칙)

### 기존 방식 vs Edge-Based 방식

```
❌ 기존 방식: 하나의 대형 모델
   whatif_demand_model(price, brand, loyalty) → demand
   
   문제점: 
   - 개별 관계의 기여도를 알 수 없음
   - 인과 경로 추적 불가
   - 모델 교체/업데이트 어려움

✅ Edge-Based 방식: 관계별 소형 모델
   edge_price_demand(price) → demand 효과
   edge_brand_demand(brand) → demand 효과
   edge_loyalty_demand(loyalty) → demand 효과
   
   → 각 효과를 합산하여 최종 demand 계산
```

### 핵심 구조

```python
@dataclass
class EdgeModel:
    """단일 Edge(인과관계)에 대한 모델"""
    edge_id: str        # "FX_RATE_to_COGS"
    source: str         # "FX_RATE"
    target: str         # "COGS"
    polarity: str       # "+" or "-"
    lag: int = 0        # 지연 (개월)
    
    # 모델 정보
    model_type: str = "linear"  # "linear", "mindsdb", "formula"
    coefficient: float = 0.05   # 탄력도/민감도
    model_name: str = None      # MindsDB 모델명
```

### 시뮬레이션 흐름

```
t=1: 외생 변수 설정
     FX_RATE = 1380
           │
           ▼
     각 Edge 효과 계산:
     ┌─────────────────────────────────────────┐
     │ Edge: FX_RATE → COGS                    │
     │   effect = 0.05 * (+1) * (1380 - 1200)  │
     │         = +9.0                          │
     └─────────────────────────────────────────┘
           │
           ▼
     COGS = baseline(100) + effect(9.0) = 109.0
           │
           ▼
     ┌─────────────────────────────────────────┐
     │ Edge: COGS → PRICE                      │
     │   effect = 1.0 * (+1) * (109 - 100)     │
     │         = +9.0                          │
     └─────────────────────────────────────────┘
           │
           ▼
     PRICE = f(COGS, PASS_THROUGH) = 125.3
           │
           ▼
     ... (그래프 순회 계속)
```

### Edge 기여도 분석

```
DEMAND에 대한 Edge 기여:
   ← PRICE:        -8.28   (가격 상승 → 수요 감소)
   ← BRAND_EQUITY: -19.20  (브랜드 하락 → 수요 감소)
   ← LOYALTY:      -24.00  (충성도 하락 → 수요 감소)
   ─────────────────────────
   총 효과:        -51.48
```

### 실행 방법

```bash
# Edge-Based 시뮬레이션 실행
python edge_based_simulation.py
```

### 결과 비교

| 시나리오 | 단기마진 | 장기브랜드 | 총이익 |
|---------|----------|------------|--------|
| **Baseline** | 13.04% | 13.69 | 12,048 |
| **FX_Shock** | 13.04% | 10.80 | 12,071 |
| **+ 가격전가 80%** | **19.35%** | 10.80 | **18,439** (+6,390) |
| **+ 마케팅 150%** | 13.04% | **39.27** | 15,817 (+3,768) |

### 인과 경로 분석

```
경로: FX_RATE → COGS → PRICE → PRICE_VOLATILITY → BRAND_EQUITY

   FX_RATE ─(+, β=0.05)─> COGS
       │
       ▼
   COGS ─(+, β=1.0)─> PRICE
       │
       ▼
   PRICE ─(+, β=0.01)─> PRICE_VOLATILITY
       │
       ▼
   PRICE_VOLATILITY ─(-, β=50.0)─> BRAND_EQUITY [lag=2개월]

해석: 환율 상승 → 원가 상승 → 가격 상승 → 가격 변동성 증가
      → 2개월 후 브랜드 가치 손상
```

### MindsDB Edge 모델 생성

각 Edge에 대해 개별 MindsDB 모델을 학습할 수 있습니다:

```sql
-- Edge: FX_RATE → COGS
CREATE MODEL mindsdb.edge_fx_cogs
FROM files (SELECT fx_rate, cogs FROM kpi_monthly)
PREDICT cogs;

-- Edge: PRICE → DEMAND
CREATE MODEL mindsdb.edge_price_demand
FROM files (SELECT price, demand FROM kpi_monthly)
PREDICT demand;

-- Edge: BRAND_EQUITY → DEMAND
CREATE MODEL mindsdb.edge_brand_demand
FROM files (SELECT brand_equity, demand FROM kpi_monthly)
PREDICT demand;
```

### 장점

1. **Explainability**: 각 Edge의 기여도를 정량적으로 파악
2. **Modularity**: 개별 관계 모델만 교체/업데이트 가능
3. **Traceability**: 결과가 어떤 경로를 통해 도출되었는지 추적
4. **Flexibility**: 새로운 관계 추가 용이

---

---

## 🔬 Causal Discovery (역방향 CLD 생성)

### 개요

**데이터로부터 인과관계를 자동으로 발견**하여 CLD를 역으로 생성하는 기능입니다.

기존 방식이 "전문가가 정의한 CLD → 시뮬레이션"이었다면,  
Causal Discovery는 "데이터 → 자동 CLD 추정 → 검증"의 역방향 접근입니다.

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│  Time Series    │───▶│ Causal Discovery│───▶│   Auto CLD      │
│  Data (CSV)     │    │   Algorithm     │    │   (Neo4j)       │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                              │
              ┌───────────────┼───────────────┐
              ▼               ▼               ▼
        ┌──────────┐   ┌──────────┐   ┌──────────┐
        │ Granger  │   │ Partial  │   │  상관     │
        │ Causality│   │ Corr.    │   │ 분석     │
        └──────────┘   └──────────┘   └──────────┘
```

### 사용되는 알고리즘

| 알고리즘 | 원리 | 장점 |
|---------|------|------|
| **Granger Causality** | X의 과거가 Y의 미래 예측에 도움이 되는가 | 시계열에 적합, 방향성 추론 |
| **Partial Correlation** | 다른 변수를 통제한 후의 상관 | 직접 관계 vs 간접 관계 구분 |
| **Correlation** | 단순 상관계수 | 빠른 초기 스크리닝 |

### 실행 방법

```bash
# 전체 파이프라인 실행
cd what-if-simulator
python reverse_cld_test.py

# 빠른 테스트 (상관관계만)
python reverse_cld_test.py --quick
```

### 실행 결과 예시

```
============================================================
🔬 Causal Discovery 시작
============================================================
📊 데이터: 36 행, 16 변수
🎯 유의수준: 0.05
📏 최소 상관: 0.35

✅ 최종 발견된 인과관계: 103개
============================================================

📊 발견된 Causal Loop Diagram (CLD)
---------------------------------------------------------------------
Source               →   Target                Strength    방향
---------------------------------------------------------------------
mkt_spend           →+   brand_equity            1.0000   positive
cogs                →+   price                   1.0000   positive
fx_rate             →+   cogs                    0.8724   positive
service_level       →+   csat                    0.9916   positive
...
```

### 생성되는 파일들

| 파일 | 내용 |
|------|------|
| `causal_discovery_results.json` | 발견된 모든 인과관계 (source, target, strength, method) |
| `influence_functions.json` | 각 Edge의 회귀 함수 (slope, intercept, R²) |
| `cld_visualization.png` | CLD 시각화 이미지 |

### 핵심 출력: 영향 함수

각 인과관계에 대해 선형 회귀 함수를 추정합니다:

```
📐 핵심 인과관계 수식:
   cogs = 0.0660 * fx_rate + 24.6651
      → R² = 0.7611 (좋음)
   
   csat = 0.7321 * service_level + 0.0818
      → R² = 0.9834 (좋음)
   
   demand = -0.4335 * price + 145.6672
      → R² = 0.1980 (약함) - 다른 요인도 영향
```

### PRD 정의 CLD와 비교

자동 발견된 CLD와 전문가가 정의한 CLD를 비교합니다:

```
🔍 기존 CLD와 비교:
   ✅ 일치: 15개 (데이터에서도 확인됨)
   ❌ 미발견: 2개 (통계적으로 유의하지 않음)
   🆕 새 발견: 68개 (검토 필요한 숨겨진 관계)
   
   📊 일치율: 88% (15/17)
```

### 피드백 루프 자동 탐지

CLD에서 피드백 루프를 자동으로 찾아냅니다:

```
🔄 피드백 루프 탐지: 76개 발견

[R] sales → loyalty → profit → delivery_time → demand → sales
    (Reinforcing: 양의 피드백, 성장 또는 붕괴 초래)

[B] sales → delivery_time → csat → demand → sales
    (Balancing: 음의 피드백, 안정화 작용)
```

### Neo4j에 자동 저장

발견된 관계는 Neo4j에 `INFERRED_CAUSES`로 저장됩니다:

```cypher
// 자동 생성된 Cypher
MATCH (s:Variable {name: 'fx_rate'})
MATCH (t:Variable {name: 'cogs'})
MERGE (s)-[r:INFERRED_CAUSES]->(t)
SET r.strength = 0.8724,
    r.method = 'correlation+granger',
    r.polarity = '+';
```

### 코드 구조

```python
# causal_discovery.py
class CausalDiscoveryEngine:
    def discover_correlations(self, data):
        """상관관계 기반 인과 후보 발견"""
    
    def discover_granger_causality(self, data):
        """Granger Causality 분석"""
    
    def discover_partial_correlations(self, data):
        """부분 상관 분석 (직접 관계 추정)"""
    
    def run_discovery(self, data, methods):
        """전체 파이프라인 실행"""

# cld_generator.py
class CLDGenerator:
    def build_graph_from_discovery(self, results):
        """NetworkX 그래프 구축"""
    
    def detect_feedback_loops(self):
        """피드백 루프 탐지"""
    
    def compare_with_existing_cld(self, existing):
        """기존 CLD와 비교"""
    
    def visualize(self, output_path):
        """CLD 시각화"""
    
    async def save_to_neo4j(self):
        """Neo4j에 저장"""
```

### 확장: 고급 알고리즘

다음 라이브러리들을 추가로 활용할 수 있습니다:

```bash
# 고급 Causal Discovery 라이브러리 설치
pip install lingam          # LiNGAM 알고리즘
pip install tigramite       # 시계열 인과 발견
pip install dowhy           # Microsoft DoWhy
pip install causal-learn    # CMU Causal Discovery
```

**LiNGAM** (Linear Non-Gaussian Acyclic Model):
```python
import lingam
model = lingam.DirectLiNGAM()
model.fit(data)
causal_order = model.causal_order_
adjacency = model.adjacency_matrix_
```

**Tigramite** (Time Series Causal Discovery):
```python
import tigramite
from tigramite.pcmci import PCMCI
pcmci = PCMCI(dataframe=df, cond_ind_test=parcorr)
results = pcmci.run_pcmci(tau_max=3)
```

---

## 🌐 REST API 서버 (신규)

### 개요

What-If Simulator는 이제 완전한 REST API 서버를 제공합니다. 이를 통해 웹 프론트엔드에서 Causal Discovery, 검증, MindsDB 비교, LLM 기반 설명 기능을 사용할 수 있습니다.

### 시작하기

```bash
# 의존성 설치
pip install -r requirements.txt

# API 서버 실행
python run_api.py

# 또는 직접 uvicorn 사용
uvicorn api.main:app --host 0.0.0.0 --port 8005 --reload
```

서버가 시작되면:
- **Direct URL**: http://localhost:8005
- **Gateway URL**: http://localhost:9000/api/gateway/whatif
- **Swagger Docs**: http://localhost:8005/docs

**API Gateway 라우팅**:
- 프론트엔드는 `/api/gateway/whatif/**` 경로를 통해 접근
- Gateway가 `/api/gateway/whatif/**` → `http://localhost:8005/api/**`로 라우팅

### 주요 API 엔드포인트

| 메서드 | 엔드포인트 | 설명 |
|--------|-----------|------|
| POST | `/api/discovery/search` | 자연어로 관련 데이터 발견 |
| POST | `/api/data/collect` | SQL 실행하여 데이터 수집 |
| POST | `/api/data/upload` | CSV 파일 업로드 |
| POST | `/api/causal/discover` | Causal Discovery 실행 |
| POST | `/api/causal/validate` | 모델 검증 결과 조회 |
| POST | `/api/mindsdb/compare` | MindsDB 모델과 비교 |
| POST | `/api/literacy/explain` | LLM 기반 설명 생성 |
| GET | `/api/sessions/{id}` | 세션 정보 조회 |

### 설정

`api/env_example.txt`를 `.env`로 복사하고 설정을 수정합니다:

```bash
# MySQL (물리 계층 데이터베이스)
WHATIF_MYSQL_HOST=localhost
WHATIF_MYSQL_PORT=3307
WHATIF_MYSQL_DATABASE=sample_db
WHATIF_MYSQL_USER=sampleuser
WHATIF_MYSQL_PASSWORD=samplepass123

# OpenAI (LLM Literacy)
OPENAI_API_KEY=sk-your-key
```

---

## 🎨 Vue3 프론트엔드 (신규)

### 개요

`robo-analyzer-vue3/src/components/whatif/` 폴더에 완전한 Vue3 프론트엔드가 구현되어 있습니다.

### 컴포넌트 구조

```
src/components/whatif/
├── WhatIfSimulator.vue    # 메인 컴포넌트 (5단계 워크플로우)
├── ScenarioInput.vue      # 시나리오 입력 UI
├── DataSelector.vue       # 데이터 선택/업로드 UI
├── CausalDiscovery.vue    # 인과관계 발견 결과 시각화
├── ValidationCompare.vue  # 검증 및 MindsDB 비교
├── DataLiteracy.vue       # LLM 설명 생성 UI
└── index.ts               # 컴포넌트 exports
```

### 워크플로우

1. **시나리오 정의**: 예측하고자 하는 내용을 자연어로 서술
2. **데이터 선택**: Text2SQL로 관련 테이블 발견 또는 CSV 업로드
3. **인과관계 발견**: Correlation, Granger Causality 분석
4. **검증 및 비교**: Train/Test 분할 검증, MindsDB 모델과 비교
5. **결과 해석**: LLM이 분석 결과를 자연어로 설명

### 사용 방법

```vue
<template>
  <WhatIfSimulator />
</template>

<script setup>
import { WhatIfSimulator } from '@/components/whatif'
</script>
```

### API 서비스

`src/services/whatif-api.ts`에서 API 호출을 관리합니다:

```typescript
import { whatifApi } from '@/services/whatif-api'

// 데이터 발견
const result = await whatifApi.discoverData("환율이 수익에 미치는 영향")

// Causal Discovery 실행
const causal = await whatifApi.runCausalDiscovery(sessionId, ['correlation', 'granger'])

// LLM 설명 생성
const explanation = await whatifApi.getExplanation(sessionId, 'summary', 'ko')
```

---

## 라이선스

내부 사용 목적으로 개발되었습니다.

---

## 참고 문헌

- **System Dynamics**: Sterman, J. D. (2000). Business Dynamics
- **Causal Inference**: Pearl, J. (2009). Causality
- **Causal Discovery**: Spirtes, P. et al. (2000). Causation, Prediction, and Search
- **MindsDB**: https://docs.mindsdb.com
- **Neo4j**: https://neo4j.com/docs
