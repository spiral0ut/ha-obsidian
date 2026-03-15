"""Config flow for the Obsidian integration."""

from __future__ import annotations

import logging
from typing import Any

import aiohttp
import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    BooleanSelector,
)

from .api import ObsidianApi, ObsidianApiError, ObsidianAuthError
from .const import (
    CONF_API_KEY,
    CONF_NOTES,
    CONF_SCAN_INTERVAL,
    CONF_URL,
    CONF_VERIFY_SSL,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_VERIFY_SSL,
    DOMAIN,
)

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


class ObsidianConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Obsidian."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._url: str = ""
        self._api_key: str = ""
        self._verify_ssl: bool = DEFAULT_VERIFY_SSL
        self._scan_interval: int = DEFAULT_SCAN_INTERVAL
        self._api: ObsidianApi | None = None
        self._available_files: list[str] = []
        self._selected_notes: list[str] = []
        self._notes_config: dict[str, list[str]] = {}
        self._current_note_index: int = 0

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial connection step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self._url = user_input[CONF_URL].rstrip("/")
            self._api_key = user_input[CONF_API_KEY]
            self._verify_ssl = user_input.get(CONF_VERIFY_SSL, DEFAULT_VERIFY_SSL)
            self._scan_interval = user_input.get(
                CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
            )

            session = async_get_clientsession(
                self.hass, verify_ssl=self._verify_ssl
            )
            self._api = ObsidianApi(
                session, self._url, self._api_key, self._verify_ssl
            )

            try:
                await self._api.test_connection()
            except ObsidianAuthError:
                errors["base"] = "invalid_auth"
            except ObsidianApiError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected error during connection test")
                errors["base"] = "unknown"
            else:
                try:
                    self._available_files = await self._api.list_vault_files()
                except ObsidianApiError:
                    errors["base"] = "cannot_connect"
                else:
                    return await self.async_step_select_notes()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_URL, default="https://localhost:27124"
                    ): TextSelector(
                        TextSelectorConfig(type=TextSelectorType.URL)
                    ),
                    vol.Required(CONF_API_KEY): TextSelector(
                        TextSelectorConfig(type=TextSelectorType.PASSWORD)
                    ),
                    vol.Optional(
                        CONF_VERIFY_SSL, default=DEFAULT_VERIFY_SSL
                    ): BooleanSelector(),
                    vol.Optional(
                        CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL
                    ): NumberSelector(
                        NumberSelectorConfig(
                            min=5, max=3600, step=1, mode=NumberSelectorMode.BOX
                        )
                    ),
                }
            ),
            errors=errors,
        )

    def _notes_selector(self) -> SelectSelector:
        """Build a multi-select selector for vault notes."""
        options = [
            SelectOptionDict(value=f, label=f) for f in self._available_files
        ]
        return SelectSelector(
            SelectSelectorConfig(
                options=options,
                multiple=True,
                mode=SelectSelectorMode.DROPDOWN,
            )
        )

    async def async_step_select_notes(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle note selection step."""
        if user_input is not None:
            self._selected_notes = user_input.get("notes", [])
            if not self._selected_notes:
                return self.async_show_form(
                    step_id="select_notes",
                    data_schema=vol.Schema(
                        {vol.Required("notes"): self._notes_selector()}
                    ),
                    errors={"base": "no_notes_selected"},
                )
            self._current_note_index = 0
            self._notes_config = {}
            return await self.async_step_select_fields()

        return self.async_show_form(
            step_id="select_notes",
            data_schema=vol.Schema(
                {vol.Required("notes"): self._notes_selector()}
            ),
        )

    async def async_step_select_fields(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle field selection for a single note."""
        if user_input is not None:
            note_path = self._selected_notes[self._current_note_index]
            selected = user_input.get("fields", [])
            if selected:
                self._notes_config[note_path] = selected
            self._current_note_index += 1
            if self._current_note_index < len(self._selected_notes):
                return await self.async_step_select_fields()
            return self._create_entry()

        note_path = self._selected_notes[self._current_note_index]

        assert self._api is not None
        try:
            note_data = await self._api.get_note(note_path)
        except ObsidianApiError:
            _LOGGER.warning("Could not fetch frontmatter for %s", note_path)
            self._current_note_index += 1
            if self._current_note_index < len(self._selected_notes):
                return await self.async_step_select_fields()
            return self._create_entry()

        frontmatter = note_data.get("frontmatter", {})
        if not frontmatter:
            self._current_note_index += 1
            if self._current_note_index < len(self._selected_notes):
                return await self.async_step_select_fields()
            return self._create_entry()

        flat = _flatten_frontmatter(frontmatter)
        field_options = [
            SelectOptionDict(value=k, label=f"{k} = {v}")
            for k, v in flat.items()
        ]
        field_selector = SelectSelector(
            SelectSelectorConfig(
                options=field_options,
                multiple=True,
                mode=SelectSelectorMode.DROPDOWN,
            )
        )

        return self.async_show_form(
            step_id="select_fields",
            data_schema=vol.Schema(
                {vol.Required("fields"): field_selector}
            ),
            description_placeholders={"note_path": note_path},
        )

    def _create_entry(self) -> ConfigFlowResult:
        """Create the config entry."""
        if not self._notes_config:
            return self.async_abort(reason="no_fields_selected")

        return self.async_create_entry(
            title=f"Obsidian ({self._url})",
            data={
                CONF_URL: self._url,
                CONF_API_KEY: self._api_key,
                CONF_VERIFY_SSL: self._verify_ssl,
            },
            options={
                CONF_SCAN_INTERVAL: self._scan_interval,
                CONF_NOTES: self._notes_config,
            },
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> ObsidianOptionsFlow:
        """Get the options flow handler."""
        return ObsidianOptionsFlow()


class ObsidianOptionsFlow(OptionsFlow):
    """Handle options for the Obsidian integration."""

    def __init__(self) -> None:
        """Initialize options flow."""
        self._api: ObsidianApi | None = None
        self._available_files: list[str] = []
        self._selected_notes: list[str] = []
        self._notes_config: dict[str, list[str]] = {}
        self._current_note_index: int = 0
        self._scan_interval: int = DEFAULT_SCAN_INTERVAL

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            scan_interval = user_input.get(
                CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
            )
            session = async_get_clientsession(
                self.hass,
                verify_ssl=self.config_entry.data.get(
                    CONF_VERIFY_SSL, DEFAULT_VERIFY_SSL
                ),
            )
            self._api = ObsidianApi(
                session,
                self.config_entry.data[CONF_URL],
                self.config_entry.data[CONF_API_KEY],
                self.config_entry.data.get(CONF_VERIFY_SSL, DEFAULT_VERIFY_SSL),
            )
            try:
                self._available_files = await self._api.list_vault_files()
            except ObsidianApiError:
                return self.async_show_form(
                    step_id="init",
                    data_schema=vol.Schema(
                        {
                            vol.Optional(
                                CONF_SCAN_INTERVAL,
                                default=self.config_entry.options.get(
                                    CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
                                ),
                            ): NumberSelector(
                                NumberSelectorConfig(
                                    min=5, max=3600, step=1,
                                    mode=NumberSelectorMode.BOX,
                                )
                            ),
                        }
                    ),
                    errors={"base": "cannot_connect"},
                )

            self._scan_interval = scan_interval
            return await self.async_step_select_notes()

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_SCAN_INTERVAL,
                        default=self.config_entry.options.get(
                            CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
                        ),
                    ): NumberSelector(
                        NumberSelectorConfig(
                            min=5, max=3600, step=1,
                            mode=NumberSelectorMode.BOX,
                        )
                    ),
                }
            ),
        )

    def _notes_selector(self) -> SelectSelector:
        """Build a multi-select selector for vault notes."""
        options = [
            SelectOptionDict(value=f, label=f) for f in self._available_files
        ]
        return SelectSelector(
            SelectSelectorConfig(
                options=options,
                multiple=True,
                mode=SelectSelectorMode.DROPDOWN,
            )
        )

    async def async_step_select_notes(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle note selection in options."""
        if user_input is not None:
            self._selected_notes = user_input.get("notes", [])
            if not self._selected_notes:
                return self.async_show_form(
                    step_id="select_notes",
                    data_schema=vol.Schema(
                        {vol.Required("notes"): self._notes_selector()}
                    ),
                    errors={"base": "no_notes_selected"},
                )
            self._current_note_index = 0
            self._notes_config = {}
            return await self.async_step_select_fields()

        current_notes = list(
            self.config_entry.options.get(CONF_NOTES, {}).keys()
        )

        return self.async_show_form(
            step_id="select_notes",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        "notes", default=current_notes
                    ): self._notes_selector(),
                }
            ),
        )

    async def async_step_select_fields(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle field selection for a single note in options."""
        if user_input is not None:
            note_path = self._selected_notes[self._current_note_index]
            selected = user_input.get("fields", [])
            if selected:
                self._notes_config[note_path] = selected
            self._current_note_index += 1
            if self._current_note_index < len(self._selected_notes):
                return await self.async_step_select_fields()
            return self.async_create_entry(
                data={
                    CONF_SCAN_INTERVAL: self._scan_interval,
                    CONF_NOTES: self._notes_config,
                },
            )

        note_path = self._selected_notes[self._current_note_index]

        assert self._api is not None
        try:
            note_data = await self._api.get_note(note_path)
        except ObsidianApiError:
            self._current_note_index += 1
            if self._current_note_index < len(self._selected_notes):
                return await self.async_step_select_fields()
            return self.async_create_entry(
                data={
                    CONF_SCAN_INTERVAL: self._scan_interval,
                    CONF_NOTES: self._notes_config,
                },
            )

        frontmatter = note_data.get("frontmatter", {})
        if not frontmatter:
            self._current_note_index += 1
            if self._current_note_index < len(self._selected_notes):
                return await self.async_step_select_fields()
            return self.async_create_entry(
                data={
                    CONF_SCAN_INTERVAL: self._scan_interval,
                    CONF_NOTES: self._notes_config,
                },
            )

        flat = _flatten_frontmatter(frontmatter)
        field_options = [
            SelectOptionDict(value=k, label=f"{k} = {v}")
            for k, v in flat.items()
        ]
        field_selector = SelectSelector(
            SelectSelectorConfig(
                options=field_options,
                multiple=True,
                mode=SelectSelectorMode.DROPDOWN,
            )
        )

        current_fields = self.config_entry.options.get(CONF_NOTES, {}).get(
            note_path, []
        )

        return self.async_show_form(
            step_id="select_fields",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        "fields", default=current_fields
                    ): field_selector,
                }
            ),
            description_placeholders={"note_path": note_path},
        )
