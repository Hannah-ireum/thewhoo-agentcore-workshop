"""Lab 1 — Bedrock Knowledge Base retrieve 도구."""
import os
import boto3
from strands import tool

_client = None


def _get_client():
    global _client
    if _client is None:
        _client = boto3.client(
            "bedrock-agent-runtime",
            region_name=os.environ.get("AWS_REGION", "us-east-1"),
        )
    return _client


@tool
def kb_retrieve(query: str) -> str:
    """Bedrock Knowledge Base에서 뷰티 상품 정보를 검색합니다.

    Args:
        query: 검색할 질문이나 키워드

    Returns:
        관련 상품 정보 텍스트 (최대 3개 청크)
    """
    kb_id = os.environ.get("KB_ID")
    if not kb_id:
        raise ValueError("KB_ID 환경변수를 설정하세요 (Lab 0 참고)")

    response = _get_client().retrieve(
        knowledgeBaseId=kb_id,
        retrievalQuery={"text": query},
        retrievalConfiguration={
            "vectorSearchConfiguration": {"numberOfResults": 3}
        },
    )

    results = response.get("retrievalResults", [])
    if not results:
        return "관련 상품 정보를 찾을 수 없습니다."

    chunks = []
    for r in results:
        text = r.get("content", {}).get("text", "")
        score = r.get("score", 0)
        if text:
            chunks.append(f"[관련도: {score:.2f}]\n{text}")

    return "\n\n---\n\n".join(chunks)
