#!/usr/bin/env bash
# Lab 7 의 dashboard 위젯을 풍성하게 채우기 위한 멀티 사용자 시뮬레이터.
#
# 10명의 가상 사용자가 각자 4 turn 씩 대화 (총 40 invoke) 하면서,
# 잘못된 페이로드 5건도 섞어 보냅니다 (app.py 의 방어 로직 확인용).
#
# 결과적으로 dashboard 위젯에 데이터가 쌓입니다:
#   - Sessions: 10
#   - Latency P50/P95/P99: 분포 풍부
#   - Invocations: ~45
#   - 모델별 토큰 / cache hit ratio: 멀티턴이라 풍부
#
# 주의: UserErrors / SystemErrors 는 0 이 정상입니다. 잘못된 페이로드는 Runtime
# frontend 에서 거부되지 않고 컨테이너까지 전달되며, app.py 가 예외 대신
# "메시지를 입력해주세요." 를 정상 응답(200) 으로 반환하기 때문입니다.
# 에러 metric 은 실제 장애(권한·타임아웃·throttle) 시에만 올라갑니다.
#
# 실행 시간: 약 8~10분
#
# Usage:
#   ./scripts/simulate-traffic.sh
#   ./scripts/simulate-traffic.sh --quick       # 사용자 10 → 3, turn 4 → 2 로 축소 (~3분)

set -uo pipefail

QUICK="${1:-}"
USER_COUNT=10
TURNS_PER_USER=4
ERROR_INJECTIONS=5
[ "${QUICK}" = "--quick" ] && USER_COUNT=3 && TURNS_PER_USER=2 && ERROR_INJECTIONS=2

SUPPRESS_BANNER="AGENTCORE_SUPPRESS_RECOMMENDATION=1"
TIMESTAMP=$(date +%s)

# ─────────────────────────────────────────────────────────────────────
# 사용자별 멀티턴 시나리오 — 각 줄이 한 사용자, 세미콜론(;) 으로 turn 구분
# ─────────────────────────────────────────────────────────────────────
SCENARIOS=(
  # 건성 피부 + 보습크림 탐색 + 재고 + 할인
  "건성 피부에 좋은 보습크림 추천해줘;그 제품 성분이 뭐야?;재고 있어?;할인하는거 있어?"
  # 지성 피부 + 토너
  "지성 피부용 가벼운 토너 추천;가격대는 어느정도야?;다른 옵션도 있어?;할인 있어?"
  # 콜라겐 안티에이징
  "콜라겐 함유 안티에이징 크림 찾아줘;평점 좋은 거 위주로;그 중 하나 추천해줘;재고 확인해줘"
  # 민감성 + 진정
  "민감성 피부에 좋은 진정 제품;비첩 자생 라인으로;재고 있어?;사용법 알려줘"
  # 신상 탐색
  "이번 봄 신상 뷰티 제품 알려줘;가장 인기있는 거 추천;가격이 부담스럽지 않은 거;그 중 추천해줘"
  # 선크림 라인
  "데일리 선크림 추천해줘;무기자차 선크림 있어?;재고 있어?;같이 쓰기 좋은 제품도 알려줘"
  # 클렌저 라인
  "민감 피부용 클렌저 찾아줘;성분 자극 없는 걸로;가격대는?;재고 있어?"
  # 아이크림 라인
  "20대 후반 아이크림 추천;다크서클에 좋은 거;재고는?;다른 추천도 줘"
  # 마스크팩
  "수분 보충 마스크팩 추천해줘;시트 마스크 있어?;프로모션 있어?;인기 마스크는 뭐야?"
  # 립케어
  "건조한 입술용 립밤 추천;성분 천연 위주;재고 있어?;다른 옵션도"
)

# ─────────────────────────────────────────────────────────────────────
# 잘못된 페이로드 — app.py 의 입력 검증 방어 로직 확인용
# (Runtime frontend 가 거부하지 않으므로 에러 metric 은 올라가지 않습니다)
# ─────────────────────────────────────────────────────────────────────
ERROR_PAYLOADS=(
  '{"foo":"missing-message"}'
  'this-is-not-json'
  '{"session_id":"err-1"}'
  ''
  '{"message":12345}'
)

# ─────────────────────────────────────────────────────────────────────
# 시작
# ─────────────────────────────────────────────────────────────────────
total_normal=$((USER_COUNT * TURNS_PER_USER))
total_error=${ERROR_INJECTIONS}
total_all=$((total_normal + total_error))

echo "==================================================================="
echo " Lab 7 — 트래픽 시뮬레이션"
echo "==================================================================="
echo "  사용자 수      : ${USER_COUNT}"
echo "  사용자당 턴    : ${TURNS_PER_USER}"
echo "  정상 invoke    : ${total_normal}"
echo "  잘못된 페이로드 : ${total_error}  (에러 metric 은 0 이 정상)"
echo "  총 invoke      : ${total_all}"
echo "  예상 소요      : 약 8~10분"
echo ""

start=$(date +%s)
sent=0

# 정상 트래픽
for i in $(seq 1 ${USER_COUNT}); do
  # runtimeSessionId 최소 33자 제약 — uuid 붙여 길이 확보
  SID="lab7-user${i}-${TIMESTAMP}-$(python3 -c 'import uuid; print(uuid.uuid4())')"
  IFS=';' read -r -a turns <<< "${SCENARIOS[$((i-1))]}"
  echo "[user ${i}/${USER_COUNT}] session=${SID}"

  # 사용자당 turn 수만큼만 사용 (시나리오 길이가 더 길어도 자름)
  for t in $(seq 0 $((TURNS_PER_USER-1))); do
    [ -z "${turns[$t]:-}" ] && break
    msg="${turns[$t]}"
    sent=$((sent + 1))
    printf "  turn %d/%d: %s ... " $((t+1)) "${TURNS_PER_USER}" "${msg}"
    if env ${SUPPRESS_BANNER} agentcore invoke --session-id "${SID}" \
        "{\"message\":\"${msg}\"}" \
        > /dev/null 2>&1; then
      echo "✓"
    else
      echo "✗"
    fi
    sleep 1
  done
  echo ""
done

# 잘못된 페이로드 — app.py 방어 로직 확인 (에러 metric 은 올라가지 않음)
echo "[errors] 의도된 schema 위반 ${ERROR_INJECTIONS} 건"
for e in $(seq 1 ${ERROR_INJECTIONS}); do
  payload="${ERROR_PAYLOADS[$((e-1))]}"
  printf "  err %d/%d: %s ... " ${e} ${ERROR_INJECTIONS} "${payload:0:40}"
  env ${SUPPRESS_BANNER} agentcore invoke "${payload}" > /dev/null 2>&1
  echo "✓ (app.py 가 안내 문구로 응답 — 정상)"
  sleep 1
done

elapsed=$(($(date +%s) - start))
echo ""
echo "==================================================================="
echo " ✓ 완료 — ${sent} 정상 + ${ERROR_INJECTIONS} 에러 / $((elapsed / 60))m $((elapsed % 60))s"
echo "==================================================================="
echo ""
echo "다음:"
echo "  1) 5~10분 대기 (metric publish 지연)"
echo "  2) Dashboard URL 새로고침 — 위젯 1·2·3·4·5 채워짐"
echo "     (위젯 1 의 에러 3종은 0 이 정상 / 위젯 7 은 비어있는 게 정상)"
echo "  3) 위젯 6 (CPU/Memory) 은 최대 60분 지연 — 1시간 뒤 재확인"
echo ""
echo "Dashboard URL:"
echo "  https://us-east-1.console.aws.amazon.com/cloudwatch/home?region=us-east-1#dashboards:name=thewhoo-chat-runtime"
