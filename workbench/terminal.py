"""Run Codex in a temporary terminal directory."""
import asyncio
from hmac import compare_digest
from hashlib import sha256
import json
import os
from shutil import which
from tempfile import TemporaryDirectory

from fastapi import WebSocket
from starlette.websockets import WebSocketDisconnect


def executable():
    return os.getenv("MEMORY_CODEX_BIN") or which("codex")


def command(url):
    binary = executable()
    if not binary:
        raise FileNotFoundError("codex")
    return [binary, "--sandbox", "read-only", "--ask-for-approval", "never",
            "-c", "mcp_servers.precedent.url=" + json.dumps(url),
            "-c", 'mcp_servers.precedent.default_tools_approval_mode="approve"']


def access(connection):
    local = (connection.url.hostname in {"127.0.0.1", "localhost", "::1"}
             and not connection.headers.get("cf-ray"))
    expected = os.getenv("MEMORY_REMOTE_PASSWORD")
    cookie = connection.cookies.get("precedent_access", "")
    authorized = local or bool(expected and compare_digest(cookie.encode(), access_cookie(expected).encode()))
    origin = connection.headers.get("origin")
    origin_ok = not origin or origin == ("http://" if local else "https://") + connection.url.netloc
    return local, authorized, origin_ok


def access_cookie(password):
    return sha256(("precedent-preview:" + password).encode()).hexdigest()


def spawn(argv, cwd, env, rows, cols):
    if os.name == "nt":
        from winpty import PtyProcess
        process = PtyProcess.spawn(argv, cwd=cwd, env=env, dimensions=(rows, cols))
        return process, process.read, process.setwinsize
    from pexpect import EOF, spawn as posix_spawn
    process = posix_spawn(argv[0], argv[1:], cwd=cwd, env=env, encoding="utf-8",
                          dimensions=(rows, cols), timeout=None)
    def read(size):
        try:
            return process.read_nonblocking(size)
        except EOF:
            return ""
    return process, read, process.setwinsize


async def terminal(socket: WebSocket):
    local, authorized, origin_ok = access(socket)
    if not authorized or not origin_ok or not socket.headers.get("origin"):
        await socket.close(code=1008)
        return
    await socket.accept()
    allowed = {"PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "USERPROFILE", "LOCALAPPDATA",
               "APPDATA", "HOME", "LANG", "SHELL", "COMSPEC", "PATHEXT",
               "OPENAI_API_KEY", "CODEX_HOME"}
    env = {key: val for key, val in os.environ.items() if key.upper() in allowed}
    env.update(TERM="xterm-256color", COLORTERM="truecolor")
    with TemporaryDirectory(prefix="precedent-agent-") as cwd:
        try:
            mcp_url = "http://" + socket.url.netloc + "/mcp" if local else os.getenv(
                "MEMORY_LOCAL_MCP_URL", "http://127.0.0.1:8125/mcp")
            process, read, resize = spawn(command(mcp_url), cwd, env, 24, 80)
        except (OSError, RuntimeError, ValueError) as exc:
            await socket.send_text(f"\r\nCould not launch Codex: {exc}\r\n")
            await socket.close()
            return

        async def toward_browser():
            try:
                while data := await asyncio.to_thread(read, 8192):
                    await socket.send_text(data)
            except (EOFError, OSError, WebSocketDisconnect, RuntimeError):
                pass

        async def toward_cli():
            while True:
                message = await socket.receive_json()
                if isinstance(message.get("input"), str):
                    process.write(message["input"])
                elif isinstance(message.get("size"), list) and len(message["size"]) == 2:
                    rows, cols = message["size"]
                    if type(rows) is int and type(cols) is int:
                        resize(max(4, min(rows, 120)), max(20, min(cols, 300)))

        send = asyncio.create_task(toward_browser())
        receive = asyncio.create_task(toward_cli())
        try:
            await asyncio.wait((send, receive), return_when=asyncio.FIRST_COMPLETED)
        finally:
            if process.isalive():
                process.close(force=True)
            for task in (send, receive):
                task.cancel()
            await asyncio.gather(send, receive, return_exceptions=True)
            try:
                await socket.close()
            except (RuntimeError, WebSocketDisconnect):
                pass
