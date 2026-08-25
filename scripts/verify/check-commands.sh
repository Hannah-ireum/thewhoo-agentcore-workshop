#!/usr/bin/env bash
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
# 3차 — 문서에 적힌 '읽기 전용' 명령을 실제로 실행해 문법 오류를 잡는다
E=0
chk(){ desc="$1"; shift; if out=$("$@" 2>&1); then echo "  OK   $desc"; else echo "  FAIL $desc"; echo "$out"|head -3|sed 's/^/       /'; E=$((E+1)); fi; }

# 프로젝트가 없는 빈 디렉터리에서 관문을 돌리면 exit 1 + "프로젝트 미생성" 안내여야 정상
gate_check(){
  local d out rc
  d=$(mktemp -d) || return 1
  mkdir -p "$d/scripts"
  cp "$REPO/scripts/check-agentcore-config.sh" "$d/scripts/" || { rm -rf "$d"; return 1; }
  out=$(cd "$d" && bash scripts/check-agentcore-config.sh 2>&1); rc=$?
  rm -rf "$d"
  [ "$rc" -ne 0 ] && printf '%s' "$out" | grep -q "프로젝트 미생성"
}

echo "=== Lab7 문서의 metric 조회 명령 ==="
ACC=$(aws sts get-caller-identity --query Account --output text)
chk "get-metric-statistics (문서 명령 형태)" aws cloudwatch get-metric-statistics \
  --namespace AWS/Bedrock-AgentCore --metric-name Invocations \
  --dimensions Name=Resource,Value="arn:aws:bedrock-agentcore:us-east-1:${ACC}:runtime/dummy" \
               Name=Operation,Value=InvokeAgentRuntime Name=Name,Value="dummy::DEFAULT" \
  --start-time "$(date -u -v-24H +%Y-%m-%dT%H:%M:%SZ)" --end-time "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  --period 60 --statistics Sum --region us-east-1

echo "=== 문서의 리소스 조회 명령 (JMESPath 문법 포함) ==="
chk "list-agent-runtimes + hewhoo 필터" aws bedrock-agentcore-control list-agent-runtimes --region us-east-1 \
  --query "agentRuntimes[?contains(agentRuntimeName,'hewhoo')].agentRuntimeId | [0]" --output text
chk "list-gateways + thewhoo-gateway 필터" aws bedrock-agentcore-control list-gateways --region us-east-1 \
  --query "items[?contains(name,'thewhoo-gateway')].gatewayId | [0]" --output text
chk "list-knowledge-bases + thewhoo-kb 필터" aws bedrock-agent list-knowledge-bases --region us-east-1 \
  --query "knowledgeBaseSummaries[?starts_with(name,'thewhoo-kb-')].knowledgeBaseId" --output text
chk "list-evaluators" aws bedrock-agentcore-control list-evaluators --region us-east-1 --query 'length(evaluators)' --output text

echo "=== 스크립트 --help / dry 경로 ==="
chk "print-env.sh"            ./scripts/print-env.sh w001
chk "check-agentcore-config.sh 안내 종료" gate_check
chk "count-categories.py"     ./.venv/bin/python scripts/count-categories.py
chk "eval-report.py --help"   ./.venv/bin/python scripts/eval-report.py --help
chk "run-golden-eval.py --help" ./.venv/bin/python scripts/run-golden-eval.py --help
# agentcore.json 이 없는 빈 디렉터리에서 실행하면 raw traceback 이 아니라
# 안내 메시지로 종료해야 정상입니다.
chk "set-agentcore-config.py 안내 종료" bash -c '
  d=$(mktemp -d); cd "$d"
  out=$("'"$REPO"'/.venv/bin/python" "'"$REPO"'/scripts/set-agentcore-config.py" 2>&1)
  rm -rf "$d"
  echo "$out" | grep -q "agentcore/agentcore.json 가 없습니다"'

echo; echo "3차 실패: ${E}건"
