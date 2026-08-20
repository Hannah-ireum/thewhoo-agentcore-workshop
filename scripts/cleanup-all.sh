#!/usr/bin/env bash
# 워크샵에서 만든 AWS 리소스를 모두 삭제. 처음부터 다시 시작할 때 사용.
#
# 삭제 순서 (의존성 고려):
#   1. Agent Runtime              (가장 먼저 — Memory, Gateway 보다 우선)
#   2. starter-toolkit 자동 Memory (thewhoo_chat_mem-*)
#   3. 워크샵 Memory              (TheWhooMemory-*)
#   4. Gateway Targets            (Gateway 보다 먼저)
#   5. Gateway
#   6. Knowledge Base DataSources
#   7. Knowledge Base
#   8. S3 Vectors 인덱스 + 버킷
#   9. CFN 스택                    (Lambda, IAM, S3, Cognito 한 번에)
#  10. CloudWatch Dashboard + Alarms
#  11. .bedrock_agentcore.yaml + agentcore deploy 캐시
#
# 안 지우는 것:
#   - SageMaker Execution Role 의 thewhoo-agentcore-workshop-extra 정책 (다음 셋업에 재사용)
#   - SageMaker 도메인 / Code Editor 스페이스 (Workshop Studio 가 관리)
#   - X-Ray Trace Segment Destination / Logs Resource Policy (계정/리전 1회 설정)
#
# 사용법:
#   ./scripts/cleanup-all.sh w001
#   ./scripts/cleanup-all.sh w001 --yes        # 확인 없이 바로 진행

set -uo pipefail

PID="${1:?사용법: ./scripts/cleanup-all.sh <participant-id> [--yes]}"
AUTO_YES="${2:-}"
REGION="${AWS_REGION:-us-east-1}"

echo ""
echo "==================================================================="
echo " 워크샵 리소스 전체 삭제"
echo "==================================================================="
echo "  ParticipantId : ${PID}"
echo "  Region        : ${REGION}"
echo ""
echo "다음 리소스를 모두 삭제합니다:"
echo "  · Agent Runtime (thewhoo_chat-*)"
echo "  · Memory (thewhoo_chat_mem-*, TheWhooMemory-*)"
echo "  · Gateway + Targets"
echo "  · Knowledge Base + DataSources"
echo "  · S3 Vectors 인덱스 + 버킷"
echo "  · CFN 스택 (thewhoo-${PID})"
echo "  · CloudWatch Dashboard (thewhoo-chat-runtime)"
echo "  · CloudWatch Alarms (thewhoo-chat-*)"
echo "  · 로컬 .bedrock_agentcore.yaml + agentcore 캐시"
echo ""

if [ "${AUTO_YES}" != "--yes" ]; then
  read -r -p "정말 삭제하시겠습니까? (yes 입력) " CONFIRM
  if [ "${CONFIRM}" != "yes" ]; then
    echo "취소됐습니다."
    exit 0
  fi
fi

echo ""
echo "[1/11] Agent Runtime 삭제"
RT_IDS=$(aws bedrock-agentcore-control list-agent-runtimes --region "${REGION}" \
  --query "agentRuntimes[?contains(agentRuntimeName, 'thewhoo')].agentRuntimeId" \
  --output text 2>/dev/null || echo "")
for rt in ${RT_IDS}; do
  echo "  · ${rt}"
  aws bedrock-agentcore-control delete-agent-runtime \
    --agent-runtime-id "${rt}" --region "${REGION}" 2>/dev/null \
    && echo "    ✓ 삭제" \
    || echo "    ⚠ 삭제 실패 (이미 없거나 권한 부족)"
done
[ -z "${RT_IDS}" ] && echo "  · 없음"

echo ""
echo "[2/11] starter-toolkit 자동 Memory (thewhoo_chat_mem-*) 삭제"
MEM_IDS=$(aws bedrock-agentcore-control list-memories --region "${REGION}" \
  --query "memories[?starts_with(id, 'thewhoo_chat_mem')].id" \
  --output text 2>/dev/null || echo "")
for mem in ${MEM_IDS}; do
  echo "  · ${mem}"
  aws bedrock-agentcore-control delete-memory \
    --memory-id "${mem}" --region "${REGION}" 2>/dev/null \
    && echo "    ✓ 삭제" \
    || echo "    ⚠ 삭제 실패"
done
[ -z "${MEM_IDS}" ] && echo "  · 없음"

echo ""
echo "[3/11] 워크샵 Memory (TheWhooMemory-*) 삭제"
MEM_IDS=$(aws bedrock-agentcore-control list-memories --region "${REGION}" \
  --query "memories[?starts_with(id, 'TheWhooMemory')].id" \
  --output text 2>/dev/null || echo "")
for mem in ${MEM_IDS}; do
  echo "  · ${mem}"
  aws bedrock-agentcore-control delete-memory \
    --memory-id "${mem}" --region "${REGION}" 2>/dev/null \
    && echo "    ✓ 삭제" \
    || echo "    ⚠ 삭제 실패"
done
[ -z "${MEM_IDS}" ] && echo "  · 없음"

echo ""
echo "[4-5/11] Gateway Target + Gateway 삭제"
GW_IDS=$(aws bedrock-agentcore-control list-gateways --region "${REGION}" \
  --query "items[?contains(name, 'thewhoo-gateway')].gatewayId" \
  --output text 2>/dev/null || echo "")
for gw in ${GW_IDS}; do
  echo "  Gateway: ${gw}"
  TGT_IDS=$(aws bedrock-agentcore-control list-gateway-targets \
    --gateway-identifier "${gw}" --region "${REGION}" \
    --query 'items[].targetId' --output text 2>/dev/null || echo "")
  for tgt in ${TGT_IDS}; do
    aws bedrock-agentcore-control delete-gateway-target \
      --gateway-identifier "${gw}" --target-id "${tgt}" --region "${REGION}" 2>/dev/null \
      && echo "    ✓ Target ${tgt} 삭제" \
      || echo "    ⚠ Target ${tgt} 삭제 실패"
  done
  aws bedrock-agentcore-control delete-gateway \
    --gateway-identifier "${gw}" --region "${REGION}" 2>/dev/null \
    && echo "    ✓ Gateway ${gw} 삭제" \
    || echo "    ⚠ Gateway ${gw} 삭제 실패"
done
[ -z "${GW_IDS}" ] && echo "  · 없음"

echo ""
echo "[6-7/11] Knowledge Base + DataSources 삭제"
KB_IDS=$(aws bedrock-agent list-knowledge-bases --region "${REGION}" \
  --query "knowledgeBaseSummaries[?starts_with(name, 'thewhoo-kb-')].knowledgeBaseId" \
  --output text 2>/dev/null || echo "")
for kb in ${KB_IDS}; do
  echo "  KB: ${kb}"
  DS_IDS=$(aws bedrock-agent list-data-sources \
    --knowledge-base-id "${kb}" --region "${REGION}" \
    --query 'dataSourceSummaries[].dataSourceId' --output text 2>/dev/null || echo "")
  for ds in ${DS_IDS}; do
    aws bedrock-agent delete-data-source \
      --knowledge-base-id "${kb}" --data-source-id "${ds}" --region "${REGION}" 2>/dev/null \
      && echo "    ✓ DataSource ${ds} 삭제" \
      || echo "    ⚠ DataSource ${ds} 삭제 실패"
  done
  aws bedrock-agent delete-knowledge-base \
    --knowledge-base-id "${kb}" --region "${REGION}" 2>/dev/null \
    && echo "    ✓ KB ${kb} 삭제" \
    || echo "    ⚠ KB ${kb} 삭제 실패"
done
[ -z "${KB_IDS}" ] && echo "  · 없음"

# KB 삭제가 완전히 끝나기 전에 벡터 버킷을 지우면 KB 가 DELETE_UNSUCCESSFUL 로
# 빠집니다 (KB 가 벡터 스토어를 정리하는 중이라 대상이 사라지면 실패).
# 반드시 KB 가 목록에서 사라진 뒤 다음 단계로 갑니다.
if [ -n "${KB_IDS}" ]; then
  echo "  · KB 삭제 완료 대기 (벡터 버킷보다 먼저 사라져야 함)"
  for i in $(seq 1 30); do
    STILL=$(aws bedrock-agent list-knowledge-bases --region "${REGION}" \
      --query "knowledgeBaseSummaries[?starts_with(name, 'thewhoo-kb-')].knowledgeBaseId" \
      --output text 2>/dev/null || echo "")
    [ -z "${STILL}" ] && { echo "    ✓ KB 삭제 완료"; break; }
    [ "${i}" = "30" ] && echo "    ⚠ KB 가 아직 남아 있습니다 (${STILL}) — 벡터 버킷 삭제를 건너뜁니다"
    sleep 6
  done
fi

echo ""
echo "[7.5/11] Mock Lambda 4종 삭제"
# 주의: Mock Lambda 는 CFN 이 아니라 package_lambdas.sh 의 `aws lambda create-function`
# 으로 만들어집니다 (workshop.yaml 에 Lambda::Function 리소스가 없음).
# 따라서 CFN 스택을 지워도 남으므로 여기서 명시적으로 삭제해야 합니다.
FN_NAMES=$(aws lambda list-functions --region "${REGION}" \
  --query "Functions[?starts_with(FunctionName, 'thewhoo-')].FunctionName" \
  --output text 2>/dev/null || echo "")
if [ -n "${FN_NAMES}" ]; then
  for fn in ${FN_NAMES}; do
    aws lambda delete-function --function-name "${fn}" --region "${REGION}" 2>/dev/null \
      && echo "  ✓ ${fn} 삭제" \
      || echo "  ⚠ ${fn} 삭제 실패"
  done
else
  echo "  · 없음"
fi

echo ""
echo "[8/11] S3 Vectors 인덱스 + 버킷 삭제"
VBUCKETS=$(aws s3vectors list-vector-buckets --region "${REGION}" \
  --query 'vectorBuckets[?contains(vectorBucketName, `thewhoo-vec`)].vectorBucketName' \
  --output text 2>/dev/null || echo "")
for vb in ${VBUCKETS}; do
  echo "  Vector Bucket: ${vb}"
  IDXS=$(aws s3vectors list-indexes --vector-bucket-name "${vb}" --region "${REGION}" \
    --query 'indexes[].indexName' --output text 2>/dev/null || echo "")
  for idx in ${IDXS}; do
    aws s3vectors delete-index \
      --vector-bucket-name "${vb}" --index-name "${idx}" --region "${REGION}" 2>/dev/null \
      && echo "    ✓ Index ${idx} 삭제" \
      || echo "    ⚠ Index ${idx} 삭제 실패"
  done
  aws s3vectors delete-vector-bucket \
    --vector-bucket-name "${vb}" --region "${REGION}" 2>/dev/null \
    && echo "    ✓ Vector Bucket ${vb} 삭제" \
    || echo "    ⚠ Vector Bucket ${vb} 삭제 실패"
done
[ -z "${VBUCKETS}" ] && echo "  · 없음"

echo ""
echo "[9/11] CFN 스택 (thewhoo-${PID}) 삭제 — 5~10분 소요"
STACK_NAME="thewhoo-${PID}"
if aws cloudformation describe-stacks --stack-name "${STACK_NAME}" --region "${REGION}" > /dev/null 2>&1; then
  # S3 버킷은 비어있어야 CFN delete 가 통과되므로 먼저 비우기
  for export_key in DataBucket LambdaCodeBucket; do
    BUCKET=$(aws cloudformation list-exports --region "${REGION}" \
      --query "Exports[?Name=='thewhoo-${PID}-${export_key}'].Value | [0]" \
      --output text 2>/dev/null || echo "")
    if [ -n "${BUCKET}" ] && [ "${BUCKET}" != "None" ]; then
      echo "  · S3 버킷 비우는 중: ${BUCKET}"
      aws s3 rm "s3://${BUCKET}" --recursive --region "${REGION}" > /dev/null 2>&1 \
        && echo "    ✓ 비움" \
        || echo "    ⚠ 일부 객체 삭제 실패"
    fi
  done

  aws cloudformation delete-stack --stack-name "${STACK_NAME}" --region "${REGION}" 2>/dev/null
  echo "  · 삭제 요청 — 완료 대기..."
  if aws cloudformation wait stack-delete-complete \
    --stack-name "${STACK_NAME}" --region "${REGION}" 2>/dev/null; then
    echo "  ✓ 스택 삭제 완료"
  else
    echo "  ⚠ 스택 삭제 실패 — 콘솔에서 원인 확인 후 수동 삭제"
    echo "    https://${REGION}.console.aws.amazon.com/cloudformation/home?region=${REGION}#/stacks"
  fi
else
  echo "  · 스택 없음"
fi

echo ""
echo "[9.5/11] 잔존 thewhoo-* S3 버킷 삭제"
# 위 [9/11] 은 CFN export 로 버킷 이름을 찾지만, 스택이 이미 삭제된 상태(재실행 등)
# 에서는 export 가 없어 버킷이 고아로 남습니다. 이름 규칙으로 한 번 더 훑습니다.
ORPHAN_BUCKETS=$(aws s3api list-buckets \
  --query "Buckets[?starts_with(Name, 'thewhoo-')].Name" --output text 2>/dev/null || echo "")
if [ -n "${ORPHAN_BUCKETS}" ]; then
  for b in ${ORPHAN_BUCKETS}; do
    aws s3 rm "s3://${b}" --recursive --region "${REGION}" > /dev/null 2>&1
    aws s3api delete-bucket --bucket "${b}" --region "${REGION}" 2>/dev/null \
      && echo "  ✓ ${b} 삭제" \
      || echo "  ⚠ ${b} 삭제 실패 (버전 객체 남았을 수 있음 — 콘솔 확인)"
  done
else
  echo "  · 없음"
fi

echo ""
echo "[10/11] CloudWatch Dashboard + Alarms 삭제"
aws cloudwatch delete-dashboards --dashboard-names thewhoo-chat-runtime \
  --region "${REGION}" 2>/dev/null \
  && echo "  ✓ Dashboard thewhoo-chat-runtime 삭제" \
  || echo "  · Dashboard 없음"

ALARM_NAMES=$(aws cloudwatch describe-alarms --region "${REGION}" \
  --query "MetricAlarms[?starts_with(AlarmName, 'thewhoo-chat-')].AlarmName" \
  --output text 2>/dev/null || echo "")
if [ -n "${ALARM_NAMES}" ]; then
  aws cloudwatch delete-alarms --alarm-names ${ALARM_NAMES} --region "${REGION}" 2>/dev/null \
    && echo "  ✓ Alarms 삭제: ${ALARM_NAMES}" \
    || echo "  ⚠ Alarms 삭제 실패"
else
  echo "  · Alarms 없음"
fi

echo ""
echo "[11/11] 로컬 cache + .bedrock_agentcore.yaml 정리"
HERE="$(cd "$(dirname "$0")/.." && pwd)"
[ -f "${HERE}/.bedrock_agentcore.yaml" ] && \
  mv "${HERE}/.bedrock_agentcore.yaml" "${HERE}/.bedrock_agentcore.yaml.bak.$(date +%s)" \
  && echo "  ✓ .bedrock_agentcore.yaml → .bak"
rm -rf "${HOME}/.bedrock_agentcore_cache" 2>/dev/null \
  && echo "  ✓ ~/.bedrock_agentcore_cache 삭제" \
  || true

echo ""
echo "[검증] 잔존 리소스 확인"
# AgentCore/Bedrock 삭제는 비동기(DELETING)라 위 단계의 "✓" 는 '요청 성공' 이지
# '삭제 완료' 가 아닙니다. 검증 없이 끝내면 과금 리소스가 남아도 모른 채
# "정리 완료" 로 보이므로, 여기서 실제 잔존 여부를 확인합니다.
LEFT=0
check() {  # $1=라벨  $2=조회 명령 결과
  if [ -n "$2" ] && [ "$2" != "None" ]; then
    echo "  ⚠ 남음 — $1: $2"
    LEFT=$((LEFT+1))
  else
    echo "  ✓ 없음 — $1"
  fi
}

for attempt in 1 2 3 4 5 6; do
  LEFT=0
  R_MEM=$(aws bedrock-agentcore-control list-memories --region "${REGION}" \
    --query "memories[?starts_with(id, 'TheWhooMemory') || starts_with(id, 'thewhoo_chat_mem')].id" \
    --output text 2>/dev/null || echo "")
  R_GW=$(aws bedrock-agentcore-control list-gateways --region "${REGION}" \
    --query "items[?contains(name, 'thewhoo-gateway')].gatewayId" --output text 2>/dev/null || echo "")
  R_KB=$(aws bedrock-agent list-knowledge-bases --region "${REGION}" \
    --query "knowledgeBaseSummaries[?starts_with(name, 'thewhoo-kb-')].knowledgeBaseId" --output text 2>/dev/null || echo "")
  R_VB=$(aws s3vectors list-vector-buckets --region "${REGION}" \
    --query 'vectorBuckets[?contains(vectorBucketName, `thewhoo-vec`)].vectorBucketName' --output text 2>/dev/null || echo "")
  R_FN=$(aws lambda list-functions --region "${REGION}" \
    --query "Functions[?starts_with(FunctionName, 'thewhoo-')].FunctionName" --output text 2>/dev/null || echo "")
  R_BK=$(aws s3api list-buckets \
    --query "Buckets[?starts_with(Name, 'thewhoo-')].Name" --output text 2>/dev/null || echo "")

  [ -n "${R_MEM}${R_GW}${R_KB}${R_VB}${R_FN}${R_BK}" ] || break
  [ "${attempt}" = "6" ] && break
  echo "  · 삭제 진행 중 — 20초 후 재확인 (${attempt}/5)"
  sleep 20
done

check "Memory"        "${R_MEM}"
check "Gateway"       "${R_GW}"
check "Knowledge Base" "${R_KB}"
check "Vector Bucket" "${R_VB}"
check "Lambda"        "${R_FN}"
check "S3 버킷"        "${R_BK}"

echo ""
echo "==================================================================="
if [ "${LEFT}" -eq 0 ]; then
  echo " ✓ 정리 완료 — 잔존 리소스 없음"
else
  echo " ⚠ 정리 미완료 — ${LEFT}종류가 아직 남아 있습니다"
  echo ""
  echo "   비동기 삭제가 진행 중일 수 있습니다. 2~3분 후 이 스크립트를"
  echo "   한 번 더 실행하세요:  ./scripts/cleanup-all.sh ${PID} --yes"
  echo "   계속 남아 있으면 위 목록의 리소스를 콘솔에서 직접 삭제하세요."
  echo "   (특히 KB / Vector Bucket / Lambda 는 과금이 계속됩니다)"
fi
echo "==================================================================="
echo ""
echo "다음:"
echo "  1) CloudShell 에서 처음부터 다시:"
echo "       cd ~/thewhoo-agentcore-workshop && git pull"
echo "       ./scripts/setup-day2-cloudshell.sh ${PID}"
echo ""
echo "  2) Code Editor 의 기존 터미널을 닫고 새 터미널을 연 뒤:"
echo "       cd ~/thewhoo-agentcore-workshop && source .venv/bin/activate"
echo "       ./scripts/setup-day2-codeeditor.sh ${PID}"
echo ""
