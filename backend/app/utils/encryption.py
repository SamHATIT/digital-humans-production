"""
Credential Encryption Service
Uses Fernet (AES-128-CBC) for symmetric encryption.
Based on SPEC Section 7.1

SECRET KEY ROTATION PROCEDURE
==============================

The migration script referenced below EXISTS: ``backend/scripts/rotate_encryption_key.py``
(LOT-E / P8 — it used to be a "TODO", i.e. a documented procedure with no
capability behind it).

1. Generate a new Fernet key:
       python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

2. Re-encrypt every credential in the database, old key -> new key:
       python scripts/rotate_encryption_key.py --new-key <new-key>          # dry-run
       python scripts/rotate_encryption_key.py --new-key <new-key> --apply

   The script verifies that every row round-trips through the new key
   before committing, and rolls the whole transaction back otherwise.

3. Set CREDENTIALS_ENCRYPTION_KEY in .env to the new key and restart.

4. Re-run the script with --verify-only to confirm every row decrypts.

IMPORTANT:
- Changing SECRET_KEY (in .env) invalidates ALL existing JWT tokens.
  All users will need to re-authenticate.
- Changing CREDENTIALS_ENCRYPTION_KEY invalidates ALL encrypted
  credentials in the database.  They MUST be re-encrypted (step 2) before
  the old key is discarded.

CONFIGURATION SOURCE (LOT-E)
============================
Keys are read from ``app.config.settings``, which loads a single ``.env``.
Reading ``os.environ`` directly meant a key present in ``backend/.env`` but
not exported was invisible here, silently falling through to another key.
"""
from cryptography.fernet import Fernet, InvalidToken
import base64
import hashlib
import logging
from typing import Optional

from app.config import settings

logger = logging.getLogger(__name__)

# Prefixes of provider tokens that must NEVER appear in
# `project_credentials.encrypted_value`. A value starting with one of these has
# never been encrypted (cla:SEC-03). Single definition, shared by the consumers
# that must refuse such a value and by scripts/rotate_encryption_key.py, which
# migrates them.
PLAINTEXT_TOKEN_PREFIXES = ("ghp_", "github_pat_", "glpat-", "gho_", "ghs_")


def looks_like_plaintext_token(value: str) -> bool:
    """True when a stored credential is a bare provider token, not ciphertext."""
    return bool(value) and value.startswith(PLAINTEXT_TOKEN_PREFIXES)


def build_fernet(key: str) -> Fernet:
    """
    Build a Fernet from an arbitrary key string.

    A well-formed 32-byte urlsafe-base64 Fernet key is used as-is; anything
    else is stretched through SHA-256. Exposed at module level so the
    rotation script can hold the OLD and the NEW key side by side without
    touching the process-wide singleton.
    """
    try:
        return Fernet(key.encode())
    except Exception:
        key_bytes = hashlib.sha256(key.encode()).digest()
        return Fernet(base64.urlsafe_b64encode(key_bytes))


def derive_fernet_from_secret_key(secret_key: str) -> Fernet:
    """
    Reproduce the legacy SECRET_KEY-derived encryption key.

    Kept so `scripts/rotate_encryption_key.py` can read credentials written
    by an older deployment that never had a CREDENTIALS_ENCRYPTION_KEY.
    """
    key_bytes = hashlib.sha256(secret_key.encode()).digest()
    return Fernet(base64.urlsafe_b64encode(key_bytes))


class CredentialEncryption:
    """
    Gestionnaire de chiffrement pour les credentials sensibles.
    Utilise Fernet (AES-128-CBC) pour le chiffrement symétrique.
    """

    def __init__(self):
        self._fernet = None

    @property
    def fernet(self) -> Fernet:
        if self._fernet is None:
            # Single source of truth: app.config.settings (one .env).
            key = settings.CREDENTIALS_ENCRYPTION_KEY

            if key:
                self._fernet = build_fernet(key)
            else:
                # Legacy: derive from SECRET_KEY. config.validate_encryption_key
                # forbids this in production (DEBUG=False); it survives here
                # only so existing DEBUG environments keep reading their data
                # until they run scripts/rotate_encryption_key.py.
                secret_key = settings.SECRET_KEY
                if not secret_key:
                    raise ValueError(
                        "CREDENTIALS_ENCRYPTION_KEY is not set. "
                        "Generate one with: python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'"
                    )
                logger.warning(
                    "CREDENTIALS_ENCRYPTION_KEY is not set — falling back to a key "
                    "derived from SECRET_KEY. Every stored credential becomes "
                    "undecryptable if SECRET_KEY changes. Set a dedicated key and "
                    "run scripts/rotate_encryption_key.py."
                )
                self._fernet = derive_fernet_from_secret_key(secret_key)

        return self._fernet
    
    def encrypt(self, plaintext: str) -> Optional[str]:
        """
        Encrypt a string and return base64-encoded ciphertext.
        
        Args:
            plaintext: The string to encrypt
            
        Returns:
            Base64-encoded encrypted string, or None if plaintext is empty
        """
        if not plaintext:
            return None
        
        encrypted = self.fernet.encrypt(plaintext.encode())
        return base64.urlsafe_b64encode(encrypted).decode()
    
    def decrypt(self, ciphertext: str) -> Optional[str]:
        """
        Decrypt a base64-encoded ciphertext.
        
        Args:
            ciphertext: The encrypted string to decrypt
            
        Returns:
            Decrypted plaintext, or None if ciphertext is empty
            
        Raises:
            ValueError: If decryption fails
        """
        if not ciphertext:
            return None
        
        try:
            decoded = base64.urlsafe_b64decode(ciphertext.encode())
            decrypted = self.fernet.decrypt(decoded)
            return decrypted.decode()
        except InvalidToken:
            raise ValueError("Failed to decrypt credential: Invalid token or key")
        except Exception as e:
            raise ValueError(f"Failed to decrypt credential: {e}")


# Singleton instance
_encryption = None


def get_encryption() -> CredentialEncryption:
    """Get the encryption service singleton."""
    global _encryption
    if _encryption is None:
        _encryption = CredentialEncryption()
    return _encryption


# Convenience functions (spec-compliant naming)
def encrypt_credential(plaintext: str) -> Optional[str]:
    """Encrypt a credential value."""
    return get_encryption().encrypt(plaintext)


def decrypt_credential(ciphertext: str) -> Optional[str]:
    """Decrypt a credential value."""
    return get_encryption().decrypt(ciphertext)


# Alias for backwards compatibility
def encrypt_value(plaintext: str) -> str:
    """Encrypt a value (alias for encrypt_credential)."""
    return encrypt_credential(plaintext) or ""


def decrypt_value(ciphertext: str) -> Optional[str]:
    """Decrypt a value (alias for decrypt_credential)."""
    return decrypt_credential(ciphertext)


# Generate new encryption key utility
def generate_encryption_key() -> str:
    """Generate a new Fernet encryption key."""
    return Fernet.generate_key().decode()


# Test
if __name__ == "__main__":
    print("Testing CredentialEncryption...")
    
    encryption = get_encryption()
    
    test_value = "my-secret-access-token-12345"
    encrypted = encryption.encrypt(test_value)
    decrypted = encryption.decrypt(encrypted)
    
    print(f"Original:  {test_value}")
    print(f"Encrypted: {encrypted[:50]}...")
    print(f"Decrypted: {decrypted}")
    print(f"Match: {test_value == decrypted}")
    
    # Test convenience functions
    encrypted2 = encrypt_credential("another-secret")
    decrypted2 = decrypt_credential(encrypted2)
    print(f"\nConvenience functions work: {decrypted2 == 'another-secret'}")
    
    print("\n✅ Encryption service working correctly")
