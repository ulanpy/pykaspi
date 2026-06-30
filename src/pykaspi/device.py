from __future__ import annotations

import base64
import hashlib
import json
import secrets
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec


EcPrivateKey = ec.EllipticCurvePrivateKey
EcPublicKey = ec.EllipticCurvePublicKey


@dataclass(slots=True)
class DeviceIdentity:
    """Stable virtual Kaspi Pay mobile device identity.

    Kaspi's private API ties sessions and signatures to a device-like identity:
    `device_id`, `install_id`, `pin_hash`, and an EC P-256 signing key. Generate
    this once per merchant/cashier integration and store it securely. Replacing
    it makes Kaspi see a new device and may require SMS re-auth.
    """

    device_id: str
    install_id: str
    pin_hash: str
    private_key: EcPrivateKey

    @classmethod
    def generate(cls) -> "DeviceIdentity":
        """Generate a new local device identity without writing it to disk."""
        private_key = ec.generate_private_key(ec.SECP256R1())
        return cls(
            device_id=str(uuid.uuid4()).upper(),
            install_id=str(uuid.uuid4()).upper(),
            pin_hash=hashlib.md5(secrets.token_bytes(16)).hexdigest(),  # noqa: S324 - mirrors Kaspi client payload
            private_key=private_key,
        )

    @classmethod
    def from_json(cls, data: str | bytes | bytearray | dict[str, Any]) -> "DeviceIdentity":
        """Load a device identity from a JSON string/bytes or dictionary."""
        raw = json.loads(data) if not isinstance(data, dict) else data
        private_der = base64.b64decode(raw["privateKey"])
        private_key = serialization.load_der_private_key(private_der, password=None)
        if not isinstance(private_key, ec.EllipticCurvePrivateKey):
            raise TypeError("privateKey must be an EC private key")
        return cls(
            device_id=raw["deviceId"],
            install_id=raw["installId"],
            pin_hash=raw["pinHash"],
            private_key=private_key,
        )

    @classmethod
    def load(cls, path: str | Path) -> "DeviceIdentity":
        """Load a device identity from a JSON file."""
        return cls.from_json(Path(path).read_text())

    def to_dict(self) -> dict[str, str]:
        """Serialize this device identity to a JSON-compatible dictionary."""
        private_der = self.private_key.private_bytes(
            encoding=serialization.Encoding.DER,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
        public_der = self.private_key.public_key().public_bytes(
            encoding=serialization.Encoding.DER,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        return {
            "deviceId": self.device_id,
            "installId": self.install_id,
            "pinHash": self.pin_hash,
            "privateKey": base64.b64encode(private_der).decode(),
            "publicKey": base64.b64encode(public_der).decode(),
        }

    def save(self, path: str | Path) -> None:
        """Save this device identity to a JSON file.

        The resulting file contains signing credentials and should be treated as
        a secret.
        """
        Path(path).write_text(json.dumps(self.to_dict(), indent=2))

    @property
    def public_key(self) -> EcPublicKey:
        """Return the EC public key associated with the device private key."""
        return self.private_key.public_key()

    @property
    def x509(self) -> str:
        """Return the device public key as base64 DER SubjectPublicKeyInfo."""
        public_der = self.public_key.public_bytes(
            encoding=serialization.Encoding.DER,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        return base64.b64encode(public_der).decode()

    @property
    def pk(self) -> str:
        """Return the uncompressed EC public key point used in entrance cookies."""
        point = self.public_key.public_bytes(
            encoding=serialization.Encoding.X962,
            format=serialization.PublicFormat.UncompressedPoint,
        )
        return base64.b64encode(point).decode()

    @property
    def pk_tag(self) -> str:
        """Return Kaspi's MD5 tag for the `pk` cookie/header value."""
        return hashlib.md5(self.pk.encode()).hexdigest()  # noqa: S324 - part of Kaspi signature protocol
