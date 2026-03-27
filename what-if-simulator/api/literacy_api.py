"""
Data Literacy API
==================

LLM을 사용하여 분석 결과를 자연어로 설명
"""

import json
from typing import Dict, List, Any, Optional
from openai import OpenAI

from .config import settings


class DataLiteracyService:
    """
    데이터 리터러시 서비스
    
    LLM을 활용하여 복잡한 분석 결과를 
    비전문가도 이해할 수 있는 자연어로 설명합니다.
    """
    
    def __init__(self):
        self.client = None
        if settings.openai_api_key:
            self.client = OpenAI(api_key=settings.openai_api_key)
        self.model = settings.openai_model
    
    def _call_llm(self, system_prompt: str, user_prompt: str) -> str:
        """LLM 호출"""
        if not self.client:
            return self._fallback_response(user_prompt)
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.7,
                max_tokens=2000
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            print(f"LLM 호출 실패: {e}")
            return self._fallback_response(user_prompt)
    
    def _fallback_response(self, context: str) -> str:
        """LLM 사용 불가 시 기본 응답"""
        return f"[분석 결과 요약]\n{context[:500]}..."
    
    async def explain_causal_discovery(self, 
                                        discovery_result: Dict,
                                        language: str = "ko") -> str:
        """
        Causal Discovery 결과 설명
        
        Args:
            discovery_result: CausalDiscoveryResult를 딕셔너리로 변환한 결과
            language: 출력 언어 (ko, en)
        """
        edges = discovery_result.get('edges', [])
        summary = discovery_result.get('summary', {})
        
        system_prompt = """당신은 데이터 분석 결과를 비전문가에게 설명하는 전문가입니다.
        인과관계 분석 결과를 명확하고 이해하기 쉬운 언어로 설명해주세요.
        
        다음 구조로 설명해주세요:
        1. 핵심 발견 (가장 중요한 3-5개 인과관계)
        2. 원인 변수 (다른 변수에 영향을 주는 핵심 원인)
        3. 결과 변수 (여러 원인에 의해 영향받는 변수)
        4. 비즈니스 의미 (이 인과관계가 의미하는 바)
        5. 권장 조치 (데이터 기반 권장 사항)"""
        
        user_prompt = f"""다음 인과관계 분석 결과를 설명해주세요:

## 발견된 인과관계 (총 {len(edges)}개)

### 주요 인과관계 (상위 10개)
{json.dumps(edges[:10], indent=2, ensure_ascii=False)}

### 요약 통계
{json.dumps(summary, indent=2, ensure_ascii=False)}

{"한국어로 설명해주세요." if language == "ko" else "Please explain in English."}"""
        
        return self._call_llm(system_prompt, user_prompt)
    
    async def explain_validation(self,
                                  validation_result: Dict,
                                  language: str = "ko") -> str:
        """
        모델 검증 결과 설명
        
        Args:
            validation_result: 검증 결과 딕셔너리
            language: 출력 언어
        """
        system_prompt = """당신은 데이터 과학 결과를 비즈니스 용어로 번역하는 전문가입니다.
        모델 검증 결과를 명확하게 설명하고, 과적합 여부와 모델 신뢰도에 대해 설명해주세요.
        
        R² (결정계수): 0에서 1 사이 값으로, 모델이 데이터를 얼마나 잘 설명하는지 나타냄
        - 0.7 이상: 좋음
        - 0.5-0.7: 보통
        - 0.5 미만: 개선 필요
        
        과적합: 훈련 데이터에서는 잘 작동하지만 새 데이터에서 성능이 떨어지는 현상"""
        
        user_prompt = f"""다음 모델 검증 결과를 설명해주세요:

{json.dumps(validation_result, indent=2, ensure_ascii=False)}

{"한국어로 설명해주세요. 비전문가도 이해할 수 있게 쉽게 설명해주세요." if language == "ko" else "Please explain in English for non-technical audience."}"""
        
        return self._call_llm(system_prompt, user_prompt)
    
    async def explain_comparison(self,
                                  comparison_result: Dict,
                                  language: str = "ko") -> str:
        """
        Causal Discovery vs MindsDB 비교 결과 설명
        """
        system_prompt = """당신은 머신러닝 모델 성능을 비교 설명하는 전문가입니다.
        
        두 가지 접근 방식을 비교합니다:
        1. Causal Discovery: 통계적 방법으로 인과관계를 발견하고 선형 회귀로 관계를 모델링
        2. MindsDB: 자동화된 머신러닝으로 변수 간 관계를 학습
        
        각 접근 방식의 장단점과 어떤 상황에서 어떤 방법이 더 적합한지 설명해주세요."""
        
        user_prompt = f"""다음 모델 비교 결과를 설명해주세요:

{json.dumps(comparison_result, indent=2, ensure_ascii=False)}

{"한국어로 설명해주세요." if language == "ko" else "Please explain in English."}"""
        
        return self._call_llm(system_prompt, user_prompt)
    
    async def generate_executive_summary(self,
                                          discovery_result: Dict,
                                          validation_result: Dict,
                                          comparison_result: Optional[Dict] = None,
                                          language: str = "ko") -> str:
        """
        경영진을 위한 종합 요약 생성
        """
        system_prompt = """당신은 데이터 분석 결과를 경영진에게 보고하는 전문가입니다.
        
        1-2분 안에 읽을 수 있는 간결한 보고서를 작성해주세요.
        다음 구조를 따르세요:
        
        📊 핵심 발견
        - 가장 중요한 3가지 인사이트
        
        ⚠️ 주의 사항
        - 데이터 또는 모델의 한계
        
        ✅ 권장 조치
        - 데이터 기반 구체적 행동 제안
        
        📈 기대 효과
        - 권장 조치 시행 시 예상되는 결과"""
        
        user_prompt = f"""다음 분석 결과를 바탕으로 경영진 보고서를 작성해주세요:

## 1. 인과관계 분석 결과
{json.dumps(discovery_result.get('summary', {}), indent=2, ensure_ascii=False)}

발견된 주요 인과관계:
{json.dumps(discovery_result.get('edges', [])[:5], indent=2, ensure_ascii=False)}

## 2. 모델 검증 결과
{json.dumps(validation_result, indent=2, ensure_ascii=False)}

{"## 3. MindsDB 비교 결과" if comparison_result else ""}
{json.dumps(comparison_result, indent=2, ensure_ascii=False) if comparison_result else ""}

{"한국어로 작성해주세요." if language == "ko" else "Please write in English."}"""
        
        return self._call_llm(system_prompt, user_prompt)
    
    async def suggest_next_steps(self,
                                  current_analysis: Dict,
                                  language: str = "ko") -> str:
        """다음 분석 단계 제안"""
        system_prompt = """당신은 데이터 분석 전략을 제안하는 컨설턴트입니다.
        현재 분석 결과를 바탕으로 다음 단계를 제안해주세요.
        
        고려할 사항:
        1. 추가로 수집해야 할 데이터
        2. 더 깊이 분석해야 할 관계
        3. 검증이 필요한 가설
        4. 실험 설계 제안"""
        
        user_prompt = f"""현재 분석 결과:
{json.dumps(current_analysis, indent=2, ensure_ascii=False)}

{"다음 분석 단계를 한국어로 제안해주세요." if language == "ko" else "Please suggest next steps in English."}"""
        
        return self._call_llm(system_prompt, user_prompt)
    
    async def generate_presentation_content(self,
                                             analysis_result: Dict,
                                             slides_count: int = 5,
                                             language: str = "ko") -> List[Dict]:
        """프레젠테이션 슬라이드 콘텐츠 생성"""
        system_prompt = f"""당신은 데이터 분석 결과를 프레젠테이션으로 만드는 전문가입니다.
        
        {slides_count}장의 슬라이드 내용을 생성해주세요.
        각 슬라이드는 다음 형식으로 작성:
        
        {{
            "title": "슬라이드 제목",
            "bullets": ["핵심 포인트 1", "핵심 포인트 2", "핵심 포인트 3"],
            "notes": "발표자 노트",
            "chart_suggestion": "추천 차트 유형 (bar, line, scatter 등)"
        }}
        
        JSON 배열로 반환해주세요."""
        
        user_prompt = f"""다음 분석 결과로 프레젠테이션을 만들어주세요:

{json.dumps(analysis_result, indent=2, ensure_ascii=False)}

{"한국어로 작성해주세요." if language == "ko" else "Please write in English."}"""
        
        response = self._call_llm(system_prompt, user_prompt)
        
        try:
            # JSON 배열 파싱 시도
            import re
            json_match = re.search(r'\[.*\]', response, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
        except:
            pass
        
        return [{"title": "분석 결과", "bullets": [response[:200]], "notes": "", "chart_suggestion": "bar"}]


# 싱글톤 인스턴스
literacy_service = DataLiteracyService()
