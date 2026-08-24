#!/usr/bin/env python3
"""공개 배포 전 보안 게이트 — 민감정보가 있으면 exit 1 로 배포를 막는다.

왜 필요한가
  이 저장소는 private 원본 → public 배포 리포로 복사되는 구조입니다.
  이전에는 배포 스크립트가 grep 으로 경고만 출력하고 **진행을 막지 않아서**
  로컬 절대경로(/Users/<name>/...)가 공개 리포에 올라간 적이 있습니다.
  그래서 게이트를 별도 스크립트로 분리하고, 실패 시 종료코드 1 을 냅니다.

Usage:
  python3 scripts/verify/check-secrets.py              # 저장소 루트 스캔
  python3 scripts/verify/check-secrets.py <디렉터리>    # 배포 스테이징 스캔
  → 발견 0건이면 exit 0, 1건 이상이면 exit 1
"""
from __future__ import annotations

import pathlib
import re
import sys

# 패턴 → (설명, 화이트리스트)
#   화이트리스트는 "문서용 예시값" 만 담습니다. 실제 값은 절대 넣지 마세요.
PATTERNS: list[tuple[str, str, set[str]]] = [
    (r'\b(?:AKIA|ASIA|AIDA|AROA|ANPA)[A-Z0-9]{16}\b', "AWS Access Key", set()),
    (r'-----BEGIN (?:RSA |EC |OPENSSH |PGP )?PRIVATE KEY', "Private Key", set()),
    (r'\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}', "JWT/Bearer 토큰", set()),
    (r'(?i)aws_secret_access_key\s*[=:]\s*\S', "AWS Secret Key", set()),
    (r'(?i)aws_session_token\s*[=:]\s*\S', "AWS Session Token", set()),
    (r'/Users/[a-z][a-z0-9._-]+', "로컬 홈 경로(macOS)", {"/Users/<name>"}),
    (r'/home/[a-z][a-z0-9._-]+', "로컬 홈 경로(Linux)",
     {"/home/<name>", "/home/user", "/home/ec2-user", "/home/sagemaker-user"}),
    (r'\b\d{12}\b', "AWS 계정 ID(12자리)", {"123456789012", "000000000000"}),
    (r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b', "이메일",
     {"user@example.com", "your-team@example.com", "someone@example.com"}),
    (r'thewhoo-agentcore-workshop', "구 저장소명(원본 리포 노출)", set()),
    (r'\b[a-z]{2}-[a-z]+-\d_[A-Za-z0-9]{9}\b', "Cognito User Pool ID", set()),
]

SKIP_DIRS = {".git", "__pycache__", "node_modules", ".venv", "venv", "agentcore"}
SKIP_SUFFIX = {".png", ".jpg", ".jpeg", ".gif", ".svg", ".pyc", ".zip", ".pdf", ".ico"}


def scan(root: pathlib.Path) -> list[tuple[str, int, str, str]]:
    found: list[tuple[str, int, str, str]] = []
    for f in sorted(root.rglob("*")):
        if not f.is_file():
            continue
        if any(p in SKIP_DIRS for p in f.parts):
            continue
        if f.suffix.lower() in SKIP_SUFFIX:
            continue
        try:
            text = f.read_text(errors="ignore")
        except Exception:
            continue
        rel = str(f.relative_to(root))
        for ln, line in enumerate(text.splitlines(), 1):
            for pat, label, allow in PATTERNS:
                for m in re.findall(pat, line):
                    v = m if isinstance(m, str) else m[0]
                    if v in allow:
                        continue
                    found.append((rel, ln, label, v[:70]))
    return found


def main() -> int:
    root = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    hits = scan(root)

    print(f"보안 스캔: {root}")
    if not hits:
        print("  ✓ 민감정보 0건 — 배포 가능")
        return 0

    # 종류별로 묶어 출력
    by_label: dict[str, list[tuple[str, int, str]]] = {}
    for rel, ln, label, v in hits:
        by_label.setdefault(label, []).append((rel, ln, v))

    print(f"  ✗ {len(hits)}건 발견 — 배포를 중단합니다\n")
    for label, items in by_label.items():
        print(f"  [{label}] {len(items)}건")
        for rel, ln, v in items[:8]:
            print(f"    {rel}:{ln}  {v}")
        if len(items) > 8:
            print(f"    ... +{len(items) - 8}건")
        print()
    print("  실제 값이면 제거하고, 문서용 예시라면 이 스크립트의")
    print("  PATTERNS 화이트리스트에 추가하세요 (실제 값은 절대 넣지 마세요).")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
