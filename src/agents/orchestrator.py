"""Lab 4 — Orchestrator Agent: Agents-as-Tools 패턴으로 서브 에이전트 조율."""
import os
from strands import Agent, tool
from strands.models import BedrockModel
from strands.models.model import CacheConfig
from .qa_agent import ask_qa_agent
from .recommend_agent import ask_recommend_agent
from .summary_agent import polish_response

SYSTEM_PROMPT = """당신은 더후(The History of Whoo) AI 챗봇의 오케스트레이터입니다.

고객 요청 유형에 따라 적절한 전문 에이전트를 호출하세요:
- 상품 성분, 효과, 사용법 질문 → qa_tool
- 상품 검색, 추천, 재고, 프로모션 → recommend_tool
- 최종 답변 톤·포맷 정리 → summary_tool

복잡한 요청은 여러 에이전트를 순차적으로 호출해 정보를 조합하세요.
항상 summary_tool로 최종 답변을 정리한 후 고객에게 전달하세요."""


@tool
def qa_tool(question: str) -> str:
    """상품 정보, 성분, 효과, 사용법 등 정보성 질문에 답변합니다.

    Args:
        question: 고객의 질문

    Returns:
        Knowledge Base 기반 답변
    """
    return ask_qa_agent(question)


@tool
def recommend_tool(request: str) -> str:
    """상품 검색, 개인화 추천, 재고 확인, 프로모션 조회를 수행합니다.

    Args:
        request: 고객의 추천/검색 요청 (피부 타입, 예산, 카테고리 포함)

    Returns:
        추천 상품 목록과 이유
    """
    return ask_recommend_agent(request)


@tool
def summary_tool(raw_response: str) -> str:
    """수집된 정보를 고객 응대에 적합한 최종 답변으로 정리합니다.

    Args:
        raw_response: 정리가 필요한 원본 응답

    Returns:
        포맷팅된 최종 고객 응대 답변
    """
    return polish_response(raw_response)


def create_orchestrator() -> Agent:
    # Prompt caching 활성화 — Strands 의 auto 전략은 system / tools / messages
    # 모두에 cachePoint 를 박아 줍니다 (deprecated 된 cache_prompt/cache_tools 보다
    # cache_config 권장. messages 영역까지 캐시 가능해야 멀티턴 대화에서 cacheRead
    # 가 잡힙니다).
    model = BedrockModel(
        model_id="us.anthropic.claude-sonnet-4-6",
        region_name=os.environ.get("AWS_REGION", "us-east-1"),
        cache_config=CacheConfig(strategy="auto"),
    )
    return Agent(
        model=model,
        system_prompt=SYSTEM_PROMPT,
        tools=[qa_tool, recommend_tool, summary_tool],
        callback_handler=None,
    )
