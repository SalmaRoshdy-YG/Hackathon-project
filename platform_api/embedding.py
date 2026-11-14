import math
import os
from functools import lru_cache
from threading import Lock

import httpx

DIMENSIONS = 1536
OPENAI_MODEL = "text-embedding-3-small"
LOCAL_MODEL = "BAAI/bge-small-en-v1.5"
_load_lock = Lock()


def model():
    mode = os.getenv("MEMORY_EMBEDDER", "openai")
    if mode not in {"local", "openai"}:
        raise ValueError("unknown embedding provider")
    return LOCAL_MODEL if mode == "local" else OPENAI_MODEL


def index_name():
    return "research_memory_local_v1" if model() == LOCAL_MODEL else "research_memory_v1"


@lru_cache(maxsize=1)
def local_model():
    from fastembed import TextEmbedding
    return TextEmbedding(model_name=LOCAL_MODEL, threads=2)


def embed(text, *, query=False):
    if model() == LOCAL_MODEL:
        with _load_lock:
            engine = local_model()
        instances = engine.query_embed(text) if query else engine.passage_embed([text])
        vector = next(iter(instances)).tolist()
        vector += [0.0] * (DIMENSIONS - len(vector))
    else:
        with httpx.Client(timeout=15) as client:
            response = client.post("https://api.openai.com/v1/embeddings",
                headers={"Authorization": "Bearer " + os.environ["OPENAI_API_KEY"]},
                json={"model": OPENAI_MODEL, "dimensions": DIMENSIONS, "input": text})
            response.raise_for_status()
        vector = response.json()["data"][0]["embedding"]
    if len(vector) != DIMENSIONS or not all(math.isfinite(x) for x in vector) or not any(vector):
        raise ValueError("invalid embedding")
    return vector
