#!/usr/bin/env python3
"""6축 — 지금까지 축이 안 본 영역: Lambda·CFN·골든셋 내용·문서 흐름."""
import json,re,pathlib,subprocess,sys
errs=[]

# A) Lambda 핸들러 ↔ openapi.json 입력 스키마 일치
for d in ['product_search','recommend_products','check_stock','get_promotion']:
    spec=json.load(open(f'lambdas/{d}/openapi.json'))
    code=pathlib.Path(f'lambdas/{d}/app.py').read_text()
    used=set(re.findall(r'params\.get\(\s*["\']([a-z_]+)["\']',code))
    inp=set()
    for _,ops in (spec.get('paths') or {}).items():
        for _,o in ops.items():
            for _,c in ((o.get('requestBody') or {}).get('content') or {}).items():
                inp|=set((c.get('schema',{}).get('properties') or {}).keys())
            for p in o.get('parameters',[]) or []: inp.add(p.get('name'))
    if used-inp: errs.append(("LAMBDA",d,f"스키마에 없는 인자를 읽음: {used-inp}"))

# B) 골든셋의 '핵심 성분/제품명' 을 화이트리스트로 고정해 대조
#    한국어 조사·활용어 때문에 토큰 단위 자동 판정은 불가능합니다
#    (형태소 분석 없이 3가지 방식을 시도했고 모두 오탐 — 결론: 하지 않는다).
#    대신 **골든셋이 사실 주장으로 쓰는 고유명사만 명시 목록**으로 관리하고,
#    그 각각이 상품 데이터에 실재하는지 확인합니다. 목록 갱신은 수동이지만,
#    골든셋에 새 성분·제품을 넣을 때 이 목록에 추가하면 자동으로 검증됩니다.
prods=[json.loads(l) for l in pathlib.Path('lambdas/_shared/beauty_products.jsonl').read_text().splitlines() if l.strip()]
blob=json.dumps(prods,ensure_ascii=False)
gs=json.load(open('docs/eval/golden-set.json'))

FACT_TERMS={  # 골든셋 assertion 이 '사실' 로 주장하는 고유명사
 '천기단','공진단','비첩','자생','환유','화현','장뇌삼','영지','청아교',
 '사향','녹용','침향','더후','궁중',
}
for term in sorted(FACT_TERMS):
    used=any(term in a for sc in gs['scenarios'] for a in sc.get('assertions',[]))
    if used and term not in blob:
        errs.append(("GOLDEN",term,"골든셋이 주장하는데 상품 데이터에 없음"))

# 역방향: 골든셋 assertion 에 FACT_TERMS 밖의 '한자 2자 + 고유명사 패턴' 이
# 새로 등장하면 목록 갱신이 필요하다는 신호 (경고성)
for sc in gs['scenarios']:
    for a in sc.get('assertions',[]):
        pats=[r'(?<![가-힣])([가-힣]{2,4})(?:\s*(?:성분|복합|라인|처방))',
              r'(?<![가-힣])([가-힣]{2,4})\s+(?:크림|에센스|토너|로션|앰플|세럼|수분크림|아이크림)']
        cand=set()
        for pt in pats: cand|=set(re.findall(pt,a))
        SUFFIX_DERIV=('피부용','케어용','전용','겸용','용도')
        for w in cand:
            if w.endswith('용') and w not in blob: continue   # 피부용·케어용 등 파생어
            if w not in FACT_TERMS and w not in blob:
                errs.append(("GOLDEN",sc['scenario_id'],
                             f"'{w}' — 성분/라인 문맥 고유명사인데 데이터·목록에 없음"))

# C) CFN 템플릿이 만드는 리소스명 ↔ 문서·스크립트가 참조하는 이름
cfn=pathlib.Path('infra/cfn/workshop.yaml').read_text()
cfn_names=set(re.findall(r'RoleName:\s*!Sub\s+([\w\-${}]+)',cfn))
cfn_lit={n.replace('${ParticipantId}','w001') for n in cfn_names}
for f in ['scripts/set-agentcore-config.py','docs/06-lab5-서비스로-배포하기.md']:
    t=pathlib.Path(f).read_text()
    for r in re.findall(r'thewhoo-[a-z]+-role-\w+',t):
        if r not in cfn_lit and r.replace('w001','${ParticipantId}') not in cfn_names:
            errs.append(("CFN",f,f"CFN 이 만들지 않는 role 참조: {r}"))

# D) 문서가 지시하는 실행 순서에 빠진 전제가 있나 (Lab N 이 Lab N-1 산출물을 쓰나)
DEPS={'06-lab5':['KB_ID','AGENTCORE_MEMORY_ID','AGENTCORE_GATEWAY_URL'],
      '08-lab7':['AGENT_RUNTIME_ARN'],'09-lab8':['AGENT_RUNTIME_ARN']}
for pre,vars_ in DEPS.items():
    f=next((p for p in pathlib.Path('docs').glob(f'{pre}*')),None)
    if not f: continue
    t=f.read_text()
    if '전제' not in t[:2000] and '준비' not in t[:2000]:
        errs.append(("FLOW",f.name,"상단에 전제 조건 명시 없음"))

# E) 스크립트가 참조하는 파일이 저장소에 있나
for sh in pathlib.Path('scripts').glob('*.sh'):
    t=sh.read_text()
    for ref in re.findall(r'(?:\./)?(scripts/[\w\-.]+\.(?:sh|py))',t):
        if not pathlib.Path(ref).exists(): errs.append(("REF",sh.name,f"없는 파일 참조: {ref}"))

print(f"=== 6차 검사: {len(errs)}건 ===")
for c,l,i in errs[:25]: print(f"  [{c}] {l}  {i}")
if len(errs)>25: print(f"  ... +{len(errs)-25}건")
