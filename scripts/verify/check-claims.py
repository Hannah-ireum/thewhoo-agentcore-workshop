#!/usr/bin/env python3
"""문서 claim 자동 교차검증 (CLI 트리·라이브 AWS 캐시 사용)."""
import json,re,pathlib,collections
import sys,glob
ROOT=pathlib.Path(__file__).resolve().parents[2]
_c=glob.glob(str(ROOT/".venv/lib/python3*/site-packages"))
SP=_c[0] if _c else next((p for p in sys.path if p.endswith("site-packages")),"")
errs=[]

# 1) CLI 트리 (캐시 파일 파싱)
txt=pathlib.Path("/tmp/cli_sub.txt").read_text()
VALID=set()
# 캐시 파일은 "###<sub>" 로 구분된 서브명령 help + 마지막에 마커 없는 top-level help
parts=re.split(r'^###([a-z][a-z-]*)$', txt, flags=re.M)
# parts[0] = 첫 마커 앞(비어있음), 이후 (name, body) 쌍, 마지막 body 에 top-level 이 붙어 있음
chunks=[(None,parts[0])]+[(parts[i],parts[i+1]) for i in range(1,len(parts)-1,2)]
for name,body in chunks:
    for m in re.finditer(r'Commands:\n(.*?)(?=\n\n|\nRun without|\nOptions:|\Z)', body or '', re.S):
        for c in re.findall(r'^\s{2}([a-z][a-z\-]*)', m.group(1), re.M):
            VALID.add(c)
            if name: VALID.add(f"{name} {c}")
INTENT={"configure","destroy","eval"}   # 의도된 구 CLI 비교 표기

# 2) Strands 가 실제 내보내는 attribute
tr=pathlib.Path(f"{SP}/strands/telemetry/tracer.py").read_text()
EMIT=set(re.findall(r'"(gen_ai\.[a-z_.]+)"',tr))
ALLOW_CTX=("OTel","표준","Anthropic API","원본","계층","점 표기","bidi")

# 3) 라이브 AWS (캐시)
live=json.loads(pathlib.Path("/tmp/live_aws.json").read_text())

for md in sorted(pathlib.Path("docs").rglob("*.md")):
    for ln,line in enumerate(md.read_text().splitlines(),1):
        loc=f"{md.name}:{ln}"
        for m in re.finditer(r'(?<!aws )(?<!aws bedrock-)\bagentcore ([a-z][a-z\- ]{1,28})',line):
            if re.search(r'aws\s+bedrock-agentcore', line): continue
            t=m.group(1).split(); c1=t[0]; c2=" ".join(t[:2])
            if c1 in INTENT: continue
            if c1 not in VALID:
                errs.append(("CLI",loc,m.group(0).strip())); continue
            # 부모 명령이 서브명령을 갖는 경우, 두 번째 토큰도 검증해야 한다
            subs={v.split(" ",1)[1] for v in VALID if v.startswith(c1+" ")}
            if subs and len(t)>1 and not t[1].startswith("-"):
                if t[1] not in subs:
                    errs.append(("CLI",loc,m.group(0).strip()))
        for a in re.findall(r'gen_ai\.usage\.[a-z_.]+',line):
            a=a.rstrip('.')
            if a in EMIT or any(k in line for k in ALLOW_CTX): continue
            errs.append(("ATTR",loc,a))
        for mm in re.findall(r'`(Invocations|Latency|Sessions|SystemErrors|UserErrors|Throttles|TokenCount|ActiveSessionCount|CPUUsed-vCPUHours|MemoryUsed-GBHours|SessionCount)`',line):
            if mm not in live["metrics"]: errs.append(("METRIC",loc,mm))
        for e in re.findall(r'`(Builtin\.[A-Za-z]+|ThirdParty\.[A-Za-z.]+)`',line):
            if e in live["evaluators"] or "Trajectory*" in line: continue
            errs.append(("EVAL",loc,e))
        for mo in re.findall(r'(?:us\.)?anthropic\.claude[\w.\-:]+',line):
            b=mo[3:] if mo.startswith("us.") else mo
            if b in live["models"] or mo in live["models"]: continue
            if mo.endswith(("...",".")) or "..." in line or "\u2026" in line: continue
            errs.append(("MODEL",loc,mo))

# 4) 문서가 참조하는 저장소 파일/스크립트가 실제로 존재하나
import os
for md in sorted(pathlib.Path("docs").rglob("*.md")):
    for ln,line in enumerate(md.read_text().splitlines(),1):
        for f in re.findall(r'`((?:scripts|src|lambdas|infra|docs)/[\w\-./]+\.(?:py|sh|json|yaml|toml|md))`',line):
            if not pathlib.Path(f).exists():
                errs.append(("FILE",f"{md.name}:{ln}",f))
        for f in re.findall(r'\b(python3? scripts/[\w\-.]+\.py)',line):
            t=f.split()[-1]
            if not pathlib.Path(t).exists(): errs.append(("SCRIPT",f"{md.name}:{ln}",t))
        for f in re.findall(r'\./(scripts/[\w\-.]+\.sh)',line):
            if not pathlib.Path(f).exists(): errs.append(("SCRIPT",f"{md.name}:{ln}",f))

print(f"=== 검사 결과: {len(errs)}건 ===")
for c,l,i in errs: print(f"  [{c}] {l}  {i}")
print(f"\n(기준: CLI {len(VALID)}종 / attr {len(EMIT)}개 / metric {len(live['metrics'])} / eval {len(live['evaluators'])} / model {len(live['models'])})")
