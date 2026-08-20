#!/usr/bin/env bash
# Day 2 패스트트랙 — CloudShell (WSParticipantRole) 단계.
#
# 새 AWS 계정에서 Day 2 만 시작할 때 사용합니다.
# Day 1 의 학습 단계는 건너뛰고 인프라만 재구성합니다.
#
# 이 스크립트가 하는 일:
#   1) 권한 부여 + Bedrock Claude 모델 활성화 (Marketplace subscribe 트리거)
#   2) Pre-Lab 인프라 (CFN: S3, IAM, Cognito, Lambda 4종, KB Role)
#   3) S3 Vectors + Bedrock Knowledge Base + ingestion
#
# Memory / Gateway 생성은 SageMaker Code Editor 에서 별도 스크립트로 진행합니다
# (Bedrock SDK 호출 권한이 SageMaker role 쪽에 있기 때문).
#
# Usage (CloudShell 에서):
#   git clone https://github.com/Hannah-ireum/thewhoo-agentcore-workshop.git
#   cd thewhoo-agentcore-workshop
#   ./scripts/setup-day2-cloudshell.sh w001

set -euo pipefail

PID="${1:?사용법: ./scripts/setup-day2-cloudshell.sh <participant-id>}"
HERE="$(cd "$(dirname "$0")/.." && pwd)"
cd "${HERE}"

# 워크샵은 us-east-1 고정. CloudShell 이 다른 region (예: us-west-2) 에서 시작해도
# 강제로 us-east-1 을 사용합니다. 사용자가 다른 region 에서 진행하려면 이 줄을 수정하세요.
REGION="us-east-1"
export AWS_REGION="${REGION}"
export AWS_DEFAULT_REGION="${REGION}"

echo ""
echo "==================================================================="
echo " Day 2 패스트트랙 (1/2) — CloudShell 단계"
echo "==================================================================="
echo "  ParticipantId : ${PID}"
echo ""
echo "이 단계가 끝나면 SageMaker Code Editor 로 이동해"
echo "  ./scripts/setup-day2-codeeditor.sh ${PID}"
echo "를 실행하세요."
echo ""

echo "[1/3] SageMaker execution role 권한 부여 + 모델 활성화"
./scripts/grant-sagemaker-permissions.sh

echo ""
echo "[2/3] AgentCore Runtime prerequisite — service-linked role + X-Ray destination"
# (a) Service-linked role: AgentCore Runtime 첫 배포에 필요. 이미 있으면 건너뜀.
echo "  service-linked role 확인..."
for sl_service in \
    runtime-identity.bedrock-agentcore.amazonaws.com \
    network.bedrock-agentcore.amazonaws.com; do
  if aws iam create-service-linked-role \
        --aws-service-name "${sl_service}" \
        > /dev/null 2>&1; then
    echo "    ✓ ${sl_service} SLR 생성"
  else
    echo "    ↺ ${sl_service} SLR 이미 존재 또는 권한 부족 (계속 진행)"
  fi
done

# (b) CloudWatch Logs Resource Policy — X-Ray 가 /aws/spans 에 쓰도록 허용
echo "  CloudWatch Logs Resource Policy (X-Ray 용) 설정..."
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
LOGS_POLICY=$(cat <<JSON
{
  "Version": "2012-10-17",
  "Statement": [{
    "Sid": "TransactionSearchXRayAccess",
    "Effect": "Allow",
    "Principal": { "Service": "xray.amazonaws.com" },
    "Action": "logs:PutLogEvents",
    "Resource": [
      "arn:aws:logs:${REGION}:${ACCOUNT_ID}:log-group:aws/spans:*",
      "arn:aws:logs:${REGION}:${ACCOUNT_ID}:log-group:/aws/application-signals/data:*"
    ],
    "Condition": {
      "ArnLike": { "aws:SourceArn": "arn:aws:xray:${REGION}:${ACCOUNT_ID}:*" },
      "StringEquals": { "aws:SourceAccount": "${ACCOUNT_ID}" }
    }
  }]
}
JSON
)
if aws logs put-resource-policy \
      --policy-name AWSCloudWatchLogsForXRay \
      --policy-document "${LOGS_POLICY}" \
      --region "${REGION}" > /dev/null 2>&1; then
  echo "    ✓ Logs Resource Policy 적용"
else
  echo "    ⚠ Logs Resource Policy 적용 실패 (이미 있거나 권한 부족)"
fi

# (c) X-Ray Trace Segment Destination — CloudWatch Logs 로 보내야 GenAI Observability 가 동작
echo "  X-Ray Trace Segment Destination 설정..."
CURRENT_DEST=$(aws xray get-trace-segment-destination --region "${REGION}" \
  --query 'Destination' --output text 2>/dev/null || echo "Unknown")
if [ "${CURRENT_DEST}" = "CloudWatchLogs" ]; then
  echo "    ✓ 이미 CloudWatchLogs"
else
  if aws xray update-trace-segment-destination \
        --destination CloudWatchLogs \
        --region "${REGION}" > /dev/null 2>&1; then
    echo "    ✓ CloudWatchLogs 로 전환"
  else
    echo "    ⚠ 전환 실패 (위의 Logs Resource Policy 가 먼저 적용돼야 합니다)"
  fi
fi

# (d) X-Ray Indexing Rule — sampling 100% (워크샵 trace 검증용)
echo "  X-Ray Indexing Rule sampling 100% 로..."
if aws xray update-indexing-rule \
      --name Default \
      --rule '{"Probabilistic":{"DesiredSamplingPercentage":100}}' \
      --region "${REGION}" > /dev/null 2>&1; then
  echo "    ✓ sampling 100% 적용"
else
  echo "    ⚠ sampling 갱신 실패 (계정 기본값으로 진행)"
fi

echo ""
echo "[3/3] Pre-Lab 인프라 + Knowledge Base 생성"
./scripts/onestop.sh "${PID}"

echo ""
echo "[검증] Transaction Search prerequisite"
DEST=$(aws xray get-trace-segment-destination --region "${REGION}" \
  --query 'Destination' --output text 2>/dev/null || echo "Unknown")
SAMPLING=$(aws xray get-indexing-rules --region "${REGION}" \
  --query 'IndexingRules[?Name==`Default`].Rule.Probabilistic.DesiredSamplingPercentage | [0]' \
  --output text 2>/dev/null || echo "Unknown")
RP=$(aws logs describe-resource-policies --region "${REGION}" \
  --query 'resourcePolicies[?policyName==`AWSCloudWatchLogsForXRay`] | length(@)' \
  --output text 2>/dev/null || echo "0")

echo "  Trace Segment Destination : ${DEST}     (기대: CloudWatchLogs)"
echo "  Indexing Sampling %       : ${SAMPLING}  (기대: 100.0)"
echo "  Logs Resource Policy 개수 : ${RP}         (기대: 1 이상)"

if [ "${DEST}" = "CloudWatchLogs" ] && [ "${RP}" != "0" ]; then
  echo "  ✓ prerequisite 충족"
else
  echo "  ⚠ 일부 미충족 — Lab 6 의 '잘 안 될 때' 표 4단계 참고"
fi
echo ""
echo "==================================================================="
echo " ✓ CloudShell 단계 완료"
echo "==================================================================="
echo ""
echo "다음:"
echo "  1) SageMaker Studio Code Editor 를 엽니다"
echo "  2) 터미널에서 다음을 실행합니다"
echo ""
echo "     cd ~ && git clone https://github.com/Hannah-ireum/thewhoo-agentcore-workshop.git 2>/dev/null || (cd ~/thewhoo-agentcore-workshop && git pull)"
echo "     cd ~/thewhoo-agentcore-workshop"
echo "     ./scripts/setup-day2-codeeditor.sh ${PID}"
echo ""
