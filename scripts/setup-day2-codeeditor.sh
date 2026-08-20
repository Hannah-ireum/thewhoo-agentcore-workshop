#!/usr/bin/env bash
# Day 2 패스트트랙 — SageMaker Code Editor 단계.
#
# CloudShell 단계 (setup-day2-cloudshell.sh) 가 끝난 뒤 실행합니다.
# Code Editor 의 SageMaker execution role 은 Bedrock 호출 권한을 받았으므로
# 여기에서 Memory / Gateway 를 생성합니다.
#
# 이 스크립트가 하는 일:
#   1) Python venv + 의존성 설치
#   2) AgentCore Memory 4-strategy 생성
#   3) AgentCore Gateway + Lambda target 4 등록
#   4) 환경변수 출력 (eval 으로 적용 안내)
#
# Usage:
#   ./scripts/setup-day2-codeeditor.sh w001

set -euo pipefail

PID="${1:?사용법: ./scripts/setup-day2-codeeditor.sh <participant-id>}"
HERE="$(cd "$(dirname "$0")/.." && pwd)"
cd "${HERE}"

export PARTICIPANT_ID="${PID}"
export AWS_REGION="${AWS_REGION:-us-east-1}"

echo ""
echo "==================================================================="
echo " Day 2 패스트트랙 (2/2) — Code Editor 단계"
echo "==================================================================="
echo "  ParticipantId : ${PID}"
echo "  Region        : ${AWS_REGION}"
echo ""

echo "[1/4] Python 환경 셋업"
./scripts/setup-python.sh
# venv 활성화는 set -e 와 trap 충돌을 피하려고 명시적 source
# shellcheck source=/dev/null
source .venv/bin/activate

echo ""
echo "[2/4] KB_ID 확인"
# 두 종류 실패를 구분합니다:
#   (a) Bedrock 권한이 SageMaker Execution Role 에 없음 → AccessDeniedException
#   (b) KB 자체가 안 만들어짐 → 정상 응답이지만 빈 결과
KB_QUERY_OUT=$(aws bedrock-agent list-knowledge-bases --region "${AWS_REGION}" \
  --query "knowledgeBaseSummaries[?name=='thewhoo-kb-${PID}'].knowledgeBaseId" \
  --output text 2>&1 || true)

if echo "${KB_QUERY_OUT}" | grep -qi "AccessDenied"; then
  cat <<EOF

[ERROR] SageMaker Execution Role 에 Bedrock 권한이 없습니다.

  현재 role: $(aws sts get-caller-identity --query Arn --output text 2>/dev/null)

  새 Workshop Studio 계정에서는 SageMaker 도메인이 만들어진 뒤에
  CloudShell 에서 grant-sagemaker-permissions.sh 를 다시 한 번 실행해야
  새 Execution Role 에도 워크샵 권한이 적용됩니다.

  복구 절차:
    1) CloudShell 로 이동
    2) cd ~/thewhoo-agentcore-workshop && git pull
    3) ./scripts/grant-sagemaker-permissions.sh
    4) (Code Editor) **터미널을 새로 엽니다** — 기존 터미널의 IMDS
        자격증명 캐시 때문에 같은 터미널에서 재시도하면 새 권한이
        반영되지 않습니다 ("30초 대기" 로는 부족).
    5) 새 터미널에서 다음으로 권한 갱신 확인:
         aws bedrock-agent list-knowledge-bases --region us-east-1
       JSON 이 나오면 OK.
    6) cd ~/thewhoo-agentcore-workshop && source .venv/bin/activate
       ./scripts/setup-day2-codeeditor.sh ${PID}

EOF
  exit 1
fi

KB_ID="${KB_QUERY_OUT}"
if [ -z "${KB_ID}" ] || [ "${KB_ID}" = "None" ]; then
  cat <<EOF

[ERROR] thewhoo-kb-${PID} Knowledge Base 가 없습니다.

  CloudShell 에서 인프라가 아직 만들어지지 않았을 수 있습니다.
  CloudShell 로 이동해 다음을 실행하세요:

    cd ~/thewhoo-agentcore-workshop
    ./scripts/setup-day2-cloudshell.sh ${PID}

EOF
  exit 1
fi
export KB_ID
echo "      KB_ID=${KB_ID}"

echo ""
echo "[3/4] AgentCore Memory 4-strategy 생성 (재실행 안전)"
python3 scripts/create-memory.py

echo ""
echo "[4/4] AgentCore Gateway + Lambda target 4 등록 (재실행 안전)"
python3 scripts/create-gateway.py

echo ""
echo "==================================================================="
echo " ✓ Day 2 패스트트랙 완료"
echo "==================================================================="
echo ""
echo "환경변수를 현재 셸에 적용:"
echo ""
echo "  eval \"\$(./scripts/print-env.sh ${PID})\""
echo "  echo \"KB=\$KB_ID  MEM=\$AGENTCORE_MEMORY_ID  GW=\$AGENTCORE_GATEWAY_URL\""
echo ""
echo "세 값이 모두 채워지면 Lab 5 (06-lab5-서비스로-배포하기.md) 로 진입하세요."
echo "Lab 5 의 2단계에서 .bedrock_agentcore.yaml 을 만들고, 4단계에서 배포합니다."
