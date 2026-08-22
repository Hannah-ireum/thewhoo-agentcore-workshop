"""Lab 5 — AgentCore Runtime 배포용 진입점.

BedrockAgentCoreApp 은 entrypoint 의 반환값을 자동으로 {"response": ...}
JSON 으로 감쌉니다. 따라서 entrypoint 가 dict 를 직접 반환하면 외부에서는
response 키 안에 dict 가 문자열로 박혀 보이게 됩니다. 가독성을 위해 본문만
문자열로 반환하고, session_id 는 응답 헤더가 아닌 본문 prefix 로 첨부하지
않습니다 (호출자가 같은 session_id 를 다음 호출에 그대로 전달하면 충분).
"""
import sys, os, uuid
sys.path.insert(0, os.path.dirname(__file__))

# Strands SDK 의 LLM/tool span 을 OTEL 로 emit 하도록 telemetry 초기화.
# aws-opentelemetry-distro 의 auto-instrumentation 만으로도 동작하지만,
# 명시적으로 한 번 더 setup 해 둬야 일부 환경에서 BatchSpanProcessor 가
# 안정적으로 붙습니다 (Strands 공식 가이드 권장 방식).
from strands.telemetry import StrandsTelemetry
StrandsTelemetry().setup_otlp_exporter()

from bedrock_agentcore import BedrockAgentCoreApp
from agents.orchestrator import create_orchestrator
from memory import retrieve_session_context, save_turn

# BedrockAgentCoreContext 는 SDK 버전에 따라 module path 가 다르거나 entrypoint
# 호출 컨텍스트 밖에서 raise 할 수 있어 안전하게 try/except 로 감쌉니다.
try:
    from bedrock_agentcore.runtime.context import BedrockAgentCoreContext  # noqa: F401
    _HAS_CONTEXT = True
except Exception:
    _HAS_CONTEXT = False


def _get_runtime_session_id() -> str | None:
    if not _HAS_CONTEXT:
        return None
    try:
        return BedrockAgentCoreContext.get_session_id()
    except Exception:
        return None


app = BedrockAgentCoreApp()
orchestrator = create_orchestrator()

ACTOR_ID = "runtime-user"


@app.entrypoint
def thewhoo_chat(payload: dict) -> str:
    """AgentCore Runtime 호출 핸들러. 답변 본문(str) 만 반환합니다.

    payload 의 메시지 키는 **호출 경로마다 다릅니다** (실측 확인):
      - `agentcore invoke "..."`  (새 AgentCore CLI) → {"prompt": "..."}
      - boto3 InvokeAgentRuntime  (워크샵 스크립트)  → {"message": "..."}
      공식 Get started 문서의 boto3 예시도 {"prompt": ...} 를 씁니다.
    두 키를 모두 받아야 CLI 와 스크립트 양쪽에서 동작합니다. `prompt` 만
    받으면 run-golden-eval.py 가, `message` 만 받으면 agentcore invoke 가
    "메시지를 입력해주세요." 로 되돌아옵니다.

    session_id 는 다음 우선순위로 결정합니다:
      1. AgentCore Runtime 의 X-Amzn-Bedrock-AgentCore-Runtime-Session-Id header
         (agentcore invoke --session-id <id> 또는 boto3 의 runtimeSessionId)
      2. payload 안의 session_id (워크샵 셸 명령 호환)
      3. 새 UUID (둘 다 없을 때)
    """
    user_message = (
        payload.get("message")
        or payload.get("prompt")
        or ""
    )
    session_id = (
        _get_runtime_session_id()
        or payload.get("session_id")
        or str(uuid.uuid4())
    )

    if not user_message:
        return "메시지를 입력해주세요."

    context = retrieve_session_context(ACTOR_ID, session_id)

    prompt = user_message
    if context:
        prompt = f"[이전 대화 맥락]\n{context}\n\n[현재 요청]\n{user_message}"

    response = orchestrator(prompt)
    response_str = str(response)

    save_turn(ACTOR_ID, session_id, user_message, response_str)

    return response_str


if __name__ == "__main__":
    app.run()
