#!/usr/bin/env bash
# Lab 6 의 "5단계 오류 케이스 관찰" 테스트용.
#
# 정상 invoke 와 의도된 에러 invoke 를 섞어 보내 GenAI Dashboard 의
# 빨간 ! 마크 / Sessions 탭의 turn 수 증가를 확인합니다.
#
# 워크샵 agent 는 도구 호출 실패도 LLM 이 받아서 친절한 답변으로 정리해
# 내보내기 때문에 일반적인 invoke 만으로는 trace 가 OK 로 끝납니다.
# 이 스크립트는 다음 3가지 의도적 에러 케이스를 생성합니다:
#
#   1. payload 형식 오류         → AgentCore Runtime layer 에서 4xx 응답
#   2. 빈 message                → src/app.py 에서 "메시지를 입력해주세요." 응답 (정상이지만 trace 단축)
#   3. 매우 긴 prompt loop 유도  → 모델 호출은 정상이지만 cost spike 시그널
#
# Usage:
#   ./scripts/test-error-trace.sh

set -uo pipefail

# runtimeSessionId 최소 33자 제약 — uuid 붙여 길이 확보
SID_BASE="error-test-$(date +%s)-$(python3 -c 'import uuid; print(uuid.uuid4())')"
echo "session prefix: ${SID_BASE}"
echo ""

# (1) payload schema 위반 — message 필드 자체 없음
echo "[1/3] payload schema 위반 (message 필드 누락)"
agentcore invoke --session-id "${SID_BASE}-1" "{\"foo\":\"bar\"}" > /tmp/err1.txt 2>&1 || true
echo "  → 응답 끝부분:"
tail -3 /tmp/err1.txt | sed 's/^/    /'
echo ""

# (2) 잘못된 JSON
echo "[2/3] payload JSON 파싱 실패"
agentcore invoke "this-is-not-json" > /tmp/err2.txt 2>&1 || true
echo "  → 응답 끝부분:"
tail -3 /tmp/err2.txt | sed 's/^/    /'
echo ""

# (3) 정상 invoke 한 번 (대조군)
echo "[3/3] 정상 invoke (대조군)"
agentcore invoke --session-id "${SID_BASE}-3" "{\"message\":\"보습크림 추천\"}" > /tmp/err3.txt 2>&1 || true
echo "  → 응답 끝부분:"
tail -3 /tmp/err3.txt | sed 's/^/    /'
echo ""

echo "==================================================================="
echo " 결과 확인 (5~10분 후)"
echo "==================================================================="
echo "  GenAI Dashboard → Sessions 탭에서 다음 검색:"
echo "    ${SID_BASE}-1  → 빨간 ! 마크 보여야 정상 (validation error)"
echo "    ${SID_BASE}-3  → ! 없는 정상 trace"
echo ""
echo "  CloudWatch metric (UserErrors) 도 5~10분 후 +1 잡혀야 합니다:"
echo ""
echo "    aws cloudwatch get-metric-statistics \\"
echo "      --namespace AWS/Bedrock-AgentCore --metric-name UserErrors \\"
echo "      --dimensions \\"
echo "        Name=Resource,Value=<RUNTIME_ARN> \\"
echo "        Name=Operation,Value=InvokeAgentRuntime \\"
echo "        Name=Name,Value=thewhoo_chat::DEFAULT \\"
echo "      --start-time \$(date -u -d '20 minutes ago' '+%Y-%m-%dT%H:%M:%SZ') \\"
echo "      --end-time \$(date -u '+%Y-%m-%dT%H:%M:%SZ') \\"
echo "      --period 60 --statistics Sum --region us-east-1"
echo ""
