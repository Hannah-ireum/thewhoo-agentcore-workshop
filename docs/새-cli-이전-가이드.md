# 새 AgentCore CLI 로 이전하기

*— 워크샵 Lab 5-8 은 Python starter-toolkit 기반입니다. 실서비스에는 공식 권장 경로인 새 AgentCore CLI 를 쓰세요.*

## 왜 이 문서가 있나

Lab 5 에서 `agentcore configure` 를 실행하면 이 배너가 뜹니다.

```
⚠️ Recommendation: The Starter Toolkit CLI is no longer supported.
   Please use the AgentCore CLI (@aws/agentcore) to create, develop, and deploy
   agents on Amazon Bedrock AgentCore.
   New Bedrock AgentCore features are only accessible in the AgentCore CLI.
```

**워크샵 실습은 그대로 진행하면 됩니다** — starter-toolkit 은 현재도 정상 동작합니다 (2026-08-20 전 Lab 완주 검증). 다만 **신규 기능은 새 CLI 에만 들어오므로**, 실제 프로젝트를 시작한다면 새 CLI 로 가는 게 맞습니다.

두 CLI 는 **같은 AgentCore 서비스**를 다룹니다. 워크샵에서 배운 개념(Runtime · Memory · Gateway · Observability · Evaluations)은 그대로 유효하고, **명령과 프로젝트 구조만 달라집니다.**

## 두 CLI 비교

| | Python starter-toolkit (워크샵) | AgentCore CLI (공식 권장) |
|---|---|---|
| 패키지 | `bedrock-agentcore-starter-toolkit` (pip) | `@aws/agentcore` (npm) |
| 설정 파일 | `.bedrock_agentcore.yaml` | `agentcore/agentcore.json` |
| 배포 방식 | 자체 패키징 → Runtime API 직접 호출 | **AWS CDK** → CloudFormation |
| 추가 전제 | 없음 (Python 만) | **Node.js 20+ · AWS CDK · `cdk bootstrap`** |
| 리소스 범위 | Runtime 위주 | Runtime · Memory · KB · Gateway · Evaluator · Dataset 등 **선언적 통합 관리** |
| 신규 기능 | 반영 안 됨 | 여기만 |

> **핵심 차이** — starter-toolkit 은 "Runtime 배포 도구" 였고, 새 CLI 는 "**프로젝트 전체를 코드로 선언**하는 IaC 도구" 입니다. 그래서 CDK 가 들어옵니다.

## 전제조건

공식 문서 [Get started with the AgentCore CLI](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-get-started-cli.html) 기준.

- **Node.js 20+** — CLI 가 npm 패키지
- **Python 3.10+** — 생성되는 에이전트 코드가 Python
- **AWS CDK** — 배포에 사용. 계정·리전에 `cdk bootstrap` 이 되어 있어야 합니다
- **IAM 권한** — starter-toolkit 보다 넓습니다. `iam:CreateRole`, `codebuild:*`, `ecr:*`, `s3:*` 등. 정확한 정책 JSON 은 공식 문서 [IAM Permissions for AgentCore Runtime → Use the AgentCore CLI](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-permissions.html#runtime-permissions-cli) 참고

> ⚠️ **워크샵 환경(Workshop Studio)에는 Node.js·CDK·bootstrap 이 준비돼 있지 않습니다.** 그래서 워크샵 Lab 은 starter-toolkit 을 유지합니다. 새 CLI 를 쓰려면 아래 준비가 먼저 필요합니다.

```bash
# Node.js 20+ 확인
node --version

# CDK 설치 + bootstrap (계정·리전당 1회)
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

| 하려는 일 | starter-toolkit (워크샵) | AgentCore CLI |
|---|---|---|
| 프로젝트 생성 | (없음 — 기존 코드에 붙임) | `agentcore create` |
| 설정 | `agentcore configure --entrypoint ... --name ...` | `agentcore/agentcore.json` 편집 또는 `agentcore add ...` |
| 로컬 실행 | `agentcore invoke --dev` | `agentcore dev` |
| 배포 | `agentcore deploy --env K=V` | `agentcore deploy` |
| 배포 전 확인 | (없음) | `agentcore deploy --dry-run` / `--diff` |
| 호출 | `agentcore invoke '{"message":"..."}'` | `agentcore invoke "..."` |
| 상태 | `agentcore status` | `agentcore status` |
| 로그 | `aws logs tail ...` | `agentcore logs` |
| trace | CloudWatch 콘솔 | `agentcore traces` |
| 평가 | `agentcore eval run --session-id ...` | `agentcore run eval --session-id ...` |
| 정리 | `agentcore destroy` | `agentcore remove all` → `agentcore deploy` |

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

# 개별 리소스 가져오기
agentcore import runtime --arn <runtime-arn> --code src/ --entrypoint app.py --name ThewhooChat
agentcore import memory   --name ThewhooChatMemory
agentcore import gateway  # target 까지 함께
agentcore import evaluator
agentcore import online-eval
```

> **권장 순서** — 새 프로젝트를 `agentcore create` 로 만든 뒤, 기존 Memory·Gateway 를 `import` 로 붙이는 게 가장 안전합니다. Runtime 은 entrypoint 계약이 달라 코드 수정이 필요하므로 새로 배포하는 편이 낫습니다.

## 워크샵 Lab 을 새 CLI 로 하면

각 Lab 이 이렇게 대응됩니다.

| Lab | 워크샵 방식 | 새 CLI |
|---|---|---|
| Lab 0 (KB) | `bootstrap_kb.py` + boto3 | `agentcore add knowledge-base` |
| Lab 2 (Memory) | `create-memory.py` 로 strategy 4개 추가 | `agentcore create --memory longAndShortTerm` **한 줄로 4-strategy 자동 생성** |
| Lab 3 (Gateway) | `create-gateway.py` + Lambda target 4개 | `agentcore add gateway` + `agentcore add gateway-target` |
| Lab 5 (배포) | `configure` → `deploy --env ...` | `agentcore deploy` (CDK) |
| Lab 6 (관측) | CloudWatch 콘솔 | `agentcore logs` / `agentcore traces` + 콘솔 |
| Lab 7 (대시보드) | `create-cloudwatch-dashboard.sh` | 동일 (CloudWatch 는 CLI 무관) |
| Lab 8 (평가) | `eval run` + `run-golden-eval.py` | `agentcore run eval --assertion ... --expected-trajectory ...` 또는 `--dataset` |

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
agentcore run insights
agentcore run recommendation
```

> 워크샵의 `run-golden-eval.py` 가 하던 일(invoke → span 수집 → evaluate → 게이트 판정)을 **CLI 가 내장**합니다. `--dataset` 을 쓰면 스크립트 없이 골든셋 회귀를 돌릴 수 있습니다.

## 빠른 실습 — 새 CLI 로 처음부터

전제(Node·CDK·bootstrap)가 준비됐다면 아래로 5분 안에 배포까지 확인할 수 있습니다. **실제로 검증한 흐름**입니다.

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

## 참고 문서

- [Get started with the AgentCore CLI](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-get-started-cli.html)
- [Direct code deployment](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-get-started-code-deploy.html)
- [IAM Permissions for AgentCore Runtime](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-permissions.html)
- [AgentCore CLI GitHub](https://github.com/aws/agentcore-cli)
