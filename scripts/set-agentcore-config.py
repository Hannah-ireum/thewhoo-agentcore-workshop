#!/usr/bin/env python3
"""agentcore.json 의 runtime 설정을 이 워크샵 구조에 맞게 채웁니다 (Lab 5).

새 AgentCore CLI 의 `agentcore create` 는 app/<name>/main.py 를 기본 엔트리포인트로
잡습니다. 이 워크샵은 Lab 1-4 에서 만든 src/app.py 를 그대로 배포하므로
codeLocation / entrypoint / runtimeVersion 을 바꾸고, KB·Memory·Gateway ID 를
envVars 로 주입합니다.

전제 — 아래 환경변수가 설정돼 있어야 합니다 (print-env.sh 로 채웁니다):
  KB_ID, AGENTCORE_MEMORY_ID, AGENTCORE_GATEWAY_URL

Usage:
  eval "$(./scripts/print-env.sh w001)"
  python3 scripts/set-agentcore-config.py
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import boto3

CONFIG = Path("agentcore/agentcore.json")
REQUIRED = ["KB_ID", "AGENTCORE_MEMORY_ID", "AGENTCORE_GATEWAY_URL"]


def main() -> int:
    if not CONFIG.exists():
        sys.exit(
            f"[ERROR] {CONFIG} 가 없습니다.\n"
            "        먼저 프로젝트를 만드세요:\n"
            "          agentcore create --name ThewhooChat --framework Strands \\\n"
            "            --protocol HTTP --model-provider Bedrock --memory none --build CodeZip"
        )

    missing = [k for k in REQUIRED if not os.environ.get(k)]
    if missing:
        sys.exit(
            f"[ERROR] 환경변수 누락: {', '.join(missing)}\n"
            '        eval "$(./scripts/print-env.sh <참가자ID>)" 를 먼저 실행하세요.'
        )

    data = json.loads(CONFIG.read_text())
    runtimes = data.get("runtimes") or []
    if not runtimes:
        sys.exit("[ERROR] agentcore.json 에 runtimes 항목이 없습니다.")

    # ── executionRoleArn ────────────────────────────────────────────
    # 생략하면 CDK 가 role 을 자동 생성하는데, 그 role 은 모델 호출 권한만
    # 갖습니다 (실측: bedrock:InvokeModel + bedrock-agentcore:*ConfigurationBundle*
    # + logs/xray). Memory·KB·Gateway 권한이 없어서 첫 invoke 가 500 으로
    # 죽습니다:
    #   AccessDeniedException ... when calling the CreateEvent operation
    # `--memory none` 으로 만들었으니 CDK 가 Memory 권한을 줄 이유가 없고,
    # 우리는 Lab 2 에서 직접 만든 Memory 를 쓰기 때문에 생기는 간극입니다.
    #
    # Pre-Lab CFN 이 만든 thewhoo-agent-role-<pid> 를 지정합니다.
    pid = os.environ.get("PARTICIPANT_ID", "w001")
    role_arn = os.environ.get("AGENT_ROLE_ARN", "")
    if not role_arn:
        try:
            acct = boto3.client("sts").get_caller_identity()["Account"]
            role_arn = f"arn:aws:iam::{acct}:role/thewhoo-agent-role-{pid}"
        except Exception as e:  # 자격증명이 없으면 사용자가 직접 넣도록 안내
            print(f"[WARN] 계정 ID 조회 실패({e}) — executionRoleArn 을 건너뜁니다.")
            print("       AGENT_ROLE_ARN 환경변수로 직접 지정할 수 있습니다.")

    runtimes[0].update({
        "entrypoint": "app.py",        # codeLocation 기준 상대경로
        "codeLocation": "src/",
        "runtimeVersion": "PYTHON_3_12",  # 기본값 PYTHON_3_14 → 의존성 호환용으로 낮춤
        # envVars 는 공식 스키마상 배열입니다 — [{"name": ..., "value": ...}, ...]
        # dict 로 넣으면 `agentcore validate` 가
        #   runtimes[0].envVars: expected "array"
        # 로 거부합니다 (schema.agentcore.aws.dev/v1/agentcore.json).
        "envVars": [
            {"name": "KB_ID", "value": os.environ["KB_ID"]},
            {"name": "AGENTCORE_MEMORY_ID", "value": os.environ["AGENTCORE_MEMORY_ID"]},
            {"name": "AGENTCORE_GATEWAY_URL", "value": os.environ["AGENTCORE_GATEWAY_URL"]},
            {"name": "AWS_REGION", "value": os.environ.get("AWS_REGION", "us-east-1")},
        ],
    })

    if role_arn:
        runtimes[0]["executionRoleArn"] = role_arn

    CONFIG.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")

    rt = runtimes[0]
    print(f"✓ {CONFIG} 갱신 완료")
    print(f"    codeLocation   : {rt['codeLocation']}")
    print(f"    entrypoint     : {rt['entrypoint']}")
    print(f"    runtimeVersion : {rt['runtimeVersion']}")
    print(f"    envVars        : {', '.join(e['name'] for e in rt['envVars'])}")
    if rt.get("executionRoleArn"):
        print(f"    executionRole  : {rt['executionRoleArn'].split('/')[-1]}")
    print()
    print("다음: agentcore deploy --dry-run -y  →  agentcore deploy -y")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
