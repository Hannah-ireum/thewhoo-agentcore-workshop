#!/usr/bin/env bash
# 샘플 데이터를 상품별 개별 파일로 재업로드하고 KB data source 를 재생성.
#
# 초기 bootstrap_kb.py 가 파일 1개(전체 상품) 를 1 chunk 로 넣어 top1 만 돌아오던
# 문제를 해결합니다. 상품별 파일 분할로 chunk 개수 = 상품 개수가 됩니다.
#
# Usage:
#   ./scripts/reindex-kb.sh <participant-id>
set -euo pipefail

PID="${1:?사용법: ./scripts/reindex-kb.sh <participant-id>}"
REGION="${AWS_REGION:-us-east-1}"
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

STACK_NAME="thewhoo-${PID}"
DATA_BUCKET="thewhoo-data-${PID}-${ACCOUNT_ID}"
KB_NAME="thewhoo-kb-${PID}"
HERE="$(cd "$(dirname "$0")/.." && pwd)"

echo ""
echo "==================================================================="
echo " KB 재인덱싱 (상품별 chunk 분리)"
echo "==================================================================="

# 1) 기존 products.jsonl 한 파일이 있으면 삭제
aws s3 rm "s3://${DATA_BUCKET}/beauty/products.jsonl" --region "${REGION}" 2>/dev/null || true

# 2) KB ID 조회
KB_ID=$(aws bedrock-agent list-knowledge-bases --region "${REGION}" \
  --query "knowledgeBaseSummaries[?name=='${KB_NAME}'].knowledgeBaseId" --output text 2>/dev/null)
if [ -z "${KB_ID}" ]; then
  echo "[ERROR] KB '${KB_NAME}' 를 찾을 수 없습니다."
  exit 1
fi
echo "  KB_ID = ${KB_ID}"

# 3) 기존 data source 삭제 (한 파일 기반)
for ds in $(aws bedrock-agent list-data-sources --knowledge-base-id "${KB_ID}" --region "${REGION}" \
    --query 'dataSourceSummaries[].dataSourceId' --output text 2>/dev/null); do
  echo "  기존 data source 삭제: ${ds}"
  aws bedrock-agent delete-data-source --knowledge-base-id "${KB_ID}" --data-source-id "${ds}" \
    --region "${REGION}" 2>/dev/null || true
done

# 4) bootstrap_kb.py 의 create_ds_and_ingest 와 동일한 로직을 직접 실행
echo "  상품 전체를 개별 JSON 파일로 업로드 + 재인덱싱"
python3 "${HERE}/infra/cfn/bootstrap_kb.py" "${PID}" "${REGION}"

echo ""
echo "==================================================================="
echo " ✓ 재인덱싱 완료 — 1~2분 후 retrieve 가능"
echo "==================================================================="
echo ""
echo "1~2분 후 테스트:"
echo ""
echo "  python3 scripts/pretty-retrieve.py \"건성 피부에 좋은 보습크림\""
echo "  python3 scripts/pretty-retrieve.py \"지성 클렌저\""
echo "  python3 scripts/pretty-retrieve.py \"향수\""
