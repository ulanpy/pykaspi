from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
import tempfile
from typing import Any

from .client import KaspiClient
from .device import DeviceIdentity
from .models import KaspiSession


@dataclass(slots=True)
class KaspiTerminal:
    """A complete Kaspi terminal loaded from one secret JSON file.

    The JSON contains both the stable signing identity and the authenticated
    Kaspi session. Keep it outside source control and grant access only to the
    payment process.
    """

    device: DeviceIdentity
    session: KaspiSession

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "KaspiTerminal":
        if data.get("version") != 1:
            raise ValueError("Unsupported terminal JSON version")
        device = data.get("device")
        session = data.get("session")
        if not isinstance(device, dict) or not isinstance(session, dict):
            raise ValueError("Terminal JSON must contain device and session objects")
        return cls(DeviceIdentity.from_json(device), KaspiSession.from_dict(session))

    @classmethod
    def load(cls, path: str | Path) -> "KaspiTerminal":
        """Load one complete terminal from its JSON file."""
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))

    def to_dict(self) -> dict[str, Any]:
        """Return the JSON-compatible terminal representation."""
        return {
            "version": 1,
            "device": self.device.to_dict(),
            "session": self.session.to_dict(),
        }

    def save(self, path: str | Path) -> None:
        """Atomically save the complete terminal JSON with owner-only mode."""
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        fd, temporary = tempfile.mkstemp(dir=target.parent, prefix=f".{target.name}.")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                json.dump(self.to_dict(), stream, ensure_ascii=False, indent=2)
                stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())
            os.chmod(temporary, 0o600)
            os.replace(temporary, target)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)

    def client(self, **kwargs: Any) -> KaspiClient:
        """Create a client tied to this terminal."""
        return KaspiClient(device=self.device, **kwargs)
