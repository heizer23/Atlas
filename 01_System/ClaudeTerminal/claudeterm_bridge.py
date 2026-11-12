#!/usr/bin/env python3
"""ClaudeTerminal bridge — attaches a browser terminal (xterm.js) to a host tmux session.

Security model (R-OPS-BP-02):
  * Binds 127.0.0.1 only. Containers cannot reach host loopback; the only way in is
    `tailscale serve` (tailnet-only, Funnel off) — see README.md.
  * Every request must carry the `Tailscale-User-Login` header injected by `tailscale serve`
    and it must equal CLAUDETERM_ALLOWED_LOGIN.
  * WebSocket upgrades must come from an Origin in CLAUDETERM_ALLOWED_ORIGINS.
  * Session names are restricted to [A-Za-z0-9_-]{1,32}; no shell is involved in spawning.

Protocol: binary WS frames = raw pty bytes (both directions); text frames from the client are
JSON, currently only {"type":"resize","cols":N,"rows":N}. Closing the socket kills only the tmux
*client*; the tmux session (and anything running in it) survives.

Stdlib only (no pip needed on the host).
"""

import asyncio
import base64
import fcntl
import hashlib
import json
import os
import pty
import re
import signal
import struct
import subprocess
import termios

HOST = "127.0.0.1"
PORT = int(os.environ.get("CLAUDETERM_PORT", "8031"))
ALLOWED_LOGIN = os.environ.get("CLAUDETERM_ALLOWED_LOGIN", "p.remmecke@gmail.com")
ALLOWED_ORIGINS = {
    o.strip() for o in os.environ.get(
        "CLAUDETERM_ALLOWED_ORIGINS", "https://workout.linspad.net,https://linspad.net"
    ).split(",") if o.strip()
}
START_DIR = os.environ.get("CLAUDETERM_START_DIR", os.path.expanduser("~/Prod/Atlas"))
SESSION_RE = re.compile(r"^[A-Za-z0-9_-]{1,32}$")
WS_GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
MAX_HEADER = 16 * 1024
MAX_FRAME = 1 << 20


# ── HTTP helpers ──────────────────────────────────────────────────────────────

async def read_request(reader):
    raw = await reader.readuntil(b"\r\n\r\n")
    if len(raw) > MAX_HEADER:
        raise ValueError("header too large")
    lines = raw.decode("latin-1").split("\r\n")
    method, target, _ = lines[0].split(" ", 2)
    headers = {}
    for line in lines[1:]:
        if ":" in line:
            k, v = line.split(":", 1)
            headers[k.strip().lower()] = v.strip()
    return method, target, headers


def respond(writer, status, body=b"", extra=None, ctype="text/plain"):
    head = [f"HTTP/1.1 {status}", f"Content-Length: {len(body)}", f"Content-Type: {ctype}", "Connection: close"]
    head += extra or []
    writer.write(("\r\n".join(head) + "\r\n\r\n").encode() + body)


def cors(headers):
    origin = headers.get("origin", "")
    return [f"Access-Control-Allow-Origin: {origin}", "Vary: Origin"] if origin in ALLOWED_ORIGINS else []


# ── WebSocket framing (RFC 6455, minimal) ─────────────────────────────────────

def ws_frame(opcode, payload=b""):
    n = len(payload)
    if n < 126:
        head = struct.pack("!BB", 0x80 | opcode, n)
    elif n < 1 << 16:
        head = struct.pack("!BBH", 0x80 | opcode, 126, n)
    else:
        head = struct.pack("!BBQ", 0x80 | opcode, 127, n)
    return head + payload


async def ws_read(reader):
    """Return (opcode, payload) for one complete message (handles fragmentation)."""
    msg_op, buf = None, b""
    while True:
        b1, b2 = await reader.readexactly(2)
        fin, op, masked, n = b1 & 0x80, b1 & 0x0F, b2 & 0x80, b2 & 0x7F
        if n == 126:
            n = struct.unpack("!H", await reader.readexactly(2))[0]
        elif n == 127:
            n = struct.unpack("!Q", await reader.readexactly(8))[0]
        if n > MAX_FRAME or not masked:
            raise ValueError("bad frame")
        mask = await reader.readexactly(4)
        data = bytearray(await reader.readexactly(n))
        for i in range(n):
            data[i] ^= mask[i % 4]
        if op >= 0x8:  # control frame — never fragmented
            return op, bytes(data)
        if op != 0:
            msg_op = op
        buf += bytes(data)
        if len(buf) > MAX_FRAME:
            raise ValueError("message too large")
        if fin:
            return msg_op, buf


# ── tmux ──────────────────────────────────────────────────────────────────────

def list_sessions():
    r = subprocess.run(
        ["tmux", "list-sessions", "-F", "#{session_name}\t#{session_windows}\t#{session_attached}"],
        capture_output=True, text=True,
    )
    out = []
    for line in r.stdout.splitlines():
        name, windows, attached = line.split("\t")
        out.append({"name": name, "windows": int(windows), "attached": int(attached)})
    return out


def set_winsize(fd, cols, rows):
    fcntl.ioctl(fd, termios.TIOCSWINSZ, struct.pack("HHHH", rows, cols, 0, 0))


def spawn_tmux(session, cols, rows):
    pid, fd = pty.fork()
    if pid == 0:
        os.chdir(START_DIR)
        env = dict(os.environ, TERM="xterm-256color")
        os.execvpe("tmux", ["tmux", "new-session", "-A", "-s", session, "-c", START_DIR], env)
    set_winsize(fd, cols, rows)
    return pid, fd


# ── Connection handler ────────────────────────────────────────────────────────

async def handle(reader, writer):
    try:
        method, target, headers = await read_request(reader)
        path, _, query = target.partition("?")

        if headers.get("tailscale-user-login") != ALLOWED_LOGIN:
            respond(writer, "403 Forbidden", b"forbidden")
        elif path == "/claudeterm/sessions" and method == "GET":
            respond(writer, "200 OK", json.dumps(list_sessions()).encode(), cors(headers), "application/json")
        elif path == "/claudeterm/ws" and headers.get("upgrade", "").lower() == "websocket":
            if headers.get("origin", "") not in ALLOWED_ORIGINS:
                respond(writer, "403 Forbidden", b"bad origin")
            else:
                await handle_ws(reader, writer, headers, query)
                return
        else:
            respond(writer, "404 Not Found", b"not found")
        await writer.drain()
    except (asyncio.IncompleteReadError, ConnectionError, ValueError, asyncio.LimitOverrunError):
        pass
    finally:
        writer.close()


async def handle_ws(reader, writer, headers, query):
    params = dict(p.split("=", 1) for p in query.split("&") if "=" in p)
    session = params.get("session", "claude")
    if not SESSION_RE.match(session):
        respond(writer, "400 Bad Request", b"bad session name")
        return
    cols = max(10, min(int(params.get("cols", 80)), 500))
    rows = max(5, min(int(params.get("rows", 24)), 200))

    accept = base64.b64encode(hashlib.sha1((headers["sec-websocket-key"] + WS_GUID).encode()).digest()).decode()
    writer.write((
        "HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
        f"Sec-WebSocket-Accept: {accept}\r\n\r\n"
    ).encode())
    await writer.drain()

    pid, fd = spawn_tmux(session, cols, rows)
    loop = asyncio.get_running_loop()
    out_q = asyncio.Queue()

    def on_pty_readable():
        try:
            data = os.read(fd, 65536)
        except OSError:
            data = b""
        out_q.put_nowait(data)
        if not data:
            loop.remove_reader(fd)

    loop.add_reader(fd, on_pty_readable)

    async def pty_to_ws():
        while True:
            data = await out_q.get()
            if not data:
                writer.write(ws_frame(0x8, struct.pack("!H", 1000)))
                await writer.drain()
                return
            writer.write(ws_frame(0x2, data))
            await writer.drain()

    async def ws_to_pty():
        while True:
            op, payload = await ws_read(reader)
            if op == 0x8:
                return
            if op == 0x9:
                writer.write(ws_frame(0xA, payload))
            elif op == 0x2:
                os.write(fd, payload)
            elif op == 0x1:
                msg = json.loads(payload)
                if msg.get("type") == "resize":
                    set_winsize(fd, max(10, min(int(msg["cols"]), 500)), max(5, min(int(msg["rows"]), 200)))
                    os.kill(pid, signal.SIGWINCH)

    tasks = [asyncio.create_task(pty_to_ws()), asyncio.create_task(ws_to_pty())]
    try:
        await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
    finally:
        for t in tasks:
            t.cancel()
        loop.remove_reader(fd)
        for sig in (signal.SIGHUP, signal.SIGKILL):
            try:
                os.kill(pid, sig)
            except ProcessLookupError:
                break
        try:
            os.waitpid(pid, 0)
        except ChildProcessError:
            pass
        os.close(fd)


async def main():
    server = await asyncio.start_server(handle, HOST, PORT)
    print(f"claudeterm bridge on {HOST}:{PORT} (login={ALLOWED_LOGIN}, origins={sorted(ALLOWED_ORIGINS)})", flush=True)
    async with server:
        await server.serve_forever()


if __name__ == "__main__":
    asyncio.run(main())
