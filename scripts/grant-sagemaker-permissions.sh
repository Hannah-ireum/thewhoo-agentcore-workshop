#!/usr/bin/env bash
# SageMaker Studio Code Editor 의 실행 role 에 워크샵 권한 추가.
#
# Code Editor 에서 직접 돌리면 AccessDenied (self-mutation 금지) 가 납니다.
# CloudShell (WSParticipantRole) 에서 이 스크립트를 돌리면 IAM 권한이
# 충분해서 Code Editor role 에 정책을 추가할 수 있습니다.
#
# Usage (CloudShell 에서):
#   ./scripts/grant-sagemaker-permissions.sh
#
# 현재 계정의 모든 SageMaker execution role 을 자동 탐지해 정책 추가.
set -euo pipefail

POLICY_NAME="thewhoo-agentcore-workshop-extra"

echo ""
echo "==================================================================="
echo " SageMaker execution role 에 워크샵 권한 추가"
echo "==================================================================="
echo ""

# 현재 계정의 SageMaker execution role 찾기
ROLES=$(aws iam list-roles \
  --query "Roles[?starts_with(RoleName, 'AmazonSageMaker-ExecutionRole-')].RoleName" \
  --output text)

if [ -z "${ROLES}" ]; then
  echo "[알림] 이 계정에 SageMaker execution role 이 없습니다."
  echo "       (SageMaker Studio 도메인을 만들면 자동 생성됩니다)"
  exit 0
fi

POLICY_DOC=$(cat <<'EOF'
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "bedrock:*", "bedrock-agent:*", "bedrock-agent-runtime:*",
        "bedrock-runtime:*", "bedrock-agentcore:*", "bedrock-agentcore-control:*",
        "aws-marketplace:ViewSubscriptions", "aws-marketplace:Subscribe",
        "aws-marketplace:Unsubscribe",
        "lambda:*", "s3vectors:*", "cognito-idp:*",
        "logs:*", "cloudwatch:*", "xray:*",
        "sts:GetCallerIdentity", "sts:AssumeRole",
        "s3:*",
        "iam:CreateRole", "iam:DeleteRole", "iam:GetRole",
        "iam:PutRolePolicy", "iam:GetRolePolicy", "iam:DeleteRolePolicy",
        "iam:ListRolePolicies", "iam:AttachRolePolicy", "iam:DetachRolePolicy",
        "iam:ListAttachedRolePolicies", "iam:PassRole",
        "iam:TagRole", "iam:UpdateAssumeRolePolicy",
        "iam:CreateServiceLinkedRole",
        "cloudformation:*"
      ],
      "Resource": "*"
    }
  ]
}
EOF
)

for role in ${ROLES}; do
  echo "  Role: ${role}"
  aws iam put-role-policy \
    --role-name "${role}" \
    --policy-name "${POLICY_NAME}" \
    --policy-document "${POLICY_DOC}"
  echo "    ✓ 정책 '${POLICY_NAME}' 적용 완료"
done

echo ""
echo "  Bedrock Claude 모델 계정-전역 활성화 (Marketplace 자동 구독 트리거)"

# WSParticipantRole 에서 Claude 4.x 모델을 한번 호출해 계정 전체에 enable.
# 이 과정이 없으면 Code Editor 의 SageMaker role 호출 시
# "aws-marketplace:Subscribe" 에러가 납니다.
for MODEL_ID in \
    "us.anthropic.claude-haiku-4-5-20251001-v1:0" \
    "us.anthropic.claude-sonnet-4-6"; do
  TMP=$(mktemp)
  if aws bedrock-runtime invoke-model \
      --model-id "${MODEL_ID}" \
      --region us-east-1 \
      --body '{"anthropic_version":"bedrock-2023-05-31","max_tokens":10,"messages":[{"role":"user","content":"ok"}]}' \
      --cli-binary-format raw-in-base64-out \
      "${TMP}" > /dev/null 2>&1; then
    echo "    ✓ ${MODEL_ID} 활성화"
  else
    echo "    ⚠ ${MODEL_ID} 활성화 실패 — 콘솔 Bedrock Playground 에서 메시지 1회 보내면 해결됨"
  fi
  rm -f "${TMP}"
done

echo ""
echo "==================================================================="
echo " ✓ SageMaker role 권한 추가 + Bedrock 모델 활성화 완료"
echo "==================================================================="
echo ""
echo "이제 Code Editor 터미널에서 Lab 1~6 을 실행할 수 있습니다."
