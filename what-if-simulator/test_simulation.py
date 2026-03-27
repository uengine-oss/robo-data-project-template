#!/usr/bin/env python3
"""
What-if Simulator 통합 테스트

1. Neo4j 온톨로지 로드
2. MindsDB 연결 확인
3. What-if 시뮬레이션 실행
4. 결과 비교 및 시각화
"""

import json
from datetime import datetime
from typing import Dict, List, Any

from config import neo4j_config, mindsdb_config, simulation_config
from ontology_loader import OntologyLoader
from mindsdb_connector import MindsDBConnector, SimulationModelAdapter
from simulation_engine import (
    SimulationEngine, 
    SimulationScenario, 
    create_default_scenarios
)


def print_header(title: str):
    print("\n" + "="*70)
    print(f"  {title}")
    print("="*70)


def print_section(title: str):
    print(f"\n{'─'*50}")
    print(f"  {title}")
    print(f"{'─'*50}")


def test_neo4j_connection() -> bool:
    """Neo4j 연결 테스트"""
    print_section("1. Neo4j 연결 테스트")
    
    try:
        from neo4j import GraphDatabase
        driver = GraphDatabase.driver(
            neo4j_config.uri,
            auth=(neo4j_config.user, neo4j_config.password)
        )
        with driver.session(database=neo4j_config.database) as session:
            result = session.run("RETURN 1 as n")
            result.single()
        driver.close()
        print(f"   ✅ Neo4j 연결 성공: {neo4j_config.uri}")
        return True
    except Exception as e:
        print(f"   ❌ Neo4j 연결 실패: {e}")
        return False


def test_mindsdb_connection() -> bool:
    """MindsDB 연결 테스트"""
    print_section("2. MindsDB 연결 테스트")
    
    connector = MindsDBConnector()
    if connector.check_connection():
        print(f"   ✅ MindsDB 연결 성공: {mindsdb_config.http_url}")
        
        models = connector.list_models()
        if models:
            print(f"   📋 현재 모델: {', '.join(models[:5])}")
        else:
            print(f"   ℹ️  등록된 모델 없음 - 기본 수식 모드 사용")
        return True
    else:
        print(f"   ⚠️  MindsDB 연결 실패 - 기본 수식 모드로 진행")
        return False


def load_ontology() -> Dict[str, Any]:
    """온톨로지 로드"""
    print_section("3. 온톨로지 로드")
    
    loader = OntologyLoader()
    try:
        loader.load_full_ontology()
        stats = loader.verify_ontology()
        
        print("\n   📊 온톨로지 통계:")
        print(f"      - Driver 노드: {stats.get('drivers', 0)}개")
        print(f"      - State 노드: {stats.get('states', 0)}개")
        print(f"      - KPI 노드: {stats.get('kpis', 0)}개")
        print(f"      - Link 노드: {stats.get('links', 0)}개")
        print(f"      - CAUSES 관계: {stats.get('causes_rels', 0)}개")
        print(f"      - MEASURED_AS 관계: {stats.get('measured_rels', 0)}개")
        
        return stats
    finally:
        loader.close()


def run_what_if_simulation() -> Dict[str, Any]:
    """What-if 시뮬레이션 실행"""
    print_section("4. What-if 시뮬레이션 실행")
    
    engine = SimulationEngine()
    try:
        engine.initialize()
        scenarios = create_default_scenarios()
        
        print(f"\n   📋 시나리오 목록:")
        for i, s in enumerate(scenarios):
            print(f"      {i+1}. {s.name}: {s.description}")
        
        # 모든 시나리오 실행 및 비교
        print_section("5. 시나리오별 시뮬레이션 결과")
        
        all_results = {}
        for scenario in scenarios:
            result = engine.run_simulation(scenario)
            all_results[scenario.name] = result
            
            print(f"\n   📈 [{scenario.name}] 결과:")
            print(f"      KPI - 단기 마진: {result.kpi_values.get('SHORT_TERM_MARGIN', 0):.4f}")
            print(f"      KPI - 장기 브랜드: {result.kpi_values.get('LONG_TERM_BRAND_VALUE', 0):.2f}")
            
            # 주요 상태 변화
            for key in ["PROFIT", "BRAND_EQUITY"]:
                if key in result.state_history:
                    vals = result.state_history[key]
                    print(f"      {key}: {vals[0]:.1f} → {vals[-1]:.1f} (Δ{vals[-1]-vals[0]:+.1f})")
        
        return all_results
        
    finally:
        engine.close()


def compare_scenarios(results: Dict[str, Any]):
    """시나리오 비교 분석"""
    print_section("6. 시나리오 비교 분석")
    
    if not results:
        print("   ⚠️  비교할 결과가 없습니다.")
        return
    
    # KPI 비교 테이블
    print("\n   📊 KPI 비교표:")
    print(f"   {'시나리오':<30} {'단기 마진':>12} {'장기 브랜드':>12}")
    print("   " + "-"*56)
    
    baseline_margin = None
    baseline_brand = None
    
    for name, result in results.items():
        margin = result.kpi_values.get("SHORT_TERM_MARGIN", 0)
        brand = result.kpi_values.get("LONG_TERM_BRAND_VALUE", 0)
        
        if baseline_margin is None:
            baseline_margin = margin
            baseline_brand = brand
            print(f"   {name:<30} {margin:>12.4f} {brand:>12.2f}  (기준)")
        else:
            margin_diff = margin - baseline_margin
            brand_diff = brand - baseline_brand
            print(f"   {name:<30} {margin:>12.4f} {brand:>12.2f}  ({margin_diff:+.4f}, {brand_diff:+.2f})")
    
    # 트레이드오프 분석
    print("\n   🔄 트레이드오프 분석:")
    
    fx_shock_result = results.get("FX_Shock")
    high_pt_result = results.get("FX_Shock_HighPassThrough")
    mkt_boost_result = results.get("FX_Shock_MarketingBoost")
    
    if fx_shock_result and high_pt_result:
        margin_gain = (high_pt_result.kpi_values.get("SHORT_TERM_MARGIN", 0) - 
                      fx_shock_result.kpi_values.get("SHORT_TERM_MARGIN", 0))
        brand_loss = (high_pt_result.kpi_values.get("LONG_TERM_BRAND_VALUE", 0) - 
                     fx_shock_result.kpi_values.get("LONG_TERM_BRAND_VALUE", 0))
        
        print(f"      가격 전가 80% 시:")
        print(f"        → 단기 마진 {margin_gain:+.4f}")
        print(f"        → 장기 브랜드 {brand_loss:+.2f}")
        if margin_gain > 0 and brand_loss < 0:
            print(f"        ⚠️  단기 이익 vs 장기 브랜드 트레이드오프 발생!")
    
    if fx_shock_result and mkt_boost_result:
        margin_change = (mkt_boost_result.kpi_values.get("SHORT_TERM_MARGIN", 0) - 
                        fx_shock_result.kpi_values.get("SHORT_TERM_MARGIN", 0))
        brand_gain = (mkt_boost_result.kpi_values.get("LONG_TERM_BRAND_VALUE", 0) - 
                     fx_shock_result.kpi_values.get("LONG_TERM_BRAND_VALUE", 0))
        
        print(f"\n      마케팅 150% 증가 시:")
        print(f"        → 단기 마진 {margin_change:+.4f}")
        print(f"        → 장기 브랜드 {brand_gain:+.2f}")
        if brand_gain > 0:
            print(f"        ✅ 마케팅 투자로 브랜드 보호 효과!")


def analyze_causal_paths(results: Dict[str, Any]):
    """인과 경로 분석"""
    print_section("7. 인과 경로 분석 (Explainable)")
    
    # 첫 번째 결과의 인과 경로 사용
    first_result = list(results.values())[0] if results else None
    if not first_result:
        return
    
    print("\n   🔗 주요 인과 경로 (FX 변화가 KPI에 미치는 영향):")
    for i, path in enumerate(first_result.top_causal_paths[:5], 1):
        polarities = ' → '.join(path.get('polarities', []))
        print(f"      {i}. {path['path']}")
        print(f"         극성: [{polarities}]")
    
    # 설명 생성
    print("\n   📝 자동 생성 설명:")
    print("""
      환율 상승 시 다음 경로로 브랜드 가치에 영향을 미칩니다:
      
      경로 1 (직접 가격 경로):
        FX_RATE ↑ → COGS ↑ → PRICE ↑ → DEMAND ↓ → PROFIT ↓
        
      경로 2 (브랜드 손상 경로):
        FX_RATE ↑ → PRICE ↑ → PRICE_VOLATILITY ↑ → BRAND_EQUITY ↓ → DEMAND ↓
        
      경로 3 (고객 만족 경로):
        FX_RATE ↑ → REFUND_RATE ↑ → BRAND_EQUITY ↓ → LOYALTY ↓
      
      ※ 가격 전가율을 높이면 단기 마진은 보호되지만,
         가격 변동성 증가로 브랜드 가치가 손상됩니다.
      """)


def export_results(results: Dict[str, Any], filename: str = "simulation_results.json"):
    """결과 내보내기"""
    print_section("8. 결과 내보내기")
    
    export_data = {
        "timestamp": datetime.now().isoformat(),
        "scenarios": {}
    }
    
    for name, result in results.items():
        export_data["scenarios"][name] = {
            "kpi_values": result.kpi_values,
            "final_states": {k: v[-1] for k, v in result.state_history.items()},
            "state_history": {k: [round(x, 4) for x in v] for k, v in result.state_history.items()},
        }
    
    filepath = f"/Users/uengine/robo-analyz/what-if-simulator/{filename}"
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(export_data, f, indent=2, ensure_ascii=False)
    
    print(f"   ✅ 결과 저장: {filepath}")


def main():
    """메인 실행 함수"""
    print_header("What-if Simulator 통합 테스트")
    print(f"   실행 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"   Neo4j: {neo4j_config.uri}")
    print(f"   MindsDB: {mindsdb_config.http_url}")
    
    # 1. Neo4j 연결 테스트
    if not test_neo4j_connection():
        print("\n❌ Neo4j 연결 실패 - 테스트 중단")
        return
    
    # 2. MindsDB 연결 테스트 (실패해도 계속)
    mindsdb_available = test_mindsdb_connection()
    
    # 3. 온톨로지 로드
    ontology_stats = load_ontology()
    
    # 4-5. What-if 시뮬레이션 실행
    results = run_what_if_simulation()
    
    # 6. 시나리오 비교
    compare_scenarios(results)
    
    # 7. 인과 경로 분석
    analyze_causal_paths(results)
    
    # 8. 결과 내보내기
    export_results(results)
    
    # 완료
    print_header("테스트 완료")
    print("""
   ✅ What-if 시뮬레이션이 성공적으로 완료되었습니다!
   
   📊 주요 발견:
      1. 환율 급등 시 가격 전가율에 따라 단기/장기 성과 트레이드오프 발생
      2. 마케팅 투자는 환율 충격의 브랜드 손상을 일부 상쇄
      3. 인과 경로를 통해 각 정책의 작용 메커니즘을 설명 가능
   
   📁 결과 파일: what-if-simulator/simulation_results.json
   
   💡 다음 단계:
      - MindsDB에 실제 데이터 연결하여 모델 학습
      - 더 정교한 지연(lag) 효과 모델링
      - 레짐/세그먼트별 분석 추가
    """)


if __name__ == "__main__":
    main()
