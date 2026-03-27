"""
What-If Simulation Agent
========================

시나리오 기반 데이터 소스 발견 및 인과관계 추론 에이전트

주요 기능:
1. 시나리오 분석 → 필요한 변수들 추론
2. Text2SQL 에이전트 호출 → 관련 데이터 소스 발견  
3. 시계열 데이터 검증 → 분석 적합성 확인
4. 후보 데이터셋 구성 → Causal Discovery 준비
"""

import asyncio
import httpx
import json
import re
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
import pandas as pd
import numpy as np
from openai import AsyncOpenAI

from .config import settings


@dataclass
class CausalVariable:
    """인과관계 변수"""
    name: str
    description: str
    variable_type: str  # 'driver', 'state', 'kpi'
    data_type: str  # 'numeric', 'categorical', 'temporal'
    potential_columns: List[str] = field(default_factory=list)
    

@dataclass
class DataSourceCandidate:
    """후보 데이터 소스"""
    table_name: str
    columns: List[str]
    row_count: int
    has_time_column: bool
    time_column: Optional[str]
    numeric_columns: List[str]
    relevance_score: float
    sample_data: List[Dict]
    validation_notes: List[str] = field(default_factory=list)


@dataclass
class ScenarioAnalysisResult:
    """시나리오 분석 결과"""
    original_scenario: str
    extracted_variables: List[CausalVariable]
    hypothesized_relationships: List[Dict]
    generated_queries: List[str]
    data_sources: List[DataSourceCandidate]
    validation_summary: Dict
    is_ready_for_causal: bool
    recommendations: List[str]


class WhatIfAgent:
    """
    What-If 시뮬레이션 메인 에이전트
    
    Text2SQL 에이전트를 서브 에이전트로 활용하여
    시나리오에 맞는 데이터 소스를 자동으로 발견하고 검증합니다.
    """
    
    def __init__(self):
        self.text2sql_url = settings.text2sql_url
        self.openai_client = AsyncOpenAI(api_key=settings.openai_api_key)
        self.model = settings.openai_model
        
    async def analyze_scenario(self, scenario: str) -> ScenarioAnalysisResult:
        """
        시나리오 분석 메인 워크플로우
        
        1. 시나리오에서 변수 추출
        2. 인과관계 가설 생성
        3. 데이터 탐색 쿼리 생성
        4. Text2SQL 에이전트로 데이터 소스 발견
        5. 시계열 데이터 검증
        6. 후보 데이터셋 평가
        """
        print(f"\n{'='*60}")
        print(f"🎯 What-If Agent: 시나리오 분석 시작")
        print(f"{'='*60}")
        print(f"시나리오: {scenario[:100]}...")
        
        # Step 1: 시나리오에서 변수 추출
        print(f"\n📊 Step 1: 변수 추출 중...")
        variables = await self._extract_variables(scenario)
        print(f"   발견된 변수: {[v.name for v in variables]}")
        
        # Step 2: 인과관계 가설 생성
        print(f"\n🔗 Step 2: 인과관계 가설 생성 중...")
        relationships = await self._hypothesize_relationships(scenario, variables)
        print(f"   생성된 관계: {len(relationships)}개")
        
        # Step 3: 데이터 탐색 쿼리 생성
        print(f"\n🔍 Step 3: 데이터 탐색 쿼리 생성 중...")
        queries = await self._generate_exploration_queries(scenario, variables)
        print(f"   생성된 쿼리: {len(queries)}개")
        
        # Step 4: Text2SQL 에이전트로 데이터 소스 발견
        print(f"\n🤖 Step 4: Text2SQL 에이전트 호출 중...")
        data_sources = await self._discover_data_sources(queries)
        print(f"   발견된 데이터 소스: {len(data_sources)}개")
        
        # Step 5: 시계열 데이터 검증
        print(f"\n⏱️ Step 5: 시계열 데이터 검증 중...")
        validated_sources = await self._validate_timeseries(data_sources)
        print(f"   검증 통과: {len([s for s in validated_sources if s.has_time_column])}개")
        
        # Step 6: 결과 평가 및 권장사항
        print(f"\n📋 Step 6: 결과 평가 중...")
        validation_summary, is_ready, recommendations = self._evaluate_results(
            variables, validated_sources
        )
        
        result = ScenarioAnalysisResult(
            original_scenario=scenario,
            extracted_variables=variables,
            hypothesized_relationships=relationships,
            generated_queries=queries,
            data_sources=validated_sources,
            validation_summary=validation_summary,
            is_ready_for_causal=is_ready,
            recommendations=recommendations
        )
        
        print(f"\n{'='*60}")
        print(f"✅ 분석 완료! Causal Discovery 준비: {'⭕ 가능' if is_ready else '❌ 추가 데이터 필요'}")
        print(f"{'='*60}\n")
        
        return result
    
    async def _extract_variables(self, scenario: str) -> List[CausalVariable]:
        """시나리오에서 인과관계 변수 추출"""
        
        prompt = f"""다음 시나리오를 분석하여 인과관계 분석에 필요한 변수들을 추출해주세요.

시나리오: {scenario}

각 변수에 대해 다음 정보를 JSON 형식으로 반환해주세요:
- name: 변수명 (영문, snake_case)
- description: 변수 설명 (한글)
- variable_type: 변수 유형 (driver: 외생/정책 변수, state: 상태 변수, kpi: 최종 성과 지표)
- data_type: 데이터 타입 (numeric, categorical, temporal)
- potential_columns: 데이터베이스에서 찾을 수 있는 잠재적 컬럼명 목록

응답은 반드시 JSON 배열 형식으로만 반환해주세요.
예시:
[
  {{"name": "exchange_rate", "description": "환율", "variable_type": "driver", "data_type": "numeric", "potential_columns": ["fx_rate", "exchange_rate", "usd_krw"]}},
  {{"name": "profit", "description": "이익", "variable_type": "kpi", "data_type": "numeric", "potential_columns": ["profit", "net_income", "earnings"]}}
]
"""
        
        try:
            response = await self.openai_client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3
            )
            
            content = response.choices[0].message.content.strip()
            # JSON 추출
            json_match = re.search(r'\[[\s\S]*\]', content)
            if json_match:
                variables_data = json.loads(json_match.group())
                return [CausalVariable(**v) for v in variables_data]
                
        except Exception as e:
            print(f"   ⚠️ 변수 추출 오류: {e}")
        
        # 기본 변수 반환
        return [
            CausalVariable("target", "목표 변수", "kpi", "numeric", ["value", "amount"]),
            CausalVariable("feature", "입력 변수", "driver", "numeric", ["input", "factor"])
        ]
    
    async def _hypothesize_relationships(self, 
                                          scenario: str, 
                                          variables: List[CausalVariable]) -> List[Dict]:
        """인과관계 가설 생성"""
        
        var_names = [v.name for v in variables]
        
        prompt = f"""다음 시나리오와 변수들을 바탕으로 인과관계 가설을 생성해주세요.

시나리오: {scenario}
변수들: {var_names}

각 관계에 대해 다음 정보를 JSON 형식으로 반환해주세요:
- source: 원인 변수
- target: 결과 변수
- direction: 영향 방향 (positive: 같은 방향, negative: 반대 방향)
- strength: 예상 강도 (strong, moderate, weak)
- reasoning: 관계 설명

JSON 배열로만 응답해주세요.
"""
        
        try:
            response = await self.openai_client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3
            )
            
            content = response.choices[0].message.content.strip()
            json_match = re.search(r'\[[\s\S]*\]', content)
            if json_match:
                return json.loads(json_match.group())
                
        except Exception as e:
            print(f"   ⚠️ 관계 가설 생성 오류: {e}")
        
        return []
    
    async def _generate_exploration_queries(self, 
                                             scenario: str,
                                             variables: List[CausalVariable]) -> List[str]:
        """데이터 탐색을 위한 자연어 쿼리 생성"""
        
        queries = []
        
        # 기본 시나리오 쿼리
        queries.append(scenario)
        
        # 변수별 탐색 쿼리
        for var in variables:
            queries.append(f"{var.description} 관련 데이터를 찾아줘")
            
            # 잠재적 컬럼명으로 검색
            for col in var.potential_columns[:2]:
                queries.append(f"{col} 데이터가 포함된 테이블")
        
        # 시계열 관련 쿼리
        queries.append("월별 또는 일별 시계열 데이터")
        queries.append("시간에 따른 변화를 분석할 수 있는 데이터")
        
        # 인과관계 분석용 쿼리
        prompt = f"""다음 시나리오의 인과관계 분석을 위해 필요한 데이터를 찾는 자연어 쿼리 3개를 생성해주세요.

시나리오: {scenario}

쿼리는 데이터베이스에서 관련 테이블을 찾는 질문 형태여야 합니다.
각 쿼리를 한 줄에 하나씩만 반환해주세요.
"""
        
        try:
            response = await self.openai_client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.5
            )
            
            content = response.choices[0].message.content.strip()
            for line in content.split('\n'):
                line = line.strip()
                if line and not line.startswith('#') and len(line) > 10:
                    # 번호 제거
                    line = re.sub(r'^[\d]+[.)\-]\s*', '', line)
                    queries.append(line)
                    
        except Exception as e:
            print(f"   ⚠️ 쿼리 생성 오류: {e}")
        
        return list(set(queries))  # 중복 제거
    
    async def _discover_data_sources(self, queries: List[str]) -> List[DataSourceCandidate]:
        """Text2SQL 에이전트를 통해 데이터 소스 발견"""
        
        discovered = {}  # table_name -> DataSourceCandidate
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            for query in queries[:10]:  # 최대 10개 쿼리
                try:
                    # Text2SQL /ask API 호출
                    response = await client.post(
                        f"{self.text2sql_url}/ask",
                        json={
                            "question": query,
                            "limit": 100
                        }
                    )
                    
                    if response.status_code == 200:
                        result = response.json()
                        
                        # SQL에서 테이블명 추출
                        sql = result.get('sql', '')
                        tables = self._extract_tables_from_sql(sql)
                        
                        # 각 테이블 정보 수집
                        for table_name in tables:
                            if table_name not in discovered:
                                table_info = await self._get_table_info(table_name)
                                if table_info:
                                    discovered[table_name] = table_info
                                    
                except Exception as e:
                    print(f"   ⚠️ Text2SQL 호출 실패 ({query[:30]}...): {e}")
        
        # 직접 MySQL 검색 (폴백)
        if not discovered:
            print(f"   📌 Text2SQL 결과 없음, 직접 검색 시도...")
            discovered = await self._direct_search_tables(queries)
        
        return list(discovered.values())
    
    def _extract_tables_from_sql(self, sql: str) -> List[str]:
        """SQL에서 테이블명 추출"""
        tables = []
        sql_upper = sql.upper()
        
        # FROM 절에서 추출
        from_pattern = r'FROM\s+[`"]?(\w+)[`"]?'
        matches = re.findall(from_pattern, sql_upper)
        tables.extend([m.lower() for m in matches])
        
        # JOIN 절에서 추출
        join_pattern = r'JOIN\s+[`"]?(\w+)[`"]?'
        matches = re.findall(join_pattern, sql_upper)
        tables.extend([m.lower() for m in matches])
        
        return list(set(tables))
    
    async def _direct_search_tables(self, queries: List[str]) -> Dict[str, DataSourceCandidate]:
        """MySQL에서 직접 테이블 검색"""
        import pymysql
        
        discovered = {}
        
        try:
            conn = pymysql.connect(
                host=settings.mysql_host,
                port=settings.mysql_port,
                database=settings.mysql_database,
                user=settings.mysql_user,
                password=settings.mysql_password
            )
            cursor = conn.cursor()
            
            # 모든 테이블 조회
            cursor.execute("""
                SELECT TABLE_NAME, TABLE_COMMENT 
                FROM INFORMATION_SCHEMA.TABLES 
                WHERE TABLE_SCHEMA = %s
            """, (settings.mysql_database,))
            
            all_tables = cursor.fetchall()
            
            for table_name, comment in all_tables:
                # 테이블 정보 수집
                table_info = await self._get_table_info_direct(cursor, table_name, comment)
                if table_info:
                    discovered[table_name] = table_info
            
            cursor.close()
            conn.close()
            
        except Exception as e:
            print(f"   ⚠️ 직접 검색 오류: {e}")
        
        return discovered
    
    async def _get_table_info(self, table_name: str) -> Optional[DataSourceCandidate]:
        """테이블 상세 정보 조회 (Text2SQL 메타 API)"""
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"{self.text2sql_url}/meta/tables/{table_name}"
                )
                
                if response.status_code == 200:
                    data = response.json()
                    
                    columns = data.get('columns', [])
                    numeric_cols = [c['name'] for c in columns 
                                   if c.get('type', '').lower() in ('int', 'float', 'decimal', 'numeric', 'double')]
                    time_col = self._detect_time_column(columns)
                    
                    return DataSourceCandidate(
                        table_name=table_name,
                        columns=[c['name'] for c in columns],
                        row_count=data.get('row_count', 0),
                        has_time_column=time_col is not None,
                        time_column=time_col,
                        numeric_columns=numeric_cols,
                        relevance_score=0.5,
                        sample_data=data.get('sample_data', [])
                    )
                    
            except Exception as e:
                print(f"   ⚠️ 테이블 정보 조회 실패 ({table_name}): {e}")
        
        return None
    
    async def _get_table_info_direct(self, cursor, table_name: str, comment: str = "") -> Optional[DataSourceCandidate]:
        """MySQL에서 직접 테이블 정보 조회"""
        
        try:
            # 컬럼 정보
            cursor.execute(f"DESCRIBE `{table_name}`")
            columns_info = cursor.fetchall()
            columns = [row[0] for row in columns_info]
            
            # 숫자형 컬럼 식별
            numeric_types = ('int', 'float', 'decimal', 'double', 'numeric', 'bigint', 'tinyint', 'smallint')
            numeric_cols = [row[0] for row in columns_info 
                          if any(t in row[1].lower() for t in numeric_types)]
            
            # 시간 컬럼 탐지
            time_col = self._detect_time_column([{'name': c} for c in columns])
            
            # 행 수
            cursor.execute(f"SELECT COUNT(*) FROM `{table_name}`")
            row_count = cursor.fetchone()[0]
            
            # 샘플 데이터
            cursor.execute(f"SELECT * FROM `{table_name}` LIMIT 5")
            sample_rows = cursor.fetchall()
            sample_data = [dict(zip(columns, row)) for row in sample_rows]
            
            # 날짜 직렬화
            for row in sample_data:
                for key, value in row.items():
                    if hasattr(value, 'isoformat'):
                        row[key] = value.isoformat()
                    elif isinstance(value, (np.integer, np.floating)):
                        row[key] = float(value)
            
            return DataSourceCandidate(
                table_name=table_name,
                columns=columns,
                row_count=row_count,
                has_time_column=time_col is not None,
                time_column=time_col,
                numeric_columns=numeric_cols,
                relevance_score=0.5,
                sample_data=sample_data,
                validation_notes=[comment] if comment else []
            )
            
        except Exception as e:
            print(f"   ⚠️ 테이블 직접 조회 실패 ({table_name}): {e}")
            return None
    
    def _detect_time_column(self, columns: List[Dict]) -> Optional[str]:
        """시간 컬럼 탐지"""
        time_keywords = ['date', 'time', 'month', 'year', 'day', 'created', 'updated', 
                        'timestamp', 'dt', 'ym', 'period']
        
        for col in columns:
            col_name = col.get('name', '').lower()
            for keyword in time_keywords:
                if keyword in col_name:
                    return col.get('name')
        
        return None
    
    async def _validate_timeseries(self, data_sources: List[DataSourceCandidate]) -> List[DataSourceCandidate]:
        """시계열 데이터 검증"""
        import pymysql
        
        for source in data_sources:
            notes = []
            
            # 시간 컬럼 존재 여부
            if source.has_time_column:
                notes.append(f"✅ 시간 컬럼 발견: {source.time_column}")
            else:
                notes.append("⚠️ 시간 컬럼 없음 - 시계열 분석 제한적")
            
            # 숫자형 컬럼 수
            num_numeric = len(source.numeric_columns)
            if num_numeric >= 3:
                notes.append(f"✅ 충분한 숫자형 변수: {num_numeric}개")
            else:
                notes.append(f"⚠️ 숫자형 변수 부족: {num_numeric}개")
            
            # 데이터 양
            if source.row_count >= 30:
                notes.append(f"✅ 충분한 데이터: {source.row_count}행")
            else:
                notes.append(f"⚠️ 데이터 부족: {source.row_count}행 (최소 30행 권장)")
            
            # 시계열 연속성 검증 (시간 컬럼이 있는 경우)
            if source.has_time_column and source.time_column:
                try:
                    conn = pymysql.connect(
                        host=settings.mysql_host,
                        port=settings.mysql_port,
                        database=settings.mysql_database,
                        user=settings.mysql_user,
                        password=settings.mysql_password
                    )
                    cursor = conn.cursor()
                    
                    # 시간 범위 확인
                    cursor.execute(f"""
                        SELECT MIN(`{source.time_column}`), MAX(`{source.time_column}`)
                        FROM `{source.table_name}`
                    """)
                    min_date, max_date = cursor.fetchone()
                    
                    if min_date and max_date:
                        notes.append(f"📅 데이터 기간: {min_date} ~ {max_date}")
                    
                    cursor.close()
                    conn.close()
                    
                except Exception as e:
                    notes.append(f"⚠️ 시계열 검증 오류: {e}")
            
            source.validation_notes.extend(notes)
            
            # 관련도 점수 업데이트
            score = 0.3
            if source.has_time_column:
                score += 0.3
            if len(source.numeric_columns) >= 3:
                score += 0.2
            if source.row_count >= 30:
                score += 0.2
            source.relevance_score = min(1.0, score)
        
        return data_sources
    
    def _evaluate_results(self, 
                          variables: List[CausalVariable],
                          data_sources: List[DataSourceCandidate]) -> Tuple[Dict, bool, List[str]]:
        """결과 평가 및 권장사항 생성"""
        
        summary = {
            'total_variables': len(variables),
            'total_data_sources': len(data_sources),
            'timeseries_ready': sum(1 for s in data_sources if s.has_time_column),
            'sufficient_data': sum(1 for s in data_sources if s.row_count >= 30),
            'total_numeric_columns': sum(len(s.numeric_columns) for s in data_sources)
        }
        
        recommendations = []
        
        # Causal Discovery 준비 상태 평가
        is_ready = False
        
        if summary['timeseries_ready'] > 0 and summary['sufficient_data'] > 0:
            if summary['total_numeric_columns'] >= 3:
                is_ready = True
                recommendations.append("✅ Causal Discovery 분석을 시작할 수 있습니다.")
            else:
                recommendations.append("⚠️ 숫자형 변수가 부족합니다. 추가 데이터가 필요합니다.")
        else:
            if summary['timeseries_ready'] == 0:
                recommendations.append("❌ 시계열 분석을 위한 시간 컬럼이 없습니다.")
            if summary['sufficient_data'] == 0:
                recommendations.append("❌ 충분한 데이터가 없습니다 (최소 30행 필요).")
        
        # 변수 매핑 권장사항
        for var in variables:
            matched = False
            for source in data_sources:
                for col in source.columns:
                    if any(pc.lower() in col.lower() for pc in var.potential_columns):
                        matched = True
                        break
            
            if not matched:
                recommendations.append(f"📌 '{var.name}' 변수에 매핑할 데이터를 찾지 못했습니다.")
        
        return summary, is_ready, recommendations


# 싱글톤 인스턴스
whatif_agent = WhatIfAgent()


# 테스트 함수
async def test_agent():
    """에이전트 테스트"""
    
    scenario = "환율 변동이 제품 원가와 최종 수익에 미치는 영향을 분석하고 싶습니다."
    
    result = await whatif_agent.analyze_scenario(scenario)
    
    print("\n" + "="*60)
    print("📊 분석 결과 요약")
    print("="*60)
    
    print(f"\n🎯 시나리오: {result.original_scenario}")
    
    print(f"\n📌 추출된 변수 ({len(result.extracted_variables)}개):")
    for var in result.extracted_variables:
        print(f"   - {var.name} ({var.variable_type}): {var.description}")
    
    print(f"\n🔗 가설 관계 ({len(result.hypothesized_relationships)}개):")
    for rel in result.hypothesized_relationships[:5]:
        print(f"   - {rel.get('source')} → {rel.get('target')} ({rel.get('direction')})")
    
    print(f"\n📂 발견된 데이터 소스 ({len(result.data_sources)}개):")
    for source in result.data_sources:
        print(f"   - {source.table_name}: {source.row_count}행, {len(source.numeric_columns)}개 숫자 컬럼")
        for note in source.validation_notes[:3]:
            print(f"      {note}")
    
    print(f"\n📋 평가 요약:")
    for key, value in result.validation_summary.items():
        print(f"   - {key}: {value}")
    
    print(f"\n💡 권장사항:")
    for rec in result.recommendations:
        print(f"   {rec}")
    
    print(f"\n✅ Causal Discovery 준비: {'가능' if result.is_ready_for_causal else '추가 준비 필요'}")
    
    return result


if __name__ == "__main__":
    asyncio.run(test_agent())
