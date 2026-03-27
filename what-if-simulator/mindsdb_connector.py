"""
MindsDB Connector - HTTP API를 통한 MindsDB 연결

시뮬레이션에 필요한 ML 모델 생성/조회/예측 기능 제공
"""

import requests
import json
import time
from typing import Dict, Any, List, Optional
from config import mindsdb_config


class MindsDBConnector:
    """MindsDB HTTP API 클라이언트"""
    
    def __init__(self):
        self.api_url = mindsdb_config.full_api_url
        self.timeout = 120.0
    
    def execute_query(self, query: str, description: str = "") -> Optional[Dict[str, Any]]:
        """SQL 쿼리 실행"""
        if description:
            print(f"🔹 {description}")
        
        try:
            response = requests.post(
                self.api_url,
                headers={"Content-Type": "application/json"},
                json={"query": query},
                timeout=self.timeout
            )
            result = response.json()
            
            if result.get("type") == "error":
                error_msg = result.get("error_message", "Unknown error")
                print(f"   ❌ Error: {error_msg[:200]}")
                return None
            elif result.get("type") == "table":
                rows = len(result.get('data', []))
                print(f"   ✅ Success! Rows: {rows}")
                return result
            else:
                print(f"   ✅ OK")
                return result
                
        except requests.exceptions.ConnectionError:
            print(f"   ❌ Connection Error: MindsDB 서버에 연결할 수 없습니다.")
            return None
        except requests.exceptions.Timeout:
            print(f"   ⏳ Timeout")
            return None
        except Exception as e:
            print(f"   ❌ Exception: {e}")
            return None
    
    def check_connection(self) -> bool:
        """MindsDB 연결 확인"""
        result = self.execute_query("SHOW DATABASES", "MindsDB 연결 확인")
        return result is not None
    
    def list_models(self) -> List[str]:
        """생성된 모델 목록 조회"""
        result = self.execute_query("SHOW MODELS", "모델 목록 조회")
        if result and result.get("data"):
            return [row[0] for row in result["data"]]
        return []
    
    def create_simple_model(self, model_name: str, target: str, 
                           features: List[str], training_data: List[Dict]) -> bool:
        """간단한 예측 모델 생성 (인메모리 데이터 사용)
        
        Note: 실제 환경에서는 데이터베이스 테이블을 사용해야 합니다.
        여기서는 시뮬레이션 목적으로 단순화된 버전을 제공합니다.
        """
        # 실제로는 MindsDB에 데이터 연결 후 모델을 학습해야 함
        # 여기서는 모델이 존재하는지 확인만 수행
        existing_models = self.list_models()
        if model_name in existing_models:
            print(f"   ℹ️ 모델 '{model_name}'이 이미 존재합니다.")
            return True
        
        print(f"   ⚠️ 모델 생성은 실제 데이터 연결이 필요합니다.")
        print(f"   → 대신 기본 수식 기반 예측을 사용합니다.")
        return False
    
    def predict(self, model_name: str, input_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """모델 예측 실행"""
        # WHERE 절 구성
        where_clause = " AND ".join([f"{k}={v}" for k, v in input_data.items()])
        
        query = f"""
        SELECT * FROM mindsdb.{model_name}
        WHERE {where_clause}
        """
        
        result = self.execute_query(query, f"모델 '{model_name}' 예측")
        
        if result and result.get("data"):
            columns = result.get("column_names", [])
            values = result["data"][0]
            return dict(zip(columns, values))
        return None
    
    def get_model_info(self, model_name: str) -> Optional[Dict[str, Any]]:
        """모델 정보 조회"""
        query = f"DESCRIBE MODEL {model_name}"
        result = self.execute_query(query, f"모델 '{model_name}' 정보 조회")
        return result


class SimulationModelAdapter:
    """시뮬레이션을 위한 모델 어댑터
    
    MindsDB 모델이 없을 때 기본 수식 기반 예측을 제공합니다.
    """
    
    def __init__(self, mindsdb: MindsDBConnector):
        self.mindsdb = mindsdb
        self.use_mindsdb = mindsdb.check_connection()
        
        # 기본 수식 정의 (MindsDB 모델이 없을 때 사용)
        self.default_formulas = {
            # COGS = 100 + 0.05 * (FX - 1200)
            "fx_to_cogs_model": lambda inputs: {
                "COGS": 100 + 0.05 * (inputs.get("FX_RATE", 1200) - 1200)
            },
            # Price = COGS * (1 + pass_through * 0.3)
            "price_model": lambda inputs: {
                "PRICE": inputs.get("COGS", 100) * (1 + inputs.get("PASS_THROUGH", 0.5) * 0.3)
            },
            # Demand elasticity model
            "price_to_demand_model": lambda inputs: {
                "DEMAND": 100 * max(0.1, 1 - 0.5 * (inputs.get("PRICE", 100) - 100) / 100 
                          + 0.3 * (inputs.get("BRAND_EQUITY", 50) - 50) / 50)
            },
            # Brand equity state-space model
            "brand_equity_model": lambda inputs: {
                "BRAND_EQUITY": max(0, min(100, 
                    inputs.get("BRAND_EQUITY_prev", 50) * 0.95
                    - 10 * inputs.get("REFUND_RATE", 0.05)
                    + 5 * inputs.get("CSAT", 0.7)
                    + 0.02 * inputs.get("MKT_SPEND", 100)
                ))
            },
            # CSAT model
            "csat_model": lambda inputs: {
                "CSAT": min(1.0, max(0.0,
                    0.5 + 0.3 * inputs.get("SERVICE_LEVEL", 0.8)
                    - 0.1 * max(0, inputs.get("DELIVERY_TIME", 3) - 2) / 3
                ))
            },
            # Profit model
            "profit_model": lambda inputs: {
                "PROFIT": inputs.get("SALES", 0) - inputs.get("COGS", 100) * inputs.get("DEMAND", 100)
            },
            # Sales model
            "sales_model": lambda inputs: {
                "SALES": inputs.get("PRICE", 100) * inputs.get("DEMAND", 100)
            },
        }
    
    def predict(self, model_name: str, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """예측 실행 (MindsDB 또는 기본 수식 사용)"""
        
        # MindsDB 연결 시 먼저 시도
        if self.use_mindsdb:
            result = self.mindsdb.predict(model_name, inputs)
            if result:
                return result
        
        # 기본 수식 사용
        if model_name in self.default_formulas:
            return self.default_formulas[model_name](inputs)
        
        # 모델이 없으면 빈 dict 반환
        print(f"   ⚠️ 모델 '{model_name}'에 대한 수식이 없습니다.")
        return {}
    
    def add_formula(self, model_name: str, formula_func):
        """커스텀 수식 추가"""
        self.default_formulas[model_name] = formula_func


if __name__ == "__main__":
    print("="*60)
    print("MindsDB 연결 테스트")
    print("="*60)
    
    connector = MindsDBConnector()
    
    # 연결 확인
    if connector.check_connection():
        print("\n✅ MindsDB 연결 성공!")
        
        # 모델 목록 조회
        models = connector.list_models()
        print(f"\n📋 현재 모델 목록: {models if models else '(없음)'}")
    else:
        print("\n⚠️ MindsDB 연결 실패 - 기본 수식 모드로 동작합니다.")
    
    # 어댑터 테스트
    print("\n" + "-"*60)
    print("SimulationModelAdapter 테스트")
    print("-"*60)
    
    adapter = SimulationModelAdapter(connector)
    
    # FX → COGS 예측 테스트
    test_inputs = {"FX_RATE": 1300}
    result = adapter.predict("fx_to_cogs_model", test_inputs)
    print(f"\n📊 FX→COGS 예측 (FX_RATE=1300):")
    print(f"   결과: {result}")
    
    # Demand 예측 테스트
    test_inputs = {"PRICE": 110, "BRAND_EQUITY": 60}
    result = adapter.predict("price_to_demand_model", test_inputs)
    print(f"\n📊 Price→Demand 예측 (PRICE=110, BRAND=60):")
    print(f"   결과: {result}")
