"""
Model Validation Engine
=======================

추정된 인과관계 함수와 실제 데이터의 일치도를 검증합니다.

주요 기능:
1. 추정 함수(회귀/MindsDB) vs 실제 데이터 비교
2. Hold-out 샘플링을 통한 과적합 방지 검증
3. 잔차 분석 및 예측 오차 평가
4. MindsDB 모델 예측값 vs 실제값 비교

Author: AI Assistant
Created: 2026-01-24
"""

import json
import asyncio
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

# MindsDB 연동
import requests


@dataclass
class ValidationResult:
    """단일 Edge 검증 결과"""
    edge_id: str
    source: str
    target: str
    
    # 회귀 함수 정보
    formula: str
    slope: float
    intercept: float
    
    # 검증 지표
    r_squared: float           # 결정계수
    rmse: float               # 평균 제곱근 오차
    mae: float                # 평균 절대 오차
    mape: float               # 평균 절대 백분율 오차 (%)
    
    # 샘플별 결과
    train_r2: float = 0.0
    test_r2: float = 0.0      # Hold-out 테스트 R²
    
    # 잔차 분석
    residual_mean: float = 0.0
    residual_std: float = 0.0
    
    # 판정
    is_valid: bool = True
    validation_notes: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        return {
            'edge_id': self.edge_id,
            'source': self.source,
            'target': self.target,
            'formula': self.formula,
            'metrics': {
                'r_squared': round(self.r_squared, 4),
                'rmse': round(self.rmse, 4),
                'mae': round(self.mae, 4),
                'mape': round(self.mape, 2),
                'train_r2': round(self.train_r2, 4),
                'test_r2': round(self.test_r2, 4),
            },
            'residuals': {
                'mean': round(self.residual_mean, 4),
                'std': round(self.residual_std, 4),
            },
            'is_valid': self.is_valid,
            'notes': self.validation_notes
        }


@dataclass
class MindsDBValidationResult:
    """MindsDB 모델 검증 결과"""
    model_name: str
    target_column: str
    
    # 예측 vs 실제
    predictions: List[float]
    actuals: List[float]
    
    # 검증 지표
    r_squared: float
    rmse: float
    mae: float
    mape: float
    
    # 샘플 정보
    sample_size: int
    
    def to_dict(self) -> Dict:
        return {
            'model_name': self.model_name,
            'target_column': self.target_column,
            'sample_size': self.sample_size,
            'metrics': {
                'r_squared': round(self.r_squared, 4),
                'rmse': round(self.rmse, 4),
                'mae': round(self.mae, 4),
                'mape': round(self.mape, 2),
            }
        }


class ModelValidationEngine:
    """
    모델 검증 엔진
    
    추정된 인과관계 함수가 실제 데이터를 얼마나 잘 설명하는지 검증합니다.
    """
    
    def __init__(self, 
                 mindsdb_url: str = "http://127.0.0.1:47334",
                 test_ratio: float = 0.2,
                 random_seed: int = 42):
        """
        Args:
            mindsdb_url: MindsDB HTTP API URL
            test_ratio: Hold-out 테스트 데이터 비율 (기본 20%)
            random_seed: 재현성을 위한 랜덤 시드
        """
        self.mindsdb_url = mindsdb_url
        self.test_ratio = test_ratio
        self.random_seed = random_seed
        np.random.seed(random_seed)
        
        self.validation_results: List[ValidationResult] = []
        self.mindsdb_results: List[MindsDBValidationResult] = []
        
    def load_data(self, filepath: str) -> pd.DataFrame:
        """데이터 로드"""
        df = pd.read_csv(filepath)
        exclude_cols = ['year_month', 'month_num']
        numeric_cols = [col for col in df.columns if col not in exclude_cols]
        return df[numeric_cols]
    
    def load_influence_functions(self, filepath: str) -> List[Dict]:
        """추정된 영향 함수 로드"""
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data.get('functions', [])
    
    def train_test_split(self, data: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """
        시계열 데이터 분할 (후반부를 테스트 데이터로)
        
        시계열에서는 랜덤 분할 대신 시간 순서대로 분할해야 합니다.
        """
        n = len(data)
        split_idx = int(n * (1 - self.test_ratio))
        
        train_data = data.iloc[:split_idx].copy()
        test_data = data.iloc[split_idx:].copy()
        
        print(f"   데이터 분할: 학습 {len(train_data)}행, 테스트 {len(test_data)}행")
        
        return train_data, test_data
    
    def validate_edge_function(self,
                                data: pd.DataFrame,
                                func: Dict) -> ValidationResult:
        """
        단일 Edge 함수 검증
        
        Args:
            data: 전체 데이터
            func: 추정된 함수 정보 (source, target, slope, intercept)
        """
        source = func['source']
        target = func['target']
        slope = func['params']['slope']
        intercept = func['params']['intercept']
        
        if source not in data.columns or target not in data.columns:
            return ValidationResult(
                edge_id=f"{source}_to_{target}",
                source=source,
                target=target,
                formula=f"{target} = {slope} * {source} + {intercept}",
                slope=slope,
                intercept=intercept,
                r_squared=0,
                rmse=999,
                mae=999,
                mape=999,
                is_valid=False,
                validation_notes=["데이터에 해당 컬럼 없음"]
            )
        
        # 데이터 분할
        train_data, test_data = self.train_test_split(data)
        
        # 전체 데이터 예측
        X = data[source].values
        y_actual = data[target].values
        y_pred = slope * X + intercept
        
        # 전체 지표 계산
        r_squared = 1 - np.sum((y_actual - y_pred)**2) / np.sum((y_actual - np.mean(y_actual))**2)
        rmse = np.sqrt(np.mean((y_actual - y_pred)**2))
        mae = np.mean(np.abs(y_actual - y_pred))
        
        # MAPE (0 제외)
        non_zero_mask = y_actual != 0
        if np.any(non_zero_mask):
            mape = np.mean(np.abs((y_actual[non_zero_mask] - y_pred[non_zero_mask]) / y_actual[non_zero_mask])) * 100
        else:
            mape = 0
        
        # 학습 데이터 R²
        X_train = train_data[source].values
        y_train = train_data[target].values
        y_train_pred = slope * X_train + intercept
        train_ss_res = np.sum((y_train - y_train_pred)**2)
        train_ss_tot = np.sum((y_train - np.mean(y_train))**2)
        train_r2 = 1 - train_ss_res / train_ss_tot if train_ss_tot > 0 else 0
        
        # 테스트 데이터 R² (Out-of-sample)
        X_test = test_data[source].values
        y_test = test_data[target].values
        y_test_pred = slope * X_test + intercept
        test_ss_res = np.sum((y_test - y_test_pred)**2)
        test_ss_tot = np.sum((y_test - np.mean(y_test))**2)
        test_r2 = 1 - test_ss_res / test_ss_tot if test_ss_tot > 0 else 0
        
        # 잔차 분석
        residuals = y_actual - y_pred
        residual_mean = np.mean(residuals)
        residual_std = np.std(residuals)
        
        # 검증 판정
        notes = []
        is_valid = True
        
        # R² 판정
        if r_squared < 0.1:
            notes.append("⚠️ R² < 0.1: 관계가 매우 약함")
            is_valid = False
        elif r_squared < 0.3:
            notes.append("⚡ R² < 0.3: 관계가 약함, 다른 요인 검토 필요")
        elif r_squared > 0.95:
            notes.append("⚠️ R² > 0.95: 과적합 가능성 검토")
            
        # 과적합 검사 (Train R² >> Test R²)
        if train_r2 - test_r2 > 0.3:
            notes.append("🔴 과적합 의심: Train R² - Test R² > 0.3")
            is_valid = False
        elif train_r2 - test_r2 > 0.15:
            notes.append("🟡 약한 과적합: Train R² - Test R² > 0.15")
            
        # 잔차 정규성 검사
        if abs(residual_mean) > 0.1 * np.std(y_actual):
            notes.append("🟡 잔차 평균이 0에서 벗어남 (편향 가능)")
            
        # 좋은 적합
        if r_squared > 0.5 and test_r2 > 0.3:
            notes.append("✅ 양호한 적합도")
            
        return ValidationResult(
            edge_id=f"{source}_to_{target}",
            source=source,
            target=target,
            formula=func['formula'],
            slope=slope,
            intercept=intercept,
            r_squared=r_squared,
            rmse=rmse,
            mae=mae,
            mape=mape,
            train_r2=train_r2,
            test_r2=test_r2,
            residual_mean=residual_mean,
            residual_std=residual_std,
            is_valid=is_valid,
            validation_notes=notes
        )
    
    async def validate_mindsdb_model(self,
                                     model_name: str,
                                     data: pd.DataFrame,
                                     feature_cols: List[str],
                                     target_col: str,
                                     sample_size: int = 10) -> Optional[MindsDBValidationResult]:
        """
        MindsDB 모델 예측값과 실제 데이터 비교
        
        Args:
            model_name: MindsDB 모델 이름
            data: 검증 데이터
            feature_cols: 입력 특성 컬럼들
            target_col: 예측 대상 컬럼
            sample_size: 샘플링 크기 (API 호출 최소화)
        """
        print(f"\n   🔄 MindsDB 모델 검증: {model_name}")
        
        # 샘플링
        if len(data) > sample_size:
            sample_indices = np.random.choice(len(data), sample_size, replace=False)
            sample_data = data.iloc[sorted(sample_indices)]
        else:
            sample_data = data
            
        predictions = []
        actuals = []
        
        for idx, row in sample_data.iterrows():
            # WHERE 절 구성
            where_conditions = []
            for col in feature_cols:
                if col in row.index:
                    where_conditions.append(f"{col} = {row[col]}")
                    
            if not where_conditions:
                continue
                
            query = f"""
                SELECT {target_col} 
                FROM mindsdb.{model_name} 
                WHERE {' AND '.join(where_conditions)}
            """
            
            try:
                response = requests.post(
                    f"{self.mindsdb_url}/api/sql/query",
                    json={"query": query},
                    timeout=10
                )
                
                if response.status_code == 200:
                    result = response.json()
                    if result.get('data') and len(result['data']) > 0:
                        pred_value = float(result['data'][0][0])
                        predictions.append(pred_value)
                        actuals.append(float(row[target_col]))
                        
            except Exception as e:
                print(f"      ⚠️ 예측 실패: {e}")
                continue
        
        if len(predictions) < 3:
            print(f"      ❌ 충분한 예측 결과 없음 ({len(predictions)}개)")
            return None
            
        predictions = np.array(predictions)
        actuals = np.array(actuals)
        
        # 지표 계산
        ss_res = np.sum((actuals - predictions)**2)
        ss_tot = np.sum((actuals - np.mean(actuals))**2)
        r_squared = 1 - ss_res / ss_tot if ss_tot > 0 else 0
        
        rmse = np.sqrt(np.mean((actuals - predictions)**2))
        mae = np.mean(np.abs(actuals - predictions))
        
        non_zero_mask = actuals != 0
        if np.any(non_zero_mask):
            mape = np.mean(np.abs((actuals[non_zero_mask] - predictions[non_zero_mask]) / actuals[non_zero_mask])) * 100
        else:
            mape = 0
            
        print(f"      ✅ 검증 완료: R²={r_squared:.4f}, RMSE={rmse:.2f}, MAPE={mape:.1f}%")
        
        return MindsDBValidationResult(
            model_name=model_name,
            target_column=target_col,
            predictions=predictions.tolist(),
            actuals=actuals.tolist(),
            r_squared=r_squared,
            rmse=rmse,
            mae=mae,
            mape=mape,
            sample_size=len(predictions)
        )
    
    async def run_full_validation(self,
                                   data_path: str,
                                   functions_path: str) -> Dict[str, Any]:
        """
        전체 검증 파이프라인 실행
        """
        print("\n" + "=" * 70)
        print("🔬 MODEL VALIDATION ENGINE")
        print("   추정 함수 vs 실제 데이터 검증")
        print("=" * 70)
        
        # 데이터 및 함수 로드
        data = self.load_data(data_path)
        functions = self.load_influence_functions(functions_path)
        
        print(f"\n📊 데이터: {len(data)} 행, {len(data.columns)} 변수")
        print(f"📐 검증할 함수: {len(functions)}개")
        
        # =====================================================================
        # 1. 추정 함수 검증
        # =====================================================================
        print("\n" + "-" * 50)
        print("📈 1단계: 추정 함수 검증")
        print("-" * 50)
        
        for func in functions:
            if func.get('type') != 'linear':
                continue
                
            result = self.validate_edge_function(data, func)
            self.validation_results.append(result)
        
        # 검증 결과 요약
        valid_count = sum(1 for r in self.validation_results if r.is_valid)
        total_count = len(self.validation_results)
        
        print(f"\n   ✅ 유효한 함수: {valid_count}/{total_count}")
        
        # 상위 10개 결과 출력
        print(f"\n   {'Edge':<30} {'R²':>8} {'Test R²':>10} {'MAPE':>8} {'판정':>10}")
        print("   " + "-" * 70)
        
        sorted_results = sorted(
            self.validation_results, 
            key=lambda x: x.r_squared, 
            reverse=True
        )
        
        for r in sorted_results[:10]:
            status = "✅" if r.is_valid else "❌"
            print(f"   {r.edge_id:<30} {r.r_squared:>8.4f} {r.test_r2:>10.4f} {r.mape:>7.1f}% {status:>10}")
            
        # 과적합 의심 케이스
        overfit_cases = [r for r in self.validation_results if r.train_r2 - r.test_r2 > 0.15]
        if overfit_cases:
            print(f"\n   ⚠️ 과적합 의심 케이스: {len(overfit_cases)}개")
            for r in overfit_cases[:5]:
                print(f"      - {r.edge_id}: Train R²={r.train_r2:.3f}, Test R²={r.test_r2:.3f}")
        
        # =====================================================================
        # 2. MindsDB 모델 검증
        # =====================================================================
        print("\n" + "-" * 50)
        print("🤖 2단계: MindsDB 모델 검증")
        print("-" * 50)
        
        # MindsDB 모델 목록
        mindsdb_models = [
            ('whatif_cogs_model', ['fx_rate'], 'cogs'),
            ('whatif_demand_model', ['price', 'brand_equity', 'loyalty'], 'demand'),
            ('whatif_brand_model', ['csat', 'refund_rate', 'mkt_spend'], 'brand_equity'),
            ('whatif_profit_model', ['price', 'demand', 'cogs'], 'profit'),
        ]
        
        for model_name, features, target in mindsdb_models:
            try:
                result = await self.validate_mindsdb_model(
                    model_name=model_name,
                    data=data,
                    feature_cols=features,
                    target_col=target,
                    sample_size=10
                )
                if result:
                    self.mindsdb_results.append(result)
            except Exception as e:
                print(f"   ⚠️ {model_name} 검증 실패: {e}")
        
        # =====================================================================
        # 3. 종합 리포트
        # =====================================================================
        print("\n" + "=" * 70)
        print("📊 검증 종합 리포트")
        print("=" * 70)
        
        # 추정 함수 통계
        r2_values = [r.r_squared for r in self.validation_results]
        test_r2_values = [r.test_r2 for r in self.validation_results]
        
        print(f"""
┌─────────────────────────────────────────────────────────────────┐
│ 📈 추정 함수 검증 결과                                           │
├─────────────────────────────────────────────────────────────────┤
│ 총 검증 함수: {total_count:>4}개                                         │
│ 유효한 함수: {valid_count:>4}개 ({100*valid_count/total_count:.0f}%)                                     │
│ 평균 R²: {np.mean(r2_values):.4f}                                          │
│ 평균 Test R²: {np.mean(test_r2_values):.4f}                                     │
│ R² 중앙값: {np.median(r2_values):.4f}                                        │
├─────────────────────────────────────────────────────────────────┤
│ 🎯 적합도 분포                                                   │
│   R² > 0.7 (좋음): {sum(1 for r in r2_values if r > 0.7):>4}개                                      │
│   R² 0.3~0.7 (보통): {sum(1 for r in r2_values if 0.3 <= r <= 0.7):>4}개                                  │
│   R² < 0.3 (약함): {sum(1 for r in r2_values if r < 0.3):>4}개                                      │
├─────────────────────────────────────────────────────────────────┤
│ ⚠️ 과적합 의심: {len(overfit_cases):>4}개 (Train-Test R² 차이 > 0.15)            │
└─────────────────────────────────────────────────────────────────┘
""")
        
        # MindsDB 모델 결과
        if self.mindsdb_results:
            print("┌─────────────────────────────────────────────────────────────────┐")
            print("│ 🤖 MindsDB 모델 검증 결과                                        │")
            print("├─────────────────────────────────────────────────────────────────┤")
            for r in self.mindsdb_results:
                quality = "좋음" if r.r_squared > 0.5 else "보통" if r.r_squared > 0.2 else "약함"
                print(f"│ {r.model_name:<25} R²={r.r_squared:.3f} MAPE={r.mape:>5.1f}% ({quality}) │")
            print("└─────────────────────────────────────────────────────────────────┘")
        
        # 결과 저장
        output = {
            'validated_at': pd.Timestamp.now().isoformat(),
            'summary': {
                'total_functions': total_count,
                'valid_functions': valid_count,
                'mean_r_squared': float(np.mean(r2_values)),
                'mean_test_r_squared': float(np.mean(test_r2_values)),
                'overfit_cases': len(overfit_cases)
            },
            'function_results': [r.to_dict() for r in self.validation_results],
            'mindsdb_results': [r.to_dict() for r in self.mindsdb_results]
        }
        
        with open('validation_results.json', 'w', encoding='utf-8') as f:
            json.dump(output, f, indent=2, ensure_ascii=False)
            
        print("\n💾 결과 저장: validation_results.json")
        
        return output


# =============================================================================
# 메인 실행
# =============================================================================

if __name__ == "__main__":
    async def main():
        engine = ModelValidationEngine(
            mindsdb_url="http://127.0.0.1:47334",
            test_ratio=0.2,
            random_seed=42
        )
        
        results = await engine.run_full_validation(
            data_path='kpi_monthly.csv',
            functions_path='influence_functions.json'
        )
        
        return results
    
    asyncio.run(main())
