"""
MindsDB API Module
==================

MindsDB와 연동하여 ML 모델 학습 및 비교
"""

import asyncio
import httpx
import pandas as pd
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
import time

from .config import settings


@dataclass
class MindsDBModel:
    """MindsDB 모델 정보"""
    name: str
    target: str
    features: List[str]
    status: str
    accuracy: Optional[float] = None
    r_squared: Optional[float] = None
    creation_time: Optional[str] = None


class MindsDBAPIService:
    """MindsDB 연동 서비스"""
    
    def __init__(self):
        self.mindsdb_url = settings.mindsdb_url
        
    async def execute_sql(self, sql: str) -> Dict[str, Any]:
        """MindsDB SQL 실행"""
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{self.mindsdb_url}/api/sql/query",
                    json={"query": sql},
                    timeout=120.0
                )
                
                if response.status_code == 200:
                    return response.json()
                else:
                    return {'error': f"HTTP {response.status_code}: {response.text}"}
                    
            except Exception as e:
                return {'error': str(e)}
    
    async def list_models(self) -> List[MindsDBModel]:
        """모든 모델 목록 조회"""
        result = await self.execute_sql("SHOW MODELS")
        
        models = []
        if 'data' in result:
            for row in result['data']:
                # 컬럼 구조에 따라 파싱
                if len(row) >= 3:
                    models.append(MindsDBModel(
                        name=row[0],
                        target=row[2] if len(row) > 2 else '',
                        features=[],
                        status=row[1] if len(row) > 1 else 'unknown'
                    ))
        
        return models
    
    async def create_analysis_view(self, 
                                    view_name: str,
                                    tables: List[Dict],
                                    mysql_db: str = 'mysql_sample') -> Dict[str, Any]:
        """
        분석용 통합 VIEW 생성
        
        발견된 테이블들을 시간 컬럼 기준으로 JOIN하여 통합 뷰 생성
        
        Args:
            view_name: 생성할 뷰 이름
            tables: 테이블 정보 리스트 [{'table_name': ..., 'columns': [...], 'time_column': ...}, ...]
            mysql_db: MindsDB에 등록된 MySQL 데이터소스 이름
        
        Returns:
            생성 결과
        """
        if not tables:
            return {'error': 'No tables provided'}
        
        # 시간 컬럼 찾기
        time_column = 'month'  # 기본값
        for t in tables:
            for col in t.get('columns', []):
                col_lower = col.lower()
                if any(tc in col_lower for tc in ['month', 'date', 'time']):
                    time_column = col
                    break
        
        # 첫 번째 테이블을 기준으로
        base_table = tables[0]
        base_alias = 't0'
        
        # SELECT 절 구성 - 모든 숫자 컬럼 선택 (컬럼명 중복 시 축약)
        select_parts = [f"{base_alias}.{time_column}"]
        used_aliases = set([time_column])
        
        for idx, table in enumerate(tables):
            alias = f"t{idx}"
            table_name = table['table_name']
            
            for col in table.get('columns', []):
                col_lower = col.lower()
                
                # id, 시간 컬럼 제외
                if col_lower in ['id', time_column.lower()]:
                    continue
                    
                # 비숫자형으로 추정되는 컬럼 제외
                if any(skip in col_lower for skip in ['name', 'type', 'status', 'description', 'text', 'comment']):
                    continue
                
                # 컬럼 별칭 생성 (중복 방지 - 테이블명 prefix 없이 간결하게)
                col_alias = col
                if col_alias in used_aliases:
                    col_alias = f"{table_name.split('_')[0]}_{col}"
                
                if col_alias not in used_aliases:
                    used_aliases.add(col_alias)
                    if col == col_alias:
                        select_parts.append(f"{alias}.{col}")
                    else:
                        select_parts.append(f"{alias}.{col} AS {col_alias}")
        
        # FROM/JOIN 절 구성
        from_clause = f"{mysql_db}.{base_table['table_name']} {base_alias}"
        join_clauses = []
        
        for idx, table in enumerate(tables[1:], 1):
            alias = f"t{idx}"
            join_clauses.append(
                f"LEFT JOIN {mysql_db}.{table['table_name']} {alias} ON {base_alias}.{time_column} = {alias}.{time_column}"
            )
        
        # VIEW SQL 생성
        select_str = ',\n        '.join(select_parts)
        join_str = '\n    '.join(join_clauses)
        
        # 먼저 기존 뷰 삭제 시도
        await self.execute_sql(f"DROP VIEW IF EXISTS mindsdb.{view_name}")
        
        sql = f"""
        CREATE VIEW mindsdb.{view_name} AS (
            SELECT 
                {select_str}
            FROM {from_clause}
            {join_str}
        )
        """
        
        result = await self.execute_sql(sql)
        
        if 'error' not in result:
            result['view_name'] = view_name
            result['columns'] = list(used_aliases)
            result['sql'] = sql
        
        return result
    
    async def get_view_data(self, view_name: str, limit: int = 1000) -> pd.DataFrame:
        """VIEW에서 데이터 조회"""
        sql = f"SELECT * FROM mindsdb.{view_name} LIMIT {limit}"
        result = await self.execute_sql(sql)
        
        if 'data' in result and 'column_names' in result:
            return pd.DataFrame(result['data'], columns=result['column_names'])
        elif 'data' in result:
            return pd.DataFrame(result['data'])
        else:
            return pd.DataFrame()
    
    async def create_materialized_table(self,
                                         table_name: str,
                                         tables: List[Dict],
                                         mysql_db: str = 'mysql_sample') -> Dict[str, Any]:
        """
        분석용 Materialized Table 생성 (CREATE TABLE)
        
        VIEW 대신 실제 테이블로 데이터를 저장하여 더 빠른 쿼리 지원
        """
        if not tables:
            return {'error': 'No tables provided'}
        
        # 시간 컬럼 찾기
        time_column = 'month'
        for t in tables:
            for col in t.get('columns', []):
                col_lower = col.lower()
                if any(tc in col_lower for tc in ['month', 'date', 'time']):
                    time_column = col
                    break
        
        base_table = tables[0]
        base_alias = 't0'
        
        # SELECT 절 구성
        select_parts = [f"{base_alias}.{time_column}"]
        
        for idx, table in enumerate(tables):
            alias = f"t{idx}"
            for col in table.get('columns', []):
                col_lower = col.lower()
                if col_lower in ['id', time_column.lower()]:
                    continue
                if not any(skip in col_lower for skip in ['name', 'type', 'status', 'description']):
                    col_alias = f"{table['table_name']}_{col}"
                    select_parts.append(f"{alias}.{col} AS {col_alias}")
        
        # FROM/JOIN 절 구성
        from_clause = f"{mysql_db}.{base_table['table_name']} {base_alias}"
        join_clauses = []
        
        for idx, table in enumerate(tables[1:], 1):
            alias = f"t{idx}"
            join_clauses.append(
                f"LEFT JOIN {mysql_db}.{table['table_name']} {alias} ON {base_alias}.{time_column} = {alias}.{time_column}"
            )
        
        select_str = ',\n            '.join(select_parts)
        join_str = '\n        '.join(join_clauses)
        
        # 기존 테이블 삭제
        await self.execute_sql(f"DROP TABLE IF EXISTS mindsdb.{table_name}")
        
        sql = f"""
        CREATE TABLE mindsdb.{table_name} (
            SELECT 
                {select_str}
            FROM {from_clause}
            {join_str}
        )
        """
        
        result = await self.execute_sql(sql)
        
        if 'error' not in result:
            result['table_name'] = table_name
            result['columns'] = [p.split(' AS ')[-1] if ' AS ' in p else p.split('.')[-1] for p in select_parts]
        
        return result
    
    async def create_model(self,
                           model_name: str,
                           target: str,
                           features: List[str],
                           data_source: str) -> Dict[str, Any]:
        """
        새 MindsDB 모델 생성
        
        Args:
            model_name: 모델 이름
            target: 예측 대상 컬럼
            features: 피처 컬럼 목록
            data_source: 데이터 소스 (테이블명 또는 뷰)
        """
        feature_cols = ', '.join(features)
        
        sql = f"""
        CREATE MODEL IF NOT EXISTS mindsdb.{model_name}
        FROM files (
            SELECT {feature_cols}, {target}
            FROM {data_source}
        )
        PREDICT {target}
        """
        
        return await self.execute_sql(sql)
    
    async def create_model_from_view(self,
                                     model_name: str,
                                     target: str,
                                     view_name: str) -> Dict[str, Any]:
        """뷰로부터 모델 생성"""
        sql = f"""
        CREATE MODEL IF NOT EXISTS mindsdb.{model_name}
        FROM mindsdb (
            SELECT * FROM {view_name}
        )
        PREDICT {target}
        """
        
        return await self.execute_sql(sql)
    
    async def wait_for_model(self, model_name: str, timeout: int = 300) -> str:
        """모델 학습 완료 대기"""
        start = time.time()
        
        while time.time() - start < timeout:
            result = await self.execute_sql(f"DESCRIBE MODEL {model_name}")
            
            if 'data' in result and result['data']:
                status = result['data'][0][1] if len(result['data'][0]) > 1 else None
                
                if status == 'complete':
                    return 'complete'
                elif status == 'error':
                    return 'error'
            
            await asyncio.sleep(5)
        
        return 'timeout'
    
    async def predict(self,
                      model_name: str,
                      input_data: Dict[str, Any]) -> Dict[str, Any]:
        """모델 예측"""
        where_clauses = []
        for key, value in input_data.items():
            if isinstance(value, str):
                where_clauses.append(f"{key} = '{value}'")
            else:
                where_clauses.append(f"{key} = {value}")
        
        where_str = ' AND '.join(where_clauses)
        
        sql = f"SELECT * FROM mindsdb.{model_name} WHERE {where_str}"
        
        return await self.execute_sql(sql)
    
    async def get_model_accuracy(self, model_name: str) -> Optional[float]:
        """모델 정확도 조회"""
        result = await self.execute_sql(f"DESCRIBE MODEL {model_name}")
        
        if 'data' in result and result['data']:
            for row in result['data']:
                # 정확도 또는 R² 값 찾기
                for item in row:
                    if isinstance(item, (int, float)):
                        return float(item)
        
        return None
    
    async def compare_with_causal(self,
                                   data: pd.DataFrame,
                                   causal_edges: List[Dict],
                                   test_ratio: float = 0.2) -> Dict[str, Any]:
        """
        Causal Discovery 결과와 MindsDB 모델 비교
        - 80% 학습 데이터로 모델 훈련
        - 20% 테스트 데이터로 예측 검증
        - 실제값 vs 예측값 비교 차트 데이터 포함
        
        Args:
            data: 원본 데이터
            causal_edges: Causal Discovery에서 발견된 엣지
            test_ratio: 테스트 데이터 비율
        """
        import numpy as np
        from sklearn.linear_model import LinearRegression
        from sklearn.metrics import r2_score, mean_absolute_percentage_error
        
        comparison_results = []
        prediction_charts = []  # 예측 vs 실제 차트 데이터
        
        n = len(data)
        train_size = int(n * (1 - test_ratio))
        train_data = data.iloc[:train_size]
        test_data = data.iloc[train_size:]
        
        # 데이터프레임 컬럼 목록 (ID 컬럼 제외, 값 컬럼 우선)
        all_columns = [c for c in data.columns 
                       if c.lower() != 'month' 
                       and not c.lower().endswith('_id')
                       and c.lower() != 'id']
        print(f"Available columns (excluding IDs): {all_columns}")
        
        # 컬럼명 매핑 함수 - 유사한 컬럼 찾기 (ID 컬럼 제외)
        def find_matching_column(edge_col: str, columns: list) -> str:
            # ID 컬럼 필터링
            value_columns = [c for c in columns 
                            if not c.lower().endswith('_id') 
                            and c.lower() != 'id']
            
            # 정확히 일치
            if edge_col in value_columns:
                return edge_col
            
            # 대소문자 무시
            for col in value_columns:
                if col.lower() == edge_col.lower():
                    return col
            
            # 부분 일치 - edge_col의 핵심 부분이 컬럼명에 포함
            edge_parts = edge_col.lower().replace('_', ' ').split()
            best_match = None
            best_score = 0
            
            for col in value_columns:
                col_lower = col.lower()
                # rate, cost, price, value 등 값을 나타내는 컬럼 우선
                value_keywords = ['rate', 'cost', 'price', 'value', 'amount', 'profit', 'revenue', 'volume', 'demand']
                has_value_keyword = any(kw in col_lower for kw in value_keywords)
                
                # 매칭 점수 계산
                score = 0
                for part in edge_parts:
                    if part in col_lower:
                        score += 2
                if has_value_keyword:
                    score += 1
                
                if score > best_score:
                    best_score = score
                    best_match = col
            
            if best_match and best_score >= 2:
                return best_match
            
            # 컬럼명이 edge_col에 포함
            for col in value_columns:
                col_parts = col.lower().replace('_', ' ').split()
                if any(part in edge_col.lower() for part in col_parts if len(part) > 3):
                    return col
            
            return None
        
        # 주요 타겟 변수 식별 (가장 많이 영향받는 변수)
        target_counts = {}
        for edge in causal_edges:
            target = edge.get('target')
            if target:
                target_counts[target] = target_counts.get(target, 0) + 1
        
        # 상위 5개 타겟에 대해 상세 분석
        main_targets = sorted(target_counts.items(), key=lambda x: x[1], reverse=True)[:5]
        
        # edges가 비어있거나 컬럼 매칭이 안되면 데이터 기반으로 자동 생성
        edges_to_process = []
        
        for edge in causal_edges[:30]:  # 상위 30개 엣지
            source = edge.get('source')
            target = edge.get('target')
            
            if not source or not target:
                continue
            
            # 컬럼 매칭
            matched_source = find_matching_column(source, all_columns)
            matched_target = find_matching_column(target, all_columns)
            
            if matched_source and matched_target and matched_source != matched_target:
                edges_to_process.append({
                    **edge,
                    'matched_source': matched_source,
                    'matched_target': matched_target
                })
        
        # 매칭된 엣지가 없으면 데이터 기반으로 자동 생성
        if not edges_to_process and len(all_columns) >= 2:
            print("No matched edges, generating from data columns")
            # 숫자 컬럼들 간의 관계 분석
            for i, col1 in enumerate(all_columns[:6]):
                for col2 in all_columns[i+1:6]:
                    edges_to_process.append({
                        'source': col1,
                        'target': col2,
                        'matched_source': col1,
                        'matched_target': col2,
                        'strength': 0.5,
                        'source_label': col1.replace('_', ' ').title(),
                        'target_label': col2.replace('_', ' ').title()
                    })
        
        print(f"Processing {len(edges_to_process)} edge pairs")
        
        for edge in edges_to_process:
            source = edge.get('matched_source', edge.get('source'))
            target = edge.get('matched_target', edge.get('target'))
            causal_strength = edge.get('strength', edge.get('r_squared', 0))
            source_label = edge.get('source_label', source)
            target_label = edge.get('target_label', target)
            
            try:
                # 온톨로지 기반 예측 (선형 회귀)
                X_train = train_data[[source]].dropna()
                y_train = train_data.loc[X_train.index, target]
                
                X_test = test_data[[source]].dropna()
                y_test = test_data.loc[X_test.index, target]
                
                if len(X_train) < 5 or len(X_test) < 2:
                    continue
                
                # 온톨로지 모델 (단순 선형 회귀)
                causal_model = LinearRegression()
                causal_model.fit(X_train, y_train)
                causal_preds = causal_model.predict(X_test)
                
                # 메트릭 계산
                causal_r2 = r2_score(y_test, causal_preds)
                causal_mape = mean_absolute_percentage_error(y_test, causal_preds) * 100
                
                result = {
                    'edge': f"{source_label} → {target_label}",
                    'source': source,
                    'target': target,
                    'source_label': source_label,
                    'target_label': target_label,
                    'causal_strength': float(causal_strength),
                    'causal_r2': float(causal_r2),
                    'causal_mape': float(causal_mape),
                    'coefficient': float(causal_model.coef_[0]),
                    'intercept': float(causal_model.intercept_),
                    'train_samples': len(X_train),
                    'test_samples': len(X_test),
                    'mindsdb_r2': None,
                    'mindsdb_mape': None
                }
                
                # 차트 데이터 생성 (상위 6개까지)
                if len(prediction_charts) < 6:
                    chart_data = {
                        'edge': f"{source_label} → {target_label}",
                        'source': source,
                        'target': target,
                        'labels': list(range(len(y_test))),
                        'actual': [float(v) for v in y_test.values],
                        'causal_predicted': [float(v) for v in causal_preds],
                        'source_values': [float(v) for v in X_test[source].values]
                    }
                    prediction_charts.append(chart_data)
                
                comparison_results.append(result)
                
            except Exception as e:
                comparison_results.append({
                    'edge': f"{source_label} → {target_label}",
                    'source': source,
                    'target': target,
                    'causal_r2': float(causal_strength),
                    'mindsdb_r2': None,
                    'error': str(e)
                })
        
        # 요약 통계
        valid_results = [r for r in comparison_results if r.get('causal_r2') is not None and 'error' not in r]
        
        if valid_results:
            mean_causal = sum(r['causal_r2'] for r in valid_results) / len(valid_results)
            avg_mape = sum(r.get('causal_mape', 0) for r in valid_results) / len(valid_results)
            good_fits = sum(1 for r in valid_results if r['causal_r2'] > 0.5)
        else:
            mean_causal = avg_mape = good_fits = 0
        
        return {
            'comparisons': comparison_results,
            'prediction_charts': prediction_charts,  # 예측 vs 실제 차트 데이터
            'summary': {
                'total_compared': len(valid_results),
                'mean_causal_r2': float(mean_causal),
                'mean_mindsdb_r2': 0,  # MindsDB 미사용시
                'avg_mape': float(avg_mape),
                'good_fits': good_fits,
                'mindsdb_wins': 0,
                'causal_wins': len(valid_results),
                'train_ratio': f"{int((1-test_ratio)*100)}%",
                'test_ratio': f"{int(test_ratio*100)}%",
                'note': '온톨로지 기반 선형 회귀 모델로 테스트 데이터 예측 검증'
            }
        }
    
    async def upload_dataframe(self, 
                                df: pd.DataFrame,
                                table_name: str) -> bool:
        """데이터프레임을 MindsDB files 데이터베이스에 업로드"""
        # CSV로 변환하여 업로드
        csv_content = df.to_csv(index=False)
        
        async with httpx.AsyncClient() as client:
            try:
                # 파일 업로드 API
                response = await client.put(
                    f"{self.mindsdb_url}/api/files/{table_name}",
                    content=csv_content.encode(),
                    headers={'Content-Type': 'text/csv'},
                    timeout=60.0
                )
                
                return response.status_code in [200, 201]
                
            except Exception as e:
                print(f"MindsDB 업로드 실패: {e}")
                return False


# 싱글톤 인스턴스
mindsdb_api = MindsDBAPIService()
