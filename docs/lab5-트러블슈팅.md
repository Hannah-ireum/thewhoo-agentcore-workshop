# Lab 5 배포 트러블슈팅

> [Lab 5 — 서비스로 배포하기](06-lab5-서비스로-배포하기.md) 에서 막혔을 때 보는 문서입니다.
> 대부분은 **🚦 관문** 이 먼저 잡아줍니다:
>
> ```bash
> ./scripts/check-agentcore-config.sh
> ```


## `CDK synth failed: Subprocess exited with error 1`

**가장 흔한 원인은 `codeLocation` 입니다.** 위 🚦 관문을 먼저 실행하세요:

```bash
./scripts/check-agentcore-config.sh
```

> **`NodeVersionSupportWarning` 은 원인이 아닙니다.** 2027년 이후 SDK 안내일 뿐이고, `aws-cdk` 는 `node >= 18`, `aws-cdk-lib` 는 `node >= 20` 이라 Code Editor 의 Node 20 으로 충분합니다 (npm registry 확인).

관문을 통과했는데도 실패하면 CDK 를 직접 실행해 상세 오류를 확보하세요:

```bash
cd ~/thewhoo-agentcore-workshop/agentcore/cdk
node dist/bin/cdk.js synth 2>&1 | tail -30
```

| 상세 오류 | 조치 |
|---|---|
| `ENOSPC` / `no space left` | `df -h /home/sagemaker-user` → `rm -rf ~/.cache/uv ~/.npm` |
| `Cannot find module` | `cd agentcore/cdk && rm -rf node_modules && npm install` |
| `no credentials` / `ExpiredToken` | 터미널을 닫고 **새로 열기** (자격증명 캐시 갱신) |
| `is not authorized to perform` | CloudShell 에서 `./scripts/grant-sagemaker-permissions.sh` → 새 터미널 |

## CDK bootstrap 이 실패할 때

```
CDK bootstrap failed: CloudFormationStack object does not hold a stack
CDK bootstrap failed: Failed to create change set ... ContainerAssetsRepository
   🛑 Automatic import of existing resource ... needs a DeletionPolicy of 'Retain'
```

앞선 배포 실패로 **`CDKToolkit` 스택이 `ROLLBACK_FAILED` / `DELETE_FAILED` 로 고착**된 상태입니다. 이 상태에서는 그 스택에 어떤 작업도 되지 않아 **반드시 정리해야** 합니다.

▶ **① 상태 확인**

```bash
aws cloudformation list-stacks --region us-east-1 \
  --stack-status-filter ROLLBACK_FAILED UPDATE_ROLLBACK_FAILED DELETE_FAILED CREATE_FAILED \
  --query 'StackSummaries[].[StackName,StackStatus]' --output table
```

▶ **② `CDKToolkit` 이 나오면 — 리소스를 먼저 비우고 스택 삭제**

```bash
ACC=$(aws sts get-caller-identity --query Account --output text)

# ECR 저장소 (이미지가 남으면 CFN 이 스택을 못 지웁니다)
#   ⚠️ 이름에 계정ID·리전이 붙습니다 — 짧은 이름으로는 삭제되지 않습니다
aws ecr delete-repository --region us-east-1 --force \
  --repository-name "cdk-hnb659fds-container-assets-${ACC}-us-east-1"

# S3 staging 버킷 (버전 관리가 켜져 있어 rm --recursive 만으로는 부족)
BUCKET="cdk-hnb659fds-assets-${ACC}-us-east-1"
aws s3 rm "s3://${BUCKET}" --recursive 2>/dev/null
aws s3api delete-objects --bucket "${BUCKET}" --region us-east-1 \
  --delete "$(aws s3api list-object-versions --bucket "${BUCKET}" --region us-east-1 \
    --query '{Objects: Versions[].{Key:Key,VersionId:VersionId}}' --output json 2>/dev/null)" 2>/dev/null
aws s3api delete-bucket --bucket "${BUCKET}" --region us-east-1 2>/dev/null

# SSM 파라미터
aws ssm delete-parameter --name /cdk-bootstrap/hnb659fds/version --region us-east-1 2>/dev/null

# 스택 삭제
aws cloudformation delete-stack --stack-name CDKToolkit --region us-east-1
aws cloudformation wait stack-delete-complete --stack-name CDKToolkit --region us-east-1 \
  && echo "✅ 삭제 완료"
```

▶ **③ 그래도 `DELETE_FAILED` 면 — 막는 리소스를 남기고 삭제**

```bash
# 막는 리소스 확인
aws cloudformation describe-stack-resources --stack-name CDKToolkit --region us-east-1 \
  --query 'StackResources[?contains(ResourceStatus,`FAILED`)].[LogicalResourceId,ResourceType]' \
  --output table

# 나온 LogicalResourceId 를 그대로 나열 (예시)
aws cloudformation delete-stack --stack-name CDKToolkit --region us-east-1 \
  --retain-resources CdkBootstrapVersion ContainerAssetsRepository
aws cloudformation wait stack-delete-complete --stack-name CDKToolkit --region us-east-1
```

> `--retain-resources` 에는 **위 명령에 실제로 나온 이름만** 넣으세요. 이미 삭제된 리소스를 지정하면 `The specified resources to retain must be in a valid state` 가 납니다.

▶ **④ bootstrap 재생성 후 배포**

```bash
ACC=$(aws sts get-caller-identity --query Account --output text)
cd ~/thewhoo-agentcore-workshop/agentcore/cdk
./node_modules/.bin/cdk bootstrap aws://$ACC/us-east-1

cd ~/thewhoo-agentcore-workshop
eval "$(./scripts/print-env.sh w001)"
./scripts/check-agentcore-config.sh && agentcore deploy -y
```

> `npx cdk` 가 아니라 **`./node_modules/.bin/cdk`** 입니다 — [Lab 5 의 0단계](06-lab5-서비스로-배포하기.md#0단계-cdk-bootstrap-계정당-1회)의 주의를 참고하세요.

> **진행자용** — 이 복구는 시간이 많이 듭니다(10분+). 워크샵 중 여러 참가자가 동시에 겪으면 **Workshop Studio 계정을 새로 발급**하는 편이 빠릅니다. 애초에 🚦 관문을 지키게 하면 이 상황 자체가 생기지 않습니다.


## npm 전역 설치가 안 될 때

`EACCES: permission denied` 또는 `agentcore: command not found` — npm 전역 경로가 root 소유(`/usr/lib`, `/usr/local`)라서 그렇습니다. **Pre-Lab 의 `setup-python.sh` 가 `~/.npm-global` 로 바꿔 두므로 보통은 발생하지 않습니다.**

```bash
mkdir -p ~/.npm-global
npm config set prefix ~/.npm-global
echo 'export PATH="$HOME/.npm-global/bin:$PATH"' >> ~/.bashrc
export PATH="$HOME/.npm-global/bin:$PATH"

npm install -g @aws/agentcore
agentcore --version
```

> **`sudo npm install -g` 는 쓰지 마세요.** root 소유 파일이 생겨 이후 `agentcore update` 나 재설치가 또 막힙니다.

진단:

```bash
npm config get prefix                  # 홈(~) 아래여야 정상
which -a agentcore                     # 비어 있으면 PATH 문제
npm ls -g --depth=0 | grep agentcore   # 설치 여부
```

## 첫 invoke 가 500 — `executionRoleArn` 누락

`executionRoleArn` 을 비우면 CDK 가 role 을 자동 생성하는데, **그 role 의 권한이 이것뿐입니다** (실측):

```
bedrock:InvokeModel / InvokeModelWithResponseStream / CountTokens
bedrock-agentcore:*ConfigurationBundle*   ← Memory 아님, 설정 번들 전용
logs:* / xray:Put*
```

즉 **모델 호출만 됩니다.** 배포는 성공하고 컨테이너도 뜨지만 첫 invoke 에서 죽습니다:

```
Error: Received error (500) from runtime. Please check your CloudWatch logs.

# CloudWatch 로그의 실제 원인
botocore.errorfactory.AccessDeniedException: An error occurred
(AccessDeniedException) when calling the CreateEvent operation
```

**해결** — `python3 scripts/set-agentcore-config.py` 가 워크샵 role 을 자동으로 넣습니다. 다른 role 을 쓰려면 실행 전에:

```bash
export AGENT_ROLE_ARN=arn:aws:iam::<account>:role/<role>
```

## `src/pyproject.toml` 이 없을 때

```
AgentCore CDK synthesis failed: Required project file not found: .../src/pyproject.toml
```

새 CLI 는 `requirements.txt` 를 읽지 않습니다. 저장소에는 포함돼 있으니 `git pull` 로 받으세요. 직접 만들 경우:

```toml
[project]
name = "thewhoo-chat"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "aws-opentelemetry-distro",
    "opentelemetry-exporter-otlp-proto-http",
    "bedrock-agentcore>=1.9.1,<2.0",
    "botocore[crt]>=1.43.0,<2.0",
    "mcp>=1.27.0,<2.0",
    "strands-agents>=1.39.0,<2.0",
    "strands-agents-tools>=0.5.2,<1.0",
    "requests-aws4auth>=1.3.0,<2.0",
    "python-dotenv>=1.0.0,<2.0",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["."]
```

> `botocore` 는 **1.43.0 이상**이어야 합니다 — 그 미만에는 `bedrock-agentcore` 서비스 정의가 없어 `UnknownServiceError` 가 납니다 (실측).

## 증상별 빠른 조회


| 증상 | 원인 / 해결 |
|---|---|
| `CDK synth failed` → `Required project file not found: .../pyproject.toml` | `codeLocation` 아래에 `pyproject.toml` 이 없습니다. 새 CLI 는 `requirements.txt` 를 읽지 않습니다. 2단계의 `pyproject.toml` 을 만드세요 |
| `agentcore: command not found` | ① `npm ls -g --depth=0 \| grep agentcore` 로 설치 여부 확인 → 없으면 재설치. ② 설치돼 있으면 **PATH 문제**: `npm config get prefix` 가 홈(`~`) 아래인지 보고, `export PATH="$(npm config get prefix)/bin:$PATH"` 후 재시도. ③ `node --version` 이 20 이상인지 확인 |
| `npm ERR! code EACCES` / `permission denied ... node_modules` | npm 전역 경로가 root 소유입니다. **sudo 대신** prefix 를 홈으로 바꾸세요: `npm config set prefix ~/.npm-global` + `.bashrc` 에 PATH 추가 (위 1단계 안내). Pre-Lab 의 `setup-python.sh` 가 이미 처리하지만, 건너뛴 경우 발생합니다 |
| `agentcore dev` 가 `Error: spawn xdg-open ENOENT` | Code Editor 는 원격 컨테이너라 브라우저가 없습니다. **`agentcore dev --logs` 를 쓰고 호출은 두 번째 터미널에서** 하세요 (3단계 참고). 웹 inspector 는 이 워크샵에 필수가 아닙니다 |
| `agentcore dev --no-browser` 가 `This command requires an interactive terminal` | 이 플래그는 TTY 가 필요해 Code Editor 에서 열리지 않을 수 있습니다. **`--logs` 를 쓰세요** |
| `agentcore dev "질문"` 이 응답 없음 | 서버가 안 떠 있습니다. 첫 터미널에 `Application startup complete.` 가 보이는지 확인하세요. 또는 `curl -N -X POST http://localhost:8080/invocations -H 'Content-Type: application/json' -d '{"prompt":"..."}'` 로 직접 호출 |
| `agentcore invoke` 가 항상 "메시지를 입력해주세요." | **payload 키 불일치.** 새 CLI 는 `{"prompt": "..."}` 를 보내고 boto3 스크립트는 `{"message": "..."}` 를 보냅니다. `src/app.py` 가 두 키를 모두 읽어야 합니다 (저장소 코드는 이미 반영). 로그로 확인: `agentcore/.cli/logs/invoke/*.log` 의 REQUEST 블록 |
| `Received error (500) from runtime` | 대개 execution role 권한 부족입니다. CloudWatch 로그에서 `AccessDeniedException ... CreateEvent` 가 보이면 위의 **executionRoleArn 필수** 절을 확인하세요 |
| `Invalid length for parameter runtimeSessionId ... greater than or equal to 33` | 세션 ID 가 33자 미만. UUID 를 붙이세요 (위 멀티턴 절 참고) |
| `aws ... Invalid choice: bedrock-agentcore-control` | AWS CLI 가 오래되어 이 서비스를 모릅니다. `print-env.sh` 가 Memory/Gateway 를 못 찾는 것도 같은 원인입니다. CLI v2 를 업데이트하세요 (Code Editor·CloudShell 은 보통 최신) |
| `'uv' is required for Python projects` (create 가 바로 종료) | `uv` 는 CLI 필수 전제조건인데 공식 devguide Prerequisites 에는 빠져 있습니다. `curl -LsSf https://astral.sh/uv/install.sh \| sh` 후 새 터미널을 여세요 |
| `Warning: uv not found — run "uv sync" manually in ...` | `--skip-install` 등으로 사전점검을 건너뛴 경우입니다. 해당 디렉터리에서 `uv sync` 를 직접 실행 |
| `agentcore` 가 실행되는데 옛 명령(`configure` 등)이 보임 | pip 로 설치된 구 starter-toolkit 이 PATH 앞에 있습니다. `which agentcore` 로 확인하고, 구 버전은 `pip uninstall bedrock-agentcore-starter-toolkit` |
| `deploy` 가 `Validate project` 에서 실패 | `agentcore validate` 로 `agentcore.json` 스키마 오류를 확인하세요 |
| 응답에 "Knowledge Base 접근에 일시적인 문제" / `AccessDenied ... bedrock:Retrieve` | Runtime execution role 에 `bedrock:Retrieve` 권한 누락. CDK 자동 생성 role 을 쓰는 경우 `agentcore.json` 의 `additionalPolicies` 로 보강하거나, `executionRoleArn` 에 워크샵 role(`thewhoo-agent-role-<pid>`)을 직접 지정하세요 |
| 응답에 "기술적 오류 / 데이터베이스 시스템 일시 오류" | `envVars` 중 하나(보통 `AGENTCORE_GATEWAY_URL`)가 빈 문자열입니다. `eval "$(./scripts/print-env.sh w001)"` 후 `python3 scripts/set-agentcore-config.py` 로 다시 채우고 재배포 |
| `agentcore invoke` 가 첫 호출에서 `Runtime initialization time exceeded` | cold start 입니다. 한 번 더 호출하면 됩니다 |
| 같은 session 두 번째 invoke 의 `cache_read_input_tokens` 가 0 | 코드 변경(`orchestrator.py` 의 `cache_config`)이 배포에 반영되지 않았을 수 있습니다. `agentcore deploy --diff` 로 변경 감지 여부를 확인하고 재배포 |
| 두 invoke 사이 5분 넘긴 후 cache_read 가 0 | TTL 만료입니다. cache 검증은 두 invoke 를 5분 안에 연속으로 보내야 합니다 |
| `Invalid length for parameter runtimeSessionId, valid min length: 33` | SDK 로 직접 호출할 때 세션 ID 가 33자 미만입니다. `str(uuid.uuid4())` 를 쓰세요. (`agentcore invoke --session-id` 는 CLI 가 알아서 보정합니다) |
| 콘솔에서 리소스를 지웠는데 `deploy` 가 이상해짐 | CDK 스택과 실제 리소스가 어긋난 상태입니다. **정리는 반드시 `agentcore remove all` → `agentcore deploy`** 로 하세요 |
| invoke 시 `ThrottlingException` / `TooManyRequestsException` | Runtime 계정 기본 한도입니다 ([공식 Quotas](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/bedrock-agentcore-limits.html#runtime-service-limits)): 동시 세션(Active session workloads) **5,000**(us-east-1·us-west-2, 그 외 리전 2,500) · 신규 세션 생성 **25 TPS** · 데이터플레인 API 합산 **1,000 TPS**(`InvokeAgentRuntime` 등 공유). 여러 PID 가 계정을 공유하거나 부하를 줄 때 나타납니다. Service Quotas 에서 증가 요청하거나 병렬 요청 수를 줄이세요 |


## `❌ Failed to create venv: unknown error` 가 나면

```
→ Setting up Python environment...
→ Creating virtual environment...
❌ Failed to create venv: unknown error
Server exited with code 1
```

CLI 가 `uv` 의 stderr 를 받지 못해 그대로 출력한 것이라 **메시지 자체로는 원인을 알 수 없습니다.** 실환경에서 확인된 원인은 두 가지입니다:

| 원인 | 확인 | 조치 |
|---|---|---|
| **`codeLocation` 이 없는 경로** (가장 흔함) | `./scripts/check-agentcore-config.sh` | 위 🚦 관문 참고 — `set-agentcore-config.py` 실행 |
| **`uv` 가 PATH 에 없음** | `which uv` | `export PATH="$HOME/.local/bin:$PATH"` |

> `uv` 는 `spawnSync("uv", ...)` 로 호출되므로 **현재 셸의 PATH** 에 있어야 합니다. `.bashrc` 에 등록돼 있어도 그 셸에 반영 안 됐으면 실패합니다.

그 외 원인은 `src` 안에서 직접 실행하면 실제 메시지가 나옵니다:

```bash
cd ~/thewhoo-agentcore-workshop/src && pwd    # 끝이 /src 인지 확인
rm -rf .venv                                   # ⚠️ 반드시 src 안에서
uv venv                                        # 여기 나오는 메시지가 진짜 원인
```

> ⚠️ **경로를 꼭 확인하세요.** 루트에서 `rm -rf .venv` 를 하면 **워크샵 venv 가 지워집니다.** 그 경우 복구: `./scripts/setup-python.sh && source .venv/bin/activate`

| `uv venv` 메시지 | 조치 |
|---|---|
| `No interpreter found for Python 3.1x` | `git pull` (저장소는 `requires-python >=3.11`) |
| `File exists at .venv` | `rm -rf src/.venv` 후 재시도 |
| `No space left` / `ENOSPC` | `df -h /home/sagemaker-user` → `rm -rf ~/.cache/uv ~/.npm` |


## 웹 inspector 를 보려면 (선택 · 고급)

`--logs` 없이 `agentcore dev` 를 실행하면 웹 UI(**8081**)가 뜹니다. 다만 **Day 1 Streamlit 처럼 포트 포워딩만으로는 열리지 않습니다.** 포워딩한 뒤 지구본을 눌러도 이렇게 됩니다 (실측):

```
connect ECONNREFUSED 0.0.0.0:8081
```

**Streamlit 과 무엇이 다른가** — 두 가지가 겹쳐 막습니다:

| | Streamlit (Day 1, 8501) | `agentcore dev` UI (8081) |
|---|---|---|
| 바인드 주소 | `0.0.0.0` (모든 인터페이스) | **`127.0.0.1` 전용** |
| Host 헤더 검사 | 없음 | **allowlist → 403 Forbidden** |

실측 확인:

```
lsof → node  127.0.0.1:8081 (LISTEN)      ← 0.0.0.0 이 아님
Host: localhost:8081                → 200
Host: <무엇이든 다른 값>              → 403 Forbidden
```

`agentcore dev` 에는 바인드 주소를 바꾸는 옵션이 **없습니다** (`agentcore dev --help` 확인 — `--port` 만 있음). 그래서 설정으로는 풀 수 없고, 두 문제를 동시에 없애는 **작은 프록시**가 필요합니다.

▶ **실행 — 터미널 3개**

```bash
# 터미널 ① dev 서버 (끄지 마세요. xdg-open ENOENT 는 정상입니다)
agentcore dev

# 터미널 ② UI 프록시 (0.0.0.0:8092 → 127.0.0.1:8081, Host 헤더 재작성)
python3 scripts/uiproxy.py 8092 8081
```

그다음 **PORTS** 탭 → **Forward a Port** → **`8092`** → **지구본 아이콘**.

> 포워딩할 포트는 **8092 (프록시)** 입니다. 8081 을 포워딩하면 위 `ECONNREFUSED` 가 납니다.

**시연에는 권하지 않습니다.** 터미널 3개가 필요하고 참가자가 헤매기 쉽습니다. 로컬 inspector 는 개발용 도구이고, **운영 관점의 시각적 확인은 Lab 6·7 의 CloudWatch GenAI Observability 가 훨씬 강력합니다** — span 트리로 Orchestrator → 서브에이전트 → Gateway 도구 호출이 전부 보이고 토큰·지연·캐시까지 나옵니다. 3단계는 위의 `agentcore dev "<질문>"` CLI 방식으로 확인하는 것으로 충분합니다.

> `--no-browser` 는 쓰지 마세요 — `Error: This command requires an interactive terminal` 로 실패합니다 (실측).
>
> 포트 구분: `agentcore dev` = 웹 UI **8081** / `agentcore dev --logs` = API **8080**. **둘은 동시에 못 씁니다.**

