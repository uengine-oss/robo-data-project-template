#!/usr/bin/env python3
"""
MindsDB 모델 설정 - files 데이터소스 활용

CSV 파일을 MindsDB files에 업로드하고 모델을 학습시킵니다.
"""

import requests
import json
import time
from typing import Dict, Any

MINDSDB_API = "http://127.0.0.1:47334/api/sql/query"


def run_query(query: str, description: str = "", timeout: int = 120) -> Dict[str, Any]:
    """MindsDB SQL 쿼리 실행"""
    if description:
        print(f"🔹 {description}")
    
    try:
        response = requests.post(
            MINDSDB_API,
            headers={"Content-Type": "application/json"},
            json={"query": query},
            timeout=timeout
        )
        result = response.json()
        
        if result.get("type") == "error":
            print(f"   ❌ Error: {result.get('error_message', '')[:200]}")
            return result
        elif result.get("type") == "table":
            rows = len(result.get('data', []))
            print(f"   ✅ Success! Rows: {rows}")
            return result
        else:
            print(f"   ✅ OK")
            return result
    except Exception as e:
        print(f"   ❌ Exception: {e}")
        return {"type": "error", "error_message": str(e)}


def upload_csv_to_files():
    """CSV 파일을 MindsDB files에 업로드"""
    print("\n" + "="*60)
    print("CSV 파일을 MindsDB files에 업로드")
    print("="*60)
    
    # MindsDB files API로 직접 업로드
    upload_url = "http://127.0.0.1:47334/api/files/kpi_monthly"
    
    try:
        with open("kpi_monthly.csv", "rb") as f:
            response = requests.put(
                upload_url,
                files={"file": ("kpi_monthly.csv", f, "text/csv")},
                timeout=60
            )
        
        if response.status_code in [200, 201]:
            print("   ✅ CSV 파일 업로드 성공!")
            return True
        else:
            print(f"   ❌ 업로드 실패: {response.status_code} - {response.text[:200]}")
            return False
    except Exception as e:
        print(f"   ❌ Exception: {e}")
        return False


def verify_data():
    """업로드된 데이터 확인"""
    print("\n📊 업로드된 데이터 확인:")
    result = run_query(
        "SELECT * FROM files.kpi_monthly LIMIT 5",
        "처음 5개 레코드 조회"
    )
    
    if result.get("data"):
        cols = result.get("column_names", [])
        print(f"\n   📋 컬럼: {cols[:8]}...")
        for i, row in enumerate(result["data"][:3]):
            print(f"   Row {i+1}: {dict(zip(cols[:5], row[:5]))}")
        return True
    return False


def create_models():
    """MindsDB 예측 모델 생성"""
    print("\n" + "="*60)
    print("MindsDB ML 모델 생성")
    print("="*60)
    
    models = [
        {
            "name": "whatif_cogs_model",
            "query": "SELECT fx_rate, cogs FROM kpi_monthly",
            "target": "cogs",
            "description": "환율 → 매출원가 예측"
        },
        {
            "name": "whatif_demand_model",
            "query": "SELECT price, brand_equity, loyalty, demand FROM kpi_monthly",
            "target": "demand",
            "description": "가격/브랜드/충성도 → 수요 예측"
        },
        {
            "name": "whatif_brand_model",
            "query": "SELECT csat, refund_rate, mkt_spend, price_volatility, brand_equity FROM kpi_monthly",
            "target": "brand_equity",
            "description": "다요인 → 브랜드가치 예측"
        },
        {
            "name": "whatif_profit_model",
            "query": "SELECT price, demand, cogs, profit FROM kpi_monthly",
            "target": "profit",
            "description": "가격/수요/원가 → 이익 예측"
        },
    ]
    
    for model in models:
        print(f"\n📊 {model['description']}")
        
        # 기존 모델 삭제
        run_query(
            f"DROP MODEL IF EXISTS mindsdb.{model['name']}",
            f"기존 모델 삭제"
        )
        
        # 새 모델 생성
        create_sql = f"""
        CREATE MODEL mindsdb.{model['name']}
        FROM files ({model['query']})
        PREDICT {model['target']}
        """
        
        result = run_query(create_sql, f"모델 생성: {model['name']}")
        
        if result.get("type") != "error":
            print(f"   ⏳ 학습 시작됨...")
    
    return models


def wait_for_training(models, max_wait=180):
    """모델 학습 완료 대기"""
    print("\n" + "="*60)
    print("모델 학습 상태 모니터링")
    print("="*60)
    
    start_time = time.time()
    completed = set()
    
    while len(completed) < len(models) and (time.time() - start_time) < max_wait:
        time.sleep(5)
        
        result = run_query("SHOW MODELS", "모델 상태 확인")
        
        if result.get("data"):
            for row in result["data"]:
                model_name = row[0]
                status = row[1] if len(row) > 1 else "unknown"
                
                if "whatif" in model_name:
                    if status == "complete" and model_name not in completed:
                        print(f"   ✅ {model_name}: 학습 완료!")
                        completed.add(model_name)
                    elif model_name not in completed:
                        print(f"   ⏳ {model_name}: {status}")
        
        elapsed = int(time.time() - start_time)
        print(f"   ... 경과 시간: {elapsed}초")
    
    if len(completed) < len(models):
        print(f"\n   ⚠️ 일부 모델이 아직 학습 중입니다. 나중에 다시 확인하세요.")
    
    return completed


def test_predictions():
    """모델 예측 테스트"""
    print("\n" + "="*60)
    print("모델 예측 테스트")
    print("="*60)
    
    # 1. COGS 예측 테스트
    print("\n📊 [whatif_cogs_model] 환율 변화에 따른 COGS 예측:")
    for fx in [1200, 1300, 1400]:
        result = run_query(
            f"SELECT fx_rate, cogs FROM mindsdb.whatif_cogs_model WHERE fx_rate = {fx}",
            f"FX_RATE = {fx}"
        )
        if result.get("data"):
            cogs = result["data"][0][1]
            print(f"   → 예측 COGS = {cogs:.2f}")
    
    # 2. Demand 예측 테스트
    print("\n📊 [whatif_demand_model] 가격/브랜드 변화에 따른 수요 예측:")
    test_cases = [
        (125, 50, 50),   # 기준
        (135, 50, 50),   # 가격 상승
        (125, 55, 55),   # 브랜드/충성도 상승
    ]
    for price, brand, loyalty in test_cases:
        result = run_query(
            f"""SELECT price, brand_equity, loyalty, demand 
                FROM mindsdb.whatif_demand_model 
                WHERE price = {price} AND brand_equity = {brand} AND loyalty = {loyalty}""",
            f"PRICE={price}, BRAND={brand}, LOYALTY={loyalty}"
        )
        if result.get("data"):
            demand = result["data"][0][3]
            print(f"   → 예측 수요 = {demand:.2f}")
    
    # 3. Brand 예측 테스트
    print("\n📊 [whatif_brand_model] 다요인 → 브랜드가치 예측:")
    test_cases = [
        (0.65, 0.06, 100, 0.01),   # 기준
        (0.75, 0.04, 120, 0.01),   # 좋은 상황
        (0.55, 0.08, 80, 0.03),    # 나쁜 상황
    ]
    for csat, refund, mkt, vol in test_cases:
        result = run_query(
            f"""SELECT csat, refund_rate, mkt_spend, price_volatility, brand_equity 
                FROM mindsdb.whatif_brand_model 
                WHERE csat = {csat} AND refund_rate = {refund} 
                AND mkt_spend = {mkt} AND price_volatility = {vol}""",
            f"CSAT={csat}, REFUND={refund}, MKT={mkt}"
        )
        if result.get("data"):
            brand = result["data"][0][4]
            print(f"   → 예측 브랜드가치 = {brand:.2f}")


def main():
    """메인 실행"""
    # 1. CSV 업로드
    if not upload_csv_to_files():
        print("\n⚠️ CSV 업로드 실패. 기존 파일이 있는지 확인합니다...")
    
    # 2. 데이터 확인
    if not verify_data():
        print("\n❌ 데이터 확인 실패. 종료합니다.")
        return
    
    # 3. 모델 생성
    models = create_models()
    
    # 4. 학습 완료 대기
    completed = wait_for_training(models, max_wait=120)
    
    # 5. 예측 테스트
    if completed:
        test_predictions()
    
    print("\n" + "="*60)
    print("✅ MindsDB 모델 설정 완료!")
    print("="*60)
    print("""
    📁 생성된 리소스:
       - 데이터: files.kpi_monthly (36개월 KPI 시계열)
       - 모델:
         - whatif_cogs_model (FX → COGS)
         - whatif_demand_model (Price/Brand/Loyalty → Demand)  
         - whatif_brand_model (CSAT/Refund/MKT/Vol → Brand)
         - whatif_profit_model (Price/Demand/COGS → Profit)
    
    💡 이제 test_mindsdb_simulation.py를 실행하여 
       MindsDB 모델을 활용한 시뮬레이션을 수행하세요.
    """)


if __name__ == "__main__":
    main()
