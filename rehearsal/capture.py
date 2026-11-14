import argparse
import json
import time
from pathlib import Path
from urllib.request import urlopen

from playwright.sync_api import expect, sync_playwright


def capture(url, output, reject):
    output.mkdir(parents=True, exist_ok=True)

    def state():
        with urlopen(f"{url}/api/state", timeout=15) as response:
            return json.load(response)

    before = state()
    existing = {decision["decision_id"] for decision in before["decisions"]}
    started = time.monotonic()
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel="msedge", args=["--disable-renderer-backgrounding"])
        with browser.new_context(
            viewport={"width": 1440, "height": 900},
            record_video_dir=output,
            record_video_size={"width": 1440, "height": 900},
        ) as context:
            page = context.new_page()
            page.goto(url)
            expect(page.locator("#terminal-toggle")).to_be_enabled(timeout=30_000)
            page.screenshot(path=output / "01-past.png")
            page.locator("#terminal-toggle").click()
            page.wait_for_timeout(4500)
            page.locator("#send-prompt").click()
            page.wait_for_timeout(750)
            page.locator('.xterm-helper-textarea').press('Enter')
            page.wait_for_timeout(3000)
            deadline = time.monotonic() + 110
            while time.monotonic() < deadline:
                current = state()
                pending = next((item for item in current["decisions"]
                                if item["decision_id"] not in existing and item["status"] == "pending"), None)
                if pending:
                    break
                page.wait_for_timeout(1000)
            else:
                page.screenshot(path=output / "terminal-timeout.png")
                raise RuntimeError("Codex did not submit a fresh pending plan.")
            (output / "plan.json").write_text(json.dumps(pending, indent=2), encoding="utf-8")
            page.locator('[data-stage="decide"]').click()
            expect(page.locator("#reject-plan")).to_be_visible(timeout=15000)
            page.locator("#reject-plan").scroll_into_view_if_needed()
            page.screenshot(path=output / "02-plan.png")
            job = pending["job_id"]
            print("Codex proposed:", job, flush=True)
            if not reject and job != "reuse":
                raise RuntimeError("Expected reuse. The plan remains unapproved.")
            page.wait_for_timeout(2200)
            page.locator("#reject-plan" if reject else "#run-plan").click()
            deadline = time.monotonic() + 100
            while time.monotonic() < deadline:
                current = state()
                result = next(item for item in current["decisions"] if item["decision_id"] == pending["decision_id"])
                if result["status"] in {"executed", "rejected", "aborted"}:
                    break
                page.wait_for_timeout(1000)
            else:
                raise RuntimeError("Decision did not reach a final state.")
            elapsed = time.monotonic() - started
            (output / "result.json").write_text(json.dumps({
                "baseline": current["baseline"], "decision": result, "wall_seconds": elapsed,
                "new_findings": [item for item in current["findings"]
                                 if item["result_id"] not in {row["result_id"] for row in before["findings"]}],
            }, indent=2), encoding="utf-8")
            page.locator('[data-stage="result"]').click()
            page.wait_for_timeout(1200)
            page.screenshot(path=output / "03-result.png")
            print(f"{result['status']} in {elapsed:.1f}s", flush=True)
            page.wait_for_timeout(7000)
            video = page.video
            page.close()
            video.save_as(output / "workbench.webm")
        browser.close()
    expected = "rejected" if reject else "executed"
    if result["status"] != expected:
        raise RuntimeError(f"Expected {expected}, got {result['status']}.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Capture a real Codex and Atlas workbench run.")
    parser.add_argument("--url", default="http://127.0.0.1:18124")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--reject", action="store_true")
    options = parser.parse_args()
    capture(options.url, options.out, options.reject)
