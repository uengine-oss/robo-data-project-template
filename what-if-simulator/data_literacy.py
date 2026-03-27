"""
Data Literacy Engine
=====================

LLM을 활용하여 데이터, 인과관계, 시뮬레이션 결과를 
자연어로 설명하는 기능을 제공합니다.

주요 기능:
1. 발견된 인과관계 설명
2. 검증 결과 해석
3. 시뮬레이션 결과 스토리텔링
4. 데이터 인사이트 요약

Author: AI Assistant
Created: 2026-01-24
"""

import json
import os
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
import requests

# OpenAI API 사용
try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False


@dataclass
class LiteracyReport:
    """데이터 리터러시 리포트"""
    title: str
    summary: str
    key_findings: List[str]
    recommendations: List[str]
    detailed_explanation: str
    
    def to_dict(self) -> Dict:
        return {
            'title': self.title,
            'summary': self.summary,
            'key_findings': self.key_findings,
            'recommendations': self.recommendations,
            'detailed_explanation': self.detailed_explanation
        }


class DataLiteracyEngine:
    """
    데이터 리터러시 엔진
    
    LLM을 활용하여 복잡한 데이터 분석 결과를 
    비전문가도 이해할 수 있는 자연어로 변환합니다.
    """
    
    def __init__(self, 
                 api_key: Optional[str] = None,
                 model: str = "gpt-4o-mini"):
        """
        Args:
            api_key: OpenAI API 키 (환경변수 OPENAI_API_KEY에서 자동 로드)
            model: 사용할 LLM 모델
        """
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.model = model
        
        if OPENAI_AVAILABLE and self.api_key:
            self.client = OpenAI(api_key=self.api_key)
        else:
            self.client = None
            
        # 기본 템플릿 정의
        self.templates = self._load_templates()
        
    def _load_templates(self) -> Dict[str, str]:
        """설명 템플릿 로드"""
        return {
            'causal_discovery': """
당신은 데이터 분석 전문가입니다. 아래의 Causal Discovery 결과를 비전문가가 이해할 수 있도록 설명해주세요.

## 분석 결과
{analysis_data}

## 요청 사항
1. 핵심 발견 사항을 3-5개의 bullet point로 요약
2. 발견된 인과관계를 실제 비즈니스 맥락에서 해석
3. 주의해야 할 점이나 한계점 언급
4. 추천하는 다음 단계 제안

한국어로 작성하고, 전문 용어는 쉽게 풀어서 설명해주세요.
""",
            'validation': """
당신은 통계 분석 전문가입니다. 모델 검증 결과를 해석해주세요.

## 검증 결과
{validation_data}

## 요청 사항
1. R² 값이 무엇을 의미하는지 설명
2. 과적합 여부와 그 의미
3. 신뢰할 수 있는 모델과 주의가 필요한 모델 구분
4. 실무에서 활용할 때의 주의사항

한국어로 작성하고, 비전문가도 이해할 수 있게 설명해주세요.
""",
            'simulation': """
당신은 비즈니스 분석가입니다. 시뮬레이션 결과를 스토리텔링으로 전달해주세요.

## 시뮬레이션 결과
{simulation_data}

## 요청 사항
1. 시나리오별 결과를 비교 설명
2. 가장 유리한 전략과 그 이유
3. 잠재적 리스크와 트레이드오프
4. 경영진에게 전달할 핵심 메시지

한국어로 작성하고, 실무 의사결정에 도움이 되도록 작성해주세요.
""",
            'edge_explanation': """
당신은 시스템 다이내믹스 전문가입니다. 인과관계(Edge)를 설명해주세요.

## 인과관계 정보
- 원인 변수: {source}
- 결과 변수: {target}
- 관계 강도: {strength}
- 방향성: {direction}
- 추정 함수: {formula}
- R²: {r_squared}

## 요청 사항
이 인과관계가 실제 비즈니스에서 어떤 의미를 갖는지 2-3문장으로 설명해주세요.
"""
        }
    
    def _call_llm(self, prompt: str) -> str:
        """LLM API 호출"""
        if not self.client:
            return self._fallback_response(prompt)
            
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "당신은 데이터 분석 및 비즈니스 인사이트 전문가입니다."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=2000
            )
            return response.choices[0].message.content
            
        except Exception as e:
            print(f"⚠️ LLM API 호출 실패: {e}")
            return self._fallback_response(prompt)
    
    def _fallback_response(self, prompt: str) -> str:
        """LLM 없이 기본 응답 생성"""
        return """
## 📊 자동 생성 분석 리포트

> ⚠️ OpenAI API 키가 설정되지 않아 기본 템플릿 응답을 제공합니다.
> 환경변수 OPENAI_API_KEY를 설정하면 LLM 기반 상세 분석을 받을 수 있습니다.

### 핵심 발견 사항
- 데이터에서 여러 인과관계가 발견되었습니다.
- 일부 관계는 통계적으로 유의하며, 일부는 추가 검증이 필요합니다.
- 시계열 데이터의 특성상 지연 효과가 있을 수 있습니다.

### 권장 사항
1. R² 값이 높은 관계를 우선적으로 활용하세요.
2. 과적합 의심 케이스는 추가 데이터로 검증하세요.
3. 인과관계 방향은 도메인 지식으로 확인하세요.

---
*이 리포트는 자동으로 생성되었습니다.*
"""
    
    def explain_causal_discovery(self, 
                                  discovery_results: Dict) -> LiteracyReport:
        """
        Causal Discovery 결과를 자연어로 설명
        """
        print("\n📝 Causal Discovery 결과 설명 생성 중...")
        
        # 요약 데이터 구성
        summary = discovery_results.get('summary', {})
        edges = discovery_results.get('edges', [])[:20]  # 상위 20개
        
        analysis_data = f"""
### 발견된 인과관계 통계
- 총 발견된 관계: {summary.get('total_edges', 0)}개
- 강한 관계 (strength > 0.5): {summary.get('strong_edges', 0)}개
- 양의 관계: {summary.get('direction_breakdown', {}).get('positive', 0)}개
- 음의 관계: {summary.get('direction_breakdown', {}).get('negative', 0)}개

### 핵심 원인 변수 (Root Causes)
{self._format_list(summary.get('root_causes', []))}

### 최종 결과 변수 (Final Effects)
{self._format_list(summary.get('final_effects', []))}

### 주요 인과관계 (상위 10개)
{self._format_edges(edges[:10])}
"""
        
        prompt = self.templates['causal_discovery'].format(analysis_data=analysis_data)
        explanation = self._call_llm(prompt)
        
        return LiteracyReport(
            title="Causal Discovery 분석 리포트",
            summary=f"총 {summary.get('total_edges', 0)}개의 인과관계가 발견되었습니다.",
            key_findings=self._extract_bullet_points(explanation),
            recommendations=[],
            detailed_explanation=explanation
        )
    
    def explain_validation(self, 
                           validation_results: Dict) -> LiteracyReport:
        """
        모델 검증 결과를 자연어로 설명
        """
        print("\n📝 검증 결과 설명 생성 중...")
        
        summary = validation_results.get('summary', {})
        func_results = validation_results.get('function_results', [])
        mindsdb_results = validation_results.get('mindsdb_results', [])
        
        validation_data = f"""
### 검증 요약
- 총 검증 함수: {summary.get('total_functions', 0)}개
- 유효한 함수: {summary.get('valid_functions', 0)}개
- 평균 R²: {summary.get('mean_r_squared', 0):.4f}
- 평균 테스트 R²: {summary.get('mean_test_r_squared', 0):.4f}
- 과적합 의심 케이스: {summary.get('overfit_cases', 0)}개

### 적합도 좋은 함수 (R² > 0.5)
{self._format_validation_results([r for r in func_results if r.get('metrics', {}).get('r_squared', 0) > 0.5][:5])}

### 과적합 의심 함수
{self._format_validation_results([r for r in func_results if r.get('metrics', {}).get('train_r2', 0) - r.get('metrics', {}).get('test_r2', 0) > 0.15][:5])}

### MindsDB 모델 검증
{self._format_mindsdb_results(mindsdb_results)}
"""
        
        prompt = self.templates['validation'].format(validation_data=validation_data)
        explanation = self._call_llm(prompt)
        
        return LiteracyReport(
            title="모델 검증 분석 리포트",
            summary=f"총 {summary.get('total_functions', 0)}개 함수 중 {summary.get('valid_functions', 0)}개가 유효합니다.",
            key_findings=self._extract_bullet_points(explanation),
            recommendations=[],
            detailed_explanation=explanation
        )
    
    def explain_simulation(self, 
                           simulation_results: Dict) -> LiteracyReport:
        """
        시뮬레이션 결과를 자연어로 설명
        """
        print("\n📝 시뮬레이션 결과 설명 생성 중...")
        
        simulation_data = json.dumps(simulation_results, indent=2, ensure_ascii=False)
        
        prompt = self.templates['simulation'].format(simulation_data=simulation_data)
        explanation = self._call_llm(prompt)
        
        return LiteracyReport(
            title="시뮬레이션 분석 리포트",
            summary="시뮬레이션 시나리오 분석 완료",
            key_findings=self._extract_bullet_points(explanation),
            recommendations=[],
            detailed_explanation=explanation
        )
    
    def explain_single_edge(self,
                            source: str,
                            target: str,
                            strength: float,
                            direction: str,
                            formula: str,
                            r_squared: float) -> str:
        """
        단일 인과관계를 설명
        """
        prompt = self.templates['edge_explanation'].format(
            source=source,
            target=target,
            strength=strength,
            direction=direction,
            formula=formula,
            r_squared=r_squared
        )
        
        return self._call_llm(prompt)
    
    def generate_executive_summary(self,
                                    discovery_results: Dict,
                                    validation_results: Dict) -> str:
        """
        경영진용 요약 리포트 생성
        """
        print("\n📝 경영진용 요약 리포트 생성 중...")
        
        prompt = f"""
당신은 최고 데이터 책임자(CDO)입니다. 아래 분석 결과를 바탕으로 
경영진에게 브리핑할 수 있는 간결한 요약문을 작성해주세요.

## Causal Discovery 결과
- 발견된 인과관계: {discovery_results.get('summary', {}).get('total_edges', 0)}개
- 핵심 원인 변수: {', '.join([x[0] for x in discovery_results.get('summary', {}).get('root_causes', [])[:3]])}
- 핵심 결과 변수: {', '.join([x[0] for x in discovery_results.get('summary', {}).get('final_effects', [])[:3]])}

## 검증 결과
- 유효한 모델 비율: {validation_results.get('summary', {}).get('valid_functions', 0)}/{validation_results.get('summary', {}).get('total_functions', 0)}
- 평균 예측 정확도 (R²): {validation_results.get('summary', {}).get('mean_r_squared', 0):.2%}
- 과적합 리스크: {validation_results.get('summary', {}).get('overfit_cases', 0)}개 모델

## 요청 사항
1. 3문장 이내의 핵심 요약
2. 의사결정에 활용할 수 있는 1가지 핵심 인사이트
3. 추가 분석이 필요한 영역 1가지

한국어로 작성하고, 비즈니스 관점에서 작성해주세요.
"""
        
        return self._call_llm(prompt)
    
    def _format_list(self, items: List) -> str:
        """리스트를 문자열로 포맷"""
        if not items:
            return "- (없음)"
        return "\n".join([f"- {item[0]}: {item[1]}개 관계" for item in items[:5]])
    
    def _format_edges(self, edges: List[Dict]) -> str:
        """엣지 목록을 포맷"""
        if not edges:
            return "- (없음)"
        lines = []
        for e in edges:
            direction = "→+" if e.get('direction') == 'positive' else "→-"
            lines.append(f"- {e.get('source')} {direction} {e.get('target')} (강도: {e.get('strength', 0):.3f})")
        return "\n".join(lines)
    
    def _format_validation_results(self, results: List[Dict]) -> str:
        """검증 결과를 포맷"""
        if not results:
            return "- (없음)"
        lines = []
        for r in results:
            metrics = r.get('metrics', {})
            lines.append(f"- {r.get('edge_id')}: R²={metrics.get('r_squared', 0):.3f}, Test R²={metrics.get('test_r2', 0):.3f}")
        return "\n".join(lines)
    
    def _format_mindsdb_results(self, results: List[Dict]) -> str:
        """MindsDB 결과를 포맷"""
        if not results:
            return "- (MindsDB 검증 결과 없음)"
        lines = []
        for r in results:
            metrics = r.get('metrics', {})
            lines.append(f"- {r.get('model_name')}: R²={metrics.get('r_squared', 0):.3f}, MAPE={metrics.get('mape', 0):.1f}%")
        return "\n".join(lines)
    
    def _extract_bullet_points(self, text: str) -> List[str]:
        """텍스트에서 bullet point 추출"""
        points = []
        for line in text.split('\n'):
            line = line.strip()
            if line.startswith('- ') or line.startswith('• ') or line.startswith('* '):
                points.append(line[2:])
            elif line.startswith('1.') or line.startswith('2.') or line.startswith('3.'):
                points.append(line[2:].strip())
        return points[:10]  # 최대 10개


# =============================================================================
# 메인 실행
# =============================================================================

def demo_without_api():
    """API 없이 템플릿 기반 데모"""
    print("\n" + "=" * 70)
    print("📚 DATA LITERACY ENGINE (Demo Mode)")
    print("=" * 70)
    
    engine = DataLiteracyEngine(api_key=None)
    
    # 샘플 데이터로 테스트
    sample_discovery = {
        'summary': {
            'total_edges': 103,
            'strong_edges': 45,
            'direction_breakdown': {'positive': 66, 'negative': 37},
            'root_causes': [('fx_rate', 15), ('mkt_spend', 9), ('pass_through', 9)],
            'final_effects': [('brand_equity', 14), ('loyalty', 14), ('demand', 11)]
        },
        'edges': [
            {'source': 'fx_rate', 'target': 'cogs', 'strength': 0.87, 'direction': 'positive'},
            {'source': 'cogs', 'target': 'price', 'strength': 1.0, 'direction': 'positive'},
            {'source': 'price', 'target': 'demand', 'strength': 0.45, 'direction': 'negative'},
        ]
    }
    
    # Causal Discovery 설명
    report = engine.explain_causal_discovery(sample_discovery)
    
    print("\n📋 생성된 리포트:")
    print("-" * 50)
    print(report.detailed_explanation)
    
    return report


if __name__ == "__main__":
    # API 키가 있으면 전체 기능 실행, 없으면 데모 모드
    import asyncio
    
    if os.getenv("OPENAI_API_KEY"):
        print("✅ OpenAI API 키 감지 - 전체 기능 모드")
        
        async def main():
            engine = DataLiteracyEngine()
            
            # 실제 파일 로드
            with open('causal_discovery_results.json', 'r') as f:
                discovery_results = json.load(f)
                
            report = engine.explain_causal_discovery(discovery_results)
            print(report.detailed_explanation)
            
            # 저장
            with open('literacy_report.json', 'w', encoding='utf-8') as f:
                json.dump(report.to_dict(), f, indent=2, ensure_ascii=False)
                
        asyncio.run(main())
    else:
        print("⚠️ OpenAI API 키 없음 - 데모 모드")
        demo_without_api()
