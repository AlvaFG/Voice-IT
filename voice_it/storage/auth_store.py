"""
Voice IT - Authentication Store
Secure credential storage using file-based storage for cookies (due to Windows
size limits) and keyring for smaller tokens.

Cookies are encrypted at rest with Fernet (symmetric AES). The encryption key
itself is stored in the OS keyring (Windows Credential Manager), so the cookie
files on disk are useless on their own.
"""

import json
import logging
import os
import threading
from pathlib import Path
from typing import Optional

try:
    import keyring
except ImportError:
    keyring = None

try:
    from cryptography.fernet import Fernet, InvalidToken
except ImportError:
    Fernet = None

    class InvalidToken(Exception):
        """Fallback so `except InvalidToken` is valid when cryptography is absent."""

from platformdirs import user_data_dir
from voice_it import __app_name__

# Fernet tokens are urlsafe-base64 of a structure that always begins with the
# version byte 0x80 -> the encoded text always starts with "gAAAAA".
_FERNET_PREFIX = b"gAAAAA"

logger = logging.getLogger(__name__)


class AuthStore:
    """
    Secure credential storage for Voice IT.
    Uses file-based storage for cookies (Windows Credential Manager has size limits)
    and keyring for smaller tokens.
    """

    SERVICE_NAME = "VoiceIT"
    # keyring key under which the Fernet cookie-encryption key is stored
    _ENCRYPTION_KEY_NAME = "cookie_encryption_key"

    def __init__(self):
        """Initialize the authentication store."""
        if keyring is None:
            raise ImportError(
                "keyring not installed. Run: pip install keyring"
            )

        # Create secure storage directory for cookies
        self._data_dir = Path(user_data_dir(__app_name__))
        self._credentials_dir = self._data_dir / "credentials"
        self._credentials_dir.mkdir(parents=True, exist_ok=True)

        self._fernet: Optional[Fernet] = None
        # Serializes cookie-file I/O (reads, writes, migration) across threads.
        # RLock because get_cookies() may call save_cookies() during migration.
        self._cookie_lock = threading.RLock()

    def _get_key(self, provider: str, token_type: str) -> str:
        """Generate a unique key for the credential."""
        return f"{provider}_{token_type}"

    # ========== Encryption ==========

    def _get_fernet(self) -> Fernet:
        """
        Get (or lazily create) the Fernet cipher used to encrypt cookie files.
        The key is persisted in the OS keyring.
        """
        if self._fernet is not None:
            return self._fernet

        if Fernet is None:
            raise ImportError(
                "cryptography not installed. Run: pip install cryptography"
            )

        key = keyring.get_password(self.SERVICE_NAME, self._ENCRYPTION_KEY_NAME)
        if not key:
            key = Fernet.generate_key().decode("utf-8")
            keyring.set_password(self.SERVICE_NAME, self._ENCRYPTION_KEY_NAME, key)
            logger.debug("AuthStore: generated new cookie encryption key")

        try:
            self._fernet = Fernet(key.encode("utf-8"))
        except (ValueError, TypeError):
            # Stored key is corrupt/invalid -> regenerate so the app can keep
            # working. Existing ciphertext becomes unrecoverable, but it already
            # was with a broken key (user just needs to reconnect providers).
            logger.warning("AuthStore: stored encryption key was invalid; regenerating")
            key = Fernet.generate_key().decode("utf-8")
            keyring.set_password(self.SERVICE_NAME, self._ENCRYPTION_KEY_NAME, key)
            self._fernet = Fernet(key.encode("utf-8"))

        return self._fernet

    def save_token(self, provider: str, token_type: str, token: str) -> bool:
        """
        Save a token to the keyring.

        Args:
            provider: Provider name (e.g., "claude", "chatgpt", "gemini")
            token_type: Token type (e.g., "session_cookies", "access_token")
            token: The token value to store

        Returns:
            True if successful, False otherwise
        """
        try:
            key = self._get_key(provider, token_type)
            keyring.set_password(self.SERVICE_NAME, key, token)
            # Verify it was saved
            verify = keyring.get_password(self.SERVICE_NAME, key)
            logger.debug("AuthStore.save_token: key=%s, verified=%s", key, verify is not None)
            return True
        except Exception as e:
            logger.error("Error saving token: %s", e, exc_info=True)
            return False

    def get_token(self, provider: str, token_type: str) -> Optional[str]:
        """
        Retrieve a token from the keyring.

        Args:
            provider: Provider name
            token_type: Token type

        Returns:
            The token value or None if not found
        """
        try:
            key = self._get_key(provider, token_type)
            result = keyring.get_password(self.SERVICE_NAME, key)
            logger.debug("AuthStore.get_token: key=%s, found=%s", key, result is not None)
            return result
        except Exception as e:
            logger.error("Error getting token: %s", e, exc_info=True)
            return None

    def delete_token(self, provider: str, token_type: str) -> bool:
        """
        Delete a token from the keyring.

        Args:
            provider: Provider name
            token_type: Token type

        Returns:
            True if successful, False otherwise
        """
        try:
            key = self._get_key(provider, token_type)
            keyring.delete_password(self.SERVICE_NAME, key)
            return True
        except keyring.errors.PasswordDeleteError:
            # Token doesn't exist, which is fine
            return True
        except Exception as e:
            logger.error("Error deleting token: %s", e)
            return False

    def _get_cookie_file(self, provider: str) -> Path:
        """Get the path to the cookie file for a provider."""
        return self._credentials_dir / f"{provider}_cookies.json"

    def save_cookies(self, provider: str, cookies: list) -> bool:
        """
        Save browser cookies to an encrypted file.
        Uses file storage because Windows Credential Manager has size limits (~2500 bytes).

        Args:
            provider: Provider name
            cookies: List of cookie dictionaries

        Returns:
            True if successful, False otherwise
        """
        try:
            cookie_file = self._get_cookie_file(provider)
            payload = json.dumps(cookies).encode("utf-8")
            encrypted = self._get_fernet().encrypt(payload)

            # Write atomically (temp file + os.replace) so a concurrent reader
            # never sees a half-written, undecryptable file.
            tmp_file = cookie_file.with_name(cookie_file.name + ".tmp")
            with self._cookie_lock:
                with open(tmp_file, "wb") as f:
                    f.write(encrypted)
                os.replace(tmp_file, cookie_file)

            logger.debug("AuthStore.save_cookies(%s): saved %d cookies (encrypted)", provider, len(cookies))
            return True

        except Exception as e:
            logger.error("Error saving cookies: %s", e, exc_info=True)
            return False

    def get_cookies(self, provider: str) -> Optional[list]:
        """
        Retrieve browser cookies from the encrypted file.

        Transparently migrates legacy plaintext-JSON cookie files: if the file
        can't be decrypted but parses as plain JSON, it's re-saved encrypted.

        Args:
            provider: Provider name

        Returns:
            List of cookie dictionaries or None
        """
        try:
            with self._cookie_lock:
                cookie_file = self._get_cookie_file(provider)

                if not cookie_file.exists():
                    logger.debug("AuthStore.get_cookies(%s): file not found", provider)
                    return None

                raw = cookie_file.read_bytes()

                # Preferred path: decrypt.
                try:
                    decrypted = self._get_fernet().decrypt(raw)
                    cookies = json.loads(decrypted.decode("utf-8"))
                    logger.debug("AuthStore.get_cookies(%s): loaded %d cookies", provider, len(cookies))
                    return cookies
                except InvalidToken:
                    # The file is a Fernet token we can't decrypt -> the
                    # encryption key was lost/rotated. Don't mistake it for a
                    # legacy plaintext file; tell the user to reconnect.
                    if raw[:len(_FERNET_PREFIX)] == _FERNET_PREFIX:
                        logger.warning(
                            "AuthStore.get_cookies(%s): cookies are encrypted with a "
                            "different/lost key and cannot be decrypted. Please reconnect "
                            "this provider.",
                            provider,
                        )
                        return None
                    # Otherwise fall through: likely a legacy plaintext file.

                # Legacy migration: old plaintext JSON (a list of cookies).
                try:
                    cookies = json.loads(raw.decode("utf-8"))
                except (ValueError, UnicodeDecodeError):
                    logger.error("AuthStore.get_cookies(%s): file is neither decryptable nor valid JSON", provider)
                    return None

                if not isinstance(cookies, list):
                    logger.error("AuthStore.get_cookies(%s): legacy cookie file is not a JSON list; ignoring", provider)
                    return None

                logger.info("AuthStore.get_cookies(%s): migrating legacy plaintext cookies to encrypted storage", provider)
                if not self.save_cookies(provider, cookies):
                    logger.warning(
                        "AuthStore.get_cookies(%s): migration re-save failed; cookie file left as plaintext",
                        provider,
                    )
                return cookies

        except Exception as e:
            logger.error("Error getting cookies: %s", e, exc_info=True)
            return None

    def delete_cookies(self, provider: str) -> bool:
        """
        Delete stored browser cookies.

        Args:
            provider: Provider name

        Returns:
            True if successful, False otherwise
        """
        try:
            with self._cookie_lock:
                cookie_file = self._get_cookie_file(provider)
                if cookie_file.exists():
                    cookie_file.unlink()
            return True
        except Exception as e:
            logger.error("Error deleting cookies: %s", e)
            return False

    def has_credentials(self, provider: str) -> bool:
        """
        Check if credentials exist for a provider.

        Args:
            provider: Provider name

        Returns:
            True if credentials exist, False otherwise
        """
        # Check for API key first (for providers like Groq)
        api_key = self.get_token(provider, "api_key")
        if api_key:
            logger.debug("AuthStore.has_credentials(%s): has API key", provider)
            return True

        # Check if cookie file exists (for browser-based providers)
        cookie_file = self._get_cookie_file(provider)
        file_exists = cookie_file.exists()

        if file_exists:
            # Verify the file has valid content
            cookies = self.get_cookies(provider)
            result = cookies is not None and len(cookies) > 0
        else:
            result = False

        logger.debug("AuthStore.has_credentials(%s): file_exists=%s, result=%s", provider, file_exists, result)
        return result

    def clear_provider(self, provider: str) -> bool:
        """
        Clear all credentials for a provider.

        Args:
            provider: Provider name

        Returns:
            True if successful, False otherwise
        """
        success = True

        # Delete cookie file
        if not self.delete_cookies(provider):
            success = False

        # Delete any tokens from keyring
        for token_type in ["session", "access_token", "refresh_token"]:
            if not self.delete_token(provider, token_type):
                success = False

        return success


# Global auth store instance
_auth_store: Optional[AuthStore] = None


def get_auth_store() -> AuthStore:
    """Get the global authentication store instance."""
    global _auth_store
    if _auth_store is None:
        _auth_store = AuthStore()
        logger.debug("get_auth_store: created AuthStore id=%s", id(_auth_store))
    return _auth_store
