#!/usr/bin/env python3
"""4차 — 문서 간 모순 / 코드-문서 불일치 교차검증."""
import json,re,pathlib,collections
errs=[]; D=pathlib.Path("docs")
alltxt={p.name:p.read_text() for p in D.rglob("*.md")}

# A) 같은 사실을 여러 문서가 다르게 말하는지 (수치 모순)
FACTS={
 "상품 수":            (r'(\d+)\s*개 상품|상품 (\d+)\s*종|(\d+)개 상품', "29"),
 "evaluator Builtin":  (r'Builtin[^\n]{0,12}?(\d{2})\s*종', "18"),
 "ThirdParty":         (r'ThirdParty[^\n]{0,20}?(\d{2})\s*종', "13"),
 "strategy 최대":       (r'strategy[^\n]{0,20}?(\d)\s*개.{0,12}(?:조정 불가|최대)', "6"),
 "세션ID 최소":         (r'(\d{2})\s*자 이상', "33"),
}
for label,(pat,expect) in FACTS.items():
    seen=collections.defaultdict(list)
    for fn,t in alltxt.items():
        for m in re.finditer(pat,t):
            v=next((g for g in m.groups() if g),None)
            if v: seen[v].append(fn)
    if seen and set(seen)!={expect}:
        others={k:sorted(set(v))[:3] for k,v in seen.items() if k!=expect}
        if others: errs.append(("모순",label,f"기대 {expect} / 발견 {others}"))

# B) 코드가 실제로 쓰는 값 vs 문서 서술
code={}
code['model_orch']=re.search(r'model_id\s*=\s*"([^"]+)"',pathlib.Path("src/agents/orchestrator.py").read_text())
code['tools']=re.findall(r'@tool\s*\ndef\s+(\w+)',pathlib.Path("src/agents/orchestrator.py").read_text())
gs=json.load(open("docs/eval/golden-set.json"))
gtools={t for s in gs['scenarios'] for t in (s.get('expected_trajectory') or [])}
missing=gtools-set(code['tools'])
if missing: errs.append(("골든셋",'expected_trajectory',f"코드에 없는 도구: {missing}"))

# C) 문서가 언급한 스크립트 옵션이 실제로 있나
OPT=[("scripts/run-golden-eval.py",["--case","--wait","--report","--evaluator","--no-warmup","--region"]),
     ("scripts/eval-report.py",["-o","--out"]),
     ("scripts/cleanup-all.sh",["--yes"])]
for f,opts in OPT:
    src=pathlib.Path(f).read_text()
    for o in opts:
        if o not in src: errs.append(("옵션",f,f"{o} 미구현인데 문서가 언급"))

# D) requirements.txt 와 src/pyproject.toml 의 의존성 범위 불일치
req={}
for l in pathlib.Path("requirements.txt").read_text().splitlines():
    m=re.match(r'^([a-z0-9\-\[\]]+)\s*([><=!,\.\d]+)?$',l.strip())
    if m and not l.startswith('#'): req[m.group(1).split('[')[0]]=m.group(2) or ''
import tomllib
pj=tomllib.load(open("src/pyproject.toml","rb"))['project']['dependencies']
for d in pj:
    m=re.match(r'^([a-z0-9\-]+)',d); name=m.group(1)
    if name in req:
        rspec=req[name]
        pspec=re.sub(r'^\[[^\]]*\]','',d[len(name):].strip())   # extras([crt]) 제거 후 비교
        if rspec and pspec and rspec!=pspec:
            errs.append(("의존성",name,f"requirements '{rspec}' vs pyproject '{pspec}'"))

# E) starter-toolkit 이 requirements 에서 제거됐는데 문서가 설치를 지시하나
for fn,t in alltxt.items():
    for ln,line in enumerate(t.splitlines(),1):
        if re.search(r'pip install[^\n]*bedrock-agentcore-starter-toolkit',line):
            errs.append(("잔재",f"{fn}:{ln}","제거된 패키지 설치 지시"))

print(f"=== 4차 검사: {len(errs)}건 ===")
for c,l,i in errs: print(f"  [{c}] {l}  {i}")
