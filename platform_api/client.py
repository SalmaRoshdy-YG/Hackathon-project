import json
import os
from pathlib import Path

import httpx
from dotenv import load_dotenv

load_dotenv()


def connect(base_url=None, token_env="MEMORY_TOKEN"):
    return httpx.Client(base_url=base_url or os.getenv("MEMORY_API_URL", "http://127.0.0.1:8000"),
                        headers={"Authorization": "Bearer " + os.environ[token_env]}, timeout=40,
                        trust_env=False)


def require(response):
    if response.is_error:
        raise ValueError(f"{response.request.method} {response.request.url.path}: "
                         f"{response.status_code} {response.json().get('detail', '')}")
    return response.json()


def save(data, path=None):
    raw = json.dumps(data, indent=2, ensure_ascii=False)
    if path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(raw+"\n", encoding="utf-8")
    print(raw)
