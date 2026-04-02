import base64
import hashlib

from cryptography.fernet import Fernet

from app.config import settings


def _get_fernet() -> Fernet:
    key = hashlib.sha256(settings.SECRET_KEY.encode()).digest()
    return Fernet(base64.urlsafe_b64encode(key))


def encrypt_pat(plain: str) -> str:
    return _get_fernet().encrypt(plain.encode()).decode()


def decrypt_pat(token: str) -> str:
    return _get_fernet().decrypt(token.encode()).decode()
