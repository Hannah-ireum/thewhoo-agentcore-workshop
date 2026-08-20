# 진행자 대본 — Day 2 (서비스 배포·운영)

> **진행자용** 문서입니다. 참가자 배포 자료가 아닙니다.
> 명령과 출력은 실제 AWS 계정에서 완주 검증한 값입니다.

## ⚠️ 진행 전 필수 확인 — CLI

Day 2 는 공식 문서가 안내하는 **AgentCore CLI**(`@aws/agentcore`, npm)를 사용합니다. AgentCore CLI 는 2026-02 public preview → 2026-03 GA(v0.4.0) 로 출시됐고, 현재 최신은 **0.27.1**(2026-08-20 npm 게시)입니다.

구 Python starter-toolkit 은 **AWS 가 legacy 로 표기**했습니다 — GitHub 저장소 설명이 "Python CLI toolkit for Amazon Bedrock AgentCore (legacy). For new projects, use the AgentCore CLI" 이고, PyPI 최신 0.3.12(2026-08-19)에도 "no longer supported" 문구가 실려 있습니다. 즉 배너뿐 아니라 **패키지 메타데이터 수준의 표기**입니다. (devguide release notes 에는 항목이 없습니다 — 공지 경로가 저장소·PyPI 쪽.)

**진행자가 확인할 것 (실습 시작 전에 한 번):**

```bash
node --version     # v20 이상
npm --version
uv --version       # ⚠️ Python 에이전트 필수
```

Code Editor 에는 Node.js 가 기본 포함돼 있습니다 (검증 시 v20.19.6 / npm 11.18.0). **`cdk bootstrap` 은 참가자가 직접 하지 않아도 됩니다** — 첫 `agentcore deploy` 가 필요하면 자동 처리합니다.

### ⚠️ `uv` — 공식 devguide 에 빠져 있는 전제조건

devguide 의 Prerequisites 는 Node.js·Python·CDK·권한·모델액세스만 적고 **`uv` 를 빠뜨렸습니다.** 하지만 CLI 저장소 README 는 "uv — for Python agents" 를 요구사항으로 명시하고, CLI 내부 사전점검이 `uv` 를 severity `error` 로 검사합니다 (`'uv' is required for Python projects`).

`uv` 가 없으면 `agentcore create` 가 **바로 멈춥니다** (실측: exit 1, 디렉터리도 안 만들어짐):

```
'uv' is required for Python projects. Install from https://github.com/astral-sh/uv#installation
```

> **진행자에게 좋은 소식** — 메시지가 명확하고 중간 상태를 남기지 않아서, 참가자가 막히면 원인을 바로 알 수 있습니다. 다만 여러 명이 동시에 막히면 시간을 잡아먹으니 **Lab 5 시작 전에 `uv --version` 을 전원 확인**시키는 게 낫습니다.

워크샵은 `setup-python.sh` 가 `uv` 를 자동 설치하고 uv 설치 스크립트가 `~/.bashrc` 를 갱신하므로, Pre-Lab 을 마친 참가자는 준비돼 있습니다. 실패했다면:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
# 새 터미널을 열거나
export PATH="$HOME/.local/bin:$PATH"
```

**참가자가 물어볼 것:**

> **Q. 왜 npm 인가요? Python 워크샵인데요.**
> CLI 만 Node 로 배포됩니다. 에이전트 코드는 그대로 Python 입니다. CLI 가 AWS CDK 를 내부적으로 쓰기 때문입니다.
>
> **Q. 예전 자료에는 `agentcore configure` 가 있는데요.**
> 구 starter-toolkit 명령입니다. 그 도구가 "신규 기능은 AgentCore CLI 에만 들어온다" 고 안내하고 있고, 공식 Get started 문서도 AgentCore CLI 를 가리킵니다. 명령 대응표는 [새 CLI 이전 가이드](새-cli-이전-가이드.md) 에 있습니다.
>
> **Q. 이미 배포한 Runtime 이 있으면 버려야 하나요?**
> 아니요. `agentcore import runtime --arn <arn>` 으로 새 프로젝트에 가져올 수 있습니다.

## 타임라인 (총 약 2시간 40분)

| 시각 | 내용 | 소요 |
|---|---|---|
| 0:00 | Day 1 복습 · Day 2 목표 | 10분 |
| 0:10 | 환경 복구 확인 | 10분 |
| 0:20 | **Lab 5** Runtime 배포 | 45분 |
| 1:05 | ☕ 휴식 | 10분 |
| 1:15 | **Lab 6** Observability | 30분 |
| 1:45 | **Lab 7** 대시보드 | 30분 |
| 2:15 | **Lab 8** Evaluations | 30분 |
| 2:45 | 마무리 · 실서비스 체크리스트 | 15분 |

> **지연 대응** — Lab 8 의 골든셋 20문항 전체 실행은 **trace 인덱싱 대기만 5분+** 라 시간을 많이 씁니다. 밀리면 `--case INFO_Q01` 단건으로 줄이세요.

---

## 오프닝 (10분)

### 말할 것

> "어제 만든 챗봇은 **여러분 터미널에서만** 돌아갑니다. 노트북을 닫으면 끝이죠. 오늘은 이걸 **서비스**로 만듭니다."
>
> "서비스가 된다는 건 세 가지가 따라온다는 뜻입니다."
>
> 1. **배포** — 누구나 호출할 수 있는 엔드포인트 (Lab 5)
> 2. **관측** — 안에서 무슨 일이 일어났는지 볼 수 있어야 함 (Lab 6·7)
> 3. **품질 보증** — 배포할 때마다 답변이 나빠지지 않았는지 자동 확인 (Lab 8)

> "특히 3번이 실무에서 가장 자주 빠집니다. LLM 앱은 코드를 안 바꿨는데도 품질이 변할 수 있습니다. 그래서 회귀 테스트가 필수입니다."

### 환경 복구 (10분)

```bash
cd ~/thewhoo-agentcore-workshop
source .venv/bin/activate          # ⚠️ 새 터미널이면 필수
eval "$(./scripts/print-env.sh w001)"
echo "KB=$KB_ID  MEM=$AGENTCORE_MEMORY_ID  GW=$AGENTCORE_GATEWAY_URL"
```

세 값이 다 나와야 진행 가능합니다.

> **진행자 주의** — Day 1 과 다른 계정이거나 리소스를 지운 참가자가 있으면 `README-day2.md` 의 **시나리오 B 패스트트랙**으로 보내세요 (약 20-25분). 전체 진행을 세우지 말고 그 참가자만 따로 돌립니다.

---

## Lab 5. Runtime 배포 (45분)

### 말할 것

> "왜 Lambda 가 아니고 AgentCore Runtime 일까요? 세 가지 때문입니다."
>
> 1. **세션 유지** — 에이전트 대화는 상태가 있습니다. Lambda 는 stateless 라 세션마다 외부 저장소가 필요합니다
> 2. **긴 실행** — 멀티턴 + 도구 호출이 이어지면 15분을 넘길 수 있습니다
> 3. **관측 자동 연결** — CloudWatch Logs·X-Ray·Transaction Search 를 배포가 알아서 붙입니다

### 강조할 개념 — 이번엔 IaC 입니다

> "새 CLI 는 '배포 스크립트' 가 아니라 **프로젝트 전체를 JSON 으로 선언**하는 방식입니다. Runtime·Memory·KB·Gateway·Evaluator 를 한 파일에서 관리하고, CDK 가 CloudFormation 으로 바꿔 적용합니다."
>
> "그래서 좋은 점 — `remove` 후 `deploy` 하면 **정확히 되돌아갑니다**. 손으로 만든 리소스는 이게 안 되죠."

### 입력할 명령

**1) CLI 설치 + 프로젝트 생성**

```bash
cd ~/thewhoo-agentcore-workshop
npm install -g @aws/agentcore
agentcore --version

agentcore create --name ThewhooChat \
  --framework Strands --protocol HTTP \
  --model-provider Bedrock --memory none --build CodeZip
```

> **`--memory none` 을 설명하세요** — "Memory 는 Lab 2 에서 이미 만들었습니다. 여기서 또 만들면 두 개가 됩니다."
>
> 새 프로젝트라면 `--memory longAndShortTerm` **한 줄로 4-strategy 가 자동 선언**된다는 것도 알려주세요. Lab 2 에서 스크립트로 한 일이 설정 한 줄이 됩니다. (개념을 알아야 이 JSON 을 읽고 조정할 수 있다는 점을 짚어주면 Lab 2 의 의미가 살아납니다.)

**2) 우리 코드를 가리키게 설정**

```bash
eval "$(./scripts/print-env.sh w001)"
python3 scripts/set-agentcore-config.py
```

이 스크립트가 `agentcore.json` 에 넣는 것을 설명하세요:

| 필드 | 값 | 왜 |
|---|---|---|
| `codeLocation` | `src/` | Lab 1-4 에서 만든 코드를 그대로 배포 |
| `entrypoint` | `app.py` | `codeLocation` **기준 상대경로** |
| `runtimeVersion` | `PYTHON_3_12` | 기본값이 3.14 라 의존성 호환용으로 낮춤 |
| `envVars` | KB/Memory/Gateway ID | 구 CLI 의 `--env` 를 대체 |

**3) 배포 — 먼저 dry-run**

```bash
agentcore deploy --dry-run -y
```

> **이걸 먼저 돌리게 하세요.** 설정 오류를 리소스 생성 전에 잡습니다. `✓ Dry run complete` 가 나와야 다음으로 갑니다.

```bash
agentcore deploy -y
agentcore status
```

### ⚠️ 진행자가 미리 알려줄 것 — `pyproject.toml`

참가자가 자기 프로젝트에 적용할 때 **가장 먼저 만나는 에러**입니다.

```
CDK synth failed: Required project file not found: .../src/pyproject.toml
```

> "새 CLI 는 `requirements.txt` 를 읽지 않습니다. `pyproject.toml` 이 필요합니다. 워크샵 저장소에는 `src/pyproject.toml` 을 미리 넣어 뒀습니다."
>
> "로컬 개발은 `requirements.txt`, 배포는 `pyproject.toml` — **두 파일의 버전 범위를 맞춰 두세요**. 어긋나면 '로컬은 되는데 배포는 실패' 가 됩니다."

### ⭐ 보여줄 것 — 멀티턴 세션

```bash
agentcore invoke --session-id lab5-demo "건성 피부인데 보습크림 추천해줘"
agentcore invoke --session-id lab5-demo "성분도 알려줘"
```

**보여줄 것**: 두 번째에서 "성분도" 만 물었는데 첫 번째 추천 제품의 성분이 나옵니다.

> "세션이 유지된다는 증거입니다. 출력 끝에 `To resume:` 로 세션 ID 를 알려주니 따로 적을 필요도 없습니다."

### ⚠️ 그리고 이걸 짚어주세요 — Transaction Search 자동 활성화

배포 출력 마지막 줄:

```
Note: Transaction search enabled. It takes ~10 minutes ...
```

> "Lab 6 의 전제조건을 배포가 알아서 켜 줬습니다. 예전에는 별도 스크립트로 했던 부분입니다. 다만 **trace 인덱싱까지 10분** 걸리니, Lab 6 은 조금 뒤에 확인합니다."

여기서 **휴식을 넣으면 타이밍이 맞습니다.**

### 자주 나오는 질문

**Q. `agentcore: command not found`**
> `npm install -g` 후 새 터미널을 여세요. `node --version` 이 20 이상인지도 확인.

**Q. 코드를 고치고 다시 배포하려면?**
> `agentcore deploy -y` 같은 명령입니다. CDK 가 변경분만 적용합니다. 뭐가 바뀌는지 미리 보려면 `--diff`.

**Q. 첫 invoke 가 `Runtime initialization time exceeded`**
> cold start 입니다. 한 번 더 호출하면 됩니다.

**Q. 콘솔에서 리소스를 지워도 되나요?**
> **안 됩니다.** CDK 스택과 어긋납니다. 정리는 `agentcore remove all` → `agentcore deploy` 로 하세요.

## Lab 6. Observability (30분)

### 말할 것

> "배포했는데 답변이 이상하다는 문의가 왔습니다. 어디를 봐야 할까요? **로그가 아니라 trace** 입니다."
>
> "에이전트 한 번 호출에 LLM 호출 여러 번, 도구 호출 여러 번이 일어납니다. 이걸 **span 트리**로 보면 어디서 시간을 썼고 어떤 도구를 왜 골랐는지가 다 보입니다."

### 입력할 명령 / 보여줄 것

CloudWatch → **GenAI Observability** → Agents → `thewhoo_chat` → Sessions → trace 하나 클릭

**span 트리에서 짚어줄 것** (실측 확인된 구조):

```
AgentCore.Runtime.Invoke          ← HTTP wrapper
  invoke_agent Strands Agents     ← ⭐ 여기 attributes 가 가장 풍성
    chat us.anthropic.claude-sonnet-4-6      ← Orchestrator
    execute_tool qa_tool
      chat us.anthropic.claude-haiku-4-5...  ← 서브에이전트
      execute_tool kb_retrieve
        Bedrock Agent Runtime.Retrieve       ← KB 호출
    execute_tool recommend_tool
      mcp tools/call product-search___product_search   ← Gateway 경유
    Bedrock AgentCore.RetrieveMemoryRecords  ← Memory
```

> "이 한 장에 어제 만든 게 다 들어 있습니다. Lab 1 의 KB, Lab 2 의 Memory, Lab 3 의 Gateway, Lab 4 의 오케스트레이션."

`invoke_agent Strands Agents` span 의 attributes 에서:

| attribute | 실측 예시 |
|---|---|
| `gen_ai.agent.tools` | `["qa_tool","recommend_tool","summary_tool"]` |
| `gen_ai.usage.cache_write_input_tokens` | 1996 (첫 호출) |
| `gen_ai.usage.cache_read_input_tokens` | 1996 (다음 호출) |
| `session.id` | invoke 시 넣은 값 |

> "cache_write 가 첫 호출에 크고, 다음 호출에서 같은 값이 cache_read 로 잡히죠. **prompt caching 이 동작한다는 직접적인 증거**입니다."

### ⚠️ 진행자가 미리 알려줄 것

- trace 는 **인덱싱에 2-5분** 걸립니다. Lab 5 invoke 직후 바로 안 보이는 게 정상입니다.
- "Enable Agent observability" 안내만 보이면 계정 레벨 **Transaction Search** 가 꺼진 것입니다 → CloudShell 에서 `./scripts/setup-day2-cloudshell.sh w001` 재실행.
- 같은 invoke 가 **두 trace** 로 보이는 건 정상입니다 (HTTP wrapper + Strands 내부).

---

## Lab 7. 대시보드 (30분)

### 말할 것

> "Observability 는 **한 건을 깊게** 보는 도구입니다. 그런데 운영자는 '지금 전체가 정상인가' 를 봐야 하죠. 그게 대시보드입니다."

### 입력할 명령

```bash
cd ~/thewhoo-agentcore-workshop
./scripts/create-cloudwatch-dashboard.sh
```

이어서 트래픽을 만듭니다 (진행자는 `--quick` 권장, 약 3분):

```bash
./scripts/simulate-traffic.sh --quick
```

5-10분 대기 후 대시보드 새로고침.

### ⚠️ 진행자가 반드시 먼저 말할 것 — "에러 0 이 정상입니다"

트래픽 스크립트가 **잘못된 페이로드도 일부러 보냅니다**. 참가자는 위젯 1 의 에러 그래프가 올라갈 거라 기대합니다. **올라가지 않습니다.**

> "왜 0 일까요? 잘못된 payload 가 Runtime 을 통과해서 컨테이너까지 옵니다. 그리고 `app.py` 가 예외를 던지지 않고 '메시지를 입력해주세요' 를 **정상 응답(200)** 으로 돌려줍니다."
>
> "이건 버그가 아니라 **의도된 방어 설계**입니다. 실서비스에서 잘못된 입력에 500 을 던지는 것보다 안내 문구가 낫죠."
>
> "대신 **대가가 있습니다** — 입력 오류가 metric 에 안 보입니다. 이런 걸 추적하려면 `app.py` 에서 custom metric 을 직접 올리거나 구조화된 WARN 로그를 남겨야 합니다. **trade-off 를 아는 것**이 이 Lab 의 포인트입니다."

### 위젯별 기대값 (실측)

| 위젯 | 기대 |
|---|---|
| 1. 호출량/에러 | Invocations 올라감, **에러 3종은 0 이 정상** |
| 2. Latency P50/P95/P99 | 분포 표시 |
| 3. Sessions | 사용자 수만큼 |
| 4. 모델별 토큰 | Sonnet + Haiku 두 줄 |
| 5. Cache Hit Ratio | **20~40% 가 정상** (실측 29%) |
| 6. CPU/Memory | **최대 60분 지연** — 오늘 안 보일 수 있음 |
| 7. 에러 로그 tail | **비어있는 게 정상** |

### ⚠️ Cache Hit Ratio 도 미리 설명

> "높은 숫자가 안 나온다고 문제가 아닙니다. `cache_config` 를 **Orchestrator 에만** 걸었고 Haiku 서브에이전트 3개는 캐시가 없습니다. 위젯은 전 모델 합산이라 구조적으로 **20~40%** 가 나옵니다 (실측 29%)."
>
> "판단 기준은 절대값이 아니라 **평소 대비 급락**입니다. 29% 였는데 5% 가 되면 system prompt 가 가변화된 신호죠."

**분모를 반드시 짚어주세요** — 참가자가 직접 계산해보다 틀리는 지점입니다.

> "prompt caching 이 켜지면 `inputTokens` 는 **캐시되지 않은 토큰만** 뜻합니다. 공식 문서에 이렇게 나옵니다:
> `total input tokens = inputTokens + cacheReadInputTokens + cacheWriteInputTokens`
> 그래서 `cache_read / input_tokens` 로 계산하면 100% 를 넘는 무의미한 값이 됩니다. 위젯은 분모에 세 항목을 다 더합니다."

### 💡 질문이 나오면 — "Haiku 에도 캐시를 걸면 되지 않나요?"

걸어도 **거의 안 걸립니다.** 모델마다 cache checkpoint 최소 토큰이 다르기 때문입니다 (공식 [Prompt caching](https://docs.aws.amazon.com/bedrock/latest/userguide/prompt-caching.html) 표):

| 모델 | 최소 토큰 / checkpoint |
|---|---|
| Claude Sonnet 4.6 (Orchestrator) | **1,024** |
| Claude Haiku 4.5 (서브에이전트) | **4,096** |

> "Orchestrator 의 system prompt 는 실측 1,996 토큰이라 Sonnet 기준 1,024 를 넘겨서 캐시가 걸립니다. 반면 서브에이전트 프롬프트는 훨씬 짧아서 Haiku 의 4,096 을 못 넘깁니다. **`cache_config` 를 걸어도 조용히 캐시가 안 잡히고**, 최소치 미달이면 추론은 성공하지만 prefix 는 캐시되지 않습니다."
>
> "실무 교훈 — 캐시를 켰는데 `cache_write` 가 0 이면 프롬프트가 그 모델의 최소치를 못 넘긴 건지 먼저 확인하세요. 모델을 바꾸면 임계값도 바뀝니다."

---

## Lab 8. Evaluations (30분)

### 말할 것

> "마지막이자 실무에서 가장 자주 빠지는 부분입니다. **LLM 앱은 코드를 안 바꿨는데도 품질이 변합니다.** 모델 업데이트, 프롬프트 한 줄 수정, 도구 설명 변경 — 다 영향을 줍니다."
>
> "그래서 **골든셋**을 만들어 둡니다. '이 질문에는 이런 답이 나와야 한다' 를 20개 정해 두고, 배포할 때마다 자동으로 채점합니다."

### 강조할 개념 — LLM-as-Judge

> "정답을 문자열로 비교할 수 없습니다. 답변이 매번 다르니까요. 그래서 **다른 LLM 이 채점**합니다. 'assertion 을 만족하는가?' 를 판단하죠."

골든셋 구조를 보여주세요 (`docs/eval/golden-set.json`):

```json
{
  "scenario_id": "INFO_Q01",
  "turns": [{ "input": "천기단 화현 크림 주요 성분이 뭐야?" }],
  "expected_trajectory": ["qa_tool"],
  "assertions": ["천기단 복합 성분과 함께 장뇌삼, 영지, 청아교 중 최소 두 가지를 언급해야 한다."]
}
```

> "`assertions` 는 **의미**를 적습니다. 키워드 일치가 아니라 '이 내용이 담겼는가' 를 judge 가 봅니다."

### 입력할 명령 — 단건 먼저

```bash
SID="eval-$(date +%s)-$(python3 -c 'import uuid;print(uuid.uuid4())')"
agentcore invoke --session-id "$SID" "건성 피부에 좋은 보습크림 추천해줘"
# trace 인덱싱 2-5분 대기
agentcore run eval --session-id "$SID" \
  --evaluator "Builtin.Helpfulness" \
  --evaluator "Builtin.GoalSuccessRate" \
  --evaluator "Builtin.ToolSelectionAccuracy"
```

**보여줄 출력** (실측):

```
Evaluator: Builtin.Helpfulness        Score: 1.00   Label: Above And Beyond
Evaluator: Builtin.GoalSuccessRate    Score: 1.00   Label: Yes
Evaluator: Builtin.ToolSelectionAccuracy  Score: 1.00  Label: Yes
```

> "`value` 는 **0~1 로 정규화**돼 옵니다. `label` 은 등급명이죠. 게이트 기준 0.5 는 이 0~1 스케일입니다."

### 골든셋 자동 회귀 (시간 있으면)

```bash
python3 scripts/run-golden-eval.py --case INFO_Q01 --wait 300
```

> **진행자 주의** — 20문항 전체는 invoke + 인덱싱 대기로 **10분 이상** 걸립니다. 시간이 없으면 `--case` 단건으로 보여주고, 전체 실행은 "CI 에서 돌리는 것" 이라고 설명만 하세요.

**게이트 통과 출력:**

```
✅ INFO_Q01                  PASS
✅ 전체 PASS — release ready
```

> "FAIL 이 하나라도 있으면 `exit 1` 입니다. GitHub Actions 나 CodePipeline 에 그대로 붙일 수 있죠. **이게 LLM 앱의 회귀 테스트**입니다."

### 자주 나오는 질문

**Q. built-in evaluator 는 몇 개인가요?**
> 문서에 13개를 표로 정리했고, 라이브 API 는 계속 늘고 있습니다 (2026-08 확인 시 Builtin 18종 + ThirdParty DeepEval 13종). `Builtin.Trajectory*` 계열이 추가돼 `expected_trajectory` 를 직접 채점할 수도 있습니다.

**Q. 커스텀 evaluator 를 만들 수 있나요?**
> 됩니다. LLM-as-judge 방식과 code-based(Lambda) 방식 둘 다 지원합니다. 정확한 키워드 검증이 필요하면 code-based 가 공식 권장입니다.

**Q. 평가 비용이 걱정됩니다.**
> judge 도 LLM 호출이라 토큰 비용이 듭니다. 실무에서는 골든셋을 PR 게이트에만 돌리고, 운영 트래픽은 Online 모드로 **일부만 샘플링**합니다.

---

## 마무리 (15분)

### 말할 것

> "이틀 동안 만든 걸 정리하면 — 근거 기반 답변, 기억, 외부 시스템 연동, 오케스트레이션, 배포, 관측, 품질 자동 검증입니다. **PoC 에서 운영까지 한 바퀴**를 돈 겁니다."

### 실서비스 체크리스트 (`10-실서비스-적용하려면.md`)

특히 강조할 것:

1. **Mock Lambda → 실제 API** — 오늘 Mock 4종은 실제 상품 DB·OMS 로 교체
2. **가드레일** — 의료 표현, 개인정보. 오늘은 프롬프트로만 했지만 실무는 Bedrock Guardrails
3. **inbound 인증** — 오늘 Gateway 는 `NONE`. 프로덕션은 반드시 JWT
4. **IAM 최소 권한** — 워크샵은 넓게 줬습니다
5. **비용 모니터링** — Lab 7 의 토큰 위젯이 출발점

### ⚠️ 리소스 정리 — 반드시 안내

> "**과금이 계속되니 꼭 지우세요.**"

```bash
./scripts/cleanup-all.sh w001 --yes
```

> "스크립트가 마지막에 **실제로 재조회해서** 남은 게 있는지 확인해 줍니다. `⚠ 정리 미완료` 가 나오면 2-3분 후 한 번 더 실행하세요 — 비동기 삭제가 진행 중일 수 있습니다."

> **진행자 주의** — KB 삭제가 벡터 버킷보다 늦으면 `DELETE_UNSUCCESSFUL` 로 고착될 수 있습니다. 스크립트는 순서를 지키지만, 참가자가 콘솔에서 수동 삭제하면 이 함정에 빠집니다. **순서는 KB → 벡터 버킷 → role** 입니다.

### 새 CLI 안내

> "마지막으로 — 실무에 적용하실 때는 새 AgentCore CLI 를 쓰세요. 오늘 배운 개념은 그대로고 명령만 달라집니다."

[새 CLI 이전 가이드](새-cli-이전-가이드.md) 를 안내하고 마칩니다.

---

## 진행자 참고 — Day 2 자주 막히는 지점

| 증상 | 원인 | 조치 |
|---|---|---|
| `agentcore: command not found` | npm 설치 후 터미널 미갱신 | 새 터미널 열기. `node --version` 20+ 확인 |
| `CDK synth failed ... pyproject.toml` | 새 CLI 는 requirements.txt 를 안 읽음 | `src/pyproject.toml` 확인 (저장소에 포함) |
| `Runtime initialization time exceeded` | cold start | 재시도 |
| trace 가 안 보임 | 인덱싱 지연 | 2-5분 대기 |
| "Enable Agent observability" 만 보임 | Transaction Search 미활성 | `setup-day2-cloudshell.sh` 재실행 |
| 대시보드 위젯 6 비어있음 | vended metric 지연 | 최대 60분 |
| 에러 metric 이 0 | **정상** | 위 Lab 7 설명 참고 |
| `No session spans found` | invoke 안 했거나 인덱싱 전 | invoke 후 대기 |
| KB 가 `DELETE_UNSUCCESSFUL` | 벡터 버킷을 먼저 삭제 | 벡터 버킷+인덱스+role 재생성 후 재삭제 |
