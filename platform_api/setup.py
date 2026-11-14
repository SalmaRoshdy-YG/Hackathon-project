"""Write an untracked environment with new project identities."""
import argparse
import json
from pathlib import Path
from secrets import token_urlsafe
from uuid import uuid4


def roles(project):
    values, tokens = {}, {}
    for name, agent, role, scope in [
        ("PUBLISHER", "agent-a", "publisher", project), ("READER", "agent-b", "reader", project),
        ("MAINTAINER", "presenter", "maintainer", project), ("OTHER", "other-reader", "reader", project+"-other"),
    ]:
        token = token_urlsafe(32)
        values["MEMORY_"+name+"_TOKEN"] = token
        tokens[token] = {"project_id": scope, "agent_id": agent, "role": role}
    values["MEMORY_TOKENS_JSON"] = json.dumps(tokens, separators=(",", ":"))
    return values


def main(*, project_prefix="project", settings=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", default=".env")
    p.add_argument("--project", default=f"{project_prefix}-{uuid4().hex[:10]}")
    args = p.parse_args()
    path = Path(args.out)
    with path.open("x", encoding="utf-8") as file:
        config = {"MEMORY_ATLAS_URI": "mongodb+srv://USER:PASSWORD@HOST/?retryWrites=true&w=majority",
                  "MEMORY_ATLAS_DB": "precedent_demo", "MEMORY_EMBEDDER": "local",
                  **roles(args.project)}
        if settings:
            config.update(settings)
        for k, v in config.items():
            file.write(f"{k}={v}\n")
    print(f"Created {path}; set the Atlas connection string before starting the platform.")


if __name__ == "__main__":
    main()
