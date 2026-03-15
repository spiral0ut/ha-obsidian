# Obsidian Integration for Home Assistant

A HACS-compatible custom component that connects Home Assistant to your [Obsidian](https://obsidian.md) vault via the [Local REST API](https://github.com/coddingtonbear/obsidian-local-rest-api) plugin. Expose frontmatter fields from your notes as Home Assistant sensors.

## Features

- Monitor frontmatter fields from any note in your Obsidian vault
- Each field becomes a separate sensor entity in Home Assistant
- Sensors grouped by note as devices
- Support for nested frontmatter (flattened with dot notation)
- Configurable polling interval
- Full UI-based configuration (no YAML needed)
- Options flow to add/remove notes and fields after setup

## Prerequisites

1. **Obsidian** with the [Local REST API](https://github.com/coddingtonbear/obsidian-local-rest-api) plugin installed and enabled
2. Note the API key from the plugin settings (Settings > Local REST API > API Key)
3. Note the URL (default: `https://localhost:27124` for HTTPS or `http://localhost:27123` for HTTP)

## Installation

### HACS (Recommended)

1. Open HACS in your Home Assistant instance
2. Click the three dots in the top right corner and select **Custom repositories**
3. Add the repository URL and select **Integration** as the category
4. Click **Add**
5. Search for "Obsidian" in HACS and install it
6. Restart Home Assistant

### Manual Installation

1. Copy the `custom_components/obsidian` directory into your Home Assistant `config/custom_components/` directory
2. Restart Home Assistant

## Configuration

1. Go to **Settings > Devices & Services > Add Integration**
2. Search for **Obsidian**
3. Enter your connection details:
   - **URL**: The Obsidian Local REST API URL (e.g., `https://192.168.1.100:27124`)
   - **API Key**: Your API key from the plugin settings
   - **Verify SSL**: Disable if using self-signed certificates (default: off)
   - **Update interval**: How often to poll for changes in seconds (default: 30)
4. Select which notes to monitor from your vault
5. For each note, select which frontmatter fields to expose as sensors

## Sensors

Each selected frontmatter field creates a sensor with:

- **State**: The current value of the frontmatter field (as a string)
- **Attributes**:
  - `note_path`: Full path of the note in the vault
  - `field_name`: Original frontmatter field name
  - `note_tags`: Tags from the note
  - `last_modified`: Note modification timestamp
  - `vault_url`: The configured Obsidian URL

### Entity ID Format

`sensor.obsidian_<note_name>_<field_name>`

For example, a note at `projects/myproject.md` with a frontmatter field `status` would create:
`sensor.obsidian_projects_myproject_status`

### Nested Frontmatter

Nested frontmatter is flattened with dot notation. For example:

```yaml
---
metadata:
  author: John
  version: 2
---
```

Creates fields `metadata.author` and `metadata.version`.

## Reconfiguring

Go to **Settings > Devices & Services**, find the Obsidian integration, and click **Configure** to:

- Change the polling interval
- Add or remove monitored notes
- Add or remove monitored frontmatter fields

## Troubleshooting

- **Cannot connect**: Ensure the Obsidian Local REST API plugin is running and the URL is reachable from your Home Assistant instance
- **Invalid API key**: Check the API key in Obsidian Settings > Local REST API
- **SSL errors**: If using HTTPS with the default self-signed certificate, make sure "Verify SSL" is disabled
- **Missing frontmatter**: Ensure your notes have valid YAML frontmatter between `---` markers
