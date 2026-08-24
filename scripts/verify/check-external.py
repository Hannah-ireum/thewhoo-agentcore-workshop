#!/usr/bin/env python3
"""2차 검증 — 1차가 못 보는 축: quota 수치·URL·코드-문서 일치·명령 실행성."""
import json,re,pathlib,subprocess,urllib.request
errs=[]
D=pathlib.Path("docs")

# A) 공식 quota 원문과 수치 대조
try:
    raw=urllib.request.urlopen("https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/bedrock-agentcore-limits.html",timeout=60).read().decode('utf-8',errors='ignore')
except Exception as e:
    raw=""; errs.append(("FETCH","limits.html",str(e)[:60]))
QUOTA={  # 문서가 주장하는 값 → 원문에 있어야 하는 문자열
 "1,000 TPS":"1,000 TPS", "25 TPS":"25 TPS", "250 MB":"250 MB",
 "2 GB":"2 GB", "750 MB":"750 MB", "15 minutes":"15 minutes",
 "100 MB":"100 MB", "5,000":"5,000", "2,500":"2,500",
 "150":"150", "200,000":"200,000",
}
if raw:
    txt=re.sub(r'<[^>]+>',' ',raw)
    for k,v in QUOTA.items():
        if v.replace(',','') not in txt.replace(',','').replace(' ',''):
            if v not in txt: errs.append(("QUOTA","limits.html",f"원문에 '{v}' 없음"))

# B) 문서의 모든 AWS URL 200 확인
urls=set()
for md in D.rglob("*.md"):
    urls|=set(re.findall(r'https://docs\.aws\.amazon\.com/[^\s)\]]+',md.read_text()))
for u in sorted(urls):
    u=u.rstrip('.,)')
    try:
        r=subprocess.run(['curl','-s','-o','/dev/null','-w','%{http_code} %{url_effective}','-L',u],capture_output=True,text=True,timeout=45)
        parts=r.stdout.strip().split(); code=parts[0]; eff=parts[1] if len(parts)>1 else ''
        if code!='200':
            errs.append(("URL",u,code)); continue
        # AWS 문서는 없는 페이지를 index 로 리다이렉트하며 200 을 돌려준다 →
        # 최종 URL 이 원본과 다르면 그 페이지는 사실상 존재하지 않는다
        if eff.rstrip('/')!=u.rstrip('/'):
            errs.append(("URL-REDIRECT",u,f"→ {eff}"))
    except Exception as e: errs.append(("URL",u,type(e).__name__))

# C) 문서에 인용된 코드 조각이 실제 소스와 일치하나
CODE_CLAIMS=[
 ("docs/06-lab5-서비스로-배포하기.md",'payload.get("message") or payload.get("prompt")',"src/app.py"),
 ("docs/09-lab8-답변-품질-평가하기.md",'"scenario_id": "INFO_Q01"',"docs/eval/golden-set.json"),
]
for doc,frag,src in CODE_CLAIMS:
    d=pathlib.Path(doc).read_text(); sp=pathlib.Path(src).read_text()
    if frag in d:
        key=frag.split('"')[1] if '"' in frag else frag
        if key not in sp: errs.append(("CODE",doc,f"'{key}' 가 {src} 에 없음"))

# D) 문서가 쓰는 환경변수가 print-env.sh 가 실제로 내보내나
pe=pathlib.Path("scripts/print-env.sh").read_text()
EXPORTED=set(re.findall(r'export ([A-Z_]+)=',pe))
for md in D.rglob("*.md"):
    for ln,line in enumerate(md.read_text().splitlines(),1):
        for v in re.findall(r'\$\{?(KB_ID|AGENTCORE_MEMORY_ID|AGENTCORE_GATEWAY_URL|AGENT_RUNTIME_ARN|PARTICIPANT_ID)\}?',line):
            if v not in EXPORTED: errs.append(("ENV",f"{md.name}:{ln}",v))

# E) golden-set 재검증 (SDK 로더)
r=subprocess.run(["/Users/hyewlee/Work/work/shopping-agent/.venv/bin/python","-c",
  "from bedrock_agentcore.evaluation import FileDatasetProvider as F;"
  "d=F('docs/eval/golden-set.json').get_dataset();"
  "assert len(d.scenarios)==20, len(d.scenarios);"
  "assert all(type(s).__name__=='PredefinedScenario' for s in d.scenarios);"
  "print('OK')"],capture_output=True,text=True,timeout=120)
if 'OK' not in r.stdout: errs.append(("GOLDEN","golden-set.json",r.stderr.strip()[:120]))

print(f"=== 2차 검사: {len(errs)}건 ===")
for c,l,i in errs: print(f"  [{c}] {l}  {i}")
print(f"\n(URL {len(urls)}개 / export 변수 {len(EXPORTED)}종)")
