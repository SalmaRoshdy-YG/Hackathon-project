"""Provision and check the MongoDB indexes and configured embedding provider."""
import argparse
import os
from time import monotonic, sleep

from platform_api.client import save
from platform_api.config import identities
from platform_api.embedding import DIMENSIONS, embed, index_name, model
from platform_api.store import Store


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", help="Optional path for the check results")
    args = parser.parse_args()
    principals = identities()
    store = Store(os.environ["MEMORY_ATLAS_URI"], os.environ["MEMORY_ATLAS_DB"])
    try:
        store.client.admin.command("ping")
        store.setup()
        deadline = monotonic() + 95
        while store.index_state() != "READY":
            if monotonic() >= deadline:
                raise RuntimeError("Atlas vector index is not queryable")
            sleep(0.5)
        vector = embed("Atlas embedding preflight", query=True)
        project = next(iter(principals.values())).project_id
        list(store.db.result_vectors.aggregate(store.search_pipeline(project, vector, None)))
        save({"atlas": "ok", "index": index_name(), "embedding_model": model(),
              "dimensions": DIMENSIONS}, args.out)
    finally:
        store.client.close()


if __name__ == "__main__":
    main()
