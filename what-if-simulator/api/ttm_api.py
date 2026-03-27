"""
IBM Granite TinyTimeMixer (TTM) 시계열 예측 서비스

사전 훈련된 TTM 모델을 사용하여 시계열 예측을 수행합니다.
https://github.com/ibm-granite/granite-tsfm

Note: torch와 tsfm_public은 선택적 의존성입니다.
      설치되지 않은 경우에도 서버는 시작되며, TTM 기능만 비활성화됩니다.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
import logging

# 선택적 의존성 (지연 로딩)
torch = None
TinyTimeMixerForPrediction = None

def _load_ttm_dependencies():
    """TTM 관련 의존성을 지연 로딩"""
    global torch, TinyTimeMixerForPrediction
    
    if torch is not None:
        return True
        
    try:
        import torch as _torch
        # 새로운 패키지명: granite-tsfm
        try:
            from tsfm_public.models.tinytimemixer import TinyTimeMixerForPrediction as _TTM
        except ImportError:
            from granite_tsfm.models.tinytimemixer import TinyTimeMixerForPrediction as _TTM
        torch = _torch
        TinyTimeMixerForPrediction = _TTM
        return True
    except ImportError as e:
        logging.warning(f"TTM 의존성 로드 실패: {e}")
        logging.info("TTM을 사용하려면: pip install torch granite-tsfm")
        return False

logger = logging.getLogger(__name__)


@dataclass
class TTMPredictionResult:
    """TTM 예측 결과"""
    predictions: np.ndarray
    actual: np.ndarray
    r2_score: float
    mape: float
    rmse: float
    model_name: str
    context_length: int
    prediction_length: int


class TTMService:
    """IBM Granite TinyTimeMixer 서비스"""
    
    def __init__(self):
        self.model = None
        self.model_name = None
        self.config = None
        self._initialized = False
        
    async def initialize(self) -> bool:
        """TTM 모델 초기화"""
        if self._initialized:
            return True
        
        # 의존성 로드
        if not _load_ttm_dependencies():
            logger.error("TTM 의존성을 로드할 수 없습니다.")
            return False
            
        try:
            # 사용 가능한 TTM 모델 목록 (우선순위 순)
            models_to_try = [
                "ibm-granite/granite-timeseries-ttm-v1",
                "ibm-granite/granite-timeseries-ttm-512-96-r1",
                "ibm-granite/granite-timeseries-ttm-1024-96-r1",
                "ibm-granite/granite-timeseries-ttm-r2",
            ]
            
            for model_name in models_to_try:
                try:
                    logger.info(f"TTM 모델 로드 시도: {model_name}")
                    self.model = TinyTimeMixerForPrediction.from_pretrained(model_name)
                    self.model_name = model_name
                    self.config = self.model.config
                    self.model.eval()
                    self._initialized = True
                    logger.info(f"TTM 모델 로드 성공: {model_name}")
                    return True
                except Exception as e:
                    logger.warning(f"TTM 모델 {model_name} 로드 실패: {e}")
                    continue
                    
            logger.error("모든 TTM 모델 로드 실패")
            return False
            
        except Exception as e:
            logger.error(f"TTM 초기화 실패: {e}")
            return False
            
    def is_available(self) -> bool:
        """TTM 모델 사용 가능 여부"""
        return self._initialized and self.model is not None
        
    def get_model_info(self) -> Dict[str, Any]:
        """모델 정보 반환"""
        if not self.is_available():
            return {"available": False}
            
        return {
            "available": True,
            "model_name": self.model_name,
            "context_length": getattr(self.config, 'context_length', 512),
            "prediction_length": getattr(self.config, 'prediction_length', 96),
            "num_input_channels": getattr(self.config, 'num_input_channels', 1),
        }
        
    async def predict(self, 
                      data: pd.DataFrame,
                      target_column: str,
                      feature_columns: Optional[List[str]] = None) -> Optional[TTMPredictionResult]:
        """
        TTM 모델로 시계열 예측 수행
        
        Args:
            data: 시계열 데이터프레임
            target_column: 예측 대상 컬럼
            feature_columns: 입력 특성 컬럼들 (None이면 target만 사용)
        """
        if not self.is_available():
            if not await self.initialize():
                return None
                
        try:
            context_length = getattr(self.config, 'context_length', 512)
            prediction_length = getattr(self.config, 'prediction_length', 96)
            
            # 데이터 준비
            if feature_columns:
                columns = feature_columns + [target_column] if target_column not in feature_columns else feature_columns
            else:
                columns = [target_column]
                
            # 데이터 길이 확인 - 최소 10개면 패딩으로 처리 가능
            min_data_required = 10
            if len(data) < min_data_required:
                logger.warning(f"데이터가 너무 적음: {len(data)} rows (최소 {min_data_required} 필요)")
                return None
                
            # 테스트 데이터 크기 결정 (최소 5개, 최대 데이터의 20%)
            test_samples = max(5, min(len(data) // 5, prediction_length))
            prediction_length = test_samples
            
            logger.info(f"TTM 예측 설정: 데이터 {len(data)}행, 테스트 {prediction_length}개, 컨텍스트 {context_length}")
                
            # 학습/테스트 분리
            train_size = len(data) - prediction_length
            test_data = data.iloc[train_size:]
            
            # 입력 데이터 준비 (패딩 적용)
            train_values = data[columns].values[:train_size]
            
            # 데이터가 context_length보다 적으면 패딩 사용
            if len(train_values) < context_length:
                padding_size = context_length - len(train_values)
                if len(train_values.shape) > 1:
                    # 다차원: 첫 번째 행으로 패딩
                    padding = np.tile(train_values[0:1], (padding_size, 1))
                    input_data = np.vstack([padding, train_values])
                else:
                    # 1차원
                    padding = np.full(padding_size, train_values[0])
                    input_data = np.concatenate([padding, train_values])
                logger.info(f"TTM 패딩 적용: {padding_size}개 추가 → 총 {len(input_data)}")
            else:
                input_data = train_values[-context_length:]
            
            # 의존성 확인
            if torch is None:
                if not _load_ttm_dependencies():
                    return None
            
            # 텐서로 변환 (batch_size, context_length, num_channels)
            if len(input_data.shape) == 1:
                input_data = input_data.reshape(-1, 1)
            input_tensor = torch.tensor(input_data, dtype=torch.float32).unsqueeze(0)
            
            # 단일 채널 모델이면 형태 조정
            num_channels = getattr(self.config, 'num_input_channels', 1)
            if num_channels == 1 and input_tensor.shape[2] > 1:
                # 타겟 컬럼만 사용
                target_idx = columns.index(target_column) if target_column in columns else 0
                input_tensor = input_tensor[:, :, target_idx:target_idx+1]
                
            # 예측 수행
            with torch.no_grad():
                output = self.model(past_values=input_tensor)
                
                if hasattr(output, 'prediction_outputs'):
                    predictions = output.prediction_outputs.numpy()[0]
                elif hasattr(output, 'last_hidden_state'):
                    predictions = output.last_hidden_state.numpy()[0]
                else:
                    predictions = output.numpy()[0] if hasattr(output, 'numpy') else np.array(output)[0]
                    
            # 예측 결과 추출 (첫 번째 채널 또는 타겟)
            if len(predictions.shape) > 1:
                predictions = predictions[:, 0]
                
            # 실제 테스트 데이터 길이에 맞춤
            actual_length = min(len(predictions), len(test_data))
            predictions = predictions[:actual_length]
            actual = test_data[target_column].values[:actual_length]
            
            # 메트릭 계산
            r2 = self._calculate_r2(actual, predictions)
            mape = self._calculate_mape(actual, predictions)
            rmse = self._calculate_rmse(actual, predictions)
            
            return TTMPredictionResult(
                predictions=predictions,
                actual=actual,
                r2_score=r2,
                mape=mape,
                rmse=rmse,
                model_name=self.model_name,
                context_length=context_length,
                prediction_length=prediction_length
            )
            
        except Exception as e:
            logger.error(f"TTM 예측 실패: {e}")
            import traceback
            traceback.print_exc()
            return None
            
    async def compare_predictions(self,
                                   data: pd.DataFrame,
                                   source_column: str,
                                   target_column: str,
                                   test_ratio: float = 0.2) -> Optional[Dict[str, Any]]:
        """
        TTM 모델과 선형 회귀 비교
        
        Args:
            data: 데이터프레임
            source_column: 입력 변수
            target_column: 출력 변수
            test_ratio: 테스트 데이터 비율
        """
        from sklearn.linear_model import LinearRegression
        from sklearn.metrics import r2_score, mean_absolute_percentage_error
        
        n = len(data)
        train_size = int(n * (1 - test_ratio))
        
        train_data = data.iloc[:train_size]
        test_data = data.iloc[train_size:]
        
        results = {
            'source': source_column,
            'target': target_column,
            'test_samples': len(test_data),
            'actual': test_data[target_column].values.tolist()
        }
        
        # 1. 선형 회귀 (온톨로지 모델)
        try:
            X_train = train_data[[source_column]].values
            y_train = train_data[target_column].values
            X_test = test_data[[source_column]].values
            y_test = test_data[target_column].values
            
            lr_model = LinearRegression()
            lr_model.fit(X_train, y_train)
            lr_preds = lr_model.predict(X_test)
            
            results['linear_regression'] = {
                'predictions': lr_preds.tolist(),
                'r2': float(r2_score(y_test, lr_preds)),
                'mape': float(mean_absolute_percentage_error(y_test, lr_preds) * 100),
                'coefficient': float(lr_model.coef_[0]),
                'intercept': float(lr_model.intercept_)
            }
        except Exception as e:
            results['linear_regression'] = {'error': str(e)}
            
        # 2. TTM 모델
        ttm_result = await self.predict(data, target_column, [source_column])
        
        if ttm_result:
            results['ttm'] = {
                'predictions': ttm_result.predictions.tolist(),
                'r2': float(ttm_result.r2_score),
                'mape': float(ttm_result.mape),
                'rmse': float(ttm_result.rmse),
                'model_name': ttm_result.model_name,
                'context_length': ttm_result.context_length,
                'prediction_length': ttm_result.prediction_length
            }
        else:
            results['ttm'] = {'error': 'TTM 모델 사용 불가'}
            
        # 3. 승자 판정
        if 'r2' in results.get('linear_regression', {}) and 'r2' in results.get('ttm', {}):
            lr_r2 = results['linear_regression']['r2']
            ttm_r2 = results['ttm']['r2']
            results['winner'] = 'TTM' if ttm_r2 > lr_r2 else 'Linear Regression'
            results['r2_difference'] = ttm_r2 - lr_r2
            
        return results
        
    @staticmethod
    def _calculate_r2(actual: np.ndarray, predicted: np.ndarray) -> float:
        """R² 계산"""
        ss_res = np.sum((actual - predicted) ** 2)
        ss_tot = np.sum((actual - np.mean(actual)) ** 2)
        return float(1 - ss_res / ss_tot) if ss_tot > 0 else 0.0
        
    @staticmethod
    def _calculate_mape(actual: np.ndarray, predicted: np.ndarray) -> float:
        """MAPE 계산"""
        mask = actual != 0
        if not np.any(mask):
            return 0.0
        return float(np.mean(np.abs((actual[mask] - predicted[mask]) / actual[mask])) * 100)
        
    @staticmethod
    def _calculate_rmse(actual: np.ndarray, predicted: np.ndarray) -> float:
        """RMSE 계산"""
        return float(np.sqrt(np.mean((actual - predicted) ** 2)))


# 싱글톤 인스턴스
ttm_service = TTMService()
