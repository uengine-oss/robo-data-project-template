"""
Data Discovery Module
=====================

Text2SQL 서비스와 연동하여 관련 데이터를 발견하고 수집합니다.
"""

import asyncio
import httpx
import pandas as pd
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
import pymysql
from .config import settings


@dataclass
class DiscoveredTable:
    """발견된 테이블 정보"""
    table_name: str
    columns: List[str]
    row_count: int
    sample_data: List[Dict]
    relevance_score: float
    description: str


@dataclass
class DataDiscoveryResult:
    """데이터 발견 결과"""
    query: str
    tables: List[DiscoveredTable]
    suggested_sql: str
    combined_dataset: Optional[pd.DataFrame] = None


class DataDiscoveryService:
    """
    데이터 발견 서비스
    
    사용자의 자연어 질의를 분석하여 관련 테이블과 데이터를 찾습니다.
    """
    
    def __init__(self):
        self.text2sql_url = settings.text2sql_url
        self.mysql_config = {
            'host': settings.mysql_host,
            'port': settings.mysql_port,
            'database': settings.mysql_database,
            'user': settings.mysql_user,
            'password': settings.mysql_password
        }
        
    async def discover_from_query(self, 
                                   natural_query: str,
                                   max_tables: int = 10) -> DataDiscoveryResult:
        """
        자연어 쿼리로 관련 데이터 발견
        
        Args:
            natural_query: 예측하고자 하는 내용에 대한 자연어 서술
            max_tables: 최대 반환 테이블 수
        """
        # 1. Text2SQL 서비스에 쿼리 전송하여 관련 테이블 탐색
        related_tables = []
        try:
            related_tables = await self._search_related_tables(natural_query)
        except Exception as e:
            print(f"Text2SQL 연동 실패: {e}")
        
        # Text2SQL 결과가 없으면 직접 MySQL 테이블 검색
        if not related_tables:
            print(f"Text2SQL 결과 없음, 직접 테이블 검색 시도...")
            related_tables = await self._direct_table_search(natural_query)
        
        # 2. 각 테이블의 상세 정보 조회
        discovered_tables = []
        for table_info in related_tables[:max_tables]:
            table = await self._get_table_details(table_info)
            if table:
                discovered_tables.append(table)
        
        # 3. 관련 SQL 생성
        suggested_sql = self._generate_combined_sql(discovered_tables)
        
        return DataDiscoveryResult(
            query=natural_query,
            tables=discovered_tables,
            suggested_sql=suggested_sql
        )
    
    async def _search_related_tables(self, query: str) -> List[Dict]:
        """Text2SQL 서비스를 통해 관련 테이블 검색"""
        async with httpx.AsyncClient() as client:
            try:
                # Neo4j text2sql의 메타 검색 API 호출
                response = await client.post(
                    f"{self.text2sql_url}/api/ask",
                    json={
                        "question": f"다음 분석에 필요한 테이블을 찾아주세요: {query}",
                        "mode": "schema_only"
                    },
                    timeout=30.0
                )
                
                if response.status_code == 200:
                    result = response.json()
                    # 응답에서 테이블 정보 추출
                    return self._extract_tables_from_response(result)
                    
            except Exception as e:
                print(f"Text2SQL API 호출 실패: {e}")
                
        return []
    
    async def _direct_table_search(self, query: str) -> List[Dict]:
        """MySQL에서 직접 테이블 검색"""
        tables = []
        
        try:
            conn = pymysql.connect(**self.mysql_config)
            cursor = conn.cursor()
            
            # 모든 테이블 목록 조회
            cursor.execute("""
                SELECT TABLE_NAME, TABLE_COMMENT 
                FROM INFORMATION_SCHEMA.TABLES 
                WHERE TABLE_SCHEMA = %s
            """, (settings.mysql_database,))
            
            for table_name, comment in cursor.fetchall():
                # 쿼리 키워드와 테이블명 매칭
                relevance = self._calculate_relevance(query, table_name, comment or "")
                if relevance > 0.1:
                    tables.append({
                        'name': table_name,
                        'comment': comment,
                        'relevance': relevance
                    })
            
            # 관련도 순으로 정렬
            tables.sort(key=lambda x: x['relevance'], reverse=True)
            
            cursor.close()
            conn.close()
            
        except Exception as e:
            print(f"MySQL 직접 검색 실패: {e}")
            
        return tables
    
    def _calculate_relevance(self, query: str, table_name: str, comment: str) -> float:
        """쿼리와 테이블의 관련도 계산"""
        query_lower = query.lower()
        table_lower = table_name.lower()
        comment_lower = comment.lower()
        
        score = 0.0
        
        # 한글-영어 키워드 매핑
        keyword_mapping = {
            '환율': ['fx', 'rate', 'exchange', 'currency'],
            '수익': ['profit', 'revenue', 'income', 'earning'],
            '비용': ['cost', 'expense', 'cogs'],
            '가격': ['price', 'pricing'],
            '수요': ['demand', 'sales', 'order'],
            '마케팅': ['marketing', 'mkt', 'ad'],
            '브랜드': ['brand', 'equity'],
            '월별': ['monthly', 'month'],
            '고객': ['customer', 'client'],
            '제품': ['product', 'item'],
            '원가': ['cogs', 'cost'],
            'kpi': ['kpi', 'metric', 'indicator'],
            '분석': ['analysis', 'kpi', 'monthly']
        }
        
        # 쿼리에서 한글 키워드 검색 후 영어 매핑
        for kr_keyword, en_keywords in keyword_mapping.items():
            if kr_keyword in query_lower or kr_keyword in query:
                for en_kw in en_keywords:
                    if en_kw in table_lower or en_kw in comment_lower:
                        score += 0.4
        
        # 영문 키워드 직접 매칭
        keywords = query_lower.split()
        for keyword in keywords:
            if len(keyword) > 2:
                if keyword in table_lower:
                    score += 0.3
                if keyword in comment_lower:
                    score += 0.2
        
        # 일반적인 분석 관련 키워드 (테이블에 포함되어 있으면 가산점)
        analysis_keywords = ['sales', 'profit', 'revenue', 'cost', 'price', 'demand', 
                           'customer', 'order', 'product', 'inventory', 'monthly', 'daily',
                           'kpi', 'fx', 'brand', 'marketing']
        for ak in analysis_keywords:
            if ak in table_lower or ak in comment_lower:
                score += 0.15
                
        return min(1.0, score)
    
    def _extract_tables_from_response(self, response: Dict) -> List[Dict]:
        """Text2SQL 응답에서 테이블 정보 추출"""
        tables = []
        
        # 응답 구조에 따라 파싱
        if 'tables' in response:
            for t in response['tables']:
                tables.append({
                    'name': t.get('name', ''),
                    'comment': t.get('description', ''),
                    'relevance': t.get('score', 0.5)
                })
        elif 'sql' in response:
            # SQL에서 테이블명 추출
            sql = response['sql'].upper()
            # 간단한 FROM 절 파싱
            if 'FROM' in sql:
                parts = sql.split('FROM')[1].split()
                if parts:
                    tables.append({
                        'name': parts[0].strip(',').lower(),
                        'comment': '',
                        'relevance': 0.8
                    })
                    
        return tables
    
    async def _get_table_details(self, table_info: Dict) -> Optional[DiscoveredTable]:
        """테이블 상세 정보 조회"""
        table_name = table_info['name']
        
        try:
            conn = pymysql.connect(**self.mysql_config)
            cursor = conn.cursor()
            
            # 컬럼 정보 조회
            cursor.execute(f"DESCRIBE {table_name}")
            columns = [row[0] for row in cursor.fetchall()]
            
            # 행 수 조회
            cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
            row_count = cursor.fetchone()[0]
            
            # 샘플 데이터 조회 (최대 5행)
            cursor.execute(f"SELECT * FROM {table_name} LIMIT 5")
            sample_rows = cursor.fetchall()
            sample_data = [dict(zip(columns, row)) for row in sample_rows]
            
            cursor.close()
            conn.close()
            
            return DiscoveredTable(
                table_name=table_name,
                columns=columns,
                row_count=row_count,
                sample_data=sample_data,
                relevance_score=table_info.get('relevance', 0.5),
                description=table_info.get('comment', '')
            )
            
        except Exception as e:
            print(f"테이블 {table_name} 상세 조회 실패: {e}")
            return None
    
    def _generate_combined_sql(self, tables: List[DiscoveredTable]) -> str:
        """발견된 테이블들을 조합한 SQL 생성"""
        if not tables:
            return ""
            
        if len(tables) == 1:
            return f"SELECT * FROM {tables[0].table_name}"
        
        # 여러 테이블인 경우 UNION 또는 JOIN 제안
        table_names = [t.table_name for t in tables]
        
        # 간단한 SELECT 문 생성
        sql_parts = []
        for table in tables:
            cols = ", ".join(table.columns[:5])  # 상위 5개 컬럼만
            sql_parts.append(f"SELECT '{table.table_name}' as source, {cols} FROM {table.table_name}")
        
        return " UNION ALL ".join(sql_parts) + " LIMIT 1000"
    
    async def collect_data(self, 
                           sql: str,
                           use_mindsdb: bool = False) -> pd.DataFrame:
        """
        SQL을 실행하여 데이터 수집
        
        Args:
            sql: 실행할 SQL
            use_mindsdb: MindsDB를 통해 실행할지 여부
        """
        if use_mindsdb:
            return await self._collect_via_mindsdb(sql)
        else:
            return await self._collect_via_mysql(sql)
    
    async def _collect_via_mysql(self, sql: str) -> pd.DataFrame:
        """MySQL에서 직접 데이터 수집"""
        try:
            conn = pymysql.connect(**self.mysql_config)
            df = pd.read_sql(sql, conn)
            conn.close()
            return df
        except Exception as e:
            print(f"MySQL 데이터 수집 실패: {e}")
            return pd.DataFrame()
    
    async def _collect_via_mindsdb(self, sql: str) -> pd.DataFrame:
        """MindsDB를 통해 데이터 수집"""
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{settings.mindsdb_url}/api/sql/query",
                    json={"query": sql},
                    timeout=60.0
                )
                
                if response.status_code == 200:
                    result = response.json()
                    if result.get('data'):
                        columns = result.get('column_names', [])
                        return pd.DataFrame(result['data'], columns=columns)
                        
            except Exception as e:
                print(f"MindsDB 데이터 수집 실패: {e}")
                
        return pd.DataFrame()
    
    async def create_mindsdb_view(self, 
                                   view_name: str,
                                   sql: str) -> bool:
        """MindsDB에 뷰 생성"""
        create_sql = f"CREATE OR REPLACE VIEW {view_name} AS ({sql})"
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{settings.mindsdb_url}/api/sql/query",
                    json={"query": create_sql},
                    timeout=30.0
                )
                return response.status_code == 200
                
            except Exception as e:
                print(f"MindsDB 뷰 생성 실패: {e}")
                return False


# 싱글톤 인스턴스
data_discovery_service = DataDiscoveryService()
