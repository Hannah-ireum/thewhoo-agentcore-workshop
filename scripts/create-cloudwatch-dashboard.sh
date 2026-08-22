#!/usr/bin/env bash
# Lab 7 — thewhoo_chat 운영용 CloudWatch Dashboard 생성/갱신
#
# 사용법:
#   ./scripts/create-cloudwatch-dashboard.sh                # 기본 이름: thewhoo-chat-runtime
#   ./scripts/create-cloudwatch-dashboard.sh my-dashboard
#
# 무엇을 만드나:
#   1) 호출량 / 에러 / Throttle (AWS/Bedrock-AgentCore native metric)
#   2) Latency P50 / P95 / P99 (native metric)
#   3) Session 수 (native metric)
#   4) 모델별 토큰 사용량 (Logs Insights → aws/spans)
#   5) Prompt cache hit ratio (cache_read / total_input × 100)
#   6) CPU·Memory 사용량 (vCPU-Hours / GB-Hours, native vended metric)
#   7) Runtime 애플리케이션 로그 에러 tail (Logs Insights → 런타임 log group)
#   8) GenAI Observability 페이지 링크 (text widget)
#
# GenAI Observability 와의 차이:
#   - GenAI Observability 는 단일 trace 드릴다운용 (디버깅).
#   - 이 Dashboard 는 KPI 시계열·알람 연결·URL 공유용 (운영 모니터링).

set -euo pipefail

DASHBOARD_NAME="${1:-thewhoo-chat-runtime}"
REGION="${AWS_REGION:-us-east-1}"

echo "==================================================================="
echo " CloudWatch Dashboard 생성/갱신"
echo "==================================================================="
echo "  Dashboard 이름 : ${DASHBOARD_NAME}"
echo "  Region         : ${REGION}"
echo ""

# Runtime ID / ARN / log group 자동 탐지
RUNTIME_ID=$(aws bedrock-agentcore-control list-agent-runtimes --region "${REGION}" \
  --query "agentRuntimes[?contains(agentRuntimeName, 'thewhoo') || contains(agentRuntimeName, 'Thewhoo')].agentRuntimeId | [0]" \
  --output text 2>/dev/null || echo "")

if [ -z "${RUNTIME_ID}" ] || [ "${RUNTIME_ID}" = "None" ]; then
  # 원인이 둘입니다 — 구분해서 안내해야 합니다.
  #  (a) Lab 5 를 아직 안 했다 → Runtime 이 실제로 없음
  #  (b) CLI 가 bedrock-agentcore-control 을 모른다 → 있어도 조회 실패
  # 위 조회가 `2>/dev/null || echo ""` 라 (b) 도 빈 값으로 나옵니다.
  if ! aws bedrock-agentcore-control help > /dev/null 2>&1; then
    echo "❌ 이 AWS CLI 는 bedrock-agentcore-control 을 모릅니다 (Runtime 조회 불가)."
    echo "   $(aws --version 2>&1 | head -1)"
    echo "   Runtime 이 이미 배포돼 있어도 이 CLI 로는 찾을 수 없습니다."
    echo "   CLI v2 를 최신으로 올린 뒤 다시 실행하세요:"
    echo "     curl -s 'https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip' -o /tmp/awscliv2.zip"
    echo "     unzip -q -o /tmp/awscliv2.zip -d /tmp && sudo /tmp/aws/install --update"
  else
    echo "❌ thewhoo 계열 Runtime 을 찾지 못했습니다. Lab 5 의 agentcore deploy 가 끝났는지 확인하세요."
  fi
  exit 1
fi

ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
RUNTIME_ARN="arn:aws:bedrock-agentcore:${REGION}:${ACCOUNT_ID}:runtime/${RUNTIME_ID}"
RUNTIME_LOG_GROUP="/aws/bedrock-agentcore/runtimes/${RUNTIME_ID}-DEFAULT"
# Name dimension 은 "<agent_name>::DEFAULT" 형식 — RUNTIME_ID 의 ID suffix (-XXXXXX)
# 를 제거한 agent_name 만 사용합니다 (예: thewhoo_chat-oC7Q624bjH → thewhoo_chat).
AGENT_NAME="${RUNTIME_ID%-*}"
RUNTIME_NAME_DIM="${AGENT_NAME}::DEFAULT"
echo "  Runtime ID     : ${RUNTIME_ID}"
echo "  Runtime ARN    : ${RUNTIME_ARN}"
echo "  Name dimension : ${RUNTIME_NAME_DIM}"
echo "  Runtime LogGrp : ${RUNTIME_LOG_GROUP}"
echo ""

# Dashboard body — 위젯 8개. JSON 안의 \" 는 escape, ${VAR} 는 셸 치환됨.
BODY=$(cat <<JSON
{
  "widgets": [
    {
      "type": "text",
      "x": 0, "y": 0, "width": 24, "height": 2,
      "properties": {
        "markdown": "# thewhoo_chat — Runtime Operations\n\n운영 KPI 모니터링용 Dashboard 입니다. 단일 trace 드릴다운은 [GenAI Observability](https://console.aws.amazon.com/cloudwatch/home?region=${REGION}#gen-ai-observability) 에서 보세요."
      }
    },
    {
      "type": "metric",
      "x": 0, "y": 2, "width": 12, "height": 6,
      "properties": {
        "title": "호출량 / 에러 / Throttle",
        "region": "${REGION}",
        "stat": "Sum",
        "period": 60,
        "view": "timeSeries",
        "stacked": false,
        "metrics": [
          [ "AWS/Bedrock-AgentCore", "Invocations", "Resource", "${RUNTIME_ARN}", "Operation", "InvokeAgentRuntime", "Name", "${RUNTIME_NAME_DIM}", { "label": "Invocations" } ],
          [ ".", "UserErrors", ".", ".", ".", ".", ".", ".", { "label": "User Errors", "color": "#ff7f0e" } ],
          [ ".", "SystemErrors", ".", ".", ".", ".", ".", ".", { "label": "System Errors", "color": "#d62728" } ],
          [ ".", "Throttles", ".", ".", ".", ".", ".", ".", { "label": "Throttles", "color": "#9467bd" } ]
        ]
      }
    },
    {
      "type": "metric",
      "x": 12, "y": 2, "width": 12, "height": 6,
      "properties": {
        "title": "Latency P50 / P95 / P99 (ms)",
        "region": "${REGION}",
        "period": 60,
        "view": "timeSeries",
        "metrics": [
          [ "AWS/Bedrock-AgentCore", "Latency", "Resource", "${RUNTIME_ARN}", "Operation", "InvokeAgentRuntime", "Name", "${RUNTIME_NAME_DIM}", { "stat": "p50", "label": "P50" } ],
          [ "...", { "stat": "p95", "label": "P95" } ],
          [ "...", { "stat": "p99", "label": "P99" } ]
        ]
      }
    },
    {
      "type": "metric",
      "x": 0, "y": 8, "width": 12, "height": 6,
      "properties": {
        "title": "Session 수 (시간대별)",
        "region": "${REGION}",
        "stat": "Sum",
        "period": 300,
        "view": "timeSeries",
        "metrics": [
          [ "AWS/Bedrock-AgentCore", "Sessions", "Resource", "${RUNTIME_ARN}", "Operation", "InvokeAgentRuntime", "Name", "${RUNTIME_NAME_DIM}", { "label": "Sessions" } ]
        ]
      }
    },
    {
      "type": "log",
      "x": 12, "y": 8, "width": 12, "height": 6,
      "properties": {
        "title": "모델별 토큰 사용량 (Logs Insights · aws/spans)",
        "region": "${REGION}",
        "view": "table",
        "query": "SOURCE 'aws/spans' | filter attributes.gen_ai.request.model like /claude/ | stats sum(attributes.gen_ai.usage.input_tokens) as input_tokens, sum(attributes.gen_ai.usage.output_tokens) as output_tokens, sum(attributes.gen_ai.usage.cache_read_input_tokens) as cache_read by attributes.gen_ai.request.model"
      }
    },
    {
      "type": "log",
      "x": 0, "y": 14, "width": 12, "height": 6,
      "properties": {
        "title": "Prompt Cache Hit Ratio (% · cache_read / 전체 input · 급락 시 회귀 의심)",
        "region": "${REGION}",
        "view": "timeSeries",
        "stacked": false,
        "query": "SOURCE 'aws/spans' | filter attributes.gen_ai.request.model like /claude/ | stats sum(attributes.gen_ai.usage.cache_read_input_tokens) * 100 / (sum(attributes.gen_ai.usage.input_tokens) + sum(attributes.gen_ai.usage.cache_read_input_tokens) + sum(attributes.gen_ai.usage.cache_write_input_tokens)) as cache_hit_pct by bin(5m)"
      }
    },
    {
      "type": "metric",
      "x": 12, "y": 14, "width": 12, "height": 6,
      "properties": {
        "title": "Resource 사용량 — vCPU-Hours / GB-Hours (vended, 최대 60분 지연)",
        "region": "${REGION}",
        "stat": "Sum",
        "period": 300,
        "view": "timeSeries",
        "metrics": [
          [ "AWS/Bedrock-AgentCore", "CPUUsed-vCPUHours", "Service", "AgentCore.Runtime", { "label": "vCPU-Hours" } ],
          [ ".", "MemoryUsed-GBHours", ".", ".", { "label": "GB-Hours", "yAxis": "right" } ]
        ]
      }
    },
    {
      "type": "log",
      "x": 0, "y": 20, "width": 24, "height": 6,
      "properties": {
        "title": "Runtime 에러 로그 tail (최근 50건 — 평소 비어있는 게 정상)",
        "region": "${REGION}",
        "view": "table",
        "query": "SOURCE '${RUNTIME_LOG_GROUP}' | fields @timestamp, severityNumber, scope.name, attributes.error_type, attributes.session.id, @message | filter severityNumber >= 17 or @message like /Exception|Traceback|denied|InternalServerError|ValidationException|InvalidPayload/ | sort @timestamp desc | limit 50"
      }
    }
  ]
}
JSON
)

echo "Dashboard 적용..."
aws cloudwatch put-dashboard \
  --dashboard-name "${DASHBOARD_NAME}" \
  --dashboard-body "${BODY}" \
  --region "${REGION}" > /dev/null

DASH_URL="https://${REGION}.console.aws.amazon.com/cloudwatch/home?region=${REGION}#dashboards:name=${DASHBOARD_NAME}"
echo "✓ 적용 완료"
echo ""
echo "  Dashboard URL : ${DASH_URL}"
echo ""
echo "다음:"
echo "  1) 위 URL 접속"
echo "  2) 일부 위젯이 비어 있다면 처음 5~10분간은 metric 데이터가 부족해서 정상."
echo "     invoke 를 몇 번 더 발생시킨 뒤 새로고침."
echo "  3) (옵션) 알람 연결 — 각 metric 위젯의 '...' 메뉴 → 'Create alarm'."
echo "     예: P95 > 5000ms 이면 SNS topic 으로 알림."
echo ""
