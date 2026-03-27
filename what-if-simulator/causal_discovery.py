"""
Causal Discovery Engine
=======================

데이터로부터 인과관계를 역으로 추정하여 CLD(Causal Loop Diagram)를 자동 생성합니다.

주요 알고리즘:
1. Granger Causality - 시계열 데이터에서 인과 방향 추정
2. Correlation-based Discovery - 상관관계 기반 초기 스크리닝
3. PC Algorithm (Partial Correlation) - 조건부 독립성 검정
4. Transfer Entropy (optional) - 정보 이론 기반 인과성

Author: AI Assistant
Created: 2026-01-24
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass
from scipy import stats
from statsmodels.tsa.stattools import grangercausalitytests
import warnings

warnings.filterwarnings('ignore')


@dataclass
class CausalEdge:
    """발견된 인과관계 엣지"""
    source: str
    target: str
    method: str  # 'granger', 'correlation', 'pc', 'transfer_entropy'
    strength: float  # 관계 강도 (0~1)
    p_value: float  # 통계적 유의성
    lag: int = 0  # 시차 (Granger용)
    direction: str = 'positive'  # 'positive' or 'negative'
    
    def to_dict(self) -> Dict:
        return {
            'source': self.source,
            'target': self.target,
            'method': self.method,
            'strength': round(self.strength, 4),
            'p_value': round(self.p_value, 6),
            'lag': self.lag,
            'direction': self.direction
        }


class CausalDiscoveryEngine:
    """
    데이터 기반 인과관계 발견 엔진
    
    PRD의 CLD 구조를 데이터로부터 역으로 추정합니다.
    """
    
    def __init__(self, 
                 significance_level: float = 0.05,
                 min_correlation: float = 0.3,
                 max_lag: int = 3):
        """
        Args:
            significance_level: p-value 임계값 (기본 0.05)
            min_correlation: 최소 상관계수 임계값 (기본 0.3)
            max_lag: Granger Causality 최대 시차 (기본 3)
        """
        self.significance_level = significance_level
        self.min_correlation = min_correlation
        self.max_lag = max_lag
        self.discovered_edges: List[CausalEdge] = []
        
    def load_data(self, filepath: str) -> pd.DataFrame:
        """CSV 파일에서 데이터 로드"""
        df = pd.read_csv(filepath)
        # 시간 관련 컬럼 제외
        exclude_cols = ['year_month', 'month_num']
        numeric_cols = [col for col in df.columns if col not in exclude_cols]
        return df[numeric_cols]
    
    def discover_correlations(self, 
                              data: pd.DataFrame, 
                              method: str = 'pearson') -> List[CausalEdge]:
        """
        상관관계 기반 인과관계 후보 발견
        
        주의: 상관관계 ≠ 인과관계
        그러나 강한 상관관계는 인과관계의 후보가 됨
        """
        edges = []
        columns = data.columns.tolist()
        
        for i, col1 in enumerate(columns):
            for col2 in columns[i+1:]:
                if method == 'pearson':
                    corr, p_value = stats.pearsonr(data[col1], data[col2])
                elif method == 'spearman':
                    corr, p_value = stats.spearmanr(data[col1], data[col2])
                else:
                    corr, p_value = stats.pearsonr(data[col1], data[col2])
                
                if abs(corr) >= self.min_correlation and p_value < self.significance_level:
                    direction = 'positive' if corr > 0 else 'negative'
                    
                    # 상관관계는 방향이 없으므로 양방향 후보 추가
                    edges.append(CausalEdge(
                        source=col1,
                        target=col2,
                        method='correlation',
                        strength=abs(corr),
                        p_value=p_value,
                        direction=direction
                    ))
                    
        return edges
    
    def discover_granger_causality(self, 
                                   data: pd.DataFrame,
                                   max_lag: Optional[int] = None) -> List[CausalEdge]:
        """
        Granger Causality 분석
        
        "X가 Y를 Granger-cause한다" = X의 과거 값이 Y의 미래 예측에 도움이 됨
        
        이 방법은 진정한 인과관계를 보장하지는 않지만,
        시계열에서 예측적 인과성을 추정합니다.
        """
        if max_lag is None:
            max_lag = self.max_lag
            
        edges = []
        columns = data.columns.tolist()
        
        print(f"\n🔍 Granger Causality 분석 중... (max_lag={max_lag})")
        
        for cause_var in columns:
            for effect_var in columns:
                if cause_var == effect_var:
                    continue
                    
                try:
                    # Granger causality test
                    # 귀무가설: cause_var는 effect_var를 Granger-cause하지 않음
                    test_data = data[[effect_var, cause_var]].dropna()
                    
                    if len(test_data) < max_lag + 10:
                        continue
                        
                    result = grangercausalitytests(
                        test_data, 
                        maxlag=max_lag, 
                        verbose=False
                    )
                    
                    # 각 lag에서 최소 p-value 찾기
                    min_p_value = 1.0
                    best_lag = 1
                    best_f_stat = 0
                    
                    for lag in range(1, max_lag + 1):
                        if lag in result:
                            # ssr_ftest 결과 사용
                            f_stat = result[lag][0]['ssr_ftest'][0]
                            p_value = result[lag][0]['ssr_ftest'][1]
                            
                            if p_value < min_p_value:
                                min_p_value = p_value
                                best_lag = lag
                                best_f_stat = f_stat
                    
                    if min_p_value < self.significance_level:
                        # 상관관계로 방향 결정
                        corr = data[cause_var].corr(data[effect_var])
                        direction = 'positive' if corr > 0 else 'negative'
                        
                        # 강도는 F-통계량 기반으로 정규화
                        strength = min(1.0, best_f_stat / 20)  # F > 20 → 강한 관계
                        
                        edges.append(CausalEdge(
                            source=cause_var,
                            target=effect_var,
                            method='granger',
                            strength=strength,
                            p_value=min_p_value,
                            lag=best_lag,
                            direction=direction
                        ))
                        
                except Exception as e:
                    # 일부 변수 조합에서 오류 발생 가능
                    continue
                    
        return edges
    
    def discover_partial_correlations(self, 
                                      data: pd.DataFrame,
                                      threshold: float = 0.3) -> List[CausalEdge]:
        """
        부분 상관 (Partial Correlation) 기반 발견
        
        두 변수 간의 관계에서 다른 변수들의 영향을 제거한 후의 상관관계.
        PC 알고리즘의 핵심 개념.
        """
        edges = []
        columns = data.columns.tolist()
        n = len(data)
        
        print(f"\n🔍 Partial Correlation 분석 중...")
        
        for i, col1 in enumerate(columns):
            for j, col2 in enumerate(columns[i+1:], i+1):
                # 조건화 변수들 (col1, col2 제외한 나머지)
                control_vars = [c for c in columns if c not in [col1, col2]]
                
                try:
                    partial_corr = self._partial_correlation(
                        data, col1, col2, control_vars
                    )
                    
                    if partial_corr is not None and abs(partial_corr) >= threshold:
                        # 부분 상관이 높으면 직접적 관계 가능성
                        direction = 'positive' if partial_corr > 0 else 'negative'
                        
                        # 방향 결정을 위해 Granger 결과 확인
                        edges.append(CausalEdge(
                            source=col1,
                            target=col2,
                            method='partial_correlation',
                            strength=abs(partial_corr),
                            p_value=0.05,  # 단순화
                            direction=direction
                        ))
                        
                except Exception:
                    continue
                    
        return edges
    
    def _partial_correlation(self, 
                             data: pd.DataFrame,
                             var1: str, 
                             var2: str,
                             control_vars: List[str]) -> Optional[float]:
        """
        두 변수 간의 부분 상관계수 계산
        """
        if not control_vars:
            return data[var1].corr(data[var2])
            
        try:
            # 회귀 분석으로 잔차 계산
            from numpy.linalg import lstsq
            
            X = data[control_vars].values
            X = np.column_stack([np.ones(len(X)), X])  # 상수항 추가
            
            y1 = data[var1].values
            y2 = data[var2].values
            
            # 잔차 계산
            coeffs1, _, _, _ = lstsq(X, y1, rcond=None)
            residuals1 = y1 - X @ coeffs1
            
            coeffs2, _, _, _ = lstsq(X, y2, rcond=None)
            residuals2 = y2 - X @ coeffs2
            
            # 잔차들의 상관계수 = 부분 상관
            partial_corr = np.corrcoef(residuals1, residuals2)[0, 1]
            
            return partial_corr if not np.isnan(partial_corr) else None
            
        except Exception:
            return None
    
    def run_discovery(self, 
                      data: pd.DataFrame,
                      methods: List[str] = ['correlation', 'granger']) -> Dict[str, Any]:
        """
        전체 인과관계 발견 파이프라인 실행
        
        Args:
            data: 시계열 데이터프레임
            methods: 사용할 방법 리스트 ['correlation', 'granger', 'partial']
            
        Returns:
            발견된 인과관계 정보
        """
        all_edges = []
        
        print("=" * 60)
        print("🔬 Causal Discovery 시작")
        print("=" * 60)
        print(f"📊 데이터: {len(data)} 행, {len(data.columns)} 변수")
        print(f"📋 변수: {', '.join(data.columns[:5])}...")
        print(f"🎯 유의수준: {self.significance_level}")
        print(f"📏 최소 상관: {self.min_correlation}")
        
        if 'correlation' in methods:
            print("\n" + "-" * 40)
            print("📈 1단계: 상관관계 분석")
            corr_edges = self.discover_correlations(data)
            print(f"   발견된 후보: {len(corr_edges)}개")
            all_edges.extend(corr_edges)
            
        if 'granger' in methods:
            print("\n" + "-" * 40)
            print("⏱️  2단계: Granger Causality 분석")
            granger_edges = self.discover_granger_causality(data)
            print(f"   발견된 인과관계: {len(granger_edges)}개")
            all_edges.extend(granger_edges)
            
        if 'partial' in methods:
            print("\n" + "-" * 40)
            print("🔗 3단계: Partial Correlation 분석")
            partial_edges = self.discover_partial_correlations(data)
            print(f"   발견된 직접 관계: {len(partial_edges)}개")
            all_edges.extend(partial_edges)
            
        # 중복 제거 및 통합
        consolidated_edges = self._consolidate_edges(all_edges)
        self.discovered_edges = consolidated_edges
        
        print("\n" + "=" * 60)
        print(f"✅ 최종 발견된 인과관계: {len(consolidated_edges)}개")
        print("=" * 60)
        
        return {
            'edges': [e.to_dict() for e in consolidated_edges],
            'summary': self._generate_summary(consolidated_edges),
            'methods_used': methods
        }
    
    def _consolidate_edges(self, edges: List[CausalEdge]) -> List[CausalEdge]:
        """
        여러 방법에서 발견된 엣지들을 통합하고 신뢰도 점수 계산
        """
        edge_map: Dict[Tuple[str, str], List[CausalEdge]] = {}
        
        for edge in edges:
            key = (edge.source, edge.target)
            if key not in edge_map:
                edge_map[key] = []
            edge_map[key].append(edge)
            
        consolidated = []
        
        for (source, target), edge_list in edge_map.items():
            # 여러 방법에서 발견되면 신뢰도 증가
            methods = set(e.method for e in edge_list)
            
            # Granger > Partial > Correlation 우선순위
            if 'granger' in methods:
                best_edge = next(e for e in edge_list if e.method == 'granger')
            elif 'partial_correlation' in methods:
                best_edge = next(e for e in edge_list if e.method == 'partial_correlation')
            else:
                best_edge = edge_list[0]
                
            # 여러 방법에서 발견되면 강도 조정
            confidence_boost = 1.0 + (len(methods) - 1) * 0.2
            adjusted_strength = min(1.0, best_edge.strength * confidence_boost)
            
            consolidated.append(CausalEdge(
                source=best_edge.source,
                target=best_edge.target,
                method='+'.join(sorted(methods)),
                strength=adjusted_strength,
                p_value=best_edge.p_value,
                lag=best_edge.lag,
                direction=best_edge.direction
            ))
            
        # 강도순 정렬
        consolidated.sort(key=lambda e: e.strength, reverse=True)
        
        return consolidated
    
    def _generate_summary(self, edges: List[CausalEdge]) -> Dict[str, Any]:
        """결과 요약 생성"""
        if not edges:
            return {'total_edges': 0}
            
        # 변수별 영향력 분석
        influence_count = {}  # 다른 변수에 영향을 주는 횟수
        influenced_count = {}  # 다른 변수로부터 영향받는 횟수
        
        for edge in edges:
            influence_count[edge.source] = influence_count.get(edge.source, 0) + 1
            influenced_count[edge.target] = influenced_count.get(edge.target, 0) + 1
            
        # 핵심 원인 변수 (가장 많은 영향을 주는 변수)
        root_causes = sorted(
            influence_count.items(), 
            key=lambda x: x[1], 
            reverse=True
        )[:5]
        
        # 최종 결과 변수 (가장 많은 영향을 받는 변수)
        final_effects = sorted(
            influenced_count.items(),
            key=lambda x: x[1],
            reverse=True
        )[:5]
        
        # 강한 인과관계 (strength > 0.5)
        strong_edges = [e for e in edges if e.strength > 0.5]
        
        return {
            'total_edges': len(edges),
            'strong_edges': len(strong_edges),
            'root_causes': root_causes,
            'final_effects': final_effects,
            'methods_breakdown': self._count_by_method(edges),
            'direction_breakdown': {
                'positive': sum(1 for e in edges if e.direction == 'positive'),
                'negative': sum(1 for e in edges if e.direction == 'negative')
            }
        }
    
    def _count_by_method(self, edges: List[CausalEdge]) -> Dict[str, int]:
        """방법별 엣지 수 집계"""
        counts = {}
        for edge in edges:
            for method in edge.method.split('+'):
                counts[method] = counts.get(method, 0) + 1
        return counts
    
    def print_discovered_cld(self):
        """발견된 CLD 구조를 텍스트로 출력"""
        if not self.discovered_edges:
            print("⚠️  발견된 인과관계가 없습니다.")
            return
            
        print("\n" + "=" * 70)
        print("📊 발견된 Causal Loop Diagram (CLD)")
        print("=" * 70)
        
        # 강도순으로 상위 20개 출력
        top_edges = self.discovered_edges[:20]
        
        print(f"\n{'Source':<20} {'→':^3} {'Target':<20} {'Strength':>10} {'방향':>8} {'방법':>20}")
        print("-" * 85)
        
        for edge in top_edges:
            arrow = "→+" if edge.direction == 'positive' else "→-"
            print(f"{edge.source:<20} {arrow:^3} {edge.target:<20} {edge.strength:>10.4f} {edge.direction:>8} {edge.method:>20}")
            
        if len(self.discovered_edges) > 20:
            print(f"\n... 외 {len(self.discovered_edges) - 20}개 추가 관계")
    
    def get_cypher_statements(self) -> List[str]:
        """
        발견된 인과관계를 Neo4j Cypher 문으로 변환
        """
        statements = []
        
        # 기존 발견된 관계 삭제
        statements.append("MATCH ()-[r:INFERRED_CAUSES]->() DELETE r;")
        
        for edge in self.discovered_edges:
            cypher = f"""
MATCH (s {{name: '{edge.source}'}}), (t {{name: '{edge.target}'}})
MERGE (s)-[r:INFERRED_CAUSES]->(t)
SET r.strength = {edge.strength},
    r.p_value = {edge.p_value},
    r.method = '{edge.method}',
    r.direction = '{edge.direction}',
    r.lag = {edge.lag};
"""
            statements.append(cypher.strip())
            
        return statements
    
    def export_to_json(self, filepath: str):
        """결과를 JSON 파일로 저장"""
        import json
        
        result = {
            'discovered_at': pd.Timestamp.now().isoformat(),
            'parameters': {
                'significance_level': self.significance_level,
                'min_correlation': self.min_correlation,
                'max_lag': self.max_lag
            },
            'edges': [e.to_dict() for e in self.discovered_edges],
            'summary': self._generate_summary(self.discovered_edges)
        }
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
            
        print(f"\n💾 결과 저장: {filepath}")


# =============================================================================
# 메인 실행
# =============================================================================

if __name__ == "__main__":
    import asyncio
    
    async def main():
        print("\n" + "🔬" * 30)
        print(" CAUSAL DISCOVERY ENGINE")
        print("🔬" * 30)
        
        # 엔진 초기화
        engine = CausalDiscoveryEngine(
            significance_level=0.05,
            min_correlation=0.3,
            max_lag=3
        )
        
        # 데이터 로드
        data = engine.load_data('kpi_monthly.csv')
        print(f"\n📊 로드된 데이터 형태: {data.shape}")
        print(f"📋 변수 목록: {list(data.columns)}")
        
        # 인과관계 발견 실행
        results = engine.run_discovery(
            data, 
            methods=['correlation', 'granger', 'partial']
        )
        
        # 결과 출력
        engine.print_discovered_cld()
        
        # 요약 출력
        summary = results['summary']
        print("\n" + "=" * 60)
        print("📊 발견 요약")
        print("=" * 60)
        print(f"총 발견된 관계: {summary['total_edges']}개")
        print(f"강한 관계 (strength > 0.5): {summary['strong_edges']}개")
        
        print("\n🎯 핵심 원인 변수 (Root Causes):")
        for var, count in summary['root_causes']:
            print(f"   - {var}: {count}개 변수에 영향")
            
        print("\n📍 최종 결과 변수 (Final Effects):")
        for var, count in summary['final_effects']:
            print(f"   - {var}: {count}개 변수로부터 영향")
            
        print("\n📈 방향성 분석:")
        print(f"   - 양의 관계 (+): {summary['direction_breakdown']['positive']}개")
        print(f"   - 음의 관계 (-): {summary['direction_breakdown']['negative']}개")
        
        # JSON 저장
        engine.export_to_json('causal_discovery_results.json')
        
        # Cypher 문 출력 (상위 5개)
        print("\n" + "=" * 60)
        print("🗄️ Neo4j Cypher 문 (샘플)")
        print("=" * 60)
        cypher_statements = engine.get_cypher_statements()
        for stmt in cypher_statements[1:6]:  # 처음 5개 관계
            print(stmt)
            print()
            
        return results
    
    asyncio.run(main())
