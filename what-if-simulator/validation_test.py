"""
Validation & Data Literacy Test
================================

전체 검증 및 데이터 리터러시 파이프라인 통합 테스트

실행 순서:
1. 모델 검증 (추정 함수 vs 실제 데이터)
2. 데이터 리터러시 리포트 생성 (LLM 기반)
3. 지속적 학습 파이프라인 실행

Author: AI Assistant
Created: 2026-01-24
"""

import asyncio
import json
from pathlib import Path
import pandas as pd


async def run_validation_test():
    """모델 검증 테스트"""
    print("\n" + "=" * 70)
    print("🧪 모델 검증 테스트")
    print("=" * 70)
    
    from model_validation import ModelValidationEngine
    
    engine = ModelValidationEngine(
        mindsdb_url="http://127.0.0.1:47334",
        test_ratio=0.2,
        random_seed=42
    )
    
    # influence_functions.json이 없으면 먼저 생성
    if not Path('influence_functions.json').exists():
        print("⚠️ influence_functions.json 없음 - 생성 중...")
        from cld_generator import CLDGenerator
        from causal_discovery import CausalDiscoveryEngine
        
        # Causal Discovery
        disc_engine = CausalDiscoveryEngine()
        data = disc_engine.load_data('kpi_monthly.csv')
        disc_results = disc_engine.run_discovery(data, methods=['correlation', 'granger'])
        disc_engine.export_to_json('causal_discovery_results.json')
        
        # CLD Generator
        cld_gen = CLDGenerator()
        cld_gen.build_graph_from_discovery(disc_results, min_strength=0.3)
        cld_gen.export_influence_functions(data, 'influence_functions.json')
    
    results = await engine.run_full_validation(
        data_path='kpi_monthly.csv',
        functions_path='influence_functions.json'
    )
    
    return results


def run_literacy_test():
    """데이터 리터러시 테스트"""
    print("\n" + "=" * 70)
    print("📚 데이터 리터러시 테스트")
    print("=" * 70)
    
    from data_literacy import DataLiteracyEngine
    
    engine = DataLiteracyEngine()
    
    # 결과 파일 로드
    with open('causal_discovery_results.json', 'r', encoding='utf-8') as f:
        discovery_results = json.load(f)
    
    with open('validation_results.json', 'r', encoding='utf-8') as f:
        validation_results = json.load(f)
    
    # 1. Causal Discovery 설명
    print("\n📝 Causal Discovery 설명 생성...")
    discovery_report = engine.explain_causal_discovery(discovery_results)
    
    print("\n" + "-" * 50)
    print(discovery_report.detailed_explanation)
    
    # 2. 검증 결과 설명
    print("\n📝 검증 결과 설명 생성...")
    validation_report = engine.explain_validation(validation_results)
    
    print("\n" + "-" * 50)
    print(validation_report.detailed_explanation)
    
    # 3. 경영진용 요약
    print("\n📝 경영진용 요약 생성...")
    exec_summary = engine.generate_executive_summary(discovery_results, validation_results)
    
    print("\n" + "-" * 50)
    print(exec_summary)
    
    # 저장
    literacy_output = {
        'generated_at': pd.Timestamp.now().isoformat(),
        'discovery_report': discovery_report.to_dict(),
        'validation_report': validation_report.to_dict(),
        'executive_summary': exec_summary
    }
    
    with open('literacy_report.json', 'w', encoding='utf-8') as f:
        json.dump(literacy_output, f, indent=2, ensure_ascii=False)
        
    print("\n💾 리포트 저장: literacy_report.json")
    
    return literacy_output


async def run_continuous_learning_test():
    """지속적 학습 테스트"""
    print("\n" + "=" * 70)
    print("🔄 지속적 학습 테스트")
    print("=" * 70)
    
    from continuous_learning import ContinuousLearningPipeline
    
    pipeline = ContinuousLearningPipeline(
        data_dir=".",
        history_dir="learning_history"
    )
    
    result = await pipeline.run_full_pipeline(
        data_path='kpi_monthly.csv',
        force_rerun=True
    )
    
    return result


async def main():
    """전체 테스트 실행"""
    print("\n")
    print("🧬" * 35)
    print(" VALIDATION & DATA LITERACY PIPELINE TEST")
    print("🧬" * 35)
    
    # 1. 모델 검증
    validation_results = await run_validation_test()
    
    # 2. 데이터 리터러시 (LLM 설명)
    literacy_results = run_literacy_test()
    
    # 3. 지속적 학습
    # (시간이 오래 걸리므로 선택적으로 실행)
    # learning_results = await run_continuous_learning_test()
    
    # 최종 요약
    print("\n" + "=" * 70)
    print("✅ 전체 테스트 완료")
    print("=" * 70)
    
    print("\n📁 생성된 파일:")
    generated_files = [
        'validation_results.json',
        'literacy_report.json',
        # 'continuous_learning_results.json'
    ]
    
    for f in generated_files:
        if Path(f).exists():
            size = Path(f).stat().st_size
            print(f"   ✅ {f} ({size:,} bytes)")
        else:
            print(f"   ❌ {f} (생성 안됨)")
    
    # 핵심 결과 출력
    print("\n" + "-" * 50)
    print("📊 핵심 결과 요약")
    print("-" * 50)
    
    summary = validation_results.get('summary', {})
    print(f"""
모델 검증:
   - 검증된 함수: {summary.get('total_functions', 0)}개
   - 유효한 함수: {summary.get('valid_functions', 0)}개 ({100*summary.get('valid_functions', 0)/max(1, summary.get('total_functions', 1)):.0f}%)
   - 평균 R²: {summary.get('mean_r_squared', 0):.4f}
   - 평균 Test R²: {summary.get('mean_test_r_squared', 0):.4f}
   - 과적합 의심: {summary.get('overfit_cases', 0)}개
""")
    
    return {
        'validation': validation_results,
        'literacy': literacy_results
    }


if __name__ == "__main__":
    asyncio.run(main())
