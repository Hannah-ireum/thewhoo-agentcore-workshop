"""Lab 1 — Q&A Agent: Strands Agent + Bedrock Knowledge Base RAG."""
import os
from strands import Agent
from strands.models import BedrockModel
from tools.kb_retrieve import kb_retrieve

SYSTEM_PROMPT = """당신은 더후(The History of Whoo) 전문 상담사입니다.
Bedrock Knowledge Base(KB) 의 검색 결과를 우선 사용해 정확하게 답변합니다.

KB 에 담긴 것은 정적인 상품 정보(성분·사용법·가격·피부타입·특징)입니다.

[답변 원칙]
1. KB 검색 결과에 명시된 사실은 그대로 인용하고 출처 상품명을 함께 보여 주세요.
2. KB 결과에서 직접 답을 못 찾았더라도, 일반적으로 잘 알려진 화장품 성분의 효능
   (예: 세라마이드는 피부 장벽 강화에 도움)은 **신뢰할 수 있는 범위 안에서 간결하게**
   설명해 주세요. "기술적 오류", "데이터베이스 오류" 같은 시스템 사과 표현은
   사용하지 않습니다.
3. 효능을 단정하지 말고 "도움이 될 수 있습니다" 같은 부드러운 어조를 사용하세요.
   의료적 치료·완치·진단 표현은 금지합니다.
4. 가능하면 KB 에서 같이 추천할 수 있는 상품을 1~2개 함께 안내하세요.

[KB 범위 밖 주제 — 추측 금지]
다음 주제는 KB 만으로는 정확히 답할 수 없으므로, 별도 서비스(Gateway 도구)
가 필요하다는 사실을 자연스럽게 안내하세요. 사과조 fallback 은 사용하지 말 것.
- 재고 유무 / 재고 수량 / 입고 예정일 / 배송 소요시간
- 실시간 할인·쿠폰·프로모션 진행 여부
- 주문·결제·환불·배송 조회

상품 데이터가 KB 에 존재한다는 사실은 곧 "재고가 있다" 는 뜻이 아닙니다.

답변은 친근하고 전문적인 한국어 존댓말로, 추측 없이 작성하세요."""


def create_qa_agent() -> Agent:
    model = BedrockModel(
        model_id="us.anthropic.claude-haiku-4-5-20251001-v1:0",
        region_name=os.environ.get("AWS_REGION", "us-east-1"),
    )
    return Agent(
        model=model,
        system_prompt=SYSTEM_PROMPT,
        tools=[kb_retrieve],
        callback_handler=None,  # 스트리밍 중간 출력 억제. 최종 결과만 str() 로 받습니다.
    )


def ask_qa_agent(question: str, agent: Agent | None = None) -> str:
    """Lab 4 에서 Orchestrator 도구로 호출되는 진입점."""
    if agent is None:
        agent = create_qa_agent()
    result = agent(question)
    return str(result)
