"""
Reverse CLD Test
================

데이터 기반 인과관계 역추정 전체 파이프라인 테스트

실행 순서:
1. Causal Discovery 실행 (데이터 → 인과관계 추정)
2. CLD 생성 (추정된 관계 → 그래프 구축)
3. Neo4j 저장 및 시각화
4. 기존 CLD와 비교 분석

Author: AI Assistant
Created: 2026-01-24
"""

import asyncio
import json
from pathlib import Path

import pandas as pd
import numpy as np

from causal_discovery import CausalDiscoveryEngine
from cld_generator import CLDGenerator
from config import Settings


# PRD에서 정의한 기존 CLD 관계 (비교용)
EXISTING_CLD_EDGES = [
    # Driver → State
    {'source': 'fx_rate', 'target': 'cogs'},
    {'source': 'pass_through', 'target': 'price'},
    {'source': 'mkt_spend', 'target': 'brand_equity'},
    {'source': 'service_level', 'target': 'delivery_time'},
    {'source': 'service_level', 'target': 'refund_rate'},
    
    # State → State
    {'source': 'cogs', 'target': 'price'},
    {'source': 'price', 'target': 'demand'},
    {'source': 'brand_equity', 'target': 'demand'},
    {'source': 'brand_equity', 'target': 'loyalty'},
    {'source': 'delivery_time', 'target': 'csat'},
    {'source': 'refund_rate', 'target': 'csat'},
    {'source': 'csat', 'target': 'brand_equity'},
    
    # State → KPI
    {'source': 'price', 'target': 'sales'},
    {'source': 'demand', 'target': 'sales'},
    {'source': 'sales', 'target': 'profit'},
    {'source': 'cogs', 'target': 'profit'},
    {'source': 'profit', 'target': 'margin'},
]


async def run_full_pipeline():
    """전체 역추정 파이프라인 실행"""
    
    print("\n")
    print("=" * 70)
    print("🔬 REVERSE CLD GENERATION PIPELINE")
    print("   데이터 기반 인과관계 역추정")
    print("=" * 70)
    
    # ==========================================================================
    # 1단계: 데이터 로드 및 확인
    # ==========================================================================
    print("\n" + "━" * 70)
    print("📊 1단계: 데이터 로드")
    print("━" * 70)
    
    data_path = 'kpi_monthly.csv'
    if not Path(data_path).exists():
        print(f"❌ 데이터 파일 없음: {data_path}")
        return
        
    df = pd.read_csv(data_path)
    print(f"   파일: {data_path}")
    print(f"   행 수: {len(df)}")
    print(f"   열 수: {len(df.columns)}")
    print(f"   기간: {df['year_month'].iloc[0]} ~ {df['year_month'].iloc[-1]}")
    
    # 기술 통계
    numeric_df = df.select_dtypes(include=[np.number])
    exclude_cols = ['month_num']
    numeric_df = numeric_df[[c for c in numeric_df.columns if c not in exclude_cols]]
    
    print(f"\n   📈 변수 통계 (샘플):")
    for col in ['fx_rate', 'cogs', 'price', 'demand', 'profit']:
        if col in numeric_df.columns:
            mean = numeric_df[col].mean()
            std = numeric_df[col].std()
            print(f"      {col}: 평균={mean:.2f}, 표준편차={std:.2f}")
    
    # ==========================================================================
    # 2단계: Causal Discovery 실행
    # ==========================================================================
    print("\n" + "━" * 70)
    print("🔍 2단계: Causal Discovery 실행")
    print("━" * 70)
    
    discovery_engine = CausalDiscoveryEngine(
        significance_level=0.05,
        min_correlation=0.35,  # 좀 더 엄격하게
        max_lag=2  # 빠른 실행을 위해
    )
    
    # 분석용 데이터 준비
    analysis_data = numeric_df.copy()
    
    discovery_results = discovery_engine.run_discovery(
        analysis_data,
        methods=['correlation', 'granger', 'partial']
    )
    
    # 발견된 CLD 출력
    discovery_engine.print_discovered_cld()
    
    # 결과 저장
    discovery_engine.export_to_json('causal_discovery_results.json')
    
    # ==========================================================================
    # 3단계: CLD 생성 및 분석
    # ==========================================================================
    print("\n" + "━" * 70)
    print("🎨 3단계: CLD 생성 및 분석")
    print("━" * 70)
    
    cld_generator = CLDGenerator()
    
    # 그래프 구축
    cld_generator.build_graph_from_discovery(
        discovery_results, 
        min_strength=0.3
    )
    
    # 노드 분류 (Driver, State, KPI)
    cld_generator.classify_nodes()
    
    # 피드백 루프 탐지
    print("\n🔄 피드백 루프 분석:")
    loops = cld_generator.detect_feedback_loops()
    
    if loops:
        print(f"\n   발견된 루프 유형:")
        r_loops = [l for l in loops if l['type'] == 'R']
        b_loops = [l for l in loops if l['type'] == 'B']
        print(f"   - Reinforcing (강화) 루프: {len(r_loops)}개")
        print(f"   - Balancing (균형) 루프: {len(b_loops)}개")
    
    # ==========================================================================
    # 4단계: 기존 CLD와 비교
    # ==========================================================================
    print("\n" + "━" * 70)
    print("🔎 4단계: PRD 정의 CLD와 비교")
    print("━" * 70)
    
    comparison = cld_generator.compare_with_existing_cld(EXISTING_CLD_EDGES)
    
    print(f"\n   📊 비교 결과:")
    print(f"   ✅ 일치하는 관계: {len(comparison['matched'])}개")
    print(f"      (데이터에서도 해당 인과관계가 발견됨)")
    
    print(f"\n   ⚠️ 데이터에서 미발견: {len(comparison['missing_in_data'])}개")
    print(f"      (PRD에서 정의했으나 데이터에서 통계적으로 유의하지 않음)")
    for src, tgt in comparison['missing_in_data'][:5]:
        print(f"         - {src} → {tgt}")
    
    print(f"\n   🆕 새로 발견된 관계: {len(comparison['newly_discovered'])}개")
    print(f"      (PRD에 없지만 데이터에서 발견됨 - 검토 필요)")
    for src, tgt in list(comparison['newly_discovered'])[:5]:
        # 해당 엣지의 강도 찾기
        edge = next((e for e in cld_generator.edges 
                    if e.source == src and e.target == tgt), None)
        if edge:
            print(f"         - {src} → {tgt} (강도: {edge.strength:.3f})")
    
    # ==========================================================================
    # 5단계: 영향 함수 추정
    # ==========================================================================
    print("\n" + "━" * 70)
    print("📐 5단계: 영향 함수 (Edge Function) 추정")
    print("━" * 70)
    
    functions = cld_generator.export_influence_functions(
        analysis_data,
        'influence_functions.json'
    )
    
    # 주요 관계에 대한 회귀식 출력
    print("\n   📈 핵심 인과관계 수식:")
    
    # PRD에서 정의한 주요 관계들
    key_relations = [
        ('fx_rate', 'cogs'),
        ('price', 'demand'),
        ('cogs', 'profit'),
        ('brand_equity', 'loyalty'),
        ('service_level', 'csat')
    ]
    
    for src, tgt in key_relations:
        func = next((f for f in functions 
                    if f.get('source') == src and f.get('target') == tgt), None)
        if func:
            r2 = func['params']['r_squared']
            print(f"      {func['formula']}")
            print(f"         → R² = {r2:.4f} ({'좋음' if r2 > 0.5 else '보통' if r2 > 0.2 else '약함'})")
    
    # ==========================================================================
    # 6단계: 시각화 및 저장
    # ==========================================================================
    print("\n" + "━" * 70)
    print("💾 6단계: 결과 저장")
    print("━" * 70)
    
    # CLD 시각화
    try:
        cld_generator.visualize('cld_visualization.png')
    except Exception as e:
        print(f"   ⚠️ 시각화 실패 (matplotlib 필요): {e}")
    
    # Neo4j 저장
    try:
        await cld_generator.save_to_neo4j()
    except Exception as e:
        print(f"   ⚠️ Neo4j 저장 실패: {e}")
    
    # ==========================================================================
    # 최종 요약
    # ==========================================================================
    print("\n" + "=" * 70)
    print("📊 최종 요약 리포트")
    print("=" * 70)
    
    summary = discovery_results.get('summary', {})
    
    print(f"""
┌─────────────────────────────────────────────────────────────────┐
│ 🔬 Causal Discovery 결과                                        │
├─────────────────────────────────────────────────────────────────┤
│ 총 발견된 인과관계: {summary.get('total_edges', 0):>4}개                              │
│ 강한 관계 (strength > 0.5): {summary.get('strong_edges', 0):>4}개                       │
│ 양의 관계 (+): {summary.get('direction_breakdown', {}).get('positive', 0):>4}개                                        │
│ 음의 관계 (-): {summary.get('direction_breakdown', {}).get('negative', 0):>4}개                                        │
├─────────────────────────────────────────────────────────────────┤
│ 🎯 핵심 원인 변수 (Root Causes):                                 │""")
    
    for var, count in summary.get('root_causes', [])[:3]:
        print(f"│    - {var:<15} → {count}개 변수에 영향                       │")
    
    print(f"""├─────────────────────────────────────────────────────────────────┤
│ 📍 최종 결과 변수 (Final Effects):                               │""")
    
    for var, count in summary.get('final_effects', [])[:3]:
        print(f"│    - {var:<15} ← {count}개 변수로부터 영향                   │")
    
    print(f"""├─────────────────────────────────────────────────────────────────┤
│ 🔄 피드백 루프: {len(loops)}개 발견                                        │
│ 📊 기존 CLD 일치율: {len(comparison['matched'])}/{len(EXISTING_CLD_EDGES)} ({100*len(comparison['matched'])/len(EXISTING_CLD_EDGES):.0f}%)                                    │
└─────────────────────────────────────────────────────────────────┘
""")
    
    print("\n📁 생성된 파일:")
    print("   1. causal_discovery_results.json  - 인과관계 발견 결과")
    print("   2. influence_functions.json       - 엣지별 영향 함수")
    print("   3. cld_visualization.png          - CLD 시각화")
    
    print("\n✅ 역방향 CLD 생성 파이프라인 완료!")
    
    return {
        'discovery_results': discovery_results,
        'comparison': comparison,
        'functions': functions,
        'loops': loops
    }


async def quick_test():
    """빠른 테스트 (상관관계만)"""
    print("\n🚀 Quick Test Mode")
    
    engine = CausalDiscoveryEngine(
        significance_level=0.05,
        min_correlation=0.4
    )
    
    data = engine.load_data('kpi_monthly.csv')
    results = engine.run_discovery(data, methods=['correlation'])
    engine.print_discovered_cld()
    
    return results


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == '--quick':
        asyncio.run(quick_test())
    else:
        asyncio.run(run_full_pipeline())
