"""
What-If Simulator API Server
============================

Causal Discovery 기반 시뮬레이션 플랫폼 메인 서버
"""

import os
import json
import uuid
from datetime import datetime
from typing import Dict, List, Any, Optional

from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import pandas as pd
import numpy as np
import io

from .config import settings
from .data_discovery import data_discovery_service, DataDiscoveryResult
from .causal_api import causal_api, CausalEdge
from .mindsdb_api import mindsdb_api
from .literacy_api import literacy_service
from .whatif_agent import whatif_agent, ScenarioAnalysisResult
from .ttm_api import ttm_service, TTMPredictionResult

# FastAPI 앱 생성
app = FastAPI(
    title="What-If Simulator API",
    description="Causal Discovery 기반 예측 시뮬레이션 플랫폼",
    version="1.0.0"
)

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ====================
# Request/Response 모델
# ====================

class DataDiscoveryRequest(BaseModel):
    """데이터 발견 요청"""
    query: str
    max_tables: int = 10


class CausalDiscoveryRequest(BaseModel):
    """Causal Discovery 요청"""
    data_source: str
    methods: List[str] = ['correlation', 'granger']
    max_lag: int = 2
    

class SQLExecuteRequest(BaseModel):
    """SQL 실행 요청"""
    sql: str
    use_mindsdb: bool = False


class ValidationRequest(BaseModel):
    """검증 요청"""
    session_id: str


class LiteracyRequest(BaseModel):
    """Literacy 설명 요청"""
    session_id: str
    report_type: str = 'summary'  # summary, discovery, validation, comparison
    language: str = 'ko'


class MindsDBCompareRequest(BaseModel):
    """MindsDB 비교 요청"""
    session_id: str
    causal_edges: Optional[List[Dict[str, Any]]] = None  # 프론트엔드에서 직접 전달
    discovered_tables: Optional[List[str]] = None  # 테이블 목록
    

class SimulationRequest(BaseModel):
    """What-If 시뮬레이션 요청"""
    session_id: str
    scenarios: Dict[str, Any]
    timesteps: int = 12


# 세션 저장소 (실제 운영에서는 Redis 등 사용)
sessions: Dict[str, Dict] = {}


# ====================
# API 엔드포인트
# ====================

@app.get("/")
async def root():
    """API 상태 확인"""
    return {
        "status": "running",
        "service": "What-If Simulator API",
        "version": "1.0.0",
        "timestamp": datetime.now().isoformat()
    }


@app.get("/api/config")
async def get_config():
    """현재 설정 조회 (민감 정보 제외)"""
    return {
        "mysql_host": settings.mysql_host,
        "mysql_port": settings.mysql_port,
        "mysql_database": settings.mysql_database,
        "mindsdb_url": settings.mindsdb_url,
        "text2sql_url": settings.text2sql_url,
        "test_ratio": settings.test_ratio
    }


class AgentAnalysisRequest(BaseModel):
    """에이전트 분석 요청"""
    scenario: str
    use_text2sql: bool = True


@app.post("/api/agent/analyze")
async def agent_analyze_scenario(request: AgentAnalysisRequest):
    """
    What-If 에이전트를 통한 시나리오 분석
    
    1. 시나리오에서 변수 추출
    2. 인과관계 가설 생성
    3. 데이터 탐색 쿼리 생성
    4. Text2SQL 에이전트로 데이터 소스 발견
    5. 시계열 데이터 검증
    """
    try:
        result = await whatif_agent.analyze_scenario(request.scenario)
        
        # 세션 생성
        session_id = str(uuid.uuid4())
        sessions[session_id] = {
            'created_at': datetime.now().isoformat(),
            'query': request.scenario,
            'agent_result': {
                'extracted_variables': [
                    {'name': v.name, 'description': v.description, 
                     'variable_type': v.variable_type, 'data_type': v.data_type}
                    for v in result.extracted_variables
                ],
                'hypothesized_relationships': result.hypothesized_relationships,
                'generated_queries': result.generated_queries,
                'data_sources': [
                    {
                        'table_name': s.table_name,
                        'columns': s.columns,
                        'row_count': s.row_count,
                        'has_time_column': s.has_time_column,
                        'time_column': s.time_column,
                        'numeric_columns': s.numeric_columns,
                        'relevance_score': s.relevance_score,
                        'sample_data': s.sample_data,
                        'validation_notes': s.validation_notes
                    } for s in result.data_sources
                ],
                'validation_summary': result.validation_summary,
                'is_ready_for_causal': result.is_ready_for_causal,
                'recommendations': result.recommendations
            }
        }
        
        return {
            'session_id': session_id,
            'scenario': result.original_scenario,
            'variables': sessions[session_id]['agent_result']['extracted_variables'],
            'relationships': result.hypothesized_relationships,
            'data_sources': sessions[session_id]['agent_result']['data_sources'],
            'validation_summary': result.validation_summary,
            'is_ready_for_causal': result.is_ready_for_causal,
            'recommendations': result.recommendations
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/discovery/search")
async def discover_data(request: DataDiscoveryRequest):
    """
    자연어 쿼리로 관련 데이터 발견
    
    사용자의 예측 요구사항을 분석하여 
    관련된 테이블과 데이터를 찾습니다.
    """
    try:
        result = await data_discovery_service.discover_from_query(
            request.query,
            request.max_tables
        )
        
        # 세션 생성
        session_id = str(uuid.uuid4())
        sessions[session_id] = {
            'created_at': datetime.now().isoformat(),
            'query': request.query,
            'discovery_result': {
                'tables': [
                    {
                        'table_name': t.table_name,
                        'columns': t.columns,
                        'row_count': t.row_count,
                        'sample_data': t.sample_data,
                        'relevance_score': t.relevance_score,
                        'description': t.description
                    } for t in result.tables
                ],
                'suggested_sql': result.suggested_sql
            }
        }
        
        return {
            'session_id': session_id,
            'query': result.query,
            'tables': sessions[session_id]['discovery_result']['tables'],
            'suggested_sql': result.suggested_sql
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/data/collect")
async def collect_data(request: SQLExecuteRequest):
    """SQL 실행하여 데이터 수집"""
    try:
        df = await data_discovery_service.collect_data(
            request.sql,
            request.use_mindsdb
        )
        
        return {
            'rows': len(df),
            'columns': df.columns.tolist(),
            'data': df.head(100).to_dict('records'),
            'dtypes': df.dtypes.astype(str).to_dict()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/data/upload")
async def upload_data(
    file: UploadFile = File(...),
    session_id: Optional[str] = Form(None)
):
    """CSV 파일 업로드"""
    try:
        content = await file.read()
        df = pd.read_csv(io.StringIO(content.decode('utf-8')))
        
        # 새 세션 생성 또는 기존 세션 사용
        if not session_id or session_id not in sessions:
            session_id = str(uuid.uuid4())
            sessions[session_id] = {
                'created_at': datetime.now().isoformat()
            }
        
        sessions[session_id]['dataframe'] = df.to_dict('records')
        sessions[session_id]['columns'] = df.columns.tolist()
        sessions[session_id]['filename'] = file.filename
        
        return {
            'session_id': session_id,
            'filename': file.filename,
            'rows': len(df),
            'columns': df.columns.tolist(),
            'sample_data': df.head(5).to_dict('records')
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/causal/discover")
async def run_causal_discovery(
    session_id: str = Form(...),
    methods: str = Form('correlation,granger'),
    max_lag: int = Form(2),
    file: Optional[UploadFile] = File(None)
):
    """
    Causal Discovery 실행
    
    데이터에서 인과관계를 발견하고 영향 함수를 추정합니다.
    세션에 agent_result가 있으면 MindsDB VIEW를 자동 생성하여 데이터 로드.
    """
    try:
        df = None
        
        # 1. 업로드된 파일이 있으면 사용
        if file:
            content = await file.read()
            df = pd.read_csv(io.StringIO(content.decode('utf-8')))
            
        # 2. 세션에 저장된 dataframe이 있으면 사용
        elif session_id in sessions and 'dataframe' in sessions[session_id]:
            df = pd.DataFrame(sessions[session_id]['dataframe'])
            
        # 3. 세션에 agent_result가 있으면 MindsDB VIEW 생성하여 데이터 로드
        elif session_id in sessions and 'agent_result' in sessions[session_id]:
            agent_result = sessions[session_id]['agent_result']
            data_sources = agent_result.get('data_sources', [])
            
            if data_sources:
                # MindsDB VIEW 생성
                view_name = f"whatif_view_{session_id.replace('-', '_')[:8]}"
                
                # 테이블 정보 변환
                tables_for_view = [
                    {
                        'table_name': ds['table_name'],
                        'columns': ds['columns'],
                        'time_column': ds.get('time_column', 'month')
                    }
                    for ds in data_sources
                    if ds.get('has_time_column', False) or 'month' in [c.lower() for c in ds.get('columns', [])]
                ]
                
                if tables_for_view:
                    # MindsDB VIEW 생성
                    view_result = await mindsdb_api.create_analysis_view(
                        view_name=view_name,
                        tables=tables_for_view,
                        mysql_db='mysql_sample'
                    )
                    
                    if 'error' not in view_result:
                        # VIEW에서 데이터 로드
                        df = await mindsdb_api.get_view_data(view_name)
                        
                        if not df.empty:
                            sessions[session_id]['view_name'] = view_name
                            sessions[session_id]['view_columns'] = view_result.get('columns', [])
                
                # VIEW 생성 실패 시 직접 MySQL 쿼리
                if df is None or df.empty:
                    # 테이블별로 데이터 조회 후 merge
                    dfs = []
                    time_col = 'month'
                    
                    for ds in data_sources[:5]:  # 최대 5개 테이블
                        try:
                            table_df = await data_discovery_service.collect_data(
                                f"SELECT * FROM {ds['table_name']}",
                                use_mindsdb=False
                            )
                            if not table_df.empty:
                                # 컬럼명에 테이블 prefix 추가 (시간 컬럼 제외)
                                renamed = {}
                                for col in table_df.columns:
                                    if col.lower() != time_col and col.lower() != 'id':
                                        renamed[col] = f"{ds['table_name']}_{col}"
                                table_df = table_df.rename(columns=renamed)
                                dfs.append(table_df)
                        except Exception as e:
                            print(f"테이블 {ds['table_name']} 로드 실패: {e}")
                    
                    if dfs:
                        # 시간 컬럼 기준으로 merge
                        df = dfs[0]
                        for other_df in dfs[1:]:
                            if time_col in df.columns and time_col in other_df.columns:
                                df = df.merge(other_df, on=time_col, how='outer')
                            elif 'month' in df.columns and 'month' in other_df.columns:
                                df = df.merge(other_df, on='month', how='outer')
        
        # 데이터가 여전히 없으면 에러
        if df is None or df.empty:
            raise HTTPException(
                status_code=400, 
                detail="데이터가 없습니다. 2단계에서 테이블을 선택하고 SQL을 실행하거나 파일을 업로드해주세요."
            )
        
        # Causal Discovery 실행
        methods_list = methods.split(',')
        result = await causal_api.discover_causality(df, methods_list, max_lag)
        
        # 영향 함수 추정
        influence_functions = await causal_api.estimate_influence_functions(df, result.edges)
        
        # 검증 실행
        validation = await causal_api.validate_edges(df, result.edges)
        
        # 세션에 결과 저장
        if session_id not in sessions:
            session_id = str(uuid.uuid4())
            sessions[session_id] = {'created_at': datetime.now().isoformat()}
            
        sessions[session_id]['dataframe'] = df.to_dict('records')
        sessions[session_id]['causal_result'] = {
            'edges': [e.to_dict() for e in result.edges],
            'summary': result.summary
        }
        sessions[session_id]['influence_functions'] = influence_functions
        sessions[session_id]['validation'] = validation
        
        return {
            'session_id': session_id,
            'edges_count': len(result.edges),
            'edges': [e.to_dict() for e in result.edges[:20]],  # 상위 20개
            'summary': result.summary,
            'influence_functions': influence_functions[:10],  # 상위 10개
            'validation': {
                'total_validated': validation['total_validated'],
                'valid_count': validation['valid_count'],
                'overfit_count': validation['overfit_count'],
                'mean_r_squared': validation['mean_r_squared']
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/causal/validate")
async def validate_models(request: ValidationRequest):
    """모델 검증 상세 결과 조회"""
    try:
        if request.session_id not in sessions:
            raise HTTPException(status_code=404, detail="세션을 찾을 수 없습니다.")
            
        session = sessions[request.session_id]
        
        if 'validation' not in session:
            raise HTTPException(status_code=400, detail="먼저 Causal Discovery를 실행해주세요.")
        
        return session['validation']
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ====================
# Neo4j 온톨로지 저장
# ====================

class Neo4jSaveRequest(BaseModel):
    """Neo4j 저장 요청"""
    session_id: str


@app.post("/api/neo4j/save")
async def save_to_neo4j(request: Neo4jSaveRequest):
    """
    발견된 인과관계를 Neo4j에 온톨로지로 저장
    """
    from neo4j import GraphDatabase
    
    try:
        if request.session_id not in sessions:
            raise HTTPException(status_code=404, detail="세션을 찾을 수 없습니다.")
            
        session = sessions[request.session_id]
        
        if 'causal_result' not in session:
            raise HTTPException(status_code=400, detail="먼저 Causal Discovery를 실행해주세요.")
        
        edges = session['causal_result']['edges']
        
        # Neo4j 연결
        driver = GraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_user, settings.neo4j_password)
        )
        
        nodes_created = 0
        edges_created = 0
        
        with driver.session() as neo_session:
            # 기존 세션의 노드/엣지 삭제 (선택적)
            neo_session.run("""
                MATCH (n:CausalVariable {session_id: $session_id})
                DETACH DELETE n
            """, session_id=request.session_id)
            
            # 노드 생성
            nodes = set()
            for edge in edges:
                nodes.add(edge['source'])
                nodes.add(edge['target'])
            
            # 핵심 원인/결과 변수 확인
            summary = session['causal_result'].get('summary', {})
            root_causes = set([name for name, _ in summary.get('root_causes', [])])
            final_effects = set([name for name, _ in summary.get('final_effects', [])])
            
            for node in nodes:
                node_type = 'intermediate'
                if node in root_causes:
                    node_type = 'root_cause'
                elif node in final_effects:
                    node_type = 'final_effect'
                
                neo_session.run("""
                    MERGE (n:CausalVariable {name: $name, session_id: $session_id})
                    SET n.type = $type, n.created_at = datetime()
                """, name=node, session_id=request.session_id, type=node_type)
                nodes_created += 1
            
            # 엣지 생성
            for edge in edges:
                neo_session.run("""
                    MATCH (s:CausalVariable {name: $source, session_id: $session_id})
                    MATCH (t:CausalVariable {name: $target, session_id: $session_id})
                    MERGE (s)-[r:CAUSES]->(t)
                    SET r.strength = $strength,
                        r.direction = $direction,
                        r.method = $method,
                        r.r_squared = $r_squared,
                        r.formula = $formula,
                        r.lag = $lag
                """, 
                    source=edge['source'],
                    target=edge['target'],
                    session_id=request.session_id,
                    strength=edge.get('strength', 0),
                    direction=edge.get('direction', 'positive'),
                    method=edge.get('method', 'correlation'),
                    r_squared=edge.get('r_squared', 0),
                    formula=edge.get('formula', ''),
                    lag=edge.get('lag', 0)
                )
                edges_created += 1
        
        driver.close()
        
        return {
            'saved': True,
            'nodes_count': nodes_created,
            'edges_count': edges_created,
            'message': f'Neo4j에 {nodes_created}개 노드와 {edges_created}개 엣지가 저장되었습니다.'
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/neo4j/graph/{session_id}")
async def get_neo4j_graph(session_id: str):
    """
    Neo4j에서 인과관계 그래프 조회
    """
    from neo4j import GraphDatabase
    
    try:
        driver = GraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_user, settings.neo4j_password)
        )
        
        nodes = []
        edges = []
        
        with driver.session() as neo_session:
            # 노드 조회
            result = neo_session.run("""
                MATCH (n:CausalVariable {session_id: $session_id})
                RETURN n.name as id, n.name as label, n.type as type
            """, session_id=session_id)
            
            for record in result:
                nodes.append({
                    'id': record['id'],
                    'label': record['label'],
                    'type': record['type']
                })
            
            # 엣지 조회
            result = neo_session.run("""
                MATCH (s:CausalVariable {session_id: $session_id})-[r:CAUSES]->(t:CausalVariable)
                RETURN s.name as source, t.name as target, 
                       r.strength as strength, r.direction as direction,
                       r.formula as formula, r.r_squared as r_squared
            """, session_id=session_id)
            
            for record in result:
                edges.append({
                    'source': record['source'],
                    'target': record['target'],
                    'strength': record['strength'],
                    'direction': record['direction'],
                    'formula': record['formula'],
                    'r_squared': record['r_squared']
                })
        
        driver.close()
        
        return {
            'nodes': nodes,
            'edges': edges
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/mindsdb/compare")
async def compare_with_mindsdb(request: MindsDBCompareRequest):
    """
    Causal Discovery 결과와 MindsDB 모델 비교
    - 세션에서 데이터를 가져오거나
    - 요청에 직접 포함된 데이터 사용
    - MySQL에서 직접 데이터 로드
    """
    import pymysql
    
    try:
        edges = None
        df = None
        
        # 1. 요청에서 직접 데이터를 받은 경우
        if request.causal_edges:
            edges = request.causal_edges
            
            # 테이블 목록이 있으면 MySQL에서 직접 데이터 로드
            if request.discovered_tables and len(request.discovered_tables) > 0:
                try:
                    conn = pymysql.connect(
                        host=settings.mysql_host,
                        port=settings.mysql_port,
                        database=settings.mysql_database,
                        user=settings.mysql_user,
                        password=settings.mysql_password
                    )
                    
                    # 각 테이블에서 데이터 로드 후 JOIN
                    dfs = []
                    for table_name in request.discovered_tables[:6]:  # 최대 6개
                        try:
                            table_df = pd.read_sql(f"SELECT * FROM {table_name} ORDER BY month LIMIT 100", conn)
                            if not table_df.empty:
                                # 테이블 이름을 컬럼 prefix로 추가 (month 제외)
                                renamed_cols = {}
                                for col in table_df.columns:
                                    if col.lower() != 'month':
                                        renamed_cols[col] = f"{table_name}_{col}"
                                table_df = table_df.rename(columns=renamed_cols)
                                dfs.append(table_df)
                        except Exception as e:
                            print(f"테이블 {table_name} 로드 실패: {e}")
                    
                    conn.close()
                    
                    # 데이터프레임 병합 (month 컬럼 기준)
                    if dfs:
                        df = dfs[0]
                        for other_df in dfs[1:]:
                            if 'month' in df.columns and 'month' in other_df.columns:
                                df = df.merge(other_df, on='month', how='outer')
                            else:
                                # month가 없으면 index로 병합
                                df = pd.concat([df, other_df], axis=1)
                        
                        # 숫자 컬럼만 유지
                        numeric_cols = df.select_dtypes(include=['number']).columns.tolist()
                        if 'month' in df.columns:
                            numeric_cols = ['month'] + [c for c in numeric_cols if c != 'month']
                        df = df[numeric_cols].dropna()
                        
                        print(f"MySQL에서 로드된 데이터: {len(df)} rows, {len(df.columns)} columns")
                        
                except Exception as e:
                    print(f"MySQL 데이터 로드 실패: {e}")
                    import traceback
                    traceback.print_exc()
        
        # 2. 세션에서 데이터 가져오기 (fallback)
        if request.session_id in sessions:
            session = sessions[request.session_id]
            if edges is None and 'causal_result' in session:
                edges = session['causal_result']['edges']
            if df is None and 'dataframe' in session:
                df = pd.DataFrame(session['dataframe'])
        
        if edges is None:
            raise HTTPException(status_code=400, detail="Causal Discovery 결과가 없습니다. 먼저 온톨로지 발견을 실행해주세요.")
        
        # 데이터가 없으면 간소화된 비교 수행
        if df is None or df.empty:
            # 데이터 없이 엣지 정보만으로 응답 생성
            return {
                'comparisons': [
                    {
                        'edge': f"{e.get('source', '')} → {e.get('target', '')}",
                        'source_label': e.get('source_label', e.get('source', '')),
                        'target_label': e.get('target_label', e.get('target', '')),
                        'causal_r2': e.get('r_squared', e.get('strength', 0)),
                        'mindsdb_r2': None,
                        'note': '데이터 없음 - MindsDB 비교 불가'
                    }
                    for e in edges[:20]  # 상위 20개만
                ],
                'summary': {
                    'total_compared': 0,
                    'mean_causal_r2': sum(e.get('r_squared', e.get('strength', 0)) for e in edges) / len(edges) if edges else 0,
                    'mean_mindsdb_r2': 0,
                    'mindsdb_wins': 0,
                    'causal_wins': 0,
                    'note': '데이터가 없어 MindsDB 비교가 불가능합니다. 데이터 선택 단계에서 테이블을 수집해주세요.'
                }
            }
        
        # MindsDB 비교 실행
        comparison = await mindsdb_api.compare_with_causal(df, edges)
        
        # 세션에 저장
        if request.session_id in sessions:
            sessions[request.session_id]['comparison'] = comparison
        
        return comparison
        
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/mindsdb/create-model")
async def create_mindsdb_model(
    model_name: str = Form(...),
    target: str = Form(...),
    features: str = Form(...),
    session_id: str = Form(...)
):
    """MindsDB 모델 생성"""
    try:
        if session_id not in sessions:
            raise HTTPException(status_code=404, detail="세션을 찾을 수 없습니다.")
            
        session = sessions[session_id]
        
        if 'dataframe' not in session:
            raise HTTPException(status_code=400, detail="데이터가 없습니다.")
        
        df = pd.DataFrame(session['dataframe'])
        
        # MindsDB에 데이터 업로드
        table_name = f"causal_data_{session_id[:8]}"
        await mindsdb_api.upload_dataframe(df, table_name)
        
        # 모델 생성
        features_list = [f.strip() for f in features.split(',')]
        result = await mindsdb_api.create_model(
            model_name,
            target,
            features_list,
            table_name
        )
        
        return {
            'model_name': model_name,
            'target': target,
            'features': features_list,
            'result': result
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/literacy/explain")
async def generate_explanation(request: LiteracyRequest):
    """
    LLM 기반 분석 결과 설명 생성
    """
    try:
        if request.session_id not in sessions:
            raise HTTPException(status_code=404, detail="세션을 찾을 수 없습니다.")
            
        session = sessions[request.session_id]
        
        if request.report_type == 'discovery':
            if 'causal_result' not in session:
                raise HTTPException(status_code=400, detail="Causal Discovery 결과가 없습니다.")
            explanation = await literacy_service.explain_causal_discovery(
                session['causal_result'],
                request.language
            )
            
        elif request.report_type == 'validation':
            if 'validation' not in session:
                raise HTTPException(status_code=400, detail="검증 결과가 없습니다.")
            explanation = await literacy_service.explain_validation(
                session['validation'],
                request.language
            )
            
        elif request.report_type == 'comparison':
            if 'comparison' not in session:
                raise HTTPException(status_code=400, detail="비교 결과가 없습니다.")
            explanation = await literacy_service.explain_comparison(
                session['comparison'],
                request.language
            )
            
        else:  # summary
            causal = session.get('causal_result', {})
            validation = session.get('validation', {})
            comparison = session.get('comparison')
            
            explanation = await literacy_service.generate_executive_summary(
                causal, validation, comparison, request.language
            )
        
        session[f'literacy_{request.report_type}'] = explanation
        
        return {
            'report_type': request.report_type,
            'language': request.language,
            'explanation': explanation
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/literacy/presentation")
async def generate_presentation(
    session_id: str = Form(...),
    slides_count: int = Form(5),
    language: str = Form('ko')
):
    """프레젠테이션 슬라이드 생성"""
    try:
        if session_id not in sessions:
            raise HTTPException(status_code=404, detail="세션을 찾을 수 없습니다.")
            
        session = sessions[session_id]
        
        analysis = {
            'causal': session.get('causal_result', {}),
            'validation': session.get('validation', {}),
            'comparison': session.get('comparison', {})
        }
        
        slides = await literacy_service.generate_presentation_content(
            analysis, slides_count, language
        )
        
        return {'slides': slides}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/sessions/{session_id}")
async def get_session(session_id: str):
    """세션 정보 조회"""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="세션을 찾을 수 없습니다.")
    
    session = sessions[session_id]
    
    # dataframe은 제외하고 반환 (크기가 클 수 있음)
    return {
        'session_id': session_id,
        'created_at': session.get('created_at'),
        'query': session.get('query'),
        'has_data': 'dataframe' in session,
        'data_rows': len(session.get('dataframe', [])),
        'columns': session.get('columns', []),
        'has_causal_result': 'causal_result' in session,
        'has_validation': 'validation' in session,
        'has_comparison': 'comparison' in session
    }


@app.get("/api/sessions")
async def list_sessions():
    """모든 세션 목록"""
    return {
        'sessions': [
            {
                'session_id': sid,
                'created_at': s.get('created_at'),
                'query': s.get('query', '')[:100]
            }
            for sid, s in sessions.items()
        ]
    }


@app.delete("/api/sessions/{session_id}")
async def delete_session(session_id: str):
    """세션 삭제"""
    if session_id in sessions:
        del sessions[session_id]
        return {'deleted': True}
    raise HTTPException(status_code=404, detail="세션을 찾을 수 없습니다.")


# ==================== TTM (Time Series Foundation Model) API ====================

@app.get("/api/ttm/info")
async def get_ttm_info():
    """TTM 모델 정보"""
    return ttm_service.get_model_info()


@app.post("/api/ttm/initialize")
async def initialize_ttm():
    """TTM 모델 초기화"""
    success = await ttm_service.initialize()
    return {
        "initialized": success,
        "info": ttm_service.get_model_info() if success else None
    }


class TTMCompareRequest(BaseModel):
    """TTM 비교 요청"""
    session_id: str
    causal_edges: Optional[List[Dict[str, Any]]] = None
    discovered_tables: Optional[List[str]] = None
    include_ttm: bool = True  # TTM 모델 포함 여부


@app.post("/api/ttm/compare")
async def compare_with_ttm(request: TTMCompareRequest):
    """
    온톨로지 모델, MindsDB, TTM 3가지 모델 비교
    """
    import pymysql
    
    try:
        edges = request.causal_edges or []
        df = None
        
        # MySQL에서 데이터 로드
        if request.discovered_tables and len(request.discovered_tables) > 0:
            try:
                conn = pymysql.connect(
                    host=settings.mysql_host,
                    port=settings.mysql_port,
                    database=settings.mysql_database,
                    user=settings.mysql_user,
                    password=settings.mysql_password
                )
                
                dfs = []
                for table_name in request.discovered_tables[:6]:
                    try:
                        table_df = pd.read_sql(f"SELECT * FROM {table_name} ORDER BY month LIMIT 100", conn)
                        if not table_df.empty:
                            renamed_cols = {}
                            for col in table_df.columns:
                                if col.lower() != 'month':
                                    renamed_cols[col] = f"{table_name}_{col}"
                            table_df = table_df.rename(columns=renamed_cols)
                            dfs.append(table_df)
                    except Exception as e:
                        print(f"테이블 {table_name} 로드 실패: {e}")
                
                conn.close()
                
                if dfs:
                    df = dfs[0]
                    for other_df in dfs[1:]:
                        if 'month' in df.columns and 'month' in other_df.columns:
                            df = df.merge(other_df, on='month', how='outer')
                        else:
                            df = pd.concat([df, other_df], axis=1)
                    
                    numeric_cols = df.select_dtypes(include=['number']).columns.tolist()
                    if 'month' in df.columns:
                        numeric_cols = ['month'] + [c for c in numeric_cols if c != 'month']
                    df = df[numeric_cols].dropna()
                    
            except Exception as e:
                print(f"MySQL 데이터 로드 실패: {e}")
        
        if df is None or df.empty:
            return {
                'error': '데이터가 없습니다.',
                'ttm_available': ttm_service.is_available()
            }
        
        # ID 컬럼 제외
        all_columns = [c for c in df.columns 
                       if c.lower() != 'month' 
                       and not c.lower().endswith('_id')
                       and c.lower() != 'id']
        
        if len(all_columns) < 2:
            return {'error': '분석할 수 있는 컬럼이 부족합니다.'}
        
        # 결과 저장
        comparison_results = []
        ttm_initialized = False
        
        # TTM 초기화 시도
        if request.include_ttm:
            ttm_initialized = await ttm_service.initialize()
        
        # 상위 컬럼 쌍에 대해 비교
        for i, col1 in enumerate(all_columns[:4]):
            for col2 in all_columns[i+1:5]:
                result = {
                    'source': col1,
                    'target': col2,
                    'source_label': col1.replace('_', ' ').title(),
                    'target_label': col2.replace('_', ' ').title()
                }
                
                # 1. 선형 회귀
                from sklearn.linear_model import LinearRegression
                from sklearn.metrics import r2_score, mean_absolute_percentage_error
                
                try:
                    n = len(df)
                    train_size = int(n * 0.8)
                    
                    X_train = df[[col1]].iloc[:train_size].values
                    y_train = df[col2].iloc[:train_size].values
                    X_test = df[[col1]].iloc[train_size:].values
                    y_test = df[col2].iloc[train_size:].values
                    
                    if len(X_train) >= 5 and len(X_test) >= 2:
                        lr_model = LinearRegression()
                        lr_model.fit(X_train, y_train)
                        lr_preds = lr_model.predict(X_test)
                        
                        result['ontology'] = {
                            'r2': float(r2_score(y_test, lr_preds)),
                            'mape': float(mean_absolute_percentage_error(y_test, lr_preds) * 100),
                            'predictions': lr_preds.tolist(),
                            'actual': y_test.tolist()
                        }
                except Exception as e:
                    result['ontology'] = {'error': str(e)}
                
                # 2. TTM 모델
                if ttm_initialized:
                    try:
                        ttm_result = await ttm_service.compare_predictions(df, col1, col2)
                        if ttm_result and 'ttm' in ttm_result:
                            result['ttm'] = ttm_result['ttm']
                    except Exception as e:
                        result['ttm'] = {'error': str(e)}
                else:
                    result['ttm'] = {'available': False, 'note': 'TTM 모델 초기화 필요'}
                
                comparison_results.append(result)
        
        # 요약 통계
        ontology_r2s = [r['ontology']['r2'] for r in comparison_results if 'ontology' in r and 'r2' in r.get('ontology', {})]
        ttm_r2s = [r['ttm']['r2'] for r in comparison_results if 'ttm' in r and 'r2' in r.get('ttm', {})]
        
        summary = {
            'total_compared': len(comparison_results),
            'ttm_available': ttm_initialized,
            'ttm_model': ttm_service.model_name if ttm_initialized else None,
            'ontology_mean_r2': float(np.mean(ontology_r2s)) if ontology_r2s else 0,
            'ttm_mean_r2': float(np.mean(ttm_r2s)) if ttm_r2s else 0,
            'ontology_wins': sum(1 for r in comparison_results 
                                if r.get('ontology', {}).get('r2', 0) > max(
                                    r.get('ttm', {}).get('r2', -999),
                                    r.get('mindsdb', {}).get('r2', -999)
                                )),
            'ttm_wins': sum(1 for r in comparison_results 
                          if r.get('ttm', {}).get('r2', 0) > max(
                              r.get('ontology', {}).get('r2', -999),
                              r.get('mindsdb', {}).get('r2', -999)
                          )),
            'mindsdb_wins': sum(1 for r in comparison_results 
                               if r.get('mindsdb', {}).get('r2', 0) > max(
                                   r.get('ontology', {}).get('r2', -999),
                                   r.get('ttm', {}).get('r2', -999)
                               )),
            'mindsdb_available': any(r.get('mindsdb', {}).get('r2') is not None for r in comparison_results),
            'mindsdb_mean_r2': np.mean([r.get('mindsdb', {}).get('r2', 0) for r in comparison_results if r.get('mindsdb', {}).get('r2') is not None]) if any(r.get('mindsdb', {}).get('r2') is not None for r in comparison_results) else 0
        }
        
        # 차트 데이터 생성
        prediction_charts = []
        for r in comparison_results[:3]:
            if 'ontology' in r and 'predictions' in r['ontology']:
                chart = {
                    'edge': f"{r['source_label']} → {r['target_label']}",
                    'source': r['source'],
                    'target': r['target'],
                    'labels': list(range(len(r['ontology']['actual']))),
                    'actual': r['ontology']['actual'],
                    'ontology_predicted': r['ontology']['predictions'],
                }
                if 'ttm' in r and 'predictions' in r['ttm']:
                    chart['ttm_predicted'] = r['ttm']['predictions']
                if 'mindsdb' in r and 'predictions' in r['mindsdb']:
                    chart['mindsdb_predicted'] = r['mindsdb']['predictions']
                prediction_charts.append(chart)
        
        return {
            'comparisons': comparison_results,
            'prediction_charts': prediction_charts,
            'summary': summary
        }
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


# 앱 실행 함수
def run():
    import uvicorn
    uvicorn.run(
        "what-if-simulator.api.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=True
    )


if __name__ == "__main__":
    run()
