"""Obsidian Local REST API client."""

from __future__ import annotations

import ssl
from typing import Any

import aiohttp

from .const import ACCEPT_JSON


class ObsidianApiError(Exception):
    """Base exception for Obsidian API errors."""


class ObsidianAuthError(ObsidianApiError):
    """Authentication error."""


class ObsidianConnectionError(ObsidianApiError):
    """Connection error."""


class ObsidianApi:
    """Client for the Obsidian Local REST API plugin."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        url: str,
        api_key: str,
        verify_ssl: bool = False,
    ) -> None:
        """Initialize the API client."""
        self._session = session
        self._url = url.rstrip("/")
        self._api_key = api_key
        self._ssl: bool | ssl.SSLContext = verify_ssl
        if not verify_ssl:
            self._ssl = False

    @property
    def _headers(self) -> dict[str, str]:
        """Return default headers."""
        return {"Authorization": f"Bearer {self._api_key}"}

    async def _request(
        self,
        method: str,
        path: str,
        headers: dict[str, str] | None = None,
        **kwargs: Any,
    ) -> aiohttp.ClientResponse:
        """Make an API request."""
        url = f"{self._url}{path}"
        req_headers = self._headers
        if headers:
            req_headers.update(headers)
        try:
            resp = await self._session.request(
                method, url, headers=req_headers, ssl=self._ssl, **kwargs
            )
        except aiohttp.ClientConnectorError as err:
            raise ObsidianConnectionError(
                f"Cannot connect to Obsidian at {self._url}: {err}"
            ) from err
        except aiohttp.ClientError as err:
            raise ObsidianApiError(f"API request failed: {err}") from err

        if resp.status == 401:
            raise ObsidianAuthError("Invalid API key")
        if resp.status == 404:
            raise ObsidianApiError(f"Not found: {path}")
        resp.raise_for_status()
        return resp

    async def test_connection(self) -> bool:
        """Test the connection to the Obsidian REST API."""
        resp = await self._request("GET", "/vault/")
        await resp.release()
        return True

    async def list_vault_files(self) -> list[str]:
        """List all files in the vault."""
        resp = await self._request("GET", "/vault/")
        data = await resp.json()
        return [f for f in data.get("files", []) if f.endswith(".md")]

    async def get_note(self, path: str) -> dict[str, Any]:
        """Get a note with its frontmatter metadata."""
        resp = await self._request(
            "GET",
            f"/vault/{path}",
            headers={"Accept": ACCEPT_JSON},
        )
        return await resp.json()
