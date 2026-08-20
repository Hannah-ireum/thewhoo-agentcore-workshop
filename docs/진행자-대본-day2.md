# 진행자 대본 — Day 2 (서비스 배포·운영)

> **진행자용** 문서입니다. 참가자 배포 자료가 아닙니다.
> 명령과 출력은 실제 AWS 계정에서 완주 검증한 값입니다.

## ⚠️ 진행 전 필수 확인 — CLI 두 가지

AWS 는 2026 년 들어 **새 AgentCore CLI**(`@aws/agentcore`, npm)를 공식 경로로 안내합니다. 현재 Lab 5-8 은 **Python starter-toolkit** 기반이고, 실행하면 이 배너가 뜹니다:

```
⚠️ Recommendation: The Starter Toolkit CLI is no longer supported.
   Please use the AgentCore CLI (@aws/agentcore) ...
```

**진행자가 알아야 할 것:**

| | Python starter-toolkit (현재 Lab) | 새 AgentCore CLI |
|---|---|---|
| 설치 | `pip install bedrock-agentcore-starter-toolkit` | `npm install -g @aws/agentcore` |
| 상태 | **동작함** (2026-08-20 완주 검증) | 공식 권장 |
| 전제 | Python 만 | **Node.js 20+ · AWS CDK · `cdk bootstrap`** + 별도 IAM 정책 |
| 신규 기능 | 안 들어옴 | 여기만 들어옴 |

**워크샵 당일 대응**: 현재 Lab 그대로 진행하세요. 실습은 정상 동작합니다.
배너가 뜨면 `AGENTCORE_SUPPRESS_RECOMMENDATION=1` 로 끌 수 있습니다.

참가자가 "그럼 실무에선 뭘 쓰나요?" 라고 물으면 → **새 CLI 를 쓰라고 답하고**, [새 CLI 이전 가이드](새-cli-이전-가이드.md) 를 안내하세요. 워크샵 개념(Runtime·Memory·Gateway·Observability·Evaluations)은 두 CLI 에서 동일합니다.

---

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
> 3. **관측 자동 연결** — CloudWatch Logs·X-Ray 를 배포가 알아서 붙입니다

### 강조할 개념 — entrypoint 계약

> "Runtime 이 요구하는 건 딱 하나입니다 — `@app.entrypoint` 로 표시된 함수. 이게 HTTP `POST /invocations` 로 매핑됩니다. 우리가 서버 코드를 쓰지 않습니다."

`src/app.py` 를 열어 `session_id` 우선순위를 짚어 주세요:

> "session_id 를 어디서 가져오는지 보세요 — **Runtime 헤더 → payload → 새 UUID** 순입니다. `agentcore invoke --session-id` 가 헤더로 전달되기 때문에 헤더가 최우선입니다."

### 입력할 명령

```bash
cd ~/thewhoo-agentcore-workshop
[ -f .bedrock_agentcore.yaml ] && mv .bedrock_agentcore.yaml .bedrock_agentcore.yaml.bak

ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
agentcore configure \
  --entrypoint src/app.py \
  --name thewhoo_chat \
  --runtime PYTHON_3_12 \
  --deployment-type direct_code_deploy \
  --requirements-file requirements.txt \
  --execution-role "arn:aws:iam::${ACCOUNT_ID}:role/thewhoo-agent-role-w001" \
  --region us-east-1 \
  --non-interactive
```

> **여기서 deprecation 배너가 뜹니다.** 위의 "CLI 두 가지" 절 내용을 이 타이밍에 설명하세요. 참가자가 불안해하지 않도록 "동작합니다, 실무는 새 CLI" 라고 명확히 정리해 주세요.

생성된 yaml 확인:

```bash
head -20 .bedrock_agentcore.yaml
```

`entrypoint` 가 현재 홈 경로이고 `account` 가 본인 계정이면 정상입니다.

**배포:**

```bash
agentcore deploy \
  --env KB_ID=$KB_ID \
  --env AGENTCORE_MEMORY_ID=$AGENTCORE_MEMORY_ID \
  --env AGENTCORE_GATEWAY_URL=$AGENTCORE_GATEWAY_URL \
  --env AWS_REGION=us-east-1
```

3-5분 걸립니다. 이 시간에 "배포가 자동으로 해 주는 것" 을 설명하세요 — 코드 zip 패키징, S3 업로드, Runtime 등록, **CloudWatch Logs·X-Ray·Transaction Search 자동 연결**.

```bash
agentcore status     # Ready / Endpoint DEFAULT (READY) 확인
```

### ⭐ 보여줄 것 — 멀티턴 세션

```bash
SID="lab5-$(date +%s)-$(python3 -c 'import uuid;print(uuid.uuid4())')"
agentcore invoke --session-id "$SID" '{"message":"건성 피부인데 보습크림 추천해줘"}'
agentcore invoke --session-id "$SID" '{"message":"성분도 알려줘"}'
```

**보여줄 것**: 두 번째 호출에서 "성분도" 만 물었는데 **첫 번째 추천 제품의 성분**이 나옵니다.

> "세션이 유지되고 있다는 증거입니다. 같은 `--session-id` 를 줬기 때문이죠. 이게 Lambda 로 하려면 직접 대화 이력을 저장·복원해야 하는 부분입니다."

### ⚠️ 진행자가 미리 알려줄 것

- **session_id 는 33자 이상**이어야 합니다 (Runtime API 제약). 위 명령이 UUID 를 붙이는 이유입니다.
- 첫 invoke 는 **cold start** 로 느리거나 `Runtime initialization time exceeded` 가 날 수 있습니다. 한 번 더 시도하면 됩니다.

### 자주 나오는 질문

**Q. `--env` 를 안 주면 어떻게 되나요?**
> 컨테이너 안에서 `KB_ID` 등을 못 찾아 실패합니다. 배포 시점에 주입해야 합니다.

**Q. 코드를 고치고 다시 배포하려면?**
> `agentcore deploy --auto-update-on-conflict` 에 같은 `--env` 를 다시 붙이면 됩니다.

**Q. `ConflictException ... already exists`**
> 같은 이름 Runtime 이 살아있는데 yaml 이 비어 있는 경우입니다. `--auto-update-on-conflict` 를 추가하세요.

---

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
| 5. Cache Hit Ratio | **40-60% 가 정상** |
| 6. CPU/Memory | **최대 60분 지연** — 오늘 안 보일 수 있음 |
| 7. 에러 로그 tail | **비어있는 게 정상** |

### ⚠️ Cache Hit Ratio 도 미리 설명

> "60% 안 나온다고 문제가 아닙니다. `cache_config` 를 **Orchestrator 에만** 걸었고 Haiku 서브에이전트 3개는 캐시가 없습니다. 위젯은 전 모델 합산이라 구조적으로 40-60% 가 나옵니다."
>
> "판단 기준은 절대값이 아니라 **평소 대비 급락**입니다. 45% 였는데 10% 가 되면 system prompt 가 가변화된 신호죠."

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
agentcore invoke --session-id "$SID" '{"message":"건성 피부에 좋은 보습크림 추천해줘"}'
# trace 인덱싱 2-5분 대기
agentcore eval run --session-id "$SID" \
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
| deprecation 배너 | starter-toolkit 사용 | 정상. `AGENTCORE_SUPPRESS_RECOMMENDATION=1` |
| `Runtime initialization time exceeded` | cold start | 재시도 |
| trace 가 안 보임 | 인덱싱 지연 | 2-5분 대기 |
| "Enable Agent observability" 만 보임 | Transaction Search 미활성 | `setup-day2-cloudshell.sh` 재실행 |
| 대시보드 위젯 6 비어있음 | vended metric 지연 | 최대 60분 |
| 에러 metric 이 0 | **정상** | 위 Lab 7 설명 참고 |
| `No session spans found` | invoke 안 했거나 인덱싱 전 | invoke 후 대기 |
| KB 가 `DELETE_UNSUCCESSFUL` | 벡터 버킷을 먼저 삭제 | 벡터 버킷+인덱스+role 재생성 후 재삭제 |
