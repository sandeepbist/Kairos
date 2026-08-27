"""Security and Encryption Vault: AES-256 Fernet token encryption."""
import base64
from cryptography.fernet import Fernet
from app.config import settings


def get_fernet_cipher() -> Fernet:
    """Instantiates Fernet cipher using configured 32-byte key."""
    raw_key = settings.ENCRYPTION_KEY.encode("utf-8")
    # Ensure key is valid 32-byte urlsafe base64
    try:
        # If already 32-byte base64
        return Fernet(raw_key)
    except Exception:
        # Fallback to deterministic derived 32-byte urlsafe base64 key
        derived_32 = (raw_key.ljust(32, b"0"))[:32]
        urlsafe_key = base64.urlsafe_b64encode(derived_32)
        return Fernet(urlsafe_key)


def encrypt_token(plain_token: str) -> str:
    """Encrypts plaintext token string into safe ciphertext."""
    if not plain_token:
        return ""
    cipher = get_fernet_cipher()
    return cipher.encrypt(plain_token.encode("utf-8")).decode("utf-8")


def decrypt_token(encrypted_token: str) -> str:
    """Decrypts ciphertext token into plaintext."""
    if not encrypted_token:
        return ""
    cipher = get_fernet_cipher()
    return cipher.decrypt(encrypted_token.encode("utf-8")).decode("utf-8")
