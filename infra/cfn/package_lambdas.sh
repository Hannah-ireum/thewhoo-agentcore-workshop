#!/usr/bin/env bash
# Workshop Studio blueprint 배포 순서:
#   A) ./package_lambdas.sh <pid> prep    → Lambda 코드 버킷 생성 (CFN 전)
#   B) aws cloudformation deploy --template-file workshop.yaml ...
#   C) python bootstrap_kb.py <pid>       → KB 자동 셋업 (Lab 0 대체)
#   D) ./package_lambdas.sh <pid> mocks   → Mock Lambda 4종 생성 (CFN 후)
set -euo pipefail

PARTICIPANT_ID="${1:?usage: package_lambdas.sh <participant-id> [prep|mocks|all]}"
MODE="${2:-all}"
REGION="${3:-us-east-1}"

STACK_NAME="thewhoo-${PARTICIPANT_ID}"
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
CODE_BUCKET="thewhoo-code-${PARTICIPANT_ID}-${ACCOUNT_ID}"
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"

ensure_bucket() {
  if ! aws s3api head-bucket --bucket "${CODE_BUCKET}" --region "${REGION}" 2>/dev/null; then
    echo "Creating code bucket s3://${CODE_BUCKET}"
    if [ "${REGION}" = "us-east-1" ]; then
      aws s3api create-bucket --bucket "${CODE_BUCKET}" --region "${REGION}" > /dev/null
    else
      aws s3api create-bucket --bucket "${CODE_BUCKET}" --region "${REGION}" \
        --create-bucket-configuration "LocationConstraint=${REGION}" > /dev/null
    fi
  fi
}

upload_mock_lambdas() {
  # CFN 배포가 완료된 이후에만 동작. Outputs 에서 LambdaRoleArn 등을 조회합니다.
  local bucket lambda_role
  bucket=$(aws cloudformation describe-stacks \
    --stack-name "${STACK_NAME}" --region "${REGION}" \
    --query "Stacks[0].Outputs[?OutputKey=='LambdaCodeBucketName'].OutputValue" \
    --output text)
  lambda_role=$(aws cloudformation describe-stacks \
    --stack-name "${STACK_NAME}" --region "${REGION}" \
    --query "Stacks[0].Outputs[?OutputKey=='LambdaRoleArn'].OutputValue" \
    --output text)

  local work; work="$(mktemp -d)"
  echo "Packaging Mock Lambdas → s3://${bucket}/"

  for fn in product_search recommend_products check_stock get_promotion; do
    local stage="${work}/${fn}"
    mkdir -p "${stage}/_shared"
    cp "${ROOT}/lambdas/${fn}/app.py" "${stage}/app.py"
    # _shared/ 안에서 python 파일만 복사 (beauty_products.jsonl 은 symlink 라 제외)
    cp "${ROOT}/lambdas/_shared/products.py" "${stage}/_shared/products.py"
    touch "${stage}/_shared/__init__.py"
    # 데이터 파일은 실제 경로에서 복사 (symlink 를 dereference)
    cp "${ROOT}/data/beauty_products.jsonl" "${stage}/beauty_products.jsonl"
    cp "${ROOT}/data/beauty_products.jsonl" "${stage}/_shared/beauty_products.jsonl"
    ( cd "${stage}" && zip -qr "${work}/${fn}.zip" . )
    aws s3 cp "${work}/${fn}.zip" "s3://${bucket}/${fn}.zip" --region "${REGION}"

    local func_name
    case "${fn}" in
      product_search)     func_name="thewhoo-product-search-${PARTICIPANT_ID}" ;;
      recommend_products) func_name="thewhoo-recommend-${PARTICIPANT_ID}" ;;
      check_stock)        func_name="thewhoo-check-stock-${PARTICIPANT_ID}" ;;
      get_promotion)      func_name="thewhoo-get-promotion-${PARTICIPANT_ID}" ;;
    esac

    if aws lambda get-function --function-name "${func_name}" --region "${REGION}" > /dev/null 2>&1; then
      aws lambda update-function-code \
        --function-name "${func_name}" \
        --s3-bucket "${bucket}" --s3-key "${fn}.zip" \
        --region "${REGION}" > /dev/null
      echo "  ↑ ${func_name} (updated)"
    else
      # 환경변수는 의도적으로 생성하지 않습니다.
      # 환경변수가 존재하면 Lambda 가 기동 시 KMS decrypt 를 시도하는데,
      # Workshop Studio 임시 계정에서 AWS 관리 KMS 키(aws/lambda) decrypt 가
      # SCP 로 막혀 KMSAccessDeniedException 으로 기동 자체가 실패하는 사례가
      # 발생했습니다. BEAUTY_PRODUCTS_FILE 경로는 products.py 의
      # DEFAULT_DATA_PATH 와 동일하므로 환경변수 없이도 정상 동작합니다.
      aws lambda create-function \
        --function-name "${func_name}" \
        --runtime python3.11 --handler app.handler \
        --role "${lambda_role}" \
        --code "S3Bucket=${bucket},S3Key=${fn}.zip" \
        --timeout 10 --memory-size 256 \
        --region "${REGION}" > /dev/null
      echo "  + ${func_name} (created)"
    fi
  done

  echo ""
  echo "Lambda ARNs:"
  for fn in product_search recommend_products check_stock get_promotion; do
    case "${fn}" in
      product_search)     func_name="thewhoo-product-search-${PARTICIPANT_ID}" ;;
      recommend_products) func_name="thewhoo-recommend-${PARTICIPANT_ID}" ;;
      check_stock)        func_name="thewhoo-check-stock-${PARTICIPANT_ID}" ;;
      get_promotion)      func_name="thewhoo-get-promotion-${PARTICIPANT_ID}" ;;
    esac
    local arn
    arn=$(aws lambda get-function --function-name "${func_name}" --region "${REGION}" \
      --query "Configuration.FunctionArn" --output text)
    echo "  ${fn}: ${arn}"
  done
}

case "${MODE}" in
  prep)  ensure_bucket ;;
  mocks) upload_mock_lambdas ;;
  all)   ensure_bucket; upload_mock_lambdas ;;
  *)     echo "mode must be one of: prep, mocks, all"; exit 1 ;;
esac

echo ""
echo "Done."
