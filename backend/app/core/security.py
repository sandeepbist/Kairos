"""Security and Encryption Vault: AES-256 Fernet token encryption."""
import base64
from cryptography.fernet import Fernet, MultiFernet
from app.config import settings


def get_fernet_cipher() -> MultiFernet:
    """MultiFernet([current, previous]): reads decrypt with either key,
    ALL NEW WRITES encrypt with the current key (MultiFernet semantics) —
    the zero-downtime rotation shape. ENCRYPTION_KEY_PREVIOUS is only set
    while a rotation is in flight."""
    def _to_fernet(raw: str) -> Fernet:
        key = raw.encode("utf-8")
        try:
            return Fernet(key)
        except Exception:
            # Fallback to deterministic derived 32-byte urlsafe base64 key
            derived_32 = (key.ljust(32, b"0"))[:32]
            return Fernet(base64.urlsafe_b64encode(derived_32))

    keys = [_to_fernet(settings.ENCRYPTION_KEY)]
    if settings.ENCRYPTION_KEY_PREVIOUS:
        keys.append(_to_fernet(settings.ENCRYPTION_KEY_PREVIOUS))
    return MultiFernet(keys)


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
