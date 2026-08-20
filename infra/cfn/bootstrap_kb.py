#!/usr/bin/env python3
"""Lab 0 — Bedrock Knowledge Base 부트스트랩 (S3 Vectors 기반).

Workshop Studio 가 배포한 CFN 스택(thewhoo-<pid>)이 만든 S3 DataBucket /
KB Role 위에, S3 Vectors 를 vector store 로 사용하는 Knowledge Base 를
구성합니다.

  1) 샘플 JSONL 을 DataBucket 에 업로드
  2) S3 Vectors bucket + index 생성
  3) Bedrock Knowledge Base 생성 (storage type = S3_VECTORS)
  4) Data source 생성
  5) Ingestion job 시작

S3 Vectors 는 AWS 2025 GA 된 완전 관리형 벡터 스토어로, 조직 수준 SCP
제약에 덜 민감하고 셋업이 단순합니다.

Usage:
  python3 infra/cfn/bootstrap_kb.py <participant-id>
  python3 infra/cfn/bootstrap_kb.py <participant-id> us-east-1
"""

from __future__ import annotations

import os
import sys
import time

import boto3
import botocore.exceptions


TITAN_EMBED_V2 = (
    "arn:aws:bedrock:{region}::foundation-model/amazon.titan-embed-text-v2:0"
)


def _stack_outputs(stack_name: str, region: str) -> dict:
    cfn = boto3.client("cloudformation", region_name=region)
    try:
        outs = cfn.describe_stacks(StackName=stack_name)["Stacks"][0]["Outputs"]
    except botocore.exceptions.ClientError as e:
        raise SystemExit(
            f"CloudFormation 스택 '{stack_name}' 을 찾을 수 없습니다.\n"
            f"Workshop Studio 가 스택을 완료 배포했는지 확인하세요. ({e})"
        )
    return {o["OutputKey"]: o["OutputValue"] for o in outs}


def upload_sample(bucket: str, jsonl_path: str, region: str) -> None:
    """샘플 상품 JSONL 을 상품 1개 = 파일 1개 로 쪼개서 S3 에 업로드.

    KB data source 의 chunkingStrategy=NONE 과 조합해 '상품 단위' 로
    retrieve 되게 하기 위함. 파일 전체를 NONE 으로 넣으면 모든 상품이
    1 chunk 로 묶여 의미 있는 semantic 검색이 어렵습니다.
    """
    print(f"[1/5] 상품별 S3 업로드 → s3://{bucket}/beauty/products/")
    import json as _json
    s3 = boto3.client("s3", region_name=region)

    count = 0
    with open(jsonl_path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            obj = _json.loads(line)
            pid = obj["product_id"]
            key = f"beauty/products/{pid}.json"
            s3.put_object(
                Bucket=bucket,
                Key=key,
                Body=_json.dumps(obj, ensure_ascii=False).encode("utf-8"),
                ContentType="application/json",
            )
            count += 1
    print(f"     ✓ {count}개 상품 업로드 완료")


def create_vector_bucket(name: str, region: str) -> str:
    """S3 Vectors bucket 생성 — 재실행 안전."""
    print(f"[2a/5] S3 Vectors bucket 생성 → {name}")
    s3v = boto3.client("s3vectors", region_name=region)
    try:
        s3v.create_vector_bucket(vectorBucketName=name)
        print("     ✓ 새로 생성됨")
    except botocore.exceptions.ClientError as e:
        if e.response["Error"]["Code"] in ("ConflictException", "BucketAlreadyOwnedByYou"):
            print("     ✓ 이미 존재 (재사용)")
        else:
            raise
    # ARN 조회
    resp = s3v.get_vector_bucket(vectorBucketName=name)
    return resp["vectorBucket"]["vectorBucketArn"]


def create_vector_index(bucket_name: str, index_name: str, region: str) -> str:
    """Vector index 생성 — 재실행 안전."""
    print(f"[2b/5] Vector index 생성 → {bucket_name}/{index_name}")
    s3v = boto3.client("s3vectors", region_name=region)
    try:
        s3v.create_index(
            vectorBucketName=bucket_name,
            indexName=index_name,
            dataType="float32",
            dimension=1024,                   # Titan Embed v2
            distanceMetric="cosine",
            metadataConfiguration={
                "nonFilterableMetadataKeys": ["AMAZON_BEDROCK_TEXT"],
            },
        )
        print("     ✓ 새로 생성됨")
    except botocore.exceptions.ClientError as e:
        if e.response["Error"]["Code"] in ("ConflictException",):
            print("     ✓ 이미 존재 (재사용)")
        else:
            raise
    resp = s3v.get_index(vectorBucketName=bucket_name, indexName=index_name)
    return resp["index"]["indexArn"]


def create_kb(
    name: str,
    kb_role_arn: str,
    vector_bucket_arn: str,
    vector_index_arn: str,
    region: str,
) -> str:
    print(f"[3/5] Knowledge Base 생성 → {name}")
    client = boto3.client("bedrock-agent", region_name=region)

    # 이미 존재하는지 확인 (페이지네이션 처리)
    paginator = client.get_paginator("list_knowledge_bases")
    for page in paginator.paginate():
        for kb in page.get("knowledgeBaseSummaries", []):
            if kb["name"] == name:
                print(f"     ✓ 이미 존재 (재사용): {kb['knowledgeBaseId']}")
                return kb["knowledgeBaseId"]

    # KB 생성은 role propagation 때문에 처음엔 실패할 수 있음 — 재시도
    last_err = None
    for attempt in range(6):
        try:
            resp = client.create_knowledge_base(
                name=name,
                roleArn=kb_role_arn,
                knowledgeBaseConfiguration={
                    "type": "VECTOR",
                    "vectorKnowledgeBaseConfiguration": {
                        "embeddingModelArn": TITAN_EMBED_V2.format(region=region),
                    },
                },
                storageConfiguration={
                    "type": "S3_VECTORS",
                    "s3VectorsConfiguration": {
                        "vectorBucketArn": vector_bucket_arn,
                        "indexArn": vector_index_arn,
                    },
                },
            )
            break
        except botocore.exceptions.ClientError as e:
            last_err = e
            msg = str(e)
            if "AccessDenied" in msg or "not authorized" in msg:
                print(f"     attempt {attempt+1}/6: role propagation 대기 중 — 10초 후 재시도")
                time.sleep(10)
            else:
                raise
    else:
        raise SystemExit(f"KB 생성 실패: {last_err}")

    kb_id = resp["knowledgeBase"]["knowledgeBaseId"]
    for _ in range(60):
        s = client.get_knowledge_base(knowledgeBaseId=kb_id)["knowledgeBase"]["status"]
        if s == "ACTIVE":
            print(f"     ✓ KB_ID = {kb_id}")
            return kb_id
        time.sleep(5)
    raise SystemExit(f"KB 생성이 ACTIVE 로 넘어가지 않음: {kb_id}")


def create_ds_and_ingest(kb_id: str, bucket: str, region: str) -> None:
    print(f"[4/5] Data source 생성 + [5/5] Ingestion job 시작")
    client = boto3.client("bedrock-agent", region_name=region)

    # KB 자체가 ACTIVE 가 될 때까지 대기 — CreateDataSource 가 ConflictException
    # ("The Knowledge Base is not in a valid status") 으로 실패하지 않도록.
    for _ in range(60):
        kb_status = client.get_knowledge_base(knowledgeBaseId=kb_id)["knowledgeBase"]["status"]
        if kb_status == "ACTIVE":
            break
        print(f"     KB 상태 {kb_status} — ACTIVE 대기 (10초)")
        time.sleep(10)
    else:
        raise SystemExit(f"[ERROR] KB {kb_id} 가 10분 내 ACTIVE 로 전환되지 않았습니다.")

    # 이미 존재하는 ACTIVE 한 data source 찾기. DELETING 상태인 것은 스킵
    def _find_active_ds():
        for s in client.list_data_sources(knowledgeBaseId=kb_id).get(
            "dataSourceSummaries", []
        ):
            if s.get("status") == "AVAILABLE":
                return s["dataSourceId"]
        return None

    ds_id = _find_active_ds()

    if ds_id is None:
        # DELETING 상태가 있으면 완료를 기다림
        for _ in range(12):
            all_ds = client.list_data_sources(knowledgeBaseId=kb_id).get(
                "dataSourceSummaries", []
            )
            deleting = [d for d in all_ds if d.get("status") == "DELETING"]
            if not deleting:
                break
            print(f"     기존 data source 삭제 대기 중 (DELETING {len(deleting)}개) — 10초 대기")
            time.sleep(10)

        ds = client.create_data_source(
            knowledgeBaseId=kb_id,
            name="beauty-products",
            dataSourceConfiguration={
                "type": "S3",
                "s3Configuration": {
                    "bucketArn": f"arn:aws:s3:::{bucket}",
                    "inclusionPrefixes": ["beauty/products/"],
                },
            },
            vectorIngestionConfiguration={
                "chunkingConfiguration": {"chunkingStrategy": "NONE"},
            },
        )
        ds_id = ds["dataSource"]["dataSourceId"]
        print(f"     ✓ Data source 생성: {ds_id}")
    else:
        print(f"     ✓ Data source 이미 존재: {ds_id}")

    client.start_ingestion_job(knowledgeBaseId=kb_id, dataSourceId=ds_id)
    print(f"     ✓ Ingestion job 시작 (1~2분 소요)")


def main() -> None:
    if len(sys.argv) < 2:
        print("usage: bootstrap_kb.py <participant-id> [region]", file=sys.stderr)
        sys.exit(1)
    pid = sys.argv[1]
    region = (
        sys.argv[2] if len(sys.argv) > 2
        else os.environ.get("AWS_REGION", "us-east-1")
    )
    stack_name = f"thewhoo-{pid}"

    print(f"Stack: {stack_name}  |  Region: {region}")
    print(f"Caller: {boto3.client('sts', region_name=region).get_caller_identity()['Arn']}")
    print()

    outs = _stack_outputs(stack_name, region)
    bucket = outs["DataBucket"]
    kb_role_arn = outs["KnowledgeBaseRoleArn"]

    here = os.path.dirname(os.path.abspath(__file__))
    jsonl = os.path.abspath(os.path.join(here, "..", "..", "data", "beauty_products.jsonl"))
    if not os.path.exists(jsonl):
        raise SystemExit(f"샘플 데이터가 없습니다: {jsonl}")

    # S3 Vectors 리소스 이름 (CFN 에 포함되지 않으므로 여기서 명명 규칙 결정)
    vec_bucket = f"thewhoo-vec-{pid}"
    vec_index = "beauty-products"

    upload_sample(bucket, jsonl, region)
    vec_bucket_arn = create_vector_bucket(vec_bucket, region)
    vec_index_arn = create_vector_index(vec_bucket, vec_index, region)

    kb_id = create_kb(
        f"thewhoo-kb-{pid}",
        kb_role_arn,
        vec_bucket_arn,
        vec_index_arn,
        region,
    )
    create_ds_and_ingest(kb_id, bucket, region)

    print()
    print("=" * 60)
    print(f"KB_ID={kb_id}")
    print("=" * 60)
    print("다음 명령을 터미널에 복사해 환경변수를 설정하세요:")
    print()
    print(f"  export KB_ID={kb_id}")
    print(f"  export AWS_REGION={region}")
    print()
    print("완료했으면 Lab 1 로 넘어갑니다.")


if __name__ == "__main__":
    main()
