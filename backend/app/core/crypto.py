"""ECDSA P-256 签名 + AES-256-GCM 密码加解密"""
import json
import os
import base64
import hashlib
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from app.config import settings


# —— ECDSA P-256 ——

def generate_ecdsa_keypair() -> ec.EllipticCurvePrivateKey:
    return ec.generate_private_key(ec.SECP256R1())


def export_private_jwk(key: ec.EllipticCurvePrivateKey) -> dict:
    numbers = key.private_numbers()
    pub = numbers.public_numbers
    return {
        "key_ops": ["sign"],
        "ext": True,
        "kty": "EC",
        "x": _b64url(pub.x.to_bytes(32, "big")),
        "y": _b64url(pub.y.to_bytes(32, "big")),
        "crv": "P-256",
        "d": _b64url(numbers.private_value.to_bytes(32, "big")),
    }


def export_public_jwk(key: ec.EllipticCurvePrivateKey) -> dict:
    pub = key.public_key().public_numbers()
    return {
        "kty": "EC",
        "x": _b64url(pub.x.to_bytes(32, "big")),
        "y": _b64url(pub.y.to_bytes(32, "big")),
        "crv": "P-256",
    }


def import_private_key(jwk: dict) -> ec.EllipticCurvePrivateKey:
    d = int.from_bytes(_b64url_decode(jwk["d"]), "big")
    return ec.derive_private_key(d, ec.SECP256R1())


def ecdsa_sign(private_key: ec.EllipticCurvePrivateKey, message: str) -> str:
    """ECDSA 签名 — DER → raw(r||s) → base64url，对齐 Web Crypto API 输出"""
    sig_der = private_key.sign(message.encode(), ec.ECDSA(hashes.SHA256()))
    r, s = decode_dss_signature(sig_der)
    sig_raw = r.to_bytes(32, "big") + s.to_bytes(32, "big")
    return _b64url(sig_raw)


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _b64url_decode(s: str) -> bytes:
    padding = 4 - len(s) % 4
    if padding != 4:
        s += "=" * padding
    return base64.urlsafe_b64decode(s)


# —— ECDSA Key Store ——

ECDSA_KEYS_FILE = "data/ecdsa_keys.json"


def load_key_store() -> dict:
    if os.path.exists(ECDSA_KEYS_FILE):
        with open(ECDSA_KEYS_FILE) as f:
            return json.load(f)
    return {}


def save_key_store(data: dict):
    os.makedirs(os.path.dirname(ECDSA_KEYS_FILE), exist_ok=True)
    with open(ECDSA_KEYS_FILE, "w") as f:
        json.dump(data, f)


# —— AES-256-GCM ——

def _derive_aes_key() -> bytes:
    return hashlib.sha256(settings.crypto_key.encode()).digest()


def encrypt_password(plaintext: str) -> str:
    key = _derive_aes_key()
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)
    ct = aesgcm.encrypt(nonce, plaintext.encode(), None)
    return base64.b64encode(nonce + ct).decode()


def decrypt_password(cipher_b64: str) -> str:
    if not cipher_b64:
        return ""
    try:
        key = _derive_aes_key()
        aesgcm = AESGCM(key)
        raw = base64.b64decode(cipher_b64)
        # Try Python format: nonce[12] + ct[includes 16-byte tag]
        try:
            return aesgcm.decrypt(raw[:12], raw[12:], None).decode()
        except Exception:
            pass
        # Try Node.js format: iv[12] + tag[16] + ciphertext
        try:
            nonce = raw[:12]
            tag = raw[12:28]
            ct = raw[28:]
            return aesgcm.decrypt(nonce, ct + tag, None).decode()
        except Exception:
            pass
        return ""
    except Exception:
        return ""
