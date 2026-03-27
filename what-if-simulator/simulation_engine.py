"""
Simulation Engine - 그래프 기반 What-if 시뮬레이션 엔진

Neo4j 인과 그래프를 순회하며 상태를 업데이트하고 
KPI 결과와 설명 가능한 경로(trace)를 생성합니다.
"""

from neo4j import GraphDatabase
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from collections import defaultdict
import json
from datetime import datetime

from config import neo4j_config, simulation_config
from mindsdb_connector import MindsDBConnector, SimulationModelAdapter


@dataclass
class SimulationScenario:
    """시뮬레이션 시나리오 정의"""
    name: str
    description: str = ""
    time_steps: int = 12
    
    # 외생 변수 시나리오 (시간별 값)
    fx_rate_schedule: List[float] = field(default_factory=lambda: [1200.0] * 12)
    
    # 정책 변수 (고정값 또는 시간별)
    pass_through: float = 0.5
    mkt_spend: float = 100.0
    service_level: float = 0.8
    
    # 초기 상태
    initial_states: Dict[str, float] = field(default_factory=dict)


@dataclass 
class SimulationTrace:
    """시뮬레이션 추적 정보"""
    time_step: int
    node: str
    old_value: float
    new_value: float
    caused_by: List[str]
    contribution: Dict[str, float]


@dataclass
class SimulationResult:
    """시뮬레이션 결과"""
    scenario_name: str
    time_steps: int
    
    # 시간별 상태 기록
    state_history: Dict[str, List[float]] = field(default_factory=dict)
    
    # KPI 결과
    kpi_values: Dict[str, float] = field(default_factory=dict)
    
    # 추적 정보
    traces: List[SimulationTrace] = field(default_factory=list)
    
    # 상위 기여 경로
    top_causal_paths: List[Dict] = field(default_factory=list)


class CausalGraph:
    """Neo4j에서 로드한 인과 그래프"""
    
    def __init__(self, driver):
        self.driver = driver
        self.nodes: Dict[str, Dict] = {}
        self.edges: List[Dict] = []
        self.adjacency: Dict[str, List[str]] = defaultdict(list)
        self.edge_info: Dict[Tuple[str, str], Dict] = {}
    
    def load_from_neo4j(self):
        """Neo4j에서 그래프 로드"""
        with self.driver.session(database=neo4j_config.database) as session:
            # 노드 로드
            result = session.run("""
                MATCH (n)
                WHERE n:SimDriver OR n:SimState OR n:SimKPI
                RETURN n.name as name, 
                       labels(n)[0] as label,
                       properties(n) as props
            """)
            for record in result:
                self.nodes[record["name"]] = {
                    "label": record["label"],
                    "props": record["props"]
                }
            
            # 관계 로드
            result = session.run("""
                MATCH (a)-[r:CAUSES]->(b)
                WHERE (a:SimDriver OR a:SimState) AND b:SimState
                RETURN a.name as source, 
                       b.name as target,
                       r.polarity as polarity,
                       r.lag as lag,
                       r.description as description
            """)
            for record in result:
                edge = {
                    "source": record["source"],
                    "target": record["target"],
                    "polarity": record["polarity"],
                    "lag": record["lag"] or 0,
                    "description": record["description"]
                }
                self.edges.append(edge)
                self.adjacency[record["source"]].append(record["target"])
                self.edge_info[(record["source"], record["target"])] = edge
            
            # KPI 측정 관계 로드
            result = session.run("""
                MATCH (s:SimState)-[r:MEASURED_AS]->(k:SimKPI)
                RETURN s.name as state, k.name as kpi
            """)
            self.kpi_measurements = [(r["state"], r["kpi"]) for r in result]
            
        print(f"✓ 그래프 로드: {len(self.nodes)} 노드, {len(self.edges)} 관계")
    
    def get_update_order(self) -> List[str]:
        """위상 정렬로 업데이트 순서 결정"""
        # 간단한 BFS 기반 위상 정렬
        in_degree = defaultdict(int)
        for edge in self.edges:
            in_degree[edge["target"]] += 1
        
        # Driver와 의존성 없는 노드부터 시작
        queue = []
        for name, info in self.nodes.items():
            if info["label"] == "SimDriver" or in_degree[name] == 0:
                if info["label"] != "SimKPI":
                    queue.append(name)
        
        order = []
        visited = set()
        
        while queue:
            node = queue.pop(0)
            if node in visited:
                continue
            visited.add(node)
            order.append(node)
            
            for target in self.adjacency[node]:
                in_degree[target] -= 1
                if in_degree[target] <= 0 and target not in visited:
                    queue.append(target)
        
        # State 노드만 반환 (Driver는 외생 변수)
        return [n for n in order if self.nodes.get(n, {}).get("label") == "SimState"]
    
    def get_incoming_edges(self, node: str) -> List[Dict]:
        """특정 노드로 들어오는 엣지 조회"""
        return [e for e in self.edges if e["target"] == node]


class SimulationEngine:
    """What-if 시뮬레이션 엔진"""
    
    def __init__(self):
        self.driver = GraphDatabase.driver(
            neo4j_config.uri,
            auth=(neo4j_config.user, neo4j_config.password)
        )
        self.graph = CausalGraph(self.driver)
        
        # MindsDB/수식 어댑터
        mindsdb = MindsDBConnector()
        self.model_adapter = SimulationModelAdapter(mindsdb)
        
        # 상태 변수 저장
        self.states: Dict[str, float] = {}
        self.state_history: Dict[str, List[float]] = defaultdict(list)
    
    def close(self):
        self.driver.close()
    
    def initialize(self):
        """시뮬레이션 초기화"""
        self.graph.load_from_neo4j()
        
        # 기본 초기값 설정
        self.default_initial_states = {
            "COGS": 100.0,
            "PRICE": 100.0,
            "PRICE_VOLATILITY": 0.0,
            "DEMAND": 100.0,
            "SALES": 10000.0,
            "PROFIT": 2000.0,
            "MARGIN": 0.2,
            "REFUND_RATE": 0.05,
            "DELIVERY_TIME": 3.0,
            "CSAT": 0.75,
            "BRAND_EQUITY": 50.0,
            "LOYALTY": 60.0,
        }
    
    def run_simulation(self, scenario: SimulationScenario) -> SimulationResult:
        """시뮬레이션 실행"""
        print(f"\n{'='*60}")
        print(f"🚀 시뮬레이션 시작: {scenario.name}")
        print(f"   시간 단계: {scenario.time_steps}개월")
        print(f"{'='*60}")
        
        # 결과 객체
        result = SimulationResult(
            scenario_name=scenario.name,
            time_steps=scenario.time_steps
        )
        
        # 초기 상태 설정
        self.states = self.default_initial_states.copy()
        self.states.update(scenario.initial_states)
        self.state_history = defaultdict(list)
        
        # 업데이트 순서 결정
        update_order = self.graph.get_update_order()
        print(f"\n📋 업데이트 순서: {' → '.join(update_order[:5])}...")
        
        # 시간 루프
        for t in range(scenario.time_steps):
            print(f"\n⏱️  t={t+1}")
            
            # Driver 값 설정 (외생/정책)
            current_drivers = {
                "FX_RATE": scenario.fx_rate_schedule[min(t, len(scenario.fx_rate_schedule)-1)],
                "PASS_THROUGH": scenario.pass_through,
                "MKT_SPEND": scenario.mkt_spend,
                "SERVICE_LEVEL": scenario.service_level,
            }
            
            # 각 State 노드 업데이트
            for node in update_order:
                old_value = self.states.get(node, 0)
                new_value, contributions = self._update_node(node, current_drivers, t)
                self.states[node] = new_value
                
                # 추적 기록
                if abs(new_value - old_value) > 0.01:
                    trace = SimulationTrace(
                        time_step=t,
                        node=node,
                        old_value=old_value,
                        new_value=new_value,
                        caused_by=list(contributions.keys()),
                        contribution=contributions
                    )
                    result.traces.append(trace)
            
            # 히스토리 저장
            for state, value in self.states.items():
                self.state_history[state].append(value)
            
            # 드라이버 히스토리도 저장
            for driver, value in current_drivers.items():
                self.state_history[driver].append(value)
        
        # 결과 저장
        result.state_history = dict(self.state_history)
        
        # KPI 계산
        result.kpi_values = self._calculate_kpis()
        
        # 상위 인과 경로 분석
        result.top_causal_paths = self._analyze_top_paths()
        
        print(f"\n{'='*60}")
        print(f"✅ 시뮬레이션 완료!")
        print(f"{'='*60}")
        
        return result
    
    def _update_node(self, node: str, drivers: Dict[str, float], t: int) -> Tuple[float, Dict[str, float]]:
        """단일 노드 업데이트"""
        incoming = self.graph.get_incoming_edges(node)
        contributions = {}
        
        if not incoming:
            return self.states.get(node, 0), contributions
        
        # 현재 값
        current_value = self.states.get(node, 0)
        new_value = current_value
        
        # 각 입력 엣지에 대해 기여도 계산
        for edge in incoming:
            source = edge["source"]
            polarity = edge["polarity"]
            lag = edge["lag"] or 0
            
            # 소스 값 가져오기 (지연 고려)
            if source in drivers:
                source_value = drivers[source]
            elif lag > 0 and t >= lag:
                history = self.state_history.get(source, [])
                if len(history) >= lag:
                    source_value = history[-(lag)]
                else:
                    source_value = self.states.get(source, 0)
            else:
                source_value = self.states.get(source, 0)
            
            # 기여도 계산 (단순화된 버전)
            contribution = self._calculate_contribution(node, source, source_value, polarity)
            contributions[source] = contribution
        
        # 모델 기반 업데이트 또는 수식 계산
        new_value = self._apply_update_formula(node, drivers, contributions, t)
        
        return new_value, contributions
    
    def _calculate_contribution(self, target: str, source: str, 
                                source_value: float, polarity: str) -> float:
        """기여도 계산"""
        # 기본 민감도 (실제로는 모델에서 학습)
        sensitivity = 0.1 if polarity == "+" else -0.1
        
        # 기준값 대비 변화
        base_values = {
            "FX_RATE": 1200.0,
            "PASS_THROUGH": 0.5,
            "MKT_SPEND": 100.0,
            "SERVICE_LEVEL": 0.8,
        }
        base = base_values.get(source, 100.0)
        deviation = (source_value - base) / base if base != 0 else 0
        
        return sensitivity * deviation
    
    def _apply_update_formula(self, node: str, drivers: Dict[str, float],
                              contributions: Dict[str, float], t: int) -> float:
        """업데이트 수식 적용"""
        current = self.states.get(node, 0)
        
        # 노드별 맞춤 로직
        if node == "COGS":
            # COGS = 100 + 0.05 * (FX - 1200)
            fx = drivers.get("FX_RATE", 1200)
            return 100 + 0.05 * (fx - 1200)
        
        elif node == "PRICE":
            # Price = COGS * (1 + pass_through * 0.3)
            cogs = self.states.get("COGS", 100)
            pt = drivers.get("PASS_THROUGH", 0.5)
            return cogs * (1 + pt * 0.3)
        
        elif node == "PRICE_VOLATILITY":
            # 가격 변동성 = 최근 가격 변화율의 표준편차
            price_history = self.state_history.get("PRICE", [])
            if len(price_history) >= 2:
                changes = [abs(price_history[i] - price_history[i-1]) / price_history[i-1] 
                          for i in range(1, len(price_history))]
                return sum(changes) / len(changes) if changes else 0
            return 0
        
        elif node == "DEMAND":
            # Demand = base * (1 - price_elasticity * price_change + brand_effect)
            price = self.states.get("PRICE", 100)
            brand = self.states.get("BRAND_EQUITY", 50)
            loyalty = self.states.get("LOYALTY", 60)
            
            base_demand = 100
            price_effect = -0.5 * (price - 100) / 100
            brand_effect = 0.3 * (brand - 50) / 50
            loyalty_effect = 0.2 * (loyalty - 50) / 50
            
            return max(10, base_demand * (1 + price_effect + brand_effect + loyalty_effect))
        
        elif node == "SALES":
            price = self.states.get("PRICE", 100)
            demand = self.states.get("DEMAND", 100)
            return price * demand
        
        elif node == "PROFIT":
            sales = self.states.get("SALES", 10000)
            cogs = self.states.get("COGS", 100)
            demand = self.states.get("DEMAND", 100)
            return sales - cogs * demand
        
        elif node == "MARGIN":
            sales = self.states.get("SALES", 10000)
            profit = self.states.get("PROFIT", 2000)
            return profit / sales if sales > 0 else 0
        
        elif node == "REFUND_RATE":
            service = drivers.get("SERVICE_LEVEL", 0.8)
            price_vol = self.states.get("PRICE_VOLATILITY", 0)
            return max(0.01, 0.1 - 0.05 * service + 0.1 * price_vol)
        
        elif node == "DELIVERY_TIME":
            service = drivers.get("SERVICE_LEVEL", 0.8)
            return max(1, 5 - 3 * service)
        
        elif node == "CSAT":
            service = drivers.get("SERVICE_LEVEL", 0.8)
            delivery = self.states.get("DELIVERY_TIME", 3)
            refund = self.states.get("REFUND_RATE", 0.05)
            return min(1.0, max(0.0, 0.5 + 0.3 * service - 0.05 * (delivery - 2) - 0.5 * refund))
        
        elif node == "BRAND_EQUITY":
            # Stock 변수: 누적/감가상각
            prev = self.states.get("BRAND_EQUITY", 50)
            csat = self.states.get("CSAT", 0.75)
            refund = self.states.get("REFUND_RATE", 0.05)
            price_vol = self.states.get("PRICE_VOLATILITY", 0)
            mkt = drivers.get("MKT_SPEND", 100)
            
            # 감가상각 + 긍정적 요인 - 부정적 요인
            depreciation = 0.02  # 2% 자연 감소
            new_val = prev * (1 - depreciation)
            new_val += 0.1 * (csat - 0.5)  # CSAT 기여
            new_val += 0.02 * (mkt - 100) / 100 * 10  # 마케팅 기여
            new_val -= 10 * refund  # 환불율 피해
            new_val -= 5 * price_vol  # 가격 변동성 피해
            
            return max(0, min(100, new_val))
        
        elif node == "LOYALTY":
            brand = self.states.get("BRAND_EQUITY", 50)
            csat = self.states.get("CSAT", 0.75)
            prev = self.states.get("LOYALTY", 60)
            
            # Stock 변수
            new_val = prev * 0.95  # 감가상각
            new_val += 0.05 * (brand - 50)  # 브랜드 기여
            new_val += 10 * (csat - 0.5)  # CSAT 기여
            
            return max(0, min(100, new_val))
        
        # 기본: 현재값 + 기여도 합
        total_contribution = sum(contributions.values())
        return current * (1 + total_contribution)
    
    def _calculate_kpis(self) -> Dict[str, float]:
        """KPI 계산"""
        kpis = {}
        
        # SHORT_TERM_MARGIN: 최근 3개월 평균 마진
        margin_history = self.state_history.get("MARGIN", [])
        if margin_history:
            recent = margin_history[-3:] if len(margin_history) >= 3 else margin_history
            kpis["SHORT_TERM_MARGIN"] = sum(recent) / len(recent)
        
        # LONG_TERM_BRAND_VALUE: 브랜드 자산 + 충성도 가중 평균
        brand = self.states.get("BRAND_EQUITY", 50)
        loyalty = self.states.get("LOYALTY", 60)
        kpis["LONG_TERM_BRAND_VALUE"] = 0.6 * brand + 0.4 * loyalty
        
        return kpis
    
    def _analyze_top_paths(self) -> List[Dict]:
        """상위 인과 경로 분석"""
        paths = []
        
        # 주요 경로 하드코딩 (실제로는 그래프 분석)
        key_paths = [
            ("FX_RATE", "BRAND_EQUITY"),
            ("FX_RATE", "PROFIT"),
            ("MKT_SPEND", "DEMAND"),
        ]
        
        with self.driver.session(database=neo4j_config.database) as session:
            for start, end in key_paths:
                result = session.run("""
                    MATCH path = (a)-[:CAUSES*1..5]->(b)
                    WHERE a.name = $start AND b.name = $end
                    RETURN [n IN nodes(path) | n.name] as nodes,
                           [r IN relationships(path) | r.polarity] as polarities
                    ORDER BY length(path)
                    LIMIT 3
                """, start=start, end=end)
                
                for record in result:
                    paths.append({
                        "from": start,
                        "to": end,
                        "path": " → ".join(record["nodes"]),
                        "polarities": record["polarities"]
                    })
        
        return paths
    
    def compare_scenarios(self, scenarios: List[SimulationScenario]) -> Dict[str, Any]:
        """시나리오 비교"""
        results = {}
        
        for scenario in scenarios:
            result = self.run_simulation(scenario)
            results[scenario.name] = {
                "kpis": result.kpi_values,
                "final_states": {k: v[-1] for k, v in result.state_history.items()},
                "state_history": result.state_history,
            }
        
        # 비교 분석
        comparison = {
            "scenarios": list(results.keys()),
            "kpi_comparison": {},
            "tradeoffs": []
        }
        
        for kpi in ["SHORT_TERM_MARGIN", "LONG_TERM_BRAND_VALUE"]:
            comparison["kpi_comparison"][kpi] = {
                name: data["kpis"].get(kpi, 0) 
                for name, data in results.items()
            }
        
        return comparison


def create_default_scenarios() -> List[SimulationScenario]:
    """기본 시나리오 세트 생성"""
    scenarios = []
    
    # 시나리오 1: 기준 (Baseline)
    scenarios.append(SimulationScenario(
        name="Baseline",
        description="기준 시나리오 - 현재 상태 유지",
        time_steps=12,
        fx_rate_schedule=[1200.0] * 12,
        pass_through=0.5,
        mkt_spend=100.0,
        service_level=0.8
    ))
    
    # 시나리오 2: 환율 급등
    fx_shock = [1200.0] * 3 + [1350.0] * 9  # 4개월차부터 급등
    scenarios.append(SimulationScenario(
        name="FX_Shock",
        description="환율 급등 시나리오 - 4개월차부터 1350원",
        time_steps=12,
        fx_rate_schedule=fx_shock,
        pass_through=0.5,
        mkt_spend=100.0,
        service_level=0.8
    ))
    
    # 시나리오 3: 환율 급등 + 높은 가격 전가
    scenarios.append(SimulationScenario(
        name="FX_Shock_HighPassThrough",
        description="환율 급등 + 가격 전가 80%",
        time_steps=12,
        fx_rate_schedule=fx_shock,
        pass_through=0.8,
        mkt_spend=100.0,
        service_level=0.8
    ))
    
    # 시나리오 4: 환율 급등 + 마케팅 강화
    scenarios.append(SimulationScenario(
        name="FX_Shock_MarketingBoost",
        description="환율 급등 + 마케팅 150% 증가",
        time_steps=12,
        fx_rate_schedule=fx_shock,
        pass_through=0.5,
        mkt_spend=150.0,
        service_level=0.8
    ))
    
    return scenarios


if __name__ == "__main__":
    engine = SimulationEngine()
    
    try:
        engine.initialize()
        
        # 기본 시나리오 실행
        scenarios = create_default_scenarios()
        
        # 첫 번째 시나리오만 실행
        result = engine.run_simulation(scenarios[0])
        
        print("\n" + "="*60)
        print("📊 시뮬레이션 결과 요약")
        print("="*60)
        
        print(f"\n📈 KPI 결과:")
        for kpi, value in result.kpi_values.items():
            print(f"   - {kpi}: {value:.4f}")
        
        print(f"\n📍 최종 상태 (주요 변수):")
        for key in ["COGS", "PRICE", "DEMAND", "PROFIT", "BRAND_EQUITY"]:
            if key in result.state_history:
                values = result.state_history[key]
                print(f"   - {key}: {values[0]:.2f} → {values[-1]:.2f}")
        
        print(f"\n🔗 주요 인과 경로:")
        for path in result.top_causal_paths[:3]:
            print(f"   - {path['path']}")
            
    finally:
        engine.close()
