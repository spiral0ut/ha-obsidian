"""Constants for the Obsidian integration."""

from typing import Final

DOMAIN: Final = "obsidian"

CONF_API_KEY: Final = "api_key"
CONF_URL: Final = "url"
CONF_VERIFY_SSL: Final = "verify_ssl"
CONF_SCAN_INTERVAL: Final = "scan_interval"
CONF_NOTES: Final = "notes"

DEFAULT_SCAN_INTERVAL: Final = 30
DEFAULT_VERIFY_SSL: Final = False

ACCEPT_JSON: Final = "application/vnd.olrapi.note+json"
