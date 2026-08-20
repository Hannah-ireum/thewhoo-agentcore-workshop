"""Lab 4 — Summary Agent: 최종 답변 톤 정리 및 포맷팅."""
import os
from strands import Agent
from strands.models import BedrockModel

SYSTEM_PROMPT = """당신은 더후(The History of Whoo)의 친절한 응대 전문가입니다.
다른 에이전트가 수집한 정보를 받아, 고객에게 전달할 최종 답변으로 다듬어주세요.
- 핵심 정보는 유지하고 중복은 제거하세요
- 친근하고 전문적인 뷰티 상담 말투를 사용하세요
- 필요시 이모지를 적절히 활용하세요
- 200자 이내로 간결하게 작성하세요"""


def create_summary_agent() -> Agent:
    model = BedrockModel(
        model_id="us.anthropic.claude-haiku-4-5-20251001-v1:0",
        region_name=os.environ.get("AWS_REGION", "us-east-1"),
    )
    return Agent(
        model=model,
        system_prompt=SYSTEM_PROMPT,
        tools=[],
        callback_handler=None,
    )


def polish_response(raw_response: str, agent: Agent | None = None) -> str:
    """Lab 4 에서 Orchestrator 도구로 호출되는 진입점."""
    if agent is None:
        agent = create_summary_agent()
    prompt = f"다음 내용을 고객 응대 답변으로 정리해주세요:\n\n{raw_response}"
    result = agent(prompt)
    return str(result)
