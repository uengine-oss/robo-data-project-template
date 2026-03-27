"""
CLD (Causal Loop Diagram) Generator
====================================

발견된 인과관계를 Neo4j에 저장하고 시각화 가능한 CLD를 생성합니다.

기능:
1. 발견된 인과관계를 Neo4j 그래프로 변환
2. CLD 시각화 (NetworkX + Matplotlib)
3. 기존 CLD와 비교하여 누락된 관계 식별
4. 피드백 루프 자동 탐지

Author: AI Assistant
Created: 2026-01-24
"""

import json
import asyncio
from typing import Dict, List, Tuple, Optional, Any, Set
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
import networkx as nx

try:
    import matplotlib.pyplot as plt
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False

from config import Settings
from neo4j import GraphDatabase


@dataclass
class CLDNode:
    """CLD 노드"""
    name: str
    node_type: str  # 'Driver', 'State', 'KPI', 'External'
    description: str = ""
    
    def to_dict(self) -> Dict:
        return {
            'name': self.name,
            'type': self.node_type,
            'description': self.description
        }


@dataclass
class CLDEdge:
    """CLD 엣지"""
    source: str
    target: str
    polarity: str  # '+' or '-'
    strength: float
    method: str
    is_inferred: bool = True
    
    def to_dict(self) -> Dict:
        return {
            'source': self.source,
            'target': self.target,
            'polarity': self.polarity,
            'strength': self.strength,
            'method': self.method,
            'is_inferred': self.is_inferred
        }


class CLDGenerator:
    """
    Causal Loop Diagram 생성기
    
    발견된 인과관계를 바탕으로 CLD를 구축하고 Neo4j에 저장합니다.
    """
    
    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or Settings()
        self.graph = nx.DiGraph()
        self.nodes: Dict[str, CLDNode] = {}
        self.edges: List[CLDEdge] = []
        
    def load_discovery_results(self, filepath: str) -> Dict[str, Any]:
        """Causal Discovery 결과 로드"""
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def build_graph_from_discovery(self, 
                                   discovery_results: Dict[str, Any],
                                   min_strength: float = 0.3) -> nx.DiGraph:
        """
        발견된 인과관계로부터 NetworkX 그래프 구축
        """
        self.graph = nx.DiGraph()
        edges = discovery_results.get('edges', [])
        
        print(f"\n📊 CLD 구축 중... (최소 강도: {min_strength})")
        
        # 강한 관계만 필터링
        strong_edges = [e for e in edges if e['strength'] >= min_strength]
        
        for edge in strong_edges:
            source = edge['source']
            target = edge['target']
            
            # 노드 추가
            if source not in self.graph:
                self.graph.add_node(source, type='unknown')
                self.nodes[source] = CLDNode(name=source, node_type='unknown')
                
            if target not in self.graph:
                self.graph.add_node(target, type='unknown')
                self.nodes[target] = CLDNode(name=target, node_type='unknown')
            
            # 엣지 추가
            polarity = '+' if edge['direction'] == 'positive' else '-'
            self.graph.add_edge(
                source, target,
                weight=edge['strength'],
                polarity=polarity,
                method=edge['method']
            )
            
            self.edges.append(CLDEdge(
                source=source,
                target=target,
                polarity=polarity,
                strength=edge['strength'],
                method=edge['method']
            ))
            
        print(f"   노드 수: {len(self.graph.nodes)}")
        print(f"   엣지 수: {len(self.graph.edges)}")
        
        return self.graph
    
    def classify_nodes(self):
        """
        노드를 역할별로 분류
        - Driver: 다른 변수에만 영향을 주고 받지 않음 (source only)
        - KPI: 영향만 받고 주지 않음 (target only)
        - State: 영향을 주고받음 (중간 변수)
        """
        for node in self.graph.nodes:
            in_degree = self.graph.in_degree(node)
            out_degree = self.graph.out_degree(node)
            
            if in_degree == 0 and out_degree > 0:
                node_type = 'Driver'
            elif out_degree == 0 and in_degree > 0:
                node_type = 'KPI'
            elif in_degree > 0 and out_degree > 0:
                node_type = 'State'
            else:
                node_type = 'External'
                
            self.nodes[node].node_type = node_type
            self.graph.nodes[node]['type'] = node_type
            
        # 분류 결과 출력
        print("\n🏷️ 노드 분류:")
        for node_type in ['Driver', 'State', 'KPI', 'External']:
            nodes = [n for n, data in self.nodes.items() if data.node_type == node_type]
            if nodes:
                print(f"   {node_type}: {', '.join(nodes[:5])}" + 
                      (f"... (+{len(nodes)-5})" if len(nodes) > 5 else ""))
    
    def detect_feedback_loops(self) -> List[List[str]]:
        """
        피드백 루프 탐지
        
        CLD에서 피드백 루프는 시스템 동적 행동을 결정하는 핵심 요소:
        - Reinforcing Loop (R): 양의 피드백, 성장 또는 붕괴
        - Balancing Loop (B): 음의 피드백, 안정화
        """
        cycles = list(nx.simple_cycles(self.graph))
        
        print(f"\n🔄 피드백 루프 탐지: {len(cycles)}개 발견")
        
        loop_info = []
        for cycle in cycles[:10]:  # 상위 10개만
            # 루프 극성 계산 (양/음)
            total_polarity = 1
            cycle_with_return = cycle + [cycle[0]]
            
            for i in range(len(cycle)):
                source = cycle_with_return[i]
                target = cycle_with_return[i+1]
                edge_data = self.graph.edges.get((source, target), {})
                polarity = edge_data.get('polarity', '+')
                total_polarity *= (1 if polarity == '+' else -1)
            
            loop_type = 'R' if total_polarity > 0 else 'B'
            
            print(f"   [{loop_type}] {' → '.join(cycle)} → {cycle[0]}")
            loop_info.append({
                'nodes': cycle,
                'type': loop_type,
                'length': len(cycle)
            })
            
        return loop_info
    
    def compare_with_existing_cld(self, 
                                  existing_edges: List[Dict]) -> Dict[str, Any]:
        """
        기존 CLD(PRD에서 정의한)와 발견된 CLD 비교
        
        Returns:
            - matched: 일치하는 관계
            - missing_in_data: 기존에 정의되었으나 데이터에서 발견되지 않음
            - newly_discovered: 데이터에서만 발견된 새로운 관계
        """
        existing_set = {(e['source'], e['target']) for e in existing_edges}
        discovered_set = {(e.source, e.target) for e in self.edges}
        
        matched = existing_set & discovered_set
        missing_in_data = existing_set - discovered_set
        newly_discovered = discovered_set - existing_set
        
        print("\n🔍 기존 CLD와 비교:")
        print(f"   ✅ 일치: {len(matched)}개")
        print(f"   ❌ 데이터에서 미발견: {len(missing_in_data)}개")
        print(f"   🆕 새로 발견: {len(newly_discovered)}개")
        
        if newly_discovered:
            print("\n   새로 발견된 관계:")
            for src, tgt in list(newly_discovered)[:5]:
                print(f"      {src} → {tgt}")
                
        return {
            'matched': list(matched),
            'missing_in_data': list(missing_in_data),
            'newly_discovered': list(newly_discovered)
        }
    
    def visualize(self, 
                  output_path: str = 'cld_visualization.png',
                  figsize: Tuple[int, int] = (16, 12)):
        """
        CLD 시각화
        """
        if not MATPLOTLIB_AVAILABLE:
            print("⚠️ matplotlib가 설치되지 않았습니다.")
            return
            
        fig, ax = plt.subplots(figsize=figsize)
        
        # 노드 색상 매핑
        color_map = {
            'Driver': '#4CAF50',    # 초록 (원인)
            'State': '#2196F3',      # 파랑 (상태)
            'KPI': '#FF5722',        # 주황 (결과)
            'External': '#9E9E9E'    # 회색
        }
        
        node_colors = [
            color_map.get(self.nodes.get(n, CLDNode(n, 'External')).node_type, '#9E9E9E')
            for n in self.graph.nodes
        ]
        
        # 레이아웃 계산
        pos = nx.spring_layout(self.graph, k=2, iterations=50, seed=42)
        
        # 노드 그리기
        nx.draw_networkx_nodes(
            self.graph, pos,
            node_color=node_colors,
            node_size=2000,
            alpha=0.9,
            ax=ax
        )
        
        # 노드 레이블
        nx.draw_networkx_labels(
            self.graph, pos,
            font_size=8,
            font_weight='bold',
            ax=ax
        )
        
        # 엣지 그리기 (극성에 따라 색상 구분)
        positive_edges = [(u, v) for u, v, d in self.graph.edges(data=True) 
                         if d.get('polarity', '+') == '+']
        negative_edges = [(u, v) for u, v, d in self.graph.edges(data=True) 
                         if d.get('polarity', '+') == '-']
        
        nx.draw_networkx_edges(
            self.graph, pos,
            edgelist=positive_edges,
            edge_color='#4CAF50',
            arrows=True,
            arrowsize=20,
            connectionstyle='arc3,rad=0.1',
            alpha=0.7,
            ax=ax
        )
        
        nx.draw_networkx_edges(
            self.graph, pos,
            edgelist=negative_edges,
            edge_color='#F44336',
            arrows=True,
            arrowsize=20,
            connectionstyle='arc3,rad=0.1',
            style='dashed',
            alpha=0.7,
            ax=ax
        )
        
        # 범례
        from matplotlib.patches import Patch
        legend_elements = [
            Patch(facecolor='#4CAF50', label='Driver (원인)'),
            Patch(facecolor='#2196F3', label='State (상태)'),
            Patch(facecolor='#FF5722', label='KPI (결과)'),
            Patch(facecolor='#4CAF50', edgecolor='#4CAF50', label='+ 영향 (양)'),
            Patch(facecolor='#F44336', edgecolor='#F44336', label='- 영향 (음)')
        ]
        ax.legend(handles=legend_elements, loc='upper left', fontsize=10)
        
        ax.set_title('Causal Loop Diagram (CLD)\n데이터 기반 자동 생성', 
                    fontsize=14, fontweight='bold')
        ax.axis('off')
        
        plt.tight_layout()
        plt.savefig(output_path, dpi=150, bbox_inches='tight')
        plt.close()
        
        print(f"\n📊 시각화 저장: {output_path}")
    
    async def save_to_neo4j(self):
        """
        발견된 CLD를 Neo4j에 저장
        """
        print("\n🗄️ Neo4j에 CLD 저장 중...")
        
        driver = GraphDatabase.driver(
            self.settings.NEO4J_URI,
            auth=(self.settings.NEO4J_USER, self.settings.NEO4J_PASSWORD)
        )
        
        try:
            with driver.session(database=self.settings.NEO4J_DATABASE) as session:
                # 기존 추론된 관계 삭제
                session.run("MATCH ()-[r:INFERRED_CAUSES]->() DELETE r")
                
                # 노드 생성 또는 업데이트
                for name, node in self.nodes.items():
                    session.run("""
                        MERGE (n:Variable {name: $name})
                        SET n.type = $type,
                            n.inferred = true
                    """, name=name, type=node.node_type)
                
                # 엣지 생성
                for edge in self.edges:
                    session.run("""
                        MATCH (s:Variable {name: $source})
                        MATCH (t:Variable {name: $target})
                        MERGE (s)-[r:INFERRED_CAUSES]->(t)
                        SET r.polarity = $polarity,
                            r.strength = $strength,
                            r.method = $method
                    """, 
                    source=edge.source,
                    target=edge.target,
                    polarity=edge.polarity,
                    strength=edge.strength,
                    method=edge.method)
                
                print(f"   ✅ {len(self.nodes)}개 노드, {len(self.edges)}개 엣지 저장 완료")
                
        finally:
            driver.close()
    
    def generate_influence_function(self, 
                                    edge: CLDEdge,
                                    data: pd.DataFrame) -> Dict[str, Any]:
        """
        각 엣지에 대한 영향 함수 추정
        
        MindsDB 모델 또는 선형 회귀로 영향 함수 도출
        """
        source = edge.source
        target = edge.target
        
        if source not in data.columns or target not in data.columns:
            return {'type': 'unknown', 'params': {}}
        
        X = data[source].values.reshape(-1, 1)
        y = data[target].values
        
        # 간단한 선형 회귀
        from scipy import stats
        slope, intercept, r_value, p_value, std_err = stats.linregress(
            data[source], data[target]
        )
        
        return {
            'type': 'linear',
            'source': source,
            'target': target,
            'params': {
                'slope': round(slope, 4),
                'intercept': round(intercept, 4),
                'r_squared': round(r_value**2, 4),
                'p_value': round(p_value, 6),
                'std_error': round(std_err, 4)
            },
            'formula': f"{target} = {slope:.4f} * {source} + {intercept:.4f}"
        }
    
    def export_influence_functions(self, 
                                   data: pd.DataFrame,
                                   output_path: str = 'influence_functions.json'):
        """모든 엣지에 대한 영향 함수 추정 및 저장"""
        
        print("\n📐 영향 함수 추정 중...")
        
        functions = []
        for edge in self.edges:
            func = self.generate_influence_function(edge, data)
            if func['type'] != 'unknown':
                functions.append(func)
                
        print(f"   추정된 함수: {len(functions)}개")
        
        # 상위 10개 출력
        print("\n📊 주요 영향 함수:")
        sorted_funcs = sorted(
            functions, 
            key=lambda x: abs(x['params'].get('slope', 0)), 
            reverse=True
        )
        
        for func in sorted_funcs[:10]:
            r2 = func['params']['r_squared']
            print(f"   {func['formula']} (R² = {r2:.3f})")
        
        # 저장
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump({
                'generated_at': pd.Timestamp.now().isoformat(),
                'total_functions': len(functions),
                'functions': functions
            }, f, indent=2, ensure_ascii=False)
            
        print(f"\n💾 영향 함수 저장: {output_path}")
        
        return functions


# =============================================================================
# 메인 실행
# =============================================================================

if __name__ == "__main__":
    async def main():
        print("\n" + "🎨" * 30)
        print(" CLD GENERATOR")
        print("🎨" * 30)
        
        # CLD 생성기 초기화
        generator = CLDGenerator()
        
        # Causal Discovery 결과 로드
        results_path = 'causal_discovery_results.json'
        
        if not Path(results_path).exists():
            print(f"⚠️ {results_path}가 없습니다. 먼저 causal_discovery.py를 실행하세요.")
            return
            
        discovery_results = generator.load_discovery_results(results_path)
        print(f"\n📂 로드된 결과: {len(discovery_results.get('edges', []))}개 관계")
        
        # 그래프 구축
        generator.build_graph_from_discovery(discovery_results, min_strength=0.3)
        
        # 노드 분류
        generator.classify_nodes()
        
        # 피드백 루프 탐지
        loops = generator.detect_feedback_loops()
        
        # 시각화
        generator.visualize('cld_visualization.png')
        
        # 영향 함수 추정
        data = pd.read_csv('kpi_monthly.csv')
        exclude_cols = ['year_month', 'month_num']
        data = data[[c for c in data.columns if c not in exclude_cols]]
        functions = generator.export_influence_functions(data)
        
        # Neo4j 저장 (선택적)
        try:
            await generator.save_to_neo4j()
        except Exception as e:
            print(f"⚠️ Neo4j 저장 실패: {e}")
        
        print("\n" + "=" * 60)
        print("✅ CLD 생성 완료!")
        print("=" * 60)
        print("\n생성된 파일:")
        print("   - causal_discovery_results.json (인과관계 데이터)")
        print("   - cld_visualization.png (시각화)")
        print("   - influence_functions.json (영향 함수)")
        
        return generator
    
    asyncio.run(main())
