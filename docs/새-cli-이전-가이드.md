# 새 AgentCore CLI 로 이전하기

*— 워크샵 Day 2 는 이미 새 AgentCore CLI 를 씁니다. 이 문서는 구 starter-toolkit 으로 만든 기존 프로젝트를 옮길 때 보는 참고 자료입니다.*

## 왜 이 문서가 있나

구 Python starter-toolkit 으로 `agentcore configure` 를 실행하면 이 배너가 뜹니다.

```
⚠️ Recommendation: The Starter Toolkit CLI is no longer supported.
   Please use the AgentCore CLI (@aws/agentcore) to create, develop, and deploy
   agents on Amazon Bedrock AgentCore.
   New Bedrock AgentCore features are only accessible in the AgentCore CLI.
```

이건 배너에 그치지 않습니다. **AWS 가 패키지 메타데이터·공식 문서 수준에서 legacy 로 표기**했습니다:

| 출처 | 표기 |
|---|---|
| GitHub `aws/bedrock-agentcore-starter-toolkit` 저장소 설명 | "Python CLI toolkit for Amazon Bedrock AgentCore **(legacy)**. For new projects, use the AgentCore CLI" |
| 같은 저장소 README · PyPI 페이지 | "The Starter Toolkit CLI is **no longer supported**. Please use the AgentCore CLI" |
| Strands Agents 공식 배포 문서 | "The AgentCore CLI **replaces** the previously available `bedrock-agentcore-starter-toolkit`" |
| `aws/agentcore-cli` README | 구 CLI 가 남아 있으면 **명령 이름이 충돌**하므로 uninstall 하라고 안내 |

> devguide 의 release notes 페이지에는 지원 종료 항목이 **없습니다** — 공지 경로가 저장소·PyPI 쪽입니다. 근거를 인용할 때는 위 표의 출처를 쓰세요.

starter-toolkit 자체는 아직 릴리스가 나오고 있습니다 (PyPI 0.3.12, 2026-08-19). 즉 **당장 멈추지는 않지만 신규 기능이 들어오지 않는** 상태입니다.

두 CLI 는 **같은 AgentCore 서비스**를 다룹니다. 워크샵에서 배운 개념(Runtime · Memory · Gateway · Observability · Evaluations)은 그대로 유효하고, **명령과 프로젝트 구조만 달라집니다.**

### ⚠️ 두 CLI 를 동시에 깔면 안 되는 이유

둘 다 `agentcore` 라는 **같은 명령 이름**을 씁니다. 새 CLI 는 설치 후 구 CLI 가 감지되면 경고를 냅니다. 원래 설치 방법에 맞춰 지우세요:

```bash
pip uninstall bedrock-agentcore-starter-toolkit       # pip 로 설치했다면
pipx uninstall bedrock-agentcore-starter-toolkit      # pipx
uv tool uninstall bedrock-agentcore-starter-toolkit   # uv
```

## 두 CLI 비교

| | Python starter-toolkit (구 워크샵·현재 미사용) | AgentCore CLI (이 워크샵 Day 2) |
|---|---|---|
| 패키지 | `bedrock-agentcore-starter-toolkit` (pip, legacy) | `@aws/agentcore` (npm) |
| 설정 파일 | `.bedrock_agentcore.yaml` | `agentcore/agentcore.json` |
| 배포 방식 | 자체 패키징 → Runtime API 직접 호출 | **AWS CDK** → CloudFormation |
| 추가 전제 | 없음 (Python 만) | **Node.js 20+ · `uv` · AWS CDK** |
| 리소스 범위 | Runtime 위주 | Runtime · Memory · KB · Gateway · Evaluator · Dataset 등 **선언적 통합 관리** |
| 신규 기능 | 반영 안 됨 | 여기만 |

> **핵심 차이** — starter-toolkit 은 "Runtime 배포 도구" 였고, 새 CLI 는 "**프로젝트 전체를 코드로 선언**하는 IaC 도구" 입니다. 그래서 CDK 가 들어옵니다.

## 전제조건

공식 문서 [Get started with the AgentCore CLI](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-get-started-cli.html) 의 Prerequisites:

- **Node.js 20+** — CLI 가 npm 패키지 (`package.json` 의 `engines.node: ">=20"`)
- **Python 3.10+** — 생성되는 에이전트 코드가 Python
- **AWS CDK** — 배포에 사용
- **IAM 권한** — 정확한 정책 JSON 은 [IAM Permissions for AgentCore Runtime → Use the AgentCore CLI](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-permissions.html#runtime-permissions-cli) 참고
- **모델 액세스** — Bedrock 을 provider 로 쓸 경우 Claude 활성화

### ⚠️ 공식 Prerequisites 에 빠진 항목 — `uv`

위 devguide 목록에는 **`uv` 가 없습니다.** 그런데 실제로는 필수입니다:

| 근거 | 내용 |
|---|---|
| `aws/agentcore-cli` README 요구사항 | "**uv** — for Python agents" |
| CLI 내부 사전점검 | `uv` 를 severity **`error`** 로 검사 — `'uv' is required for Python projects` |
| `agentcore create` 동작 | 내부적으로 `uv sync` 로 Python 의존성 설치 |
| `--skip-install` 사용 시 CLI 안내 | "Run 'npm install' in agentcore/cdk/ and **'uv sync' in your agent directory**" |

`uv` 가 없으면 `agentcore create` 가 **즉시 실패**합니다 (실측 — exit code 1, 파일 생성 없음):

```
'uv' is required for Python projects. Install from https://github.com/astral-sh/uv#installation
```

메시지가 명확하고 중간 상태를 남기지 않는다는 점은 다행입니다. 다만 **공식 devguide Prerequisites 만 보고 준비하면 이 지점에서 막힙니다.** 먼저 확인하세요:

```bash
node --version                                    # 20 이상
uv --version                                      # 없으면 아래로 설치
curl -LsSf https://astral.sh/uv/install.sh | sh   # ~/.bashrc 도 함께 갱신됨
```

> **워크샵 환경** — `setup-python.sh` 가 `zip` 과 `uv` 를 자동 설치하므로 Pre-Lab 을 마쳤다면 준비돼 있습니다. Node.js 는 Code Editor 에 기본 포함(검증 시 v20.19.6)입니다.

`cdk bootstrap` 은 공식 문서가 전제조건으로 적고 트러블슈팅에도 나오지만, 워크샵 환경 실측에서는 첫 `agentcore deploy` 가 자동 처리했습니다. 실패하면 수동으로:

```bash
npm install -g aws-cdk
cdk bootstrap aws://<ACCOUNT_ID>/us-east-1
```

## 설치

```bash
npm install -g @aws/agentcore
agentcore --help
```

> **주의** — 이러면 `agentcore` 명령이 **두 개** 생깁니다(pip 것과 npm 것). PATH 순서에 따라 다른 게 실행되니, 한 셸에서 둘을 섞어 쓰지 마세요. `which agentcore` 로 확인하세요.

## 명령 대응표

| 하려는 일 | starter-toolkit (구 방식) | AgentCore CLI (현재) |
|---|---|---|
| 프로젝트 생성 | (없음 — 기존 코드에 붙임) | `agentcore create` |
| 설정 | `agentcore configure --entrypoint ... --name ...` | `agentcore/agentcore.json` 편집 또는 `agentcore add ...` |
| 로컬 실행 | `agentcore invoke --dev` | `agentcore dev` |
| 배포 | `agentcore deploy --env K=V` | `agentcore deploy` (별칭 `dp`) |
| 배포 전 확인 | (없음) | `agentcore deploy --dry-run` / `--diff` |
| 호출 | `agentcore invoke '{"message":"..."}'` | `agentcore invoke "..."` |
| 상태 | `agentcore status` | `agentcore status` |
| 로그 | `aws logs tail ...` | `agentcore logs` |
| trace | CloudWatch 콘솔 | `agentcore traces` |
| 평가 | `agentcore eval run --session-id ...` | `agentcore run eval --session-id ...` |
| 설정 검증 | (없음) | `agentcore validate` |
| 정리 | `agentcore destroy` | `agentcore remove all` → `agentcore deploy` |

> **버전 주의** — devguide 의 [CLI reference](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/agentcore-cli-reference.html) 는 페이지 안에 *"Auto-generated from `@aws/agentcore` v0.24.2"* 라고 적혀 있습니다. npm 최신은 **0.27.1** 이라 문서보다 앞서 있고, 실제로 문서에 없는 명령이 여럿 있습니다 (`exec`, `dataset`, `batch-evaluations`, `promote`, `stop`, `view`, `export`, `feedback`, `telemetry`, `config`). Get started 페이지의 명령 목록도 구버전 기준입니다.
>
> **가장 정확한 출처는 설치된 CLI 자신입니다.** 막히면 이렇게 확인하세요:
>
> ```bash
> agentcore --version
> agentcore --help                # 전체 명령
> agentcore add --help            # 하위 명령
> agentcore run eval --help       # 플래그
> ```

## 프로젝트 구조 차이

**starter-toolkit** — 기존 코드에 설정 파일 하나를 얹는 방식

```
thewhoo-agentcore-workshop/
  .bedrock_agentcore.yaml     # 배포 설정
  src/app.py                  # entrypoint
  requirements.txt
```

**AgentCore CLI** — `agentcore create` 가 정해진 구조를 만들어 줍니다

```
ThewhooChat/
  agentcore/
    agentcore.json            # 프로젝트 전체 선언 (runtimes/memories/
                              #  knowledgeBases/evaluators/gateways/datasets)
    aws-targets.json          # 계정·리전 타겟
    cdk/                      # CDK 프로젝트 (자동 생성)
    .env.local                # 로컬 환경변수 (gitignored)
  app/ThewhooChat/
    main.py                   # entrypoint
    memory/session.py         # Memory 세션 관리
    pyproject.toml
```

## entrypoint 계약이 다릅니다

**이게 이전 시 가장 큰 작업입니다.**

| | 워크샵 `src/app.py` | 새 CLI `app/<name>/main.py` |
|---|---|---|
| payload | `{"message": "..."}` | `{"prompt": "..."}` |
| 함수 형태 | 동기, `str` 반환 | **`async`, `yield` 스트리밍** |
| session/user | `_get_runtime_session_id()` 직접 구현 | `context.session_id` / `context.user_id` |
| Memory | `create_event` / `retrieve_memories` 직접 호출 | `get_memory_session_manager(session_id, actor_id)` 를 Agent 에 주입 |
| MCP | `MCPClient(...)` 수동 구성 | `get_streamable_http_mcp_client()` |

새 CLI 가 생성하는 형태:

```python
app = BedrockAgentCoreApp()

@app.entrypoint
async def invoke(payload, context):
    session_id = getattr(context, 'session_id', 'default-session')
    user_id = getattr(context, 'user_id', 'default-user')
    agent = get_or_create_agent(session_id, user_id)
    prompt = payload.get("prompt", "")
    async for event in agent.stream_async(prompt):
        yield event
```

> Memory 를 직접 다루지 않고 `session_manager` 에 위임한다는 게 큰 차이입니다. Lab 2 에서 배운 4-strategy 개념은 그대로지만, 코드에서 `create_event` 를 부르지 않습니다.

## 기존 자산 가져오기 — `agentcore import`

처음부터 다시 만들지 않아도 됩니다. 이미 AWS 에 있는 리소스를 프로젝트로 흡수할 수 있습니다.

```bash
# starter-toolkit 설정을 그대로 가져오기
agentcore import --source .bedrock_agentcore.yaml

# 개별 리소스 가져오기 (CLI 0.27.1 의 실제 하위 명령)
agentcore import runtime      # 기존 AgentCore Runtime
agentcore import memory       # 기존 AgentCore Memory
agentcore import gateway      # 기존 Gateway (target 까지 함께)
agentcore import evaluator    # 기존 Evaluator
agentcore import online-eval  # 기존 Online Evaluation Config
```

> 하위 명령 5종은 `agentcore import --help` 로 확인한 값입니다. 각 명령의 플래그는 버전마다 바뀌므로 `agentcore import runtime --help` 로 그때그때 확인하세요.

> **권장 순서** — 새 프로젝트를 `agentcore create` 로 만든 뒤, 기존 Memory·Gateway 를 `import` 로 붙이는 게 가장 안전합니다. Runtime 은 entrypoint 계약이 달라 코드 수정이 필요하므로 새로 배포하는 편이 낫습니다.

## 워크샵 Lab 을 전부 새 CLI 로 하면

워크샵은 **Lab 0-4 를 boto3 스크립트로** 진행합니다 — 각 리소스가 무엇이고 어떤 필드가 왜 필요한지 배우는 게 목적이기 때문입니다. 실서비스에서는 아래처럼 선언으로 대체할 수 있습니다.

| Lab | 워크샵 방식 (학습용) | 새 CLI |
|---|---|---|
| Lab 0 (KB) | `bootstrap_kb.py` + boto3 | `agentcore add knowledge-base` |
| Lab 2 (Memory) | `create-memory.py` 로 strategy 4개 추가 | `agentcore create --memory longAndShortTerm` **한 줄로 4-strategy 자동 생성** (또는 `agentcore add memory --strategies ...`) |
| Lab 3 (Gateway) | `create-gateway.py` + Lambda target 4개 | `agentcore add gateway` + `agentcore add gateway-target` |
| Lab 5 (배포) | — (Day 2 는 이미 새 CLI 사용) | `agentcore deploy` (CDK) |
| Lab 6 (관측) | CloudWatch 콘솔 | `agentcore logs` / `agentcore traces` + 콘솔 |
| Lab 7 (대시보드) | `create-cloudwatch-dashboard.sh` | 동일 (CloudWatch 는 CLI 무관) |
| Lab 8 (평가) | `run-golden-eval.py` (게이트 판정용) | `agentcore run eval --assertion ... --expected-trajectory ...` 또는 `--dataset` |

`agentcore add` 의 전체 하위 명령 (CLI 0.27.1 실측 — devguide 문서보다 많습니다):

```
agent · harness · memory · dataset · credential · evaluator · online-eval
online-insights · gateway · gateway-target · knowledge-base · policy-engine
policy · config-bundle · runtime-endpoint · payment-manager[preview]
payment-connector[preview] · tool · skill
```

> 워크샵에서 다루지 않는 것들 — `harness`(관리형 에이전트 루프), `policy-engine`/`policy`(Cedar 기반 도구 호출 인가), `config-bundle`(프롬프트·설정 버저닝 + A/B 테스트), `runtime-endpoint`(버전 별칭). 실서비스 고도화 단계에서 살펴볼 가치가 있습니다.

### Memory 자동 생성 확인 (실측)

`agentcore create --memory longAndShortTerm` 하나로 `agentcore.json` 에 4-strategy 가 선언됩니다.

```json
"memories": [{
  "name": "ThewhooChatMemory",
  "eventExpiryDuration": 30,
  "strategies": [
    { "type": "SEMANTIC",        "namespaceTemplates": ["/users/{actorId}/facts"] },
    { "type": "USER_PREFERENCE", "namespaceTemplates": ["/users/{actorId}/preferences"] },
    { "type": "SUMMARIZATION",   "namespaceTemplates": ["/summaries/{actorId}/{sessionId}"] },
    { "type": "EPISODIC",
      "namespaceTemplates": ["/episodes/{actorId}/{sessionId}"],
      "reflectionNamespaceTemplates": ["/episodes/{actorId}"] }
  ]
}]
```

> Lab 2 에서 스크립트로 한 일이 **선언 한 줄**로 대체됩니다. namespace 설계 개념을 이해하고 있으면 이 JSON 을 읽고 조정할 수 있습니다 — 그래서 Lab 2 를 배우는 의미가 있습니다.

### Lab 8 이 특히 좋아집니다

새 CLI 는 골든셋 개념을 **CLI 플래그로 직접 지원**합니다.

```bash
agentcore run eval \
  --evaluator Builtin.Helpfulness \
  --assertion "천기단 복합 성분과 장뇌삼을 언급해야 한다" \
  --expected-trajectory qa_tool

# 데이터셋 기반 (골든셋 JSON 을 dataset 으로 등록)
agentcore add dataset --name GoldenSet
agentcore run eval --dataset GoldenSet

# 전 세션 배치 평가
agentcore run batch-evaluation

# 실패 분석 / 프롬프트 최적화
agentcore run insights          # [preview]
agentcore run recommendation
```

`agentcore run eval --help` 로 확인한 ground truth 관련 플래그:

| 플래그 | 의미 | 골든셋 대응 |
|---|---|---|
| `-A, --assertion <text...>` | 답변이 만족해야 할 assertion (반복 가능) | `assertions` |
| `--expected-trajectory <names>` | 기대 도구 호출 순서 (**콤마 구분**) | `expected_trajectory` |
| `--expected-response <text>` | 기대 답변 텍스트 | `turns[].expected_response` |
| `--dataset` / `--dataset-version` | dataset 시나리오로 **에이전트를 직접 invoke** | 골든셋 전체 |
| `--runtime-arn` + `--region` | 프로젝트 디렉터리 밖에서 실행 | CI 에서 유용 |
| `-s, --session-id` / `-t, --trace-id` | 특정 세션·trace 만 평가 | 단건 확인 |
| `--days` | 조회 기간 (기본 7일) | |

> `--expected-trajectory` 는 **콤마 구분 문자열 하나**이고 `--assertion` 은 **반복 가능한 플래그**입니다. 형태가 다르니 주의하세요.
>
> 워크샵의 `run-golden-eval.py` 가 하던 일(invoke → span 수집 → evaluate → 게이트 판정)을 **CLI 가 대부분 내장**합니다. 특히 `--dataset` 은 과거 trace 를 읽는 게 아니라 **시나리오로 에이전트를 새로 invoke** 하므로, 스크립트의 invoke 단계까지 대체합니다.
>
> 다만 **PASS/FAIL 게이트 판정과 `exit 1`** 은 CLI 가 해주지 않습니다. CI 회귀 테스트로 쓰려면 그 부분은 여전히 스크립트가 필요합니다 — `run-golden-eval.py` 를 유지하는 이유입니다.

## 빠른 실습 — 새 CLI 로 처음부터

전제(Node 20+ · `uv` · CDK)가 준비됐다면 아래로 5분 안에 배포까지 확인할 수 있습니다. **실제로 검증한 흐름**입니다.

```bash
npm install -g @aws/agentcore

agentcore create --name ThewhooChat --framework Strands --protocol HTTP \
  --model-provider Bedrock --memory longAndShortTerm --build CodeZip
cd ThewhooChat

agentcore deploy --dry-run -y     # 먼저 검증만
agentcore deploy -y               # 실제 배포
agentcore status
agentcore invoke "천기단 화현 크림 성분 알려줘"
```

배포가 끝나면 Outputs 에 Runtime ARN · Memory ARN · IAM Role ARN 이 나오고, **Transaction Search 가 자동 활성화**됩니다 (약 10분 후 trace 인덱싱).

정리:

```bash
agentcore remove all -y
agentcore deploy -y      # CDK 가 실제 리소스를 teardown
```

## 주의사항 (실측 기준)

- `agentcore create` 의 기본 `runtimeVersion` 은 **PYTHON_3_14** 입니다. 의존성 호환성을 확인하세요.
- 생성된 기본 에이전트는 KB·Gateway 가 연결돼 있지 않습니다. 그 상태로 상품을 물으면 **LLM 이 환각합니다** — 반드시 `add knowledge-base` / `add gateway-target` 로 근거를 붙이세요. (실제로 확인한 현상입니다.)
- `agentcore run eval` 은 trace 인덱싱 전에는 `No session spans found` 를 반환합니다. invoke 후 몇 분 기다리세요.
- 배포는 CDK 스택(`AgentCore-<project>-default`)으로 관리되므로, 콘솔에서 리소스를 직접 지우면 스택과 어긋납니다. **정리는 반드시 `remove all` → `deploy`** 로 하세요.
- **`--output-dir` 은 부모 디렉터리만 지정합니다.** 문서에는 "Output directory (default: current directory)" 로만 적혀 있어 현재 디렉터리에 바로 펼쳐질 것처럼 읽히지만, 실측하면 `--output-dir .` 도 `./<name>/` 하위를 만듭니다. 기존 저장소 루트에 얹으려면 생성 후 `mv <name>/agentcore ./` 가 필요합니다.
- **`--defaults` 는 harness 프로젝트를 만듭니다.** CLI 0.27.1 에서 `agentcore create --name X --defaults` 는 "Harness project created successfully" 를 출력합니다 — Strands runtime 을 원하면 `--framework Strands --protocol HTTP --model-provider Bedrock` 을 **명시**하세요. (워크샵 Lab 5 명령은 이미 명시하고 있어 영향 없습니다.)
- **`agentcore.json` 의 `envVars` 는 배열**입니다: `[{"name": "K", "value": "V"}]`. 객체로 넣으면 `agentcore validate` 가 `expected "array"` 로 거부합니다.

## 참고 문서

- [Get started with the AgentCore CLI](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-get-started-cli.html)
- [Direct code deployment](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-get-started-code-deploy.html)
- [IAM Permissions for AgentCore Runtime](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-permissions.html)
- [AgentCore CLI GitHub](https://github.com/aws/agentcore-cli)
