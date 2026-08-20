"""Lab 3 Streamlit 데모 — Gateway + MCP 도구 호출 시각화."""
import os

import streamlit as st
from mcp.client.streamable_http import streamablehttp_client
from strands import Agent
from strands.models import BedrockModel
from strands.tools.mcp import MCPClient

from agents.recommend_agent import SYSTEM_PROMPT
from ui.chat import (
    extract_tool_trace,
    render_chat,
    render_header,
    reset_session,
)

st.set_page_config(page_title="Lab 3 — 도구 호출", page_icon="🔧", layout="centered")

render_header(
    title="외부 도구를 호출하는 챗봇",
    subtitle="AgentCore Gateway로 Lambda 4종을 MCP 도구로 등록 · Agent가 자율 선택",
    lab_tag="LAB 3",
)

GATEWAY_URL = os.environ.get("AGENTCORE_GATEWAY_URL", "")
if not GATEWAY_URL:
    st.error("환경변수 `AGENTCORE_GATEWAY_URL`이 설정되지 않았습니다. Lab 3 문서 확인하세요.")
    st.stop()


# MCP 세션과 Agent를 Streamlit 세션 수명 동안 한번만 초기화
def _init_agent():
    mcp_client = MCPClient(lambda: streamablehttp_client(GATEWAY_URL))
    mcp_client.__enter__()  # context 수동 오픈 — Streamlit rerun 간 유지
    tools = mcp_client.list_tools_sync()
    model = BedrockModel(
        model_id="us.anthropic.claude-haiku-4-5-20251001-v1:0",
        region_name=os.environ.get("AWS_REGION", "us-east-1"),
    )
    agent = Agent(model=model, system_prompt=SYSTEM_PROMPT, tools=tools)
    return mcp_client, agent, [t.tool_name for t in tools]


if "lab3_agent" not in st.session_state:
    _mcp, _agent, _tool_names = _init_agent()
    st.session_state.lab3_mcp = _mcp
    st.session_state.lab3_agent = _agent
    st.session_state.lab3_tool_names = _tool_names

with st.sidebar:
    st.subheader("연결된 도구")

    builtin_tools = [
        n for n in st.session_state.lab3_tool_names if n.startswith("x_amz_")
    ]
    lambda_tools = [
        n for n in st.session_state.lab3_tool_names if not n.startswith("x_amz_")
    ]

    if builtin_tools:
        st.markdown("🔍 **Semantic Search 활성화**")
        st.caption("Gateway가 도구 검색용 빌트인 도구를 자동 추가")
        for name in builtin_tools:
            st.markdown(f"- `{name}` *(builtin)*")
        st.divider()

    st.caption("Lambda target 도구")
    for name in lambda_tools:
        st.markdown(f"- `{name}`")

    st.divider()
    st.subheader("Agent 동작")
    st.markdown(
        f"Agent가 질문을 분석해 {len(lambda_tools)}개 도구 중 **어떤 것을 호출할지 자동 결정**합니다. "
        "여러 도구를 순차 호출해서 답을 조합하기도 합니다."
    )
    if builtin_tools:
        st.info(
            "도구 수가 많아지면 Agent는 먼저 `x_amz_bedrock_agentcore_search`로 "
            "관련 도구를 찾은 뒤 호출합니다."
        )

    if st.button("대화 초기화"):
        reset_session("lab3")
        st.rerun()


SCENARIOS = [
    ("키워드 검색", "5만원 이하 향수 뭐 있어?"),
    ("개인화 추천", "건성 피부에 좋은 보습 세럼 추천해줘"),
    ("복합 질의", "민감성인데 진정에 좋은 거 + 재고 + 프로모션까지 알려줘"),
]


def handler(user_msg: str, session_id: str) -> tuple[str, dict]:
    result = st.session_state.lab3_agent(user_msg)
    return str(result), {"trace": extract_tool_trace(result)}


render_chat(
    handler=handler,
    state_key="lab3",
    placeholder="상품 검색 · 추천 · 재고 · 프로모션 무엇이든 물어보세요...",
    scenarios=SCENARIOS,
    show_trace=True,
)
