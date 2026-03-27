"""
Ontology Loader - PRD 온톨로지를 Neo4j에 로드

PRD에 정의된 인과관계 그래프(CLD)를 Neo4j에 생성합니다.
"""

from neo4j import GraphDatabase
from typing import Dict, List, Any
from config import neo4j_config


class OntologyLoader:
    """PRD 온톨로지를 Neo4j에 로드하는 클래스"""
    
    def __init__(self):
        self.driver = GraphDatabase.driver(
            neo4j_config.uri,
            auth=(neo4j_config.user, neo4j_config.password)
        )
    
    def close(self):
        self.driver.close()
    
    def clear_ontology(self):
        """기존 What-if 시뮬레이션 온톨로지 삭제"""
        with self.driver.session(database=neo4j_config.database) as session:
            # 시뮬레이션 관련 노드만 삭제 (라벨로 구분)
            queries = [
                "MATCH (n:SimDriver) DETACH DELETE n",
                "MATCH (n:SimState) DETACH DELETE n",
                "MATCH (n:SimKPI) DETACH DELETE n",
                "MATCH (n:SimModel) DETACH DELETE n",
                "MATCH (n:SimLink) DETACH DELETE n",
            ]
            for query in queries:
                session.run(query)
            print("✓ 기존 시뮬레이션 온톨로지 삭제 완료")
    
    def create_driver_nodes(self):
        """Driver 노드 생성 (외생/정책 변수)"""
        drivers = [
            {"name": "FX_RATE", "type": "exogenous", "description": "환율 (원/달러)", "unit": "KRW/USD", "default_value": 1200.0},
            {"name": "PASS_THROUGH", "type": "policy", "description": "가격 전가율 (0-1)", "unit": "ratio", "default_value": 0.5},
            {"name": "MKT_SPEND", "type": "policy", "description": "마케팅 지출", "unit": "index", "default_value": 100.0},
            {"name": "SERVICE_LEVEL", "type": "policy", "description": "서비스 수준 (0-1)", "unit": "ratio", "default_value": 0.8},
        ]
        
        with self.driver.session(database=neo4j_config.database) as session:
            for d in drivers:
                session.run("""
                    MERGE (n:SimDriver {name: $name})
                    SET n.type = $type,
                        n.description = $description,
                        n.unit = $unit,
                        n.default_value = $default_value
                """, d)
            print(f"✓ {len(drivers)}개 Driver 노드 생성 완료")
    
    def create_state_nodes(self):
        """State 노드 생성 (시간 상태 변수)"""
        states = [
            {"name": "COGS", "description": "매출원가", "unit": "index", "is_stock": False},
            {"name": "PRICE", "description": "판매가격", "unit": "index", "is_stock": False},
            {"name": "PRICE_VOLATILITY", "description": "가격 변동성", "unit": "ratio", "is_stock": False},
            {"name": "DEMAND", "description": "수요", "unit": "quantity", "is_stock": False},
            {"name": "SALES", "description": "매출", "unit": "currency", "is_stock": False},
            {"name": "PROFIT", "description": "이익", "unit": "currency", "is_stock": False},
            {"name": "MARGIN", "description": "마진율", "unit": "ratio", "is_stock": False},
            {"name": "REFUND_RATE", "description": "환불율", "unit": "ratio", "is_stock": False},
            {"name": "DELIVERY_TIME", "description": "배송 시간", "unit": "days", "is_stock": False},
            {"name": "CSAT", "description": "고객 만족도", "unit": "score", "is_stock": False},
            {"name": "BRAND_EQUITY", "description": "브랜드 가치", "unit": "index", "is_stock": True},
            {"name": "LOYALTY", "description": "고객 충성도", "unit": "score", "is_stock": True},
        ]
        
        with self.driver.session(database=neo4j_config.database) as session:
            for s in states:
                session.run("""
                    MERGE (n:SimState {name: $name})
                    SET n.description = $description,
                        n.unit = $unit,
                        n.is_stock = $is_stock
                """, s)
            print(f"✓ {len(states)}개 State 노드 생성 완료")
    
    def create_kpi_nodes(self):
        """KPI 노드 생성"""
        kpis = [
            {"name": "SHORT_TERM_MARGIN", "description": "단기 마진 성과", "time_horizon": "short"},
            {"name": "LONG_TERM_BRAND_VALUE", "description": "장기 브랜드 가치", "time_horizon": "long"},
        ]
        
        with self.driver.session(database=neo4j_config.database) as session:
            for k in kpis:
                session.run("""
                    MERGE (n:SimKPI {name: $name})
                    SET n.description = $description,
                        n.time_horizon = $time_horizon
                """, k)
            print(f"✓ {len(kpis)}개 KPI 노드 생성 완료")
    
    def create_causal_relationships(self):
        """인과 관계(CAUSES) 생성 - PRD의 CLD 기반"""
        # (source, target, polarity, lag, description)
        causal_links = [
            # Driver → State
            ("FX_RATE", "COGS", "+", 0, "환율 상승 → 매출원가 증가"),
            ("PASS_THROUGH", "PRICE", "+", 0, "전가율 → 가격 반영 정도"),
            ("MKT_SPEND", "BRAND_EQUITY", "+", 3, "마케팅 → 브랜드 가치 (3개월 지연)"),
            ("SERVICE_LEVEL", "CSAT", "+", 0, "서비스 수준 → 고객 만족도"),
            ("SERVICE_LEVEL", "REFUND_RATE", "-", 0, "서비스 수준 ↑ → 환불율 ↓"),
            
            # State → State (Core Chain)
            ("COGS", "PRICE", "+", 0, "원가 상승 → 가격 조정 압력"),
            ("PRICE", "DEMAND", "-", 0, "가격 상승 → 수요 감소"),
            ("PRICE", "PRICE_VOLATILITY", "+", 0, "가격 변경 빈도/폭 → 변동성"),
            ("DEMAND", "SALES", "+", 0, "수요 → 매출"),
            ("SALES", "PROFIT", "+", 0, "매출 → 이익"),
            ("PRICE", "PROFIT", "+", 0, "가격(마진) → 이익"),
            ("COGS", "PROFIT", "-", 0, "원가 → 이익 감소"),
            ("PROFIT", "MARGIN", "+", 0, "이익 → 마진율"),
            
            # Brand/Loyalty Loop (R: Reinforcing)
            ("BRAND_EQUITY", "DEMAND", "+", 0, "브랜드 가치 → 수요 증가"),
            ("BRAND_EQUITY", "LOYALTY", "+", 1, "브랜드 → 충성도 (1개월 지연)"),
            ("LOYALTY", "DEMAND", "+", 0, "충성도 → 재구매 수요"),
            
            # Negative Feedback on Brand (B: Balancing)
            ("PRICE_VOLATILITY", "BRAND_EQUITY", "-", 2, "가격 변동성 → 브랜드 손상"),
            ("REFUND_RATE", "BRAND_EQUITY", "-", 1, "환불율 → 브랜드 손상"),
            ("CSAT", "BRAND_EQUITY", "+", 1, "고객만족 → 브랜드 강화"),
            ("CSAT", "LOYALTY", "+", 0, "고객만족 → 충성도"),
            
            # Delivery affects CSAT
            ("DELIVERY_TIME", "CSAT", "-", 0, "배송 지연 → 만족도 하락"),
        ]
        
        with self.driver.session(database=neo4j_config.database) as session:
            for src, tgt, polarity, lag, desc in causal_links:
                # 소스/타겟이 Driver인지 State인지 확인
                session.run("""
                    MATCH (a) WHERE a.name = $src AND (a:SimDriver OR a:SimState)
                    MATCH (b:SimState {name: $tgt})
                    MERGE (a)-[r:CAUSES]->(b)
                    SET r.polarity = $polarity,
                        r.lag = $lag,
                        r.description = $desc
                """, src=src, tgt=tgt, polarity=polarity, lag=lag, desc=desc)
            print(f"✓ {len(causal_links)}개 CAUSES 관계 생성 완료")
    
    def create_kpi_measurements(self):
        """State → KPI 측정 관계 생성"""
        measurements = [
            ("PROFIT", "SHORT_TERM_MARGIN", "이익 → 단기 마진 KPI"),
            ("MARGIN", "SHORT_TERM_MARGIN", "마진율 → 단기 마진 KPI"),
            ("BRAND_EQUITY", "LONG_TERM_BRAND_VALUE", "브랜드 가치 → 장기 브랜드 KPI"),
            ("LOYALTY", "LONG_TERM_BRAND_VALUE", "충성도 → 장기 브랜드 KPI"),
        ]
        
        with self.driver.session(database=neo4j_config.database) as session:
            for src, tgt, desc in measurements:
                session.run("""
                    MATCH (s:SimState {name: $src})
                    MATCH (k:SimKPI {name: $tgt})
                    MERGE (s)-[r:MEASURED_AS]->(k)
                    SET r.description = $desc
                """, src=src, tgt=tgt, desc=desc)
            print(f"✓ {len(measurements)}개 MEASURED_AS 관계 생성 완료")
    
    def create_link_nodes_with_models(self):
        """Link 노드 생성 (학습 가능한 Edge)"""
        # 핵심 링크들에 대해 Link 노드와 모델 참조 생성
        links = [
            {
                "id": "link_fx_cogs",
                "from_node": "FX_RATE",
                "to_node": "COGS",
                "model_type": "linear",
                "model_name": "fx_to_cogs_model",
                "formula": "COGS = 100 + 0.05 * (FX_RATE - 1200)",
            },
            {
                "id": "link_price_demand",
                "from_node": "PRICE",
                "to_node": "DEMAND",
                "model_type": "GAM",
                "model_name": "price_to_demand_model",
                "formula": "DEMAND = base_demand * (1 - elasticity * ln(PRICE/base_price))",
            },
            {
                "id": "link_brand_demand",
                "from_node": "BRAND_EQUITY",
                "to_node": "DEMAND",
                "model_type": "linear",
                "model_name": "brand_to_demand_model",
                "formula": "DEMAND += 0.3 * (BRAND_EQUITY - 50)",
            },
            {
                "id": "link_factors_brand",
                "from_node": "REFUND_RATE",
                "to_node": "BRAND_EQUITY",
                "model_type": "state_space",
                "model_name": "brand_equity_model",
                "formula": "BRAND_t+1 = BRAND_t * 0.95 - 10 * REFUND_RATE + 5 * CSAT + 0.1 * MKT",
            },
        ]
        
        with self.driver.session(database=neo4j_config.database) as session:
            for link in links:
                # Link 노드 생성
                session.run("""
                    MERGE (l:SimLink {id: $id})
                    SET l.model_type = $model_type,
                        l.model_name = $model_name,
                        l.formula = $formula
                """, id=link["id"], model_type=link["model_type"], 
                   model_name=link["model_name"], formula=link["formula"])
                
                # FROM/TO 관계 생성
                session.run("""
                    MATCH (a) WHERE a.name = $from_node AND (a:SimDriver OR a:SimState)
                    MATCH (l:SimLink {id: $id})
                    MATCH (b:SimState {name: $to_node})
                    MERGE (a)-[:FROM]->(l)
                    MERGE (l)-[:TO]->(b)
                """, from_node=link["from_node"], id=link["id"], to_node=link["to_node"])
            
            print(f"✓ {len(links)}개 SimLink 노드 및 관계 생성 완료")
    
    def load_full_ontology(self):
        """전체 온톨로지 로드"""
        print("\n" + "="*60)
        print("What-if Simulator 온톨로지 로드 시작")
        print("="*60 + "\n")
        
        self.clear_ontology()
        self.create_driver_nodes()
        self.create_state_nodes()
        self.create_kpi_nodes()
        self.create_causal_relationships()
        self.create_kpi_measurements()
        self.create_link_nodes_with_models()
        
        print("\n" + "="*60)
        print("✅ 온톨로지 로드 완료!")
        print("="*60)
    
    def verify_ontology(self) -> Dict[str, Any]:
        """온톨로지 검증 및 통계"""
        with self.driver.session(database=neo4j_config.database) as session:
            stats = {}
            
            # 노드 수
            result = session.run("MATCH (n:SimDriver) RETURN count(n) as cnt")
            stats["drivers"] = result.single()["cnt"]
            
            result = session.run("MATCH (n:SimState) RETURN count(n) as cnt")
            stats["states"] = result.single()["cnt"]
            
            result = session.run("MATCH (n:SimKPI) RETURN count(n) as cnt")
            stats["kpis"] = result.single()["cnt"]
            
            result = session.run("MATCH (n:SimLink) RETURN count(n) as cnt")
            stats["links"] = result.single()["cnt"]
            
            # 관계 수
            result = session.run("MATCH ()-[r:CAUSES]->() RETURN count(r) as cnt")
            stats["causes_rels"] = result.single()["cnt"]
            
            result = session.run("MATCH ()-[r:MEASURED_AS]->() RETURN count(r) as cnt")
            stats["measured_rels"] = result.single()["cnt"]
            
            return stats
    
    def get_causal_paths(self, start: str, end: str, max_hops: int = 5) -> List[Dict]:
        """두 노드 사이의 인과 경로 조회"""
        with self.driver.session(database=neo4j_config.database) as session:
            result = session.run("""
                MATCH path = (a)-[:CAUSES*1..5]->(b)
                WHERE a.name = $start AND b.name = $end
                RETURN [n IN nodes(path) | n.name] as nodes,
                       [r IN relationships(path) | {polarity: r.polarity, lag: r.lag}] as edges,
                       length(path) as hops
                ORDER BY hops
                LIMIT 10
            """, start=start, end=end)
            
            paths = []
            for record in result:
                paths.append({
                    "nodes": record["nodes"],
                    "edges": record["edges"],
                    "hops": record["hops"]
                })
            return paths


if __name__ == "__main__":
    loader = OntologyLoader()
    
    try:
        # 온톨로지 로드
        loader.load_full_ontology()
        
        # 검증
        print("\n📊 온톨로지 통계:")
        stats = loader.verify_ontology()
        for key, value in stats.items():
            print(f"  - {key}: {value}")
        
        # 인과 경로 예시
        print("\n🔍 인과 경로 예시 (FX_RATE → BRAND_EQUITY):")
        paths = loader.get_causal_paths("FX_RATE", "BRAND_EQUITY")
        for i, path in enumerate(paths):
            print(f"  경로 {i+1}: {' → '.join(path['nodes'])}")
            
    finally:
        loader.close()
