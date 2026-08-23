#!/usr/bin/env python3
"""Lab 8 보조 — 골든셋 평가 결과를 HTML 리포트로 시각화.

`run-golden-eval.py --report <path.json>` 이 남긴 JSON 을 읽어
브라우저로 볼 수 있는 한 장짜리 리포트를 만듭니다.

왜 필요한가
  CLI 출력은 스크롤로 흘러가서 20개 시나리오 × evaluator 4종 = 80개 판정을
  한눈에 보기 어렵습니다. 특히 워크샵에서 화면 공유로 설명할 때, 어느
  시나리오가 어느 evaluator 에서 깨졌는지 매트릭스로 보여주는 게 효과적입니다.

Usage:
  python3 scripts/run-golden-eval.py --report /tmp/eval.json
  python3 scripts/eval-report.py /tmp/eval.json -o /tmp/eval.html
  open /tmp/eval.html          # macOS / Code Editor 는 파일 우클릭 → Open Preview
"""
from __future__ import annotations

import argparse
import html
import json
import sys
from pathlib import Path

# evaluator 별 판정 색 (PASS/FAIL/SKIP)
CSS = """
:root { --pass:#0a7c4a; --fail:#c0392b; --skip:#7f8c8d; --bg:#fafafa; --line:#e1e4e8; }
* { box-sizing:border-box; }
body { font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,"Malgun Gothic",sans-serif;
       margin:0; padding:32px; background:var(--bg); color:#24292e; line-height:1.5; }
h1 { font-size:22px; margin:0 0 4px; }
.sub { color:#586069; font-size:13px; margin-bottom:24px; }
.cards { display:flex; gap:12px; flex-wrap:wrap; margin-bottom:28px; }
.card { background:#fff; border:1px solid var(--line); border-radius:8px; padding:14px 18px; min-width:132px; }
.card .n { font-size:26px; font-weight:600; line-height:1.1; }
.card .l { font-size:12px; color:#586069; margin-top:2px; }
.card.ok .n { color:var(--pass); } .card.ng .n { color:var(--fail); }
table { border-collapse:collapse; width:100%; background:#fff; font-size:13px;
        border:1px solid var(--line); border-radius:8px; overflow:hidden; }
th,td { padding:9px 12px; text-align:left; border-bottom:1px solid var(--line); }
th { background:#f6f8fa; font-weight:600; font-size:12px; white-space:nowrap; }
td.sid { font-family:ui-monospace,SFMono-Regular,Menlo,monospace; white-space:nowrap; }
.v { display:inline-block; min-width:52px; padding:2px 8px; border-radius:11px;
     font-size:11px; font-weight:600; text-align:center; }
.v.pass { background:#e6f4ea; color:var(--pass); }
.v.fail { background:#fdecea; color:var(--fail); }
.v.skip { background:#eceff1; color:var(--skip); }
tr.row-fail td.sid { color:var(--fail); font-weight:600; }
details { margin-top:22px; background:#fff; border:1px solid var(--line);
          border-radius:8px; padding:12px 16px; }
summary { cursor:pointer; font-weight:600; font-size:13px; }
pre { background:#f6f8fa; padding:10px; border-radius:6px; overflow-x:auto;
      font-size:12px; white-space:pre-wrap; }
.exp { color:#586069; font-size:12px; margin:6px 0 14px; }
.foot { margin-top:26px; color:#586069; font-size:12px; }
"""


def _verdict_cls(ok: bool | None) -> str:
    if ok is None:
        return "skip"
    return "pass" if ok else "fail"


def _verdict_txt(ok: bool | None) -> str:
    if ok is None:
        return "SKIP"
    return "PASS" if ok else "FAIL"


def build_html(data: dict) -> str:
    scenarios = data.get("scenarios", [])
    evaluators = data.get("evaluators", [])
    runtime = data.get("runtime", "?")
    started = data.get("started_at", "?")

    n_total = len(scenarios)
    n_pass = sum(1 for s in scenarios if s.get("status") == "PASS")
    n_fail = n_total - n_pass

    rows = []
    for s in scenarios:
        sid = html.escape(str(s.get("scenario_id", "?")))
        cls = "" if s.get("status") == "PASS" else "row-fail"
        cells = [f'<td class="sid">{sid}</td>']
        for ev in evaluators:
            r = (s.get("results") or {}).get(ev) or {}
            ok = r.get("passed")
            detail = r.get("summary", "")
            cells.append(
                f'<td><span class="v {_verdict_cls(ok)}">{_verdict_txt(ok)}</span>'
                f'<div class="exp">{html.escape(str(detail))}</div></td>'
            )
        rows.append(f'<tr class="{cls}">' + "".join(cells) + "</tr>")

    ths = "".join(
        f"<th>{html.escape(e.replace('Builtin.', ''))}</th>" for e in evaluators
    )
    gate_txt = json.dumps(data.get("gate", {}), ensure_ascii=False, indent=2, default=str)

    return f"""<!doctype html>
<html lang="ko"><head><meta charset="utf-8">
<title>골든셋 평가 리포트</title><style>{CSS}</style></head><body>
<h1>골든셋 평가 리포트</h1>
<div class="sub">runtime <code>{html.escape(str(runtime))}</code> · 실행 {html.escape(str(started))}</div>

<div class="cards">
  <div class="card"><div class="n">{n_total}</div><div class="l">시나리오</div></div>
  <div class="card ok"><div class="n">{n_pass}</div><div class="l">PASS</div></div>
  <div class="card ng"><div class="n">{n_fail}</div><div class="l">FAIL</div></div>
  <div class="card"><div class="n">{len(evaluators)}</div><div class="l">evaluator</div></div>
</div>

<table><thead><tr><th>시나리오</th>{ths}</tr></thead>
<tbody>{''.join(rows)}</tbody></table>

<details><summary>게이트 기준 (DEFAULT_GATE)</summary>
<pre>{html.escape(gate_txt)}</pre>
<p class="exp">float = 평균 score 하한 · 집합 = 허용 label. 하나라도 못 넘기면 그 시나리오는 FAIL 입니다.</p>
</details>

<div class="foot">
{'✅ 전체 PASS — release ready' if n_fail == 0 else f'❌ {n_fail}개 시나리오 FAIL — 회귀 원인 추적 필요'}
</div>
</body></html>"""


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("json_path", help="run-golden-eval.py --report 로 만든 JSON")
    p.add_argument("-o", "--out", default=None, help="출력 HTML 경로 (기본: <json>.html)")
    a = p.parse_args()

    src = Path(a.json_path)
    if not src.exists():
        sys.exit(
            f"[ERROR] {src} 가 없습니다.\n"
            "        먼저 리포트를 남기세요:\n"
            "          python3 scripts/run-golden-eval.py --report /tmp/eval.json"
        )

    data = json.loads(src.read_text())
    out = Path(a.out) if a.out else src.with_suffix(".html")
    out.write_text(build_html(data), encoding="utf-8")

    n = len(data.get("scenarios", []))
    ok = sum(1 for s in data.get("scenarios", []) if s.get("status") == "PASS")
    print(f"✓ {out}  ({ok}/{n} PASS)")
    print()
    print("보기:")
    print(f"  macOS       open {out}")
    print(f"  Code Editor 파일 우클릭 → Open Preview")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
