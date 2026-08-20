#!/usr/bin/env bash
# Python 환경 셋업 (1회 실행, idempotent).
#
# SageMaker Studio Code Editor 에서는 Python 3.11 이 기본 설치되어 있어
# 즉시 venv 로 넘어갑니다. CloudShell (기본 Python 3.9) 에서는 pyenv 로
# 3.11 을 먼저 설치합니다. 환경을 자동 감지합니다.
#
# 재실행해도 안전합니다.
set -euo pipefail

PY_VERSION="3.11.9"
HERE="$(cd "$(dirname "$0")/.." && pwd)"

START=$(date +%s)
elapsed() {
  local now=$(date +%s)
  local s=$((now - START))
  printf "[경과 %dm%02ds]\n" $((s/60)) $((s%60))
}

echo ""
echo "==================================================================="
echo " Python 환경 셋업"
echo "==================================================================="
echo ""

# ────────────────────────────────────────────────────────────────
# 환경 감지 — 쓸만한 Python (3.10+) 이 있나?
# ────────────────────────────────────────────────────────────────
PY_BIN=""
for candidate in python3.12 python3.11 python3.10 python3; do
  if command -v "$candidate" > /dev/null 2>&1; then
    VERSION=$("$candidate" -c 'import sys; print(f"{sys.version_info[0]}.{sys.version_info[1]}")')
    MAJOR=${VERSION%.*}
    MINOR=${VERSION#*.}
    if [ "${MAJOR}" -eq 3 ] && [ "${MINOR}" -ge 10 ]; then
      PY_BIN="$candidate"
      echo ">> 시스템에 ${candidate} (${VERSION}) 을 찾았습니다."
      break
    fi
  fi
done

# ────────────────────────────────────────────────────────────────
# Python 3.10+ 이 없으면 pyenv 로 설치 (CloudShell 케이스)
# ────────────────────────────────────────────────────────────────
if [ -z "${PY_BIN}" ]; then
  echo ">> Python 3.10+ 이 없어 pyenv 로 3.11 을 설치합니다 (~5분)."
  echo ""

  # 빌드 의존성 (Amazon Linux 기준)
  echo "   [1/3] 빌드 의존성 설치"
  elapsed
  if command -v dnf > /dev/null 2>&1; then
    sudo dnf install -y gcc make patch \
      zlib-devel bzip2-devel readline-devel \
      sqlite-devel openssl-devel libffi-devel xz-devel > /dev/null
  elif command -v apt-get > /dev/null 2>&1; then
    sudo apt-get install -y make build-essential libssl-dev zlib1g-dev \
      libbz2-dev libreadline-dev libsqlite3-dev libffi-dev liblzma-dev > /dev/null
  fi
  echo "       ✓ 완료"

  # pyenv
  echo "   [2/3] pyenv 설치"
  elapsed
  if [ -d "$HOME/.pyenv" ]; then
    echo "       ✓ 이미 설치됨"
  else
    curl -sS https://pyenv.run | bash > /dev/null
    echo "       ✓ 설치 완료"
  fi

  export PYENV_ROOT="$HOME/.pyenv"
  export PATH="$PYENV_ROOT/bin:$PATH"
  eval "$(pyenv init -)"

  # bashrc 자동 등록
  BASHRC_BLOCK='
# --- pyenv (thewhoo-agentcore-workshop) ---
export PYENV_ROOT="$HOME/.pyenv"
[[ -d $PYENV_ROOT/bin ]] && export PATH="$PYENV_ROOT/bin:$PATH"
eval "$(pyenv init - 2>/dev/null || true)"
# --- end pyenv ---'
  if ! grep -q "# --- pyenv (thewhoo-agentcore-workshop) ---" "$HOME/.bashrc" 2>/dev/null; then
    echo "$BASHRC_BLOCK" >> "$HOME/.bashrc"
    echo "       ✓ ~/.bashrc 에 pyenv 자동 로드 추가"
  fi

  # Python 3.11 빌드
  echo "   [3/3] Python ${PY_VERSION} 빌드 (3~5분)"
  elapsed
  if pyenv versions --bare | grep -q "^${PY_VERSION}\$"; then
    echo "       ✓ 이미 설치됨"
  else
    pyenv install "${PY_VERSION}"
  fi
  pyenv shell "${PY_VERSION}"
  PY_BIN="python"
  echo ""
fi

# ────────────────────────────────────────────────────────────────
# venv + requirements
# ────────────────────────────────────────────────────────────────
echo ">> venv 생성 + 의존성 설치"
elapsed
cd "${HERE}"

if [ -d ".venv" ]; then
  echo "   ✓ .venv 이미 존재 (재사용)"
else
  "${PY_BIN}" -m venv .venv
  echo "   ✓ .venv 생성"
fi

# shellcheck source=/dev/null
source .venv/bin/activate
# --no-cache-dir: pip cache 공간 절약 (CloudShell 1GB 한계 대응)
pip install --no-cache-dir --upgrade --quiet pip
pip install --no-cache-dir --quiet -r requirements.txt
rm -rf "$HOME/.cache/pip" 2>/dev/null
echo "   ✓ requirements.txt 설치 완료"
echo ""

# ────────────────────────────────────────────────────────────────
# 배포 prerequisite — zip / uv
#
# uv 는 새 AgentCore CLI(@aws/agentcore) 의 **필수** 전제조건입니다.
#   - aws/agentcore-cli README 요구사항: "uv — for Python agents"
#   - CLI 내부 사전점검이 uv 를 severity=error 로 검사
#     ("'uv' is required for Python projects")
#   - agentcore create 가 내부적으로 `uv sync` 로 의존성을 설치
#
# 주의: 공식 devguide 의 Prerequisites 목록에는 uv 가 **빠져 있습니다**
# (Node/Python/CDK/권한/모델액세스만 나열). 문서만 따라가면 놓칩니다.
#
# uv 가 없으면 agentcore create 가 실패하지 않고 경고만 냅니다 —
#   "Warning: uv not found — run 'uv sync' manually in app/<name>"
# 그리고 배포 단계에서 의존성 누락으로 터집니다. 그래서 여기서 확실히 깝니다.
# ────────────────────────────────────────────────────────────────
echo ">> 배포 의존 도구 (zip, uv) 확인"

if ! command -v zip > /dev/null 2>&1; then
  echo "   zip 설치 시도..."
  if command -v dnf > /dev/null 2>&1; then
    sudo dnf install -y -q zip > /dev/null 2>&1 && echo "   ✓ zip 설치 (dnf)" \
      || echo "   ⚠ zip 설치 실패 — 수동 설치 필요: sudo dnf install -y zip"
  elif command -v apt-get > /dev/null 2>&1; then
    sudo apt-get update -qq > /dev/null 2>&1 || true
    sudo apt-get install -y -qq zip > /dev/null 2>&1 && echo "   ✓ zip 설치 (apt-get)" \
      || echo "   ⚠ zip 설치 실패 — 수동 설치 필요: sudo apt-get install -y zip"
  else
    echo "   ⚠ apt-get/dnf 둘 다 없습니다. 수동으로 zip 을 PATH 에 두세요."
  fi
else
  echo "   ✓ zip 존재"
fi

if ! command -v uv > /dev/null 2>&1; then
  echo "   uv 설치 시도..."
  curl -LsSf https://astral.sh/uv/install.sh | sh > /dev/null 2>&1 || true
  # uv 기본 설치 경로 (설치 스크립트가 ~/.bashrc 도 갱신하므로 새 터미널에도 반영됨)
  export PATH="$HOME/.local/bin:$PATH"
  if command -v uv > /dev/null 2>&1; then
    echo "   ✓ uv 설치 ($(uv --version 2>/dev/null || which uv))"
  else
    echo ""
    echo "   ✗ uv 설치 실패 — Day 2 의 agentcore CLI 가 동작하지 않습니다."
    echo "     uv 는 @aws/agentcore 의 필수 전제조건입니다 (Python 에이전트)."
    echo "     없으면 'agentcore create' 가 경고만 내고 넘어간 뒤 배포에서 실패합니다."
    echo ""
    echo "     수동 설치:"
    echo "       curl -LsSf https://astral.sh/uv/install.sh | sh"
    echo "       export PATH=\"\$HOME/.local/bin:\$PATH\""
    echo ""
    UV_MISSING=1
  fi
else
  echo "   ✓ uv 존재 ($(uv --version 2>/dev/null || which uv))"
fi
echo ""

# ────────────────────────────────────────────────────────────────
# AWS CLI 지원 서비스 확인
# Lab 3 / 6 / 7 · env-recovery · cleanup-all 은 `aws bedrock-agentcore-control`
# 과 `aws s3vectors` 를 직접 호출합니다. CLI 가 오래되면 이 서비스들이 아예
# 'Invalid choice' 로 거부됩니다 (자격증명·권한 문제가 아니라 CLI 버전 문제).
# onestop.sh 는 boto3 를 쓰므로 Pre-Lab 은 영향 없습니다.
# ────────────────────────────────────────────────────────────────
echo ">> AWS CLI 지원 서비스 확인"
CLI_VER=$(aws --version 2>&1 | head -1)
echo "   ${CLI_VER}"

CLI_MISSING=""
for svc in bedrock-agentcore-control bedrock-agentcore s3vectors; do
  aws "${svc}" help > /dev/null 2>&1 || CLI_MISSING="${CLI_MISSING} ${svc}"
done

if [ -n "${CLI_MISSING}" ]; then
  echo "   ⚠ 이 CLI 가 모르는 서비스:${CLI_MISSING}"
  echo "     → Lab 3 / 6 / 7, env-recovery.md, cleanup-all.sh 의 aws 명령이 실패합니다."
  echo "     → CLI v2 를 최신으로 올리세요:"
  echo "         curl -s 'https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip' -o /tmp/awscliv2.zip"
  echo "         unzip -q -o /tmp/awscliv2.zip -d /tmp && sudo /tmp/aws/install --update"
  echo "     (Workshop Studio Code Editor / CloudShell 은 보통 최신이라 이 경고가 안 뜹니다.)"
else
  echo "   ✓ bedrock-agentcore-control / bedrock-agentcore / s3vectors 모두 지원"
fi
echo ""

# ────────────────────────────────────────────────────────────────
# Node.js 확인 (Day 2 Lab 5 의 AgentCore CLI 가 npm 패키지)
# ────────────────────────────────────────────────────────────────
echo ">> Node.js 확인 (Day 2 배포용)"
if command -v node > /dev/null 2>&1; then
  NODE_VER=$(node --version 2>/dev/null)
  NODE_MAJOR=$(echo "${NODE_VER}" | sed 's/^v//' | cut -d. -f1)
  if [ "${NODE_MAJOR:-0}" -ge 20 ] 2>/dev/null; then
    echo "   ✓ ${NODE_VER} (Day 2 의 agentcore CLI 사용 가능)"
  else
    echo "   ⚠ ${NODE_VER} — Day 2 Lab 5 는 Node 20 이상이 필요합니다."
    echo "     Day 1 만 진행하면 문제 없습니다."
  fi
else
  echo "   ⚠ node 없음 — Day 2 Lab 5 (agentcore CLI) 에서 필요합니다."
  echo "     Day 1 만 진행하면 문제 없습니다."
fi
echo ""

# ────────────────────────────────────────────────────────────────
# 완료
# ────────────────────────────────────────────────────────────────
FINISH=$(date +%s)
TOTAL=$((FINISH - START))

echo "==================================================================="
printf " ✓ Python 환경 준비 완료 (총 %dm%02ds)\n" $((TOTAL/60)) $((TOTAL%60))
echo "==================================================================="
echo ""
echo "세션 재접속 시에는 아래 한 줄만 실행하세요:"
echo ""
echo "  cd ${HERE/#$HOME/~} && source .venv/bin/activate"
echo ""
# 호출자가 다음 단계 안내를 직접 출력하도록, 여기서는 일반 메시지만 남깁니다.
# (Day 1 Pre-Lab 직후 라면 Lab 0 또는 Lab 1 로, Day 2 패스트트랙 안에서면
#  Memory/Gateway 생성으로 이어지는 식으로 컨텍스트가 다릅니다.)
if [[ "${UV_MISSING:-0}" == "1" ]]; then
  echo "⚠️  uv 가 없습니다 — Day 1 은 진행 가능하지만 Day 2 (agentcore CLI) 전에"
  echo "    반드시 설치해야 합니다. 위의 수동 설치 안내를 참고하세요."
  echo ""
fi

echo "Python 환경 준비가 끝났습니다."
echo ""
echo "다음 단계는 워크샵 진행 단계에 따라 다릅니다:"
echo "  · Day 1 Pre-Lab 직후      → Lab 0 / Lab 1 로 이동"
echo "  · Day 2 패스트트랙 사용   → setup-day2-codeeditor.sh 가 자동으로 이어집니다"
echo "  · 인프라가 아직 없다면    → CloudShell 에서 ./scripts/onestop.sh <참가자 ID>"
echo ""
