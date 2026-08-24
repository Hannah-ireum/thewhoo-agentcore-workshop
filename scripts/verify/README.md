# 문서 검증기 — 4축 자동 대조

워크샵 문서가 **공식 문서·실제 CLI·라이브 AWS·저장소 코드와 어긋나는지** 기계적으로 잡습니다.
문서를 고친 뒤 이 4개를 돌려 0건이면 회귀가 없는 상태입니다.

## 사용법

```bash
cd <repo-root>
export PATH="$PWD/.venv/bin:$PATH"

# 사전 준비 — CLI 트리 캐시 (agentcore --help 한 호출이 5초대라 캐시 필수)
{ agentcore --help; for t in add import run traces remove evals; do
    echo "###$t"; agentcore $t --help; done; } > /tmp/cli_sub.txt 2>&1

# 라이브 AWS 캐시
python - <<'PY'
import boto3,json
cw=boto3.client("cloudwatch",region_name="us-east-1")
ac=boto3.client("bedrock-agentcore-control",region_name="us-east-1")
br=boto3.client("bedrock",region_name="us-east-1")
ev=[];tok=None
while True:
    r=ac.list_evaluators(**({"nextToken":tok} if tok else {}))
    ev+=[e["evaluatorId"] for e in r["evaluators"]]; tok=r.get("nextToken")
    if not tok: break
json.dump({"metrics":sorted({m["MetricName"] for m in cw.list_metrics(Namespace="AWS/Bedrock-AgentCore")["Metrics"]}),
 "evaluators":sorted(ev),
 "models":sorted({m["modelId"] for m in br.list_foundation_models()["modelSummaries"]})},
 open("/tmp/live_aws.json","w"))
PY

python scripts/verify/check-claims.py       # 1축
python scripts/verify/check-external.py     # 2축
bash   scripts/verify/check-commands.sh     # 3축
python scripts/verify/check-consistency.py  # 4축
```

## 각 축이 잡는 것

| 축 | 파일 | 검사 대상 |
|---|---|---|
| 1 | `check-claims.py` | `agentcore` 명령·서브명령, `gen_ai.*` attribute(Strands 소스 대조), CloudWatch metric, evaluator, 모델 ID, 저장소 파일 존재 |
| 2 | `check-external.py` | 공식 quota 수치, AWS URL(리다이렉트 추적 포함), 문서 인용 코드 ↔ 실제 소스, 환경변수 ↔ `print-env.sh`, 골든셋 SDK 로더 |
| 3 | `check-commands.sh` | 문서의 읽기전용 명령을 **실제 실행** (JMESPath 문법 오류까지 잡음) |
| 4 | `check-consistency.py` | 문서 간 수치 모순, 골든셋 도구명 ↔ 코드 `@tool`, 스크립트 옵션 실존, `requirements.txt` ↔ `src/pyproject.toml` 범위 일치 |

## 검출기 자체를 신뢰하려면

**의도적 오류를 심어 탐지되는지 먼저 확인하세요.** 이 검증기들은 그 과정에서
두 번 결함이 드러났습니다:

- 부모 명령만 맞으면 통과시켜 `agentcore traces listing` 같은 **서브명령 오타를 놓쳤음**
  → 캐시에 부모별 서브명령을 넣고 두 번째 토큰까지 검증하도록 수정
- AWS 문서는 **없는 페이지를 index 로 리다이렉트하며 200** 을 돌려줌
  → 최종 URL 이 원본과 다르면 실패로 처리하도록 수정

즉 "0건"은 검출기의 탐지 범위 안에서만 유효합니다.

## 5축 — 보안 게이트 (`check-secrets.py`)

공개 배포 전에 **민감정보가 있으면 exit 1 로 배포를 막습니다.**

```bash
python3 scripts/verify/check-secrets.py <배포 스테이징 디렉터리>
```

탐지 대상: AWS Access Key / Secret / Session Token, Private Key, JWT,
AWS 계정 ID(12자리), 로컬 홈 경로(`/Users/…`, `/home/…`),
Cognito User Pool ID, 구 저장소명(`thewhoo-agentcore-workshop`), 이메일.

문서용 예시값(`123456789012`, `user@example.com`, `/home/sagemaker-user` 등)은
스크립트 안 화이트리스트로 통과시킵니다. **실제 값은 절대 화이트리스트에
넣지 마세요.**

> **왜 별도 게이트인가** — 이전에는 배포 스크립트가 `grep` 으로 경고만 내고
> 진행을 막지 않아서 로컬 절대경로가 공개 리포에 올라간 적이 있습니다.
> 이제 `scripts/publish-public.sh` 가 이 스캔을 통과하지 못하면 **push 자체를
> 하지 않습니다.**

의도적 주입으로 탐지력을 확인했습니다 — 실제 키·계정ID·경로·Pool ID·JWT
7종을 전부 잡고, 예시값 3종은 통과했습니다.
