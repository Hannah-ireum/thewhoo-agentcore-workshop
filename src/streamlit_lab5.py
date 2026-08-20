"""Lab 5 Streamlit 데모 — 배포된 AgentCore Runtime 원격 호출."""
import json
import os

import boto3
import streamlit as st

from ui.chat import render_chat, render_header, reset_session

st.set_page_config(page_title="Lab 5 — 원격 호출", page_icon="☁️", layout="centered")

render_header(
    title="배포된 에이전트에 원격 호출",
    subtitle="Lab 5에서 AgentCore Runtime에 배포한 agent를 HTTPS로 호출",
    lab_tag="LAB 5",
)

RUNTIME_ARN = os.environ.get("AGENT_RUNTIME_ARN", "")
REGION = os.environ.get("AWS_REGION", "us-east-1")

if not RUNTIME_ARN:
    st.error(
        "환경변수 `AGENT_RUNTIME_ARN`이 설정되지 않았습니다.\n\n"
        "`agentcore status` 출력의 Agent ARN을 설정하세요:\n"
        "```bash\n"
        "export AGENT_RUNTIME_ARN=arn:aws:bedrock-agentcore:...:runtime/thewhoo_chat-xxx\n"
        "```"
    )
    st.stop()


@st.cache_resource
def _client():
    return boto3.client("bedrock-agentcore", region_name=REGION)


with st.sidebar:
    st.subheader("원격 엔드포인트")
    st.caption("배포된 Runtime ARN")
    st.code(RUNTIME_ARN, language=None)

    st.divider()
    st.subheader("로컬과 달라진 점")
    st.markdown(
        "- **SigV4 인증**으로 HTTPS 호출\n"
        "- AWS 관리 **OTel 계측**으로 trace 자동 수집 (Lab 6)\n"
        "- 여러 동시 사용자 처리 (stateless scale-out)"
    )

    if st.button("대화 초기화"):
        reset_session("lab5")
        st.rerun()


SCENARIOS = [
    ("Q&A", "비첩 자생 수분크림은 어떤 피부에 좋아?"),
    ("추천", "건성 피부에 맞는 보습 세럼 추천해줘"),
    ("요약", "현재 진행 중인 스킨케어 프로모션 정리해줘"),
]


def handler(user_msg: str, session_id: str) -> tuple[str, dict]:
    resp = _client().invoke_agent_runtime(
        agentRuntimeArn=RUNTIME_ARN,
        runtimeSessionId=session_id,
        payload=json.dumps(
            {
                "user_id": "streamlit-user",
                "session_id": session_id,
                "message": user_msg,
            }
        ),
    )
    body = resp["response"].read()
    # entrypoint 가 str 을 반환하면 Runtime 이 JSON-encoded string 으로 감싸서
    # 응답 본문이 dict 가 아닌 단순 string 으로 올 수 있습니다. 두 케이스 모두 처리.
    try:
        data = json.loads(body)
        if isinstance(data, dict):
            response = data.get("response", str(data))
        elif isinstance(data, str):
            response = data
        else:
            response = str(data)
    except Exception:
        response = body.decode("utf-8", errors="replace")
    return response, {}


render_chat(
    handler=handler,
    state_key="lab5",
    placeholder="배포된 에이전트에게 물어보세요...",
    scenarios=SCENARIOS,
)
