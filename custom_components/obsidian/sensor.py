"""Sensor platform for the Obsidian integration."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import slugify

from .const import CONF_NOTES, CONF_URL, DOMAIN
from .coordinator import ObsidianCoordinator

_LOGGER = logging.getLogger(__name__)


def _flatten_frontmatter(
    data: dict[str, Any], prefix: str = ""
) -> dict[str, Any]:
    """Flatten nested frontmatter dict with dot notation keys."""
    items: dict[str, Any] = {}
    for key, value in data.items():
        full_key = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict):
            items.update(_flatten_frontmatter(value, full_key))
        else:
            items[full_key] = value
    return items


def _note_slug(note_path: str) -> str:
    """Create a slug from a note path."""
    name = note_path
    if name.endswith(".md"):
        name = name[:-3]
    return slugify(name.replace("/", "_"))


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Obsidian sensors from a config entry."""
    coordinator: ObsidianCoordinator = hass.data[DOMAIN][entry.entry_id]
    notes_config: dict[str, list[str]] = entry.options.get(CONF_NOTES, {})

    entities: list[ObsidianFrontmatterSensor] = []
    for note_path, fields in notes_config.items():
        for field_name in fields:
            entities.append(
                ObsidianFrontmatterSensor(
                    coordinator=coordinator,
                    entry=entry,
                    note_path=note_path,
                    field_name=field_name,
                )
            )

    async_add_entities(entities)


class ObsidianFrontmatterSensor(
    CoordinatorEntity[ObsidianCoordinator], SensorEntity
):
    """Sensor for a single frontmatter field of an Obsidian note."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: ObsidianCoordinator,
        entry: ConfigEntry,
        note_path: str,
        field_name: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._note_path = note_path
        self._field_name = field_name
        self._entry = entry

        note_slug = _note_slug(note_path)
        field_slug = slugify(field_name)

        self._attr_unique_id = f"{entry.entry_id}_{note_slug}_{field_slug}"
        self._attr_name = field_name
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{entry.entry_id}_{note_slug}")},
            name=f"Obsidian: {note_path}",
            entry_type=DeviceEntryType.SERVICE,
            manufacturer="Obsidian",
            model="Vault Note",
            configuration_url=entry.data.get(CONF_URL),
        )

    @property
    def native_value(self) -> str | None:
        """Return the current value of the frontmatter field."""
        note_data = self._get_note_data()
        if note_data is None:
            return None
        frontmatter = note_data.get("frontmatter", {})
        flat = _flatten_frontmatter(frontmatter)
        value = flat.get(self._field_name)
        if value is None:
            return None
        if isinstance(value, list):
            return ", ".join(str(v) for v in value)
        return str(value)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional attributes."""
        attrs: dict[str, Any] = {
            "note_path": self._note_path,
            "field_name": self._field_name,
            "vault_url": self._entry.data.get(CONF_URL),
        }
        note_data = self._get_note_data()
        if note_data is not None:
            attrs["note_tags"] = note_data.get("tags", [])
            stat = note_data.get("stat", {})
            if "mtime" in stat:
                attrs["last_modified"] = stat["mtime"]
        return attrs

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.async_write_ha_state()

    def _get_note_data(self) -> dict[str, Any] | None:
        """Get the note data from the coordinator."""
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.get(self._note_path)
