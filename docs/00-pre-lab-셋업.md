# Pre-Lab. 인프라 셋업

**소요 시간**: 약 15분 (대부분 대기 시간, 실제 입력은 몇 분 안 됨)

## 무엇을 하는지

세 개 스크립트로 끝납니다.

| # | 위치 | 스크립트 | 역할 |
|---|---|---|---|
| 1 | **CloudShell** | `onestop.sh` | AWS 인프라 + Knowledge Base 생성 |
| 2 | **CloudShell** | `grant-sagemaker-permissions.sh` | Code Editor 에서 Bedrock 호출 가능하게 권한 추가 |
| 3 | **Code Editor** | `setup-python.sh` | Python 3.11 + requirements 설치 |

> **CloudShell 과 Code Editor 를 모두 사용하는 이유**
>
> CloudShell 의 `WSParticipantRole` 은 권한이 넓지만 디스크가 1GB 로 Python 3.11 설치에 부족합니다. Code Editor 는 Python 3.11 이 기본이고 디스크도 5GB 지만 실행 role 이 `AmazonSageMakerFullAccess` 만 가져 Bedrock 호출이 막혀 있습니다. 인프라 배포는 CloudShell 에서, Lab 실행은 Code Editor 에서 하고 권한만 한 번 이어주면 됩니다.

## 사전 요구사항

- AWS Console 로그인 (Workshop Studio 또는 실습자 계정)
- **SageMaker Studio 도메인** 생성 (없으면: Console → SageMaker AI → Studio → Create domain, 기본값으로 ~3분)

> Bedrock Claude 4.x 모델은 Marketplace 경로로 fulfillment 되므로 참가자 계정에서 1회 활성화가 필요합니다. `grant-sagemaker-permissions.sh` 가 WSParticipantRole 로 Haiku 4.5 / Sonnet 4.6 을 자동 호출해 활성화하므로 별도 조치는 필요 없습니다. 만약 자동 활성화가 실패하면 Console → Amazon Bedrock → Model catalog 에서 해당 모델의 Playground 에 한 번만 메시지 보내면 됩니다.

## 1단계. CloudShell 에서 인프라 배포

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

## 2단계. Code Editor 로 이동

1. Console → **SageMaker AI** → **Studio** → 도메인 진입
2. 좌측 **Code Editor** → **Create space** (기본값) → **Open**
3. 좌측 메뉴 → **Terminal → New Terminal**

```bash
cd ~
git clone https://github.com/Hannah-ireum/thewhoo-agentcore-workshop.git
cd thewhoo-agentcore-workshop
./scripts/setup-python.sh

# CloudShell 에서 복사한 값
export PARTICIPANT_ID=w001
export AWS_REGION=us-east-1
export KB_ID=<위에서 기억해둔 값>
```

## 여기까지 됐으면 성공

- `echo $KB_ID` 가 값을 돌려주면 완료
- Lab 0 로 이동해서 `retrieve` 테스트

## 잘 안 될 때

| 증상 | 해결 |
|---|---|
| CloudShell 에서 "SageMaker execution role 로 실행 중" | Code Editor 가 아닌 **CloudShell** 탭에서 실행해야 함 |
| `ResourceExistenceCheck` | 이전 배포 잔해. `aws cloudformation delete-stack --stack-name thewhoo-<pid>` 로 정리 후 재실행 |
| `Knowledge Base 생성 실패 (role propagation)` | IAM 전파 대기. 한 번 더 `./scripts/onestop.sh <pid>` |
| Code Editor 에서 `AccessDeniedException bedrock:InvokeModel` | `grant-sagemaker-permissions.sh` 가 실행됐는지 확인 |
| `setup-python.sh` 실행 안 됨 | `git pull` 로 최신 받고 재실행 |
| `ModuleNotFoundError: No module named 'bedrock_agentcore'` | venv 미활성화. `cd ~/thewhoo-agentcore-workshop && source .venv/bin/activate` |
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
