# Radarr MCP Server

This server provides a set of tools to interact with a Radarr instance using the Model Context Protocol (MCP). It is built with FastMCP and allows for managing movies, quality profiles, and download queues, all based on the Radarr API v3.

## Implemented Tools

1.  `get_movies()`: Retrieves all movies in the Radarr library with monitoring and download status.
2.  `lookup_movie(term)`: Searches TMDB for movies via Radarr.
3.  `add_movie(tmdb_id, title, quality_profile_id, root_folder_path, ...)`: Adds a new movie to Radarr.
4.  `get_queue()`: Retrieves the active download queue.
5.  `get_quality_profiles()`: Lists available quality profiles.
6.  `get_root_folders()`: Lists configured root folder paths.
7.  `get_system_status()`: Retrieves Radarr system status and health information.

## Quick Start

### Prerequisites
- Python 3.10+
- An operational Radarr instance (v3 API compatible).

### Setup

1.  **Set up environment variables** in the `yarr-mcp` project root `.env`:

    ```env
    RADARR_URL=http://your-radarr-host:7878
    RADARR_API_KEY=your_radarr_api_key_here

    RADARR_MCP_TRANSPORT=sse
    RADARR_MCP_HOST=0.0.0.0
    RADARR_MCP_PORT=6975
    RADARR_MCP_LOG_LEVEL=INFO
    ```
    The API key can be found in Radarr under Settings > General.

### Running the Server

```bash
python src/radarr-mcp/radarr-mcp-server.py
```
The server will start using SSE transport on `0.0.0.0:6975/mcp` by default.

## Client Configuration

```json
{
  "mcpServers": {
    "radarr-mcp": {
      "url": "http://localhost:6975/mcp",
      "timeout": 30
    }
  }
}
```
