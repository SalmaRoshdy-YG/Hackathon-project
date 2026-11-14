"""Check the documented local and password-protected workbench entry points."""
from unittest import IsolatedAsyncioTestCase
from unittest.mock import patch

from httpx import ASGITransport, AsyncClient
from starlette.testclient import TestClient

from workbench.app import app


class WorkbenchAccessTests(IsolatedAsyncioTestCase):
    async def test_remote_password_and_mcp_scope(self):
        with patch.dict("os.environ", {"MEMORY_REMOTE_PASSWORD": "fixture-password"}):
            transport = ASGITransport(app=app, client=("192.0.2.12", 1234))
            async with AsyncClient(transport=transport, base_url="https://preview.example") as browser:
                self.assertEqual((await browser.get("/api/state")).status_code, 401)
                self.assertEqual((await browser.get("/")).status_code, 303)
                self.assertEqual((await browser.post("/login", data={"password": "wrong"})).status_code, 401)
                login = await browser.post("/login", data={"password": "fixture-password"})
                self.assertEqual(login.status_code, 303)
                self.assertEqual(login.headers["location"], "/")
                cookie = login.headers["set-cookie"].lower()
                for flag in ("secure", "httponly", "samesite=strict"):
                    self.assertIn(flag, cookie)
                self.assertEqual((await browser.get("/")).status_code, 200)
                self.assertEqual((await browser.get("/mcp")).status_code, 403)
                wrong_origin = await browser.get("/", headers={"Origin": "https://other.example"})
                self.assertEqual(wrong_origin.status_code, 403)

    async def test_without_remote_password_only_local_workbench_is_available(self):
        with patch.dict("os.environ", {"MEMORY_REMOTE_PASSWORD": ""}):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="https://preview.example") as browser:
                self.assertEqual((await browser.get("/login")).status_code, 403)
            async with AsyncClient(transport=transport, base_url="http://127.0.0.1") as browser:
                self.assertEqual((await browser.get("/")).status_code, 200)

    def test_websocket_requires_origin_and_remote_auth(self):
        from starlette.websockets import WebSocketDisconnect

        with patch.dict("os.environ", {"MEMORY_REMOTE_PASSWORD": "fixture-password"}):
            cases = (("http://127.0.0.1", {}), ("https://preview.example", {"Origin": "https://preview.example"}))
            for url, headers in cases:
                with self.subTest(url=url):
                    browser = TestClient(app, base_url=url)
                    with self.assertRaises(WebSocketDisconnect) as closed:
                        with browser.websocket_connect("/terminal/codex", headers=headers):
                            self.fail("unauthorized terminal opened")
                    self.assertEqual(closed.exception.code, 1008)
