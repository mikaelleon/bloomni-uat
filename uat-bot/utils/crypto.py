import os
import re

from cryptography.fernet import Fernet
from dotenv import load_dotenv

load_dotenv()

_fernet: Fernet | None = None


def _get_fernet() -> Fernet:
    global _fernet
    if _fernet is None:
        key = os.getenv("FERNET_KEY", "").strip()
        if not key:
            raise RuntimeError("FERNET_KEY is not set in environment")
        _fernet = Fernet(key.encode() if isinstance(key, str) else key)
    return _fernet


def encrypt_gcash(number: str) -> str:
    return _get_fernet().encrypt(number.encode()).decode()


def decrypt_gcash(encrypted: str) -> str:
    return _get_fernet().decrypt(encrypted.encode()).decode()


def mask_gcash(number: str) -> str:
    digits = re.sub(r"\D", "", number)
    if len(digits) != 11:
        return "****"
    return f"{digits[:2]}XX****{digits[-3:]}"
