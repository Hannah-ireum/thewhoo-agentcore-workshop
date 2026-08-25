#!/usr/bin/env bash
# Lab 5 전용 사전점검 — `agentcore dev` / `agentcore deploy` 전에 실행.
#
# 왜 필요한가
#   `agentcore create` 는 codeLocation 을 자기 스캐폴딩(app/<name>/)으로 둡니다.
#   워크샵은 기존 src/ 를 배포하므로 set-agentcore-config.py 로 바꿔야 하는데,
#   이 단계를 건너뛰면 CLI 가 **없는 디렉터리**를 대상으로 동작해 원인을 알 수
#   없는 오류를 냅니다 (실환경에서 확인):
#     agentcore dev    → ❌ Failed to create venv: unknown error
#     agentcore deploy → CDK synth failed: Subprocess exited with error 1
#   두 오류의 원인이 같은데 메시지가 전혀 알려주지 않아 디버깅이 매우 어렵습니다.
#
# 그래서 실행 전에 이 스크립트로 "설정이 실제 파일 시스템과 맞는지" 를 봅니다.
#
# Usage:
#   ./scripts/check-agentcore-config.sh
#   → 통과하면 exit 0, 문제가 있으면 원인과 조치를 출력하고 exit 1

set -uo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
CFG="agentcore/agentcore.json"
FAIL=0

say()  { printf '%s\n' "$*"; }
ok()   { printf '  ✓ %s\n' "$*"; }
bad()  { printf '  ✗ %s\n' "$*"; FAIL=1; }
hint() { printf '      → %s\n' "$*"; }

say ""
say "==================================================================="
say " Lab 5 사전점검 — agentcore dev / deploy 전에 확인"
say "==================================================================="

# ── 1) 프로젝트가 만들어졌나 ─────────────────────────────────────
if [ ! -f "${CFG}" ]; then
  bad "${CFG} 가 없습니다 (프로젝트 미생성)"
  hint "agentcore create --name ThewhooChat --framework Strands \\"
  hint "  --protocol HTTP --model-provider Bedrock --memory none --build CodeZip"
  hint "mv ThewhooChat/agentcore ./ && rm -rf ThewhooChat"
  say ""
  exit 1
fi
ok "${CFG} 존재"

# ── 2) codeLocation 이 실제 존재하는 디렉터리를 가리키나 (핵심) ──
CODE_LOC=$(python3 -c "
import json
d=json.load(open('${CFG}'))
r=(d.get('runtimes') or [{}])[0]
print(r.get('codeLocation',''))
" 2>/dev/null)

ENTRY=$(python3 -c "
import json
d=json.load(open('${CFG}'))
r=(d.get('runtimes') or [{}])[0]
print(r.get('entrypoint',''))
" 2>/dev/null)

if [ -z "${CODE_LOC}" ]; then
  bad "codeLocation 이 비어 있습니다"
elif [ ! -d "${CODE_LOC}" ]; then
  bad "codeLocation='${CODE_LOC}' — 이 디렉터리가 없습니다"
  hint "agentcore create 의 기본값(app/<이름>/)이 그대로 남은 상태입니다."
  hint "이 상태로 dev 를 돌리면 'Failed to create venv: unknown error',"
  hint "deploy 를 돌리면 'CDK synth failed' 가 납니다."
  hint ""
  hint "해결 — 2단계를 실행하세요:"
  hint "  eval \"\$(./scripts/print-env.sh w001)\""
  hint "  python3 scripts/set-agentcore-config.py"
elif [ "${CODE_LOC%/}" != "src" ]; then
  bad "codeLocation='${CODE_LOC}' — 워크샵은 'src/' 여야 합니다"
  hint "python3 scripts/set-agentcore-config.py 를 실행하세요"
else
  ok "codeLocation='${CODE_LOC}' (디렉터리 존재)"
fi

# ── 3) entrypoint 파일이 codeLocation 안에 있나 ──────────────────
if [ -n "${CODE_LOC}" ] && [ -d "${CODE_LOC}" ]; then
  if [ -z "${ENTRY}" ]; then
    bad "entrypoint 가 비어 있습니다"
  elif [ ! -f "${CODE_LOC%/}/${ENTRY}" ]; then
    bad "entrypoint='${ENTRY}' 를 ${CODE_LOC} 에서 찾을 수 없습니다"
    hint "python3 scripts/set-agentcore-config.py 를 실행하세요"
  else
    ok "entrypoint='${ENTRY}' (${CODE_LOC%/}/${ENTRY} 존재)"
  fi

  # dev 가 uv 로 venv 를 만들 때 필요
  if [ -f "${CODE_LOC%/}/pyproject.toml" ]; then
    ok "${CODE_LOC%/}/pyproject.toml 존재 (배포 의존성 선언)"
  else
    bad "${CODE_LOC%/}/pyproject.toml 이 없습니다"
    hint "새 CLI 는 requirements.txt 를 읽지 않습니다. git pull 로 받으세요."
  fi
fi

# ── 4) envVars 3종이 채워졌나 ────────────────────────────────────
ENV_MISSING=$(python3 -c "
import json
d=json.load(open('${CFG}'))
r=(d.get('runtimes') or [{}])[0]
got={e.get('name'): e.get('value') for e in (r.get('envVars') or [])}
need=['KB_ID','AGENTCORE_MEMORY_ID','AGENTCORE_GATEWAY_URL']
print(' '.join(n for n in need if not got.get(n)))
" 2>/dev/null)

if [ -n "${ENV_MISSING}" ]; then
  bad "envVars 누락/빈값: ${ENV_MISSING}"
  hint "eval \"\$(./scripts/print-env.sh w001)\" 후"
  hint "python3 scripts/set-agentcore-config.py 를 다시 실행하세요"
else
  ok "envVars 3종 설정됨 (KB / Memory / Gateway)"
fi

# ── 5) executionRoleArn ─────────────────────────────────────────
ROLE=$(python3 -c "
import json
d=json.load(open('${CFG}'))
print((d.get('runtimes') or [{}])[0].get('executionRoleArn',''))
" 2>/dev/null)

if [ -z "${ROLE}" ]; then
  bad "executionRoleArn 이 비어 있습니다"
  hint "CDK 자동 생성 role 은 Memory·KB 권한이 없어 첫 invoke 가 500 이 됩니다."
  hint "python3 scripts/set-agentcore-config.py 가 자동으로 넣어 줍니다."
else
  ok "executionRoleArn=$(basename "${ROLE}")"
fi

# ── 6) 실행 도구 ────────────────────────────────────────────────
command -v node >/dev/null 2>&1 && ok "node $(node --version)" || bad "node 없음"
if command -v uv >/dev/null 2>&1; then
  ok "uv $(uv --version 2>/dev/null | awk '{print $2}') ($(command -v uv))"
else
  bad "uv 를 PATH 에서 찾을 수 없습니다"
  hint "agentcore dev 가 'Failed to create venv' 로 실패합니다."
  hint "export PATH=\"\$HOME/.local/bin:\$PATH\"  (또는 setup-python.sh 재실행)"
fi
command -v agentcore >/dev/null 2>&1 \
  && ok "agentcore $(agentcore --version 2>/dev/null | head -1)" \
  || bad "agentcore 없음 — npm install -g @aws/agentcore"

# ── 7) 자격증명 ─────────────────────────────────────────────────
if ACCT=$(aws sts get-caller-identity --query Account --output text 2>/dev/null); then
  ok "AWS 자격증명 정상 (account ${ACCT})"
else
  bad "AWS 자격증명 실패"
  hint "Code Editor 터미널을 닫고 새로 열어 자격증명을 갱신하세요"
fi

# ── 8) CDK bootstrap 상태 ───────────────────────────────────────
# deploy 는 CDK 로 수행되므로 리전에 CDKToolkit 스택이 있어야 합니다.
# 없을 때 `agentcore deploy -y` 의 자동 bootstrap 은 **새 계정에서 실패**하고
# (CloudFormationStack object does not hold a stack), 그 실패가 스택을
# ROLLBACK_COMPLETE 껍데기로 남깁니다. 이 상태는 업데이트가 불가능해서
# 이후 모든 deploy 가 같은 오류로 막힙니다 — 그래서 미리 잡습니다.
REGION="${AWS_REGION:-us-east-1}"
BS=$(aws cloudformation describe-stacks --stack-name CDKToolkit \
      --region "${REGION}" --query 'Stacks[0].StackStatus' \
      --output text 2>/dev/null)

case "${BS}" in
  CREATE_COMPLETE|UPDATE_COMPLETE|IMPORT_COMPLETE)
    ok "CDK bootstrap 완료 (CDKToolkit=${BS})"
    ;;
  "")
    bad "CDK bootstrap 이 안 돼 있습니다 (${REGION} 에 CDKToolkit 스택 없음)"
    hint "이 상태로 agentcore deploy 를 돌리면 원인을 알 수 없는 오류가 납니다:"
    hint "  CDK bootstrap failed: CloudFormationStack object does not hold a stack"
    hint "게다가 실패 흔적이 ROLLBACK_COMPLETE 로 남아 이후 배포까지 막습니다."
    hint ""
    hint "해결 — 2.5단계를 실행하세요 (계정당 1회, 2~3분):"
    hint "  ACC=\$(aws sts get-caller-identity --query Account --output text)"
    hint "  (cd agentcore/cdk && ./node_modules/.bin/cdk bootstrap aws://\$ACC/${REGION})"
    hint "  ※ npx cdk 는 출력 없이 조용히 실패합니다 — .bin/cdk 를 직접 쓰세요"
    ;;
  ROLLBACK_COMPLETE|ROLLBACK_FAILED|DELETE_FAILED|*ROLLBACK_FAILED|CREATE_FAILED)
    bad "CDKToolkit 스택이 '${BS}' 로 고착됐습니다 (배포 불가 상태)"
    hint "이 상태의 스택은 업데이트가 안 되고 삭제만 됩니다."
    hint "지우고 다시 bootstrap 하세요:"
    hint "  aws cloudformation delete-stack --stack-name CDKToolkit --region ${REGION}"
    hint "  aws cloudformation wait stack-delete-complete --stack-name CDKToolkit --region ${REGION}"
    hint "  ACC=\$(aws sts get-caller-identity --query Account --output text)"
    hint "  (cd agentcore/cdk && ./node_modules/.bin/cdk bootstrap aws://\$ACC/${REGION})"
    hint "  ※ npx cdk 는 출력 없이 조용히 실패합니다 — .bin/cdk 를 직접 쓰세요"
    hint ""
    hint "삭제가 권한 부족으로 실패하면 (ecr:DeleteRepository / DeleteParameter),"
    hint "CloudShell 에서 ./scripts/grant-sagemaker-permissions.sh 를 실행하세요."
    ;;
  *IN_PROGRESS)
    bad "CDKToolkit 이 '${BS}' — 작업이 진행 중입니다"
    hint "끝날 때까지 기다린 뒤 다시 실행하세요 (보통 2~3분)"
    ;;
  *)
    bad "CDKToolkit 상태가 '${BS}' 입니다 (예상 밖)"
    hint "aws cloudformation describe-stack-events --stack-name CDKToolkit \\"
    hint "  --region ${REGION} --max-items 20 로 원인을 확인하세요"
    ;;
esac

say ""
say "==================================================================="
if [ "${FAIL}" -eq 0 ]; then
  say " ✓ 사전점검 통과 — agentcore dev / deploy 를 진행하세요"
  say "==================================================================="
  say ""
  exit 0
fi
say " ✗ 위 항목을 해결한 뒤 다시 실행하세요"
say "==================================================================="
say ""
exit 1
