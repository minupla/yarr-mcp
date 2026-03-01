# Audiobookshelf MCP Server 📚

An MCP server for interacting with an [Audiobookshelf](https://www.audiobookshelf.org/) instance. Browse libraries, search for audiobooks, track and sync playback progress, and view listening statistics.

## Key Feature: Progress Sync

The `update_progress` tool enables syncing playback position from external players (e.g., Listen audiobook player on Android). This is the primary use case — keeping your Audiobookshelf progress in sync regardless of which player you use.

## Tools

### Library Browsing
| Tool | Description |
|------|-------------|
| `get_libraries` | List all libraries with id, name, and mediaType |
| `get_library_items` | List items in a library with title, author, duration, progress (paginated) |
| `search_library` | Search a library by title or author |
| `get_item` | Get full item details including chapters |

### Progress / Playback Position
| Tool | Description |
|------|-------------|
| `get_progress` | Get current playback position for an item |
| `update_progress` | Update playback position (sync from external players) |
| `get_all_progress` | Get all items currently in progress |

### Listening Sessions & Stats
| Tool | Description |
|------|-------------|
| `get_listening_sessions` | Get recent listening sessions |
| `get_listening_stats` | Get total listen time, books finished, etc. |
| `get_in_progress` | Shorthand for currently listening items |

## Configuration

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `ABS_URL` | Yes | — | Audiobookshelf server URL |
| `ABS_TOKEN` | Yes | — | API Bearer token |
| `ABS_MCP_TRANSPORT` | No | `sse` | Transport: `sse` or `stdio` |
| `ABS_MCP_HOST` | No | `0.0.0.0` | Host to bind to |
| `ABS_MCP_PORT` | No | `6977` | Port for SSE transport |
| `ABS_MCP_LOG_LEVEL` | No | `INFO` | Log level |

### Getting an API Token

1. Log in to your Audiobookshelf instance
2. Go to Settings → Users → Select your user
3. Copy the API token, or generate one via the API:
   ```bash
   curl -X POST https://your-abs-url/login \
     -H "Content-Type: application/json" \
     -d '{"username": "your_user", "password": "your_pass"}'
   ```

## Running

```bash
# From yarr-mcp project root
python src/audiobookshelf-mcp/audiobookshelf-mcp-server.py
```

Default SSE endpoint: `http://localhost:6977/mcp`

## API Reference

Based on the [Audiobookshelf API](https://api.audiobookshelf.org/).
