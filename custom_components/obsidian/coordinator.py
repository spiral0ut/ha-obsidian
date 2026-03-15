"""DataUpdateCoordinator for the Obsidian integration."""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import ObsidianApi, ObsidianApiError

_LOGGER = logging.getLogger(__name__)


class ObsidianCoordinator(DataUpdateCoordinator[dict[str, dict[str, Any]]]):
    """Coordinator to fetch data from Obsidian for all configured notes."""

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        api: ObsidianApi,
        notes: dict[str, list[str]],
        scan_interval: int,
    ) -> None:
        """Initialize the coordinator.

        Args:
            hass: HomeAssistant instance.
            api: Obsidian API client.
            notes: Mapping of note path -> list of frontmatter field names.
            scan_interval: Polling interval in seconds.
        """
        super().__init__(
            hass,
            _LOGGER,
            name="Obsidian",
            update_interval=timedelta(seconds=scan_interval),
        )
        self.api = api
        self.notes = notes

    async def _async_update_data(self) -> dict[str, dict[str, Any]]:
        """Fetch data for all configured notes."""
        data: dict[str, dict[str, Any]] = {}
        errors: list[str] = []

        for note_path in self.notes:
            try:
                note_data = await self.api.get_note(note_path)
                data[note_path] = note_data
            except ObsidianApiError as err:
                _LOGGER.warning("Failed to fetch note %s: %s", note_path, err)
                errors.append(note_path)

        if errors and not data:
            raise UpdateFailed(
                f"Failed to fetch all configured notes: {', '.join(errors)}"
            )

        return data
