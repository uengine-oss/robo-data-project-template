#!/usr/bin/env python3
"""
시뮬레이션용 샘플 데이터 생성

MindsDB에 연결된 MySQL에 KPI 시계열 데이터를 생성합니다.
"""

import requests
import json
import random
import math
from datetime import datetime, timedelta
from typing import List, Dict, Any

MINDSDB_API = "http://127.0.0.1:47334/api/sql/query"


def run_query(query: str, description: str = "") -> Dict[str, Any]:
    """MindsDB SQL 쿼리 실행"""
    if description:
        print(f"🔹 {description}")
    
    try:
        response = requests.post(
            MINDSDB_API,
            headers={"Content-Type": "application/json"},
            json={"query": query},
            timeout=60
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


def generate_kpi_data(months: int = 36) -> List[Dict]:
    """36개월치 KPI 시계열 데이터 생성
    
    실제적인 인과관계를 반영한 데이터 생성:
    - FX_RATE 변화 → COGS 변화 → PRICE 조정 → DEMAND 변화
    - 마케팅/서비스 → 브랜드/충성도 → 수요
    """
    data = []
    random.seed(42)
    
    # 초기값
    fx_rate = 1150.0
    cogs = 100.0
    price = 115.0
    demand = 100.0
    brand_equity = 50.0
    loyalty = 60.0
    csat = 0.75
    mkt_spend = 100.0
    service_level = 0.8
    pass_through = 0.5
    
    base_date = datetime(2023, 1, 1)
    
    for month in range(months):
        current_date = base_date + timedelta(days=30 * month)
        
        # 외생 변수: 환율 랜덤워크 + 트렌드 + 계절성
        fx_shock = random.gauss(0, 20)
        fx_trend = 2.5  # 월 평균 2.5원 상승 추세
        fx_seasonal = 30 * math.sin(2 * math.pi * month / 12)  # 계절성
        fx_rate = max(1000, min(1500, fx_rate + fx_shock + fx_trend + fx_seasonal))
        
        # 정책 변수: 가끔 변경
        if month == 12:  # 1년 후 마케팅 증가
            mkt_spend = 120.0
        if month == 24:  # 2년 후 가격 전가율 조정
            pass_through = 0.6
        
        # 서비스 수준 약간의 변동
        service_level = 0.75 + 0.1 * math.sin(2 * math.pi * month / 6) + random.gauss(0, 0.02)
        service_level = max(0.6, min(0.95, service_level))
        
        # COGS = f(FX_RATE)
        cogs_base = 100.0
        cogs = cogs_base + 0.05 * (fx_rate - 1150) + random.gauss(0, 2)
        cogs = max(80, min(150, cogs))
        
        # PRICE = f(COGS, PASS_THROUGH)
        price = cogs * (1 + pass_through * 0.3) + random.gauss(0, 1)
        price = max(100, min(180, price))
        
        # 가격 변동성 (이전 가격 대비)
        if month > 0:
            price_volatility = abs(price - data[-1]["price"]) / data[-1]["price"]
        else:
            price_volatility = 0
        
        # 환불율 = f(SERVICE_LEVEL, PRICE_VOLATILITY)
        refund_rate = 0.1 - 0.05 * service_level + 0.1 * price_volatility + random.gauss(0, 0.01)
        refund_rate = max(0.01, min(0.15, refund_rate))
        
        # 배송 시간 = f(SERVICE_LEVEL)
        delivery_time = 5 - 3 * service_level + random.gauss(0, 0.3)
        delivery_time = max(1, min(7, delivery_time))
        
        # CSAT = f(SERVICE_LEVEL, DELIVERY_TIME, REFUND_RATE)
        csat = 0.5 + 0.3 * service_level - 0.05 * (delivery_time - 2) - 0.5 * refund_rate
        csat += random.gauss(0, 0.03)
        csat = max(0.3, min(0.95, csat))
        
        # BRAND_EQUITY = Stock (누적/감가상각)
        # 긍정: CSAT, MKT_SPEND / 부정: REFUND_RATE, PRICE_VOLATILITY
        brand_delta = (
            -0.02 * brand_equity  # 자연 감가상각 2%
            + 0.1 * (csat - 0.5)  # CSAT 기여
            + 0.02 * (mkt_spend - 100) / 100 * 10  # 마케팅 기여
            - 10 * refund_rate  # 환불율 피해
            - 5 * price_volatility  # 가격 변동성 피해
            + random.gauss(0, 0.5)
        )
        brand_equity = max(20, min(80, brand_equity + brand_delta))
        
        # LOYALTY = Stock
        loyalty_delta = (
            -0.05 * loyalty  # 5% 감가상각
            + 0.05 * (brand_equity - 50)
            + 10 * (csat - 0.5)
            + random.gauss(0, 0.5)
        )
        loyalty = max(30, min(90, loyalty + loyalty_delta))
        
        # DEMAND = f(PRICE, BRAND_EQUITY, LOYALTY)
        base_demand = 100
        price_effect = -0.5 * (price - 115) / 115
        brand_effect = 0.3 * (brand_equity - 50) / 50
        loyalty_effect = 0.2 * (loyalty - 50) / 50
        demand = base_demand * (1 + price_effect + brand_effect + loyalty_effect)
        demand += random.gauss(0, 3)
        demand = max(50, min(150, demand))
        
        # SALES = PRICE * DEMAND
        sales = price * demand
        
        # PROFIT = SALES - COGS * DEMAND
        profit = sales - cogs * demand
        
        # MARGIN = PROFIT / SALES
        margin = profit / sales if sales > 0 else 0
        
        # 데이터 레코드
        record = {
            "year_month": current_date.strftime("%Y-%m"),
            "month_num": month + 1,
            "fx_rate": round(fx_rate, 2),
            "pass_through": round(pass_through, 2),
            "mkt_spend": round(mkt_spend, 2),
            "service_level": round(service_level, 3),
            "cogs": round(cogs, 2),
            "price": round(price, 2),
            "price_volatility": round(price_volatility, 4),
            "demand": round(demand, 2),
            "sales": round(sales, 2),
            "profit": round(profit, 2),
            "margin": round(margin, 4),
            "refund_rate": round(refund_rate, 4),
            "delivery_time": round(delivery_time, 2),
            "csat": round(csat, 4),
            "brand_equity": round(brand_equity, 2),
            "loyalty": round(loyalty, 2),
        }
        data.append(record)
    
    return data


def create_table_and_insert_data():
    """MySQL에 테이블 생성 및 데이터 삽입"""
    print("\n" + "="*60)
    print("What-if Simulator 샘플 데이터 생성")
    print("="*60)
    
    # 1. 데이터 생성
    print("\n📊 36개월치 KPI 데이터 생성 중...")
    data = generate_kpi_data(36)
    print(f"   ✅ {len(data)}개 레코드 생성 완료")
    
    # 2. 테이블 삭제 (있으면)
    run_query(
        "DROP TABLE IF EXISTS mysql.kpi_monthly",
        "기존 테이블 삭제 시도"
    )
    
    # 3. 테이블 생성
    create_table_sql = """
    CREATE TABLE mysql.kpi_monthly (
        id INT AUTO_INCREMENT PRIMARY KEY,
        year_month VARCHAR(7),
        month_num INT,
        fx_rate DECIMAL(10,2),
        pass_through DECIMAL(5,2),
        mkt_spend DECIMAL(10,2),
        service_level DECIMAL(5,3),
        cogs DECIMAL(10,2),
        price DECIMAL(10,2),
        price_volatility DECIMAL(10,4),
        demand DECIMAL(10,2),
        sales DECIMAL(15,2),
        profit DECIMAL(15,2),
        margin DECIMAL(10,4),
        refund_rate DECIMAL(10,4),
        delivery_time DECIMAL(5,2),
        csat DECIMAL(5,4),
        brand_equity DECIMAL(10,2),
        loyalty DECIMAL(10,2)
    )
    """
    run_query(create_table_sql, "kpi_monthly 테이블 생성")
    
    # 4. 데이터 삽입
    print("\n📝 데이터 삽입 중...")
    for i, record in enumerate(data):
        insert_sql = f"""
        INSERT INTO mysql.kpi_monthly 
        (year_month, month_num, fx_rate, pass_through, mkt_spend, service_level,
         cogs, price, price_volatility, demand, sales, profit, margin,
         refund_rate, delivery_time, csat, brand_equity, loyalty)
        VALUES (
            '{record["year_month"]}', {record["month_num"]}, {record["fx_rate"]},
            {record["pass_through"]}, {record["mkt_spend"]}, {record["service_level"]},
            {record["cogs"]}, {record["price"]}, {record["price_volatility"]},
            {record["demand"]}, {record["sales"]}, {record["profit"]}, {record["margin"]},
            {record["refund_rate"]}, {record["delivery_time"]}, {record["csat"]},
            {record["brand_equity"]}, {record["loyalty"]}
        )
        """
        result = requests.post(MINDSDB_API, json={"query": insert_sql}).json()
        if result.get("type") == "error":
            print(f"   ❌ Insert failed at row {i+1}: {result.get('error_message', '')[:100]}")
            break
        if (i + 1) % 12 == 0:
            print(f"   ... {i+1}/{len(data)} 레코드 삽입됨")
    
    print(f"   ✅ 총 {len(data)}개 레코드 삽입 완료")
    
    # 5. 검증
    result = run_query(
        "SELECT * FROM mysql.kpi_monthly ORDER BY month_num LIMIT 5",
        "데이터 검증 (처음 5개 레코드)"
    )
    if result.get("data"):
        print("\n   📋 샘플 데이터:")
        cols = result.get("column_names", [])
        for row in result["data"][:3]:
            print(f"      {dict(zip(cols[:6], row[:6]))}")
    
    return data


def create_mindsdb_models():
    """MindsDB ML 모델 생성"""
    print("\n" + "="*60)
    print("MindsDB ML 모델 생성")
    print("="*60)
    
    models = [
        {
            "name": "whatif_cogs_model",
            "target": "cogs",
            "features": "fx_rate",
            "description": "환율 → 매출원가 예측 모델"
        },
        {
            "name": "whatif_demand_model",
            "target": "demand",
            "features": "price, brand_equity, loyalty",
            "description": "가격/브랜드 → 수요 예측 모델"
        },
        {
            "name": "whatif_brand_model",
            "target": "brand_equity",
            "features": "csat, refund_rate, mkt_spend, price_volatility",
            "description": "다요인 → 브랜드 가치 예측 모델"
        },
    ]
    
    for model in models:
        print(f"\n📊 {model['description']}")
        
        # 기존 모델 삭제
        run_query(
            f"DROP MODEL IF EXISTS mindsdb.{model['name']}",
            f"기존 모델 삭제: {model['name']}"
        )
        
        # 모델 생성
        create_sql = f"""
        CREATE MODEL mindsdb.{model['name']}
        FROM mysql (
            SELECT {model['features']}, {model['target']}
            FROM kpi_monthly
        )
        PREDICT {model['target']}
        """
        
        result = run_query(create_sql, f"모델 생성: {model['name']}")
        
        if result.get("type") != "error":
            print(f"   ⏳ 모델 학습이 백그라운드에서 진행됩니다...")
    
    # 모델 상태 확인
    print("\n📋 모델 학습 상태 확인...")
    import time
    for _ in range(3):
        time.sleep(2)
        result = run_query("SHOW MODELS", "현재 모델 목록")
        if result.get("data"):
            for row in result["data"]:
                if "whatif" in str(row[0]):
                    print(f"   - {row[0]}: {row[1] if len(row) > 1 else 'unknown'}")


def test_predictions():
    """모델 예측 테스트"""
    print("\n" + "="*60)
    print("모델 예측 테스트")
    print("="*60)
    
    # COGS 예측 테스트
    print("\n📊 환율 변화에 따른 COGS 예측:")
    for fx in [1150, 1250, 1350]:
        result = run_query(
            f"SELECT fx_rate, cogs FROM mindsdb.whatif_cogs_model WHERE fx_rate = {fx}",
            f"FX_RATE={fx} 일 때 COGS 예측"
        )
        if result.get("data"):
            print(f"   → FX_RATE={fx}: COGS = {result['data'][0][1]}")
    
    # Demand 예측 테스트
    print("\n📊 가격/브랜드 변화에 따른 수요 예측:")
    test_cases = [
        (115, 50, 60),   # 기준
        (125, 50, 60),   # 가격 상승
        (115, 60, 70),   # 브랜드/충성도 상승
    ]
    for price, brand, loyalty in test_cases:
        result = run_query(
            f"""SELECT price, brand_equity, loyalty, demand 
                FROM mindsdb.whatif_demand_model 
                WHERE price = {price} AND brand_equity = {brand} AND loyalty = {loyalty}""",
            f"PRICE={price}, BRAND={brand}, LOYALTY={loyalty}"
        )
        if result.get("data"):
            print(f"   → 예측 수요 = {result['data'][0][3]}")


def main():
    """메인 실행"""
    # 1. 테이블 및 데이터 생성
    create_table_and_insert_data()
    
    # 2. MindsDB 모델 생성
    create_mindsdb_models()
    
    # 3. 예측 테스트 (모델 학습 완료 후)
    print("\n" + "="*60)
    print("✅ 샘플 데이터 및 모델 설정 완료!")
    print("="*60)
    print("""
    📁 생성된 리소스:
       - MySQL 테이블: mysql.kpi_monthly (36개월 KPI 데이터)
       - MindsDB 모델:
         - whatif_cogs_model (FX → COGS)
         - whatif_demand_model (Price/Brand → Demand)
         - whatif_brand_model (다요인 → Brand)
    
    💡 모델 학습에 약간의 시간이 필요합니다.
       학습 완료 후 test_mindsdb_simulation.py를 실행하세요.
    """)


if __name__ == "__main__":
    main()
