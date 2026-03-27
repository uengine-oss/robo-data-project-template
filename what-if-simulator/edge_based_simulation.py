#!/usr/bin/env python3
"""
Edge-Based Causal Simulation Engine

PRD 핵심 원칙:
- ❌ 하나의 대형 모델
- ✅ 관계별 소형 모델

각 CAUSES 관계(Edge)마다 개별 모델을 적용하고,
그래프를 순회하면서 인과관계를 따라 값을 단계적으로 전파합니다.
"""

import requests
import json
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple, Callable
from dataclasses import dataclass, field
from collections import defaultdict
from neo4j import GraphDatabase

from config import neo4j_config

MINDSDB_API = "http://127.0.0.1:47334/api/sql/query"


def run_query(query: str, silent: bool = True) -> Optional[Dict]:
    """MindsDB SQL 쿼리 실행"""
    try:
        response = requests.post(
            MINDSDB_API,
            headers={"Content-Type": "application/json"},
            json={"query": query},
            timeout=30
        )
        result = response.json()
        if result.get("type") == "error":
            if not silent:
                print(f"   ❌ Error: {result.get('error_message', '')[:100]}")
            return None
        return result
    except Exception as e:
        if not silent:
            print(f"   ❌ Exception: {e}")
        return None


@dataclass
class EdgeModel:
    """단일 Edge(인과관계)에 대한 모델 정의"""
    edge_id: str
    source: str
    target: str
    polarity: str  # "+" or "-"
    lag: int = 0
    
    # 모델 정보
    model_type: str = "formula"  # "formula", "mindsdb", "linear"
    model_name: Optional[str] = None
    
    # 수식 기반 모델 파라미터
    coefficient: float = 1.0  # 탄력도/민감도
    base_effect: float = 0.0
    
    # MindsDB 모델이 있으면 사용, 없으면 수식 사용
    formula: Optional[Callable] = None
    
    def compute_effect(self, source_value: float, source_baseline: float = 0) -> float:
        """소스 값 변화에 따른 타겟 효과 계산"""
        # 기준값 대비 변화량
        delta = source_value - source_baseline
        
        # 극성 적용
        sign = 1.0 if self.polarity == "+" else -1.0
        
        # 효과 = 계수 * 부호 * 변화량
        effect = self.coefficient * sign * delta
        
        return effect


@dataclass
class CausalNode:
    """인과 그래프의 노드"""
    name: str
    node_type: str  # "driver", "state", "kpi"
    is_stock: bool = False
    
    # 현재 값과 기준값
    value: float = 0.0
    baseline: float = 0.0
    
    # 들어오는 Edge들
    incoming_edges: List[str] = field(default_factory=list)


class EdgeBasedCausalGraph:
    """Edge 기반 인과 그래프"""
    
    def __init__(self):
        self.driver = GraphDatabase.driver(
            neo4j_config.uri,
            auth=(neo4j_config.user, neo4j_config.password)
        )
        self.nodes: Dict[str, CausalNode] = {}
        self.edges: Dict[str, EdgeModel] = {}
        self.edge_models: Dict[str, EdgeModel] = {}
        
        # 각 노드의 기준값 (초기 상태)
        self.baselines = {
            "FX_RATE": 1200.0,
            "PASS_THROUGH": 0.5,
            "MKT_SPEND": 100.0,
            "SERVICE_LEVEL": 0.8,
            "COGS": 100.0,
            "PRICE": 115.0,
            "PRICE_VOLATILITY": 0.0,
            "DEMAND": 100.0,
            "SALES": 11500.0,
            "PROFIT": 1500.0,
            "MARGIN": 0.13,
            "REFUND_RATE": 0.05,
            "DELIVERY_TIME": 2.6,
            "CSAT": 0.75,
            "BRAND_EQUITY": 50.0,
            "LOYALTY": 60.0,
        }
    
    def close(self):
        self.driver.close()
    
    def load_from_neo4j(self):
        """Neo4j에서 노드와 Edge 로드"""
        with self.driver.session(database=neo4j_config.database) as session:
            # 노드 로드
            result = session.run("""
                MATCH (n)
                WHERE n:SimDriver OR n:SimState OR n:SimKPI
                RETURN n.name as name, labels(n)[0] as label, 
                       coalesce(n.is_stock, false) as is_stock
            """)
            
            for record in result:
                name = record["name"]
                label = record["label"]
                node_type = "driver" if label == "SimDriver" else (
                    "state" if label == "SimState" else "kpi"
                )
                
                self.nodes[name] = CausalNode(
                    name=name,
                    node_type=node_type,
                    is_stock=record["is_stock"],
                    value=self.baselines.get(name, 0),
                    baseline=self.baselines.get(name, 0)
                )
            
            # Edge 로드 (CAUSES 관계)
            result = session.run("""
                MATCH (a)-[r:CAUSES]->(b)
                WHERE (a:SimDriver OR a:SimState) AND b:SimState
                RETURN a.name as source, b.name as target,
                       r.polarity as polarity, 
                       coalesce(r.lag, 0) as lag,
                       r.description as description
            """)
            
            for record in result:
                source = record["source"]
                target = record["target"]
                edge_id = f"{source}_to_{target}"
                
                edge = EdgeModel(
                    edge_id=edge_id,
                    source=source,
                    target=target,
                    polarity=record["polarity"] or "+",
                    lag=record["lag"] or 0
                )
                
                self.edges[edge_id] = edge
                
                # 노드의 incoming_edges에 추가
                if target in self.nodes:
                    self.nodes[target].incoming_edges.append(edge_id)
        
        print(f"✓ 그래프 로드: {len(self.nodes)} 노드, {len(self.edges)} Edge")
    
    def setup_edge_models(self):
        """각 Edge에 모델/수식 할당"""
        
        # Edge별 계수 및 모델 타입 정의
        # PRD 기반: 각 관계에 대한 탄력도/민감도 설정
        edge_configs = {
            # Driver → State
            "FX_RATE_to_COGS": {
                "model_type": "linear",
                "coefficient": 0.05,  # FX 100원 상승 → COGS 5 상승
                "model_name": "edge_fx_cogs"
            },
            "PASS_THROUGH_to_PRICE": {
                "model_type": "formula",
                "coefficient": 30.0,  # 전가율 0.1 증가 → 가격 3 상승
            },
            "MKT_SPEND_to_BRAND_EQUITY": {
                "model_type": "linear",
                "coefficient": 0.05,  # 마케팅 10 증가 → 브랜드 0.5 증가
                "lag": 3
            },
            "SERVICE_LEVEL_to_CSAT": {
                "model_type": "linear",
                "coefficient": 0.5,  # 서비스 0.1 증가 → CSAT 0.05 증가
            },
            "SERVICE_LEVEL_to_REFUND_RATE": {
                "model_type": "linear",
                "coefficient": 0.1,  # 서비스 0.1 증가 → 환불율 0.01 감소
            },
            
            # State → State (Core Chain)
            "COGS_to_PRICE": {
                "model_type": "linear",
                "coefficient": 1.0,  # COGS 1 상승 → PRICE 1 상승 (전가율 적용)
            },
            "PRICE_to_DEMAND": {
                "model_type": "linear",
                "coefficient": 0.8,  # 가격탄력성: 가격 1% 상승 → 수요 0.8% 감소
            },
            "PRICE_to_PRICE_VOLATILITY": {
                "model_type": "formula",
                "coefficient": 0.01,
            },
            "DEMAND_to_SALES": {
                "model_type": "formula",
                "coefficient": 1.0,
            },
            "SALES_to_PROFIT": {
                "model_type": "formula",
                "coefficient": 1.0,
            },
            "PRICE_to_PROFIT": {
                "model_type": "formula",
                "coefficient": 1.0,
            },
            "COGS_to_PROFIT": {
                "model_type": "formula",
                "coefficient": 1.0,
            },
            "PROFIT_to_MARGIN": {
                "model_type": "formula",
                "coefficient": 1.0,
            },
            
            # Brand/Loyalty Loop
            "BRAND_EQUITY_to_DEMAND": {
                "model_type": "linear",
                "coefficient": 0.6,  # 브랜드 1 상승 → 수요 0.6 상승
            },
            "BRAND_EQUITY_to_LOYALTY": {
                "model_type": "linear",
                "coefficient": 0.5,
                "lag": 1
            },
            "LOYALTY_to_DEMAND": {
                "model_type": "linear",
                "coefficient": 0.4,  # 충성도 1 상승 → 수요 0.4 상승
            },
            
            # Negative Feedback on Brand
            "PRICE_VOLATILITY_to_BRAND_EQUITY": {
                "model_type": "linear",
                "coefficient": 50.0,  # 변동성 0.01 상승 → 브랜드 0.5 감소
                "lag": 2
            },
            "REFUND_RATE_to_BRAND_EQUITY": {
                "model_type": "linear",
                "coefficient": 100.0,  # 환불율 0.01 상승 → 브랜드 1 감소
                "lag": 1
            },
            "CSAT_to_BRAND_EQUITY": {
                "model_type": "linear",
                "coefficient": 10.0,  # CSAT 0.1 상승 → 브랜드 1 상승
                "lag": 1
            },
            "CSAT_to_LOYALTY": {
                "model_type": "linear",
                "coefficient": 20.0,  # CSAT 0.1 상승 → 충성도 2 상승
            },
            "DELIVERY_TIME_to_CSAT": {
                "model_type": "linear",
                "coefficient": 0.05,  # 배송 1일 증가 → CSAT 0.05 감소
            },
        }
        
        # Edge에 설정 적용
        for edge_id, edge in self.edges.items():
            if edge_id in edge_configs:
                config = edge_configs[edge_id]
                edge.model_type = config.get("model_type", "formula")
                edge.coefficient = config.get("coefficient", 1.0)
                edge.model_name = config.get("model_name")
                if "lag" in config:
                    edge.lag = config["lag"]
        
        print(f"✓ {len(edge_configs)}개 Edge 모델 설정 완료")
    
    def get_topological_order(self) -> List[str]:
        """위상 정렬로 업데이트 순서 결정"""
        in_degree = defaultdict(int)
        
        # 진입 차수 계산
        for edge in self.edges.values():
            if edge.target in self.nodes:
                in_degree[edge.target] += 1
        
        # Driver 노드와 진입 차수 0인 노드부터 시작
        queue = []
        for name, node in self.nodes.items():
            if node.node_type == "driver" or in_degree[name] == 0:
                queue.append(name)
        
        order = []
        visited = set()
        
        while queue:
            current = queue.pop(0)
            if current in visited:
                continue
            
            visited.add(current)
            order.append(current)
            
            # 나가는 Edge의 타겟 진입 차수 감소
            for edge in self.edges.values():
                if edge.source == current:
                    in_degree[edge.target] -= 1
                    if in_degree[edge.target] <= 0 and edge.target not in visited:
                        queue.append(edge.target)
        
        # State 노드만 반환 (Driver는 외생)
        return [n for n in order if self.nodes[n].node_type == "state"]


class EdgeBasedSimulator:
    """Edge 기반 시뮬레이션 엔진"""
    
    def __init__(self):
        self.graph = EdgeBasedCausalGraph()
        self.state_history: Dict[str, List[float]] = defaultdict(list)
        self.edge_contributions: Dict[str, List[Dict]] = defaultdict(list)
    
    def initialize(self):
        """초기화"""
        print("\n" + "="*60)
        print("Edge-Based Causal Simulation Engine 초기화")
        print("="*60)
        
        self.graph.load_from_neo4j()
        self.graph.setup_edge_models()
        
        # MindsDB Edge 모델 확인/생성
        self._setup_mindsdb_edge_models()
    
    def _setup_mindsdb_edge_models(self):
        """MindsDB에 Edge별 모델 생성"""
        print("\n📊 MindsDB Edge 모델 확인...")
        
        # 현재 모델 목록 확인
        result = run_query("SELECT name, status FROM mindsdb.models", silent=True)
        existing_models = set()
        if result and result.get("data"):
            for row in result["data"]:
                existing_models.add(row[0])
        
        # 필요한 Edge 모델 정의
        edge_model_specs = [
            {
                "name": "edge_fx_cogs",
                "query": "SELECT fx_rate, cogs FROM kpi_monthly",
                "target": "cogs",
                "description": "FX_RATE → COGS"
            },
            {
                "name": "edge_price_demand",
                "query": "SELECT price, demand FROM kpi_monthly",
                "target": "demand",
                "description": "PRICE → DEMAND"
            },
            {
                "name": "edge_brand_demand",
                "query": "SELECT brand_equity, demand FROM kpi_monthly",
                "target": "demand",
                "description": "BRAND_EQUITY → DEMAND"
            },
            {
                "name": "edge_csat_brand",
                "query": "SELECT csat, brand_equity FROM kpi_monthly",
                "target": "brand_equity",
                "description": "CSAT → BRAND_EQUITY"
            },
            {
                "name": "edge_refund_brand",
                "query": "SELECT refund_rate, brand_equity FROM kpi_monthly",
                "target": "brand_equity",
                "description": "REFUND_RATE → BRAND_EQUITY"
            },
        ]
        
        for spec in edge_model_specs:
            if spec["name"] in existing_models:
                print(f"   ✓ {spec['name']} (기존)")
            else:
                # 모델 생성
                create_sql = f"""
                CREATE MODEL mindsdb.{spec['name']}
                FROM files ({spec['query']})
                PREDICT {spec['target']}
                """
                result = run_query(create_sql, silent=False)
                if result:
                    print(f"   ⏳ {spec['name']} 생성 시작...")
    
    def close(self):
        self.graph.close()
    
    def run_simulation(self, scenario: Dict) -> Dict:
        """시뮬레이션 실행"""
        print(f"\n{'='*60}")
        print(f"🚀 시나리오: {scenario['name']}")
        print(f"   {scenario.get('description', '')}")
        print(f"{'='*60}")
        
        time_steps = scenario.get("time_steps", 12)
        
        # 상태 초기화
        for name, node in self.graph.nodes.items():
            node.value = node.baseline
        
        self.state_history = defaultdict(list)
        self.edge_contributions = defaultdict(list)
        
        # 이전 값 저장 (지연 효과용)
        history_buffer: Dict[str, List[float]] = defaultdict(list)
        
        # 업데이트 순서
        update_order = self.graph.get_topological_order()
        
        for t in range(time_steps):
            # 1. Driver 값 설정
            drivers = {
                "FX_RATE": scenario["fx_schedule"][min(t, len(scenario["fx_schedule"])-1)],
                "PASS_THROUGH": scenario.get("pass_through", 0.5),
                "MKT_SPEND": scenario.get("mkt_spend", 100.0),
                "SERVICE_LEVEL": scenario.get("service_level", 0.8),
            }
            
            for name, value in drivers.items():
                if name in self.graph.nodes:
                    self.graph.nodes[name].value = value
            
            # 2. 그래프 순회하며 각 노드 업데이트
            for node_name in update_order:
                node = self.graph.nodes[node_name]
                
                # 이 노드로 들어오는 모든 Edge의 효과 합산
                total_effect = 0.0
                edge_effects = {}
                
                for edge_id in node.incoming_edges:
                    edge = self.graph.edges[edge_id]
                    source_node = self.graph.nodes.get(edge.source)
                    
                    if not source_node:
                        continue
                    
                    # 지연 효과 처리
                    if edge.lag > 0 and t >= edge.lag:
                        # 과거 값 사용
                        if len(history_buffer[edge.source]) >= edge.lag:
                            source_value = history_buffer[edge.source][-edge.lag]
                        else:
                            source_value = source_node.baseline
                    else:
                        source_value = source_node.value
                    
                    # Edge 효과 계산
                    effect = self._compute_edge_effect(
                        edge, source_value, source_node.baseline, t
                    )
                    
                    total_effect += effect
                    edge_effects[edge.source] = effect
                
                # 노드 값 업데이트
                new_value = self._apply_node_update(
                    node_name, node, total_effect, drivers, t
                )
                node.value = new_value
                
                # Edge 기여도 기록
                self.edge_contributions[node_name].append({
                    "t": t,
                    "effects": edge_effects,
                    "total": total_effect,
                    "new_value": new_value
                })
            
            # 3. 히스토리 저장
            for name, node in self.graph.nodes.items():
                self.state_history[name].append(node.value)
                history_buffer[name].append(node.value)
            
            # 진행 표시
            if (t + 1) % 4 == 0 or t == 0:
                fx = drivers["FX_RATE"]
                cogs = self.graph.nodes["COGS"].value
                price = self.graph.nodes["PRICE"].value
                demand = self.graph.nodes["DEMAND"].value
                brand = self.graph.nodes["BRAND_EQUITY"].value
                
                print(f"   t={t+1}: FX={fx:.0f} → COGS={cogs:.1f} → "
                      f"Price={price:.1f} → Demand={demand:.1f}, Brand={brand:.1f}")
        
        # 4. 결과 계산
        return self._compute_results(scenario["name"])
    
    def _compute_edge_effect(self, edge: EdgeModel, source_value: float,
                            source_baseline: float, t: int) -> float:
        """Edge 효과 계산"""
        
        # MindsDB 모델 사용 시도
        if edge.model_name and edge.model_type == "mindsdb":
            result = self._predict_with_mindsdb(edge, source_value)
            if result is not None:
                return result
        
        # 기본 수식: 선형 효과
        delta = source_value - source_baseline
        sign = 1.0 if edge.polarity == "+" else -1.0
        
        return edge.coefficient * sign * delta
    
    def _predict_with_mindsdb(self, edge: EdgeModel, source_value: float) -> Optional[float]:
        """MindsDB 모델로 예측"""
        query = f"""
        SELECT {edge.target} FROM mindsdb.{edge.model_name}
        WHERE {edge.source.lower()} = {source_value}
        """
        result = run_query(query, silent=True)
        
        if result and result.get("data"):
            predicted = float(result["data"][0][0])
            # 기준값 대비 차이를 효과로 반환
            baseline = self.graph.baselines.get(edge.target, 0)
            return predicted - baseline
        
        return None
    
    def _apply_node_update(self, name: str, node: CausalNode, 
                          total_effect: float, drivers: Dict, t: int) -> float:
        """노드 값 업데이트"""
        
        # Stock 변수: 누적/감가상각
        if node.is_stock:
            depreciation = 0.02  # 2% 자연 감소
            new_value = node.value * (1 - depreciation) + total_effect
            return max(0, min(100, new_value))
        
        # 특수 노드별 계산
        if name == "COGS":
            # COGS = baseline + FX 효과
            fx = drivers.get("FX_RATE", 1200)
            return 100 + 0.05 * (fx - 1200)
        
        elif name == "PRICE":
            # PRICE = COGS * (1 + pass_through * margin_rate)
            cogs = self.graph.nodes["COGS"].value
            pt = drivers.get("PASS_THROUGH", 0.5)
            return cogs * (1 + pt * 0.3)
        
        elif name == "PRICE_VOLATILITY":
            # 가격 변동성 = 최근 가격 변화율
            price_hist = self.state_history.get("PRICE", [])
            if len(price_hist) >= 1:
                prev_price = price_hist[-1]
                curr_price = self.graph.nodes["PRICE"].value
                return abs(curr_price - prev_price) / prev_price if prev_price > 0 else 0
            return 0
        
        elif name == "DEMAND":
            # 수요 = 기준 + 가격효과 + 브랜드효과 + 충성도효과
            base = 100
            
            # 각 Edge 효과 개별 계산
            price = self.graph.nodes["PRICE"].value
            brand = self.graph.nodes["BRAND_EQUITY"].value
            loyalty = self.graph.nodes["LOYALTY"].value
            
            price_effect = -0.8 * (price - 115) / 115 * base
            brand_effect = 0.6 * (brand - 50) / 50 * base
            loyalty_effect = 0.4 * (loyalty - 60) / 60 * base
            
            return max(50, base + price_effect + brand_effect + loyalty_effect)
        
        elif name == "SALES":
            price = self.graph.nodes["PRICE"].value
            demand = self.graph.nodes["DEMAND"].value
            return price * demand
        
        elif name == "PROFIT":
            sales = self.graph.nodes["SALES"].value
            cogs = self.graph.nodes["COGS"].value
            demand = self.graph.nodes["DEMAND"].value
            return sales - cogs * demand
        
        elif name == "MARGIN":
            sales = self.graph.nodes["SALES"].value
            profit = self.graph.nodes["PROFIT"].value
            return profit / sales if sales > 0 else 0
        
        elif name == "REFUND_RATE":
            service = drivers.get("SERVICE_LEVEL", 0.8)
            price_vol = self.graph.nodes["PRICE_VOLATILITY"].value
            return max(0.01, 0.08 - 0.05 * (service - 0.5) + 0.5 * price_vol)
        
        elif name == "DELIVERY_TIME":
            service = drivers.get("SERVICE_LEVEL", 0.8)
            return max(1, 5 - 4 * service)
        
        elif name == "CSAT":
            service = drivers.get("SERVICE_LEVEL", 0.8)
            delivery = self.graph.nodes["DELIVERY_TIME"].value
            refund = self.graph.nodes["REFUND_RATE"].value
            base_csat = 0.5 + 0.3 * service
            delivery_effect = -0.05 * (delivery - 2.6)
            refund_effect = -0.5 * refund
            return min(1.0, max(0.3, base_csat + delivery_effect + refund_effect))
        
        # 기본: 기준값 + 총 효과
        return node.baseline + total_effect
    
    def _compute_results(self, scenario_name: str) -> Dict:
        """결과 계산"""
        
        # KPI 계산
        margin_history = self.state_history.get("MARGIN", [])
        brand = self.graph.nodes["BRAND_EQUITY"].value
        loyalty = self.graph.nodes["LOYALTY"].value
        profit_history = self.state_history.get("PROFIT", [])
        
        kpis = {
            "SHORT_TERM_MARGIN": sum(margin_history[-3:]) / 3 if margin_history else 0,
            "LONG_TERM_BRAND_VALUE": 0.6 * brand + 0.4 * loyalty,
            "TOTAL_PROFIT": sum(profit_history),
            "AVG_DEMAND": sum(self.state_history.get("DEMAND", [])) / len(self.state_history.get("DEMAND", [1])),
        }
        
        # 주요 Edge 기여도 분석
        top_contributions = self._analyze_edge_contributions()
        
        return {
            "scenario_name": scenario_name,
            "kpis": kpis,
            "state_history": dict(self.state_history),
            "final_states": {n: node.value for n, node in self.graph.nodes.items()},
            "edge_contributions": top_contributions,
        }
    
    def _analyze_edge_contributions(self) -> Dict[str, Dict]:
        """Edge 기여도 분석"""
        contributions = {}
        
        for node_name, records in self.edge_contributions.items():
            if not records:
                continue
            
            # 마지막 기록의 효과들
            last_record = records[-1]
            contributions[node_name] = last_record["effects"]
        
        return contributions
    
    def explain_path(self, start: str, end: str) -> List[Dict]:
        """인과 경로 설명 생성"""
        # BFS로 경로 찾기
        from collections import deque
        
        queue = deque([(start, [start])])
        visited = set()
        paths = []
        
        while queue:
            current, path = queue.popleft()
            
            if current == end:
                paths.append(path)
                continue
            
            if current in visited:
                continue
            visited.add(current)
            
            # 나가는 Edge 탐색
            for edge in self.graph.edges.values():
                if edge.source == current and edge.target not in visited:
                    queue.append((edge.target, path + [edge.target]))
        
        # 경로에 Edge 정보 추가
        explained_paths = []
        for path in paths[:5]:  # 상위 5개
            edges_info = []
            for i in range(len(path) - 1):
                edge_id = f"{path[i]}_to_{path[i+1]}"
                if edge_id in self.graph.edges:
                    edge = self.graph.edges[edge_id]
                    edges_info.append({
                        "from": path[i],
                        "to": path[i+1],
                        "polarity": edge.polarity,
                        "coefficient": edge.coefficient,
                        "lag": edge.lag
                    })
            
            explained_paths.append({
                "path": " → ".join(path),
                "edges": edges_info
            })
        
        return explained_paths


def create_scenarios() -> List[Dict]:
    """시나리오 생성"""
    return [
        {
            "name": "Baseline",
            "description": "현재 환율(1270) 유지",
            "time_steps": 12,
            "fx_schedule": [1270.0] * 12,
            "pass_through": 0.5,
            "mkt_spend": 100.0,
            "service_level": 0.8
        },
        {
            "name": "FX_Shock",
            "description": "4개월차부터 환율 1380원 급등",
            "time_steps": 12,
            "fx_schedule": [1270.0] * 3 + [1380.0] * 9,
            "pass_through": 0.5,
            "mkt_spend": 100.0,
            "service_level": 0.8
        },
        {
            "name": "FX_Shock_HighPassThrough",
            "description": "환율 급등 + 가격 전가 80%",
            "time_steps": 12,
            "fx_schedule": [1270.0] * 3 + [1380.0] * 9,
            "pass_through": 0.8,
            "mkt_spend": 100.0,
            "service_level": 0.8
        },
        {
            "name": "FX_Shock_MarketingBoost",
            "description": "환율 급등 + 마케팅 150%",
            "time_steps": 12,
            "fx_schedule": [1270.0] * 3 + [1380.0] * 9,
            "pass_through": 0.5,
            "mkt_spend": 150.0,
            "service_level": 0.8
        },
    ]


def main():
    """메인 실행"""
    print("="*70)
    print("  Edge-Based Causal Loop Simulation")
    print("  (PRD 원칙: 관계별 소형 모델 적용)")
    print(f"  실행 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*70)
    
    simulator = EdgeBasedSimulator()
    
    try:
        simulator.initialize()
        
        # 시나리오 실행
        scenarios = create_scenarios()
        results = {}
        
        for scenario in scenarios:
            result = simulator.run_simulation(scenario)
            results[scenario["name"]] = result
        
        # 결과 비교
        print("\n" + "="*70)
        print("📊 시나리오 비교 (Edge-Based)")
        print("="*70)
        
        print(f"\n{'시나리오':<30} {'단기마진':>10} {'장기브랜드':>12} {'총이익':>12}")
        print("-" * 66)
        
        baseline = results.get("Baseline", {}).get("kpis", {})
        
        for name, result in results.items():
            kpis = result["kpis"]
            margin = kpis["SHORT_TERM_MARGIN"]
            brand = kpis["LONG_TERM_BRAND_VALUE"]
            profit = kpis["TOTAL_PROFIT"]
            
            if name == "Baseline":
                print(f"{name:<30} {margin:>10.2%} {brand:>12.2f} {profit:>12,.0f}  (기준)")
            else:
                m_diff = margin - baseline.get("SHORT_TERM_MARGIN", 0)
                b_diff = brand - baseline.get("LONG_TERM_BRAND_VALUE", 0)
                p_diff = profit - baseline.get("TOTAL_PROFIT", 0)
                print(f"{name:<30} {margin:>10.2%} {brand:>12.2f} {profit:>12,.0f}  "
                      f"({m_diff:+.2%}, {b_diff:+.1f}, {p_diff:+,.0f})")
        
        # 인과 경로 분석
        print("\n" + "="*70)
        print("🔗 인과 경로 분석 (FX_RATE → BRAND_EQUITY)")
        print("="*70)
        
        paths = simulator.explain_path("FX_RATE", "BRAND_EQUITY")
        for i, p in enumerate(paths, 1):
            print(f"\n   경로 {i}: {p['path']}")
            for edge in p["edges"]:
                print(f"      {edge['from']} ─({edge['polarity']}, β={edge['coefficient']})─> {edge['to']}"
                      + (f" [lag={edge['lag']}]" if edge['lag'] > 0 else ""))
        
        # Edge 기여도 분석
        print("\n" + "="*70)
        print("📈 Edge 기여도 분석 (FX_Shock 시나리오)")
        print("="*70)
        
        fx_shock_result = results.get("FX_Shock", {})
        edge_contribs = fx_shock_result.get("edge_contributions", {})
        
        for node in ["DEMAND", "BRAND_EQUITY"]:
            if node in edge_contribs:
                print(f"\n   {node}에 대한 Edge 기여:")
                for source, effect in edge_contribs[node].items():
                    print(f"      ← {source}: {effect:+.2f}")
        
        # 결과 저장
        export_path = "/Users/uengine/robo-analyz/what-if-simulator/edge_simulation_results.json"
        with open(export_path, 'w', encoding='utf-8') as f:
            json.dump({
                "timestamp": datetime.now().isoformat(),
                "scenarios": {
                    name: {
                        "kpis": r["kpis"],
                        "final_states": r["final_states"],
                    } for name, r in results.items()
                }
            }, f, indent=2, ensure_ascii=False)
        
        print(f"\n📁 결과 저장: {export_path}")
        
        print("\n" + "="*70)
        print("✅ Edge-Based Simulation 완료!")
        print("="*70)
        
    finally:
        simulator.close()


if __name__ == "__main__":
    main()
