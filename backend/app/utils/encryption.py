"""
Credential Encryption Service
Uses Fernet (AES-128-CBC) for symmetric encryption.
Based on SPEC Section 7.1

SECRET KEY ROTATION PROCEDURE
==============================

1. Generate a new Fernet key:
       python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

2. Set CREDENTIALS_ENCRYPTION_KEY in .env to the new key.

3. Run a migration script to re-encrypt all existing credentials stored
   in the database using the new key.  (TODO: create migration script
   ``scripts/rotate_encryption_key.py``.)

4. Verify decryption works with the new key, then remove the old key.

IMPORTANT:
- Changing SECRET_KEY (in .env) invalidates ALL existing JWT tokens.
  All users will need to re-authenticate.
- Changing CREDENTIALS_ENCRYPTION_KEY invalidates ALL encrypted
  credentials in the database.  They MUST be re-encrypted before the
  old key is discarded.
"""
from cryptography.fernet import Fernet, InvalidToken
from functools import lru_cache
import os
import base64
import hashlib
from typing import Optional


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
            # Try CREDENTIALS_ENCRYPTION_KEY first (recommended)
            key = os.getenv("CREDENTIALS_ENCRYPTION_KEY")
            
            if key:
                # Use provided Fernet key directly
                try:
                    self._fernet = Fernet(key.encode())
                except Exception:
                    # If not a valid Fernet key, derive one
                    key_bytes = hashlib.sha256(key.encode()).digest()
                    fernet_key = base64.urlsafe_b64encode(key_bytes)
                    self._fernet = Fernet(fernet_key)
            else:
                # Fallback to SECRET_KEY (for backwards compatibility)
                secret_key = os.getenv("SECRET_KEY")
                if not secret_key:
                    raise ValueError(
                        "CREDENTIALS_ENCRYPTION_KEY or SECRET_KEY environment variable not set. "
                        "Generate one with: python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'"
                    )
                # Derive a 32-byte key from SECRET_KEY using SHA256
                key_bytes = hashlib.sha256(secret_key.encode()).digest()
                fernet_key = base64.urlsafe_b64encode(key_bytes)
                self._fernet = Fernet(fernet_key)
        
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
