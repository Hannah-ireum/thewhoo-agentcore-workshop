#!/usr/bin/env python3
"""agentcore dev 웹 UI 를 Code Editor 포트포워딩으로 볼 수 있게 하는 프록시.

agentcore dev 의 웹 UI 는 두 가지 이유로 Code Editor 프록시에서 직접 안 열립니다:
  1) 127.0.0.1 에만 바인드  → 외부 인터페이스로 접근 불가
  2) Host 헤더 allowlist    → localhost/127.0.0.1 이외의 Host 는 403 Forbidden
이 프록시가 0.0.0.0 에 붙고 Host 를 127.0.0.1 로 바꿔서 두 문제를 동시에 없앱니다.
"""
import re, socket, sys, threading

LISTEN = int(sys.argv[1]) if len(sys.argv) > 1 else 8091
TARGET = int(sys.argv[2]) if len(sys.argv) > 2 else 8081
HOSTHDR = f"127.0.0.1:{TARGET}".encode()

def fix_host(head: bytes) -> bytes:
    return re.sub(rb'(?im)^Host:[^\r\n]*', b'Host: ' + HOSTHDR, head)

def relay(a, b):
    try:
        while True:
            d = a.recv(65536)
            if not d: break
            b.sendall(d)
    except Exception: pass
    finally:
        for s in (a, b):
            try: s.shutdown(socket.SHUT_RDWR)
            except Exception: pass
            try: s.close()
            except Exception: pass

def handle(cli):
    try:
        up = socket.create_connection(("127.0.0.1", TARGET))
    except Exception:
        cli.close(); return
    buf = b""
    try:
        while b"\r\n\r\n" not in buf:
            d = cli.recv(65536)
            if not d:
                cli.close(); up.close(); return
            buf += d
        head, rest = buf.split(b"\r\n\r\n", 1)
        up.sendall(fix_host(head) + b"\r\n\r\n" + rest)
    except Exception:
        cli.close(); up.close(); return
    threading.Thread(target=relay, args=(cli, up), daemon=True).start()
    threading.Thread(target=relay, args=(up, cli), daemon=True).start()

srv = socket.socket()
srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
srv.bind(("0.0.0.0", LISTEN)); srv.listen(128)
print(f"UI 프록시 준비됨 — PORTS 탭에서 {LISTEN} 을 포워딩하세요 (대상 dev UI: {TARGET})", flush=True)
try:
    while True:
        c, _ = srv.accept()
        threading.Thread(target=handle, args=(c,), daemon=True).start()
except KeyboardInterrupt:
    pass
