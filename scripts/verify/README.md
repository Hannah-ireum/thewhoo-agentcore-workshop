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

## 6축 — 소스 자산 (`check-assets.py`)

문서가 아니라 **코드·데이터 자산**을 검사합니다.

| 검사 | 내용 |
|---|---|
| Lambda ↔ openapi | 핸들러가 읽는 `params.get()` 키가 입력 스키마에 선언돼 있나 |
| 골든셋 사실성 | assertion 이 주장하는 제품·성분 고유명사가 상품 데이터에 실재하나 |
| CFN ↔ 참조 | 문서·스크립트가 참조하는 IAM role 을 CFN 이 실제로 만드나 |
| 문서 흐름 | Lab 문서 상단에 전제 조건이 명시돼 있나 |
| 스크립트 참조 | 스크립트가 호출하는 다른 스크립트가 존재하나 |

> **한국어 토큰 자동 판정은 포기했습니다.** 골든셋 assertion 의 고유명사를
> 형태소 분석 없이 판정하려 3가지 방식(어휘 대조 / 동적 vocab / 유사도)을
> 시도했고 전부 조사·활용어를 오탐했습니다. 그래서 **사실 주장에 쓰이는
> 고유명사만 `FACT_TERMS` 화이트리스트로 고정**하고, `X 성분`·`X 크림` 같은
> 문맥 패턴으로 목록 밖 신규 용어가 등장하면 경고합니다.
> 골든셋에 새 성분·제품을 넣을 때는 `FACT_TERMS` 도 갱신하세요.

## 전체 실행 (6축)

```bash
export PATH="$PWD/.venv/bin:$PATH"
python scripts/verify/check-claims.py
python scripts/verify/check-external.py
bash   scripts/verify/check-commands.sh
python scripts/verify/check-consistency.py
python scripts/verify/check-assets.py
# 보안 게이트는 배포 스테이징을 대상으로 (publish-public.sh 가 자동 실행)
python scripts/verify/check-secrets.py <스테이징 디렉터리>
```
