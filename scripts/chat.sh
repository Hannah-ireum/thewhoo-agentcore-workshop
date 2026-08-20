#!/usr/bin/env bash
# CLI 에서 AgentCore agent 와 대화. \n 등 JSON escape 를 풀어 예쁘게 출력합니다.
#
# Usage:
#   ./scripts/chat.sh "보습크림 추천"                       # dev 서버 (localhost:8080)
#   ./scripts/chat.sh -s my-session "건성 피부야"           # session_id 지정 (기본: cli-1)
#   ./scripts/chat.sh -r "보습크림 추천"                    # 배포된 Runtime (AGENT_RUNTIME_ARN 사용)
#   ./scripts/chat.sh -r -s shop-1 "재고 있어?"             # Runtime + session_id
#
# 전제:
#   dev 모드  : 다른 터미널에서 agentcore dev --port 8080 가 떠 있어야 함
#   runtime 모드: AGENT_RUNTIME_ARN 환경변수가 export 돼 있어야 함
#                 (eval "$(./scripts/print-env.sh w001)" 로 자동 export)

set -euo pipefail

USE_RUNTIME=false
# runtimeSessionId 33자 이상 제약 — uuid 로 길이 확보
SESSION_ID="cli-$(python3 -c 'import uuid; print(uuid.uuid4())')"

while [ $# -gt 0 ]; do
  case "$1" in
    -r|--runtime) USE_RUNTIME=true; shift ;;
    -s|--session) SESSION_ID="$2"; shift 2 ;;
    -h|--help)
      sed -n '2,15p' "$0" | sed 's/^# //; s/^#//'
      exit 0 ;;
    *) MESSAGE="$1"; shift ;;
  esac
done

if [ -z "${MESSAGE:-}" ]; then
  echo "사용법: ./scripts/chat.sh [\"-r\" | \"-s <id>\"] \"메시지\"" >&2
  exit 1
fi

# AgentCore Runtime API 의 runtimeSessionId 는 33자 이상 필수
if [ ${#SESSION_ID} -lt 33 ]; then
  SESSION_ID="${SESSION_ID}-$(python3 -c 'import uuid; print(uuid.uuid4())')"
fi

PAYLOAD=$(python3 -c "import json,sys; print(json.dumps({'session_id':'${SESSION_ID}','message':'${MESSAGE}'}))")

if [ "${USE_RUNTIME}" = true ]; then
  if [ -z "${AGENT_RUNTIME_ARN:-}" ]; then
    echo "[ERROR] AGENT_RUNTIME_ARN 가 설정되지 않았습니다." >&2
    echo "  eval \"\$(./scripts/print-env.sh w001)\" 를 먼저 실행하세요." >&2
    exit 1
  fi

  RAW=$(python3 - <<PYEOF
import boto3, json, os
client = boto3.client("bedrock-agentcore", region_name=os.environ.get("AWS_REGION", "us-east-1"))
resp = client.invoke_agent_runtime(
    agentRuntimeArn="${AGENT_RUNTIME_ARN}",
    runtimeSessionId="${SESSION_ID}-$(date +%s)",
    payload='${PAYLOAD}',
)
body = resp["response"].read()
try:
    data = json.loads(body)
    print(data if isinstance(data, str) else json.dumps(data, ensure_ascii=False))
except Exception:
    print(body.decode("utf-8", errors="replace"))
PYEOF
)
else
  RAW=$(curl -s -X POST http://localhost:8080/invocations \
    -H "Content-Type: application/json" \
    -d "${PAYLOAD}")
fi

# JSON-encoded string 풀어서 출력
python3 -c "
import json, sys
raw = '''${RAW}'''
try:
    data = json.loads(raw)
    if isinstance(data, str):
        print(data)
    elif isinstance(data, dict) and 'response' in data:
        v = data['response']
        if isinstance(v, str):
            try:
                v = json.loads(v)
            except Exception:
                pass
        print(v if isinstance(v, str) else json.dumps(v, ensure_ascii=False, indent=2))
    else:
        print(json.dumps(data, ensure_ascii=False, indent=2))
except Exception:
    print(raw)
"
