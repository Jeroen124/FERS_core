# fers_core/cloud/client.py
"""
FersCloudClient — authenticate with FersCloud and manage cloud models.

Usage with API key (recommended)::

    from fers_core.cloud import FersCloudClient

    cloud = FersCloudClient()
    cloud.connect(api_key="clxyz123.AbCdEf...")

    # Save a model
    cloud.save_model("My Bridge", model.to_dict(include_results=False))

    # List your models
    for m in cloud.list_models():
        print(m["id"], m["name"])

    # Load a model
    data = cloud.load_model("model-id-here")

Usage with email + password::

    cloud = FersCloudClient()
    cloud.login("you@example.com", "password")

API keys are created in your FersCloud profile or via
``POST /api/sdk/api-keys``.  They persist until revoked.

When ``is_premium`` is True the authenticated user may run
unlimited solver calculations.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Any


DEFAULT_BASE_URL = "https://ferscloud.com"


class FersCloudError(Exception):
    """Base exception for FersCloud operations."""


class AuthenticationError(FersCloudError):
    """Raised when login fails or a token is invalid/expired."""


class CloudAPIError(FersCloudError):
    """Raised when a cloud API call fails."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class FersCloudClient:
    """Thin client for the FersCloud SDK API.

    Parameters
    ----------
    base_url : str
        The base URL of your FersCloud instance.
        Defaults to ``https://ferscloud.com``.
        For local development use ``http://localhost:3000``.
    """

    def __init__(self, base_url: str = DEFAULT_BASE_URL) -> None:
        self.base_url = base_url.rstrip("/")
        self._token: str | None = None
        self._api_key: str | None = None
        self._expires_at: datetime | None = None
        self._is_premium: bool = False
        self._user_id: str | None = None
        self._email: str | None = None

    # ── Properties ──────────────────────────────────────

    @property
    def is_authenticated(self) -> bool:
        """``True`` if a valid auth method is available (API key or non-expired token)."""
        if self._api_key is not None:
            return True
        if self._token is None or self._expires_at is None:
            return False
        return datetime.now(tz=timezone.utc) < self._expires_at

    @property
    def is_premium(self) -> bool:
        """``True`` if the authenticated user has a premium licence."""
        return self._is_premium

    @property
    def user_id(self) -> str | None:
        return self._user_id

    @property
    def email(self) -> str | None:
        return self._email

    @property
    def token_expires_at(self) -> datetime | None:
        return self._expires_at

    # ── Authentication ──────────────────────────────────

    def login(self, email: str, password: str) -> dict[str, Any]:
        """Authenticate with FersCloud and obtain a 1-hour SDK token.

        Parameters
        ----------
        email : str
            Your FersCloud account email.
        password : str
            Your FersCloud account password.

        Returns
        -------
        dict
            Response containing ``token``, ``expires_at``, ``is_premium``,
            and ``user`` info.

        Raises
        ------
        AuthenticationError
            If the credentials are invalid or the email is not verified.
        """
        data = self._post("/api/sdk/token", {"email": email, "password": password}, auth=False)
        self._token = data["token"]
        self._expires_at = datetime.fromisoformat(data["expires_at"])
        self._is_premium = data["is_premium"]
        self._user_id = data["user"]["id"]
        self._email = data["user"]["email"]
        return data

    def connect(self, api_key: str) -> dict[str, Any]:
        """Authenticate with a persistent API key.

        API keys are created in your FersCloud profile or via
        ``POST /api/sdk/api-keys``.  They persist until revoked.

        Parameters
        ----------
        api_key : str
            A FersCloud API key in ``{keyId}.{secret}`` format,
            e.g. ``"clxyz123.AbCdEfGhIjKlMnOpQrStUvWx"``.

        Returns
        -------
        dict
            User information: ``user_id``, ``email``, ``is_premium``.

        Raises
        ------
        AuthenticationError
            If the key is invalid, revoked, or expired.
        """
        self._api_key = api_key
        # Clear any previous JWT auth
        self._token = None
        self._expires_at = None
        try:
            data = self._get("/api/sdk/me")
        except (AuthenticationError, CloudAPIError):
            self._api_key = None
            raise
        self._is_premium = data.get("is_premium", False)
        self._user_id = data.get("user_id")
        self._email = data.get("email")
        return data

    def logout(self) -> None:
        """Clear all local credentials (token and API key)."""
        self._token = None
        self._api_key = None
        self._expires_at = None
        self._is_premium = False
        self._user_id = None
        self._email = None

    # ── Cloud Models ────────────────────────────────────

    def list_models(self) -> list[dict[str, Any]]:
        """Return a list of all cloud models for the authenticated user.

        Each dict contains ``id``, ``name``, ``description``,
        ``createdAt``, ``updatedAt``.
        """
        resp = self._get("/api/sdk/models")
        return resp["models"]

    def save_model(
        self,
        name: str,
        model_dict: dict[str, Any],
        description: str | None = None,
    ) -> dict[str, Any]:
        """Save a FERS model to the cloud.

        Parameters
        ----------
        name : str
            Display name for the cloud model.
        model_dict : dict
            The model data, typically from ``fers.to_dict(include_results=False)``.
        description : str, optional
            An optional description.

        Returns
        -------
        dict
            Created model metadata (``id``, ``name``, etc.).
        """
        payload: dict[str, Any] = {"name": name, "model": model_dict}
        if description is not None:
            payload["description"] = description
        return self._post("/api/sdk/models", payload)

    def load_model(self, model_id: str) -> dict[str, Any]:
        """Download a cloud model by its ID.

        Returns
        -------
        dict
            Contains ``id``, ``name``, ``description``, ``model`` (the
            full JSON dict), ``created_at``, ``updated_at``.
        """
        return self._get(f"/api/sdk/models/{model_id}")

    def update_model(
        self,
        model_id: str,
        *,
        name: str | None = None,
        description: str | None = None,
        model_dict: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Update an existing cloud model.

        Pass only the fields you want to change.
        """
        payload: dict[str, Any] = {}
        if name is not None:
            payload["name"] = name
        if description is not None:
            payload["description"] = description
        if model_dict is not None:
            payload["model"] = model_dict
        return self._put(f"/api/sdk/models/{model_id}", payload)

    def delete_model(self, model_id: str) -> None:
        """Delete a cloud model by its ID."""
        self._delete(f"/api/sdk/models/{model_id}")

    def check_token(self) -> dict[str, Any]:
        """Verify the current token and return user info.

        Returns
        -------
        dict
            Contains ``user_id``, ``email``, ``is_premium``,
            ``token_expires_at``.
        """
        return self._get("/api/sdk/me")

    # ── Internal HTTP helpers (stdlib only) ─────────────

    def _ensure_auth(self) -> None:
        if not self.is_authenticated:
            raise AuthenticationError(
                "Not authenticated or token expired. "
                "Call connect(api_key) or login(email, password) first."
            )

    def _headers(self, auth: bool = True) -> dict[str, str]:
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if auth:
            self._ensure_auth()
            if self._api_key is not None:
                headers["X-API-Key"] = self._api_key
            else:
                headers["Authorization"] = f"Bearer {self._token}"
        return headers

    def _request(
        self,
        method: str,
        path: str,
        body: dict[str, Any] | None = None,
        *,
        auth: bool = True,
    ) -> dict[str, Any] | None:
        url = f"{self.base_url}{path}"
        data = json.dumps(body).encode("utf-8") if body is not None else None
        req = urllib.request.Request(url, data=data, headers=self._headers(auth), method=method)

        try:
            with urllib.request.urlopen(req) as resp:
                if resp.status == 204:
                    return None
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            try:
                err_body = json.loads(exc.read().decode("utf-8"))
                msg = err_body.get("error", str(exc))
            except Exception:
                msg = str(exc)

            if exc.code == 401:
                raise AuthenticationError(msg) from exc
            raise CloudAPIError(msg, status_code=exc.code) from exc
        except urllib.error.URLError as exc:
            raise CloudAPIError(f"Cannot reach FersCloud at {self.base_url}: {exc.reason}") from exc

    def _get(self, path: str) -> dict[str, Any]:
        result = self._request("GET", path)
        assert result is not None
        return result

    def _post(self, path: str, body: dict[str, Any], *, auth: bool = True) -> dict[str, Any]:
        result = self._request("POST", path, body, auth=auth)
        assert result is not None
        return result

    def _put(self, path: str, body: dict[str, Any]) -> dict[str, Any]:
        result = self._request("PUT", path, body)
        assert result is not None
        return result

    def _delete(self, path: str) -> None:
        self._request("DELETE", path)
