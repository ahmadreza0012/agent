"""
Secret Manager - Secure handling of secrets.

This module provides encryption and secure storage for sensitive configuration values.
Secrets are encrypted at rest using Fernet (symmetric encryption) and can be loaded
from environment variables or encrypted storage files.

Features:
- Encrypt secrets at rest
- Decrypt on demand
- Environment variable fallback
- Master key protection via PBKDF2 key derivation
"""

import os
import json
import base64
import hashlib
from typing import Optional, Dict, Any
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class SecretManager:
    """
    Secure secret management with encryption.
    
    Features:
    - Encrypt secrets at rest
    - Decrypt on demand
    - Environment variable fallback
    - Master key protection
    """
    
    def __init__(self, key_path: Optional[str] = None, env_prefix: str = "TRADING_"):
        self.env_prefix = env_prefix
        self.key_path = key_path or "data/secret.key"
        self._cipher = None
        self._initialize_cipher()
    
    def _initialize_cipher(self):
        """Initialize encryption cipher."""
        if os.path.exists(self.key_path):
            with open(self.key_path, 'rb') as f:
                key = f.read()
        else:
            # Generate new key from environment or create one
            master_key = os.environ.get(f"{self.env_prefix}MASTER_KEY")
            if master_key:
                key = self._derive_key(master_key)
            else:
                key = Fernet.generate_key()
            
            Path(self.key_path).parent.mkdir(parents=True, exist_ok=True)
            with open(self.key_path, 'wb') as f:
                f.write(key)
        
        self._cipher = Fernet(key)
    
    def _derive_key(self, master_key: str) -> bytes:
        """Derive encryption key from master key."""
        salt = os.environ.get(f"{self.env_prefix}SALT", "trading_system_salt").encode()
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(master_key.encode()))
        return key
    
    def encrypt(self, value: str) -> str:
        """Encrypt a secret."""
        if not self._cipher:
            raise RuntimeError("Cipher not initialized")
        return self._cipher.encrypt(value.encode()).decode()
    
    def decrypt(self, encrypted: str) -> str:
        """Decrypt a secret."""
        if not self._cipher:
            raise RuntimeError("Cipher not initialized")
        return self._cipher.decrypt(encrypted.encode()).decode()
    
    def get_secret(self, key: str, encrypted_value: Optional[str] = None) -> Optional[str]:
        """Get a secret from encrypted value or environment."""
        if encrypted_value:
            try:
                return self.decrypt(encrypted_value)
            except Exception as e:
                logger.warning(f"Failed to decrypt secret {key}: {e}")
                return None
        
        # Fallback to environment variable
        env_key = f"{self.env_prefix}{key.upper()}"
        return os.environ.get(env_key)
    
    def store_encrypted(self, key: str, value: str, file_path: str = "data/encrypted_secrets.json") -> bool:
        """Store encrypted secret in file."""
        try:
            encrypted = self.encrypt(value)
            
            # Load existing secrets
            secrets = {}
            if os.path.exists(file_path):
                with open(file_path, 'r') as f:
                    secrets = json.load(f)
            
            secrets[key] = encrypted
            
            # Save
            with open(file_path, 'w') as f:
                json.dump(secrets, f, indent=2)
            
            return True
        except Exception as e:
            logger.error(f"Failed to store secret {key}: {e}")
            return False
    
    def load_encrypted(self, key: str, file_path: str = "data/encrypted_secrets.json") -> Optional[str]:
        """Load and decrypt secret from file."""
        try:
            if not os.path.exists(file_path):
                return None
            
            with open(file_path, 'r') as f:
                secrets = json.load(f)
            
            encrypted = secrets.get(key)
            if encrypted:
                return self.decrypt(encrypted)
            return None
        except Exception as e:
            logger.error(f"Failed to load secret {key}: {e}")
            return None
    
    def has_secret(self, key: str, file_path: str = "data/encrypted_secrets.json") -> bool:
        """Check if secret exists."""
        try:
            if not os.path.exists(file_path):
                return False
            with open(file_path, 'r') as f:
                secrets = json.load(f)
            return key in secrets
        except Exception:
            return False


# --- Singleton ---
_secret_manager: Optional[SecretManager] = None

def get_secret_manager(key_path: Optional[str] = None) -> SecretManager:
    """Get singleton secret manager."""
    global _secret_manager
    if _secret_manager is None:
        _secret_manager = SecretManager(key_path)
    return _secret_manager


# --- Convenience Functions ---
def get_required_secret(key: str, encrypted_value: Optional[str] = None) -> str:
    """Get a required secret, raise error if missing."""
    manager = get_secret_manager()
    value = manager.get_secret(key, encrypted_value)
    if value is None:
        raise ValueError(f"Required secret not found: {key}")
    return value


def get_optional_secret(key: str, encrypted_value: Optional[str] = None, default: Optional[str] = None) -> Optional[str]:
    """Get an optional secret with default."""
    manager = get_secret_manager()
    return manager.get_secret(key, encrypted_value) or default
