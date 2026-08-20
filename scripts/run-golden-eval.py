#!/usr/bin/env python3
"""Lab 8 — 골든셋 전체를 순차 invoke → CloudWatch span 수집 → evaluate 로 실행 + 회귀 판정.

SDK 1.9.1 실제 API 기반:
  - invoke: boto3 bedrock-agentcore InvokeAgentRuntime
  - span 수집: bedrock_agentcore.evaluation.fetch_spans_from_cloudwatch
  - evaluate: boto3 bedrock-agentcore Evaluate

흐름:
  1) 골든셋 로드 (docs/eval/golden-set.json)
  2) Runtime ARN 자동 탐지
  3) warmup invoke (cold-start 흡수)
  4) 시나리오별 invoke → session_id 기록
  5) span 인덱싱 대기 (기본 300초)
  6) 시나리오별 span 수집 → evaluate API 호출
  7) DEFAULT_GATE 와 비교해 PASS / FAIL 판정
  8) FAIL 이 하나라도 있으면 exit 1 (CI 게이트)

Usage:
  python3 scripts/run-golden-eval.py
  python3 scripts/run-golden-eval.py --case INFO_Q01
  python3 scripts/run-golden-eval.py --wait 600
  python3 scripts/run-golden-eval.py --no-warmup
  python3 scripts/run-golden-eval.py --evaluator Builtin.Helpfulness

전제:
  - Lab 5 까지 끝나서 Runtime 이 배포됨
  - bedrock-agentcore:Evaluate / InvokeAgentRuntime 권한 있는 IAM
  - bedrock-agentcore SDK >= 1.9.1
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import boto3

from bedrock_agentcore.evaluation import fetch_spans_from_cloudwatch


REPO_ROOT = Path(__file__).resolve().parent.parent
GOLDEN_SET_PATH = REPO_ROOT / "docs" / "eval" / "golden-set.json"

DEFAULT_EVALUATORS = [
    "Builtin.Helpfulness",
    "Builtin.GoalSuccessRate",
    "Builtin.ToolSelectionAccuracy",
]

# evaluator 별 PASS 기준.
#  - float: 평균 score 의 하한 (Helpfulness 0~1 스케일)
#  - str:   label 정답 (GoalSuccessRate / ToolSelectionAccuracy)
DEFAULT_GATE = {
    "Builtin.Helpfulness": 0.5,
    "Builtin.GoalSuccessRate": "Yes",
    "Builtin.ToolSelectionAccuracy": "Yes",
}


def resolve_runtime(region: str) -> tuple[str, str]:
    """thewhoo 계열 Runtime 의 (runtime_id, runtime_arn) 반환."""
    ac = boto3.client("bedrock-agentcore-control", region_name=region)
    items = ac.list_agent_runtimes().get("agentRuntimes", []) or []
    for r in items:
        if "thewhoo" in r.get("agentRuntimeName", "").lower():
            runtime_id = r["agentRuntimeId"]
            account = boto3.client("sts", region_name=region).get_caller_identity()["Account"]
            arn = f"arn:aws:bedrock-agentcore:{region}:{account}:runtime/{runtime_id}"
            return runtime_id, arn
    sys.exit("[ERROR] thewhoo 계열 Runtime 을 찾지 못했습니다.")


def invoke_runtime(bac, runtime_arn: str, session_id: str, message: str) -> str:
    """Runtime 을 한 번 invoke 하고 응답 문자열을 반환합니다."""
    if len(session_id) < 33:
        session_id = f"{session_id}-{uuid.uuid4()}"
    resp = bac.invoke_agent_runtime(
        agentRuntimeArn=runtime_arn,
        runtimeSessionId=session_id,
        payload=json.dumps({"message": message}),
    )
    body = resp["response"].read()
    try:
        return json.loads(body).get("response", body.decode("utf-8", errors="ignore"))
    except json.JSONDecodeError:
        return body.decode("utf-8", errors="ignore")


def warmup(bac, runtime_arn: str) -> None:
    """첫 시나리오 cold-start 흡수용. 실패해도 무시."""
    sid = f"warmup-{uuid.uuid4()}-{uuid.uuid4()}"
    try:
        invoke_runtime(bac, runtime_arn, sid, "안녕")
        print("[warmup] ✓ 컨테이너 ready")
    except Exception as e:
        print(f"[warmup] ⚠ 실패 ({e}) — 그래도 계속 진행")


def gate_check(evaluator_id: str, results: list[dict], gate) -> tuple[bool, str]:
    """evaluator 결과 리스트를 gate 기준과 비교. (pass, summary_line) 반환."""
    valid = [r for r in results if "errorCode" not in r]
    if not valid:
        return True, f"  · {evaluator_id}: 결과 없음 (skip)"

    if gate is None:
        return True, f"  · {evaluator_id}: {[r.get('label') for r in valid]} (gate 없음)"

    if isinstance(gate, (int, float)):
        scores = [r.get("value") for r in valid if isinstance(r.get("value"), (int, float))]
        if not scores:
            return True, f"  · {evaluator_id}: 숫자 score 없음 (skip)"
        avg = sum(scores) / len(scores)
        ok = avg >= gate
        marker = "✅ PASS" if ok else "❌ FAIL"
        return ok, f"  · {evaluator_id}: 평균 {avg:.2f} (gate {gate}) {marker}"

    labels = [r.get("label") for r in valid]
    ok = all(label == gate for label in labels)
    marker = "✅ PASS" if ok else "❌ FAIL"
    summary = labels[0] if len(labels) == 1 else labels
    return ok, f"  · {evaluator_id}: {summary} (expected {gate}) {marker}"


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--case", help="특정 scenario_id 만 실행")
    p.add_argument("--wait", type=int, default=300, help="span 인덱싱 대기 (초, 기본 300)")
    p.add_argument("--region", default=os.environ.get("AWS_REGION", "us-east-1"))
    p.add_argument("--no-warmup", action="store_true")
    p.add_argument("--evaluator", action="append", default=None,
                   help="evaluator id (반복 가능). 미지정 시 기본 3종.")
    args = p.parse_args()

    evaluators = args.evaluator or DEFAULT_EVALUATORS

    # 1) 골든셋 로드
    with open(GOLDEN_SET_PATH) as f:
        golden = json.load(f)
    scenarios = golden["scenarios"]
    if args.case:
        scenarios = [s for s in scenarios if s["scenario_id"] == args.case]
        if not scenarios:
            sys.exit(f"[ERROR] scenario '{args.case}' 가 골든셋에 없습니다.")

    # 2) Runtime 탐지
    runtime_id, runtime_arn = resolve_runtime(args.region)
    runtime_log_group = f"/aws/bedrock-agentcore/runtimes/{runtime_id}-DEFAULT"
    bac = boto3.client("bedrock-agentcore", region_name=args.region)

    print(f"runtime    : {runtime_id}")
    print(f"scenarios  : {len(scenarios)}")
    print(f"evaluators : {evaluators}")
    print()

    # 3) Warmup
    if not args.no_warmup:
        warmup(bac, runtime_arn)
        print()

    # 4) 시나리오별 invoke — 시작 시각 기록 (span 수집 범위용)
    invoke_start = datetime.now(timezone.utc) - timedelta(seconds=30)
    session_map: dict[str, str] = {}  # scenario_id -> session_id

    print("[run] 시나리오 invoke 시작")
    for scenario in scenarios:
        sid = scenario["scenario_id"]
        session_id = f"golden-{sid.lower()}-{uuid.uuid4()}"
        session_map[sid] = session_id

        for turn in scenario.get("turns", []):
            msg = turn.get("input", "")
            try:
                invoke_runtime(bac, runtime_arn, session_id, msg)
                print(f"  ✓ {sid}  \"{msg[:40]}\"")
            except Exception as e:
                print(f"  ✗ {sid}  invoke 실패: {e}")
        time.sleep(1)  # 연속 invoke 간 짧은 간격

    print()

    # 5) span 인덱싱 대기
    print(f"[wait] span 인덱싱 대기 {args.wait}초 ...")
    time.sleep(args.wait)
    print()

    # 6) 시나리오별 evaluate
    overall_pass = True
    summary: list[tuple[str, str]] = []

    for scenario in scenarios:
        sid = scenario["scenario_id"]
        session_id = session_map[sid]
        print(f"[evaluate] {sid}")

        # span 수집
        spans = fetch_spans_from_cloudwatch(
            session_id=session_id,
            event_log_group=runtime_log_group,
            start_time=invoke_start,
            region=args.region,
        )

        if not spans:
            print(f"  ⚠ span 없음 — 인덱싱이 아직 안 됐거나 invoke 실패. skip.")
            summary.append((sid, "NO_SPANS"))
            overall_pass = False
            print()
            continue

        case_pass = True
        for evaluator_id in evaluators:
            try:
                resp = bac.evaluate(
                    evaluatorId=evaluator_id,
                    evaluationInput={"sessionSpans": spans},
                )
            except Exception as e:
                print(f"  ❌ {evaluator_id}: API 실패 — {e}")
                case_pass = False
                continue

            results = resp.get("evaluationResults", [])
            gate = DEFAULT_GATE.get(evaluator_id)
            ok, line = gate_check(evaluator_id, results, gate)
            print(line)
            if not ok:
                case_pass = False

        summary.append((sid, "PASS" if case_pass else "FAIL"))
        if not case_pass:
            overall_pass = False
        print()

    # 7) 요약
    print("=" * 67)
    print(f" 골든셋 평가 요약 — {len(summary)} scenarios")
    print("=" * 67)
    for sid, status in summary:
        marker = {"PASS": "✅", "FAIL": "❌"}.get(status, "⚠️")
        print(f"  {marker} {sid:<25} {status}")
    print()

    if overall_pass:
        print("✅ 전체 PASS — release ready")
        return 0
    print("❌ 일부 FAIL — explanation 확인 후 회귀 원인 추적")
    return 1


if __name__ == "__main__":
    sys.exit(main())
