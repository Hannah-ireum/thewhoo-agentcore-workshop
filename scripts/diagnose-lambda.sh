#!/usr/bin/env bash
# Gateway 경유로 'internal error' 가 나오면 실제 Lambda 에러가 가려집니다.
# 이 스크립트는 Lambda 를 직접 호출해 진짜 오류 메시지를 보여줍니다.
#
# Usage:
#   ./scripts/diagnose-lambda.sh <participant-id>
#   예) ./scripts/diagnose-lambda.sh w001

set -uo pipefail

PID="${1:?사용법: ./scripts/diagnose-lambda.sh <participant-id>}"
REGION="${AWS_REGION:-us-east-1}"

echo "==================================================================="
echo " Lambda 직접 호출 진단 (participant=${PID})"
echo "==================================================================="

call() {
    local fn="$1"
    local payload="$2"
    echo ""
    echo "───── ${fn} ─────"
    echo "payload: ${payload}"
    local tmp
    tmp=$(mktemp)
    local status
    status=$(aws lambda invoke \
        --function-name "thewhoo-${fn}-${PID}" \
        --cli-binary-format raw-in-base64-out \
        --payload "${payload}" \
        --region "${REGION}" \
        "${tmp}" --query 'FunctionError' --output text 2>&1) || true
    echo "FunctionError: ${status}"
    echo "Response:"
    cat "${tmp}"
    echo ""
    rm -f "${tmp}"
}

# 시나리오 1 에서 터진 호출 재현
call "product-search" '{"body":"{\"query\":\"향수\",\"category\":\"향수\",\"price_max\":30000}"}'

# 정상 호출 비교용
call "recommend" '{"body":"{\"skin_type\":\"건성\",\"concerns\":[\"보습\"]}"}'
call "check-stock" '{"body":"{\"product_id\":\"WHOO-00101\"}"}'

echo ""
echo "FunctionError = None 이면 Lambda 는 정상. Gateway 쪽 문제일 가능성."
echo "FunctionError = Unhandled 면 Response 의 errorMessage / stackTrace 확인."
