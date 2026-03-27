"""
Continuous Learning Pipeline
============================

새로운 데이터가 추가될 때 자동으로:
1. 인과관계 재발견
2. 영향 함수 재추정
3. 모델 검증
4. 변화 감지 및 알림

Author: AI Assistant
Created: 2026-01-24
"""

import json
import asyncio
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from pathlib import Path
import hashlib

import pandas as pd
import numpy as np


@dataclass
class ChangeDetectionResult:
    """변화 감지 결과"""
    timestamp: str
    data_hash: str
    
    # 변화 통계
    new_edges: List[Dict]           # 새로 발견된 관계
    removed_edges: List[Dict]       # 사라진 관계
    strengthened_edges: List[Dict]  # 강화된 관계
    weakened_edges: List[Dict]      # 약화된 관계
    
    # 모델 변화
    improved_models: List[str]      # R² 개선된 모델
    degraded_models: List[str]      # R² 저하된 모델
    
    # 알림 수준
    alert_level: str  # 'info', 'warning', 'critical'
    
    def to_dict(self) -> Dict:
        return {
            'timestamp': self.timestamp,
            'data_hash': self.data_hash,
            'changes': {
                'new_edges': len(self.new_edges),
                'removed_edges': len(self.removed_edges),
                'strengthened_edges': len(self.strengthened_edges),
                'weakened_edges': len(self.weakened_edges),
            },
            'model_changes': {
                'improved': self.improved_models,
                'degraded': self.degraded_models,
            },
            'alert_level': self.alert_level
        }


class ContinuousLearningPipeline:
    """
    지속적 학습 파이프라인
    
    새 데이터가 추가될 때마다 전체 분석 파이프라인을 재실행하고
    기존 결과와의 변화를 감지합니다.
    """
    
    def __init__(self, 
                 data_dir: str = ".",
                 history_dir: str = "learning_history"):
        self.data_dir = Path(data_dir)
        self.history_dir = Path(history_dir)
        self.history_dir.mkdir(exist_ok=True)
        
        # 이전 결과 로드
        self.previous_discovery: Optional[Dict] = None
        self.previous_validation: Optional[Dict] = None
        
    def compute_data_hash(self, data: pd.DataFrame) -> str:
        """데이터의 해시값 계산 (변경 감지용)"""
        data_str = data.to_csv(index=False)
        return hashlib.md5(data_str.encode()).hexdigest()[:16]
    
    def load_previous_results(self) -> Tuple[Optional[Dict], Optional[Dict]]:
        """이전 실행 결과 로드"""
        discovery_path = self.data_dir / "causal_discovery_results.json"
        validation_path = self.data_dir / "validation_results.json"
        
        discovery = None
        validation = None
        
        if discovery_path.exists():
            with open(discovery_path, 'r', encoding='utf-8') as f:
                discovery = json.load(f)
                
        if validation_path.exists():
            with open(validation_path, 'r', encoding='utf-8') as f:
                validation = json.load(f)
                
        return discovery, validation
    
    def save_to_history(self, 
                        results: Dict, 
                        result_type: str,
                        data_hash: str):
        """결과를 히스토리에 저장"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{result_type}_{timestamp}_{data_hash}.json"
        filepath = self.history_dir / filename
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
            
        print(f"   💾 히스토리 저장: {filepath}")
    
    def detect_edge_changes(self,
                            old_edges: List[Dict],
                            new_edges: List[Dict],
                            strength_threshold: float = 0.1) -> Dict[str, List]:
        """
        엣지(인과관계) 변화 감지
        """
        old_edge_map = {(e['source'], e['target']): e for e in old_edges}
        new_edge_map = {(e['source'], e['target']): e for e in new_edges}
        
        old_keys = set(old_edge_map.keys())
        new_keys = set(new_edge_map.keys())
        
        # 새로 발견된 관계
        new_discovered = [new_edge_map[k] for k in (new_keys - old_keys)]
        
        # 사라진 관계
        removed = [old_edge_map[k] for k in (old_keys - new_keys)]
        
        # 공통 관계에서 강도 변화
        common_keys = old_keys & new_keys
        strengthened = []
        weakened = []
        
        for k in common_keys:
            old_strength = old_edge_map[k].get('strength', 0)
            new_strength = new_edge_map[k].get('strength', 0)
            diff = new_strength - old_strength
            
            if diff > strength_threshold:
                strengthened.append({
                    **new_edge_map[k],
                    'old_strength': old_strength,
                    'change': diff
                })
            elif diff < -strength_threshold:
                weakened.append({
                    **new_edge_map[k],
                    'old_strength': old_strength,
                    'change': diff
                })
                
        return {
            'new': new_discovered,
            'removed': removed,
            'strengthened': strengthened,
            'weakened': weakened
        }
    
    def detect_model_changes(self,
                              old_validation: Dict,
                              new_validation: Dict,
                              r2_threshold: float = 0.05) -> Dict[str, List]:
        """
        모델 성능 변화 감지
        """
        old_results = {r['edge_id']: r for r in old_validation.get('function_results', [])}
        new_results = {r['edge_id']: r for r in new_validation.get('function_results', [])}
        
        improved = []
        degraded = []
        
        for edge_id in set(old_results.keys()) & set(new_results.keys()):
            old_r2 = old_results[edge_id].get('metrics', {}).get('r_squared', 0)
            new_r2 = new_results[edge_id].get('metrics', {}).get('r_squared', 0)
            diff = new_r2 - old_r2
            
            if diff > r2_threshold:
                improved.append(f"{edge_id} (+{diff:.3f})")
            elif diff < -r2_threshold:
                degraded.append(f"{edge_id} ({diff:.3f})")
                
        return {
            'improved': improved,
            'degraded': degraded
        }
    
    def determine_alert_level(self, changes: Dict) -> str:
        """
        알림 수준 결정
        """
        # Critical: 많은 관계가 사라지거나 모델 성능이 크게 저하
        if len(changes.get('removed', [])) > 5 or len(changes.get('degraded', [])) > 3:
            return 'critical'
            
        # Warning: 일부 변화 감지
        if (len(changes.get('new', [])) > 3 or 
            len(changes.get('weakened', [])) > 3 or
            len(changes.get('degraded', [])) > 0):
            return 'warning'
            
        return 'info'
    
    async def run_discovery(self, data: pd.DataFrame) -> Dict:
        """Causal Discovery 실행"""
        from causal_discovery import CausalDiscoveryEngine
        
        engine = CausalDiscoveryEngine(
            significance_level=0.05,
            min_correlation=0.35,
            max_lag=2
        )
        
        results = engine.run_discovery(
            data,
            methods=['correlation', 'granger', 'partial']
        )
        engine.export_to_json(str(self.data_dir / 'causal_discovery_results.json'))
        
        return results
    
    async def run_validation(self, data_path: str, functions_path: str) -> Dict:
        """모델 검증 실행"""
        from model_validation import ModelValidationEngine
        
        engine = ModelValidationEngine(test_ratio=0.2)
        results = await engine.run_full_validation(data_path, functions_path)
        
        return results
    
    async def run_full_pipeline(self, 
                                 data_path: str,
                                 force_rerun: bool = False) -> ChangeDetectionResult:
        """
        전체 지속적 학습 파이프라인 실행
        
        Args:
            data_path: 새 데이터 경로
            force_rerun: 변경 없어도 강제 재실행
        """
        print("\n" + "=" * 70)
        print("🔄 CONTINUOUS LEARNING PIPELINE")
        print("=" * 70)
        
        # 1. 데이터 로드 및 해시 계산
        print("\n📊 1. 데이터 로드...")
        data = pd.read_csv(data_path)
        exclude_cols = ['year_month', 'month_num']
        numeric_data = data[[c for c in data.columns if c not in exclude_cols]]
        
        current_hash = self.compute_data_hash(data)
        print(f"   데이터 해시: {current_hash}")
        print(f"   데이터 크기: {len(data)} 행, {len(data.columns)} 열")
        
        # 2. 이전 결과 로드
        print("\n📂 2. 이전 결과 로드...")
        old_discovery, old_validation = self.load_previous_results()
        
        if old_discovery:
            old_hash = old_discovery.get('parameters', {}).get('data_hash', '')
            if old_hash == current_hash and not force_rerun:
                print("   ⏸️ 데이터 변경 없음 - 파이프라인 스킵")
                return ChangeDetectionResult(
                    timestamp=datetime.now().isoformat(),
                    data_hash=current_hash,
                    new_edges=[],
                    removed_edges=[],
                    strengthened_edges=[],
                    weakened_edges=[],
                    improved_models=[],
                    degraded_models=[],
                    alert_level='info'
                )
        
        # 3. Causal Discovery 실행
        print("\n🔍 3. Causal Discovery 재실행...")
        new_discovery = await self.run_discovery(numeric_data)
        
        # 데이터 해시 저장
        new_discovery['parameters'] = new_discovery.get('parameters', {})
        new_discovery['parameters']['data_hash'] = current_hash
        
        # 4. 영향 함수 재추정 (CLD Generator)
        print("\n📐 4. 영향 함수 재추정...")
        from cld_generator import CLDGenerator
        
        cld_gen = CLDGenerator()
        cld_gen.build_graph_from_discovery(new_discovery, min_strength=0.3)
        cld_gen.classify_nodes()
        functions = cld_gen.export_influence_functions(
            numeric_data,
            str(self.data_dir / 'influence_functions.json')
        )
        
        # 5. 모델 검증
        print("\n✅ 5. 모델 검증...")
        new_validation = await self.run_validation(
            data_path,
            str(self.data_dir / 'influence_functions.json')
        )
        
        # 6. 변화 감지
        print("\n🔎 6. 변화 감지...")
        edge_changes = {}
        model_changes = {}
        
        if old_discovery:
            old_edges = old_discovery.get('edges', [])
            new_edges = new_discovery.get('edges', [])
            edge_changes = self.detect_edge_changes(old_edges, new_edges)
            
            print(f"   🆕 새로 발견: {len(edge_changes.get('new', []))}개")
            print(f"   ❌ 사라진 관계: {len(edge_changes.get('removed', []))}개")
            print(f"   ⬆️ 강화된 관계: {len(edge_changes.get('strengthened', []))}개")
            print(f"   ⬇️ 약화된 관계: {len(edge_changes.get('weakened', []))}개")
            
        if old_validation:
            model_changes = self.detect_model_changes(old_validation, new_validation)
            print(f"   📈 개선된 모델: {len(model_changes.get('improved', []))}개")
            print(f"   📉 저하된 모델: {len(model_changes.get('degraded', []))}개")
        
        # 7. 알림 수준 결정
        alert_level = self.determine_alert_level({
            **edge_changes,
            **model_changes
        })
        
        # 8. 히스토리 저장
        print("\n💾 7. 히스토리 저장...")
        self.save_to_history(new_discovery, 'discovery', current_hash)
        self.save_to_history(new_validation, 'validation', current_hash)
        
        # 9. 결과 생성
        result = ChangeDetectionResult(
            timestamp=datetime.now().isoformat(),
            data_hash=current_hash,
            new_edges=edge_changes.get('new', []),
            removed_edges=edge_changes.get('removed', []),
            strengthened_edges=edge_changes.get('strengthened', []),
            weakened_edges=edge_changes.get('weakened', []),
            improved_models=model_changes.get('improved', []),
            degraded_models=model_changes.get('degraded', []),
            alert_level=alert_level
        )
        
        # 10. 결과 출력
        print("\n" + "=" * 70)
        print("📊 파이프라인 실행 완료")
        print("=" * 70)
        
        alert_emoji = {'info': 'ℹ️', 'warning': '⚠️', 'critical': '🚨'}
        print(f"""
┌─────────────────────────────────────────────────────────────────┐
│ 🔄 Continuous Learning 결과                                      │
├─────────────────────────────────────────────────────────────────┤
│ 데이터 해시: {current_hash}                                      │
│ 알림 수준: {alert_emoji.get(alert_level, '')} {alert_level.upper()}                                          │
├─────────────────────────────────────────────────────────────────┤
│ 인과관계 변화                                                    │
│   🆕 새로 발견: {len(result.new_edges):>4}개                                       │
│   ❌ 사라짐: {len(result.removed_edges):>4}개                                          │
│   ⬆️ 강화: {len(result.strengthened_edges):>4}개                                            │
│   ⬇️ 약화: {len(result.weakened_edges):>4}개                                            │
├─────────────────────────────────────────────────────────────────┤
│ 모델 성능 변화                                                   │
│   📈 개선: {len(result.improved_models):>4}개                                           │
│   📉 저하: {len(result.degraded_models):>4}개                                           │
└─────────────────────────────────────────────────────────────────┘
""")
        
        # 변화 상세 출력
        if result.new_edges:
            print("🆕 새로 발견된 관계:")
            for e in result.new_edges[:5]:
                print(f"   - {e.get('source')} → {e.get('target')} (강도: {e.get('strength', 0):.3f})")
                
        if result.degraded_models:
            print("\n📉 성능 저하된 모델:")
            for m in result.degraded_models[:5]:
                print(f"   - {m}")
        
        # 결과 저장
        with open(self.data_dir / 'continuous_learning_results.json', 'w', encoding='utf-8') as f:
            json.dump(result.to_dict(), f, indent=2, ensure_ascii=False)
            
        return result


# =============================================================================
# 메인 실행
# =============================================================================

if __name__ == "__main__":
    async def main():
        pipeline = ContinuousLearningPipeline(
            data_dir=".",
            history_dir="learning_history"
        )
        
        result = await pipeline.run_full_pipeline(
            data_path='kpi_monthly.csv',
            force_rerun=True
        )
        
        return result
    
    asyncio.run(main())
