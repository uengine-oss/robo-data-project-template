"""
Causal Discovery API
=====================

인과관계 발견, 검증, 시뮬레이션 API
"""

import json
import asyncio
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
import pandas as pd
import numpy as np
from scipy import stats
from statsmodels.tsa.stattools import grangercausalitytests
import warnings

from .config import settings

warnings.filterwarnings('ignore')


@dataclass
class CausalEdge:
    """인과관계 엣지"""
    source: str
    target: str
    strength: float
    direction: str
    method: str
    p_value: float
    lag: int = 0
    formula: Optional[str] = None
    r_squared: Optional[float] = None
    source_label: Optional[str] = None
    target_label: Optional[str] = None
    
    def to_dict(self) -> Dict:
        result = asdict(self)
        # 라벨이 없으면 자동 생성
        if not result.get('source_label'):
            result['source_label'] = format_variable_label(self.source)
        if not result.get('target_label'):
            result['target_label'] = format_variable_label(self.target)
        return result


# 변수명을 의미 있는 한글 라벨로 변환
VARIABLE_LABEL_MAP = {
    # 환율 관련
    'usd_krw': 'USD/KRW 환율',
    'eur_krw': 'EUR/KRW 환율',
    'jpy_krw': 'JPY/KRW 환율',
    'fx_rate': '외환 환율',
    'exchange_rate': '환율',
    
    # 비용 관련
    'import_cost': '수입 비용',
    'material_cost': '원자재 비용',
    'product_cost': '제품 원가',
    'total_cost': '총 비용',
    'monthly_cogs': '월간 매출원가',
    'labor_cost': '인건비',
    'logistics_cost': '물류비',
    
    # 수익 관련
    'final_profit': '최종 수익',
    'monthly_profit': '월간 수익',
    'gross_profit': '총 이익',
    'net_profit': '순 이익',
    'revenue': '매출',
    'sales_revenue': '판매 매출',
    
    # 판매 관련
    'selling_price': '판매 가격',
    'unit_price': '단가',
    'sales_volume': '판매량',
    'market_demand': '시장 수요',
    'demand': '수요',
    
    # 기타
    'inventory': '재고',
    'production': '생산량',
    'market_share': '시장 점유율',
    'customer_satisfaction': '고객 만족도'
}

# 영어 키워드 → 한글 변환
KEYWORD_TRANSLATIONS = {
    'rate': '율',
    'cost': '비용',
    'price': '가격',
    'profit': '수익',
    'revenue': '매출',
    'sales': '판매',
    'demand': '수요',
    'supply': '공급',
    'volume': '량',
    'total': '총',
    'monthly': '월간',
    'daily': '일간',
    'annual': '연간',
    'import': '수입',
    'export': '수출',
    'material': '원자재',
    'product': '제품',
    'market': '시장',
    'exchange': '환율',
    'fx': '외환',
    'usd': 'USD',
    'eur': 'EUR',
    'jpy': 'JPY',
    'krw': 'KRW',
    'cny': 'CNY',
    'gross': '총',
    'net': '순',
    'unit': '단위',
    'selling': '판매',
    'buying': '구매',
    'cogs': '매출원가',
    'inventory': '재고',
    'production': '생산',
    'final': '최종'
}


def format_variable_label(name: str) -> str:
    """변수명을 의미 있는 한글 라벨로 변환"""
    lower_name = name.lower()
    
    # 정확히 일치하는 매핑이 있으면 사용
    if lower_name in VARIABLE_LABEL_MAP:
        return VARIABLE_LABEL_MAP[lower_name]
    
    # 부분 매칭 시도
    for key, label in VARIABLE_LABEL_MAP.items():
        if key in lower_name:
            return label
    
    # 언더스코어로 분리된 이름 처리
    if '_' in name:
        parts = name.split('_')
        
        # 통화 코드 확인
        currency_pattern = ['usd', 'eur', 'jpy', 'cny', 'krw']
        currencies = [p.upper() for p in parts if p.lower() in currency_pattern]
        
        if len(currencies) >= 2:
            return f"{currencies[0]}/{currencies[1]} 환율"
        elif len(currencies) == 1:
            return f"{currencies[0]} 환율"
        
        # 마지막 2-3개 부분을 변환
        relevant_parts = parts[-3:] if len(parts) > 3 else parts
        translated = []
        
        for part in relevant_parts:
            lower_part = part.lower()
            if lower_part in KEYWORD_TRANSLATIONS:
                translated.append(KEYWORD_TRANSLATIONS[lower_part])
            elif lower_part not in currency_pattern:
                translated.append(part)
        
        return ' '.join(translated) if translated else name
    
    return name


@dataclass
class ValidationResult:
    """검증 결과"""
    edge_id: str
    r_squared: float
    train_r2: float
    test_r2: float
    rmse: float
    mape: float
    is_valid: bool
    is_overfit: bool
    notes: List[str]


@dataclass
class CausalDiscoveryResult:
    """인과관계 발견 결과"""
    edges: List[CausalEdge]
    summary: Dict[str, Any]
    validation: Optional[Dict[str, Any]] = None


class CausalDiscoveryAPI:
    """
    Causal Discovery 및 Validation API
    """
    
    def __init__(self):
        self.significance_level = settings.significance_level
        self.min_correlation = settings.min_correlation
        self.test_ratio = settings.test_ratio
        
    async def discover_causality(self,
                                  data: pd.DataFrame,
                                  methods: List[str] = ['correlation', 'granger'],
                                  max_lag: int = 2) -> CausalDiscoveryResult:
        """
        데이터에서 인과관계 발견
        
        Args:
            data: 분석할 데이터프레임
            methods: 사용할 방법 ['correlation', 'granger', 'partial']
            max_lag: Granger Causality 최대 시차
        """
        all_edges = []
        
        # 수치형 컬럼만 선택
        numeric_cols = data.select_dtypes(include=[np.number]).columns.tolist()
        numeric_data = data[numeric_cols]
        
        if len(numeric_data) < 10:
            return CausalDiscoveryResult(
                edges=[],
                summary={'error': '데이터가 충분하지 않습니다 (최소 10행 필요)'}
            )
        
        # 1. 상관관계 분석
        if 'correlation' in methods:
            corr_edges = self._discover_correlations(numeric_data)
            all_edges.extend(corr_edges)
        
        # 2. Granger Causality
        if 'granger' in methods:
            granger_edges = self._discover_granger(numeric_data, max_lag)
            all_edges.extend(granger_edges)
        
        # 3. Partial Correlation
        if 'partial' in methods:
            partial_edges = self._discover_partial(numeric_data)
            all_edges.extend(partial_edges)
        
        # 중복 제거 및 통합
        consolidated = self._consolidate_edges(all_edges)
        
        # 4. 끊어진 클러스터 연결 (브릿지 엣지 추가)
        connected = self._connect_clusters(consolidated, numeric_data, min_bridge_corr=0.2)
        
        # 요약 생성
        summary = self._generate_summary(connected)
        
        return CausalDiscoveryResult(
            edges=connected,
            summary=summary
        )
    
    def _discover_correlations(self, data: pd.DataFrame) -> List[CausalEdge]:
        """상관관계 기반 발견"""
        edges = []
        columns = data.columns.tolist()
        
        for i, col1 in enumerate(columns):
            for col2 in columns[i+1:]:
                try:
                    corr, p_value = stats.pearsonr(data[col1].dropna(), data[col2].dropna())
                    
                    if abs(corr) >= self.min_correlation and p_value < self.significance_level:
                        direction = 'positive' if corr > 0 else 'negative'
                        edges.append(CausalEdge(
                            source=col1,
                            target=col2,
                            strength=abs(corr),
                            direction=direction,
                            method='correlation',
                            p_value=p_value
                        ))
                except Exception:
                    continue
                    
        return edges
    
    def _discover_granger(self, data: pd.DataFrame, max_lag: int) -> List[CausalEdge]:
        """Granger Causality 분석"""
        edges = []
        columns = data.columns.tolist()
        
        for cause in columns:
            for effect in columns:
                if cause == effect:
                    continue
                    
                try:
                    test_data = data[[effect, cause]].dropna()
                    if len(test_data) < max_lag + 10:
                        continue
                    
                    result = grangercausalitytests(test_data, maxlag=max_lag, verbose=False)
                    
                    min_p = 1.0
                    best_lag = 1
                    
                    for lag in range(1, max_lag + 1):
                        if lag in result:
                            p_value = result[lag][0]['ssr_ftest'][1]
                            if p_value < min_p:
                                min_p = p_value
                                best_lag = lag
                    
                    if min_p < self.significance_level:
                        corr = data[cause].corr(data[effect])
                        direction = 'positive' if corr > 0 else 'negative'
                        
                        f_stat = result[best_lag][0]['ssr_ftest'][0]
                        strength = min(1.0, f_stat / 20)
                        
                        edges.append(CausalEdge(
                            source=cause,
                            target=effect,
                            strength=strength,
                            direction=direction,
                            method='granger',
                            p_value=min_p,
                            lag=best_lag
                        ))
                        
                except Exception:
                    continue
                    
        return edges
    
    def _discover_partial(self, data: pd.DataFrame) -> List[CausalEdge]:
        """Partial Correlation 분석"""
        edges = []
        columns = data.columns.tolist()
        
        for i, col1 in enumerate(columns):
            for col2 in columns[i+1:]:
                try:
                    control_vars = [c for c in columns if c not in [col1, col2]]
                    partial_corr = self._partial_correlation(data, col1, col2, control_vars)
                    
                    if partial_corr is not None and abs(partial_corr) >= self.min_correlation:
                        direction = 'positive' if partial_corr > 0 else 'negative'
                        edges.append(CausalEdge(
                            source=col1,
                            target=col2,
                            strength=abs(partial_corr),
                            direction=direction,
                            method='partial',
                            p_value=0.05
                        ))
                except Exception:
                    continue
                    
        return edges
    
    def _partial_correlation(self, data: pd.DataFrame, 
                             var1: str, var2: str, 
                             control_vars: List[str]) -> Optional[float]:
        """부분 상관계수 계산"""
        if not control_vars:
            return data[var1].corr(data[var2])
            
        try:
            X = data[control_vars].values
            X = np.column_stack([np.ones(len(X)), X])
            
            y1 = data[var1].values
            y2 = data[var2].values
            
            coeffs1, _, _, _ = np.linalg.lstsq(X, y1, rcond=None)
            residuals1 = y1 - X @ coeffs1
            
            coeffs2, _, _, _ = np.linalg.lstsq(X, y2, rcond=None)
            residuals2 = y2 - X @ coeffs2
            
            partial = np.corrcoef(residuals1, residuals2)[0, 1]
            return partial if not np.isnan(partial) else None
            
        except Exception:
            return None
    
    def _consolidate_edges(self, edges: List[CausalEdge]) -> List[CausalEdge]:
        """엣지 통합 및 중복 제거"""
        edge_map: Dict[tuple, List[CausalEdge]] = {}
        
        for edge in edges:
            key = (edge.source, edge.target)
            if key not in edge_map:
                edge_map[key] = []
            edge_map[key].append(edge)
        
        consolidated = []
        for (source, target), edge_list in edge_map.items():
            methods = set(e.method for e in edge_list)
            
            if 'granger' in methods:
                best = next(e for e in edge_list if e.method == 'granger')
            elif 'partial' in methods:
                best = next(e for e in edge_list if e.method == 'partial')
            else:
                best = edge_list[0]
            
            # 여러 방법에서 발견되면 신뢰도 증가
            boost = 1.0 + (len(methods) - 1) * 0.2
            
            consolidated.append(CausalEdge(
                source=source,
                target=target,
                strength=min(1.0, best.strength * boost),
                direction=best.direction,
                method='+'.join(sorted(methods)),
                p_value=best.p_value,
                lag=best.lag
            ))
        
        consolidated.sort(key=lambda e: e.strength, reverse=True)
        return consolidated
    
    def _find_connected_components(self, edges: List[CausalEdge]) -> List[set]:
        """연결된 컴포넌트 찾기 (Union-Find)"""
        if not edges:
            return []
            
        # 모든 노드 수집
        nodes = set()
        for edge in edges:
            nodes.add(edge.source)
            nodes.add(edge.target)
        
        # 부모 딕셔너리
        parent = {node: node for node in nodes}
        
        def find(x):
            if parent[x] != x:
                parent[x] = find(parent[x])
            return parent[x]
        
        def union(x, y):
            px, py = find(x), find(y)
            if px != py:
                parent[px] = py
        
        # 연결
        for edge in edges:
            union(edge.source, edge.target)
        
        # 컴포넌트 그룹화
        components = {}
        for node in nodes:
            root = find(node)
            if root not in components:
                components[root] = set()
            components[root].add(node)
        
        return list(components.values())
    
    def _connect_clusters(self, 
                          edges: List[CausalEdge], 
                          data: pd.DataFrame,
                          min_bridge_corr: float = 0.2) -> List[CausalEdge]:
        """
        끊어진 클러스터들을 연결하는 브릿지 엣지 추가
        
        약한 상관관계라도 클러스터 간 연결이 필요하면 추가
        """
        components = self._find_connected_components(edges)
        
        if len(components) <= 1:
            return edges  # 이미 연결됨
        
        # 클러스터 간 최적 연결점 찾기
        bridge_edges = []
        processed_pairs = set()
        
        for i, comp1 in enumerate(components):
            for j, comp2 in enumerate(components[i+1:], i+1):
                pair_key = (min(i, j), max(i, j))
                if pair_key in processed_pairs:
                    continue
                processed_pairs.add(pair_key)
                
                best_corr = 0
                best_pair = None
                
                for node1 in comp1:
                    for node2 in comp2:
                        if node1 not in data.columns or node2 not in data.columns:
                            continue
                        try:
                            corr = abs(data[node1].corr(data[node2]))
                            if corr > best_corr:
                                best_corr = corr
                                best_pair = (node1, node2)
                        except:
                            continue
                
                # 약한 상관관계라도 클러스터 연결을 위해 추가
                if best_pair and best_corr >= min_bridge_corr:
                    node1, node2 = best_pair
                    actual_corr = data[node1].corr(data[node2])
                    direction = 'positive' if actual_corr > 0 else 'negative'
                    
                    bridge_edges.append(CausalEdge(
                        source=node1,
                        target=node2,
                        strength=abs(actual_corr),
                        direction=direction,
                        method='bridge',
                        p_value=0.1,  # 약한 연결임을 표시
                        lag=0
                    ))
        
        return edges + bridge_edges
    
    def _generate_summary(self, edges: List[CausalEdge]) -> Dict[str, Any]:
        """결과 요약 생성"""
        if not edges:
            return {'total_edges': 0}
        
        influence_count = {}
        influenced_count = {}
        
        for edge in edges:
            influence_count[edge.source] = influence_count.get(edge.source, 0) + 1
            influenced_count[edge.target] = influenced_count.get(edge.target, 0) + 1
        
        root_causes = sorted(influence_count.items(), key=lambda x: x[1], reverse=True)[:5]
        final_effects = sorted(influenced_count.items(), key=lambda x: x[1], reverse=True)[:5]
        
        # 연결 컴포넌트 분석
        components = self._find_connected_components(edges)
        
        return {
            'total_edges': len(edges),
            'strong_edges': sum(1 for e in edges if e.strength > 0.5),
            'positive_count': sum(1 for e in edges if e.direction == 'positive'),
            'negative_count': sum(1 for e in edges if e.direction == 'negative'),
            'root_causes': root_causes,
            'final_effects': final_effects,
            'connected_components': len(components),
            'is_fully_connected': len(components) == 1
        }
    
    async def validate_edges(self,
                              data: pd.DataFrame,
                              edges: List[CausalEdge]) -> Dict[str, Any]:
        """
        발견된 엣지 검증
        
        Train/Test 분할하여 과적합 검사
        """
        n = len(data)
        split_idx = int(n * (1 - self.test_ratio))
        
        train_data = data.iloc[:split_idx]
        test_data = data.iloc[split_idx:]
        
        results = []
        
        for edge in edges:
            if edge.source not in data.columns or edge.target not in data.columns:
                continue
            
            # 회귀 분석
            try:
                X_train = train_data[edge.source].values
                y_train = train_data[edge.target].values
                
                slope, intercept, r_value, p_value, std_err = stats.linregress(X_train, y_train)
                train_r2 = r_value ** 2
                
                # 테스트 데이터로 평가
                X_test = test_data[edge.source].values
                y_test = test_data[edge.target].values
                y_pred = slope * X_test + intercept
                
                ss_res = np.sum((y_test - y_pred) ** 2)
                ss_tot = np.sum((y_test - np.mean(y_test)) ** 2)
                test_r2 = 1 - ss_res / ss_tot if ss_tot > 0 else 0
                
                # 전체 R²
                X_all = data[edge.source].values
                y_all = data[edge.target].values
                y_all_pred = slope * X_all + intercept
                
                rmse = np.sqrt(np.mean((y_all - y_all_pred) ** 2))
                mape = np.mean(np.abs((y_all - y_all_pred) / np.where(y_all != 0, y_all, 1))) * 100
                
                # 과적합 판정
                is_overfit = (train_r2 - test_r2) > 0.15
                is_valid = train_r2 > 0.1 and not is_overfit
                
                notes = []
                if is_overfit:
                    notes.append("과적합 의심")
                if train_r2 > 0.7 and test_r2 > 0.5:
                    notes.append("양호")
                
                # 엣지에 회귀 정보 추가
                edge.formula = f"{edge.target} = {slope:.4f} * {edge.source} + {intercept:.4f}"
                edge.r_squared = train_r2
                
                results.append(ValidationResult(
                    edge_id=f"{edge.source}_to_{edge.target}",
                    r_squared=float(train_r2),
                    train_r2=float(train_r2),
                    test_r2=float(test_r2),
                    rmse=float(rmse),
                    mape=float(mape),
                    is_valid=is_valid,
                    is_overfit=is_overfit,
                    notes=notes
                ))
                
            except Exception as e:
                continue
        
        # 요약 통계
        valid_count = sum(1 for r in results if r.is_valid)
        overfit_count = sum(1 for r in results if r.is_overfit)
        mean_r2 = np.mean([r.r_squared for r in results]) if results else 0
        
        return {
            'total_validated': len(results),
            'valid_count': valid_count,
            'overfit_count': overfit_count,
            'mean_r_squared': float(mean_r2),
            'results': [asdict(r) for r in results]
        }
    
    async def estimate_influence_functions(self,
                                            data: pd.DataFrame,
                                            edges: List[CausalEdge]) -> List[Dict]:
        """각 엣지의 영향 함수 추정"""
        functions = []
        
        for edge in edges:
            if edge.source not in data.columns or edge.target not in data.columns:
                continue
            
            try:
                X = data[edge.source].values
                y = data[edge.target].values
                
                slope, intercept, r_value, p_value, std_err = stats.linregress(X, y)
                
                functions.append({
                    'source': edge.source,
                    'target': edge.target,
                    'formula': f"{edge.target} = {slope:.4f} * {edge.source} + {intercept:.4f}",
                    'slope': float(slope),
                    'intercept': float(intercept),
                    'r_squared': float(r_value ** 2),
                    'p_value': float(p_value)
                })
                
            except Exception:
                continue
        
        return functions


# 싱글톤 인스턴스
causal_api = CausalDiscoveryAPI()
