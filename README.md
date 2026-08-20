# 더후(The History of Whoo) AI 챗봇 워크샵

Amazon Bedrock **AgentCore** 와 **Strands Agents SDK** 로 뷰티 커머스 AI 챗봇을 처음부터 만들고, 실제 서비스처럼 배포·운영까지 다루는 **2일 실습 워크샵**입니다.

> 문서는 이 저장소의 `docs/` 안에 있고, 아래 목차에서 바로 열어 볼 수 있습니다.

## 무엇을 만드나요?

> **고객**: 건성 피부에 쓰기 좋은 보습크림 뭐가 있어?
>
> **챗봇**: 건성 피부에 맞춰 2가지 추천드려요. ① 더후 천기단 화현 크림 (195,000원) — 천기단 복합 성분으로 탄력·수분 동시 케어. ② 더후 비첩 자생 수분크림 (135,000원) — 민감 피부에도 자극 없는 보습크림.
>
> **(같은 세션 이어서)** 저번에 추천한 첫 번째 거 재고 있어?
>
> **챗봇**: 더후 천기단 화현 크림 말씀이시죠. 현재 재고가 있고 오늘 출고 가능합니다.

한 번의 질문만 답하는 게 아니라, **고객의 피부타입과 이전 대화 맥락을 기억**하고, **상품 검색·재고·프로모션 API 를 스스로 호출**하며, **근거 기반으로 답변을 정제**합니다.

## 시작하기

**처음이라면 여기서 출발하세요** → [시작하기 전에](docs/00-시작하기-전에.md) → [Pre-Lab. 인프라 셋업](docs/00-pre-lab-셋업.md)

```bash
git clone https://github.com/Hannah-ireum/thewhoo-agentcore-workshop.git
cd thewhoo-agentcore-workshop
```

## Day 1 — 통합 챗봇 만들기

로컬에서 동작하는 챗봇을 완성합니다.

| Lab | 내용 | 핵심 리소스 |
|---|---|---|
| [Pre-Lab](docs/00-pre-lab-셋업.md) | 인프라 셋업 (S3, IAM, Cognito, Mock Lambda 4종, KB + S3 Vectors) | `onestop.sh` |
| [Lab 0](docs/01-lab0-데이터-준비하기.md) | 상품 데이터를 Knowledge Base 에 색인 | Bedrock KB ingestion |
| [Lab 1](docs/02-lab1-상품정보-답하는-챗봇.md) | 근거 기반 상품 QnA 챗봇 (RAG) | Strands Agent + KB retrieve |
| [Lab 2](docs/03-lab2-대화를-기억하기.md) | AgentCore Memory 로 프로필·맥락 유지 | `create-memory.py` (4 strategy) |
| [Lab 3](docs/04-lab3-외부-도구-연결하기.md) | AgentCore Gateway 에 MCP 도구 등록 | `create-gateway.py` (Lambda target 4종) |
| [Lab 4](docs/05-lab4-에이전트-팀으로-묶기.md) | Orchestrator 로 전문 Agent 3개 통합 | Agents-as-Tools 패턴 |

## Day 2 — 서비스 배포·운영

Day 1 에서 만든 챗봇을 실제 서비스처럼 배포하고 운영 품질을 챙깁니다.

| Lab | 내용 | 핵심 도구 |
|---|---|---|
| [Lab 5](docs/06-lab5-서비스로-배포하기.md) | AgentCore Runtime 배포 — HTTPS 엔드포인트 | `agentcore deploy`, `invoke_agent_runtime` |
| [Lab 6](docs/07-lab6-운영-상태-들여다보기.md) | 운영 가시성 — trace span 트리 · prompt cache | GenAI Observability |
| [Lab 7](docs/08-lab7-운영-모니터링-대시보드.md) | 운영 모니터링 — KPI · 알람 · 비용 | CloudWatch Dashboard |
| [Lab 8](docs/09-lab8-답변-품질-평가하기.md) | 답변 품질 자동 평가 | AgentCore Evaluations (골든셋 20 시나리오) |
| [마무리](docs/10-실서비스-적용하려면.md) | 실서비스 적용 체크리스트 | 실 DB 연동 · 가드레일 · 다국어 |

> Day 2 를 새 AWS 계정에서 시작하는 경우 [Day 2 시작 안내](docs/README-day2.md) 의 패스트트랙 스크립트를 사용하세요.

## 아키텍처

![최종 아키텍처](docs/assets/diagrams/final.svg)

## 배우는 것

* 상품 데이터를 **검색 가능한 지식창고**(Bedrock Knowledge Base + S3 Vectors) 로 구성
* **Strands Agents SDK** 로 AI 에이전트를 가볍게 구성
* **AgentCore Memory** 로 사용자 선호·대화 맥락을 저장하고 재사용
* **AgentCore Gateway + MCP** 로 외부 API 를 에이전트가 자율적으로 호출
* 여러 전문 에이전트를 **하나의 Orchestrator 아래로 묶는** 오케스트레이션 패턴
* **AgentCore Runtime / Observability / Evaluations** 로 배포와 운영 품질 확보

## 참고 문서

* [Streamlit UI 여는 법 (Code Editor)](docs/streamlit-on-code-editor.md)
* [환경변수 복구 (세션이 끊겼을 때)](docs/env-recovery.md)

## 사전 요구사항

* AWS 계정 (`us-east-1` 기준) — Bedrock 모델 접근 가능
* Python 3.10 이상 (3.11/3.12 권장)
* 최신 AWS CLI v2 — `bedrock-agentcore-control` / `s3vectors` 지원 버전
  (`setup-python.sh` 가 자동으로 확인해 줍니다)

## 저장소 구조

```
docs/          워크샵 문서 (Day 1 · Day 2)
src/           에이전트 코드 (QnA · Recommend · Summary · Orchestrator) + Streamlit UI
lambdas/       Mock API 4종 (상품검색 · 추천 · 재고 · 프로모션) + OpenAPI 스펙
scripts/       셋업 · 운영 · 평가 · 정리 스크립트
infra/cfn/     CloudFormation 템플릿 + Knowledge Base 부트스트랩
data/          샘플 상품 데이터 (더후 29종)
```

## 정리

워크샵이 끝나면 과금 리소스를 반드시 삭제하세요.

```bash
./scripts/cleanup-all.sh <참가자ID> --yes
```

스크립트가 마지막에 잔존 리소스를 실제로 재조회해 확인해 줍니다.

---

Amazon Bedrock AgentCore + Strands Agents SDK · 실습 소요 약 2일
