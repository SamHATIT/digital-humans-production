"""
Encryption utility for storing sensitive credentials.
Uses Fernet symmetric encryption with key derived from SECRET_KEY.
"""
import os
import base64
import hashlib
from typing import Optional
from cryptography.fernet import Fernet, InvalidToken


class EncryptionService:
    """Service for encrypting and decrypting sensitive data."""
    
    _instance = None
    _fernet: Optional[Fernet] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialize()
        return cls._instance
    
    def _initialize(self):
        """Initialize Fernet with key derived from SECRET_KEY."""
        secret_key = os.getenv("SECRET_KEY", "default-dev-key-change-in-production")
        
        # Derive a 32-byte key from SECRET_KEY using SHA256
        key_bytes = hashlib.sha256(secret_key.encode()).digest()
        fernet_key = base64.urlsafe_b64encode(key_bytes)
        
        self._fernet = Fernet(fernet_key)
    
    def encrypt(self, plaintext: str) -> str:
        """
        Encrypt a plaintext string.
        
        Args:
            plaintext: The string to encrypt
            
        Returns:
            Base64-encoded encrypted string
        """
        if not plaintext:
            return ""
        
        encrypted_bytes = self._fernet.encrypt(plaintext.encode('utf-8'))
        return encrypted_bytes.decode('utf-8')
    
    def decrypt(self, ciphertext: str) -> Optional[str]:
        """
        Decrypt a ciphertext string.
        
        Args:
            ciphertext: The encrypted string to decrypt
            
        Returns:
            Decrypted plaintext, or None if decryption fails
        """
        if not ciphertext:
            return None
        
        try:
            decrypted_bytes = self._fernet.decrypt(ciphertext.encode('utf-8'))
            return decrypted_bytes.decode('utf-8')
        except InvalidToken:
            return None
        except Exception as e:
            print(f"Decryption error: {e}")
            return None


# Singleton instance
def get_encryption_service() -> EncryptionService:
    """Get the encryption service singleton."""
    return EncryptionService()


# Convenience functions
def encrypt_value(plaintext: str) -> str:
    """Encrypt a value."""
    return get_encryption_service().encrypt(plaintext)


def decrypt_value(ciphertext: str) -> Optional[str]:
    """Decrypt a value."""
    return get_encryption_service().decrypt(ciphertext)


# Test
if __name__ == "__main__":
    service = get_encryption_service()
    
    test_value = "my-secret-token-12345"
    encrypted = service.encrypt(test_value)
    decrypted = service.decrypt(encrypted)
    
    print(f"Original:  {test_value}")
    print(f"Encrypted: {encrypted[:50]}...")
    print(f"Decrypted: {decrypted}")
    print(f"Match: {test_value == decrypted}")
