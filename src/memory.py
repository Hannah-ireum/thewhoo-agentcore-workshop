"""Lab 2 — AgentCore Memory: 4-strategy 세션 메모리 관리.

장기 strategy 구성 (create-memory.py 참고):
  - SUMMARIZATION      /summaries/{actorId}/{sessionId}/
  - USER_PREFERENCE    /preferences/{actorId}/
  - SEMANTIC           /facts/{actorId}/
  - EPISODIC           /episodes/{actorId}/{sessionId}/  +  reflection /episodes/{actorId}/
"""
import os
import json
from bedrock_agentcore.memory import MemoryClient

_memory_client: MemoryClient | None = None
_memory_id: str | None = None


def get_memory_client() -> MemoryClient:
    global _memory_client
    if _memory_client is None:
        _memory_client = MemoryClient(
            region_name=os.environ.get("AWS_REGION", "us-east-1")
        )
    return _memory_client


def get_memory_id() -> str:
    global _memory_id
    if _memory_id is None:
        _memory_id = os.environ.get("AGENTCORE_MEMORY_ID")
        if not _memory_id:
            raise ValueError("AGENTCORE_MEMORY_ID 환경변수를 설정하세요 (Lab 2 참고)")
    return _memory_id


def _parse_content(raw: str) -> str:
    """retrieve_memories content.text(JSON)에서 사람이 읽을 수 있는 텍스트 추출."""
    try:
        obj = json.loads(raw)
        return obj.get("preference") or obj.get("context") or raw
    except Exception:
        return raw


def retrieve_session_context(actor_id: str, session_id: str) -> str:
    """세션 시작 시 UserPreference + Summary + Episodic 메모리를 JIT 로드.

    - UserPreference: 사용자 선호 (항상 조회)
    - Summary: 이번 세션 대화 요약 (재접속 시 유용)
    - Episodic: 과거 상담 에피소드 (cross-session 참조)
    - Semantic 은 특정 질의에서만 조회하므로 여기 포함 X
    """
    client = get_memory_client()
    memory_id = get_memory_id()

    lines = []

    for ns, query, label in [
        (f"/preferences/{actor_id}/",              "피부타입 선호",   "선호"),
        (f"/summaries/{actor_id}/{session_id}/",   "이전 대화 요약",   "요약"),
        (f"/episodes/{actor_id}/",                 "과거 상담 기록",   "에피소드"),
    ]:
        try:
            for p in client.retrieve_memories(memory_id=memory_id, namespace=ns, query=query):
                text = _parse_content(p["content"]["text"])
                lines.append(f"[{label}] {text}")
        except Exception:
            # 해당 strategy 가 없어도 다른 것은 계속 진행
            pass

    return "\n".join(lines)


def save_turn(actor_id: str, session_id: str, user_msg: str, agent_msg: str) -> None:
    """대화 턴을 메모리에 저장합니다."""
    client = get_memory_client()
    memory_id = get_memory_id()

    client.create_event(
        memory_id=memory_id,
        actor_id=actor_id,
        session_id=session_id,
        messages=[
            (user_msg, "USER"),
            (agent_msg, "ASSISTANT"),
        ],
    )
