# Sonarr MCP Server

This server provides a set of tools to interact with a Sonarr instance using the Model Context Protocol (MCP). It is built with FastMCP and allows for managing TV series, episodes, quality profiles, and download queues, all based on the Sonarr API v3.

## Design Rationale

The tools were chosen to expose core Sonarr functionalities for TV show management via an MCP-compatible client. The selection covers series library management, episode tracking, quality profile configuration, and download queue monitoring.

Key considerations:
- **Comprehensive Coverage**: Series management, episode tracking, quality profiles, root folders, queue, and system status.
- **User-Friendliness**: Human-readable summaries with full JSON data for programmatic use.
- **Configuration**: Environment variables for Sonarr API URL/Key and MCP server settings.
- **Transport**: Defaults to SSE for remote accessibility.

## Implemented Tools

1.  `get_series()`: Retrieves all series in the Sonarr library with monitoring status.
2.  `lookup_series(term)`: Searches TVDB for TV series via Sonarr.
3.  `add_series(tvdb_id, title, quality_profile_id, root_folder_path, ...)`: Adds a new TV series to Sonarr.
4.  `get_episodes(series_id)`: Retrieves all episodes for a given series.
5.  `get_season_status(series_id)`: Gets download status per season for a series.
6.  `get_queue()`: Retrieves the active download queue.
7.  `get_quality_profiles()`: Lists available quality profiles.
8.  `get_root_folders()`: Lists configured root folder paths.
9.  `get_system_status()`: Retrieves Sonarr system status and health information.

## Quick Start

### Prerequisites
- Python 3.10+
- An operational Sonarr instance (v3 API compatible).
- `uv` (recommended for package management within the `yarr-mcp` project).

### Installation

1.  **Clone the `yarr-mcp` repository (if you haven't already):**
    ```bash
    git clone https://github.com/jmagar/yarr-mcp.git
    cd yarr-mcp
    ```

2.  **Install dependencies:**
    ```bash
    source .venv/bin/activate
    ```

3.  **Set up environment variables:**
    Create or update a `.env` file in the `yarr-mcp` project root.
    Refer to `src/sonarr-mcp/.env.example` for all available options:

    ```env
    SONARR_URL=http://your-sonarr-host:8989
    SONARR_API_KEY=your_sonarr_api_key_here

    SONARR_MCP_TRANSPORT=sse
    SONARR_MCP_HOST=0.0.0.0
    SONARR_MCP_PORT=6974
    SONARR_MCP_LOG_LEVEL=INFO
    SONARR_MCP_LOG_FILE=sonarr_mcp.log
    ```
    The API key can be found in Sonarr under Settings > General.

### Running the Server

From the `yarr-mcp` project root:
```bash
python src/sonarr-mcp/sonarr-mcp-server.py
```
The server will start using SSE transport on `0.0.0.0:6974/mcp` by default.

## Client Configuration

### SSE (Default)
```json
{
  "mcpServers": {
    "sonarr-mcp": {
      "url": "http://localhost:6974/mcp",
      "timeout": 30
    }
  }
}
```

### STDIO
Set `SONARR_MCP_TRANSPORT=stdio` and configure your client with:
```json
{
  "name": "Sonarr (yarr-mcp)",
  "command": ["python", "src/sonarr-mcp/sonarr-mcp-server.py"],
  "working_directory": "/path/to/yarr-mcp"
}
```

## Troubleshooting

1.  **401 Unauthorized**: Verify `SONARR_URL` and `SONARR_API_KEY` are correct.
2.  **Connection issues**: Ensure the server is running and accessible. Check firewalls.
3.  **Tool failures**: Check server logs (`sonarr_mcp.log`) for detailed errors.
