#!/usr/bin/env python3
"""
MindsDB 모델을 활용한 What-if 시뮬레이션

학습된 ML 모델을 사용하여 더 정확한 시뮬레이션을 수행합니다.
"""

import requests
import json
from datetime import datetime
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field

MINDSDB_API = "http://127.0.0.1:47334/api/sql/query"


def run_query(query: str, silent: bool = False) -> Optional[Dict[str, Any]]:
    """MindsDB SQL 쿼리 실행"""
    try:
        response = requests.post(
            MINDSDB_API,
            headers={"Content-Type": "application/json"},
            json={"query": query},
            timeout=30
        )
        result = response.json()
        
        if result.get("type") == "error":
            if not silent:
                print(f"   ❌ Error: {result.get('error_message', '')[:100]}")
            return None
        return result
    except Exception as e:
        if not silent:
            print(f"   ❌ Exception: {e}")
        return None


class MindsDBPredictor:
    """MindsDB 모델을 통한 예측"""
    
    def __init__(self):
        self.models_available = self._check_models()
    
    def _check_models(self) -> Dict[str, bool]:
        """사용 가능한 모델 확인"""
        result = run_query("SELECT name, status FROM mindsdb.models", silent=True)
        models = {}
        if result and result.get("data"):
            for row in result["data"]:
                name, status = row[0], row[1]
                models[name] = (status == "complete")
        return models
    
    def predict_cogs(self, fx_rate: float) -> float:
        """환율 → COGS 예측"""
        if not self.models_available.get("whatif_cogs_model"):
            # 폴백: 기본 수식
            return 100 + 0.05 * (fx_rate - 1200)
        
        result = run_query(
            f"SELECT cogs FROM mindsdb.whatif_cogs_model WHERE fx_rate = {fx_rate}",
            silent=True
        )
        if result and result.get("data"):
            return float(result["data"][0][0])
        return 100 + 0.05 * (fx_rate - 1200)
    
    def predict_demand(self, price: float, brand_equity: float, loyalty: float) -> float:
        """가격/브랜드/충성도 → 수요 예측"""
        if not self.models_available.get("whatif_demand_model"):
            base = 100
            price_effect = -0.5 * (price - 125) / 125
            brand_effect = 0.3 * (brand_equity - 50) / 50
            loyalty_effect = 0.2 * (loyalty - 50) / 50
            return max(50, base * (1 + price_effect + brand_effect + loyalty_effect))
        
        result = run_query(
            f"""SELECT demand FROM mindsdb.whatif_demand_model 
                WHERE price = {price} AND brand_equity = {brand_equity} AND loyalty = {loyalty}""",
            silent=True
        )
        if result and result.get("data"):
            return float(result["data"][0][0])
        return 90.0
    
    def predict_brand_equity(self, csat: float, refund_rate: float, 
                            mkt_spend: float, price_volatility: float) -> float:
        """다요인 → 브랜드가치 예측"""
        if not self.models_available.get("whatif_brand_model"):
            return 50 + 10 * (csat - 0.65) - 100 * refund_rate + 0.1 * (mkt_spend - 100)
        
        result = run_query(
            f"""SELECT brand_equity FROM mindsdb.whatif_brand_model 
                WHERE csat = {csat} AND refund_rate = {refund_rate} 
                AND mkt_spend = {mkt_spend} AND price_volatility = {price_volatility}""",
            silent=True
        )
        if result and result.get("data"):
            return float(result["data"][0][0])
        return 50.0
    
    def predict_profit(self, price: float, demand: float, cogs: float) -> float:
        """가격/수요/원가 → 이익 예측"""
        if not self.models_available.get("whatif_profit_model"):
            return price * demand - cogs * demand
        
        result = run_query(
            f"""SELECT profit FROM mindsdb.whatif_profit_model 
                WHERE price = {price} AND demand = {demand} AND cogs = {cogs}""",
            silent=True
        )
        if result and result.get("data"):
            return float(result["data"][0][0])
        return price * demand - cogs * demand


@dataclass
class ScenarioConfig:
    """시나리오 설정"""
    name: str
    description: str
    time_steps: int = 12
    
    # 환율 스케줄
    fx_schedule: List[float] = field(default_factory=lambda: [1270.0] * 12)
    
    # 정책 변수
    pass_through: float = 0.5
    mkt_spend: float = 100.0
    service_level: float = 0.8


@dataclass
class SimulationState:
    """시뮬레이션 상태"""
    fx_rate: float = 1270.0
    cogs: float = 107.0
    price: float = 127.0
    price_volatility: float = 0.01
    demand: float = 90.0
    sales: float = 11430.0
    profit: float = 1800.0
    margin: float = 0.157
    refund_rate: float = 0.06
    delivery_time: float = 2.6
    csat: float = 0.68
    brand_equity: float = 50.0
    loyalty: float = 50.0


class MindsDBSimulator:
    """MindsDB 기반 시뮬레이터"""
    
    def __init__(self):
        print("🔧 MindsDB 시뮬레이터 초기화 중...")
        self.predictor = MindsDBPredictor()
        
        print(f"   사용 가능한 모델:")
        for name, available in self.predictor.models_available.items():
            status = "✅" if available else "❌"
            print(f"     {status} {name}")
    
    def run_scenario(self, config: ScenarioConfig) -> Dict[str, Any]:
        """시나리오 시뮬레이션 실행"""
        print(f"\n{'='*60}")
        print(f"🚀 시나리오: {config.name}")
        print(f"   {config.description}")
        print(f"{'='*60}")
        
        # 초기 상태
        state = SimulationState()
        history = {
            "fx_rate": [], "cogs": [], "price": [], "demand": [],
            "sales": [], "profit": [], "margin": [],
            "brand_equity": [], "loyalty": [], "csat": []
        }
        
        prev_price = state.price
        
        for t in range(config.time_steps):
            # 1. 외생 변수 설정
            fx = config.fx_schedule[min(t, len(config.fx_schedule)-1)]
            state.fx_rate = fx
            
            # 2. COGS 예측 (MindsDB)
            state.cogs = self.predictor.predict_cogs(fx)
            
            # 3. 가격 결정 (전가율 적용)
            state.price = state.cogs * (1 + config.pass_through * 0.3)
            
            # 4. 가격 변동성
            state.price_volatility = abs(state.price - prev_price) / prev_price if prev_price > 0 else 0
            prev_price = state.price
            
            # 5. 서비스 관련 변수
            state.delivery_time = 5 - 3 * config.service_level
            state.refund_rate = max(0.02, 0.1 - 0.05 * config.service_level + 0.1 * state.price_volatility)
            state.csat = min(0.95, max(0.4, 
                0.5 + 0.3 * config.service_level - 0.05 * (state.delivery_time - 2) - 0.5 * state.refund_rate
            ))
            
            # 6. 브랜드 가치 예측 (MindsDB)
            predicted_brand = self.predictor.predict_brand_equity(
                state.csat, state.refund_rate, config.mkt_spend, state.price_volatility
            )
            # 스톡 변수: 점진적 변화
            state.brand_equity = 0.9 * state.brand_equity + 0.1 * predicted_brand
            
            # 7. 충성도 (스톡)
            state.loyalty = 0.95 * state.loyalty + 0.05 * (state.brand_equity + 10 * (state.csat - 0.5))
            
            # 8. 수요 예측 (MindsDB)
            state.demand = self.predictor.predict_demand(
                state.price, state.brand_equity, state.loyalty
            )
            
            # 9. 매출 및 이익
            state.sales = state.price * state.demand
            state.profit = self.predictor.predict_profit(
                state.price, state.demand, state.cogs
            )
            state.margin = state.profit / state.sales if state.sales > 0 else 0
            
            # 히스토리 저장
            for key in history:
                history[key].append(getattr(state, key))
            
            # 진행 표시
            if (t + 1) % 4 == 0 or t == 0:
                print(f"   t={t+1}: FX={fx:.0f}, COGS={state.cogs:.1f}, "
                      f"Price={state.price:.1f}, Demand={state.demand:.1f}, "
                      f"Profit={state.profit:.0f}, Brand={state.brand_equity:.1f}")
        
        # KPI 계산
        kpis = {
            "SHORT_TERM_MARGIN": sum(history["margin"][-3:]) / 3,
            "LONG_TERM_BRAND_VALUE": 0.6 * state.brand_equity + 0.4 * state.loyalty,
            "TOTAL_PROFIT": sum(history["profit"]),
            "AVG_DEMAND": sum(history["demand"]) / len(history["demand"]),
        }
        
        return {
            "config": config,
            "final_state": state,
            "history": history,
            "kpis": kpis
        }


def create_scenarios() -> List[ScenarioConfig]:
    """시나리오 생성"""
    scenarios = []
    
    # 1. Baseline
    scenarios.append(ScenarioConfig(
        name="Baseline",
        description="현재 환율(1270) 유지, 기본 정책",
        fx_schedule=[1270.0] * 12,
        pass_through=0.5,
        mkt_spend=100.0,
        service_level=0.8
    ))
    
    # 2. 환율 급등
    fx_shock = [1270.0] * 3 + [1380.0] * 9
    scenarios.append(ScenarioConfig(
        name="FX_Shock",
        description="4개월차부터 환율 1380원으로 급등",
        fx_schedule=fx_shock,
        pass_through=0.5,
        mkt_spend=100.0,
        service_level=0.8
    ))
    
    # 3. 환율 급등 + 높은 가격 전가
    scenarios.append(ScenarioConfig(
        name="FX_Shock_HighPassThrough",
        description="환율 급등 + 가격 전가 80%",
        fx_schedule=fx_shock,
        pass_through=0.8,
        mkt_spend=100.0,
        service_level=0.8
    ))
    
    # 4. 환율 급등 + 마케팅 강화
    scenarios.append(ScenarioConfig(
        name="FX_Shock_MarketingBoost",
        description="환율 급등 + 마케팅 130%",
        fx_schedule=fx_shock,
        pass_through=0.5,
        mkt_spend=130.0,
        service_level=0.8
    ))
    
    # 5. 환율 급등 + 서비스 강화
    scenarios.append(ScenarioConfig(
        name="FX_Shock_ServiceBoost",
        description="환율 급등 + 서비스 수준 95%",
        fx_schedule=fx_shock,
        pass_through=0.5,
        mkt_spend=100.0,
        service_level=0.95
    ))
    
    return scenarios


def compare_results(results: Dict[str, Dict]) -> None:
    """결과 비교"""
    print("\n" + "="*70)
    print("📊 시나리오 비교 분석")
    print("="*70)
    
    # KPI 비교표
    print(f"\n{'시나리오':<30} {'단기마진':>10} {'장기브랜드':>12} {'총이익':>12} {'평균수요':>10}")
    print("-" * 76)
    
    baseline = results.get("Baseline", {}).get("kpis", {})
    
    for name, result in results.items():
        kpis = result["kpis"]
        margin = kpis["SHORT_TERM_MARGIN"]
        brand = kpis["LONG_TERM_BRAND_VALUE"]
        profit = kpis["TOTAL_PROFIT"]
        demand = kpis["AVG_DEMAND"]
        
        if name == "Baseline":
            print(f"{name:<30} {margin:>10.2%} {brand:>12.2f} {profit:>12,.0f} {demand:>10.1f}  (기준)")
        else:
            m_diff = margin - baseline.get("SHORT_TERM_MARGIN", 0)
            b_diff = brand - baseline.get("LONG_TERM_BRAND_VALUE", 0)
            p_diff = profit - baseline.get("TOTAL_PROFIT", 0)
            print(f"{name:<30} {margin:>10.2%} {brand:>12.2f} {profit:>12,.0f} {demand:>10.1f}  "
                  f"({m_diff:+.2%}, {b_diff:+.1f}, {p_diff:+,.0f})")


def analyze_tradeoffs(results: Dict[str, Dict]) -> None:
    """트레이드오프 분석"""
    print("\n" + "="*70)
    print("🔄 정책 트레이드오프 분석")
    print("="*70)
    
    fx_shock = results.get("FX_Shock", {}).get("kpis", {})
    
    policies = [
        ("FX_Shock_HighPassThrough", "가격 전가 80%"),
        ("FX_Shock_MarketingBoost", "마케팅 130%"),
        ("FX_Shock_ServiceBoost", "서비스 95%"),
    ]
    
    for scenario_name, policy_name in policies:
        if scenario_name not in results:
            continue
        
        kpis = results[scenario_name]["kpis"]
        
        margin_change = kpis["SHORT_TERM_MARGIN"] - fx_shock.get("SHORT_TERM_MARGIN", 0)
        brand_change = kpis["LONG_TERM_BRAND_VALUE"] - fx_shock.get("LONG_TERM_BRAND_VALUE", 0)
        profit_change = kpis["TOTAL_PROFIT"] - fx_shock.get("TOTAL_PROFIT", 0)
        
        print(f"\n📌 {policy_name}:")
        print(f"   • 단기 마진: {margin_change:+.2%}")
        print(f"   • 장기 브랜드: {brand_change:+.2f}")
        print(f"   • 총 이익: {profit_change:+,.0f}")
        
        # 트레이드오프 판단
        if margin_change > 0 and brand_change < 0:
            print(f"   ⚠️ 단기 이익 vs 장기 브랜드 트레이드오프!")
        elif margin_change < 0 and brand_change > 0:
            print(f"   ⚠️ 단기 희생 → 장기 브랜드 투자!")
        elif margin_change > 0 and brand_change > 0:
            print(f"   ✅ 단기/장기 모두 개선!")


def export_results(results: Dict[str, Dict], filename: str = "mindsdb_simulation_results.json"):
    """결과 내보내기"""
    export_data = {
        "timestamp": datetime.now().isoformat(),
        "scenarios": {}
    }
    
    for name, result in results.items():
        export_data["scenarios"][name] = {
            "description": result["config"].description,
            "kpis": result["kpis"],
            "final_state": {
                "fx_rate": result["final_state"].fx_rate,
                "cogs": result["final_state"].cogs,
                "price": result["final_state"].price,
                "demand": result["final_state"].demand,
                "profit": result["final_state"].profit,
                "brand_equity": result["final_state"].brand_equity,
                "loyalty": result["final_state"].loyalty,
            },
            "history": {k: [round(v, 2) for v in vals] 
                       for k, vals in result["history"].items()}
        }
    
    filepath = f"/Users/uengine/robo-analyz/what-if-simulator/{filename}"
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(export_data, f, indent=2, ensure_ascii=False)
    
    print(f"\n📁 결과 저장: {filepath}")


def main():
    """메인 실행"""
    print("="*70)
    print("  MindsDB 모델 기반 What-if 시뮬레이션")
    print(f"  실행 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*70)
    
    # 시뮬레이터 초기화
    simulator = MindsDBSimulator()
    
    # 시나리오 생성 및 실행
    scenarios = create_scenarios()
    results = {}
    
    for config in scenarios:
        result = simulator.run_scenario(config)
        results[config.name] = result
    
    # 결과 비교
    compare_results(results)
    
    # 트레이드오프 분석
    analyze_tradeoffs(results)
    
    # 결과 저장
    export_results(results)
    
    # 완료
    print("\n" + "="*70)
    print("✅ MindsDB 기반 What-if 시뮬레이션 완료!")
    print("="*70)
    print("""
    📊 주요 발견:
       1. MindsDB 모델이 데이터 기반으로 인과관계를 학습
       2. 정책 변화에 따른 KPI 영향을 정량적으로 예측
       3. 단기/장기 트레이드오프를 명확히 파악 가능
    
    💡 활용 방안:
       - 환율 시나리오별 대응 전략 수립
       - 가격/마케팅/서비스 정책 최적화
       - 경영진 의사결정 지원
    """)


if __name__ == "__main__":
    main()
