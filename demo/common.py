"""Process boundary shared by the presenter and rehearsal."""
import json
import os
import subprocess
import sys

from benchmark.client import connect


def run_agent(module, token_env, *args):
    allowed = {"PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "USERPROFILE", "LOCALAPPDATA",
               "APPDATA", "MEMORY_API_URL", "MEMORY_PLANNER", "SSL_CERT_FILE"}
    if module == "benchmark.agent":
        allowed.add("OPENAI_API_KEY")
    child = {k: v for k, v in os.environ.items() if k.upper() in allowed}
    child.update(MEMORY_TOKEN=os.environ[token_env], PYTHONUTF8="1", PYTHONUNBUFFERED="1")
    # Do not allow dotenv to reintroduce other roles in a child process.
    child["PYTHON_DOTENV_DISABLED"] = "1"
    result = subprocess.run([sys.executable, "-m", module, *args], env=child,
                            capture_output=True, text=True, encoding="utf-8", timeout=100)
    if result.returncode:
        raise RuntimeError(f"{module} failed (exit {result.returncode})")
    return json.loads(result.stdout)


def client(role):
    return connect(token_env=f"MEMORY_{role.upper()}_TOKEN")
