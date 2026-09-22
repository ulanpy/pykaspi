import json
from typing import Any


def json_body(value: Any) -> str:
    """Serialize signed requests exactly as JavaScript JSON.stringify does."""
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
