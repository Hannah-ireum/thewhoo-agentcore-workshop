# 더후(The History of Whoo) AI 챗봇 워크샵 — Day 2

Day 1 에서 **로컬에서 동작하는 통합 챗봇** 을 만들었다면, Day 2 에서는 이 챗봇을 **실제 서비스처럼 배포하고 운영 품질을 챙기는 단계** 를 다룹니다.

> **코드 블록 표기 안내**
> - ▶ **실행** — 워크샵 진행 중 터미널에 그대로 복사해 실행할 명령
> - 📖 **참고** — 개념 이해를 돕기 위한 예시 코드 또는 자동 생성되는 파일의 형태 (직접 실행하지 않음)
> - 라벨이 없는 일반 코드 블록은 **개념 설명용 스니펫** 입니다. 실행 단계에는 ▶ 라벨이 항상 붙습니다.

## Day 2 학습 목표

* **AgentCore Runtime** 으로 로컬 Python 챗봇을 HTTPS 엔드포인트로 배포 (SigV4 기반 인증)
* **GenAI Observability** 로 단일 trace 의 span 트리를 읽어 호출 흐름·지연 분석
* **CloudWatch Dashboard** 로 호출량·지연·토큰·CPU 의 24시간 KPI 시계열·알람 운영
* **AgentCore Evaluations** 로 골든셋 기반 LLM-as-Judge 답변 품질 평가

## Day 2 Lab 구성

| Lab | 내용 | 주요 도구·리소스 |
|---|---|---|
| [Lab 5](06-lab5-서비스로-배포하기.md) | 배포 — Runtime + HTTPS 엔드포인트 | `agentcore deploy`, `invoke_agent_runtime` |
| [Lab 6](07-lab6-운영-상태-들여다보기.md) | 운영 가시성 — trace + cache | GenAI Observability Dashboard |
| [Lab 7](08-lab7-운영-모니터링-대시보드.md) | 운영 모니터링 — KPI · 알람 · 비용 | CloudWatch Dashboard, CloudWatch Alarms |
| [Lab 8](09-lab8-답변-품질-평가하기.md) | 답변 품질 평가 | AgentCore Evaluations (Built-in evaluator) |
| [실서비스에 적용하려면](10-실서비스-적용하려면.md) | 범위 밖 항목 체크리스트 | 실 DB 연동, 가드레일, 다국어 등 |

## 시작 전 준비

Day 2 의 Lab 5-8 은 **Day 1 에서 만든 인프라(KB / Memory / Gateway / Mock Lambda)** 위에서 동작합니다. 시작 전에 어느 시나리오인지 확인하세요.

> **시작 전 필수** — 진행 전 `git pull` 로 최신 master 를 받아 주세요. Day 1 을 **이전에 만든 계정에서 이어서** 진행하는 경우, 그 사이 반영된 CFN 변경분(KB Retrieve IAM action 등)을 적용하기 위해 `update-stack` 한 번이 필요합니다 (Lab 5 의 "잘 안 될 때" 표 KB Retrieve 행 참고).

### 시나리오 A — Day 1 과 같은 AWS 계정에서 이어서 진행

Day 1 의 인프라가 그대로 살아있으므로 **재생성은 필요 없고 환경변수만 복원**합니다.

```bash
cd ~/thewhoo-agentcore-workshop && git pull
source .venv/bin/activate
pip install -r requirements.txt          # Day 2 신규 의존성 (strands-agents 등) 반영
eval "$(./scripts/print-env.sh w001)"
echo "KB_ID=$KB_ID  MEM=$AGENTCORE_MEMORY_ID  GW=$AGENTCORE_GATEWAY_URL"
```

세 환경변수가 모두 출력되면 [Lab 5](06-lab5-서비스로-배포하기.md) 로 바로 진입합니다.

### 시나리오 B — 새 AWS 계정에서 Day 2 만 시작 (Workshop Studio 재발급 등)

Day 1 에서 만든 인프라가 새 계정에는 없으므로 **인프라만 빠르게 재구성**해야 합니다. Day 1 Lab 의 학습 단계를 다시 거칠 필요는 없고, **자동화 스크립트 두 개**로 처리합니다 (약 20-25분).

> 에이전트의 **Python 코드** 자체(QnA / Recommend / Summary / Orchestrator) 는 git 저장소에 그대로 있으므로 다시 작성할 필요가 없습니다. 사라진 것은 AWS 에 만들었던 **리소스(Memory · Gateway · KB · Lambda)** 뿐이며, 아래 절차로 동일하게 재생성됩니다.

> ⚠️ **순서 중요** — 1단계 (Studio 도메인 트리거) 를 먼저 하지 않고 2단계 CloudShell 부터 실행하면, `grant-sagemaker-permissions.sh` 가 부여할 SageMaker Execution Role 이 아직 없어서 Code Editor 에서 권한 에러가 납니다.

**1단계 — SageMaker Studio 도메인 만들기** (약 5분)

Workshop Studio Console 에서 SageMaker Studio (또는 Studio Classic) 를 한 번 열어주세요. **여기서 Code Editor 를 한 번이라도 열어서 터미널을 띄우면** SageMaker Execution Role 이 자동 생성됩니다.

이 단계가 끝나면 일단 Code Editor 는 열어둔 채로 두고, 다음 2단계로 갑니다.

**2단계 — CloudShell 에서 인프라 + KB 생성** (약 10-15분)

CloudShell(Console 우상단 아이콘)을 열고:

```bash
git clone https://github.com/Hannah-ireum/thewhoo-agentcore-workshop.git
cd thewhoo-agentcore-workshop
./scripts/setup-day2-cloudshell.sh w001
```

이 스크립트가 수행하는 것:

* `grant-sagemaker-permissions.sh` — 1단계에서 만들어진 SageMaker Execution Role 에 워크샵 권한 부여 + Bedrock Claude 모델 Marketplace 자동 활성화
* `onestop.sh` — CFN 스택 (S3, IAM, Cognito, Lambda 4종) + S3 Vectors + Bedrock Knowledge Base + ingestion

**3단계 — Code Editor 에서 새 터미널 + Memory + Gateway 생성** (약 3-5분)

권한 부여가 끝났지만, **1단계에서 열어둔 Code Editor 터미널은 옛 자격증명을 캐시하고 있습니다**. 터미널을 닫고 새로 열어 진행:

```bash
cd ~ && git clone https://github.com/Hannah-ireum/thewhoo-agentcore-workshop.git 2>/dev/null || (cd ~/thewhoo-agentcore-workshop && git pull)
cd ~/thewhoo-agentcore-workshop
./scripts/setup-day2-codeeditor.sh w001
```

이 스크립트가 수행하는 것:

* `setup-python.sh` — Python 3.11 venv + 의존성 설치 (strands-agents, bedrock-agentcore, strands-agents 등)
* `create-memory.py` — AgentCore Memory 4-strategy 생성 (Summary · UserPreference · Semantic · Episodic)
* `create-gateway.py` — AgentCore Gateway + Lambda target 4 등록

**4단계 — 환경변수 export**

```bash
cd ~/thewhoo-agentcore-workshop
source .venv/bin/activate
eval "$(./scripts/print-env.sh w001)"
echo "KB=$KB_ID  MEM=$AGENTCORE_MEMORY_ID  GW=$AGENTCORE_GATEWAY_URL"
```

세 값이 모두 출력되면 [Lab 5](06-lab5-서비스로-배포하기.md) 로 진입합니다.

> **(선택) Lab 2 데모용 프로필 시드** — Lab 2 의 Memory 동작을 시연하려면 시드를 한 번 돌리고 60초 대기합니다.
> ```bash
> cd ~/thewhoo-agentcore-workshop/src && python run_lab2.py seed && sleep 60
> ```

### Code Editor 에서 `AccessDeniedException` 이 뜨는 경우

새 Workshop Studio 계정에서 가장 흔한 시나리오입니다. SageMaker Studio 도메인이 CloudShell 작업 **이후에** 생성되면 `grant-sagemaker-permissions.sh` 가 신규 Execution Role 을 미처 보지 못하고, Code Editor 에서 KB 조회 등 Bedrock API 호출이 권한 부족으로 실패합니다.

증상 예:

```
aws: [ERROR]: An error occurred (AccessDeniedException) when calling the
ListKnowledgeBases operation: User: ...
AmazonSageMaker-ExecutionRole-20260513T230551/SageMaker is not authorized
to perform: bedrock:ListKnowledgeBases
```

복구 절차:

1. **CloudShell 로 이동** (Console 우상단 CloudShell 아이콘)
2. 권한 재부여
   ```bash
   cd ~/thewhoo-agentcore-workshop
   git pull
   ./scripts/grant-sagemaker-permissions.sh
   ```
   스크립트 출력에 새 SageMaker Execution Role 이름이 보이고 `정책 적용 완료` 가 나와야 정상.
3. **Code Editor 의 기존 터미널을 닫고 새 터미널을 엽니다.**
   기존 터미널은 권한 부여 이전에 받아둔 IMDS 자격증명을 캐시하고 있어 새 정책이 반영되지 않습니다. STS 자격증명은 보통 1시간 단위로 갱신되므로 "잠깐 대기" 로는 풀리지 않으니, 셸 프로세스를 새로 띄우는 게 가장 확실합니다.
4. 새 터미널에서 권한 적용 확인
   ```bash
   aws bedrock-agent list-knowledge-bases \
     --region us-east-1 \
     --query "knowledgeBaseSummaries[?starts_with(name, 'thewhoo-kb-')].[name,knowledgeBaseId]" \
     --output table
   ```
   표가 출력되면 정상 — 셋업 재실행
   ```bash
   cd ~/thewhoo-agentcore-workshop && source .venv/bin/activate
   ./scripts/setup-day2-codeeditor.sh w001
   ```

`setup-day2-codeeditor.sh` 자체도 KB 조회 단계에서 `AccessDenied` 인지 KB 미생성인지 자동으로 구분해 안내하므로, 메시지대로 따라가시면 됩니다.

### 어느 쪽인지 확인하는 법

다음 명령으로 KB 가 이미 있는지 확인:

```bash
aws bedrock-agent list-knowledge-bases \
  --region us-east-1 \
  --query "knowledgeBaseSummaries[?starts_with(name, 'thewhoo-kb-')].name" \
  --output text
```

* 결과가 **나오면** 시나리오 A — 환경변수 복원만 진행
* **비어 있으면** 시나리오 B — 패스트트랙 스크립트 실행
* `AccessDeniedException` 이 뜨면 위의 **Code Editor 에서 AccessDeniedException** 절차 진행

---

준비가 끝났다면 [**Lab 5. 실제 서비스처럼 배포하기**](06-lab5-서비스로-배포하기.md) 로 이동하세요.
