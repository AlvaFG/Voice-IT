"""
Voice IT - Authentication Store
Secure credential storage using file-based storage for cookies (due to Windows size limits)
and keyring for smaller tokens.
"""

import json
import os
from pathlib import Path
from typing import Any, Dict, Optional

try:
    import keyring
except ImportError:
    keyring = None

from platformdirs import user_data_dir
from voice_it import __app_name__


class AuthStore:
    """
    Secure credential storage for Voice IT.
    Uses file-based storage for cookies (Windows Credential Manager has size limits)
    and keyring for smaller tokens.
    """

    SERVICE_NAME = "VoiceIT"

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

    def _get_key(self, provider: str, token_type: str) -> str:
        """Generate a unique key for the credential."""
        return f"{provider}_{token_type}"

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
            print(f"[DEBUG] AuthStore.save_token: service={self.SERVICE_NAME}, key={key}, token_len={len(token)}")
            keyring.set_password(self.SERVICE_NAME, key, token)
            # Verify it was saved
            verify = keyring.get_password(self.SERVICE_NAME, key)
            print(f"[DEBUG] AuthStore.save_token: verify read back = {verify is not None}")
            return True
        except Exception as e:
            print(f"Error saving token: {e}")
            import traceback
            traceback.print_exc()
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
            print(f"[DEBUG] AuthStore.get_token: service={self.SERVICE_NAME}, key={key}, found={result is not None}")
            return result
        except Exception as e:
            print(f"Error getting token: {e}")
            import traceback
            traceback.print_exc()
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
            print(f"Error deleting token: {e}")
            return False

    def _get_cookie_file(self, provider: str) -> Path:
        """Get the path to the cookie file for a provider."""
        return self._credentials_dir / f"{provider}_cookies.json"

    def save_cookies(self, provider: str, cookies: list) -> bool:
        """
        Save browser cookies to a file.
        Uses file storage because Windows Credential Manager has size limits (~2500 bytes).

        Args:
            provider: Provider name
            cookies: List of cookie dictionaries

        Returns:
            True if successful, False otherwise
        """
        try:
            cookie_file = self._get_cookie_file(provider)
            print(f"[DEBUG] AuthStore.save_cookies({provider}): saving {len(cookies)} cookies to {cookie_file}")

            # Write cookies to file
            with open(cookie_file, "w", encoding="utf-8") as f:
                json.dump(cookies, f)

            # Verify it was saved
            if cookie_file.exists():
                print(f"[DEBUG] AuthStore.save_cookies({provider}): saved successfully")
                return True
            else:
                print(f"[DEBUG] AuthStore.save_cookies({provider}): file not created")
                return False

        except Exception as e:
            print(f"Error saving cookies: {e}")
            import traceback
            traceback.print_exc()
            return False

    def get_cookies(self, provider: str) -> Optional[list]:
        """
        Retrieve browser cookies from file.

        Args:
            provider: Provider name

        Returns:
            List of cookie dictionaries or None
        """
        try:
            cookie_file = self._get_cookie_file(provider)
            print(f"[DEBUG] AuthStore.get_cookies({provider}): checking {cookie_file}")

            if not cookie_file.exists():
                print(f"[DEBUG] AuthStore.get_cookies({provider}): file not found")
                return None

            with open(cookie_file, "r", encoding="utf-8") as f:
                cookies = json.load(f)

            print(f"[DEBUG] AuthStore.get_cookies({provider}): loaded {len(cookies)} cookies")
            return cookies

        except Exception as e:
            print(f"Error getting cookies: {e}")
            import traceback
            traceback.print_exc()
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
            cookie_file = self._get_cookie_file(provider)
            if cookie_file.exists():
                cookie_file.unlink()
            return True
        except Exception as e:
            print(f"Error deleting cookies: {e}")
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
            print(f"[DEBUG] AuthStore.has_credentials({provider}): has API key")
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

        print(f"[DEBUG] AuthStore.has_credentials({provider}): file_exists={file_exists}, result={result}")
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
        print("[DEBUG] get_auth_store: Creating new AuthStore instance")
        _auth_store = AuthStore()
        print(f"[DEBUG] get_auth_store: AuthStore id={id(_auth_store)}")
    else:
        print(f"[DEBUG] get_auth_store: Returning existing AuthStore id={id(_auth_store)}")
    return _auth_store
