"""
환율 → 매출 예측 TTM 테스트

IBM Granite TTM 모델을 사용하여 환율 변화가 매출에 미치는 영향을 예측합니다.
"""

import torch
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

# TTM 모델 로드
try:
    from tsfm_public.models.tinytimemixer import TinyTimeMixerForPrediction
except ImportError:
    from granite_tsfm.models.tinytimemixer import TinyTimeMixerForPrediction


def generate_exchange_rate_sales_data(num_months=100, seed=42):
    """환율과 매출의 인과관계 시뮬레이션 데이터 생성"""
    np.random.seed(seed)
    
    # 시간 인덱스 (월별)
    months = pd.date_range(start='2016-01-01', periods=num_months, freq='M')
    
    # 환율 시계열 (USD/KRW) - 트렌드 + 계절성 + 노이즈
    trend = np.linspace(1100, 1350, num_months)
    seasonal = 50 * np.sin(2 * np.pi * np.arange(num_months) / 12)  # 연간 주기
    noise = np.random.randn(num_months) * 20
    exchange_rate = trend + seasonal + noise
    
    # 수입 비용 = 환율 × 수입량 × 가격변동
    import_volume = 1000 + np.random.randn(num_months) * 50
    import_cost = exchange_rate * import_volume / 1000 + np.random.randn(num_months) * 100
    
    # 제품 원가 = 수입 비용 + 생산비용
    production_cost = 500 + np.random.randn(num_months) * 30
    product_cost = import_cost + production_cost
    
    # 매출 = 기본 매출 - 원가 영향 + 시장 수요
    base_sales = 2000000
    market_demand = 100000 * np.sin(2 * np.pi * np.arange(num_months) / 12) + 50000  # 계절성
    sales_revenue = base_sales - product_cost * 500 + market_demand + np.random.randn(num_months) * 50000
    
    # 최종 수익 = 매출 - 비용
    final_profit = sales_revenue - product_cost * 800 + np.random.randn(num_months) * 30000
    
    df = pd.DataFrame({
        'month': months,
        'exchange_rate': exchange_rate,
        'import_cost': import_cost,
        'product_cost': product_cost,
        'sales_revenue': sales_revenue,
        'final_profit': final_profit
    })
    
    return df


def test_ttm_prediction():
    """TTM 모델로 환율 → 매출 예측 테스트"""
    print("=" * 70)
    print("🔮 IBM Granite TTM - 환율 → 매출 예측 테스트")
    print("=" * 70)
    
    # 1. 데이터 생성
    print("\n📊 1. 환율-매출 인과관계 시뮬레이션 데이터 생성...")
    df = generate_exchange_rate_sales_data(num_months=100)
    print(f"   - 데이터 행 수: {len(df)}")
    print(f"   - 기간: {df['month'].min()} ~ {df['month'].max()}")
    print(f"\n   데이터 샘플:")
    print(df.tail(10).to_string(index=False))
    
    # 2. TTM 모델 로드
    print("\n🧠 2. IBM Granite TTM 모델 로드...")
    model_name = "ibm-granite/granite-timeseries-ttm-v1"
    model = TinyTimeMixerForPrediction.from_pretrained(model_name)
    model.eval()
    
    config = model.config
    context_length = getattr(config, 'context_length', 512)
    prediction_length = getattr(config, 'prediction_length', 96)
    
    print(f"   - 모델: {model_name}")
    print(f"   - Context Length: {context_length}")
    print(f"   - Prediction Length: {prediction_length}")
    
    # 3. 데이터 준비 (context_length 조정)
    print("\n📈 3. 데이터 전처리...")
    
    # 데이터가 context_length보다 적으면 조정
    actual_context = min(context_length, len(df) - 10)
    actual_prediction = min(prediction_length, 10)
    
    # 환율 데이터로 매출 예측
    target_col = 'sales_revenue'
    feature_cols = ['exchange_rate']
    
    # 입력 데이터 (정규화)
    train_end = len(df) - actual_prediction
    input_data = df[target_col].values[:train_end]
    
    # 패딩 (context_length보다 데이터가 적으면)
    if len(input_data) < context_length:
        padding = np.full(context_length - len(input_data), input_data[0])
        input_data = np.concatenate([padding, input_data])
    else:
        input_data = input_data[-context_length:]
    
    # 텐서로 변환 (batch_size, context_length, num_channels)
    input_tensor = torch.tensor(input_data, dtype=torch.float32).unsqueeze(0).unsqueeze(-1)
    print(f"   - 입력 텐서 형태: {input_tensor.shape}")
    
    # 4. 예측 수행
    print("\n🔮 4. TTM 예측 수행...")
    with torch.no_grad():
        output = model(past_values=input_tensor)
        
        if hasattr(output, 'prediction_outputs'):
            predictions = output.prediction_outputs.numpy()[0, :, 0]
        else:
            predictions = output.numpy()[0, :, 0]
    
    # 실제 테스트 데이터
    actual_values = df[target_col].values[train_end:]
    pred_values = predictions[:len(actual_values)]
    
    print(f"   - 예측 완료! 예측 길이: {len(pred_values)}")
    
    # 5. 메트릭 계산
    print("\n📉 5. 성능 평가...")
    
    # R² 계산
    ss_res = np.sum((actual_values - pred_values) ** 2)
    ss_tot = np.sum((actual_values - np.mean(actual_values)) ** 2)
    r2 = 1 - ss_res / ss_tot if ss_tot > 0 else 0
    
    # MAPE 계산
    mape = np.mean(np.abs((actual_values - pred_values) / actual_values)) * 100
    
    # RMSE 계산
    rmse = np.sqrt(np.mean((actual_values - pred_values) ** 2))
    
    print(f"   - R² Score: {r2:.4f} ({r2*100:.1f}%)")
    print(f"   - MAPE: {mape:.2f}%")
    print(f"   - RMSE: {rmse:,.0f}")
    
    # 6. 선형 회귀와 비교
    print("\n⚖️ 6. 온톨로지 모델 (선형 회귀)과 비교...")
    from sklearn.linear_model import LinearRegression
    from sklearn.metrics import r2_score
    
    X_train = df['exchange_rate'].values[:train_end].reshape(-1, 1)
    y_train = df[target_col].values[:train_end]
    X_test = df['exchange_rate'].values[train_end:].reshape(-1, 1)
    y_test = df[target_col].values[train_end:]
    
    lr_model = LinearRegression()
    lr_model.fit(X_train, y_train)
    lr_preds = lr_model.predict(X_test)
    lr_r2 = r2_score(y_test, lr_preds)
    lr_mape = np.mean(np.abs((y_test - lr_preds) / y_test)) * 100
    
    print(f"\n   ┌─────────────────────────────────────────────┐")
    print(f"   │        🔬 온톨로지 모델 (선형 회귀)           │")
    print(f"   │  R²: {lr_r2:.4f} ({lr_r2*100:.1f}%)   MAPE: {lr_mape:.2f}%  │")
    print(f"   ├─────────────────────────────────────────────┤")
    print(f"   │        🧠 IBM Granite TTM                   │")
    print(f"   │  R²: {r2:.4f} ({r2*100:.1f}%)   MAPE: {mape:.2f}%  │")
    print(f"   └─────────────────────────────────────────────┘")
    
    winner = "TTM" if r2 > lr_r2 else "온톨로지 모델"
    print(f"\n   🏆 승자: {winner}")
    
    # 7. 시각화
    print("\n📊 7. 결과 시각화...")
    
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    
    # 환율 시계열
    ax1 = axes[0, 0]
    ax1.plot(df['month'], df['exchange_rate'], 'b-', label='환율 (USD/KRW)')
    ax1.set_title('💱 환율 시계열')
    ax1.set_xlabel('월')
    ax1.set_ylabel('환율')
    ax1.legend()
    ax1.grid(True, alpha=0.3)
    
    # 매출 시계열 + 예측
    ax2 = axes[0, 1]
    ax2.plot(df['month'], df['sales_revenue'], 'g-', label='실제 매출', alpha=0.7)
    test_months = df['month'].values[train_end:]
    ax2.plot(test_months, pred_values, 'r--', label='TTM 예측', linewidth=2)
    ax2.plot(test_months, lr_preds, 'orange', label='선형회귀 예측', linewidth=2, linestyle=':')
    ax2.axvline(x=df['month'].values[train_end], color='gray', linestyle='--', label='예측 시작')
    ax2.set_title('📈 매출 예측 비교')
    ax2.set_xlabel('월')
    ax2.set_ylabel('매출')
    ax2.legend()
    ax2.grid(True, alpha=0.3)
    
    # 예측 vs 실제 (TTM)
    ax3 = axes[1, 0]
    ax3.scatter(actual_values, pred_values, alpha=0.7, color='red')
    min_val = min(actual_values.min(), pred_values.min())
    max_val = max(actual_values.max(), pred_values.max())
    ax3.plot([min_val, max_val], [min_val, max_val], 'k--', label='완벽한 예측')
    ax3.set_title(f'🧠 TTM: 예측 vs 실제 (R²={r2:.3f})')
    ax3.set_xlabel('실제값')
    ax3.set_ylabel('예측값')
    ax3.legend()
    ax3.grid(True, alpha=0.3)
    
    # 예측 vs 실제 (선형회귀)
    ax4 = axes[1, 1]
    ax4.scatter(y_test, lr_preds, alpha=0.7, color='orange')
    ax4.plot([min_val, max_val], [min_val, max_val], 'k--', label='완벽한 예측')
    ax4.set_title(f'🔬 선형회귀: 예측 vs 실제 (R²={lr_r2:.3f})')
    ax4.set_xlabel('실제값')
    ax4.set_ylabel('예측값')
    ax4.legend()
    ax4.grid(True, alpha=0.3)
    
    plt.tight_layout()
    output_path = '/Users/uengine/robo-analyz/what-if-simulator/ttm_exchange_rate_prediction.png'
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    print(f"   - 결과 저장: {output_path}")
    plt.close()
    
    print("\n" + "=" * 70)
    print("✅ 테스트 완료!")
    print("=" * 70)
    
    return {
        'ttm': {'r2': r2, 'mape': mape, 'rmse': rmse},
        'linear_regression': {'r2': lr_r2, 'mape': lr_mape},
        'winner': winner
    }


if __name__ == "__main__":
    result = test_ttm_prediction()
    print(f"\n📋 최종 결과: {result}")
