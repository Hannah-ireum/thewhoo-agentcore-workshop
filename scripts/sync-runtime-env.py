#!/usr/bin/env python3
"""Lab 5 보조 — 배포된 Runtime 의 environmentVariables 를 현재 셸 값으로 동기화.

`agentcore deploy --env KEY=$VAL` 가 빈 값으로 박힐 수 있는 케이스(셸 변수가
비어 있던 시점에 deploy 한 경우)나, 환경변수를 추가/수정하고 싶을 때 사용.

UpdateAgentRuntime API 로 environmentVariables 만 수정하고, 다른 설정은
GetAgentRuntime 응답을 그대로 다시 넣습니다 (필수 필드라 생략 불가).

사용법:
  cd ~/thewhoo-agentcore-workshop && source .venv/bin/activate
  eval "$(./scripts/print-env.sh w001)"
  python3 scripts/sync-runtime-env.py                       # 기본 agent (config 의 default)
  python3 scripts/sync-runtime-env.py thewhoo_chat-zDiS2wEqSx
  python3 scripts/sync-runtime-env.py --extra FOO=bar       # 추가 환경변수도 함께 박기

요건:
  - AGENTCORE_MEMORY_ID, AGENTCORE_GATEWAY_URL, KB_ID 가 환경변수로 export 돼 있어야 함
"""
from __future__ import annotations

import argparse
import os
import sys

import boto3


REQUIRED = ["KB_ID", "AGENTCORE_MEMORY_ID", "AGENTCORE_GATEWAY_URL"]


def _resolve_runtime_id(client, explicit: str | None) -> str:
    if explicit:
        return explicit
    # 가장 최근 thewhoo_chat 계열 Runtime 자동 선택
    resp = client.list_agent_runtimes()
    items = resp.get("agentRuntimes") or resp.get("items") or []
    candidates = [
        r for r in items
        if "thewhoo" in (r.get("agentRuntimeName") or "").lower()
    ]
    if not candidates:
        sys.exit("[ERROR] thewhoo 계열 Runtime 을 찾지 못했습니다. ID 를 직접 지정하세요.")
    candidates.sort(key=lambda r: r.get("createdAt", 0), reverse=True)
    return candidates[0].get("agentRuntimeId") or candidates[0].get("id")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("runtime_id", nargs="?", default=None,
                   help="Runtime ID. 생략 시 thewhoo 계열 중 최신을 사용합니다.")
    p.add_argument("--extra", action="append", default=[],
                   help="추가 환경변수 (KEY=VALUE 형식). 여러 번 지정 가능.")
    p.add_argument("--region", default=os.environ.get("AWS_REGION", "us-east-1"))
    args = p.parse_args()

    missing = [k for k in REQUIRED if not os.environ.get(k)]
    if missing:
        sys.exit(
            f"[ERROR] 환경변수가 비어 있습니다: {', '.join(missing)}\n"
            "  eval \"$(./scripts/print-env.sh w001)\" 를 먼저 실행하세요."
        )

    client = boto3.client("bedrock-agentcore-control", region_name=args.region)
    rid = _resolve_runtime_id(client, args.runtime_id)
    print(f"target runtime: {rid}")

    current = client.get_agent_runtime(agentRuntimeId=rid)
    env = dict(current.get("environmentVariables") or {})

    # 표준 4종 동기화
    env["KB_ID"] = os.environ["KB_ID"]
    env["AGENTCORE_MEMORY_ID"] = os.environ["AGENTCORE_MEMORY_ID"]
    env["AGENTCORE_GATEWAY_URL"] = os.environ["AGENTCORE_GATEWAY_URL"]
    env["AWS_REGION"] = args.region

    # --extra 처리
    for kv in args.extra:
        if "=" not in kv:
            sys.exit(f"[ERROR] --extra '{kv}' 형식이 잘못됨. KEY=VALUE 사용.")
        k, v = kv.split("=", 1)
        env[k] = v

    resp = client.update_agent_runtime(
        agentRuntimeId=rid,
        agentRuntimeArtifact=current["agentRuntimeArtifact"],
        networkConfiguration=current["networkConfiguration"],
        roleArn=current["roleArn"],
        environmentVariables=env,
    )

    print(f"status: {resp.get('status')}")
    print("environmentVariables now:")
    for k, v in sorted(env.items()):
        masked = (v[:60] + "…") if v and len(v) > 60 else v
        print(f"  {k:30s} = {masked or '(empty)'}")
    print()
    print("적용까지 보통 30~60초 걸립니다. 그 후 agentcore invoke 로 재시도하세요.")


if __name__ == "__main__":
    main()
