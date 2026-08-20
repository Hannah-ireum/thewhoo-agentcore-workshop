# CloudFormation 템플릿 + 부트스트랩 스크립트

참가자가 CloudShell 에서 실행하는 **Pre-Lab 인프라 코드**가 여기 있습니다. 사용자 매뉴얼은 `docs/00-pre-lab-셋업.md` 를 참고하세요. 이 README 는 **파일 구조와 각 스크립트의 역할**만 정리합니다.

## 파일

| 파일 | 역할 |
|---|---|
| `workshop.yaml` | S3 / IAM Role / Cognito 를 프로비저닝하는 CloudFormation 템플릿 |
| `package_lambdas.sh` | 코드 버킷 생성 + Mock Lambda 4종 zip 업로드 |
| `bootstrap_kb.py` | S3 Vectors bucket/index + Bedrock Knowledge Base + ingestion 생성 |

진입점은 `../scripts/onestop.sh` 로, 위 세 개를 순차 호출합니다.

## 리소스 요약

CFN 스택이 만드는 것:
- `DataBucket` — 샘플 상품 JSONL 저장
- `KnowledgeBaseRole` — Bedrock KB 가 S3 / S3 Vectors / Titan 호출에 사용
- `LambdaRole` — Mock Lambda 4종 실행 role
- `AgentRuntimeRole` — Lab 3, 5 에서 Gateway / AgentCore Runtime 이 사용 (Bedrock + Lambda + Logs + XRay + S3 Vectors retrieve 권한)
- `WorkshopUserPool`, `WorkshopUserPoolClient` — Lab 3 Gateway inbound OAuth 용 (선택)

CFN 이 만들지 않는 것 (bootstrap_kb.py 가 처리):
- S3 Vectors bucket/index — CFN native 리소스가 없어 boto3 로 생성
- Bedrock Knowledge Base + data source + ingestion job

## 왜 KB 는 CFN 에 없나요?

Amazon S3 Vectors 는 2025 년 GA 된 서비스로 CloudFormation 리소스 타입이 아직 없습니다. boto3 로 `create_vector_bucket` / `create_index` 를 호출해야 해서 bootstrap_kb.py 스크립트가 담당합니다. 어차피 Bedrock KB 자체도 생성 후 role propagation 대기 등 재시도 로직이 필요하므로 Python 으로 처리하는 게 자연스럽습니다.

## Outputs (참가자가 쓰는 값)

| Key | 용도 |
|---|---|
| `DataBucket` | bootstrap_kb.py 가 샘플 상품 업로드 |
| `KnowledgeBaseRoleArn` | bootstrap_kb.py 가 KB 생성 시 지정 |
| `CognitoUserPoolId`, `CognitoClientId` | Lab 3 Gateway inbound OAuth (선택) |
| `AgentRuntimeRoleArn` | Lab 3 Gateway + Lab 5 Runtime 실행 role |
| `LambdaCodeBucketName`, `LambdaRoleArn` | Mock Lambda 재배포 시 참조 |
