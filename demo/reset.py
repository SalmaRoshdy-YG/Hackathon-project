"""Clear one configured demo namespace; never drops shared collections or indexes."""
import argparse
import os

from platform_api.config import identities
from platform_api.store import Store


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--project", required=True)
    args = p.parse_args()
    maintainer = identities()[os.environ["MEMORY_MAINTAINER_TOKEN"]]
    if (maintainer.role != "maintainer" or args.project != maintainer.project_id
            or not args.project.startswith("demo-")):
        p.error("only the configured demo-* maintainer project can be cleared")
    store = Store(os.environ["MEMORY_ATLAS_URI"], os.environ["MEMORY_ATLAS_DB"])
    try:
        for name in ("decisions", "results", "result_versions", "result_vectors"):
            result = store.db[name].delete_many({"project_id": args.project})
            print(f"{name}: {result.deleted_count} deleted")
    finally:
        store.client.close()


if __name__ == "__main__":
    main()
