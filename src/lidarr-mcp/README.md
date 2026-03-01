# Lidarr MCP Server

This server provides a set of tools to interact with a Lidarr instance using the Model Context Protocol (MCP). It is built with FastMCP and allows for managing music artists, albums, quality/metadata profiles, and download queues, all based on the Lidarr API v1.

## Implemented Tools

1.  `get_artists()`: Retrieves all artists in the Lidarr library with monitoring status.
2.  `lookup_artist(term)`: Searches MusicBrainz for artists via Lidarr.
3.  `add_artist(foreign_artist_id, artist_name, quality_profile_id, metadata_profile_id, root_folder_path, ...)`: Adds a new artist to Lidarr.
4.  `get_albums(artist_id)`: Retrieves all albums for a given artist.
5.  `get_queue()`: Retrieves the active download queue.
6.  `get_quality_profiles()`: Lists available quality profiles.
7.  `get_metadata_profiles()`: Lists available metadata profiles (Lidarr-specific).
8.  `get_root_folders()`: Lists configured root folder paths.
9.  `get_system_status()`: Retrieves Lidarr system status and health information.

## Quick Start

### Prerequisites
- Python 3.10+
- An operational Lidarr instance (v1 API compatible).

### Setup

1.  **Set up environment variables** in the `yarr-mcp` project root `.env`:

    ```env
    LIDARR_URL=http://your-lidarr-host:8686
    LIDARR_API_KEY=your_lidarr_api_key_here

    LIDARR_MCP_TRANSPORT=sse
    LIDARR_MCP_HOST=0.0.0.0
    LIDARR_MCP_PORT=6976
    LIDARR_MCP_LOG_LEVEL=INFO
    ```
    The API key can be found in Lidarr under Settings > General.

### Running the Server

```bash
python src/lidarr-mcp/lidarr-mcp-server.py
```
The server will start using SSE transport on `0.0.0.0:6976/mcp` by default.

## Client Configuration

```json
{
  "mcpServers": {
    "lidarr-mcp": {
      "url": "http://localhost:6976/mcp",
      "timeout": 30
    }
  }
}
```
