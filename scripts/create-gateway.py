#!/usr/bin/env python3
"""Lab 3 — Gateway + 4 Lambda targets 생성.

Pre-Lab 의 onestop 은 인프라만 만들고 Gateway 는 건드리지 않습니다.
이 스크립트가 Gateway 1개 + Lambda target 4개를 생성하고
`AGENTCORE_GATEWAY_URL` 을 출력합니다.

이미 `thewhoo-gateway-<pid>` 가 존재하면 재사용합니다 (idempotent).

Usage (Code Editor 터미널):
  cd ~/thewhoo-agentcore-workshop
  python3 scripts/create-gateway.py

환경변수 요구:
  PARTICIPANT_ID, AWS_REGION
"""

from __future__ import annotations

import json
import os
import sys
import time

import boto3
import botocore.exceptions


PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def find_existing_gateway(client, name: str) -> tuple[str, str] | None:
    """list_gateways 응답에는 gatewayUrl 이 없으므로 get_gateway 로 다시 조회."""
    try:
        resp = client.list_gateways()
    except botocore.exceptions.ClientError as e:
        print(f"[ERROR] list_gateways 실패: {e}")
        sys.exit(1)

    for gw in resp.get("items", []) or []:
        if gw.get("name") == name:
            gw_id = gw["gatewayId"]
            detail = client.get_gateway(gatewayIdentifier=gw_id)
            return gw_id, detail["gatewayUrl"]
    return None


def get_agent_runtime_role_arn(pid: str, region: str) -> str:
    cfn = boto3.client("cloudformation", region_name=region)
    outs = cfn.describe_stacks(StackName=f"thewhoo-{pid}")["Stacks"][0]["Outputs"]
    for o in outs:
        if o["OutputKey"] == "AgentRuntimeRoleArn":
            return o["OutputValue"]
    raise SystemExit("AgentRuntimeRoleArn 을 CFN Outputs 에서 찾을 수 없음.")


def openapi_to_tool_schema(spec: dict) -> list[dict]:
    tools = []
    for path_item in spec.get("paths", {}).values():
        for method, op in path_item.items():
            if method not in ("get", "post", "put", "patch", "delete"):
                continue
            tool = {
                "name": op["operationId"],
                "description": op.get("description") or op.get("summary", ""),
            }
            rb = op.get("requestBody", {}).get("content", {}).get("application/json", {})
            if "schema" in rb:
                tool["inputSchema"] = rb["schema"]
            tools.append(tool)
    return tools


def create_gateway(client, name: str, role_arn: str) -> tuple[str, str]:
    print(f"[1/2] Gateway 생성: {name}")
    resp = client.create_gateway(
        name=name,
        description=f"뷰티 챗봇용 Gateway ({name})",
        roleArn=role_arn,
        protocolType="MCP",
        protocolConfiguration={"mcp": {"searchType": "SEMANTIC"}},
        authorizerType="NONE",
    )
    gw_id = resp["gatewayId"]
    gw_url = resp["gatewayUrl"]

    # READY 대기
    for _ in range(30):
        s = client.get_gateway(gatewayIdentifier=gw_id)["status"]
        if s == "READY":
            break
        time.sleep(3)
    else:
        raise SystemExit(f"Gateway 가 READY 로 넘어가지 않음: {gw_id}")

    print(f"      ✓ GATEWAY_URL = {gw_url}")
    return gw_id, gw_url


def create_targets(client, gw_id: str, pid: str, account: str, region: str) -> None:
    print(f"[2/2] Lambda target 4종 등록")

    targets = {
        "product-search":     f"arn:aws:lambda:{region}:{account}:function:thewhoo-product-search-{pid}",
        "recommend-products": f"arn:aws:lambda:{region}:{account}:function:thewhoo-recommend-{pid}",
        "check-stock":        f"arn:aws:lambda:{region}:{account}:function:thewhoo-check-stock-{pid}",
        "get-promotion":      f"arn:aws:lambda:{region}:{account}:function:thewhoo-get-promotion-{pid}",
    }
    schemas = {k: f"lambdas/{k.replace('-', '_')}/openapi.json" for k in targets}

    # 기존 target 목록
    existing = {
        t["name"]
        for t in client.list_gateway_targets(gatewayIdentifier=gw_id).get("items", []) or []
    }

    for name, lambda_arn in targets.items():
        if name in existing:
            print(f"      ✓ {name} (이미 존재)")
            continue
        spec_path = os.path.join(PROJECT_ROOT, schemas[name])
        with open(spec_path) as f:
            spec = json.load(f)
        client.create_gateway_target(
            gatewayIdentifier=gw_id,
            name=name,
            description=spec["info"].get("description", name)[:200],
            targetConfiguration={
                "mcp": {
                    "lambda": {
                        "lambdaArn": lambda_arn,
                        "toolSchema": {"inlinePayload": openapi_to_tool_schema(spec)},
                    }
                }
            },
            credentialProviderConfigurations=[
                {"credentialProviderType": "GATEWAY_IAM_ROLE"}
            ],
        )
        print(f"      ✓ {name} (생성됨)")


def main() -> None:
    pid = os.environ.get("PARTICIPANT_ID")
    if not pid:
        print("PARTICIPANT_ID 환경변수가 없습니다.", file=sys.stderr)
        sys.exit(1)
    region = os.environ.get("AWS_REGION", "us-east-1")
    account = boto3.client("sts").get_caller_identity()["Account"]
    gateway_name = f"thewhoo-gateway-{pid}"

    client = boto3.client("bedrock-agentcore-control", region_name=region)

    # 이미 있으면 재사용
    existing = find_existing_gateway(client, gateway_name)
    if existing:
        gw_id, gw_url = existing
        print(f"[알림] 이미 '{gateway_name}' 존재 (재사용): {gw_id}")
    else:
        role_arn = get_agent_runtime_role_arn(pid, region)
        gw_id, gw_url = create_gateway(client, gateway_name, role_arn)

    create_targets(client, gw_id, pid, account, region)

    print()
    print("=" * 60)
    print(f"AGENTCORE_GATEWAY_URL={gw_url}")
    print("=" * 60)
    print()
    print("다음 명령을 터미널에 복사해 환경변수를 설정하세요:")
    print()
    print(f"  export AGENTCORE_GATEWAY_URL={gw_url}")


if __name__ == "__main__":
    main()
