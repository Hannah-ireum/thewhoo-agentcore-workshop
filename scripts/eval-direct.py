#!/usr/bin/env python3
"""Lab 8 — boto3 직접 호출로 evaluation 실행 (공식 문서 패턴).

agentcore eval run 이 'No spans found' 로 막힐 때 우회 경로.
fetch_spans_from_cloudwatch + Evaluate API 흐름 그대로 사용.

Usage:
  python3 scripts/eval-direct.py --session-id eval-XXXX
  python3 scripts/eval-direct.py --session-id eval-XXXX --evaluator Builtin.Helpfulness
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta, timezone

import boto3

from bedrock_agentcore.evaluation import fetch_spans_from_cloudwatch


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--session-id", required=True)
    p.add_argument("--region", default="us-east-1")
    p.add_argument("--minutes", type=int, default=60, help="lookback minutes (기본 60)")
    p.add_argument("--evaluator", action="append", default=[],
                   help="evaluator id (반복 가능). 기본: 3 builtin")
    args = p.parse_args()

    if not args.evaluator:
        args.evaluator = [
            "Builtin.Helpfulness",
            "Builtin.GoalSuccessRate",
            "Builtin.ToolSelectionAccuracy",
        ]

    region = args.region

    # Runtime ID 자동 탐지
    ac = boto3.client("bedrock-agentcore-control", region_name=region)
    items = ac.list_agent_runtimes().get("agentRuntimes", [])
    rt = next((r for r in items if "thewhoo" in r.get("agentRuntimeName", "").lower()), None)
    if not rt:
        sys.exit("[ERROR] thewhoo 계열 Runtime 을 찾지 못했습니다.")
    agent_id = rt["agentRuntimeId"]
    runtime_log_group = f"/aws/bedrock-agentcore/runtimes/{agent_id}-DEFAULT"

    print(f"agent_id    : {agent_id}")
    print(f"session_id  : {args.session_id}")
    print(f"lookback    : {args.minutes} minutes")
    print()

    # span 수집
    start_time = datetime.now(timezone.utc) - timedelta(minutes=args.minutes)
    print(f"[1/2] span 수집 (runtime log group + aws/spans) ...")
    spans = fetch_spans_from_cloudwatch(
        session_id=args.session_id,
        event_log_group=runtime_log_group,
        start_time=start_time,
        region=region,
    )
    print(f"      {len(spans)} spans 수집됨")

    if not spans:
        sys.exit(
            f"\n[ERROR] session_id '{args.session_id}' 의 span 이 0건입니다.\n"
            f"가능한 원인:\n"
            f"  · 그 session_id 로 invoke 한 적이 없음 (오타?)\n"
            f"  · invoke 후 인덱싱 5~10분 미경과\n"
            f"  · agentcore invoke 시 --session-id <ID> 옵션을 안 줬을 가능성\n"
        )

    # Evaluate
    bac = boto3.client("bedrock-agentcore", region_name=region)
    print(f"\n[2/2] Evaluate API 호출 (총 {len(spans)} spans)")

    for evaluator_id in args.evaluator:
        print(f"\n  ── {evaluator_id} ──")
        try:
            resp = bac.evaluate(
                evaluatorId=evaluator_id,
                evaluationInput={"sessionSpans": spans},
            )
        except Exception as e:
            print(f"  ❌ API 실패: {e}")
            continue

        results = resp.get("evaluationResults", [])
        if not results:
            print("  (결과 없음)")
            continue

        for r in results:
            if "errorCode" in r:
                print(f"  ❌ {r['errorCode']}: {r.get('errorMessage', '')[:120]}")
                continue
            ctx = r.get("context", {}).get("spanContext", {})
            target = ctx.get("traceId") or ctx.get("spanId") or ctx.get("sessionId") or "-"
            value = r.get("value")
            label = r.get("label", "")
            score = f"{value:.2f}" if isinstance(value, (int, float)) else str(value)
            print(f"  ✅ {target[:24]:<24} {score:>6}  {label}")
            ex = (r.get("explanation") or "").strip()
            if ex:
                short = ex[:160] + ("..." if len(ex) > 160 else "")
                print(f"     → {short}")


if __name__ == "__main__":
    main()
