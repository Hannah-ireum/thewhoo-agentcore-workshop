#!/usr/bin/env python3
"""Lab 3 보조 — Gateway Semantic Tool Search 직접 호출 데모.

Gateway 가 searchType=SEMANTIC 으로 생성됐다면 빌트인 도구
`x_amz_bedrock_agentcore_search` 가 도구 목록에 함께 노출됩니다.
이 스크립트는 다음 흐름을 그대로 보여줍니다.

  1) MCPClient 로 Gateway 에 접속
  2) list_tools_sync() 로 등록된 도구 목록 출력
  3) `x_amz_bedrock_agentcore_search(query=...)` 직접 호출 →
     쿼리에 의미적으로 가까운 도구 후보를 받아옴
  4) (옵션) 후보 중 첫 번째 도구를 그대로 호출해 응답 확인

워크샵 도구는 4개뿐이라 실제 절감 효과를 체감하긴 어렵지만,
"의미 기반 후보 좁히기" 흐름은 수십 개 도구 환경에서도 동일합니다.

사용법 (src/ 와 동일한 venv 에서):
  python3 scripts/run-semantic-tool-search.py
  python3 scripts/run-semantic-tool-search.py "재고 빨리 알려줘"
  python3 scripts/run-semantic-tool-search.py --no-followup "프로모션 있나"

환경변수: AGENTCORE_GATEWAY_URL (필수)

출처:
  https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/gateway-using-mcp-semantic-search.html
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import uuid

from mcp.client.streamable_http import streamablehttp_client
from strands.tools.mcp.mcp_client import MCPClient

DEFAULT_QUERY = "건성 피부에 좋은 보습 제품 추천"


def _print_tool_summary(tool) -> None:
    name = getattr(tool, "tool_name", None) or getattr(tool, "name", "?")
    desc = (getattr(tool, "tool_spec", {}) or {}).get("description", "")
    if not desc:
        # MCPAgentTool 의 description 위치는 SDK 버전마다 다를 수 있음
        desc = str(getattr(tool, "description", "")) or ""
    desc = desc.replace("\n", " ").strip()
    if len(desc) > 90:
        desc = desc[:87] + "..."
    print(f"  - {name:50s}  {desc}")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("query", nargs="?", default=DEFAULT_QUERY)
    p.add_argument("--no-followup", action="store_true",
                   help="후보 첫 번째 도구를 자동 호출하지 않습니다.")
    args = p.parse_args()

    gw_url = os.environ.get("AGENTCORE_GATEWAY_URL", "").strip()
    if not gw_url:
        print("ERROR: AGENTCORE_GATEWAY_URL 환경변수가 비어 있습니다.")
        print("  eval \"$(./scripts/print-env.sh w001)\"  로 export 후 재시도하세요.")
        sys.exit(1)

    print(f"Gateway: {gw_url}")
    print(f"Query  : {args.query}")
    print()

    mcp_client = MCPClient(lambda: streamablehttp_client(gw_url))
    with mcp_client:
        tools = mcp_client.list_tools_sync()
        print(f"[1] 등록된 도구 ({len(tools)} 개)")
        for t in tools:
            _print_tool_summary(t)

        # SEMANTIC 활성화 확인
        names = []
        for t in tools:
            n = getattr(t, "tool_name", None) or getattr(t, "name", None)
            if n:
                names.append(n)
        if "x_amz_bedrock_agentcore_search" not in names:
            print()
            print("[!] 빌트인 search 도구가 보이지 않습니다.")
            print("    Gateway 가 searchType=SEMANTIC 으로 생성되었는지 확인하세요.")
            sys.exit(2)

        print()
        print(f"[2] x_amz_bedrock_agentcore_search 호출 (query={args.query!r})")
        result = mcp_client.call_tool_sync(
            tool_use_id=f"sem-{uuid.uuid4().hex[:8]}",
            name="x_amz_bedrock_agentcore_search",
            arguments={"query": args.query},
        )
        # MCPToolResult 의 content 는 보통 [{"type":"text","text":"..."}] 형태
        body_text = ""
        for c in getattr(result, "content", []) or []:
            t = (c.get("text") if isinstance(c, dict) else getattr(c, "text", None))
            if t:
                body_text = t
                break
        if not body_text:
            body_text = str(result)[:400]
        print("  status :", getattr(result, "status", None))
        print("  result :", body_text[:1200])
        print()

        # 후보 도구 후속 호출 (선택)
        if args.no_followup:
            return

        # search 결과에서 첫 번째 도구 이름 추출 시도
        first_candidate = None
        try:
            parsed = json.loads(body_text) if body_text.startswith("{") or body_text.startswith("[") else None
            if isinstance(parsed, list):
                if parsed and isinstance(parsed[0], dict):
                    first_candidate = parsed[0].get("toolName") or parsed[0].get("name")
            elif isinstance(parsed, dict):
                tools_field = parsed.get("tools") or parsed.get("results") or []
                if tools_field and isinstance(tools_field[0], dict):
                    first_candidate = tools_field[0].get("toolName") or tools_field[0].get("name")
        except Exception:
            first_candidate = None

        if not first_candidate:
            print("[3] 후속 호출 생략 — search 결과에서 도구 이름을 자동 식별하지 못했습니다.")
            print("    응답 포맷이 SDK/리전 버전마다 다를 수 있으므로 위 result 출력을 보고 수동 호출하세요.")
            return

        print(f"[3] 후속 호출: {first_candidate} (후보 중 첫 번째)")
        print("    실제 인자는 도구마다 다르므로 여기서는 빈 인자로만 호출 시도합니다.")
        try:
            f = mcp_client.call_tool_sync(
                tool_use_id=f"call-{uuid.uuid4().hex[:8]}",
                name=first_candidate,
                arguments={},
            )
            print("  status :", getattr(f, "status", None))
            for c in getattr(f, "content", []) or []:
                t = (c.get("text") if isinstance(c, dict) else getattr(c, "text", None))
                if t:
                    print("  result :", t[:600])
                    break
        except Exception as e:
            print(f"  followup ERROR: {type(e).__name__}: {e}")


if __name__ == "__main__":
    main()
