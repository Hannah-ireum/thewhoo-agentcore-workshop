"""Lab 3 — Recommend Agent: Strands Agent + AgentCore Gateway (MCP over HTTP)."""
import json
import os
from strands import Agent
from strands.models import BedrockModel
from strands.tools.mcp import MCPClient
from mcp.client.streamable_http import streamablehttp_client

SYSTEM_PROMPT = """당신은 더후(The History of Whoo)의 상품 추천·검색 도우미입니다.
주어진 도구를 상황에 맞게 선택하여 사용자 질문에 답하세요.

도구 선택 기준:
- 단순 키워드/카테고리 검색 → product-search___product_search
- 피부타입·고민 기반 개인화 추천 → recommend-products___recommend_products (사용자 프로필 반드시 활용)
- 특정 상품의 재고 → check-stock___check_stock
- 현재 진행 중인 할인/증정/쿠폰 → get-promotion___get_promotion

도구 이름은 위에 적힌 전체 이름(`<target>___<tool>`)을 그대로 사용하세요.
Gateway 가 target 이름을 prefix 로 붙여 노출하므로, prefix 를 뺀 짧은 이름으로
호출하면 "tool not found in registry" 로 실패하고 재시도가 발생합니다.

답변은 한국어 존댓말, 핵심 정보 위주로 간결하게.
"""


def _get_mcp_client(gateway_url: str | None = None) -> MCPClient:
    url = gateway_url or os.environ.get("AGENTCORE_GATEWAY_URL", "")
    if not url:
        raise ValueError("AGENTCORE_GATEWAY_URL 환경변수를 설정하세요 (Lab 3 참고)")
    return MCPClient(lambda: streamablehttp_client(url))


class _VerboseHandler:
    """도구 호출 시작/결과를 한 줄씩 출력.

    Strands callback 은 스트리밍 토큰마다 current_tool_use 가 계속 갱신되므로,
    같은 tool_use_id 는 한 번만 출력하고, 입력이 완성된(toolUse 블록이 최종 assistant
    메시지에 들어간) 시점의 input 을 찍습니다.
    """

    def __init__(self):
        self._printed_calls: set[str] = set()
        self._printed_results: set[str] = set()

    def __call__(self, **kwargs) -> None:
        msg = kwargs.get("message")
        if not isinstance(msg, dict):
            return

        for block in msg.get("content", []) or []:
            if not isinstance(block, dict):
                continue

            tool_use = block.get("toolUse")
            if tool_use:
                tu_id = tool_use.get("toolUseId") or tool_use.get("id") or ""
                if tu_id and tu_id not in self._printed_calls:
                    self._printed_calls.add(tu_id)
                    args = tool_use.get("input", {})
                    args_str = json.dumps(args, ensure_ascii=False)
                    if len(args_str) > 300:
                        args_str = args_str[:300] + "…"
                    print(f"  → {tool_use.get('name', '?')}  {args_str}", flush=True)
                continue

            tool_result = block.get("toolResult")
            if tool_result:
                tu_id = tool_result.get("toolUseId") or ""
                if tu_id and tu_id not in self._printed_results:
                    self._printed_results.add(tu_id)
                    status = tool_result.get("status", "?")
                    body_preview = _summarize_result(tool_result)
                    print(f"  ← result [{status}]  {body_preview}", flush=True)


def _summarize_result(tool_result: dict) -> str:
    """tool result body 에서 사람이 보기 좋은 짧은 요약을 추출."""
    for c in tool_result.get("content", []) or []:
        if isinstance(c, dict) and "text" in c:
            raw = c["text"]
            # Lambda 가 {"statusCode":200,"body":"..."} 로 감싸 돌려줄 때
            try:
                outer = json.loads(raw)
                if isinstance(outer, dict) and "body" in outer and isinstance(outer["body"], str):
                    inner = json.loads(outer["body"])
                    return _compact_summary(inner)
                return _compact_summary(outer)
            except (json.JSONDecodeError, TypeError):
                return raw[:200]
    return ""


def _compact_summary(obj) -> str:
    """dict 안에 count / products / promotions / available 같은 핵심 키가 있으면 요약."""
    if not isinstance(obj, dict):
        return str(obj)[:200]
    if "available" in obj:
        return f"available={obj['available']}, eta={obj.get('eta')}, {obj.get('brand', '')} {obj.get('name', '')}"
    if "count" in obj and "products" in obj:
        names = ", ".join(p.get("name", "?") for p in obj.get("products", [])[:3])
        return f"count={obj['count']}, products=[{names}]"
    if "count" in obj and "promotions" in obj:
        titles = ", ".join(p.get("title", "?") for p in obj.get("promotions", [])[:2])
        return f"count={obj['count']}, promotions=[{titles}]"
    return json.dumps(obj, ensure_ascii=False)[:200]


def ask_recommend_agent(
    request: str,
    gateway_url: str | None = None,
    verbose: bool = False,
) -> str:
    """MCP 세션을 새로 열고 에이전트를 1회 호출합니다 (Lab 4 Orchestrator 진입점).

    매 호출마다 새 Agent 를 만들기 때문에 대화 이력은 보존되지 않습니다.
    대화형(REPL) 에서 이력을 이어가려면 chat_session() 을 사용하세요.
    verbose=True 를 주면 각 도구 호출과 결과 일부를 stdout 에 출력합니다.
    """
    model = BedrockModel(
        model_id="us.anthropic.claude-haiku-4-5-20251001-v1:0",
        region_name=os.environ.get("AWS_REGION", "us-east-1"),
    )
    mcp_client = _get_mcp_client(gateway_url)
    handler = _VerboseHandler() if verbose else None

    # MCP 세션을 유지한 채로 Agent를 생성하고 호출해야 합니다.
    with mcp_client:
        agent = Agent(
            model=model,
            system_prompt=SYSTEM_PROMPT,
            tools=mcp_client.list_tools_sync(),
            callback_handler=handler,
        )
        result = agent(request)
    return str(result)


class chat_session:
    """대화형(REPL)에서 대화 이력을 유지하며 여러 턴을 이어갑니다.

    Strands Agent 를 한 번만 만들고 여러 번 __call__ 해야 `messages` 이력이
    누적됩니다. MCP 세션도 with 블록 내내 열린 상태로 유지됩니다.

    Usage:
        with chat_session(verbose=True) as chat:
            print(chat("장뇌삼 함유 상품 있어?"))
            print(chat("재고 확인해줘"))   # 이전 턴 참조 가능
    """

    def __init__(self, gateway_url: str | None = None, verbose: bool = False):
        self._model = BedrockModel(
            model_id="us.anthropic.claude-haiku-4-5-20251001-v1:0",
            region_name=os.environ.get("AWS_REGION", "us-east-1"),
        )
        self._mcp_client = _get_mcp_client(gateway_url)
        self._handler = _VerboseHandler() if verbose else None
        self._agent: Agent | None = None

    def __enter__(self) -> "chat_session":
        self._mcp_client.__enter__()
        self._agent = Agent(
            model=self._model,
            system_prompt=SYSTEM_PROMPT,
            tools=self._mcp_client.list_tools_sync(),
            callback_handler=self._handler,
        )
        return self

    def __exit__(self, *exc) -> None:
        self._mcp_client.__exit__(*exc)

    def __call__(self, request: str) -> str:
        assert self._agent is not None, "chat_session 은 with 블록 안에서만 사용하세요"
        return str(self._agent(request))


def create_recommend_agent(gateway_url: str | None = None):
    """Lab 4 호환용 — MCPClient context를 반환합니다."""
    return _get_mcp_client(gateway_url)
