# 진행자 대본 — Day 1 (통합 챗봇 만들기)

> 이 문서는 **진행자용**입니다. 참가자 배포 자료가 아닙니다.
> 무대에서 **읽을 문장**은 [발표 대본](발표-대본-day1.md) 에 있습니다. 이 문서는 운영 정보(타임라인·명령·함정·Q&A)입니다.
> 각 Lab 마다 **말할 것 / 입력할 명령 / 보여줄 것 / 자주 나오는 질문** 순서로 정리했습니다.
> 명령과 출력은 실제 AWS 계정에서 완주 검증한 값입니다.

## 타임라인 (총 약 4시간 30분 + 휴식)

| 시각 | 내용 | 소요 |
|---|---|---|
| 0:00 | 오프닝 · 아키텍처 소개 | 15분 |
| 0:15 | **Pre-Lab** 인프라 셋업 | 30분 |
| 0:45 | **Lab 0** 데이터 → Knowledge Base | 20분 |
| 1:05 | **Lab 1** RAG 챗봇 | 40분 |
| 1:45 | ☕ 휴식 | 10분 |
| 1:55 | **Lab 2** Memory | 45분 |
| 2:40 | **Lab 3** Gateway + MCP | 55분 |
| 3:35 | ☕ 휴식 | 10분 |
| 3:45 | **Lab 4** Orchestrator | 40분 |
| 4:25 | 마무리 · Day 2 예고 | 10분 |

> **지연 대응 우선순위** — 시간이 밀리면 ① Lab 3 의 Semantic Tool Search 절을 설명만 하고 넘기기 ② Lab 2 의 Episodic 실습을 데모로 대체 ③ Lab 4 를 진행자 시연으로 전환. **Lab 1 은 절대 줄이지 마세요** (이후 전부의 토대).

---

## 오프닝 (15분)

### 말할 것

> "오늘 만드는 건 더후 상품을 상담하는 AI 챗봇입니다. 그런데 단순히 '질문하면 답하는' 봇이 아닙니다. 세 가지를 할 수 있어야 합니다."
>
> 1. **근거 기반 답변** — 상품 성분·사용법을 지어내지 않고 실제 데이터에서 찾아 답한다
> 2. **맥락 기억** — "저번에 추천한 그거"를 이해한다
> 3. **외부 시스템 호출** — 재고·프로모션처럼 실시간으로 바뀌는 값을 API 로 가져온다
>
> "이 세 가지가 각각 Lab 1, Lab 2, Lab 3 입니다. Lab 4 에서 하나로 묶습니다."

### 보여줄 것

`docs/assets/diagrams/final.svg` 를 띄워 놓고 **오늘 만들 전체 그림**을 먼저 보여줍니다. 지금은 이해 안 돼도 괜찮다고 말해 주세요 — Lab 이 끝날 때마다 이 그림의 한 조각이 채워진다고 안내합니다.

### 강조할 개념 — "무엇을 어디에 저장하는가"

칠판이나 슬라이드에 이 표를 그려 주세요. 오늘 워크샵의 **핵심 설계 판단**입니다.

| 정보 성격 | 예시 | 저장 위치 | 어느 Lab |
|---|---|---|---|
| **정적** | 성분, 사용법, 가격 | Knowledge Base | Lab 0-1 |
| **실시간** | 재고, 프로모션 | 외부 API → Gateway | Lab 3 |
| **사용자별** | 피부타입, 이전 대화 | AgentCore Memory | Lab 2 |

> "재고를 Knowledge Base 에 넣으면 어떻게 될까요? 어제 값으로 '재고 있습니다' 라고 답합니다. 그래서 정보의 성격에 따라 저장소를 나눕니다."

---

## Pre-Lab. 인프라 셋업 (30분)

### 말할 것

> "여기는 배우는 단계가 아니라 **준비 단계**입니다. 스크립트가 알아서 해 줍니다. 다만 **순서**가 중요합니다 — 순서를 어기면 뒤에서 권한 에러가 나는데 원인을 찾기 어렵습니다."

### ⚠️ 워크샵 시작 전에 진행자가 확인할 것 — Anthropic FTU

**참가자 계정에서 Claude 를 한 번도 호출한 적이 없으면, First Time Use 양식 제출이 필요합니다.** 공식 문서에 "must complete the FTU form before invoking" 으로 명시된 **필수** 단계입니다.

안 하면 Lab 1 에서 전원이 `AccessDeniedException` 으로 멈춥니다. Workshop Studio 계정이 새로 발급된 경우 특히 확인하세요.

> **사전 안내 문구 예시** — 워크샵 하루 전 공지에 넣으면 좋습니다:
> "Console → Amazon Bedrock → Model catalog → Claude 모델 선택 → use case 양식을 미리 제출해 주세요. 사용 목적과 회사/GitHub URL 이 필요합니다."

현장에서 확인:

```bash
aws bedrock get-foundation-model-availability \
  --model-id anthropic.claude-haiku-4-5-20251001-v1:0 --region us-east-1
```

`agreementAvailability.status` = `AVAILABLE` 이면 정상입니다.

### ⚠️ 진행자가 가장 먼저 강조할 것

**"SageMaker Studio 도메인을 먼저 만드세요."**

도메인을 만들 때 SageMaker execution role 이 자동 생성되고, 그 role 에 권한을 붙이는 게 다음 단계입니다. 도메인이 없으면 `grant-sagemaker-permissions.sh` 가 이렇게 끝납니다:

```
[알림] 이 계정에 SageMaker execution role 이 없습니다.
```

**아무 일도 하지 않고 정상 종료**하기 때문에 참가자가 성공했다고 착각합니다. 그리고 Lab 1 에서 `AccessDeniedException` 을 만납니다.

### 입력할 명령 (순서대로)

**1단계 — Console 에서 도메인 생성 (걸어두고 바로 2단계로)**

Console → SageMaker AI → Studio → **Create domain** → **Set up for single user (Quick setup)**

> 진행자 팁: 도메인 생성은 3-5분 걸립니다. **기다리지 말고** 바로 CloudShell 로 보내세요. `onestop.sh` 가 10분 걸리므로 그 사이 도메인이 완성됩니다.

**2단계 — CloudShell**

```bash
git clone https://github.com/Hannah-ireum/thewhoo-agentcore-workshop.git
cd thewhoo-agentcore-workshop
./scripts/onestop.sh w001
```

끝나면 `KB_ID` 를 받아 적게 하고, 이어서:

```bash
./scripts/grant-sagemaker-permissions.sh
```

> **여기서 반드시 확인시킬 것**: 출력에 `정책 적용 완료` 가 보여야 합니다.
> `execution role 이 없습니다` 가 나오면 1단계 도메인이 아직 안 끝난 것 — 도메인 InService 확인 후 재실행.

**3단계 — Code Editor**

Studio → Applications → **Code Editor** → **Create Code Editor space** → Run space → Open → Terminal

```bash
cd ~
git clone https://github.com/Hannah-ireum/thewhoo-agentcore-workshop.git
cd thewhoo-agentcore-workshop
./scripts/setup-python.sh

source .venv/bin/activate   # ⚠️ 이 줄을 빠뜨리면 Lab 1 부터 전부 실패
which python                # .venv/bin/python 이 나와야 정상
```

### ⚠️ 두 번째로 강조할 것 — venv

> "`setup-python.sh` 는 venv 를 **만들어 주지만 켜 주지는 않습니다**. 스크립트는 자식 프로세스라서, 끝나면 여러분 터미널은 원래 Python 으로 돌아옵니다. 그래서 `source` 를 직접 해야 합니다."

빠뜨리면 이 에러가 납니다 — **참가자가 가장 많이 막히는 지점**입니다:

```
ImportError: cannot import name 'CacheConfig' from 'strands.models.model'
  (/opt/conda/lib/python3.12/site-packages/strands/models/model.py)
```

> 판별법: **에러 경로에 `/opt/conda` 가 보이면 venv 미활성화**입니다. `source .venv/bin/activate` 후 재시도.
> 터미널을 새로 열 때마다 다시 해야 하고, 프롬프트에 `(.venv)` 가 보이면 정상입니다.

### 자주 나오는 질문

**Q. CloudShell 과 Code Editor 를 왜 둘 다 쓰나요? 같은 걸 두 번 하는 것 같은데요.**
> 겹치는 건 `git clone` 뿐이고 서로 다른 머신이라 각자 코드를 받아야 합니다. 역할이 갈립니다 — CloudShell 은 권한이 넓어(WSParticipantRole) 인프라를 만들 수 있지만 디스크가 1GB 라 Python 의존성 설치가 안 됩니다. Code Editor 는 반대입니다. 그리고 `grant-sagemaker-permissions.sh` 는 **자기 자신의 role 에 권한을 못 붙이기 때문에**(self-mutation 금지) 반드시 외부에서 실행해야 합니다.

**Q. PID 를 w001 말고 다른 걸 써도 되나요?**
> 됩니다. 다만 **그 이후 모든 명령에서 같은 값**을 써야 합니다. 한 곳만 다르면 IAM AccessDenied 가 납니다. 단독 진행이면 `w001` 그대로 두는 게 안전합니다.

---

## Lab 0. 데이터 → Knowledge Base (20분)

### 말할 것

> "Knowledge Base 는 세 조각으로 됩니다 — **원본(S3) / 임베딩 모델 / 벡터 저장소**. 이 셋의 **dimension 이 정확히 일치**해야 하고, **어떻게 쪼개 넣느냐**(chunking)가 검색 품질의 80% 를 결정합니다."

### ⚠️ 진행자가 먼저 밝혀야 할 것 — 샘플 데이터입니다

> "이 29개 상품 데이터는 **워크샵 실습용 샘플**입니다. 제품명과 라인(천기단·비첩자생·공진단)은 실제 더후 체계를 참고했지만, **가격·전성분·평점·리뷰는 실제 값이 아닙니다.**"

고객사 담당자가 있는 자리라면 이걸 **먼저** 밝히세요. 화장품은 전성분·기능성 표기가 화장품법 규제 대상이라, 실제 값처럼 오해되면 곤란합니다. 실서비스 전환 시 사내 PIM/상품 DB 로 교체해야 한다는 점을 함께 안내하세요.

### 강조할 개념 — chunking 을 왜 NONE 으로 했나

> "상품 하나가 파일 하나입니다. 그리고 chunking 을 `NONE` 으로 뒀습니다. 왜일까요?"
>
> "상품 정보는 이미 **자연스러운 의미 단위**입니다. 이름·성분·사용법·가격이 한 묶음이죠. 이걸 300 토큰 단위로 자르면 성분 절반이 다른 chunk 로 갈립니다."
>
> "그리고 결정적인 이유 — 만약 29개 상품을 파일 하나에 다 넣고 `NONE` 을 쓰면 **chunk 가 1개**입니다. top-3 를 요청해도 같은 덩어리만 3번 나옵니다."

### 입력할 명령

```bash
python3 scripts/count-categories.py
```

**보여줄 출력** (실측값):

```
총 29개 상품

  스킨케어: 12개
  메이크업: 8개
  바디: 4개
  헤어: 3개
  향수: 2개
```

이어서 실제 검색을 시연합니다:

```bash
python3 scripts/pretty-retrieve.py "천기단 복합 성분"
```

**보여줄 것** — 서로 **다른 상품 3개**가 관련도 순으로 나옵니다 (실측 score 0.70-0.72).

> "여기가 chunking 설계의 결과입니다. 서로 다른 상품 3개가 나오죠. 파일을 합쳐 놨다면 같은 답이 3번 나왔을 겁니다."

### 완료 확인

ingestion job 이 `COMPLETE` 이고 `numberOfDocumentsScanned=29`, `Indexed=29` 면 정상입니다.

### 자주 나오는 질문

**Q. score 가 0.7 인데 낮은 건가요?**
> 0.5 이상이면 의미 있는 결과입니다. 1.0 은 거의 안 나옵니다. 실무에서는 **0.4 이하는 무시하고 "관련 상품 없음"** 으로 처리하는 fallback 을 두는 게 좋습니다.

**Q. 상품이 수만 개면 어떻게 하나요?**
> 파일 분할 원칙은 그대로 유지하되, 카테고리별 prefix 로 data source 를 나누고 metadata 필터를 씁니다. Lab 0 문서의 "실제 서비스에 적용할 때" 절 참고.

---

## Lab 1. RAG 챗봇 (40분) — **가장 중요한 Lab**

### 말할 것

> "Strands Agent 는 세 가지로 만듭니다 — **model / system_prompt / tools**. 이 세 줄이 에이전트의 전부입니다."
>
> "그리고 오늘 가장 중요한 개념 — **에이전트는 도구를 언제 쓸지 스스로 판단합니다**. 우리가 if-else 로 정해주지 않습니다. 그럼 무엇을 보고 판단할까요? **docstring** 입니다."

### 강조할 개념 — docstring 이 곧 명세다

```python
@tool
def kb_retrieve(query: str) -> str:
    """Bedrock Knowledge Base에서 뷰티 상품 정보를 검색합니다.

    Args:
        query: 검색할 질문이나 키워드
    """
```

> "이 docstring 이 LLM 에게 전달되는 **유일한 설명서**입니다. 여기를 모호하게 쓰면 엉뚱한 도구를 부릅니다. 실무에서 '에이전트가 도구를 잘못 골라요' 라는 문제의 80% 는 description 문제입니다."

### 입력할 명령

```bash
cd ~/thewhoo-agentcore-workshop/src        # 이미 src 안이면 생략
python run_lab1.py
```

**보여줄 출력** — 성분/사용법이 섹션으로 정리돼 나옵니다. 실측 예시:

> **주요 성분**
> - 천기단(天氣丹) 복합 성분 — 한방 왕실 처방 기반
> - 장뇌삼 — 피부 활력
> - 영지 / 청아교 — 보습과 영양
>
> **사용법**: 세안 후 토너, 에센스 다음 단계에서...

### ⭐ 이 Lab 의 하이라이트 — 한계를 보여주기

```bash
python run_lab1.py "천기단 화현 크림 재고 있어?"
```

**보여줄 출력** (실측):

> 천기단 화현 크림의 재고 여부는 KB에서 확인할 수 없어요. 재고 상황, 배송 예정일 등은 실시간 주문 시스템을 통해 확인해야 하므로...

### 말할 것 (여기서 시간을 쓰세요)

> "실패한 것처럼 보이지만 **이게 정상이고, 오늘 가장 중요한 장면**입니다."
>
> "왜 중요한가요? 나쁜 에이전트는 여기서 **지어냅니다**. '재고 3개 남았습니다' 라고요. 데이터에 없는데도요. 그게 실서비스에서 사고가 됩니다."
>
> "우리 에이전트는 '내 지식 범위 밖'이라고 정직하게 말합니다. 그리고 이 빈칸을 **Lab 3 에서 Gateway 도구로 채웁니다**."

> 진행자 팁: 여기서 오프닝의 정적/실시간/사용자별 표를 다시 가리키세요. "지금 정적 칸을 채웠고, 실시간 칸이 비어 있는 상태입니다."

### 자주 나오는 질문

**Q. `ImportError: cannot import name 'CacheConfig'` 가 나요.**
> venv 미활성화입니다. 에러 경로에 `/opt/conda` 가 보이는지 확인하세요. `cd ~/thewhoo-agentcore-workshop && source .venv/bin/activate` 후 재시도.

**Q. `cd: src: No such file or directory`**
> 이미 `src` 안에 있습니다. 그대로 실행하거나 `cd ~/thewhoo-agentcore-workshop/src` 를 쓰세요.

**Q. 답변이 문서 예시와 글자가 다릅니다.**
> 정상입니다. LLM 이라 매번 다릅니다. **구조와 사실관계**(성분 이름, 가격)가 맞으면 됩니다.

---

## Lab 2. Memory (45분)

### 말할 것

> "지금 챗봇은 대화가 끝나면 다 잊습니다. '저번에 추천한 거' 를 모릅니다. AgentCore Memory 를 붙입니다."
>
> "그런데 Memory 는 하나가 아니라 **4가지 종류**가 있습니다. 왜 나눴을까요? **읽는 시점이 다르기 때문**입니다."

### 강조할 개념 — 4-strategy 를 나눈 이유

| Strategy | 무엇을 담나 | 언제 읽나 |
|---|---|---|
| **UserPreference** | 피부타입, 선호 | 세션 시작 시 1회 |
| **Summary** | 이번 대화 요약 | 재접속할 때 |
| **Semantic** | 도메인 사실 | 관련 질문 감지 시 |
| **Episodic** | 상담 에피소드 | "저번에" 같은 모호한 참조 |

> "전부 매 턴 읽으면 context window 가 낭비되고 비용·지연이 늘어납니다. 용도별로 나눠서 **필요할 때만** 읽는 게 설계 포인트입니다."

### 입력할 명령

```bash
python3 scripts/create-memory.py     # 프로젝트 루트에서
```

> **진행자 주의** — 이 스크립트는 strategy 4개가 ACTIVE 될 때까지 기다리므로 **수 분 걸립니다**. 돌려놓고 그 사이 위의 4-strategy 개념을 설명하세요. 시간을 채우기 좋은 구간입니다.

이어서 프로필을 심고 60초 기다립니다:

```bash
cd ~/thewhoo-agentcore-workshop/src
python run_lab2.py seed
# 60초 대기 후
python run_lab2.py ask "보습크림 추천해줘"
```

### ⭐ 보여줄 것

답변에 **"민감 피부 전용"**, **"자극 최소화"** 같은 표현이 들어갑니다. 질문에는 그런 말이 없었는데요.

> "제가 질문에 '민감성' 이라고 안 썼습니다. 그런데 답변이 민감 피부를 고려하고 있죠. `seed` 로 심어둔 프로필을 Memory 에서 읽어온 겁니다."

### ⚠️ 진행자가 미리 알려줄 것 — eventual consistency

> "`seed` 직후 바로 `ask` 하면 프로필이 안 나올 수 있습니다. 장기 Memory 추출은 **비동기**라서요. 60초 기다리세요. 실무에서도 '방금 저장한 게 안 읽힌다' 는 이슈가 여기서 옵니다."

### 자주 나오는 질문

**Q. namespace 의 `{actorId}` 는 누가 채우나요?**
> `create_event` 호출 시 넘긴 `actor_id` 로 자동 치환됩니다. 그래서 **사용자마다 저장 공간이 자동 분리**됩니다.

**Q. Episodic 의 reflection 이 뭔가요?**
> 여러 에피소드를 가로질러 공통 패턴을 뽑는 자동 통합 단계입니다. 개별 에피소드는 `/episodes/{actorId}/{sessionId}/` 에, 통합 insight 는 `/episodes/{actorId}/` 에 쌓입니다. 읽을 때는 후자를 씁니다.

---

## Lab 3. Gateway + MCP (55분) — **가장 긴 Lab**

### 말할 것

> "Lab 1 에서 못 답했던 재고 질문, 이제 해결합니다. 외부 API 를 에이전트가 부를 수 있게 연결합니다."
>
> "방법은 두 가지입니다. ① `@tool` 로 직접 감싸기 ② Gateway 에 등록하기. Lab 1 의 `kb_retrieve` 는 ① 이었죠. 그럼 왜 Gateway 를 쓸까요?"

### 강조할 개념 — Gateway 를 쓰는 판단 기준

> "도구가 3개 이상이거나 / 여러 에이전트가 같은 도구를 공유하거나 / inbound 인증이 필요하면 Gateway 입니다."
>
> "`@tool` 방식은 도구가 20개로 늘면 에이전트 코드에 boto3 호출이 20개 박힙니다. 인증도 각각 관리해야 하죠. Gateway 는 '**MCP 서버에 붙기**' 하나만 알면 백엔드가 Lambda 든 온프렘 API 든 차이를 흡수합니다."

### 입력할 명령

```bash
cd ~/thewhoo-agentcore-workshop
python3 scripts/create-gateway.py
```

30초쯤 후 `AGENTCORE_GATEWAY_URL` 이 나오면 export 합니다.

target 4개가 READY 인지 확인:

```bash
GW_ID=$(aws bedrock-agentcore-control list-gateways --region us-east-1 \
  --query "items[?contains(name, 'thewhoo-gateway')].gatewayId | [0]" --output text)
aws bedrock-agentcore-control list-gateway-targets \
  --gateway-identifier "$GW_ID" --region us-east-1 \
  --query 'items[].[name,status]' --output table
```

**보여줄 출력** (실측) — 4개 전부 `READY`.

### ⭐ 실행하며 보여줄 것

```bash
cd ~/thewhoo-agentcore-workshop/src
python run_lab3.py "WHOO-00101 재고 있어?"
```

verbose 출력의 `[도구 호출 내역]` 블록을 **꼭 화면에 띄워 주세요**:

```
→ check-stock___check_stock  {"product_id": "WHOO-00101"}
← result [success]  available=True, eta=2~3일 이내 도착
```

> "여기가 핵심입니다. 제가 '재고 확인해' 라고 코드에 쓴 게 아닙니다. 에이전트가 질문을 보고 **4개 도구 중 `check_stock` 을 골랐고**, `WHOO-00101` 을 인자로 뽑아냈습니다."

이어서 복합 질의를 시연합니다:

```bash
python run_lab3.py "민감성에 진정 좋은 거 추천하고 프로모션도 알려줘"
```

> "도구를 **두 개 연달아** 부릅니다. 추천 → 프로모션. 이걸 우리가 순서를 정해준 게 아닙니다."

### ⚠️ 진행자가 설명할 것 — 도구 이름의 `___`

도구 이름이 `check-stock___check_stock` 처럼 나오는 걸 참가자가 반드시 물어봅니다.

> "Gateway 가 **target 이름을 prefix 로 붙여서** 노출합니다. `<target>___<tool>` 형태죠. 그래서 system prompt 에도 이 전체 이름을 적어야 합니다. 짧은 이름으로 부르면 `tool not found in registry` 로 실패하고 재시도가 발생합니다."

### 자주 나오는 질문

**Q. target 이름에 언더스코어를 쓰면?**
> 생성 단계에서 실패합니다. **알파벳·숫자·하이픈만** 허용됩니다.

**Q. Semantic Tool Search 는 꼭 켜야 하나요?**
> 도구 1-5개면 OFF 가 단순합니다. 20개 이상이거나 동적으로 추가되면 ON 을 고려하세요. **Gateway 생성 시에만 설정 가능**하고 나중에 바꾸려면 재생성해야 합니다.

**Q. `count: 0` 이 나옵니다.**
> 샘플 데이터에 그 조건의 상품이 없는 것입니다. 정상 동작입니다.

---

## Lab 4. Orchestrator (40분)

### 말할 것

> "이제 조각이 다 모였습니다 — RAG, Memory, 외부 도구. 그런데 지금은 따로 돌고 있죠. 하나로 묶습니다."
>
> "패턴 이름은 **Agents-as-Tools** 입니다. 전문 에이전트를 **도구처럼** 감싸서 상위 에이전트에게 줍니다."

### 강조할 개념 — 왜 나누나

| 에이전트 | 모델 | 책임 |
|---|---|---|
| Orchestrator | Sonnet 4.6 | 의도 분류, 조율 (직접 KB·도구 호출 금지) |
| Q&A | Haiku 4.5 | KB 검색 |
| Recommend | Haiku 4.5 | Gateway 도구 4종 |
| Summary | Haiku 4.5 | 톤·포맷 정리 |

> "판단은 큰 모델이, 실행은 작은 모델이 합니다. **비용과 품질의 균형**입니다. 하나의 거대한 프롬프트로 다 하려 하면 디버깅이 불가능해집니다."

### 입력할 명령

```bash
cd ~/thewhoo-agentcore-workshop/src
python run_lab4.py
```

3가지 시나리오가 순차 실행됩니다.

### ⭐ 보여줄 것

시나리오 ③ (프로모션 정리) 에서 **프로모션 기간이 오늘을 포함**하는지 보여주세요. 실측 예시:

> 📅 **기간:** 2026.08.17 ~ 2026.08.31
> 💡 프로모션 기간이 8월 31일까지로 얼마 남지 않았어요!

> "Mock Lambda 가 오늘 기준으로 기간을 계산합니다. 고정 날짜를 박아두면 나중에 '진행 중' 이라면서 끝난 날짜를 안내하게 되죠. 사소해 보이지만 실서비스에서 신뢰를 깎는 종류의 버그입니다."

그리고 프로필이 이어지는 것도 보여주세요 — Lab 2 에서 심은 건성·민감성이 답변에 반영됩니다.

### 자주 나오는 질문

**Q. Orchestrator 가 도구를 안 부르고 직접 답하면?**
> system prompt 에 "직접 KB·도구 호출 금지" 를 명시했지만 LLM 이라 100% 는 아닙니다. 실무에서는 Lab 8 의 `ToolSelectionAccuracy` evaluator 로 이런 회귀를 잡습니다.

**Q. 서브에이전트를 더 늘려도 되나요?**
> 됩니다. 다만 도구 설명이 겹치면 선택 정확도가 떨어집니다. 책임 경계를 명확히 나누세요.

---

## 마무리 (10분)

### 말할 것

> "오늘 만든 걸 정리하면 — 상품 데이터를 검색 가능하게 만들고(Lab 0-1), 사용자를 기억하고(Lab 2), 외부 시스템을 부르고(Lab 3), 전문 에이전트를 묶었습니다(Lab 4)."
>
> "그런데 지금 이건 **여러분 터미널에서만 돌아갑니다**. 노트북을 닫으면 끝이죠."
>
> "Day 2 에서는 이걸 **HTTPS 엔드포인트로 배포**하고, **운영 지표를 보고**, **답변 품질을 자동 평가**합니다. 즉 '만든 것' 에서 '운영하는 것' 으로 넘어갑니다."

### 오프닝 그림 다시 보여주기

`final.svg` 를 다시 띄우고, 오늘 채운 조각들을 하나씩 짚어 주세요. 남은 조각(Runtime, Observability, Evaluations)이 Day 2 입니다.

### ⚠️ 진행자 필수 안내 — 리소스 유지

> "**리소스를 지우지 마세요.** Day 2 는 오늘 만든 KB·Memory·Gateway 위에서 진행합니다."

세션이 끊긴 참가자를 위해 복구 방법을 안내합니다:

```bash
cd ~/thewhoo-agentcore-workshop
source .venv/bin/activate
eval "$(./scripts/print-env.sh w001)"
echo "KB=$KB_ID  MEM=$AGENTCORE_MEMORY_ID  GW=$AGENTCORE_GATEWAY_URL"
```

세 값이 다 나오면 정상입니다. (Memory·Gateway 는 Lab 2·3 을 마친 뒤에만 나옵니다.)

---

## 진행자 참고 — 자주 막히는 지점 요약

| 증상 | 원인 | 조치 |
|---|---|---|
| `execution role 이 없습니다` | 도메인 미생성 | 도메인 InService 확인 후 재실행 |
| `AccessDeniedException` | 권한 부여 전 터미널을 열었음 | 터미널 닫고 새로 열기 |
| `CacheConfig` ImportError | **venv 미활성화** (가장 흔함) | `source .venv/bin/activate` |
| `cd: src: No such file` | 이미 src 안 | 절대경로 사용 |
| `tool not found in registry` | 도구 이름에 `___` prefix 누락 | 최신 코드로 `git pull` |
| 프로필이 답변에 안 보임 | Memory 추출 지연 | 60초 대기 후 재시도 |
