#!/usr/bin/env bash
# 원스톱 Pre-Lab 셋업 — CloudShell (WSParticipantRole) 전용.
#
# 이 하나의 스크립트가 Pre-Lab 의 모든 AWS 리소스를 만듭니다:
#   1) Lambda 코드 버킷
#   2) CloudFormation 스택 (S3 / IAM / Cognito)
#   3) Mock Lambda 4종
#   4) S3 Vectors + Bedrock Knowledge Base + ingestion
#
# Python 3.11 이나 venv 는 필요하지 않습니다 (boto3/awscli 만 사용).
# CloudShell 기본 python3.9 로 전부 돌아갑니다.
#
# Usage:
#   ./scripts/onestop.sh <participant-id>
#
# 예:
#   ./scripts/onestop.sh w001
set -euo pipefail

PID="${1:?사용법: ./scripts/onestop.sh <participant-id>  (예: ./scripts/onestop.sh w001)}"
# 워크샵은 us-east-1 고정. CloudShell 이 다른 region 에서 시작해도 강제 적용.
REGION="us-east-1"
export AWS_REGION="${REGION}"
export AWS_DEFAULT_REGION="${REGION}"
HERE="$(cd "$(dirname "$0")/.." && pwd)"

START=$(date +%s)
elapsed() {
  local now=$(date +%s)
  local s=$((now - START))
  printf "[경과 %dm%02ds]\n" $((s/60)) $((s%60))
}

echo ""
echo "==================================================================="
echo " 더후 워크샵 원스톱 Pre-Lab 셋업"
echo "==================================================================="

CALLER_ARN=$(aws sts get-caller-identity --query Arn --output text 2>/dev/null || echo "")
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text 2>/dev/null || echo "")

if [ -z "${CALLER_ARN}" ]; then
  echo "[ERROR] AWS 자격증명이 설정되지 않았습니다."
  exit 1
fi

# WSParticipantRole 권장 안내 (SageMaker execution role 이면 제한 있음)
if [[ "${CALLER_ARN}" == *"SageMaker-ExecutionRole"* ]]; then
  cat <<EOF

[주의] 현재 SageMaker execution role 로 실행 중입니다.
       이 role 은 IAM / CloudFormation / Bedrock / Lambda 권한이 부족해
       대부분 실패합니다.

       CloudShell (Console 우상단 검색창 오른쪽 터미널 아이콘 >_) 을 열고 다시 실행하세요.
       CloudShell 은 WSParticipantRole 로 동작하여 Admin 권한을 가집니다.

EOF
  exit 1
fi

echo "  ParticipantId : ${PID}"
echo "  Region        : ${REGION}"
echo "  Account       : ${ACCOUNT_ID}"
echo "  Caller        : ${CALLER_ARN}"
echo ""
echo "예상 소요 시간: 약 10분"
echo "==================================================================="
echo ""

STACK_NAME="thewhoo-${PID}"
CODE_BUCKET="thewhoo-code-${PID}-${ACCOUNT_ID}"

# ────────────────────────────────────────────────────────────────
# 1/4. 코드 버킷
# ────────────────────────────────────────────────────────────────
echo ">> [1/4] 코드 버킷 생성"
elapsed
bash "${HERE}/infra/cfn/package_lambdas.sh" "${PID}" prep "${REGION}"
echo ""

# ────────────────────────────────────────────────────────────────
# 2/4. CFN 스택
# ────────────────────────────────────────────────────────────────
echo ">> [2/4] CloudFormation 스택 배포 (5~8분)"
elapsed
aws cloudformation deploy \
  --template-file "${HERE}/infra/cfn/workshop.yaml" \
  --stack-name "${STACK_NAME}" \
  --parameter-overrides \
    "ParticipantId=${PID}" \
    "LambdaCodeBucket=${CODE_BUCKET}" \
  --capabilities CAPABILITY_NAMED_IAM \
  --region "${REGION}" \
  --no-fail-on-empty-changeset
echo ""

# ────────────────────────────────────────────────────────────────
# 3/4. Mock Lambda 4종
# ────────────────────────────────────────────────────────────────
echo ">> [3/4] Mock Lambda 4종 배포"
elapsed
bash "${HERE}/infra/cfn/package_lambdas.sh" "${PID}" mocks "${REGION}"
echo ""

# ────────────────────────────────────────────────────────────────
# 4/4. Knowledge Base 부트스트랩
# ────────────────────────────────────────────────────────────────
echo ">> [4/4] Knowledge Base 부트스트랩 (1~2분)"
elapsed

# CloudShell 의 기본 python3 (3.9) 로도 bootstrap_kb 가 동작합니다 (boto3 만 사용)
BOOTSTRAP_LOG="$(mktemp)"
python3 "${HERE}/infra/cfn/bootstrap_kb.py" "${PID}" "${REGION}" | tee "${BOOTSTRAP_LOG}"
KB_ID=$(grep -E "^KB_ID=" "${BOOTSTRAP_LOG}" | tail -1 | cut -d= -f2)
rm -f "${BOOTSTRAP_LOG}"

if [ -z "${KB_ID}" ]; then
  echo "[ERROR] KB_ID 를 찾을 수 없습니다. 위 출력을 확인하세요."
  exit 1
fi

# ────────────────────────────────────────────────────────────────
# 완료
# ────────────────────────────────────────────────────────────────
FINISH=$(date +%s)
TOTAL=$((FINISH - START))

cat <<EOF

===================================================================
 ✓ Pre-Lab 셋업 완료 (총 $((TOTAL/60))m$((TOTAL%60))s)
===================================================================

Lab 1~6 을 실행하려면 SageMaker Studio Code Editor 로 이동하세요.
(Python 3.11 + strands-agents 는 Code Editor 안에서 준비합니다.)

Code Editor 터미널에서 실행할 명령:

  git clone https://github.com/Hannah-ireum/thewhoo-agentcore-workshop.git
  cd thewhoo-agentcore-workshop
  ./scripts/setup-python.sh

그리고 환경변수:

  export PARTICIPANT_ID=${PID}
  export AWS_REGION=${REGION}
  export KB_ID=${KB_ID}

Code Editor 가 Bedrock / Gateway 등을 호출할 수 있으려면 SageMaker
execution role 에 추가 권한이 필요합니다. Pre-Lab 문서의 "Code Editor
권한 추가" 섹션을 참고하세요.
EOF
