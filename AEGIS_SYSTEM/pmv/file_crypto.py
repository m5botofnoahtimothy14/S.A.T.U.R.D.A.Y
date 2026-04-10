import os
import base64
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.fernet import Fernet

class FileCrypto:
    def __init__(self, passphrase: str, salt_path: str = "config/salt.dat"):
        self.salt_path = Path(salt_path)
        self.salt = self._get_or_create_salt()
        self.key = self._derive_key(passphrase)
        self.fernet = Fernet(self.key)

    def _get_or_create_salt(self) -> bytes:
        if self.salt_path.exists():
            return self.salt_path.read_bytes()
        
        # Generate a new 16-byte random salt
        new_salt = os.urandom(16)
        self.salt_path.parent.mkdir(parents=True, exist_ok=True)
        self.salt_path.write_bytes(new_salt)
        return new_salt

    def _derive_key(self, passphrase: str) -> bytes:
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=self.salt,
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(passphrase.encode()))
        return key

    def encrypt_data(self, data: bytes) -> bytes:
        return self.fernet.encrypt(data)

    def decrypt_data(self, token: bytes) -> bytes:
        return self.fernet.decrypt(token)

    def encrypt_file(self, file_path: str, destination_path: str = None):
        with open(file_path, 'rb') as f:
            data = f.read()
        encrypted_data = self.encrypt_data(data)
        dest = destination_path if destination_path else file_path
        with open(dest, 'wb') as f:
            f.write(encrypted_data)

    def decrypt_file(self, file_path: str) -> bytes:
        with open(file_path, 'rb') as f:
            encrypted_data = f.read()
        return self.decrypt_data(encrypted_data)

    def clear(self):
        """Wipes the key from memory as much as Python allows."""
        self.key = None
        self.fernet = None
