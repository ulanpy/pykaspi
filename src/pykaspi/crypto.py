from __future__ import annotations

import base64
import hashlib
import hmac
import time
from dataclasses import dataclass

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec

from .device import DeviceIdentity


VTOKEN_SUITE = b"OCRA-1:HOTP-SHA256-6:QH64-T1M"


@dataclass(slots=True)
class EcdhKeyPair:
    private_key: ec.EllipticCurvePrivateKey

    @classmethod
    def generate(cls) -> "EcdhKeyPair":
        return cls(ec.generate_private_key(ec.SECP256R1()))

    @property
    def x509(self) -> str:
        public_der = self.private_key.public_key().public_bytes(
            encoding=serialization.Encoding.DER,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        return base64.b64encode(public_der).decode()

    def complete(self, server_x509_b64: str) -> bytes:
        server_public = serialization.load_der_public_key(base64.b64decode(server_x509_b64))
        if not isinstance(server_public, ec.EllipticCurvePublicKey):
            raise TypeError("server x509 must be an EC public key")
        return self.private_key.exchange(ec.ECDH(), server_public)


def compute_token_sn_mac(token_sn: str | None, secret: bytes | None) -> str:
    if not secret:
        return "000000"

    time_step = int(time.time() * 1000) // 30000
    time_hex = f"{time_step:x}"
    q_hex = (token_sn or "00000000").encode().hex()[:64]

    q_bytes = bytes.fromhex(q_hex.ljust(256, "0"))
    t_bytes = bytes.fromhex(time_hex.rjust(16, "0"))
    data = VTOKEN_SUITE + b"\x00" + q_bytes + t_bytes
    digest = hmac.new(secret, data, hashlib.sha256).digest()

    offset = digest[-1] & 0x0F
    code = (
        ((digest[offset] & 0x7F) << 24)
        | ((digest[offset + 1] & 0xFF) << 16)
        | ((digest[offset + 2] & 0xFF) << 8)
        | (digest[offset + 3] & 0xFF)
    )
    return str(code % 1_000_000).zfill(6)


def ec_sign(data: str | bytes, device: DeviceIdentity) -> str:
    payload = data.encode() if isinstance(data, str) else data
    signature = device.private_key.sign(payload, ec.ECDSA(hashes.SHA256()))
    return base64.b64encode(signature).decode()


def sign_data_payload(data_b64: str, device: DeviceIdentity) -> str:
    return ec_sign(data_b64, device)


def compute_xsu(url: str) -> str:
    return hashlib.md5(url.lower().encode()).hexdigest()  # noqa: S324 - part of Kaspi signature protocol


def compute_x_sign(url: str, headers: dict[str, str], xsh_list: str, device: DeviceIdentity) -> str:
    parts: list[str] = []
    for name in xsh_list.split(","):
        if name == "url":
            from urllib.parse import urlsplit

            parsed = urlsplit(url)
            path = parsed.path or url
            parts.append(path + (f"?{parsed.query}" if parsed.query else ""))
        else:
            parts.append(headers.get(name, ""))
    return ec_sign("".join(parts), device)


def secret_to_base64(secret: bytes) -> str:
    return base64.b64encode(secret).decode()


def secret_from_base64(value: str) -> bytes:
    return base64.b64decode(value)
