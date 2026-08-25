# Day 2 부록 — 근거 자료

> **진행 중에 읽는 문서가 아닙니다.** 실습은 각 Lab 본문만 따라가면 됩니다.
> 이 문서는 두 경우에 봅니다:
>
> - 고객이 **"그 수치·제약의 근거가 뭐냐"** 고 물을 때
> - **실서비스 설계**에서 규모·한도를 정할 때

## 한도 (quota)

[Quotas 페이지](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/bedrock-agentcore-limits.html#evaluation-service-limits) 기준입니다. 전부 **조정 불가**입니다.

| 항목 | 값 | 의미 |
|---|---|---|
| built-in evaluator 입력 토큰 | 200,000/분 | judge 도 LLM 이라 토큰을 씁니다. 골든셋을 한꺼번에 돌리면 여기에 먼저 걸립니다 |
| built-in evaluator 평가 횟수 | 100/분 | 20 시나리오 × evaluator 4종 = 80회 → 1분 안에 몰아치면 근접합니다 |
| **evaluator / on-demand 평가 1회** | **1** | 여러 evaluator 는 각각 따로 호출해야 합니다 (`run-golden-eval.py` 가 루프로 처리) |
| span / on-demand 평가 | 1,000 | 매우 긴 세션은 초과 가능 |
| on-demand payload | 15 MB | span 이 많으면 나눠 호출 |
| 평가당 입력 토큰 | 200,000 | 한 세션의 span 이 너무 크면 초과 |

> 워크샵 규모(20 시나리오)에서는 문제가 없지만, **실서비스 골든셋을 수백 개로 늘리면** 분당 100회·200K 토큰에 먼저 부딪힙니다. 그때는 Batch 평가로 옮기는 게 정석입니다 (`agentcore run batch-evaluation` — 세션 500개/job, evaluator 10개/job).


### Runtime 한도

| 항목 | 값 | 근거 |
|---|---|---|
| 동시 세션 (Active session workloads) | **5,000** (us-east-1·us-west-2) / 2,500 (그 외) | [Runtime service limits](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/bedrock-agentcore-limits.html#runtime-service-limits) |
| 신규 세션 생성 | **25 TPS** | 같은 문서 |
| 데이터플레인 API 합산 | **1,000 TPS** (`InvokeAgentRuntime` 등 공유) | 같은 문서 |
| `runtimeSessionId` 최소 길이 | **33자** | 같은 문서 (*"session ID minimum is 33 characters"*) |

여러 참가자가 한 계정을 공유하거나 부하를 줄 때 `ThrottlingException` / `TooManyRequestsException` 으로 나타납니다. Service Quotas 에서 증가 요청하거나 병렬 요청 수를 줄이세요.

## API 스키마 교차검증

문서 서술이 맞는지 **API 정의로 직접 확인한 기록**입니다. 공식 문서에 명시가 없거나 헷갈리기 쉬운 지점만 남겼습니다.

### `environmentVariables` 는 map, `envVars` 는 배열

같은 개념인데 **표현이 다릅니다.**

| 어디 | 이름 | 타입 |
|---|---|---|
| `CreateAgentRuntime` API (boto3) | `environmentVariables` | **map** — `{"KB_ID": "..."}` |
| `agentcore.json` (CLI 설정) | `envVars` | **배열** — `[{"name": "KB_ID", "value": "..."}]` |

boto3 로 직접 Runtime 을 만들거나 고칠 때(`scripts/sync-runtime-env.py`)는 map, CLI 설정 파일은 배열입니다. **service model 로 확인한 사실**이며, 둘을 바꿔 쓰면 각각 다른 방식으로 거부됩니다.

### Online 평가에는 ground truth 를 넘길 통로가 없다

공식 문서가 *"cannot be used in online evaluation configurations, because online evaluations monitor live production traffic where ground truth values are not available"* 라고 서술하는데, **API 로도 교차 확인됩니다** — `CreateOnlineEvaluationConfig` 에는 `evaluationReferenceInputs` 에 해당하는 필드가 **아예 없습니다** (`rule` / `dataSourceConfig` / `evaluators` / `insights` / `clusteringConfig` 등). 즉 정답을 넘길 방법 자체가 존재하지 않습니다.

그래서 골든셋 회귀는 **On-demand 또는 Batch** 로 돌립니다.

### IAM action prefix 는 endpoint 이름이 아니라 signingName

boto3 클라이언트 이름과 IAM prefix 가 다릅니다:

| boto3 클라이언트 | IAM action prefix |
|---|---|
| `bedrock` / `bedrock-runtime` / `bedrock-agent` / `bedrock-agent-runtime` | 전부 **`bedrock:*`** |
| `bedrock-agentcore` / `bedrock-agentcore-control` | 전부 **`bedrock-agentcore:*`** |

`bedrock-runtime:*` / `bedrock-agent-runtime:*` / `bedrock-agentcore-control:*` 는 **존재하지 않는 prefix** 입니다. IAM 은 오타 prefix 를 거부하지 않고 **조용히 무시**하므로 아무 권한도 주지 않은 채 통과합니다 (`SimulateCustomPolicy` 로 `implicitDeny` 확인).

### `cdk bootstrap` 에는 ecr·ssm 권한이 필요하다

bootstrap 은 ECR 리포지토리(`ContainerAssetsRepository`)와 SSM 파라미터(`CdkBootstrapVersion`)를 만듭니다. **`cloudformation:*` 만으로는 부족합니다** — CloudFormation 이 참가자 자격증명으로 대상 서비스를 호출하기 때문에 `ecr` · `ssm` 권한이 따로 있어야 합니다 (실측 확인).

### prompt cache 토큰 이름이 3번 바뀐다

| 층 | 이름 |
|---|---|
| Anthropic API 응답 | `cache_creation_input_tokens` |
| Strands SDK 내부 | `cacheWriteInputTokens` |
| **span attribute (콘솔에서 보이는 것)** | **`gen_ai.usage.cache_write_input_tokens`** |

콘솔에서 `cache_creation` 으로 검색하면 아무것도 안 나옵니다. 변환 경로는 `strands/models/anthropic.py` → `strands/telemetry/tracer.py` 에서 확인했습니다.

### prompt caching 최소 토큰은 모델마다 다르다

| 모델 | 최소 토큰 |
|---|---|
| Sonnet 4.6 | **1,024** |
| Haiku 4.5 | **4,096** |

이 워크샵에서 Haiku 서브에이전트에 캐시가 안 잡히는 이유입니다 — 프롬프트가 4,096 을 못 넘깁니다. Orchestrator(Sonnet)는 1,996 토큰이라 1,024 를 넘겨 통과합니다.

### Strands 가 만드는 span 이름은 4종

| span 이름 | 무엇인가 |
|---|---|
| `invoke_agent <에이전트명>` | 에이전트 1회 실행 |
| `execute_event_loop_cycle` | 추론 루프 1사이클 |
| **`chat <모델ID>`** | **모델 호출 — 캐시 토큰이 여기** |
| `execute_tool <도구명>` | 도구 실행 |

`orchestrator` 나 `LLM` 이라는 이름의 span 은 **없습니다.** root span 은 `POST /invocations` (kind=SERVER) 입니다.

## ground truth 필드의 적용 범위

공식 [Ground truth evaluations](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/ground-truth-evaluations.html) 기준, 필드마다 scope 가 다릅니다.

| 필드 | scope | 의미 |
|---|---|---|
| `assertions` | **Session** | 세션 전체에 대해 1건 채점 |
| `expectedTrajectory` | **Session** | 세션 전체의 도구 호출 시퀀스 1건 |
| `expectedResponse` | **Trace** | 특정 turn 의 답변 — 매핑 규칙이 호출 방식마다 다름 (아래) |

### `expected_response` 매핑 — 두 문서를 구분해 읽어야 합니다

| 사용 방식 | 매핑 규칙 | 출처 |
|---|---|---|
| **데이터셋 러너** (`--dataset`, `FileDatasetProvider`) | **위치 기반** — turn 0 → trace 0, turn 1 → trace 1 | [Dataset schema](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/dataset-evaluations-schema.html): *"Mapped positionally to the trace produced by this turn"* |
| **Evaluate API 직접 호출** (`run-golden-eval.py`) | `traceId` 를 주면 그 trace, **없으면 세션의 마지막 trace** | [Ground truth evaluations](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/ground-truth-evaluations.html): *"String form — matched against the last trace in the session"* |

러너는 turns 를 순서대로 실행하므로 위치 기반 매핑이 성립하고, API 를 직접 부를 때는 어느 trace 인지 알려줄 방법이 `traceId` 뿐입니다. **워크샵 스크립트는 후자**이므로 멀티턴에서 턴마다 정답을 채점하려면 turn 별 `traceId` 를 찾아 reference input 을 나눠야 합니다. (현재 골든셋은 전부 단일 턴 + `expected_response` 미사용이라 해당되지 않습니다.)

**evaluator 가 안 쓰는 필드는 무시됩니다 — 에러가 아닙니다.** 응답의 `ignoredReferenceInputFields` 에 어떤 필드가 안 쓰였는지 보고되므로, reference input 을 한 번 만들어 여러 evaluator 에 재사용할 수 있습니다.

## 골든셋 데이터셋 보관 방식 두 갈래

같은 스키마를 쓰지만 보관 방식이 다릅니다. **워크샵은 B** 입니다.

| | A. CLI 데이터셋 리소스 | B. 로컬 파일 (이 워크샵) |
|---|---|---|
| 파일 | `agentcore/datasets/<name>.jsonl` (**JSONL**) | `golden-set.json` (**단일 JSON**) |
| 등록 | `agentcore add dataset --schema-type AGENTCORE_EVALUATION_PREDEFINED_V1` → `deploy` | 없음 |
| 버전 관리 | 서비스가 관리 | git |
| 로드 | `--dataset <name>` | `FileDatasetProvider(path)` |
| 한도 | 요청당 예제 1,000개 · inline 5MB | 없음 |

**왜 B 인가** — 골든셋을 **git 에 두고 코드와 함께 리뷰·버전 관리**하는 것이 회귀 테스트의 기본이고, PR 게이트에 그대로 붙습니다. A 는 여러 팀이 데이터셋을 공유하거나 서비스측 버전 이력이 필요할 때 유리합니다. 형식만 다르고 스키마는 같으므로 전환은 `scenarios` 배열을 한 줄씩 JSONL 로 풀어 쓰면 됩니다.
