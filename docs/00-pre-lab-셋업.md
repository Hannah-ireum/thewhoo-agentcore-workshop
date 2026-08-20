# Pre-Lab. 인프라 셋업

**소요 시간**: 약 15분 (대부분 대기 시간, 실제 입력은 몇 분 안 됨)

## 무엇을 하는지

**순서가 중요합니다.** 아래 4단계를 위에서 아래로 그대로 따라가세요.

| # | 위치 | 할 일 | 역할 |
|---|---|---|---|
| 1 | **Console** | SageMaker Studio 도메인 생성 | Code Editor 사용 + **execution role 자동 생성** |
| 2 | **CloudShell** | `onestop.sh` | AWS 인프라 + Knowledge Base 생성 |
| 3 | **CloudShell** | `grant-sagemaker-permissions.sh` | 1단계에서 만들어진 role 에 Bedrock 권한 추가 |
| 4 | **Code Editor** | `setup-python.sh` | Python 3.11 + requirements 설치 |

> ⚠️ **1단계를 먼저 하지 않으면 3단계가 아무 일도 하지 않고 넘어갑니다.**
> 권한을 부여할 SageMaker execution role 자체가 아직 없기 때문입니다
> (`[알림] 이 계정에 SageMaker execution role 이 없습니다` 출력 후 종료).
> 이 상태로 진행하면 4단계 Code Editor 에서 `AccessDeniedException` 이 납니다.

> **CloudShell 과 Code Editor 를 모두 사용하는 이유 — 같은 스크립트를 두 번 돌리는 게 아닙니다**
>
> 두 환경은 **실행 주체(IAM role)와 디스크 용량**이 달라서 할 수 있는 일이 갈립니다. 겹치는 명령은 `git clone` 뿐이고, 서로 다른 머신이라 각자 코드를 받아야 하기 때문입니다.
>
> | | CloudShell | Code Editor |
> |---|---|---|
> | 실행 주체 | `WSParticipantRole` (Admin 급) | `AmazonSageMaker-ExecutionRole` (제한적) |
> | 디스크 | 1 GB | 5 GB |
> | 여기서 하는 일 | `onestop.sh` (인프라·KB 생성)<br>`grant-sagemaker-permissions.sh` (권한 부여) | `setup-python.sh`<br>Lab 1-4 실행 |
>
> **CloudShell 을 건너뛸 수 없는 이유** — 두 스크립트가 Code Editor 에서는 구조적으로 실패합니다.
> - `onestop.sh` 는 SageMaker role 을 감지하면 **스스로 종료**합니다. IAM·CloudFormation·Lambda 생성 권한이 없어 어차피 실패하기 때문입니다.
> - `grant-sagemaker-permissions.sh` 는 **자기 자신의 role 에 권한을 붙일 수 없습니다**(self-mutation 금지). 반드시 권한이 더 큰 외부 환경에서 해줘야 합니다.
>
> **Code Editor 를 건너뛸 수 없는 이유** — CloudShell 은 디스크가 1 GB 라 Python 3.11 + 의존성(strands-agents 등) 설치가 용량 부족으로 실패합니다.
>
> 정리하면 **인프라 생성과 권한 부여는 CloudShell, 실제 Lab 실행은 Code Editor** 입니다. "권한만 주고 CloudShell 은 건너뛰기" 는 불가능합니다 — 인프라 생성 자체가 CloudShell 에서만 되기 때문입니다.

## 사전 요구사항

- AWS Console 로그인 (Workshop Studio 또는 실습자 계정)

> Bedrock Claude 4.x 모델은 Marketplace 경로로 fulfillment 되므로 참가자 계정에서 1회 활성화가 필요합니다. `grant-sagemaker-permissions.sh` 가 WSParticipantRole 로 Haiku 4.5 / Sonnet 4.6 을 자동 호출해 활성화하므로 별도 조치는 필요 없습니다. 만약 자동 활성화가 실패하면 Console → Amazon Bedrock → Model catalog 에서 해당 모델의 Playground 에 한 번만 메시지 보내면 됩니다.

## 1단계. SageMaker Studio 도메인 만들기 (가장 먼저)

**이 단계를 반드시 먼저 해야 합니다.** 도메인을 만들 때 `AmazonSageMaker-ExecutionRole-<타임스탬프>` 가 **자동으로 생성**되고, 3단계에서 그 role 에 Bedrock 권한을 붙입니다. 도메인이 없으면 붙일 role 이 없어 3단계가 그냥 넘어가고, Lab 실행 단계에서 권한 에러로 막힙니다.

1. Console 상단 검색창에 **SageMaker AI** 입력 → 진입
2. 좌측 메뉴 **Studio** 클릭
3. **Create domain** 클릭
4. **Set up for single user (Quick setup)** 선택 → **Set up**
5. 상태가 **InService** 가 될 때까지 대기 (약 3-5분)

> Quick setup 이면 VPC·IAM 설정을 직접 만질 필요가 없습니다. 기본값 그대로 두세요.

도메인이 만들어졌으면 role 이 생겼는지 확인해 두면 좋습니다 (CloudShell 이나 Console → IAM → Roles 에서 `AmazonSageMaker-ExecutionRole` 검색):

```bash
aws iam list-roles \
  --query "Roles[?starts_with(RoleName, 'AmazonSageMaker-ExecutionRole-')].RoleName" \
  --output text
```

이름이 하나라도 나오면 정상입니다. 아직 비어 있으면 도메인 생성이 끝나지 않은 것이니 조금 더 기다리세요.

**이 단계가 끝나면 Code Editor 는 아직 열지 않고** 다음 2단계로 갑니다. (권한을 먼저 붙여야 Code Editor 터미널이 올바른 자격증명을 캐시합니다.)

## 2단계. CloudShell 에서 인프라 배포

Console 우상단 🔔 옆 **CloudShell 아이콘** → 터미널 준비되면:

```bash
git clone https://github.com/Hannah-ireum/thewhoo-agentcore-workshop.git
cd thewhoo-agentcore-workshop
./scripts/onestop.sh w001   # 워크샵 진행자가 다른 PID 를 안내했으면 그 값으로
```

> **PID 값 안내** — 단일 계정·단독 진행이면 `w001` 그대로 두세요. 변경하면 그 후 모든 명령 (Lab 5 의 `agentcore configure --execution-role` 의 `thewhoo-agent-role-<PID>`, `print-env.sh w001` 등) 에서 같은 값을 일관되게 써야 합니다 — 한 곳만 다르게 쓰면 IAM AccessDenied 원인이 됩니다.

10 분 정도 걸립니다. 마지막에 이런 출력이 나옵니다:

```
 ✓ Pre-Lab 셋업 완료

  export PARTICIPANT_ID=w001
  export AWS_REGION=us-east-1
  export KB_ID=MNUBMHKQMM
```

**KB_ID 값을 기억**해두세요 (Code Editor 에서 씁니다).

이어서 SageMaker role 에 권한 추가:

```bash
./scripts/grant-sagemaker-permissions.sh
```

## 3단계. Code Editor 로 이동

> 여기서 여는 터미널은 **2단계에서 권한을 부여한 뒤에** 열어야 합니다. 터미널은 열릴 때 자격증명을 캐시하므로, 권한 부여 전에 열어둔 터미널은 새 정책을 못 봅니다. 이미 열어두셨다면 그 터미널을 닫고 새로 여세요.

### 3-1. Studio 열기

1. Console 상단 검색창 → **SageMaker AI** → 좌측 **Studio**
2. 1단계에서 만든 도메인의 사용자(user profile) 옆 **Open Studio** 클릭
3. Studio 홈 화면이 새 탭으로 열립니다

### 3-2. Code Editor space 만들기

Studio 안에서 **Code Editor 는 "space" 를 하나 만들어야** 쓸 수 있습니다. space 는 실습용 개발 환경(컨테이너 + EBS 볼륨) 한 벌입니다.

1. Studio 좌측 메뉴 **Applications** 하위의 **Code Editor** 클릭
2. **Create Code Editor space** 버튼 클릭
3. **Name**: `workshop` (자유롭게)
4. **Create space** 클릭
5. space 설정 화면이 나오면 기본값 그대로 두고 **Run space** 클릭
   - Instance type: `ml.t3.medium` (기본) 로 충분합니다
   - Storage: 기본 `5 GB` — Python 3.11 + 의존성 설치에 넉넉합니다
6. 상태가 **Running** 이 되면 (약 2-3분) **Open** 클릭 → VS Code 화면이 열립니다

> space 를 이미 만들어 두셨다면 **Run space → Open** 만 하면 됩니다.
> 상태가 `Stopped` 면 **Run space** 를 먼저 눌러야 Open 이 활성화됩니다.

### 3-3. 터미널 열기

VS Code 화면에서 상단 메뉴 **Terminal → New Terminal** (또는 `Ctrl+``)

터미널이 열리면 아래를 실행합니다.

```bash
cd ~
git clone https://github.com/Hannah-ireum/thewhoo-agentcore-workshop.git
cd thewhoo-agentcore-workshop
./scripts/setup-python.sh
```

### 3-4. venv 활성화 (⚠️ 반드시 필요)

`setup-python.sh` 는 `.venv` 를 **만들어 주지만, 활성화까지 이어지지는 않습니다.** 스크립트는 자기 프로세스 안에서만 활성화하고 종료되므로, 스크립트가 끝나면 터미널은 다시 시스템 Python(`/opt/conda/...`) 을 가리킵니다.

**활성화하지 않으면** 시스템에 미리 깔린 구버전 `strands` 가 잡혀서 Lab 1 부터 이런 에러가 납니다:

```
ImportError: cannot import name 'CacheConfig' from 'strands.models.model'
  (/opt/conda/lib/python3.12/site-packages/strands/models/model.py)
```

경로에 `/opt/conda` 가 보이면 venv 가 활성화되지 않은 것입니다.

```bash
cd ~/thewhoo-agentcore-workshop
source .venv/bin/activate

# 확인 — 반드시 .venv 경로가 나와야 합니다
which python        # → /home/sagemaker-user/thewhoo-agentcore-workshop/.venv/bin/python

# 설치된 버전 + 문제가 됐던 import 가 실제로 되는지 확인
python -c "import importlib.metadata as m; print('strands-agents', m.version('strands-agents'))"
python -c "from strands.models.model import CacheConfig; print('CacheConfig OK')"
```

두 명령이 모두 정상 출력되면 준비 완료입니다.

이어서 환경변수를 설정합니다.

```bash
# CloudShell 에서 복사한 값
export PARTICIPANT_ID=w001
export AWS_REGION=us-east-1
export KB_ID=<위에서 기억해둔 값>
```

> **터미널을 새로 열 때마다** `source .venv/bin/activate` 를 다시 해야 합니다.
> 프롬프트 앞에 `(.venv)` 가 보이면 활성화된 상태입니다.

## 여기까지 됐으면 성공

- [ ] SageMaker Studio 도메인 상태가 **InService**
- [ ] `aws iam list-roles --query "Roles[?starts_with(RoleName, 'AmazonSageMaker-ExecutionRole-')].RoleName" --output text` 가 role 이름을 출력
- [ ] `grant-sagemaker-permissions.sh` 출력에 **`정책 적용 완료`** 가 보임 (`execution role 이 없습니다` 가 아니어야 함)
- [ ] Code Editor space 상태가 **Running** 이고 터미널이 열림
- [ ] `which python` 이 **`.venv/bin/python`** 을 가리킴 (`/opt/conda` 면 venv 미활성화)
- [ ] `echo $KB_ID` 가 값을 돌려줌

## 잘 안 될 때

| 증상 | 해결 |
|---|---|
| CloudShell 에서 "SageMaker execution role 로 실행 중" | Code Editor 가 아닌 **CloudShell** 탭에서 실행해야 함 |
| `ResourceExistenceCheck` | 이전 배포 잔해. `aws cloudformation delete-stack --stack-name thewhoo-<pid>` 로 정리 후 재실행 |
| `Knowledge Base 생성 실패 (role propagation)` | IAM 전파 대기. 한 번 더 `./scripts/onestop.sh <pid>` |
| `grant-sagemaker-permissions.sh` 가 `[알림] 이 계정에 SageMaker execution role 이 없습니다` 만 출력하고 끝남 | **1단계(도메인 생성)를 건너뛴 경우입니다.** 권한을 줄 role 이 아직 없어 스크립트가 아무 일도 하지 않고 종료합니다. 1단계로 돌아가 도메인을 만들고(InService 확인) 이 스크립트를 **다시 실행**하세요. |
| Code Editor 에서 `AccessDeniedException bedrock:InvokeModel` | ① `grant-sagemaker-permissions.sh` 가 `정책 적용 완료` 를 출력했는지 확인. ② 출력이 정상이었다면 **터미널이 옛 자격증명을 캐시**한 경우이니 Code Editor 터미널을 닫고 새로 열어 재시도. ③ 도메인을 CloudShell 작업 **이후에** 만들었다면 CloudShell 에서 `./scripts/grant-sagemaker-permissions.sh` 를 한 번 더 실행 |
| `setup-python.sh` 실행 안 됨 | `git pull` 로 최신 받고 재실행 |
| `ImportError: cannot import name 'CacheConfig' from 'strands.models.model'` | **venv 미활성화**입니다. 에러 경로에 `/opt/conda` 가 보이면 시스템에 깔린 구버전 strands 를 쓰고 있는 것입니다. `cd ~/thewhoo-agentcore-workshop && source .venv/bin/activate` 후 `which python` 으로 `.venv` 경로를 확인하고 재실행하세요. |
| `ModuleNotFoundError: No module named 'bedrock_agentcore'` | 같은 원인(venv 미활성화). `cd ~/thewhoo-agentcore-workshop && source .venv/bin/activate` |
| `print-env.sh` 가 아무것도 출력 안 함 | 최신 스크립트 아님. `git pull` 후 재실행. 기본적으로 `PARTICIPANT_ID`, `AWS_REGION` 은 항상 출력됨 |

## 세션이 끊어졌다면

Code Editor 에서 재접속 후 **두 가지를 반드시** 다시 해야 합니다:

```bash
# 1) venv 활성화 (안 하면 ModuleNotFoundError: No module named 'bedrock_agentcore')
cd ~/thewhoo-agentcore-workshop
source .venv/bin/activate
which python       # .venv/bin/python 이 나와야 정상

# 2) 환경변수 복구
eval "$(./scripts/print-env.sh w001)"
echo "KB_ID=$KB_ID"  # 값이 찍혀야 정상
```

`print-env.sh` 는 **이미 만들어진 리소스만** 출력합니다. Memory 나 Gateway 는 Lab 2/3 에서 만들기 전까지는 비어있는 것이 정상입니다.

더 자세한 내용은 [환경변수 복구 가이드](env-recovery.md) 참고.

CloudShell 은 인프라가 유지되므로 재실행 불필요.

## 다음

[**Lab 0. 데이터 준비하기**](01-lab0-데이터-준비하기.md)
