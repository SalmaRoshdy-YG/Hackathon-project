import json
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Identity:
    project_id: str
    agent_id: str
    role: str


def identities():
    raw = json.loads(os.environ["MEMORY_TOKENS_JSON"])
    mapping = {}
    for token, entry in raw.items():
        identity = Identity(**entry)
        if (len(token) < 24 or identity.role not in {"publisher", "reader", "maintainer"}
                or not all(re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_.-]{0,79}", value)
                           for value in (identity.project_id, identity.agent_id))):
            raise ValueError("invalid identity configuration")
        mapping[token] = identity
    if not mapping:
        raise ValueError("configure at least one project identity")
    return mapping


def utcnow():
    return datetime.now(timezone.utc)
