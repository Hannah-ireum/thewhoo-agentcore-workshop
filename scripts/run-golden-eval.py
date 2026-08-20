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
    "Builtin.GoalSuccessRate",          # assertions 를 소비
    "Builtin.ToolSelectionAccuracy",
    "Builtin.TrajectoryInOrderMatch",   # expected_trajectory 를 소비
]

# evaluator 별 PASS 기준.
#  - float: 평균 score 의 하한 (Helpfulness 0~1 스케일)
#  - str:   label 정답 (GoalSuccessRate / ToolSelectionAccuracy)
# evaluator 별 PASS 기준.
#  - float: 평균 value 의 하한 (value 는 0~1 정규화)
#  - set:   허용 label 집합
#
# 주의: GoalSuccessRate 는 ground truth(assertions) 를 넘기면 **다른 prompt template**
# 이 적용되고 verdict 어휘가 Yes/No → SUCCESS/FAILURE 로 바뀝니다. 그래서 label 은
# 집합으로 받고, 판정은 value 기준을 우선합니다.
DEFAULT_GATE = {
    "Builtin.Helpfulness": 0.5,
    "Builtin.GoalSuccessRate": {"Yes", "SUCCESS"},
    "Builtin.ToolSelectionAccuracy": {"Yes", "SUCCESS"},
    "Builtin.TrajectoryInOrderMatch": 1.0,   # 기대 도구가 순서대로 등장하면 1.0
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
    # app.py 의 entrypoint 는 문자열을 반환하므로 응답 본문은 JSON 문자열
    # (예: "안녕하세요...") 입니다. json.loads 결과가 dict 가 아닐 수 있으므로
    # 타입을 확인해야 합니다 — 예전 코드는 .get() 을 바로 불러 AttributeError
    # ('str' object has no attribute 'get') 로 invoke 가 전부 실패했습니다.
    try:
        parsed = json.loads(body)
    except json.JSONDecodeError:
        return body.decode("utf-8", errors="ignore")
    if isinstance(parsed, dict):
        return parsed.get("response") or parsed.get("message") or json.dumps(parsed, ensure_ascii=False)
    return parsed if isinstance(parsed, str) else str(parsed)


def warmup(bac, runtime_arn: str) -> None:
    """첫 시나리오 cold-start 흡수용. 실패해도 무시."""
    sid = f"warmup-{uuid.uuid4()}-{uuid.uuid4()}"
    try:
        invoke_runtime(bac, runtime_arn, sid, "안녕")
        print("[warmup] ✓ 컨테이너 ready")
    except Exception as e:
        print(f"[warmup] ⚠ 실패 ({e}) — 그래도 계속 진행")


def build_reference_inputs(scenario: dict, session_id: str) -> list[dict]:
    """골든셋 시나리오 → Evaluate API 의 evaluationReferenceInputs 로 변환.

    공식 스펙 (botocore bedrock-agentcore / ground-truth-evaluations.html):
      evaluationReferenceInputs=[{
          "context": {"spanContext": {"sessionId": ...}},   # context 는 필수
          "assertions": [{"text": ...}],
          "expectedTrajectory": {"toolNames": [...]},
          "expectedResponse": {"text": ...},
      }]

    ground truth 필드의 **scope 가 다릅니다** (공식 문서 표):
      assertions / expectedTrajectory → Session level (세션당 1건)
      expectedResponse               → Trace level  (trace 를 지정해야 정확)

    evaluator 가 안 쓰는 필드는 무시되고 응답의 ignoredReferenceInputFields
    에 보고됩니다 — 에러가 아니라 정상 동작입니다. 그래서 한 번 만든
    reference input 을 여러 evaluator 에 그대로 재사용할 수 있습니다.

    ground truth 가 하나도 없으면 빈 리스트를 반환합니다 (그 경우 호출 시 생략).
    """
    ref: dict = {"context": {"spanContext": {"sessionId": session_id}}}

    if scenario.get("assertions"):
        ref["assertions"] = [{"text": a} for a in scenario["assertions"]]

    if scenario.get("expected_trajectory"):
        ref["expectedTrajectory"] = {"toolNames": scenario["expected_trajectory"]}

    # expectedResponse 는 **trace level** 입니다. traceId 를 주지 않으면 공식
    # 문서 기준 "세션의 마지막 trace" 에 매칭됩니다 (turn 0 → trace 0 이 아닙니다).
    # 현재 골든셋은 전부 단일 턴 + expected_response 미사용(0건)이라 이 분기는
    # 타지 않습니다. 여러 턴에 각각 정답을 주려면 turn 별 traceId 를 알아내
    # reference input 을 여러 개로 나눠야 하므로, 그때 이 함수를 확장하세요.
    expected = [t.get("expected_response") for t in scenario.get("turns", [])]
    expected = [e for e in expected if e]
    if expected:
        if len(expected) > 1:
            print(f"  ⚠ {scenario['scenario_id']}: expected_response 가 {len(expected)}개 —"
                  " traceId 없이는 마지막 trace 에만 적용됩니다. 첫 값만 사용합니다.")
        ref["expectedResponse"] = {"text": expected[0]}

    # context 외에 아무 것도 없으면 굳이 넘기지 않습니다.
    return [ref] if len(ref) > 1 else []


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
    allowed = gate if isinstance(gate, (set, frozenset)) else {gate}
    ok = all(label in allowed for label in labels)
    marker = "✅ PASS" if ok else "❌ FAIL"
    summary = labels[0] if len(labels) == 1 else labels
    expected = " 또는 ".join(sorted(allowed))
    return ok, f"  · {evaluator_id}: {summary} (expected {expected}) {marker}"


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
    invoke_failed: set[str] = set()   # invoke 가 실패한 scenario_id

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
                # invoke 가 실패한 시나리오는 평가 대상에서 제외해야 합니다.
                # 기록하지 않으면 이 세션의 span 이 없는 상태로 evaluate 로 넘어가고,
                # 최악의 경우 다른 세션 span 을 주워 잘못된 PASS 가 납니다.
                invoke_failed.add(sid)
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
        if sid in invoke_failed:
            print(f"  ✗ invoke 가 실패한 시나리오 — 평가 생략, FAIL 처리")
            summary.append((sid, "INVOKE_FAILED"))
            overall_pass = False
            print()
            continue

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

        # 골든셋의 ground truth (assertions / expected_trajectory / expected_response) 를
        # evaluationReferenceInputs 로 넘겨야 evaluator 가 실제로 사용합니다.
        # 이걸 빼면 GoalSuccessRate 등이 ground-truth-free 모드로 돌아 골든셋과
        # 무관한 것을 채점합니다 (공식 ground-truth-evaluations.html 참고).
        reference_inputs = build_reference_inputs(scenario, session_id)

        case_pass = True
        for evaluator_id in evaluators:
            try:
                kwargs = {
                    "evaluatorId": evaluator_id,
                    "evaluationInput": {"sessionSpans": spans},
                }
                if reference_inputs:
                    kwargs["evaluationReferenceInputs"] = reference_inputs
                resp = bac.evaluate(**kwargs)
            except Exception as e:
                print(f"  ❌ {evaluator_id}: API 실패 — {e}")
                case_pass = False
                continue

            # evaluationResults 는 evaluator level 에 따라 건수가 달라집니다:
            #   - Session level (GoalSuccessRate / Trajectory*) → 세션당 1건
            #   - Trace level   (Correctness / Helpfulness)     → trace 당 1건
            # 특정 trace 만 채점하려면 evaluationTarget={"traceIds": [...]} 를 씁니다.
            # (공식 quota: span 1,000/on-demand 평가, payload 15MB)
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
