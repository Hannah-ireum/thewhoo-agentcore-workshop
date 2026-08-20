#!/usr/bin/env bash
# 현재 AWS 계정에서 사용 중인 워크샵 리소스를 조회해 export 구문 출력.
#
# Usage:
#   ./scripts/print-env.sh <participant-id>
#   eval "$(./scripts/print-env.sh w001)"
#
# 아직 만들지 않은 리소스는 건너뛰고 존재하는 것만 출력합니다.
# (예: Lab 2 전엔 MEMORY 없음 — 당연히 정상)

PID="${1:?사용법: ./scripts/print-env.sh <participant-id>}"
REGION="${AWS_REGION:-us-east-1}"

# 기본 환경변수는 항상 출력
echo "export PARTICIPANT_ID=${PID}"
echo "export AWS_REGION=${REGION}"

# KB_ID (Pre-Lab 에서 만들어짐)
KB_ID=$(aws bedrock-agent list-knowledge-bases --region "${REGION}" \
  --query "knowledgeBaseSummaries[?name=='thewhoo-kb-${PID}'].knowledgeBaseId" \
  --output text 2>/dev/null || echo "")
[ -n "${KB_ID}" ] && [ "${KB_ID}" != "None" ] && echo "export KB_ID=${KB_ID}"

# Memory (Lab 2 에서 만들어짐)
# list_memories 응답은 'name' 필드가 없고 id 가 'TheWhooMemory-<suffix>' 형태라
# id/memoryId prefix 로 매칭합니다.
MEM_JSON=$(aws bedrock-agentcore-control list-memories --region "${REGION}" 2>/dev/null || echo "")
if [ -n "${MEM_JSON}" ]; then
  MEM_ID=$(echo "${MEM_JSON}" | python3 -c "
import sys, json
data = json.load(sys.stdin)
items = data.get('memories', []) or data.get('items', []) or []
for m in items:
    mid = m.get('id') or m.get('memoryId', '')
    if mid.startswith('TheWhooMemory'):
        print(mid)
        break
" 2>/dev/null || echo "")
  [ -n "${MEM_ID}" ] && echo "export AGENTCORE_MEMORY_ID=${MEM_ID}"
fi

# Gateway URL (Lab 3 에서 만들어짐)
# ListGateways summary 에는 gatewayUrl 이 없으므로 GetGateway 로 다시 조회.
GW_ID=$(aws bedrock-agentcore-control list-gateways --region "${REGION}" \
  --query "items[?contains(name, 'thewhoo-gateway')].gatewayId | [0]" \
  --output text 2>/dev/null || echo "")
if [ -n "${GW_ID}" ] && [ "${GW_ID}" != "None" ]; then
  GW_URL=$(aws bedrock-agentcore-control get-gateway \
    --gateway-identifier "${GW_ID}" \
    --region "${REGION}" \
    --query 'gatewayUrl' \
    --output text 2>/dev/null || echo "")
  [ -n "${GW_URL}" ] && [ "${GW_URL}" != "None" ] && echo "export AGENTCORE_GATEWAY_URL=${GW_URL}"
fi

# Agent Runtime ARN (Lab 5 이후)
RT_JSON=$(aws bedrock-agentcore-control list-agent-runtimes --region "${REGION}" 2>/dev/null || echo "")
if [ -n "${RT_JSON}" ]; then
  RT_ARN=$(echo "${RT_JSON}" | python3 -c "
import sys, json
data = json.load(sys.stdin)
items = data.get('agentRuntimes', []) or data.get('items', []) or []
for r in items:
    if 'thewhoo' in r.get('agentRuntimeName', '').lower():
        print(r.get('agentRuntimeArn', ''))
        break
" 2>/dev/null || echo "")
  [ -n "${RT_ARN}" ] && echo "export AGENT_RUNTIME_ARN=${RT_ARN}"
fi

# 마지막 조건문의 결과가 스크립트 종료코드가 되지 않게 명시적으로 0 반환.
# (Lab 5 전에는 Runtime 이 없어 위 [ -n ... ] 이 false → exit 1 이 되고,
#  `eval "$(./scripts/print-env.sh w001)"` 이 set -e 환경에서 중단됩니다.)
exit 0
